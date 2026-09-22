#include "rm65_teleop_adapter/adapter_logic.hpp"
#include "rm65_teleop_adapter/quest_input_deadman.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <functional>
#include <iomanip>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "geometry_msgs/msg/pose.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "quest2ros/msg/ovr2_ros_inputs.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rm_ros_interfaces/msg/cartepos.hpp"
#include "std_msgs/msg/empty.hpp"
#include "std_msgs/msg/string.hpp"
#include "std_srvs/srv/trigger.hpp"

namespace rm65_teleop_adapter
{
namespace
{
using SteadyClock = std::chrono::steady_clock;

Pose3 from_ros_pose(const geometry_msgs::msg::Pose & pose)
{
  Pose3 result;
  result.position = {pose.position.x, pose.position.y, pose.position.z};
  result.orientation = {pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w};
  return result;
}

geometry_msgs::msg::Pose to_ros_pose(const Pose3 & pose)
{
  geometry_msgs::msg::Pose result;
  result.position.x = pose.position[0];
  result.position.y = pose.position[1];
  result.position.z = pose.position[2];
  result.orientation.x = pose.orientation.x;
  result.orientation.y = pose.orientation.y;
  result.orientation.z = pose.orientation.z;
  result.orientation.w = pose.orientation.w;
  return result;
}

template<typename TimePointT>
bool is_fresh(bool received, const TimePointT & stamp, double timeout_seconds)
{
  if (!received) return false;
  return std::chrono::duration<double>(SteadyClock::now() - stamp).count() <= timeout_seconds;
}

bool finite_position(const geometry_msgs::msg::PoseStamped & pose)
{
  return std::isfinite(pose.pose.position.x) && std::isfinite(pose.pose.position.y) &&
         std::isfinite(pose.pose.position.z);
}
}  // namespace

class AdapterNode : public rclcpp::Node
{
public:
  AdapterNode() : Node("rm65_teleop_adapter")
  {
    dry_run_ = declare_parameter<bool>("dry_run", true);
    hardware_write_enabled_ = declare_parameter<bool>("hardware_write_enabled", false);
    mapping_verified_ = declare_parameter<bool>("mapping_verified", false);
    if (dry_run_ && hardware_write_enabled_) {
      throw std::invalid_argument("dry_run=true requires hardware_write_enabled=false");
    }
    if (!dry_run_ && (!hardware_write_enabled_ || !mapping_verified_)) {
      throw std::invalid_argument(
              "hardware mode requires dry_run=false, hardware_write_enabled=true and mapping_verified=true");
    }
    hardware_mode_ = !dry_run_ && hardware_write_enabled_ && mapping_verified_;

    AdapterConfig config;
    config.translation_scale = declare_parameter<double>("translation_scale", 1.0);
    config.max_velocity_mps = declare_parameter<double>("max_velocity_mps", 0.01);
    config.max_step_m = declare_parameter<double>("max_step_m", 0.0001);
    config.max_anchor_distance_m = declare_parameter<double>("max_anchor_distance_m", 0.03);
    config.unexpected_target_jump_m = declare_parameter<double>("unexpected_target_jump_m", 0.10);
    const auto mapping = declare_parameter<std::vector<double>>(
      "mapping", {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0});
    const auto workspace_min = declare_parameter<std::vector<double>>(
      "workspace_min", {-1.0, -1.0, 0.0});
    const auto workspace_max = declare_parameter<std::vector<double>>(
      "workspace_max", {1.0, 1.0, 1.5});
    if (mapping.size() != 9 || workspace_min.size() != 3 || workspace_max.size() != 3) {
      throw std::invalid_argument("mapping must contain 9 values and workspace bounds 3 values");
    }
    std::copy(mapping.begin(), mapping.end(), config.mapping.begin());
    std::copy(workspace_min.begin(), workspace_min.end(), config.workspace_min.begin());
    std::copy(workspace_max.begin(), workspace_max.end(), config.workspace_max.begin());
    logic_ = std::make_unique<AdapterLogic>(config);

    target_timeout_ = declare_parameter<double>("target_timeout", 0.20);
    quest_pose_timeout_ = declare_parameter<double>("quest_pose_timeout", 0.20);
    inputs_timeout_ = declare_parameter<double>("inputs_timeout", 0.20);
    robot_timeout_ = declare_parameter<double>("robot_timeout", 0.10);
    max_control_period_ = declare_parameter<double>("max_control_period", 0.010);
    follow_ = declare_parameter<bool>("follow", true);
    stop_repeat_count_ = declare_parameter<int>("stop_repeat_count", 3);
    const double control_rate_hz = declare_parameter<double>("control_rate_hz", 200.0);
    preview_frame_id_ = declare_parameter<std::string>("preview_frame_id", "right_rm65_base");
    if (!std::isfinite(control_rate_hz) || control_rate_hz <= 0.0 ||
      !std::isfinite(max_control_period_) || max_control_period_ <= 0.0)
    {
      throw std::invalid_argument("control rate and maximum period must be positive and finite");
    }

    const auto target_topic = declare_parameter<std::string>("target_topic", "/quest_right_target_pose");
    const auto quest_pose_topic = declare_parameter<std::string>("quest_pose_topic", "/q2r_right_hand_pose");
    const auto inputs_topic = declare_parameter<std::string>("inputs_topic", "/q2r_right_hand_inputs");
    const auto robot_pose_topic = declare_parameter<std::string>(
      "robot_pose_topic", "/right/rm_driver/udp_arm_position");
    command_topic_ = declare_parameter<std::string>(
      "command_topic", "/right/rm_driver/movep_canfd_cmd");
    stop_topic_ = declare_parameter<std::string>(
      "stop_topic", "/right/rm_driver/move_stop_cmd");

    preview_publisher_ = create_publisher<geometry_msgs::msg::PoseStamped>(
      "/right/rm65_teleop/preview_target_pose", 10);
    status_publisher_ = create_publisher<std_msgs::msg::String>(
      "/right/rm65_teleop/status", 10);
    if (hardware_mode_) {
      command_publisher_ = create_publisher<rm_ros_interfaces::msg::Cartepos>(command_topic_, 10);
      stop_publisher_ = create_publisher<std_msgs::msg::Empty>(stop_topic_, 10);
    }

    target_subscription_ = create_subscription<geometry_msgs::msg::PoseStamped>(
      target_topic, 10, [this](geometry_msgs::msg::PoseStamped::SharedPtr message) {
        target_pose_ = *message;
        target_received_ = true;
        target_valid_ = finite_position(*message);
        target_time_ = SteadyClock::now();
      });
    quest_pose_subscription_ = create_subscription<geometry_msgs::msg::PoseStamped>(
      quest_pose_topic, 10, [this](geometry_msgs::msg::PoseStamped::SharedPtr message) {
        quest_pose_received_ = true;
        quest_pose_valid_ = finite_position(*message);
        quest_pose_time_ = SteadyClock::now();
      });
    inputs_subscription_ = create_subscription<quest2ros::msg::OVR2ROSInputs>(
      inputs_topic, 10, [this](quest2ros::msg::OVR2ROSInputs::SharedPtr message) {
        deadman_pressed_ = input_deadman_.update(*message);
        inputs_received_ = true;
        inputs_time_ = SteadyClock::now();
      });
    robot_pose_subscription_ = create_subscription<geometry_msgs::msg::Pose>(
      robot_pose_topic, 10, [this](geometry_msgs::msg::Pose::SharedPtr message) {
        robot_pose_ = *message;
        robot_received_ = true;
        robot_time_ = SteadyClock::now();
      });

    clear_fault_service_ = create_service<std_srvs::srv::Trigger>(
      "/right/rm65_teleop/clear_fault",
      [this](const std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response) {
        response->success = logic_->clear_fault(deadman_pressed_);
        response->message = response->success ?
          "fault cleared; release-to-press rearm still required" :
          "clear rejected: no fault or deadman is pressed";
      });

    const auto period = std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::duration<double>(1.0 / control_rate_hz));
    last_cycle_time_ = SteadyClock::now();
    last_status_time_ = last_cycle_time_;
    control_timer_ = create_wall_timer(period, std::bind(&AdapterNode::control_cycle, this));
    RCLCPP_INFO(get_logger(), "Adapter started: mode=%s mapping_verified=%s",
      hardware_mode_ ? "HARDWARE" : "DRY_RUN", mapping_verified_ ? "true" : "false");
  }

  ~AdapterNode() override
  {
    if (hardware_mode_ && logic_ && logic_->state() == AdapterState::ACTIVE) publish_stop();
  }

private:
  bool command_path_ready() const
  {
    if (!hardware_mode_) return true;
    return command_publisher_->get_subscription_count() == 1 &&
           stop_publisher_->get_subscription_count() == 1 &&
           count_publishers(command_topic_) == 1;
  }

  void publish_stop()
  {
    if (!stop_publisher_) return;
    const int repeat = std::max(1, stop_repeat_count_);
    for (int i = 0; i < repeat; ++i) stop_publisher_->publish(std_msgs::msg::Empty{});
  }

  void control_cycle()
  {
    const auto now = SteadyClock::now();
    const double dt = std::chrono::duration<double>(now - last_cycle_time_).count();
    last_cycle_time_ = now;
    max_cycle_period_seen_ = std::max(max_cycle_period_seen_, dt);

    CycleInput input;
    input.enable = deadman_pressed_;
    input.target_fresh = target_valid_ && is_fresh(target_received_, target_time_, target_timeout_);
    input.quest_pose_fresh = quest_pose_valid_ &&
      is_fresh(quest_pose_received_, quest_pose_time_, quest_pose_timeout_);
    input.inputs_fresh = is_fresh(inputs_received_, inputs_time_, inputs_timeout_);
    input.robot_fresh = is_fresh(robot_received_, robot_time_, robot_timeout_);
    input.control_period_valid = !hardware_mode_ || dt <= max_control_period_;
    input.command_path_ready = command_path_ready();
    input.dt_seconds = dt;
    if (target_received_) input.target_pose = from_ros_pose(target_pose_.pose);
    if (robot_received_) input.robot_pose = from_ros_pose(robot_pose_);

    const AdapterState previous = logic_->state();
    const CycleOutput output = logic_->update(input);
    if (output.state != previous) {
      RCLCPP_INFO(get_logger(), "state %s -> %s (%s)", state_name(previous),
        state_name(output.state), output.reason.empty() ? "ok" : output.reason.c_str());
    }
    if (output.stop_requested) publish_stop();
    if (output.command.has_value()) {
      geometry_msgs::msg::PoseStamped preview;
      preview.header.stamp = get_clock()->now();
      preview.header.frame_id = preview_frame_id_;
      preview.pose = to_ros_pose(*output.command);
      preview_publisher_->publish(preview);
      if (hardware_mode_) {
        rm_ros_interfaces::msg::Cartepos command;
        command.pose = preview.pose;
        command.follow = follow_;
        command_publisher_->publish(command);
      }
    }
    if (std::chrono::duration<double>(now - last_status_time_).count() >= 0.10) {
      publish_status(input, output);
      last_status_time_ = now;
    }
  }

  void publish_status(const CycleInput & input, const CycleOutput & output)
  {
    std::ostringstream stream;
    stream << std::boolalpha << std::fixed << std::setprecision(3)
           << "{\"state\":\"" << state_name(output.state) << "\""
           << ",\"dry_run\":" << dry_run_
           << ",\"hardware_write_enabled\":" << hardware_write_enabled_
           << ",\"hardware_output_available\":" << hardware_mode_
           << ",\"mapping_verified\":" << mapping_verified_
           << ",\"deadman_pressed\":" << input.enable
           << ",\"deadman_source\":\"press_middle\""
           << ",\"target_fresh\":" << input.target_fresh
           << ",\"quest_pose_fresh\":" << input.quest_pose_fresh
           << ",\"inputs_fresh\":" << input.inputs_fresh
           << ",\"robot_fresh\":" << input.robot_fresh
           << ",\"command_path_ready\":" << input.command_path_ready
           << ",\"max_cycle_period_ms\":" << max_cycle_period_seen_ * 1000.0
           << ",\"reason\":\"" << output.reason << "\"}";
    std_msgs::msg::String status;
    status.data = stream.str();
    status_publisher_->publish(status);
  }

  bool dry_run_{true}, hardware_write_enabled_{false}, mapping_verified_{false};
  bool hardware_mode_{false}, follow_{true}, deadman_pressed_{false};
  bool target_received_{false}, target_valid_{false}, quest_pose_received_{false};
  bool quest_pose_valid_{false}, inputs_received_{false}, robot_received_{false};
  int stop_repeat_count_{3};
  double target_timeout_{0.20}, quest_pose_timeout_{0.20}, inputs_timeout_{0.20};
  double robot_timeout_{0.10}, max_control_period_{0.010}, max_cycle_period_seen_{0.0};
  std::string preview_frame_id_, command_topic_, stop_topic_;
  geometry_msgs::msg::PoseStamped target_pose_;
  geometry_msgs::msg::Pose robot_pose_;
  SteadyClock::time_point target_time_{}, quest_pose_time_{}, inputs_time_{}, robot_time_{};
  SteadyClock::time_point last_cycle_time_{}, last_status_time_{};
  std::unique_ptr<AdapterLogic> logic_;
  QuestInputDeadman input_deadman_;
  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr preview_publisher_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_publisher_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Cartepos>::SharedPtr command_publisher_;
  rclcpp::Publisher<std_msgs::msg::Empty>::SharedPtr stop_publisher_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr target_subscription_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr quest_pose_subscription_;
  rclcpp::Subscription<quest2ros::msg::OVR2ROSInputs>::SharedPtr inputs_subscription_;
  rclcpp::Subscription<geometry_msgs::msg::Pose>::SharedPtr robot_pose_subscription_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr clear_fault_service_;
  rclcpp::TimerBase::SharedPtr control_timer_;
};
}  // namespace rm65_teleop_adapter

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  try {
    rclcpp::spin(std::make_shared<rm65_teleop_adapter::AdapterNode>());
  } catch (const std::exception & exception) {
    RCLCPP_FATAL(rclcpp::get_logger("rm65_teleop_adapter"), "%s", exception.what());
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
