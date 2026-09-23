#include <cmath>
#include <limits>

#include "gtest/gtest.h"
#include "rm65_teleop_adapter/adapter_logic.hpp"

namespace
{
using rm65_teleop_adapter::AdapterConfig;
using rm65_teleop_adapter::AdapterLogic;
using rm65_teleop_adapter::AdapterState;
using rm65_teleop_adapter::CycleInput;
using rm65_teleop_adapter::Matrix3RowMajor;
using rm65_teleop_adapter::OrientationSampleStatus;
using rm65_teleop_adapter::QuaternionXyzw;
using rm65_teleop_adapter::hamilton_product;
using rm65_teleop_adapter::shortest_angular_distance;

constexpr double kPi = 3.14159265358979323846;

QuaternionXyzw axis_angle(
  const double x, const double y, const double z, const double angle)
{
  const double sine = std::sin(angle / 2.0);
  return {x * sine, y * sine, z * sine, std::cos(angle / 2.0)};
}

QuaternionXyzw q_x90()
{
  return axis_angle(1.0, 0.0, 0.0, kPi / 2.0);
}

QuaternionXyzw q_y90()
{
  return axis_angle(0.0, 1.0, 0.0, kPi / 2.0);
}

QuaternionXyzw q_minus_z90()
{
  return axis_angle(0.0, 0.0, -1.0, kPi / 2.0);
}

Matrix3RowMajor verified_mapping()
{
  return {
    0.0, 0.0, 1.0,
    -1.0, 0.0, 0.0,
    0.0, -1.0, 0.0};
}

CycleInput fresh_input()
{
  CycleInput input;
  input.target_fresh = true;
  input.quest_pose_fresh = true;
  input.inputs_fresh = true;
  input.robot_fresh = true;
  input.dt_seconds = 0.01;
  input.quest_orientation = QuaternionXyzw{0.0, 0.0, 0.0, 1.0};
  input.quest_orientation_valid = true;
  input.robot_orientation_valid = true;
  input.quest_orientation_status = OrientationSampleStatus::VALID;
  input.quest_orientation_jump_rad = 0.0;
  input.robot_pose.position = {0.4, 0.0, 0.5};
  input.robot_pose.orientation = QuaternionXyzw{0.0, 0.0, 0.0, 1.0};
  return input;
}

void activate(AdapterLogic & logic, CycleInput & input)
{
  input.enable = false;
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.enable = true;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::ACTIVE);
  EXPECT_TRUE(output.anchor_captured);
  ASSERT_TRUE(output.command.has_value());
}

TEST(AdapterLogic, StartupPressedRequiresReleaseThenPress)
{
  AdapterLogic logic;
  auto input = fresh_input();
  input.enable = true;
  EXPECT_EQ(logic.update(input).state, AdapterState::REARM_REQUIRED);
  EXPECT_EQ(logic.update(input).state, AdapterState::REARM_REQUIRED);
  input.enable = false;
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.enable = true;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::ACTIVE);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_DOUBLE_EQ(output.command->position[0], input.robot_pose.position[0]);
}

TEST(AdapterLogic, RelativeTranslationUsesAnchorsAndUnchangedIdentityOrientation)
{
  AdapterConfig config;
  config.max_velocity_mps = 10.0;
  config.max_step_m = 1.0;
  config.max_anchor_distance_m = 1.0;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position = {0.02, -0.03, 0.04};
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_NEAR(output.command->position[0], 0.42, 1e-12);
  EXPECT_NEAR(output.command->position[1], -0.03, 1e-12);
  EXPECT_NEAR(output.command->position[2], 0.54, 1e-12);
  EXPECT_NEAR(
    shortest_angular_distance(output.command->orientation, QuaternionXyzw{}),
    0.0, 1e-12);
}

TEST(AdapterLogic, DeadmanReleaseRequiresReanchorAndDoesNotJump)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.enable = false;
  const auto stopped = logic.update(input);
  EXPECT_EQ(stopped.state, AdapterState::REARM_REQUIRED);
  EXPECT_TRUE(stopped.stop_requested);
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.target_pose.position = {0.3, 0.2, 0.1};
  input.robot_pose.position = {0.45, 0.02, 0.55};
  input.enable = true;
  const auto restarted = logic.update(input);
  ASSERT_TRUE(restarted.command.has_value());
  EXPECT_TRUE(restarted.anchor_captured);
  EXPECT_EQ(restarted.command->position, input.robot_pose.position);
}

TEST(AdapterLogic, InputTimeoutDoesNotAutoResume)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.inputs_fresh = false;
  const auto stopped = logic.update(input);
  EXPECT_EQ(stopped.state, AdapterState::REARM_REQUIRED);
  EXPECT_TRUE(stopped.stop_requested);
  input.inputs_fresh = true;
  EXPECT_EQ(logic.update(input).state, AdapterState::REARM_REQUIRED);
  input.enable = false;
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
}

TEST(AdapterLogic, VelocityAndStepLimitsAreApplied)
{
  AdapterConfig config;
  config.max_velocity_mps = 1.0;
  config.max_step_m = 0.001;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position[0] = 0.01;
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_NEAR(output.command->position[0], 0.401, 1e-12);
}

TEST(AdapterLogic, WorkspaceViolationLatchesFault)
{
  AdapterConfig config;
  config.max_velocity_mps = 10.0;
  config.max_step_m = 1.0;
  config.workspace_max = {0.405, 1.0, 1.5};
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position[0] = 0.01;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_TRUE(output.stop_requested);
  EXPECT_EQ(output.reason, "workspace_violation");
  EXPECT_FALSE(logic.clear_fault(true));
  EXPECT_TRUE(logic.clear_fault(false));
}

TEST(AdapterLogic, NonFinitePoseLatchesFault)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position[0] = std::numeric_limits<double>::quiet_NaN();
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_TRUE(output.stop_requested);
  EXPECT_EQ(output.reason, "non_finite_or_invalid_pose");
}

TEST(AdapterLogic, UnexpectedTargetJumpLatchesFault)
{
  AdapterConfig config;
  config.unexpected_target_jump_m = 0.02;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position[0] = 0.03;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_TRUE(output.stop_requested);
  EXPECT_EQ(output.reason, "unexpected_target_jump");
}

TEST(AdapterLogic, PhysicalAxisMappingMatchesVerifiedFrames)
{
  AdapterConfig config;
  config.mapping = verified_mapping();
  config.max_velocity_mps = 10.0;
  config.max_step_m = 1.0;
  config.max_anchor_distance_m = 1.0;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position = {0.01, 0.02, 0.03};
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_NEAR(output.command->position[0], 0.43, 1e-12);
  EXPECT_NEAR(output.command->position[1], -0.01, 1e-12);
  EXPECT_NEAR(output.command->position[2], 0.48, 1e-12);
}

TEST(AdapterLogic, AnchorDistanceViolationLatchesFault)
{
  AdapterConfig config;
  config.max_anchor_distance_m = 0.03;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position[0] = 0.031;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_TRUE(output.stop_requested);
  EXPECT_EQ(output.reason, "anchor_distance_violation");
}

TEST(AdapterLogic, ControlPeriodViolationStopsActiveMotion)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.control_period_valid = false;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_TRUE(output.stop_requested);
  EXPECT_EQ(output.reason, "control_period_exceeded");
}

TEST(AdapterLogic, CommandPathMustBeReadyBeforeActivation)
{
  AdapterLogic logic;
  auto input = fresh_input();
  input.enable = false;
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.command_path_ready = false;
  input.enable = true;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_FALSE(output.command.has_value());
  EXPECT_EQ(output.reason, "command_path_not_ready");
}

TEST(AdapterLogic, FirstPressCapturesNormalizedRobotOrientationWithoutJump)
{
  AdapterLogic logic;
  auto input = fresh_input();
  input.robot_pose.orientation = QuaternionXyzw{0.0, 0.0, 0.0, 2.0};
  activate(logic, input);
  input.enable = true;
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_NEAR(
    shortest_angular_distance(output.command->orientation, QuaternionXyzw{}),
    0.0, 1e-12);
}

TEST(AdapterLogic, WorldFrameDeltaUsesMappedLeftComposition)
{
  AdapterConfig config;
  config.mapping = verified_mapping();
  config.rotation_scale = 1.0;
  config.max_angular_velocity_rad_s = 100.0;
  config.max_angular_step_rad = kPi;
  config.max_anchor_angle_rad = kPi;
  AdapterLogic logic(config);
  auto input = fresh_input();
  input.dt_seconds = 0.1;
  input.robot_pose.orientation = q_x90();
  activate(logic, input);
  input.quest_orientation = q_y90();
  const auto output = logic.update(input);
  const auto expected = hamilton_product(q_minus_z90(), q_x90());
  ASSERT_TRUE(output.command.has_value());
  EXPECT_NEAR(
    shortest_angular_distance(output.command->orientation, expected), 0.0, 1e-12);
}

TEST(AdapterLogic, TranslationAndOrientationShareOneCommand)
{
  AdapterConfig config;
  config.mapping = verified_mapping();
  config.max_velocity_mps = 10.0;
  config.max_step_m = 1.0;
  config.max_anchor_distance_m = 1.0;
  config.max_angular_velocity_rad_s = 100.0;
  config.max_angular_step_rad = kPi;
  config.max_anchor_angle_rad = kPi;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position = {0.01, 0.0, 0.0};
  input.quest_orientation = axis_angle(1.0, 0.0, 0.0, 0.2);
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_NEAR(output.command->position[0], 0.4, 1e-12);
  EXPECT_NEAR(output.command->position[1], -0.01, 1e-12);
  EXPECT_NEAR(output.command->position[2], 0.5, 1e-12);
  const auto expected = axis_angle(0.0, -1.0, 0.0, 0.2);
  EXPECT_NEAR(
    shortest_angular_distance(output.command->orientation, expected), 0.0, 1e-12);
}

TEST(AdapterLogic, DeadmanRepressCapturesNewOrientationAnchorsWithoutJump)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.enable = false;
  EXPECT_EQ(logic.update(input).state, AdapterState::REARM_REQUIRED);
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.quest_orientation = axis_angle(0.0, 1.0, 0.0, 0.7);
  input.robot_pose.orientation = QuaternionXyzw{
    2.0 * std::sin(0.2), 0.0, 0.0, 2.0 * std::cos(0.2)};
  input.enable = true;
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  const auto expected = axis_angle(1.0, 0.0, 0.0, 0.4);
  EXPECT_TRUE(output.anchor_captured);
  EXPECT_NEAR(
    shortest_angular_distance(output.command->orientation, expected), 0.0, 1e-12);
}

TEST(AdapterLogic, RotationWhileReleasedIsIgnored)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.enable = false;
  EXPECT_FALSE(logic.update(input).command.has_value());
  input.quest_orientation = axis_angle(0.0, 0.0, 1.0, 2.0);
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.robot_pose.orientation = axis_angle(1.0, 0.0, 0.0, 0.3);
  input.enable = true;
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_NEAR(
    shortest_angular_distance(
      output.command->orientation, input.robot_pose.orientation),
    0.0, 1e-12);
}

TEST(AdapterLogic, AngularVelocityLimitIsApplied)
{
  AdapterConfig config;
  config.max_angular_velocity_rad_s = 0.5;
  config.max_angular_step_rad = 1.0;
  AdapterLogic logic(config);
  auto input = fresh_input();
  input.dt_seconds = 0.1;
  activate(logic, input);
  input.quest_orientation = axis_angle(0.0, 0.0, 1.0, 0.2);
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_NEAR(
    shortest_angular_distance(QuaternionXyzw{}, output.command->orientation),
    0.05, 1e-10);
}

TEST(AdapterLogic, AngularStepLimitIsApplied)
{
  AdapterConfig config;
  config.max_angular_velocity_rad_s = 10.0;
  config.max_angular_step_rad = 0.01;
  AdapterLogic logic(config);
  auto input = fresh_input();
  input.dt_seconds = 0.1;
  activate(logic, input);
  input.quest_orientation = axis_angle(0.0, 0.0, 1.0, 0.2);
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_NEAR(
    shortest_angular_distance(QuaternionXyzw{}, output.command->orientation),
    0.01, 1e-10);
}

TEST(AdapterLogic, SmallerAngularLimitWins)
{
  const auto commanded_angle = [](const double velocity, const double step) {
      AdapterConfig config;
      config.max_angular_velocity_rad_s = velocity;
      config.max_angular_step_rad = step;
      AdapterLogic logic(config);
      auto input = fresh_input();
      input.dt_seconds = 0.1;
      activate(logic, input);
      input.quest_orientation = axis_angle(0.0, 0.0, 1.0, 0.2);
      const auto output = logic.update(input);
      EXPECT_TRUE(output.command.has_value());
      return output.command ?
             shortest_angular_distance(QuaternionXyzw{}, output.command->orientation) :
             -1.0;
    };

  EXPECT_NEAR(commanded_angle(0.2, 0.01), 0.01, 1e-10);
  EXPECT_NEAR(commanded_angle(0.05, 0.01), 0.005, 1e-10);
}

TEST(AdapterLogic, InvalidQuestOrientationFaultsStopsAndEmitsNoCommand)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.quest_orientation_valid = false;
  input.quest_orientation_status = OrientationSampleStatus::INVALID;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_EQ(output.reason, "invalid_quest_orientation");
  EXPECT_TRUE(output.stop_requested);
  EXPECT_FALSE(output.command.has_value());
}

TEST(AdapterLogic, UnexpectedOrientationJumpFaultsStopsAndEmitsNoCommand)
{
  AdapterConfig config;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.quest_orientation_status = OrientationSampleStatus::UNEXPECTED_JUMP;
  input.quest_orientation_jump_rad = config.unexpected_orientation_jump_rad + 1.0e-6;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_EQ(output.reason, "unexpected_orientation_jump");
  EXPECT_TRUE(output.stop_requested);
  EXPECT_FALSE(output.command.has_value());
}

TEST(AdapterLogic, JumpExactlyFortyFiveDegreesIsAllowed)
{
  AdapterConfig config;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.quest_orientation_status = OrientationSampleStatus::VALID;
  input.quest_orientation_jump_rad = config.unexpected_orientation_jump_rad;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::ACTIVE);
  EXPECT_TRUE(output.command.has_value());
}

TEST(AdapterLogic, QuaternionSignFlipDoesNotFaultOrMove)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.quest_orientation = QuaternionXyzw{0.0, 0.0, 0.0, -1.0};
  const auto output = logic.update(input);
  ASSERT_TRUE(output.command.has_value());
  EXPECT_EQ(output.state, AdapterState::ACTIVE);
  EXPECT_NEAR(
    shortest_angular_distance(QuaternionXyzw{}, output.command->orientation),
    0.0, 1e-12);
}

TEST(AdapterLogic, AnchorAngleExactlyNinetyDegreesIsAllowed)
{
  AdapterConfig config;
  config.max_angular_velocity_rad_s = 100.0;
  config.max_angular_step_rad = kPi;
  AdapterLogic logic(config);
  auto input = fresh_input();
  input.dt_seconds = 0.1;
  activate(logic, input);
  input.quest_orientation = axis_angle(0.0, 0.0, 1.0, config.max_anchor_angle_rad);
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::ACTIVE);
  EXPECT_TRUE(output.command.has_value());
}

TEST(AdapterLogic, AnchorAngleAboveNinetyDegreesFaultsAndStops)
{
  AdapterConfig config;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.quest_orientation =
    axis_angle(0.0, 0.0, 1.0, config.max_anchor_angle_rad + 1.0e-6);
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_EQ(output.reason, "anchor_angle_violation");
  EXPECT_TRUE(output.stop_requested);
  EXPECT_FALSE(output.command.has_value());
}

TEST(AdapterLogic, OrientationFaultDoesNotPublishTranslationCandidate)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position[0] = 0.01;
  input.quest_orientation_valid = false;
  input.quest_orientation_status = OrientationSampleStatus::INVALID;
  const auto output = logic.update(input);
  EXPECT_EQ(output.reason, "invalid_quest_orientation");
  EXPECT_FALSE(output.command.has_value());
}

TEST(AdapterLogic, TranslationFaultDoesNotPublishOrientationCandidate)
{
  AdapterConfig config;
  config.max_anchor_distance_m = 0.001;
  AdapterLogic logic(config);
  auto input = fresh_input();
  activate(logic, input);
  input.target_pose.position[0] = 0.01;
  input.quest_orientation = axis_angle(0.0, 0.0, 1.0, 0.2);
  const auto output = logic.update(input);
  EXPECT_EQ(output.reason, "anchor_distance_violation");
  EXPECT_FALSE(output.command.has_value());
}

TEST(AdapterLogic, InvalidRobotOrientationCannotBecomeAnchor)
{
  AdapterLogic logic;
  auto input = fresh_input();
  input.enable = false;
  ASSERT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.robot_orientation_valid = false;
  input.enable = true;
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::FAULT);
  EXPECT_EQ(output.reason, "invalid_robot_orientation");
  EXPECT_FALSE(output.command.has_value());
}

TEST(AdapterLogic, TimeoutAndReleaseRearmSemanticsRemainUnchanged)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.enable = false;
  input.inputs_fresh = false;
  input.quest_orientation_valid = false;
  input.quest_orientation_status = OrientationSampleStatus::INVALID;
  const auto released = logic.update(input);
  EXPECT_EQ(released.state, AdapterState::REARM_REQUIRED);
  EXPECT_EQ(released.reason, "deadman_released");
  EXPECT_TRUE(released.stop_requested);

  input.enable = true;
  input.inputs_fresh = true;
  input.quest_orientation_valid = true;
  input.quest_orientation_status = OrientationSampleStatus::VALID;
  EXPECT_EQ(logic.update(input).state, AdapterState::REARM_REQUIRED);
  input.enable = false;
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.enable = true;
  ASSERT_EQ(logic.update(input).state, AdapterState::ACTIVE);
  input.inputs_fresh = false;
  const auto timed_out = logic.update(input);
  EXPECT_EQ(timed_out.state, AdapterState::REARM_REQUIRED);
  EXPECT_EQ(timed_out.reason, "input_not_fresh");
  EXPECT_TRUE(timed_out.stop_requested);
}

TEST(AdapterLogic, ClearOrientationFaultStillRequiresReleaseThenPress)
{
  AdapterLogic logic;
  auto input = fresh_input();
  activate(logic, input);
  input.quest_orientation_valid = false;
  input.quest_orientation_status = OrientationSampleStatus::INVALID;
  ASSERT_EQ(logic.update(input).state, AdapterState::FAULT);
  EXPECT_FALSE(logic.clear_fault(true));
  EXPECT_TRUE(logic.clear_fault(false));

  input.quest_orientation_valid = true;
  input.quest_orientation_status = OrientationSampleStatus::VALID;
  input.enable = true;
  EXPECT_EQ(logic.update(input).state, AdapterState::REARM_REQUIRED);
  input.enable = false;
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.enable = true;
  const auto restarted = logic.update(input);
  EXPECT_EQ(restarted.state, AdapterState::ACTIVE);
  EXPECT_TRUE(restarted.anchor_captured);
}



CycleInput home_ready_input()
{
  auto input = fresh_input();
  input.home_button_pressed = true;
  input.joint_state_fresh = true;
  input.joint_state_valid = true;
  input.home_action_ready = true;
  input.home_plan_valid = true;
  input.dt_seconds = 0.5;
  return input;
}

void start_home(AdapterLogic & logic, CycleInput & input)
{
  input.enable = false;
  input.home_button_pressed = false;
  ASSERT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.home_button_pressed = true;
  EXPECT_FALSE(logic.update(input).home_goal_requested);
  EXPECT_FALSE(logic.update(input).home_goal_requested);
  const auto started = logic.update(input);
  ASSERT_EQ(started.state, AdapterState::HOMING);
  ASSERT_TRUE(started.home_goal_requested);
}

TEST(AdapterLogic, HomeHoldShorterThanThresholdAndExactlyOnceAtThreshold)
{
  AdapterLogic logic;
  auto input = home_ready_input();
  input.home_button_pressed = false;
  ASSERT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.home_button_pressed = true;
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  const auto output = logic.update(input);
  EXPECT_EQ(output.state, AdapterState::HOMING);
  EXPECT_TRUE(output.home_goal_requested);
  EXPECT_FALSE(logic.update(input).home_goal_requested);
}

TEST(AdapterLogic, HomeRequiresReleasedGripFreshJointsAndReadyAction)
{
  AdapterLogic logic;
  auto input = home_ready_input();
  input.home_button_pressed = false;
  ASSERT_EQ(logic.update(input).state, AdapterState::ARMED);
  input.home_button_pressed = true;
  input.joint_state_fresh = false;
  for (int i=0; i<4; ++i) EXPECT_FALSE(logic.update(input).home_goal_requested);
  input.joint_state_fresh = true;
  input.home_action_ready = false;
  for (int i=0; i<4; ++i) EXPECT_FALSE(logic.update(input).home_goal_requested);
  input.home_action_ready = true;
  input.enable = true;
  EXPECT_EQ(logic.update(input).state, AdapterState::ACTIVE);
  EXPECT_FALSE(logic.update(input).home_goal_requested);
}

TEST(AdapterLogic, HomingNeverEmitsCartesianAndGripCannotTakeOver)
{
  AdapterLogic logic;
  auto input = home_ready_input();
  start_home(logic, input);
  input.enable = true;
  input.target_pose.position[0] = 0.03;
  const auto out = logic.update(input);
  EXPECT_EQ(out.state, AdapterState::HOMING);
  EXPECT_FALSE(out.command);
  EXPECT_FALSE(out.home_goal_requested);
}

TEST(AdapterLogic, ButtonReleaseRequestsCancelAndWaitsForTerminal)
{
  AdapterLogic logic;
  auto input = home_ready_input();
  start_home(logic, input);
  input.home_button_pressed = false;
  auto out = logic.update(input);
  EXPECT_EQ(out.state, AdapterState::HOMING);
  EXPECT_TRUE(out.home_cancel_requested);
  EXPECT_TRUE(out.stop_requested);
  EXPECT_FALSE(out.command);
  out = logic.update(input);
  EXPECT_EQ(out.state, AdapterState::HOMING);
  EXPECT_FALSE(out.home_cancel_requested);
  input.home_action_event = rm65_teleop_adapter::HomeActionEvent::CANCELED;
  out = logic.update(input);
  EXPECT_EQ(out.state, AdapterState::REARM_REQUIRED);
  EXPECT_FALSE(out.command);
}

TEST(AdapterLogic, HomeWatchdogLossRequestsCancelAndWaits)
{
  for (int source=0; source<5; ++source) {
    AdapterLogic logic;
    auto input = home_ready_input();
    start_home(logic, input);
    if (source==0) input.quest_pose_fresh = false;
    if (source==1) input.inputs_fresh = false;
    if (source==2) input.robot_fresh = false;
    if (source==3) input.joint_state_fresh = false;
    if (source==4) input.joint_state_valid = false;
    const auto out = logic.update(input);
    EXPECT_EQ(out.state, AdapterState::HOMING);
    EXPECT_TRUE(out.home_cancel_requested);
    EXPECT_TRUE(out.stop_requested);
    EXPECT_FALSE(out.command);
    EXPECT_EQ(logic.update(input).state, AdapterState::HOMING);
  }
}

TEST(AdapterLogic, HomeTerminalOutcomesAndHeldButtonCannotRetrigger)
{
  for (auto event : {rm65_teleop_adapter::HomeActionEvent::SUCCEEDED,
                     rm65_teleop_adapter::HomeActionEvent::CANCELED,
                     rm65_teleop_adapter::HomeActionEvent::REJECTED,
                     rm65_teleop_adapter::HomeActionEvent::ABORTED}) {
    AdapterLogic logic;
    auto input = home_ready_input();
    start_home(logic, input);
    input.home_action_event = event;
    auto out = logic.update(input);
    EXPECT_EQ(out.state, (event == rm65_teleop_adapter::HomeActionEvent::SUCCEEDED ||
                           event == rm65_teleop_adapter::HomeActionEvent::CANCELED) ?
                        AdapterState::REARM_REQUIRED : AdapterState::FAULT);
    input.home_action_event = rm65_teleop_adapter::HomeActionEvent::NONE;
    for (int i=0; i<5; ++i) EXPECT_FALSE(logic.update(input).home_goal_requested);
  }
}

TEST(AdapterLogic, NewHomeRequiresReleaseThenFreshHold)
{
  AdapterLogic logic;
  auto input = home_ready_input();
  start_home(logic, input);
  input.home_action_event = rm65_teleop_adapter::HomeActionEvent::SUCCEEDED;
  EXPECT_EQ(logic.update(input).state, AdapterState::REARM_REQUIRED);
  input.home_action_event = rm65_teleop_adapter::HomeActionEvent::NONE;
  EXPECT_EQ(logic.update(input).state, AdapterState::ARMED);
  for (int i=0; i<5; ++i) EXPECT_FALSE(logic.update(input).home_goal_requested);
  input.home_button_pressed = false;
  logic.update(input);
  input.home_button_pressed = true;
  EXPECT_FALSE(logic.update(input).home_goal_requested);
  EXPECT_FALSE(logic.update(input).home_goal_requested);
  EXPECT_TRUE(logic.update(input).home_goal_requested);
}
}  // namespace
