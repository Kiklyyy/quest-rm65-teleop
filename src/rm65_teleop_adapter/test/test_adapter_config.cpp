#include "rm65_teleop_adapter/adapter_logic.hpp"
#include "rm65_teleop_adapter/home_config.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

#include <gtest/gtest.h>

namespace rm65_teleop_adapter
{
namespace
{

constexpr double kPi = 3.14159265358979323846;

Matrix3RowMajor verified_mapping()
{
  return {
    0.0, 0.0, 1.0,
    -1.0, 0.0, 0.0,
    0.0, -1.0, 0.0};
}

void expect_invalid_config(
  const AdapterConfig & config, const std::string & expected_substring)
{
  try {
    const AdapterLogic logic(config);
    static_cast<void>(logic);
    FAIL() << "Expected std::invalid_argument";
  } catch (const std::invalid_argument & error) {
    EXPECT_NE(std::string(error.what()).find(expected_substring), std::string::npos)
      << error.what();
  }
}

TEST(AdapterConfigValidation, AcceptsVerifiedMappingAndOrientationEnvelope)
{
  AdapterConfig config;
  config.mapping = verified_mapping();
  config.rotation_scale = 1.0;
  config.max_angular_velocity_rad_s = 1.5707963267948966;
  config.max_angular_step_rad = 0.01;
  config.max_anchor_angle_rad = 1.5707963267948966;
  config.unexpected_orientation_jump_rad = 0.7853981633974483;
  EXPECT_NO_THROW({
    const AdapterLogic logic(config);
    static_cast<void>(logic);
  });
}

TEST(AdapterConfigValidation, RejectsNonFiniteMappingEntry)
{
  AdapterConfig config;
  config.mapping = verified_mapping();
  config.mapping[0] = std::numeric_limits<double>::quiet_NaN();
  expect_invalid_config(config, "proper rotation matrix");
}

TEST(AdapterConfigValidation, RejectsNonOrthogonalScaledMapping)
{
  AdapterConfig config;
  config.mapping[0] = 2.0;
  expect_invalid_config(config, "proper rotation matrix");
}

TEST(AdapterConfigValidation, RejectsReflectionWithNegativeDeterminant)
{
  AdapterConfig config;
  config.mapping = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1.0};
  expect_invalid_config(config, "proper rotation matrix");
}

TEST(AdapterConfigValidation, RejectsNonFiniteOrNonPositiveRotationScale)
{
  for (const double value : {
      0.0, -1.0, std::numeric_limits<double>::infinity(),
      std::numeric_limits<double>::quiet_NaN()})
  {
    AdapterConfig config;
    config.rotation_scale = value;
    expect_invalid_config(config, "rotation_scale");
  }
}

TEST(AdapterConfigValidation, RejectsNonFiniteOrNonPositiveAngularVelocity)
{
  for (const double value : {
      0.0, -1.0, std::numeric_limits<double>::infinity(),
      std::numeric_limits<double>::quiet_NaN()})
  {
    AdapterConfig config;
    config.max_angular_velocity_rad_s = value;
    expect_invalid_config(config, "max_angular_velocity_rad_s");
  }
}

TEST(AdapterConfigValidation, RejectsNonFiniteOrNonPositiveAngularStep)
{
  for (const double value : {
      0.0, -1.0, std::numeric_limits<double>::infinity(),
      std::numeric_limits<double>::quiet_NaN()})
  {
    AdapterConfig config;
    config.max_angular_step_rad = value;
    expect_invalid_config(config, "max_angular_step_rad");
  }
}

TEST(AdapterConfigValidation, AcceptsRightHardwareAnchorAngleOf270Degrees)
{
  AdapterConfig config;
  config.max_anchor_angle_rad = 1.5 * kPi;
  EXPECT_NO_THROW({
    const AdapterLogic logic(config);
    static_cast<void>(logic);
  });
}

TEST(AdapterConfigValidation, RejectsAnchorAngleOutsideZeroToTwoPi)
{
  for (const double value : {
      0.0, -1.0, 2.0 * kPi + 1.0e-6, std::numeric_limits<double>::infinity(),
      std::numeric_limits<double>::quiet_NaN()})
  {
    AdapterConfig config;
    config.max_anchor_angle_rad = value;
    expect_invalid_config(config, "max_anchor_angle_rad must be in (0, 2*pi]");
  }
}

TEST(AdapterConfigValidation, RejectsJumpAngleOutsideZeroToPi)
{
  for (const double value : {
      0.0, -1.0, kPi + 1.0e-6, std::numeric_limits<double>::infinity(),
      std::numeric_limits<double>::quiet_NaN()})
  {
    AdapterConfig config;
    config.unexpected_orientation_jump_rad = value;
    expect_invalid_config(config, "unexpected_orientation_jump_rad must be in (0, pi]");
  }
}


HomeParameterSet valid_home_parameters()
{
  HomeParameterSet p;
  p.dry_run = false;
  p.enabled = true;
  p.button_field = "upper";
  p.action_name = "/right/rm_group_controller/follow_joint_trajectory";
  p.joint_degrees = {68.3241063822369, -8.489398369548377, 60.14265142722264, 31.52005176840807, 51.634258495569824, -144.10081659391062};
  p.joint_names = {"joint1", "joint2", "joint3", "joint4", "joint5", "joint6"};
  p.speed_deg_s = 15.0;
  p.hold_seconds = 1.5;
  return p;
}

TEST(HomeConfigValidation, AcceptsConfirmedHardwareParameters)
{
  auto resolved = resolve_home_config(valid_home_parameters());
  ASSERT_TRUE(resolved);
  EXPECT_EQ(resolved->button_field, QuestFaceButtonField::UPPER);
  EXPECT_EQ(resolved->trajectory.joint_names[0], "joint1");
}

TEST(HomeConfigValidation, RejectsInvalidFieldsAndDryRun)
{
  auto p = valid_home_parameters();
  p.dry_run = true; EXPECT_FALSE(resolve_home_config(p));
  p = valid_home_parameters(); p.button_field = "unknown";
  EXPECT_FALSE(resolve_home_config(p));
  p = valid_home_parameters(); p.joint_degrees.pop_back();
  EXPECT_FALSE(resolve_home_config(p));
  p = valid_home_parameters(); p.joint_names.pop_back();
  EXPECT_FALSE(resolve_home_config(p));
  p = valid_home_parameters(); p.joint_names[1] = "joint1";
  EXPECT_FALSE(resolve_home_config(p));
  p = valid_home_parameters(); p.speed_deg_s = 0;
  EXPECT_FALSE(resolve_home_config(p));
  p = valid_home_parameters(); p.hold_seconds = 0;
  EXPECT_FALSE(resolve_home_config(p));
  p = valid_home_parameters(); p.action_name = "";
  EXPECT_FALSE(resolve_home_config(p));
}
}  // namespace
}  // namespace rm65_teleop_adapter
