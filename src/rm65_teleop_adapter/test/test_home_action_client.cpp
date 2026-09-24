#include <array>
#include <chrono>
#include <cmath>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include <gtest/gtest.h>
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "rm65_teleop_adapter/home_action_client.hpp"

namespace
{
using namespace std::chrono_literals;
using rm65_teleop_adapter::HomeActionClient;
using rm65_teleop_adapter::HomeActionEvent;
using rm65_teleop_adapter::HomeTrajectoryPlan;
using FollowJT = control_msgs::action::FollowJointTrajectory;
using ServerHandle = rclcpp_action::ServerGoalHandle<FollowJT>;

class HomeActionClientTest : public ::testing::Test
{
protected:
  static void SetUpTestSuite() {int argc=0; rclcpp::init(argc, nullptr);}
  static void TearDownTestSuite() {rclcpp::shutdown();}
  void SetUp() override
  {
    server_node_ = std::make_shared<rclcpp::Node>("synthetic_home_server");
    client_node_ = std::make_shared<rclcpp::Node>("synthetic_home_client");
    server_ = rclcpp_action::create_server<FollowJT>(
      server_node_, "/test/right/home_action",
      [this](const rclcpp_action::GoalUUID &, std::shared_ptr<const FollowJT::Goal>) {
        return reject_ ? rclcpp_action::GoalResponse::REJECT :
                        rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [this](const std::shared_ptr<ServerHandle>) {
        ++cancel_count_;
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](const std::shared_ptr<ServerHandle> handle) {
        handle_ = handle;
      });
    executor_.add_node(server_node_);
    executor_.add_node(client_node_);
    client_ = std::make_unique<HomeActionClient>(
      *client_node_, "/test/right/home_action",
      [this](HomeActionEvent event) {events_.push_back(event);});
    ASSERT_TRUE(wait_until([this] {return client_->server_ready();}));
  }
  void TearDown() override
  {
    client_.reset();
    executor_.remove_node(client_node_);
    executor_.remove_node(server_node_);
    server_.reset();
  }
  template<class F> bool wait_until(F predicate)
  {
    for (int i=0; i<2000; ++i) {
      executor_.spin_some();
      if (predicate()) return true;
      std::this_thread::sleep_for(1ms);
    }
    return false;
  }
  HomeTrajectoryPlan plan() const
  {
    return {{"joint1","joint2","joint3","joint4","joint5","joint6"},
            {0,1,2,3,4,5}, {1,2,3,4,5,6}, 2.5};
  }
  bool reject_{false};
  int cancel_count_{0};
  std::vector<HomeActionEvent> events_;
  rclcpp::Node::SharedPtr server_node_, client_node_;
  rclcpp_action::Server<FollowJT>::SharedPtr server_;
  std::shared_ptr<ServerHandle> handle_;
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::unique_ptr<HomeActionClient> client_;
};

TEST_F(HomeActionClientTest, ServerAvailableGoalPayloadAndSecondGoalBlocked)
{
  const auto expected = plan();
  ASSERT_TRUE(client_->send_goal(expected));
  ASSERT_TRUE(wait_until([this] {return static_cast<bool>(handle_);}));
  EXPECT_TRUE(client_->goal_active());
  EXPECT_FALSE(client_->send_goal(expected));
  const auto goal = handle_->get_goal();
  EXPECT_EQ(goal->trajectory.joint_names,
    (std::vector<std::string>{"joint1","joint2","joint3","joint4","joint5","joint6"}));
  ASSERT_EQ(goal->trajectory.points.size(), 4u);
  const std::array<double, 4> blends{{0.0, 7.0 / 27.0, 20.0 / 27.0, 1.0}};
  for (std::size_t p = 0; p < 4; ++p) {
    const auto & point = goal->trajectory.points[p];
    ASSERT_EQ(point.positions.size(), 6u);
    ASSERT_EQ(point.velocities.size(), 6u);
    ASSERT_EQ(point.accelerations.size(), 6u);
    for (std::size_t j = 0; j < 6; ++j) {
      EXPECT_NEAR(point.positions[j], static_cast<double>(j) + blends[p], 1e-12);
      EXPECT_TRUE(std::isfinite(point.velocities[j]));
      EXPECT_TRUE(std::isfinite(point.accelerations[j]));
    }
  }
  EXPECT_DOUBLE_EQ(goal->trajectory.points.front().velocities.front(), 0.0);
  EXPECT_DOUBLE_EQ(goal->trajectory.points.back().velocities.front(), 0.0);
  EXPECT_EQ(goal->trajectory.points.front().time_from_start.sec, 0);
  EXPECT_EQ(goal->trajectory.points.front().time_from_start.nanosec, 0u);
  EXPECT_EQ(goal->trajectory.points.back().positions,
    (std::vector<double>{1,2,3,4,5,6}));
  EXPECT_EQ(goal->trajectory.points.back().time_from_start.sec, 2);
  EXPECT_EQ(goal->trajectory.points.back().time_from_start.nanosec, 500000000u);
  handle_->succeed(std::make_shared<FollowJT::Result>());
  ASSERT_TRUE(wait_until([this] {return !events_.empty();}));
  EXPECT_EQ(events_.back(), HomeActionEvent::SUCCEEDED);
  EXPECT_FALSE(client_->goal_active());
}

TEST_F(HomeActionClientTest, CancelWaitsForCanceledTerminal)
{
  ASSERT_TRUE(client_->send_goal(plan()));
  ASSERT_TRUE(wait_until([this] {return static_cast<bool>(handle_);}));
  ASSERT_TRUE(client_->request_cancel());
  ASSERT_TRUE(wait_until([this] {return cancel_count_ == 1;}));
  EXPECT_TRUE(client_->goal_active());
  EXPECT_TRUE(events_.empty());
  handle_->canceled(std::make_shared<FollowJT::Result>());
  ASSERT_TRUE(wait_until([this] {return !events_.empty();}));
  EXPECT_EQ(events_.back(), HomeActionEvent::CANCELED);
}

TEST_F(HomeActionClientTest, CancelRequestedVendorSuccessReportsCanceled)
{
  ASSERT_TRUE(client_->send_goal(plan()));
  ASSERT_TRUE(wait_until([this] {return static_cast<bool>(handle_);}));
  ASSERT_TRUE(client_->request_cancel());
  ASSERT_TRUE(wait_until([this] {return cancel_count_ == 1;}));
  EXPECT_TRUE(client_->goal_active());
  EXPECT_TRUE(events_.empty());
  auto result = std::make_shared<FollowJT::Result>();
  result->error_code = FollowJT::Result::SUCCESSFUL;
  handle_->succeed(result);
  ASSERT_TRUE(wait_until([this] {return !events_.empty();}));
  EXPECT_EQ(events_.back(), HomeActionEvent::CANCELED);
  EXPECT_FALSE(client_->goal_active());
}

TEST_F(HomeActionClientTest, RejectedGoalReportsRejected)
{
  reject_ = true;
  ASSERT_TRUE(client_->send_goal(plan()));
  ASSERT_TRUE(wait_until([this] {return !events_.empty();}));
  EXPECT_EQ(events_.back(), HomeActionEvent::REJECTED);
  EXPECT_FALSE(client_->goal_active());
}

TEST_F(HomeActionClientTest, AbortedGoalReportsAborted)
{
  ASSERT_TRUE(client_->send_goal(plan()));
  ASSERT_TRUE(wait_until([this] {return static_cast<bool>(handle_);}));
  handle_->abort(std::make_shared<FollowJT::Result>());
  ASSERT_TRUE(wait_until([this] {return !events_.empty();}));
  EXPECT_EQ(events_.back(), HomeActionEvent::ABORTED);
}

TEST_F(HomeActionClientTest, MissingServerCannotSend)
{
  HomeActionClient missing(*client_node_, "/test/right/missing_home_action",
    [this](HomeActionEvent event) {events_.push_back(event);});
  EXPECT_FALSE(missing.server_ready());
  EXPECT_FALSE(missing.send_goal(plan()));
  EXPECT_FALSE(missing.goal_active());
}

TEST_F(HomeActionClientTest, CancelBeforeGoalAcceptanceIsForwarded)
{
  ASSERT_TRUE(client_->send_goal(plan()));
  ASSERT_TRUE(client_->request_cancel());
  ASSERT_TRUE(wait_until([this] {return cancel_count_ == 1;}));
  EXPECT_TRUE(client_->goal_active());
  ASSERT_TRUE(handle_);
  handle_->canceled(std::make_shared<FollowJT::Result>());
  ASSERT_TRUE(wait_until([this] {return !events_.empty();}));
  EXPECT_EQ(events_.back(), HomeActionEvent::CANCELED);
}

TEST_F(HomeActionClientTest, ControllerErrorInSucceededActionReportsAbort)
{
  ASSERT_TRUE(client_->send_goal(plan()));
  ASSERT_TRUE(wait_until([this] {return static_cast<bool>(handle_);}));
  auto result = std::make_shared<FollowJT::Result>();
  result->error_code = FollowJT::Result::PATH_TOLERANCE_VIOLATED;
  handle_->succeed(result);
  ASSERT_TRUE(wait_until([this] {return !events_.empty();}));
  EXPECT_EQ(events_.back(), HomeActionEvent::ABORTED);
}
}  // namespace
