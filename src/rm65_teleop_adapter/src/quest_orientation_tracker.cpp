#include "rm65_teleop_adapter/quest_orientation_tracker.hpp"

#include <cmath>
#include <limits>

namespace rm65_teleop_adapter
{

QuestOrientationTracker::QuestOrientationTracker(const double unexpected_jump_rad)
: unexpected_jump_rad_(unexpected_jump_rad)
{
}

void QuestOrientationTracker::ingest(const QuaternionXyzw & raw_orientation)
{
  const auto normalized = normalize_quaternion(raw_orientation);
  if (!normalized) {
    latest_sample_valid_ = false;
    if (pending_status_ == OrientationSampleStatus::VALID) {
      pending_status_ = OrientationSampleStatus::INVALID;
      pending_jump_angle_rad_ = 0.0;
    }
    return;
  }

  auto candidate = *normalized;
  if (latest_valid_) {
    candidate = align_quaternion_hemisphere(*latest_valid_, candidate);
  }

  if (active_session_ && previous_active_) {
    candidate = align_quaternion_hemisphere(*previous_active_, candidate);
    const double jump_angle = shortest_angular_distance(*previous_active_, candidate);
    const double threshold_upper_bound =
      std::nextafter(unexpected_jump_rad_, std::numeric_limits<double>::infinity());
    if (jump_angle > threshold_upper_bound) {
      if (pending_status_ == OrientationSampleStatus::VALID) {
        pending_status_ = OrientationSampleStatus::UNEXPECTED_JUMP;
        pending_jump_angle_rad_ = jump_angle;
      }
    } else {
      previous_active_ = candidate;
    }
  }

  latest_valid_ = candidate;
  latest_sample_valid_ = true;
}

OrientationSnapshot QuestOrientationTracker::consume_snapshot()
{
  OrientationSnapshot snapshot;
  if (latest_valid_) {
    snapshot.latest_orientation = *latest_valid_;
    snapshot.has_valid_orientation = true;
  }
  snapshot.latest_sample_valid = latest_sample_valid_;
  snapshot.status = pending_status_;
  snapshot.jump_angle_rad = pending_jump_angle_rad_;

  pending_status_ = OrientationSampleStatus::VALID;
  pending_jump_angle_rad_ = 0.0;
  return snapshot;
}

void QuestOrientationTracker::begin_active_session(
  const QuaternionXyzw & normalized_anchor)
{
  previous_active_ = normalized_anchor;
  active_session_ = true;
  pending_status_ = OrientationSampleStatus::VALID;
  pending_jump_angle_rad_ = 0.0;
}

void QuestOrientationTracker::end_active_session()
{
  active_session_ = false;
  previous_active_.reset();
}

bool QuestOrientationTracker::active_session() const
{
  return active_session_;
}

}  // namespace rm65_teleop_adapter
