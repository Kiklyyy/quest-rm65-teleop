#pragma once

#include <functional>
#include <string>

#include "control_msgs/action/follow_joint_trajectory.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "rm65_teleop_adapter/adapter_logic.hpp"
#include "rm65_teleop_adapter/home_trajectory.hpp"

namespace rm65_teleop_adapter
{
class HomeActionClient
{
public:
  using FollowJT = control_msgs::action::FollowJointTrajectory;
  using EventCallback = std::function<void(HomeActionEvent)>;
  using GoalHandle = rclcpp_action::ClientGoalHandle<FollowJT>;

  HomeActionClient(rclcpp::Node & node, const std::string & action_name,
    EventCallback callback);
  bool server_ready() const;
  bool goal_active() const {return in_flight_;}
  bool goal_accepted() const {return static_cast<bool>(handle_);}
  bool send_goal(const HomeTrajectoryPlan & plan);
  bool request_cancel();

private:
  rclcpp_action::Client<FollowJT>::SharedPtr client_;
  GoalHandle::SharedPtr handle_;
  EventCallback callback_;
  bool in_flight_{false};
  bool cancel_requested_{false};
};
}  // namespace rm65_teleop_adapter
