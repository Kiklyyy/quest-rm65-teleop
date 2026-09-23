#pragma once

#include <array>
#include <optional>
#include <string>

#include "rm65_teleop_adapter/quaternion_math.hpp"
#include "rm65_teleop_adapter/quest_orientation_tracker.hpp"

namespace rm65_teleop_adapter
{

enum class AdapterState {DISABLED, ARMED, ACTIVE, HOMING, REARM_REQUIRED, FAULT};
enum class HomeActionEvent {NONE, SUCCEEDED, CANCELED, REJECTED, ABORTED};
const char * state_name(AdapterState state);

struct Pose3
{
  std::array<double, 3> position{0.0, 0.0, 0.0};
  QuaternionXyzw orientation{};
};

struct AdapterConfig
{
  Matrix3RowMajor mapping{1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
  double home_hold_seconds{1.5};
  double translation_scale{1.0};
  double max_velocity_mps{0.01};
  double max_step_m{0.0001};
  double max_anchor_distance_m{0.03};
  double unexpected_target_jump_m{0.10};
  double rotation_scale{1.0};
  double max_angular_velocity_rad_s{1.5707963267948966};
  double max_angular_step_rad{0.01};
  double max_anchor_angle_rad{1.5707963267948966};
  double unexpected_orientation_jump_rad{0.7853981633974483};
  std::array<double, 3> workspace_min{-1.0, -1.0, 0.0};
  std::array<double, 3> workspace_max{1.0, 1.0, 1.5};
};

struct CycleInput
{
  Pose3 target_pose;
  Pose3 robot_pose;
  QuaternionXyzw quest_orientation{};
  bool quest_orientation_valid{false};
  bool robot_orientation_valid{false};
  OrientationSampleStatus quest_orientation_status{OrientationSampleStatus::VALID};
  double quest_orientation_jump_rad{0.0};
  bool enable{false};
  bool home_button_pressed{false};
  bool joint_state_fresh{false};
  bool joint_state_valid{false};
  bool home_action_ready{false};
  bool home_plan_valid{false};
  HomeActionEvent home_action_event{HomeActionEvent::NONE};
  bool target_fresh{false};
  bool quest_pose_fresh{false};
  bool inputs_fresh{false};
  bool robot_fresh{false};
  bool control_period_valid{true};
  bool command_path_ready{true};
  double dt_seconds{0.0};
};

struct CycleOutput
{
  AdapterState state{AdapterState::DISABLED};
  std::optional<Pose3> command;
  bool anchor_captured{false};
  bool stop_requested{false};
  bool home_goal_requested{false};
  bool home_cancel_requested{false};
  double home_hold_progress{0.0};
  std::string reason;
};

class AdapterLogic
{
public:
  explicit AdapterLogic(AdapterConfig config = AdapterConfig{});
  CycleOutput update(const CycleInput & input);
  bool clear_fault(bool enable_pressed);
  AdapterState state() const {return state_;}
  const std::string & fault_reason() const {return fault_reason_;}

private:
  bool all_fresh(const CycleInput & input) const;
  bool pose_is_finite(const Pose3 & pose) const;
  bool inside_workspace(const std::array<double, 3> & point) const;
  void enter_rearm(bool enable_pressed, const std::string & reason);
  void enter_fault(const std::string & reason);

  AdapterConfig config_;
  AdapterState state_{AdapterState::DISABLED};
  bool release_observed_{false};
  double home_hold_elapsed_seconds_{0.0};
  bool home_request_latched_{false};
  bool home_cancel_pending_{false};
  bool home_rearm_pending_{false};
  Pose3 quest_anchor_;
  QuaternionXyzw quest_orientation_anchor_;
  Pose3 robot_anchor_;
  Pose3 last_command_;
  Pose3 last_target_;
  std::string fault_reason_;
};

}  // namespace rm65_teleop_adapter
