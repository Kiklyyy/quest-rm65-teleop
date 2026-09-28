#include "rm65_teleop_adapter/adapter_logic.hpp"
#include "rm65_teleop_adapter/home_action_client.hpp"
#include "rm65_teleop_adapter/home_config.hpp"
#include "rm65_teleop_adapter/quest_input_deadman.hpp"
#include "rm65_teleop_adapter/quest_joint_preset.hpp"
#include "rm65_teleop_adapter/quest_orientation_tracker.hpp"

#include <algorithm>
#include <array>
#include <csignal>
#include <chrono>
#include <cmath>
#include <functional>
#include <deque>
#include <initializer_list>
#include <optional>
#include <iomanip>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "geometry_msgs/msg/pose.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "quest2ros/msg/ovr2_ros_inputs.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rm_ros_interfaces/msg/cartepos.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
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

template<typename TimePointT>
double age_ms(bool received, const TimePointT & stamp)
{
  if (!received) return -1.0;
  return std::chrono::duration<double, std::milli>(SteadyClock::now() - stamp).count();
}

bool finite_position(const geometry_msgs::msg::PoseStamped & pose)
{
  return std::isfinite(pose.pose.position.x) && std::isfinite(pose.pose.position.y) &&
         std::isfinite(pose.pose.position.z);
}

using Endpoint = std::pair<std::string, std::string>;
Endpoint parse_absolute_node(const std::string & full_name)
{
  const auto slash = full_name.rfind('/');
  if (full_name.empty() || full_name.front() != '/' || slash == std::string::npos ||
      slash == full_name.size() - 1 || full_name.find("//") != std::string::npos) {
    throw std::invalid_argument("expected node identities must be complete absolute names");
  }
  return {full_name.substr(slash + 1), slash == 0 ? "/" : full_name.substr(0, slash)};
}

bool exactly_these_endpoints(
  const std::vector<rclcpp::TopicEndpointInfo> & actual,
  std::initializer_list<Endpoint> expected, const std::string & type)
{
  if (actual.size() != expected.size()) return false;
  std::vector<Endpoint> remaining(expected);
  for (const auto & endpoint : actual) {
    if (endpoint.topic_type() != type) return false;
    const Endpoint identity{endpoint.node_name(), endpoint.node_namespace()};
    const auto found = std::find(remaining.begin(), remaining.end(), identity);
    if (found == remaining.end()) return false;
    remaining.erase(found);
  }
  return remaining.empty();
}

struct CommandPaths
{
  bool cartesian{false};
  bool home{false};
};
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
    const auto adapter_node_name = declare_parameter<std::string>(
      "expected_adapter_node", "/rm65_teleop_adapter");
    const auto driver_node_name = declare_parameter<std::string>(
      "expected_driver_node", "/right/rm_driver");
    expected_controller_node_name_ = declare_parameter<std::string>(
      "expected_control_node", "/right/rm_control");
    expected_adapter_ = parse_absolute_node(adapter_node_name);
    expected_driver_ = parse_absolute_node(driver_node_name);
    expected_controller_ = parse_absolute_node(expected_controller_node_name_);
    if (adapter_node_name != get_fully_qualified_name() ||
        expected_adapter_ == expected_driver_ ||
        expected_adapter_ == expected_controller_ ||
        expected_driver_ == expected_controller_) {
      throw std::invalid_argument("configured command node identities must be distinct and match this adapter");
    }
    home_enabled_ = declare_parameter<bool>("home_enabled", false);
    HomeParameterSet home_parameters;
    home_parameters.dry_run = dry_run_;
    home_parameters.enabled = home_enabled_;
    home_parameters.button_field = declare_parameter<std::string>("home_button_field", "upper");
    home_parameters.action_name = declare_parameter<std::string>("home_action_name", "");
    const auto configured_home_joint_degrees = declare_parameter<std::vector<double>>(
      "home_joint_degrees", std::vector<double>{});
    const auto quest_right_first = declare_parameter<std::vector<double>>(
      "quest_right_first", std::vector<double>{});
    const auto quest_right_second = declare_parameter<std::vector<double>>(
      "quest_right_second", std::vector<double>{});
    const auto quest_right_last = declare_parameter<std::vector<double>>(
      "quest_right_last", std::vector<double>{});
    quest_right_x_inputs_topic_ = declare_parameter<std::string>(
      "quest_right_x_inputs_topic", "");
    const bool any_joint_preset = !quest_right_first.empty() ||
      !quest_right_second.empty() || !quest_right_last.empty();
    joint_presets_enabled_ = quest_right_first.size() == 6 &&
      quest_right_second.size() == 6 && quest_right_last.size() == 6;
    if (any_joint_preset && !joint_presets_enabled_) {
      throw std::invalid_argument(
              "quest_right_first/second/last must each contain six joint degrees");
    }
    if (joint_presets_enabled_ && quest_right_x_inputs_topic_.empty()) {
      throw std::invalid_argument("Quest X joint preset requires quest_right_x_inputs_topic");
    }
    home_parameters.joint_degrees = joint_presets_enabled_ ?
      quest_right_first : configured_home_joint_degrees;
    home_parameters.joint_names = declare_parameter<std::vector<std::string>>(
      "home_joint_names", std::vector<std::string>{});
    home_parameters.speed_deg_s = declare_parameter<double>("home_speed_deg_s", 0.0);
    home_parameters.hold_seconds = declare_parameter<double>("home_hold_seconds", 0.0);
    joint_state_topic_ = declare_parameter<std::string>("joint_state_topic", "/right/joint_states");
    joint_state_timeout_ = declare_parameter<double>("joint_state_timeout", 0.10);
    if (home_enabled_) {
      if (!hardware_mode_ || !std::isfinite(joint_state_timeout_) ||
          joint_state_timeout_ <= 0.0 || joint_state_topic_.empty()) {
        throw std::invalid_argument("Home requires valid hardware mode and joint-state watchdog");
      }
      home_config_ = resolve_home_config(home_parameters);
      if (!home_config_) throw std::invalid_argument("invalid enabled Home configuration");
      if (joint_presets_enabled_) {
        const std::array<std::vector<double>, 3> configured_presets{
          quest_right_first, quest_right_second, quest_right_last};
        for (std::size_t i = 0; i < configured_presets.size(); ++i) {
          joint_preset_trajectories_[i] = home_config_->trajectory;
          std::copy(configured_presets[i].begin(), configured_presets[i].end(),
            joint_preset_trajectories_[i].target_degrees.begin());
          if (!home_trajectory_config_valid(joint_preset_trajectories_[i])) {
            throw std::invalid_argument("invalid Quest right joint preset configuration");
          }
        }
      }
    }

    AdapterConfig config;
    if (home_config_) config.home_hold_seconds = home_config_->trajectory.hold_seconds;
    config.translation_scale = declare_parameter<double>("translation_scale", 1.0);
    config.max_velocity_mps = declare_parameter<double>("max_velocity_mps", 0.01);
    config.max_step_m = declare_parameter<double>("max_step_m", 0.0001);
    config.max_anchor_distance_m = declare_parameter<double>("max_anchor_distance_m", 0.03);
    config.unexpected_target_jump_m = declare_parameter<double>("unexpected_target_jump_m", 0.10);
    config.rotation_scale = this->declare_parameter<double>("rotation_scale", 1.0);
    config.max_angular_velocity_rad_s = this->declare_parameter<double>(
      "max_angular_velocity_rad_s", 1.5707963267948966);
    config.max_angular_step_rad = this->declare_parameter<double>(
      "max_angular_step_rad", 0.01);
    config.max_anchor_angle_rad = this->declare_parameter<double>(
      "max_anchor_angle_rad", 1.5707963267948966);
    config.unexpected_orientation_jump_rad = this->declare_parameter<double>(
      "unexpected_orientation_jump_rad", 0.7853981633974483);
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
    orientation_tracker_ = std::make_unique<QuestOrientationTracker>(
      config.unexpected_orientation_jump_rad);

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
    home_movej_topic_ = declare_parameter<std::string>(
      "home_movej_topic", "/right/rm_driver/movej_canfd_cmd");
    stop_topic_ = declare_parameter<std::string>(
      "stop_topic", "/right/rm_driver/move_stop_cmd");
    if (home_config_ && home_movej_topic_.empty()) {
      throw std::invalid_argument("Home requires a movej command topic");
    }

    const auto preview_topic = declare_parameter<std::string>(
      "preview_topic", "/right/rm65_teleop/preview_target_pose");
    const auto status_topic = declare_parameter<std::string>(
      "status_topic", "/right/rm65_teleop/status");
    const auto clear_fault_service = declare_parameter<std::string>(
      "clear_fault_service", "/right/rm65_teleop/clear_fault");
    if (preview_topic.empty() || status_topic.empty() || clear_fault_service.empty()) {
      throw std::invalid_argument("adapter status, preview and clear-fault endpoints are required");
    }
    preview_publisher_ = create_publisher<geometry_msgs::msg::PoseStamped>(
      preview_topic, 10);
    status_publisher_ = create_publisher<std_msgs::msg::String>(
      status_topic, 10);
    if (hardware_mode_) {
      command_publisher_ = create_publisher<rm_ros_interfaces::msg::Cartepos>(command_topic_, 10);
      stop_publisher_ = create_publisher<std_msgs::msg::Empty>(stop_topic_, 10);
    }
    if (home_config_) {
      home_client_ = std::make_unique<HomeActionClient>(
        *this, home_config_->action_name,
        [this](HomeActionEvent event) {home_events_.push_back(event);});
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
        const QuaternionXyzw raw_orientation{
          message->pose.orientation.x, message->pose.orientation.y,
          message->pose.orientation.z, message->pose.orientation.w};
        orientation_tracker_->ingest(raw_orientation);
        quest_pose_received_ = true;
        quest_pose_valid_ = finite_position(*message);
        quest_pose_time_ = SteadyClock::now();
      });
    inputs_subscription_ = create_subscription<quest2ros::msg::OVR2ROSInputs>(
      inputs_topic, 10, [this](quest2ros::msg::OVR2ROSInputs::SharedPtr message) {
        deadman_pressed_ = input_deadman_.update(*message);
        if (joint_presets_enabled_) {
          joint_preset_a_pressed_ = static_cast<bool>(message->button_lower);
          joint_preset_b_pressed_ = static_cast<bool>(message->button_upper);
        } else if (home_config_) {
          home_button_pressed_ = quest_face_button_pressed(*message, home_config_->button_field);
        }
        inputs_received_ = true;
        inputs_time_ = SteadyClock::now();
      });
    if (joint_presets_enabled_) {
      joint_preset_x_subscription_ = create_subscription<quest2ros::msg::OVR2ROSInputs>(
        quest_right_x_inputs_topic_, 10,
        [this](quest2ros::msg::OVR2ROSInputs::SharedPtr message) {
          joint_preset_x_pressed_ = static_cast<bool>(message->button_lower);
          joint_preset_x_inputs_received_ = true;
          joint_preset_x_inputs_time_ = SteadyClock::now();
        });
    }
    robot_pose_subscription_ = create_subscription<geometry_msgs::msg::Pose>(
      robot_pose_topic, 10, [this](geometry_msgs::msg::Pose::SharedPtr message) {
        robot_received_ = true;
        robot_time_ = SteadyClock::now();
        Pose3 candidate = from_ros_pose(*message);
        const auto normalized = normalize_quaternion(candidate.orientation);
        if (!normalized.has_value()) {
          robot_orientation_valid_ = false;
          return;
        }
        candidate.orientation = *normalized;
        robot_pose_ = candidate;
        robot_orientation_valid_ = true;
      });

    if (home_config_) {
      joint_state_subscription_ = create_subscription<sensor_msgs::msg::JointState>(
        joint_state_topic_, 10, [this](sensor_msgs::msg::JointState::SharedPtr message) {
          joint_state_received_ = true;
          joint_state_time_ = SteadyClock::now();
          const auto ordered = reorder_joint_positions(
            message->name, message->position, home_config_->trajectory.joint_names);
          joint_state_valid_ = ordered.has_value();
          if (ordered) joint_positions_ = *ordered;
        });
    }

    clear_fault_service_ = create_service<std_srvs::srv::Trigger>(
      clear_fault_service,
      [this](const std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response) {
        response->success = logic_->clear_fault(deadman_pressed_);
        if (response->success) ++rearm_count_;
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
    if (!shutting_down_) prepare_shutdown();
  }

  void prepare_shutdown()
  {
    if (shutting_down_) return;
    shutting_down_ = true;
    if (control_timer_) control_timer_->cancel();
    if (!hardware_mode_ || !logic_) return;
    const bool home_in_progress = logic_->state() == AdapterState::HOMING ||
      (home_client_ && home_client_->goal_active());
    if (home_in_progress && home_client_) home_client_->request_cancel();
    if (home_in_progress || logic_->state() == AdapterState::ACTIVE) publish_stop();
  }

  bool home_goal_in_flight() const
  {
    return home_client_ && home_client_->goal_active();
  }

private:
  CommandPaths command_paths() const
  {
    if (!hardware_mode_) return {true, false};
    const bool movep_owned = exactly_these_endpoints(
      get_publishers_info_by_topic(command_topic_), {expected_adapter_},
      "rm_ros_interfaces/msg/Cartepos") &&
      exactly_these_endpoints(
      get_subscriptions_info_by_topic(command_topic_), {expected_driver_},
      "rm_ros_interfaces/msg/Cartepos");
    const bool stop_owned = exactly_these_endpoints(
      get_publishers_info_by_topic(stop_topic_), {expected_adapter_}, "std_msgs/msg/Empty");
    const auto stop_subscribers = get_subscriptions_info_by_topic(stop_topic_);
    const bool driver_only_stop = exactly_these_endpoints(
      stop_subscribers, {expected_driver_}, "std_msgs/msg/Empty");
    const bool home_stop = exactly_these_endpoints(
      stop_subscribers, {expected_driver_, expected_controller_}, "std_msgs/msg/Empty");
    const auto node_names = get_node_names();
    const bool controller_unique =
      std::count(node_names.begin(), node_names.end(), expected_controller_node_name_) == 1;
    const bool cartesian = movep_owned && stop_owned &&
      (driver_only_stop || (home_stop && controller_unique));
    if (!home_config_ || !cartesian || !home_stop || !controller_unique) {
      return {cartesian, false};
    }
    const bool movej_owned = exactly_these_endpoints(
      get_publishers_info_by_topic(home_movej_topic_), {expected_controller_},
      "rm_ros_interfaces/msg/Jointpos") &&
      exactly_these_endpoints(
      get_subscriptions_info_by_topic(home_movej_topic_), {expected_driver_},
      "rm_ros_interfaces/msg/Jointpos");
    const bool action_owned = exactly_these_endpoints(
      get_publishers_info_by_topic(home_config_->action_name + "/_action/status"),
      {expected_controller_}, "action_msgs/msg/GoalStatusArray") &&
      home_client_ && home_client_->server_ready();
    return {cartesian, movej_owned && action_owned};
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
    const OrientationSnapshot orientation = orientation_tracker_->consume_snapshot();
    input.quest_orientation = orientation.latest_orientation;
    input.quest_orientation_valid =
      orientation.has_valid_orientation && orientation.latest_sample_valid;
    input.quest_orientation_status = orientation.status;
    input.quest_orientation_jump_rad = orientation.jump_angle_rad;
    input.enable = deadman_pressed_;
    input.target_fresh = target_valid_ && is_fresh(target_received_, target_time_, target_timeout_);
    input.quest_pose_fresh = quest_pose_valid_ &&
      is_fresh(quest_pose_received_, quest_pose_time_, quest_pose_timeout_);
    input.inputs_fresh = is_fresh(inputs_received_, inputs_time_, inputs_timeout_);
    input.robot_fresh = is_fresh(robot_received_, robot_time_, robot_timeout_);
    input.control_period_valid = !hardware_mode_ || dt <= max_control_period_;
    input.robot_orientation_valid = robot_orientation_valid_;
    const auto paths = command_paths();
    input.command_path_ready = paths.cartesian;
    input.home_command_path_ready = paths.home;
    const HomeTrajectoryConfig * selected_home_trajectory = nullptr;
    if (joint_presets_enabled_) {
      current_joint_preset_ = joint_preset_selector_.update(
        inputs_received_ && joint_preset_x_inputs_received_,
        joint_preset_x_pressed_, joint_preset_a_pressed_, joint_preset_b_pressed_);
      const auto preset_index = quest_joint_preset_index(current_joint_preset_);
      if (preset_index) {
        selected_home_trajectory = &joint_preset_trajectories_[*preset_index];
      }
      input.home_button_pressed = preset_index.has_value();
      input.home_inputs_fresh = input.inputs_fresh && is_fresh(
        joint_preset_x_inputs_received_, joint_preset_x_inputs_time_, inputs_timeout_);
    } else {
      input.home_button_pressed = home_button_pressed_;
      input.home_inputs_fresh = input.inputs_fresh;
      if (home_config_) selected_home_trajectory = &home_config_->trajectory;
    }
    input.joint_state_fresh = home_enabled_ &&
      is_fresh(joint_state_received_, joint_state_time_, joint_state_timeout_);
    input.joint_state_valid = joint_state_valid_;
    input.home_action_ready = home_client_ && home_client_->server_ready() &&
      (logic_->state() == AdapterState::HOMING || !home_client_->goal_active());
    input.home_plan_valid = selected_home_trajectory && joint_state_valid_ &&
      make_home_trajectory_plan(joint_positions_, *selected_home_trajectory).has_value();
    if (!home_events_.empty()) {
      input.home_action_event = home_events_.front();
      last_home_event_ = input.home_action_event;
      home_cancel_pending_ = false;
      home_events_.pop_front();
    }
    input.dt_seconds = dt;
    if (target_received_) input.target_pose = from_ros_pose(target_pose_.pose);
    if (robot_received_) input.robot_pose = robot_pose_;

    const AdapterState previous = logic_->state();
    const CycleOutput output = logic_->update(input);
    if (output.anchor_captured) {
      orientation_tracker_->begin_active_session(input.quest_orientation);
    }
    if (previous == AdapterState::ACTIVE && output.state != AdapterState::ACTIVE) {
      orientation_tracker_->end_active_session();
    }
    if (output.state != previous && output.state == AdapterState::REARM_REQUIRED) {
      ++rearm_count_;
    }
    if ((output.state != previous && output.reason == "input_not_fresh") ||
        (output.home_cancel_requested && output.reason.rfind("home_", 0) == 0 &&
         output.reason.find("_not_fresh") != std::string::npos)) {
      ++watchdog_count_;
    }
    if (output.state != previous) {
      RCLCPP_INFO(get_logger(), "state %s -> %s (%s)", state_name(previous),
        state_name(output.state), output.reason.empty() ? "ok" : output.reason.c_str());
    }
    if (output.home_goal_requested) {
      last_home_event_ = HomeActionEvent::NONE;
      home_cancel_pending_ = false;
      active_joint_preset_ = current_joint_preset_;
      const auto plan = selected_home_trajectory ?
        make_home_trajectory_plan(joint_positions_, *selected_home_trajectory) :
        std::optional<HomeTrajectoryPlan>{};
      RCLCPP_INFO(
        get_logger(), "joint trajectory requested: %s",
        joint_presets_enabled_ ? quest_joint_preset_name(active_joint_preset_) : "HOME");
      if (!home_client_ || !plan || !home_client_->send_goal(*plan)) {
        home_events_.push_back(HomeActionEvent::REJECTED);
        publish_stop();
      }
    }
    if (output.home_cancel_requested && home_client_) {
      home_cancel_pending_ = true;
      home_client_->request_cancel();
    }
    if (output.stop_requested) publish_stop();
    if (output.command.has_value() && output.state == AdapterState::ACTIVE) {
      if (previous == AdapterState::ARMED) {
        const auto & anchor = input.robot_pose;
        const auto & first = *output.command;
        const double dx = first.position[0] - anchor.position[0];
        const double dy = first.position[1] - anchor.position[1];
        const double dz = first.position[2] - anchor.position[2];
        RCLCPP_INFO(
          get_logger(),
          "first_command_anchor anchor=(%.6f,%.6f,%.6f) first=(%.6f,%.6f,%.6f) "
          "delta_m=%.9f anchor_q=(%.6f,%.6f,%.6f,%.6f) "
          "first_q=(%.6f,%.6f,%.6f,%.6f)",
          anchor.position[0], anchor.position[1], anchor.position[2],
          first.position[0], first.position[1], first.position[2],
          std::sqrt(dx * dx + dy * dy + dz * dz),
          anchor.orientation.x, anchor.orientation.y, anchor.orientation.z, anchor.orientation.w,
          first.orientation.x, first.orientation.y, first.orientation.z, first.orientation.w);
      }
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
    if (output.state != previous ||
        std::chrono::duration<double>(now - last_status_time_).count() >= 0.10) {
      publish_status(input, output);
      last_status_time_ = now;
    }
  }

  void publish_status(const CycleInput & input, const CycleOutput & output)
  {
    std::string home_action_state = "DISABLED";
    if (home_client_) {
      if (output.state == AdapterState::HOMING) {
        home_action_state = home_cancel_pending_ ? "CANCELING" :
          home_client_->goal_accepted() ? "ACTIVE" : "PENDING";
      } else if (last_home_event_ == HomeActionEvent::SUCCEEDED) {
        home_action_state = "SUCCEEDED";
      } else if (last_home_event_ == HomeActionEvent::CANCELED) {
        home_action_state = "CANCELED";
      } else if (last_home_event_ == HomeActionEvent::REJECTED) {
        home_action_state = "REJECTED";
      } else if (last_home_event_ == HomeActionEvent::ABORTED) {
        home_action_state = "ABORTED";
      } else {
        home_action_state = home_client_->server_ready() ? "IDLE" : "SERVER_UNAVAILABLE";
      }
    }
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
           << ",\"home_inputs_fresh\":" << input.home_inputs_fresh
           << ",\"robot_fresh\":" << input.robot_fresh
           << ",\"joint_state_fresh\":" << input.joint_state_fresh
           << ",\"quest_pose_age_ms\":" << age_ms(quest_pose_received_, quest_pose_time_)
           << ",\"inputs_age_ms\":" << age_ms(inputs_received_, inputs_time_)
           << ",\"joint_preset_x_inputs_age_ms\":" << age_ms(
      joint_preset_x_inputs_received_, joint_preset_x_inputs_time_)
           << ",\"robot_age_ms\":" << age_ms(robot_received_, robot_time_)
           << ",\"joint_state_age_ms\":" << age_ms(joint_state_received_, joint_state_time_)
           << ",\"rearm_count\":" << rearm_count_
           << ",\"watchdog_count\":" << watchdog_count_
           << ",\"home_button_pressed\":" << input.home_button_pressed
           << ",\"joint_presets_enabled\":" << joint_presets_enabled_
           << ",\"joint_preset_selection\":\"" << quest_joint_preset_name(
      current_joint_preset_) << "\""
           << ",\"joint_preset_active\":\"" << quest_joint_preset_name(
      active_joint_preset_) << "\""
           << ",\"home_hold_progress\":" << output.home_hold_progress
           << ",\"home_action_state\":\"" << home_action_state << "\""
           << ",\"command_path_ready\":" << input.command_path_ready
           << ",\"home_command_path_ready\":" << input.home_command_path_ready
           << ",\"max_cycle_period_ms\":" << max_cycle_period_seen_ * 1000.0
           << ",\"reason\":\"" << output.reason << "\"}";
    std_msgs::msg::String status;
    status.data = stream.str();
    status_publisher_->publish(status);
  }

  bool dry_run_{true}, hardware_write_enabled_{false}, mapping_verified_{false};
  bool home_enabled_{false}, home_button_pressed_{false};
  bool joint_presets_enabled_{false};
  bool joint_preset_x_pressed_{false}, joint_preset_a_pressed_{false};
  bool joint_preset_b_pressed_{false}, joint_preset_x_inputs_received_{false};
  bool joint_state_received_{false}, joint_state_valid_{false};
  double joint_state_timeout_{0.10};
  std::string joint_state_topic_;
  std::array<double, 6> joint_positions_{};
  SteadyClock::time_point joint_state_time_{};
  std::optional<ResolvedHomeConfig> home_config_;
  std::array<HomeTrajectoryConfig, 3> joint_preset_trajectories_{};
  QuestJointPresetSelector joint_preset_selector_;
  QuestJointPreset current_joint_preset_{QuestJointPreset::NONE};
  QuestJointPreset active_joint_preset_{QuestJointPreset::NONE};
  std::unique_ptr<HomeActionClient> home_client_;
  std::deque<HomeActionEvent> home_events_;
  HomeActionEvent last_home_event_{HomeActionEvent::NONE};
  bool home_cancel_pending_{false};
  bool shutting_down_{false};
  std::size_t rearm_count_{0}, watchdog_count_{0};
  bool hardware_mode_{false}, follow_{true}, deadman_pressed_{false};
  bool target_received_{false}, target_valid_{false}, quest_pose_received_{false};
  bool quest_pose_valid_{false}, inputs_received_{false}, robot_received_{false};
  int stop_repeat_count_{3};
  bool robot_orientation_valid_{false};
  double target_timeout_{0.20}, quest_pose_timeout_{0.20}, inputs_timeout_{0.20};
  double robot_timeout_{0.10}, max_control_period_{0.010}, max_cycle_period_seen_{0.0};
  std::string preview_frame_id_, command_topic_, home_movej_topic_, stop_topic_;
  std::string quest_right_x_inputs_topic_;
  std::string expected_controller_node_name_;
  Endpoint expected_adapter_, expected_driver_, expected_controller_;
  geometry_msgs::msg::PoseStamped target_pose_;
  Pose3 robot_pose_;
  SteadyClock::time_point target_time_{}, quest_pose_time_{}, inputs_time_{}, robot_time_{};
  SteadyClock::time_point joint_preset_x_inputs_time_{};
  SteadyClock::time_point last_cycle_time_{}, last_status_time_{};
  std::unique_ptr<AdapterLogic> logic_;
  QuestInputDeadman input_deadman_;
  std::unique_ptr<QuestOrientationTracker> orientation_tracker_;
  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr preview_publisher_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_publisher_;
  rclcpp::Publisher<rm_ros_interfaces::msg::Cartepos>::SharedPtr command_publisher_;
  rclcpp::Publisher<std_msgs::msg::Empty>::SharedPtr stop_publisher_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr target_subscription_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr quest_pose_subscription_;
  rclcpp::Subscription<quest2ros::msg::OVR2ROSInputs>::SharedPtr inputs_subscription_;
  rclcpp::Subscription<quest2ros::msg::OVR2ROSInputs>::SharedPtr joint_preset_x_subscription_;
  rclcpp::Subscription<geometry_msgs::msg::Pose>::SharedPtr robot_pose_subscription_;
  rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr joint_state_subscription_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr clear_fault_service_;
  rclcpp::TimerBase::SharedPtr control_timer_;
};
}  // namespace rm65_teleop_adapter

namespace
{
volatile std::sig_atomic_t shutdown_signal = 0;
void request_shutdown_signal(int) {shutdown_signal = 1;}
}

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv, rclcpp::InitOptions{}, rclcpp::SignalHandlerOptions::None);
  std::signal(SIGINT, request_shutdown_signal);
  std::signal(SIGTERM, request_shutdown_signal);
  try {
    auto node = std::make_shared<rm65_teleop_adapter::AdapterNode>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    while (rclcpp::ok() && !shutdown_signal) {
      executor.spin_once(std::chrono::milliseconds(20));
    }
    node->prepare_shutdown();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (rclcpp::ok() && node->home_goal_in_flight() &&
           std::chrono::steady_clock::now() < deadline) {
      executor.spin_once(std::chrono::milliseconds(10));
    }
    executor.remove_node(node);
    node.reset();
  } catch (const std::exception & exception) {
    RCLCPP_FATAL(rclcpp::get_logger("rm65_teleop_adapter"), "%s", exception.what());
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
