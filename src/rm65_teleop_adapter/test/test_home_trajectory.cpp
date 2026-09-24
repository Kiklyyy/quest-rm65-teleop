#include <cmath>
#include <limits>
#include "gtest/gtest.h"
#include "rm65_teleop_adapter/home_trajectory.hpp"

namespace
{
using namespace rm65_teleop_adapter;
HomeTrajectoryConfig valid_config()
{
  return {{68.3241063822369, -8.489398369548377, 60.14265142722264, 31.52005176840807, 51.634258495569824, -144.10081659391062},
          {"joint1", "joint2", "joint3", "joint4", "joint5", "joint6"}, 15.0, 1.5};
}

TEST(HomeTrajectory, ValidatesCompleteConfig)
{
  auto cfg = valid_config();
  EXPECT_TRUE(home_trajectory_config_valid(cfg));
  cfg.target_degrees[2] = std::numeric_limits<double>::quiet_NaN();
  EXPECT_FALSE(home_trajectory_config_valid(cfg));
  cfg = valid_config(); cfg.joint_names[3] = cfg.joint_names[2];
  EXPECT_FALSE(home_trajectory_config_valid(cfg));
  cfg = valid_config(); cfg.joint_names[0] = "";
  EXPECT_FALSE(home_trajectory_config_valid(cfg));
  cfg = valid_config(); cfg.speed_deg_s = 0.0;
  EXPECT_FALSE(home_trajectory_config_valid(cfg));
  cfg = valid_config(); cfg.hold_seconds = std::numeric_limits<double>::infinity();
  EXPECT_FALSE(home_trajectory_config_valid(cfg));
}

TEST(HomeTrajectory, ReordersShuffledJointState)
{
  auto result = reorder_joint_positions(
    {"joint3", "joint1", "joint6", "joint2", "joint5", "joint4"},
    {3, 1, 6, 2, 5, 4}, valid_config().joint_names);
  ASSERT_TRUE(result);
  EXPECT_EQ(*result, (std::array<double, 6>{1, 2, 3, 4, 5, 6}));
}

TEST(HomeTrajectory, RejectsMalformedJointState)
{
  auto names = valid_config().joint_names;
  EXPECT_FALSE(reorder_joint_positions(
    {"joint1", "joint2", "joint3", "joint4", "joint5"}, {1,2,3,4,5}, names));
  EXPECT_FALSE(reorder_joint_positions(
    {"joint1", "joint2", "joint3", "joint4", "joint5", "joint5"},
    {1,2,3,4,5,6}, names));
  EXPECT_FALSE(reorder_joint_positions(
    {"joint1", "joint2", "joint3", "joint4", "joint5", "joint6"},
    {1,2,3,4,5}, names));
  EXPECT_FALSE(reorder_joint_positions(
    {"joint1", "joint2", "joint3", "joint4", "joint5", "joint6"},
    {1,2,3,4,5,std::numeric_limits<double>::infinity()}, names));
}

TEST(HomeTrajectory, SpeedBoundAndNearHomeMinimum)
{
  auto cfg = valid_config();
  cfg.target_degrees = {30, 0, 0, 0, 0, 0};
  auto plan = make_home_trajectory_plan({0,0,0,0,0,0}, cfg);
  ASSERT_TRUE(plan);
  EXPECT_NEAR(plan->duration_seconds, 2.0, 1e-12);
  EXPECT_NEAR(plan->target_radians[0], 30.0 * 3.14159265358979323846 / 180.0, 1e-12);
  cfg.target_degrees[0] = 0.001;
  plan = make_home_trajectory_plan({0,0,0,0,0,0}, cfg);
  ASSERT_TRUE(plan);
  EXPECT_GE(plan->duration_seconds, 0.001 / 15.0);
  EXPECT_GT(plan->duration_seconds, 0.0);
  EXPECT_FALSE(make_home_trajectory_plan(
    {std::numeric_limits<double>::quiet_NaN(),0,0,0,0,0}, cfg));
}
}  // namespace
