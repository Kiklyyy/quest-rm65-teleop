#include "rm65_teleop_adapter/home_action_client.hpp"

#include <cmath>
#include <utility>

#include "trajectory_msgs/msg/joint_trajectory_point.hpp"

namespace rm65_teleop_adapter
{
HomeActionClient::HomeActionClient(
  rclcpp::Node & node, const std::string & action_name, EventCallback callback)
: callback_(std::move(callback))
{
  client_ = rclcpp_action::create_client<FollowJT>(
    node.get_node_base_interface(), node.get_node_graph_interface(),
    node.get_node_logging_interface(), node.get_node_waitables_interface(), action_name);
}

bool HomeActionClient::server_ready() const
{
  return client_->action_server_is_ready();
}

bool HomeActionClient::send_goal(const HomeTrajectoryPlan & plan)
{
  if (in_flight_ || !server_ready() || !std::isfinite(plan.duration_seconds) ||
      plan.duration_seconds <= 0.0) return false;
  for (std::size_t i = 0; i < 6; ++i) {
    if (plan.joint_names[i].empty() || !std::isfinite(plan.target_radians[i])) return false;
  }
  FollowJT::Goal goal;
  goal.trajectory.joint_names.assign(plan.joint_names.begin(), plan.joint_names.end());
  trajectory_msgs::msg::JointTrajectoryPoint point;
  point.positions.assign(plan.target_radians.begin(), plan.target_radians.end());
  point.time_from_start = rclcpp::Duration::from_seconds(plan.duration_seconds);
  goal.trajectory.points.push_back(point);

  typename rclcpp_action::Client<FollowJT>::SendGoalOptions options;
  options.goal_response_callback = [this](GoalHandle::SharedPtr handle) {
      if (!handle) {
        in_flight_ = false;
        cancel_requested_ = false;
        callback_(HomeActionEvent::REJECTED);
        return;
      }
      handle_ = handle;
      if (cancel_requested_) client_->async_cancel_goal(handle_);
    };
  options.result_callback = [this](const GoalHandle::WrappedResult & result) {
      in_flight_ = false;
      cancel_requested_ = false;
      handle_.reset();
      if (result.code == rclcpp_action::ResultCode::SUCCEEDED && result.result &&
          result.result->error_code == FollowJT::Result::SUCCESSFUL) {
        callback_(HomeActionEvent::SUCCEEDED);
      } else if (result.code == rclcpp_action::ResultCode::CANCELED) {
        callback_(HomeActionEvent::CANCELED);
      } else {
        callback_(HomeActionEvent::ABORTED);
      }
    };
  in_flight_ = true;
  cancel_requested_ = false;
  try {
    client_->async_send_goal(goal, options);
  } catch (const std::exception &) {
    in_flight_ = false;
    return false;
  }
  return true;
}

bool HomeActionClient::request_cancel()
{
  if (!in_flight_) return false;
  if (cancel_requested_) return true;
  cancel_requested_ = true;
  if (handle_) {
    try {
      client_->async_cancel_goal(handle_);
    } catch (const std::exception &) {
      return false;
    }
  }
  return true;
}
}  // namespace rm65_teleop_adapter
