#include "rm65_teleop_adapter/adapter_logic.hpp"

#include <algorithm>
#include <cmath>
#include <utility>

namespace rm65_teleop_adapter
{
namespace
{
double norm3(const std::array<double, 3> & value)
{
  return std::sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2]);
}
std::array<double, 3> subtract(const std::array<double, 3> & lhs, const std::array<double, 3> & rhs)
{
  return {lhs[0] - rhs[0], lhs[1] - rhs[1], lhs[2] - rhs[2]};
}
}  // namespace

const char * state_name(AdapterState state)
{
  switch (state) {
    case AdapterState::DISABLED: return "DISABLED";
    case AdapterState::ARMED: return "ARMED";
    case AdapterState::ACTIVE: return "ACTIVE";
    case AdapterState::REARM_REQUIRED: return "REARM_REQUIRED";
    case AdapterState::FAULT: return "FAULT";
  }
  return "UNKNOWN";
}

AdapterLogic::AdapterLogic(AdapterConfig config) : config_(std::move(config)) {}

bool AdapterLogic::all_fresh(const CycleInput & input) const
{
  return input.target_fresh && input.quest_pose_fresh && input.inputs_fresh && input.robot_fresh;
}

bool AdapterLogic::pose_is_finite(const Pose3 & pose) const
{
  for (const double value : pose.position) if (!std::isfinite(value)) return false;
  double norm_squared = 0.0;
  for (const double value : pose.orientation) {
    if (!std::isfinite(value)) return false;
    norm_squared += value * value;
  }
  return norm_squared > 0.5 && norm_squared < 1.5;
}

bool AdapterLogic::inside_workspace(const std::array<double, 3> & point) const
{
  for (std::size_t i = 0; i < point.size(); ++i) {
    if (point[i] < config_.workspace_min[i] || point[i] > config_.workspace_max[i]) return false;
  }
  return true;
}

void AdapterLogic::enter_rearm(bool enable_pressed, const std::string & reason)
{
  state_ = AdapterState::REARM_REQUIRED;
  release_observed_ = !enable_pressed;
  fault_reason_ = reason;
}

void AdapterLogic::enter_fault(const std::string & reason)
{
  state_ = AdapterState::FAULT;
  release_observed_ = false;
  fault_reason_ = reason;
}

bool AdapterLogic::clear_fault(bool enable_pressed)
{
  if (state_ != AdapterState::FAULT || enable_pressed) return false;
  state_ = AdapterState::REARM_REQUIRED;
  release_observed_ = true;
  fault_reason_.clear();
  return true;
}

CycleOutput AdapterLogic::update(const CycleInput & input)
{
  CycleOutput output;
  const bool was_active = state_ == AdapterState::ACTIVE;
  if (!pose_is_finite(input.target_pose) || !pose_is_finite(input.robot_pose)) {
    enter_fault("non_finite_or_invalid_pose");
    output.state = state_;
    output.stop_requested = was_active;
    output.reason = fault_reason_;
    return output;
  }
  if (state_ == AdapterState::FAULT) {
    output.state = state_;
    output.reason = fault_reason_;
    return output;
  }

  const bool fresh = all_fresh(input);
  if (state_ == AdapterState::DISABLED) {
    if (!input.enable && fresh) {
      release_observed_ = true;
      state_ = AdapterState::ARMED;
      fault_reason_.clear();
    } else if (input.enable) {
      enter_rearm(true, "startup_requires_release");
    }
  } else if (state_ == AdapterState::ARMED) {
    if (!fresh) {
      enter_rearm(input.enable, "input_not_fresh");
    } else if (input.enable && !input.command_path_ready) {
      enter_fault("command_path_not_ready");
    } else if (input.enable) {
      quest_anchor_ = input.target_pose;
      robot_anchor_ = input.robot_pose;
      last_command_ = robot_anchor_;
      last_target_ = input.target_pose;
      state_ = AdapterState::ACTIVE;
      release_observed_ = false;
      fault_reason_.clear();
      output.command = last_command_;
      output.anchor_captured = true;
    }
  } else if (state_ == AdapterState::REARM_REQUIRED) {
    if (!input.enable) release_observed_ = true;
    if (release_observed_ && !input.enable && fresh) {
      state_ = AdapterState::ARMED;
      fault_reason_.clear();
    }
  } else if (state_ == AdapterState::ACTIVE) {
    if (!input.enable) {
      enter_rearm(false, "deadman_released");
      output.stop_requested = true;
    } else if (!fresh) {
      enter_rearm(true, "input_not_fresh");
      output.stop_requested = true;
    } else if (!input.command_path_ready) {
      enter_fault("command_path_not_ready");
      output.stop_requested = true;
    } else if (!input.control_period_valid) {
      enter_fault("control_period_exceeded");
      output.stop_requested = true;
    } else if (!std::isfinite(input.dt_seconds) || input.dt_seconds <= 0.0) {
      enter_fault("invalid_control_period");
      output.stop_requested = true;
    } else {
      const auto target_step = subtract(input.target_pose.position, last_target_.position);
      if (norm3(target_step) > config_.unexpected_target_jump_m) {
        enter_fault("unexpected_target_jump");
        output.stop_requested = true;
      } else {
        last_target_ = input.target_pose;
        const auto quest_delta = subtract(input.target_pose.position, quest_anchor_.position);
        Pose3 desired = robot_anchor_;
        for (std::size_t row = 0; row < 3; ++row) {
          double mapped = 0.0;
          for (std::size_t column = 0; column < 3; ++column) {
            mapped += config_.mapping[row * 3 + column] * quest_delta[column];
          }
          desired.position[row] += config_.translation_scale * mapped;
        }
        const double anchor_distance = norm3(subtract(desired.position, robot_anchor_.position));
        if (anchor_distance > config_.max_anchor_distance_m) {
          enter_fault("anchor_distance_violation");
          output.stop_requested = true;
        } else if (!inside_workspace(desired.position)) {
          enter_fault("workspace_violation");
          output.stop_requested = true;
        } else {
          const auto command_delta = subtract(desired.position, last_command_.position);
          const double distance = norm3(command_delta);
          const double allowed = std::min(config_.max_step_m, config_.max_velocity_mps * input.dt_seconds);
          if (!std::isfinite(allowed) || allowed <= 0.0) {
            enter_fault("invalid_motion_limit");
            output.stop_requested = true;
          } else {
            const double ratio = distance > allowed ? allowed / distance : 1.0;
            for (std::size_t i = 0; i < 3; ++i) last_command_.position[i] += command_delta[i] * ratio;
            last_command_.orientation = robot_anchor_.orientation;
            output.command = last_command_;
          }
        }
      }
    }
  }
  output.state = state_;
  output.reason = fault_reason_;
  return output;
}

}  // namespace rm65_teleop_adapter
