#include <limits>

#include "gtest/gtest.h"
#include "rm65_teleop_adapter/adapter_logic.hpp"
#include "rm65_teleop_adapter/quest_input_deadman.hpp"

namespace
{
using rm65_teleop_adapter::AdapterLogic;
using rm65_teleop_adapter::AdapterState;
using rm65_teleop_adapter::CycleInput;
using rm65_teleop_adapter::QuestInputDeadman;

struct FakeInputs
{
  bool button_lower{false};
  float press_middle{0.0F};
};

CycleInput fresh_input()
{
  CycleInput input;
  input.target_fresh = true;
  input.quest_pose_fresh = true;
  input.inputs_fresh = true;
  input.robot_fresh = true;
  input.dt_seconds = 0.01;
  input.robot_pose.position = {0.4, 0.0, 0.5};
  return input;
}

TEST(QuestInputDeadman, AppliesPressAndReleaseThresholdsWithHysteresis)
{
  QuestInputDeadman deadman;
  FakeInputs input;
  EXPECT_FALSE(deadman.update(input));

  input.press_middle = 0.60;
  EXPECT_TRUE(deadman.update(input));
  input.press_middle = 1.0;
  EXPECT_TRUE(deadman.update(input));
  for (const double value : {0.59, 0.50, 0.41}) {
    input.press_middle = value;
    EXPECT_TRUE(deadman.update(input));
  }

  input.press_middle = 0.40;
  EXPECT_FALSE(deadman.update(input));
  for (const double value : {0.41, 0.50, 0.59}) {
    input.press_middle = value;
    EXPECT_FALSE(deadman.update(input));
  }
}

TEST(QuestInputDeadman, IgnoresButtonLower)
{
  QuestInputDeadman deadman;
  FakeInputs input;
  input.button_lower = true;
  input.press_middle = 0.0;

  EXPECT_FALSE(deadman.update(input));
}

TEST(QuestInputDeadman, Float32WireValueAtReleaseThresholdReleases)
{
  QuestInputDeadman deadman;
  FakeInputs input;
  input.press_middle = 0.60F;
  ASSERT_TRUE(deadman.update(input));

  input.press_middle = 0.40F;

  EXPECT_FALSE(deadman.update(input));
}

TEST(QuestInputDeadman, NonFiniteValueSafelyReleases)
{
  QuestInputDeadman deadman;
  FakeInputs input;
  input.press_middle = 1.0;
  ASSERT_TRUE(deadman.update(input));

  for (const double value : {
      std::numeric_limits<double>::quiet_NaN(),
      std::numeric_limits<double>::infinity(),
      -std::numeric_limits<double>::infinity()})
  {
    input.press_middle = value;
    EXPECT_FALSE(deadman.update(input));
  }
}

TEST(QuestInputDeadman, ReleaseStopsActiveAndRecoveryRequiresReleaseThenPress)
{
  QuestInputDeadman deadman;
  AdapterLogic logic;
  auto cycle = fresh_input();
  FakeInputs input;

  cycle.enable = deadman.update(input);
  EXPECT_EQ(logic.update(cycle).state, AdapterState::ARMED);

  input.press_middle = 0.60;
  cycle.enable = deadman.update(input);
  EXPECT_EQ(logic.update(cycle).state, AdapterState::ACTIVE);

  input.press_middle = 0.40;
  cycle.enable = deadman.update(input);
  const auto stopped = logic.update(cycle);
  EXPECT_EQ(stopped.state, AdapterState::REARM_REQUIRED);
  EXPECT_TRUE(stopped.stop_requested);

  input.press_middle = 0.60;
  cycle.enable = deadman.update(input);
  EXPECT_EQ(logic.update(cycle).state, AdapterState::REARM_REQUIRED);

  input.press_middle = 0.40;
  cycle.enable = deadman.update(input);
  EXPECT_EQ(logic.update(cycle).state, AdapterState::ARMED);

  input.press_middle = 0.60;
  cycle.enable = deadman.update(input);
  EXPECT_EQ(logic.update(cycle).state, AdapterState::ACTIVE);
}

TEST(QuestInputDeadman, HeldTriggerDoesNotResumeAfterInputRecovery)
{
  QuestInputDeadman deadman;
  AdapterLogic logic;
  auto cycle = fresh_input();
  FakeInputs input;

  cycle.enable = deadman.update(input);
  ASSERT_EQ(logic.update(cycle).state, AdapterState::ARMED);
  input.press_middle = 0.60;
  cycle.enable = deadman.update(input);
  ASSERT_EQ(logic.update(cycle).state, AdapterState::ACTIVE);

  cycle.inputs_fresh = false;
  const auto stopped = logic.update(cycle);
  ASSERT_EQ(stopped.state, AdapterState::REARM_REQUIRED);
  ASSERT_TRUE(stopped.stop_requested);

  cycle.inputs_fresh = true;
  EXPECT_EQ(logic.update(cycle).state, AdapterState::REARM_REQUIRED);

  input.press_middle = 0.40;
  cycle.enable = deadman.update(input);
  EXPECT_EQ(logic.update(cycle).state, AdapterState::ARMED);
  input.press_middle = 0.60;
  cycle.enable = deadman.update(input);
  EXPECT_EQ(logic.update(cycle).state, AdapterState::ACTIVE);
}
}  // namespace
