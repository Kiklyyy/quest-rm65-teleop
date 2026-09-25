#include "rm65_teleop_adapter/quaternion_math.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>
#include <tuple>

#include <gtest/gtest.h>

namespace rm65_teleop_adapter
{
namespace
{

TEST(QuaternionMath, RejectsNonFiniteAndNearZeroNorm)
{
  EXPECT_FALSE(normalize_quaternion({NAN, 0.0, 0.0, 1.0}).has_value());
  EXPECT_FALSE(normalize_quaternion({0.0, 0.0, 0.0, 0.0}).has_value());
  EXPECT_FALSE(normalize_quaternion({1.0e-8, 0.0, 0.0, 0.0}).has_value());
}

TEST(QuaternionMath, NormalizesXyzwWithoutChangingOrientation)
{
  const auto value = normalize_quaternion({0.0, 0.0, 0.0, 2.0});
  ASSERT_TRUE(value.has_value());
  EXPECT_DOUBLE_EQ(value->x, 0.0);
  EXPECT_DOUBLE_EQ(value->y, 0.0);
  EXPECT_DOUBLE_EQ(value->z, 0.0);
  EXPECT_DOUBLE_EQ(value->w, 1.0);
}
constexpr double kPi = 3.14159265358979323846;
constexpr Matrix3RowMajor kVerifiedMapping{
  0.0, 0.0, 1.0,
  -1.0, 0.0, 0.0,
  0.0, -1.0, 0.0};

QuaternionXyzw axis_angle(double x, double y, double z, double angle)
{
  const double axis_norm = std::sqrt(x * x + y * y + z * z);
  const double sine = std::sin(angle / 2.0);
  return {x / axis_norm * sine, y / axis_norm * sine, z / axis_norm * sine,
    std::cos(angle / 2.0)};
}

QuaternionXyzw negate(const QuaternionXyzw & quaternion)
{
  return {-quaternion.x, -quaternion.y, -quaternion.z, -quaternion.w};
}

TEST(QuaternionMath, HamiltonProductUsesXyzwStorage)
{
  const auto result = hamilton_product(
    axis_angle(1.0, 0.0, 0.0, kPi / 2.0),
    axis_angle(0.0, 1.0, 0.0, kPi / 2.0));
  EXPECT_NEAR(result.x, 0.5, 1.0e-12);
  EXPECT_NEAR(result.y, 0.5, 1.0e-12);
  EXPECT_NEAR(result.z, 0.5, 1.0e-12);
  EXPECT_NEAR(result.w, 0.5, 1.0e-12);
}

TEST(QuaternionMath, RelativeWorldRotationAtAnchorIsIdentity)
{
  const auto anchor = axis_angle(1.0, 2.0, 3.0, 0.8);
  const auto result = relative_world_rotation(anchor, anchor);
  EXPECT_NEAR(shortest_angular_distance(result, {0.0, 0.0, 0.0, 1.0}), 0.0, 1.0e-12);
}

TEST(QuaternionMath, RelativeWorldRotationUsesCurrentTimesInverseAnchor)
{
  const auto anchor = axis_angle(1.0, 0.0, 0.0, kPi / 2.0);
  const auto expected_delta = axis_angle(0.0, 1.0, 0.0, kPi / 2.0);
  const auto current = hamilton_product(expected_delta, anchor);
  const auto actual = relative_world_rotation(current, anchor);
  EXPECT_NEAR(shortest_angular_distance(actual, expected_delta), 0.0, 1.0e-12);
}

TEST(QuaternionMath, RobotAnchorCompositionIsMappedDeltaTimesAnchor)
{
  const auto mapped_delta = axis_angle(0.0, 0.0, 1.0, kPi / 2.0);
  const auto robot_anchor = axis_angle(1.0, 0.0, 0.0, kPi / 2.0);
  const QuaternionXyzw expected{0.5, 0.5, 0.5, 0.5};
  const auto actual = compose_world_relative_rotation(mapped_delta, robot_anchor);
  EXPECT_NEAR(shortest_angular_distance(actual, expected), 0.0, 1.0e-12);
}

TEST(QuaternionMath, ShortestAngularDistanceReturnsKnownNinetyDegrees)
{
  EXPECT_NEAR(shortest_angular_distance(
    {0.0, 0.0, 0.0, 1.0}, axis_angle(0.0, 0.0, 1.0, kPi / 2.0)),
    kPi / 2.0, 1.0e-12);
}

TEST(QuaternionMath, QuaternionAndNegativeQuaternionHaveZeroDistance)
{
  const auto orientation = axis_angle(1.0, -2.0, 3.0, 1.1);
  EXPECT_NEAR(shortest_angular_distance(orientation, negate(orientation)), 0.0, 1.0e-12);
}

TEST(QuaternionMath, ShortestSlerpDoesNotTakeTheLongArc)
{
  const auto from = axis_angle(0.0, 0.0, 1.0, 170.0 * kPi / 180.0);
  const auto to = axis_angle(0.0, 0.0, 1.0, -170.0 * kPi / 180.0);
  const auto halfway = slerp_shortest(from, to, 0.5);
  const auto expected = axis_angle(0.0, 0.0, 1.0, kPi);
  EXPECT_NEAR(shortest_angular_distance(halfway, expected), 0.0, 1.0e-12);
}

TEST(QuaternionMath, SlerpRejectsNonFiniteOrOutOfRangeFraction)
{
  const QuaternionXyzw identity{};
  EXPECT_THROW(slerp_shortest(identity, identity, -0.1), std::invalid_argument);
  EXPECT_THROW(slerp_shortest(identity, identity, 1.1), std::invalid_argument);
  EXPECT_THROW(
    slerp_shortest(identity, identity, std::numeric_limits<double>::quiet_NaN()),
    std::invalid_argument);
}

TEST(QuaternionMath, QuaternionMatrixRoundTripPreservesRotation)
{
  const auto original = axis_angle(1.0, 2.0, 3.0, 1.2);
  const auto restored = rotation_matrix_to_quaternion(
    quaternion_to_rotation_matrix(original));
  ASSERT_TRUE(restored.has_value());
  EXPECT_NEAR(shortest_angular_distance(*restored, original), 0.0, 1.0e-12);
}

TEST(QuaternionMath, ScaleShortestRotationMapsNinetyDegreesToFortyFiveDegrees)
{
  const auto scaled = scale_shortest_rotation(
    axis_angle(1.0, 0.0, 0.0, kPi / 2.0), 0.5);
  const auto expected = axis_angle(1.0, 0.0, 0.0, kPi / 4.0);
  EXPECT_NEAR(shortest_angular_distance(scaled, expected), 0.0, 1.0e-12);
}

TEST(QuaternionMath, RotationScaleOnePreservesAngle)
{
  const auto original = axis_angle(1.0, -2.0, 3.0, 0.7);
  const auto scaled = scale_shortest_rotation(original, 1.0);
  EXPECT_NEAR(shortest_angular_distance(scaled, original), 0.0, 1.0e-12);
}

TEST(QuaternionMath, QuestBasisRotationsMapToRmMinusYMinusZPlusX)
{
  const std::vector<std::tuple<QuaternionXyzw, QuaternionXyzw>> cases{
    {axis_angle(1.0, 0.0, 0.0, kPi / 2.0),
      axis_angle(0.0, -1.0, 0.0, kPi / 2.0)},
    {axis_angle(0.0, 1.0, 0.0, kPi / 2.0),
      axis_angle(0.0, 0.0, -1.0, kPi / 2.0)},
    {axis_angle(0.0, 0.0, 1.0, kPi / 2.0),
      axis_angle(1.0, 0.0, 0.0, kPi / 2.0)}};
  for (const auto & [quest, expected_rm] : cases) {
    const auto actual = map_relative_rotation(quest, kVerifiedMapping);
    EXPECT_NEAR(shortest_angular_distance(actual, expected_rm), 0.0, 1.0e-12);
  }
}

TEST(QuaternionMath, VerifiedMappingIsProperRotation)
{
  EXPECT_TRUE(is_proper_rotation_matrix(kVerifiedMapping));
}

TEST(QuaternionMath, RejectsReflectionScaledAndNonFiniteMappings)
{
  const Matrix3RowMajor reflection{1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1.0};
  const Matrix3RowMajor scaled{2.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
  auto non_finite = kVerifiedMapping;
  non_finite[0] = std::numeric_limits<double>::infinity();
  EXPECT_FALSE(is_proper_rotation_matrix(reflection));
  EXPECT_FALSE(is_proper_rotation_matrix(scaled));
  EXPECT_FALSE(is_proper_rotation_matrix(non_finite));
}

TEST(QuaternionMath, RotationMatrixConversionRejectsImproperMatrix)
{
  const Matrix3RowMajor reflection{1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1.0};
  EXPECT_FALSE(rotation_matrix_to_quaternion(reflection).has_value());
}

constexpr Matrix3RowMajor kLeftMapping{
  0.0, 0.0, -1.0,
  -1.0, 0.0, 0.0,
  0.0, 1.0, 0.0};

TEST(QuaternionMath, LeftMappingIsProperAndMapsAllBasisRotations)
{
  EXPECT_TRUE(is_proper_rotation_matrix(kLeftMapping));
  const std::vector<std::tuple<QuaternionXyzw, QuaternionXyzw>> cases{
    {axis_angle(1.0, 0.0, 0.0, kPi / 2.0),
      axis_angle(0.0, -1.0, 0.0, kPi / 2.0)},
    {axis_angle(0.0, 1.0, 0.0, kPi / 2.0),
      axis_angle(0.0, 0.0, 1.0, kPi / 2.0)},
    {axis_angle(0.0, 0.0, 1.0, kPi / 2.0),
      axis_angle(-1.0, 0.0, 0.0, kPi / 2.0)}};
  for (const auto & [quest, expected_rm] : cases) {
    const auto mapped = map_relative_rotation(quest, kLeftMapping);
    EXPECT_NEAR(shortest_angular_distance(mapped, expected_rm), 0.0, 1.0e-12);
    const auto sign_equivalent = map_relative_rotation(negate(quest), kLeftMapping);
    EXPECT_NEAR(shortest_angular_distance(mapped, sign_equivalent), 0.0, 1.0e-12);
    const auto normalized = normalize_quaternion(mapped);
    ASSERT_TRUE(normalized.has_value());
    EXPECT_NEAR(quaternion_dot(*normalized, *normalized), 1.0, 1.0e-12);
  }
}

TEST(QuaternionMath, LeftWorldDeltaMultipliesRobotAnchorOnLeft)
{
  const auto quest_anchor = axis_angle(1.0, 0.0, 0.0, 0.7);
  const auto quest_delta = axis_angle(0.0, 1.0, 0.0, 0.4);
  const auto quest_current = hamilton_product(quest_delta, quest_anchor);
  const auto robot_anchor = axis_angle(1.0, 0.0, 0.0, 0.5);
  const auto mapped = map_relative_rotation(
    relative_world_rotation(quest_current, quest_anchor), kLeftMapping);
  const auto result = compose_world_relative_rotation(mapped, robot_anchor);
  const auto expected = hamilton_product(
    axis_angle(0.0, 0.0, 1.0, 0.4), robot_anchor);
  EXPECT_NEAR(shortest_angular_distance(result, expected), 0.0, 1.0e-12);
  const auto body_frame_wrong = hamilton_product(robot_anchor, mapped);
  EXPECT_GT(shortest_angular_distance(result, body_frame_wrong), 0.01);
}

}  // namespace
}  // namespace rm65_teleop_adapter
