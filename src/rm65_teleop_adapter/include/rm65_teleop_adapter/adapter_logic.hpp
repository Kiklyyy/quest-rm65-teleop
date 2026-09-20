#pragma once

#include <array>
#include <optional>
#include <string>

namespace rm65_teleop_adapter
{

enum class AdapterState {DISABLED, ARMED, ACTIVE, REARM_REQUIRED, FAULT};
const char * state_name(AdapterState state);

struct Pose3
{
  std::array<double, 3> position{0.0, 0.0, 0.0};
  std::array<double, 4> orientation{0.0, 0.0, 0.0, 1.0};
};

struct AdapterConfig
{
  std::array<double, 9> mapping{1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
  double translation_scale{1.0};
  double max_velocity_mps{0.01};
  double max_step_m{0.0001};
  double unexpected_target_jump_m{0.10};
  std::array<double, 3> workspace_min{-1.0, -1.0, 0.0};
  std::array<double, 3> workspace_max{1.0, 1.0, 1.5};
};

struct CycleInput
{
  Pose3 target_pose;
  Pose3 robot_pose;
  bool enable{false};
  bool target_fresh{false};
  bool quest_pose_fresh{false};
  bool inputs_fresh{false};
  bool robot_fresh{false};
  double dt_seconds{0.0};
};

struct CycleOutput
{
  AdapterState state{AdapterState::DISABLED};
  std::optional<Pose3> command;
  bool anchor_captured{false};
  bool stop_requested{false};
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
  Pose3 quest_anchor_;
  Pose3 robot_anchor_;
  Pose3 last_command_;
  Pose3 last_target_;
  std::string fault_reason_;
};

}  // namespace rm65_teleop_adapter
