#include "rm65_teleop_adapter/quest_orientation_tracker.hpp"

#include <cmath>
#include <limits>

#include <gtest/gtest.h>

namespace rm65_teleop_adapter
{
namespace
{

constexpr double kPi = 3.14159265358979323846;
constexpr double kThreshold = 0.7853981633974483;

QuaternionXyzw identity()
{
  return {};
}

QuaternionXyzw axis_angle_z(const double angle)
{
  return {0.0, 0.0, std::sin(angle / 2.0), std::cos(angle / 2.0)};
}

TEST(QuestOrientationTracker, NormalizesAndStoresFirstValidSample)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.ingest({0.0, 0.0, 0.0, 2.0});
  const auto snapshot = tracker.consume_snapshot();
  EXPECT_TRUE(snapshot.has_valid_orientation);
  EXPECT_TRUE(snapshot.latest_sample_valid);
  EXPECT_EQ(snapshot.status, OrientationSampleStatus::VALID);
  EXPECT_DOUBLE_EQ(snapshot.latest_orientation.w, 1.0);
}

TEST(QuestOrientationTracker, InvalidSampleDoesNotReplaceLatestValidOrientation)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.ingest(identity());
  tracker.consume_snapshot();
  tracker.ingest({std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0, 1.0});
  const auto snapshot = tracker.consume_snapshot();
  EXPECT_TRUE(snapshot.has_valid_orientation);
  EXPECT_FALSE(snapshot.latest_sample_valid);
  EXPECT_EQ(snapshot.status, OrientationSampleStatus::INVALID);
  EXPECT_NEAR(shortest_angular_distance(snapshot.latest_orientation, identity()), 0.0, 1.0e-12);
}

TEST(QuestOrientationTracker, QuaternionSignFlipHasZeroJump)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.begin_active_session(identity());
  tracker.ingest({0.0, 0.0, 0.0, -1.0});
  const auto snapshot = tracker.consume_snapshot();
  EXPECT_EQ(snapshot.status, OrientationSampleStatus::VALID);
  EXPECT_NEAR(snapshot.jump_angle_rad, 0.0, 1.0e-12);
}

TEST(QuestOrientationTracker, InactiveFastRotationNeverEmitsJump)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.ingest(identity());
  tracker.ingest(axis_angle_z(kPi));
  EXPECT_EQ(tracker.consume_snapshot().status, OrientationSampleStatus::VALID);
}

TEST(QuestOrientationTracker, ActiveJumpExactlyAtThresholdIsValid)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.begin_active_session(identity());
  tracker.ingest(axis_angle_z(kThreshold));
  EXPECT_EQ(tracker.consume_snapshot().status, OrientationSampleStatus::VALID);
}

TEST(QuestOrientationTracker, ActiveJumpAboveThresholdIsUnexpected)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.begin_active_session(identity());
  tracker.ingest(axis_angle_z(kThreshold + 1.0e-6));
  const auto snapshot = tracker.consume_snapshot();
  EXPECT_EQ(snapshot.status, OrientationSampleStatus::UNEXPECTED_JUMP);
  EXPECT_GT(snapshot.jump_angle_rad, kThreshold);
}

TEST(QuestOrientationTracker, FirstFaultEventRemainsLatchedUntilConsumed)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.ingest({std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0, 1.0});
  tracker.ingest(identity());
  const auto fault = tracker.consume_snapshot();
  EXPECT_EQ(fault.status, OrientationSampleStatus::INVALID);
  EXPECT_TRUE(fault.latest_sample_valid);
  EXPECT_TRUE(fault.has_valid_orientation);
  EXPECT_EQ(tracker.consume_snapshot().status, OrientationSampleStatus::VALID);
}

TEST(QuestOrientationTracker, ConsumeClearsEventButPreservesLatestOrientation)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.ingest(axis_angle_z(0.2));
  const auto first = tracker.consume_snapshot();
  const auto second = tracker.consume_snapshot();
  EXPECT_EQ(second.status, OrientationSampleStatus::VALID);
  EXPECT_TRUE(second.has_valid_orientation);
  EXPECT_TRUE(second.latest_sample_valid);
  EXPECT_NEAR(
    shortest_angular_distance(first.latest_orientation, second.latest_orientation),
    0.0, 1.0e-12);
}

TEST(QuestOrientationTracker, BeginActiveSessionResetsBaselineToAnchor)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.ingest({std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0, 1.0});
  const auto anchor = axis_angle_z(1.2);
  tracker.begin_active_session(anchor);
  tracker.ingest(anchor);
  const auto snapshot = tracker.consume_snapshot();
  EXPECT_EQ(snapshot.status, OrientationSampleStatus::VALID);
  EXPECT_TRUE(snapshot.latest_sample_valid);
}

TEST(QuestOrientationTracker, EndActiveSessionDisablesJumpFaulting)
{
  QuestOrientationTracker tracker(kThreshold);
  tracker.begin_active_session(identity());
  tracker.end_active_session();
  tracker.ingest(axis_angle_z(kPi));
  EXPECT_FALSE(tracker.active_session());
  EXPECT_EQ(tracker.consume_snapshot().status, OrientationSampleStatus::VALID);
}

}  // namespace
}  // namespace rm65_teleop_adapter
