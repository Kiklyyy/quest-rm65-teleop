#include "rm65_teleop_adapter/adapter_logic.hpp"

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

TEST(AdapterConfigValidation, RejectsAnchorAngleOutsideZeroToPi)
{
  for (const double value : {
      0.0, -1.0, kPi + 1.0e-6, std::numeric_limits<double>::infinity(),
      std::numeric_limits<double>::quiet_NaN()})
  {
    AdapterConfig config;
    config.max_anchor_angle_rad = value;
    expect_invalid_config(config, "max_anchor_angle_rad must be in (0, pi]");
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

}  // namespace
}  // namespace rm65_teleop_adapter
