#include "rm65_teleop_adapter/adapter_logic.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace rm65_teleop_adapter
{
namespace
{
double norm3(const std::array<double, 3> & value)
{
  return std::sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2]);
}

std::array<double, 3> subtract(
  const std::array<double, 3> & lhs, const std::array<double, 3> & rhs)
{
  return {lhs[0] - rhs[0], lhs[1] - rhs[1], lhs[2] - rhs[2]};
}

bool exceeds_strict_threshold(const double value, const double threshold)
{
  return value > std::nextafter(threshold, std::numeric_limits<double>::infinity());
}

void require_finite_positive(const char * name, const double value)
{
  if (!std::isfinite(value) || value <= 0.0) {
    throw std::invalid_argument(
            std::string(name) + " must be finite and greater than zero");
  }
}

void require_angle_in_zero_pi(const char * name, const double value)
{
  constexpr double kPi = 3.14159265358979323846;
  if (!std::isfinite(value) || value <= 0.0 || value > kPi) {
    throw std::invalid_argument(std::string(name) + " must be in (0, pi]");
  }
}

void require_anchor_angle_in_zero_two_pi(const double value)
{
  constexpr double kTwoPi = 6.28318530717958647692;
  if (!std::isfinite(value) || value <= 0.0 || value > kTwoPi) {
    throw std::invalid_argument("max_anchor_angle_rad must be in (0, 2*pi]");
  }
}

}  // namespace

const char * state_name(AdapterState state)
{
  switch (state) {
    case AdapterState::DISABLED: return "DISABLED";
    case AdapterState::ARMED: return "ARMED";
    case AdapterState::ACTIVE: return "ACTIVE";
    case AdapterState::HOMING: return "HOMING";
    case AdapterState::REARM_REQUIRED: return "REARM_REQUIRED";
    case AdapterState::FAULT: return "FAULT";
  }
  return "UNKNOWN";
}

AdapterLogic::AdapterLogic(AdapterConfig config) : config_(std::move(config))
{
  if (!is_proper_rotation_matrix(config_.mapping)) {
    throw std::invalid_argument("mapping must be a finite proper rotation matrix");
  }
  require_finite_positive("home_hold_seconds", config_.home_hold_seconds);
  require_finite_positive("rotation_scale", config_.rotation_scale);
  require_finite_positive(
    "max_angular_velocity_rad_s", config_.max_angular_velocity_rad_s);
  require_finite_positive("max_angular_step_rad", config_.max_angular_step_rad);
  require_anchor_angle_in_zero_two_pi(config_.max_anchor_angle_rad);
  require_angle_in_zero_pi(
    "unexpected_orientation_jump_rad", config_.unexpected_orientation_jump_rad);
}

bool AdapterLogic::all_fresh(const CycleInput & input) const
{
  return input.target_fresh && input.quest_pose_fresh && input.inputs_fresh &&
         input.robot_fresh && input.quest_orientation_valid && input.robot_orientation_valid;
}

bool AdapterLogic::pose_is_finite(const Pose3 & pose) const
{
  for (const double value : pose.position) {
    if (!std::isfinite(value)) return false;
  }
  return true;
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
  if (!input.home_button_pressed) {
    home_request_latched_ = false;
    home_hold_elapsed_seconds_ = 0.0;
  }
  if (state_ == AdapterState::HOMING) {
    output.home_hold_progress = 1.0;
    if (input.home_action_event == HomeActionEvent::SUCCEEDED) {
      home_cancel_pending_ = false;
      home_rearm_pending_ = true;
      enter_rearm(true, "home_succeeded");
    } else if (input.home_action_event == HomeActionEvent::CANCELED) {
      home_cancel_pending_ = false;
      home_rearm_pending_ = true;
      enter_rearm(true, fault_reason_.empty() ? "home_canceled" : fault_reason_);
    } else if (input.home_action_event == HomeActionEvent::REJECTED) {
      home_cancel_pending_ = false;
      enter_fault("home_goal_rejected");
      output.stop_requested = true;
    } else if (input.home_action_event == HomeActionEvent::ABORTED) {
      home_cancel_pending_ = false;
      enter_fault("home_goal_aborted");
      output.stop_requested = true;
    } else if (!home_cancel_pending_) {
      const char * cancel_reason = nullptr;
      if (!input.home_button_pressed) cancel_reason = "home_button_released";
      else if (!input.control_period_valid) cancel_reason = "home_control_period_exceeded";
      else if (!input.quest_pose_fresh) cancel_reason = "home_quest_pose_not_fresh";
      else if (!input.inputs_fresh) cancel_reason = "home_inputs_not_fresh";
      else if (!input.home_inputs_fresh) cancel_reason = "home_preset_inputs_not_fresh";
      else if (!input.robot_fresh) cancel_reason = "home_robot_not_fresh";
      else if (!input.quest_orientation_valid ||
               input.quest_orientation_status == OrientationSampleStatus::INVALID ||
               !normalize_quaternion(input.quest_orientation))
        cancel_reason = "home_quest_pose_invalid";
      else if (!input.robot_orientation_valid ||
               !normalize_quaternion(input.robot_pose.orientation))
        cancel_reason = "home_robot_pose_invalid";
      else if (!input.joint_state_fresh) cancel_reason = "home_joint_state_not_fresh";
      else if (!input.joint_state_valid) cancel_reason = "home_joint_state_invalid";
      else if (!input.target_fresh) cancel_reason = "home_target_not_fresh";
      else if (!pose_is_finite(input.target_pose) || !pose_is_finite(input.robot_pose))
        cancel_reason = "home_pose_invalid";
      else if (!input.command_path_ready || !input.home_command_path_ready)
        cancel_reason = "home_command_path_not_ready";
      else if (!input.home_action_ready) cancel_reason = "home_action_not_ready";
      if (cancel_reason) {
        fault_reason_ = cancel_reason;
        home_cancel_pending_ = true;
        output.home_cancel_requested = true;
        output.stop_requested = true;
      }
    }
    output.state = state_;
    output.reason = fault_reason_;
    return output;
  }
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
    const auto normalized_quest = normalize_quaternion(input.quest_orientation);
    const auto normalized_robot = normalize_quaternion(input.robot_pose.orientation);
    if (input.enable &&
      (!input.quest_orientation_valid ||
      input.quest_orientation_status == OrientationSampleStatus::INVALID ||
      !normalized_quest))
    {
      enter_fault("invalid_quest_orientation");
    } else if (input.enable && (!input.robot_orientation_valid || !normalized_robot)) {
      enter_fault("invalid_robot_orientation");
    } else if (!fresh) {
      enter_rearm(input.enable, "input_not_fresh");
    } else if (input.enable && !input.command_path_ready) {
      enter_fault("command_path_not_ready");
    } else if (input.enable) {
      quest_anchor_ = input.target_pose;
      quest_orientation_anchor_ = *normalized_quest;
      robot_anchor_ = input.robot_pose;
      robot_anchor_.orientation = *normalized_robot;
      last_command_ = robot_anchor_;
      last_target_ = input.target_pose;
      state_ = AdapterState::ACTIVE;
      release_observed_ = false;
      fault_reason_.clear();
      output.command = last_command_;
      output.anchor_captured = true;
    } else {
      const bool home_ready = input.home_button_pressed && !home_request_latched_ &&
        input.target_fresh && input.quest_pose_fresh && input.inputs_fresh &&
        input.home_inputs_fresh &&
        input.robot_fresh && input.joint_state_fresh && input.joint_state_valid &&
        input.home_action_ready && input.home_plan_valid && input.command_path_ready &&
        input.home_command_path_ready &&
        input.control_period_valid &&
        input.quest_orientation_valid && input.robot_orientation_valid &&
        pose_is_finite(input.target_pose) && pose_is_finite(input.robot_pose);
      if (home_ready && std::isfinite(input.dt_seconds) && input.dt_seconds > 0.0) {
        home_hold_elapsed_seconds_ += input.dt_seconds;
        output.home_hold_progress = std::min(
          1.0, home_hold_elapsed_seconds_ / config_.home_hold_seconds);
        if (home_hold_elapsed_seconds_ >= config_.home_hold_seconds) {
          state_ = AdapterState::HOMING;
          home_request_latched_ = true;
          home_cancel_pending_ = false;
          fault_reason_.clear();
          output.home_goal_requested = true;
        }
      } else {
        home_hold_elapsed_seconds_ = 0.0;
      }
    }
  } else if (state_ == AdapterState::REARM_REQUIRED) {
    if (home_rearm_pending_ && !input.home_button_pressed) {
      home_rearm_pending_ = false;
      release_observed_ = false;
    }
    if (!home_rearm_pending_ && !input.enable) release_observed_ = true;
    if (!home_rearm_pending_ && release_observed_ && !input.enable && fresh) {
      state_ = AdapterState::ARMED;
      fault_reason_.clear();
    }
  } else if (state_ == AdapterState::ACTIVE) {
    const auto normalized_quest = normalize_quaternion(input.quest_orientation);
    const auto normalized_robot = normalize_quaternion(input.robot_pose.orientation);
    if (!input.enable) {
      enter_rearm(false, "deadman_released");
      output.stop_requested = true;
    } else if (
      !input.quest_orientation_valid ||
      input.quest_orientation_status == OrientationSampleStatus::INVALID ||
      !normalized_quest)
    {
      enter_fault("invalid_quest_orientation");
      output.stop_requested = true;
    } else if (!input.robot_orientation_valid || !normalized_robot) {
      enter_fault("invalid_robot_orientation");
      output.stop_requested = true;
    } else if (
      input.quest_orientation_status == OrientationSampleStatus::UNEXPECTED_JUMP ||
      exceeds_strict_threshold(
        input.quest_orientation_jump_rad, config_.unexpected_orientation_jump_rad))
    {
      enter_fault("unexpected_orientation_jump");
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
          const auto delta_q = relative_world_rotation(
            *normalized_quest, quest_orientation_anchor_);
          const double raw_anchor_angle = shortest_angular_distance(QuaternionXyzw{}, delta_q);
          const double mapped_anchor_angle = config_.rotation_scale * raw_anchor_angle;
          if (exceeds_strict_threshold(
              mapped_anchor_angle, config_.max_anchor_angle_rad))
          {
            enter_fault("anchor_angle_violation");
            output.stop_requested = true;
          } else {
            const auto scaled_delta_q =
              scale_shortest_rotation(delta_q, config_.rotation_scale);
            const auto mapped_delta_q =
              map_relative_rotation(scaled_delta_q, config_.mapping);
            desired.orientation = compose_world_relative_rotation(
              mapped_delta_q, robot_anchor_.orientation);

            const auto command_delta = subtract(desired.position, last_command_.position);
            const double distance = norm3(command_delta);
            const double allowed = std::min(
              config_.max_step_m, config_.max_velocity_mps * input.dt_seconds);
            const double allowed_angle = std::min(
              config_.max_angular_step_rad,
              config_.max_angular_velocity_rad_s * input.dt_seconds);
            if (!std::isfinite(allowed) || allowed <= 0.0 ||
              !std::isfinite(allowed_angle) || allowed_angle <= 0.0)
            {
              enter_fault("invalid_motion_limit");
              output.stop_requested = true;
            } else {
              const double ratio = distance > allowed ? allowed / distance : 1.0;
              Pose3 next_command = last_command_;
              for (std::size_t i = 0; i < 3; ++i) {
                next_command.position[i] += command_delta[i] * ratio;
              }
              const double angular_distance = shortest_angular_distance(
                last_command_.orientation, desired.orientation);
              if (angular_distance <= allowed_angle) {
                next_command.orientation = desired.orientation;
              } else {
                next_command.orientation = slerp_shortest(
                  last_command_.orientation, desired.orientation,
                  allowed_angle / angular_distance);
              }
              last_command_ = next_command;
              output.command = last_command_;
            }
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
