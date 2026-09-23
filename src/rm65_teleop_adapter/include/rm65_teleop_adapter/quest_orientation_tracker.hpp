#pragma once

#include <optional>

#include "rm65_teleop_adapter/quaternion_math.hpp"

namespace rm65_teleop_adapter
{

enum class OrientationSampleStatus {VALID, INVALID, UNEXPECTED_JUMP};

struct OrientationSnapshot
{
  QuaternionXyzw latest_orientation{};
  bool has_valid_orientation{false};
  bool latest_sample_valid{false};
  OrientationSampleStatus status{OrientationSampleStatus::VALID};
  double jump_angle_rad{0.0};
};

class QuestOrientationTracker
{
public:
  explicit QuestOrientationTracker(double unexpected_jump_rad);
  void ingest(const QuaternionXyzw & raw_orientation);
  OrientationSnapshot consume_snapshot();
  void begin_active_session(const QuaternionXyzw & normalized_anchor);
  void end_active_session();
  bool active_session() const;

private:
  double unexpected_jump_rad_;
  std::optional<QuaternionXyzw> latest_valid_;
  std::optional<QuaternionXyzw> previous_active_;
  bool latest_sample_valid_{false};
  bool active_session_{false};
  OrientationSampleStatus pending_status_{OrientationSampleStatus::VALID};
  double pending_jump_angle_rad_{0.0};
};

}  // namespace rm65_teleop_adapter
