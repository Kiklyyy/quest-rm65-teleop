#include "rm65_teleop_adapter/quest_joint_preset.hpp"

#include <gtest/gtest.h>

namespace rm65_teleop_adapter
{
namespace
{

TEST(QuestJointPreset, MapsXAToFirstSecondAndBToLastAfterRelease)
{
  QuestJointPresetSelector selector;
  EXPECT_EQ(selector.update(false, false, false, false), QuestJointPreset::NONE);
  EXPECT_EQ(selector.update(true, false, false, false), QuestJointPreset::NONE);
  EXPECT_EQ(selector.update(true, true, false, false), QuestJointPreset::FIRST_X);
  EXPECT_EQ(selector.update(false, false, false, false), QuestJointPreset::FIRST_X);
  EXPECT_EQ(quest_joint_preset_index(QuestJointPreset::FIRST_X), 0U);
  EXPECT_STREQ(quest_joint_preset_name(QuestJointPreset::FIRST_X), "X_FIRST");
  EXPECT_EQ(selector.update(true, false, false, false), QuestJointPreset::NONE);
  EXPECT_EQ(selector.update(true, false, true, false), QuestJointPreset::SECOND_A);
  EXPECT_EQ(quest_joint_preset_index(QuestJointPreset::SECOND_A), 1U);
  EXPECT_EQ(selector.update(true, false, false, false), QuestJointPreset::NONE);
  EXPECT_EQ(selector.update(true, false, false, true), QuestJointPreset::LAST_B);
  EXPECT_EQ(quest_joint_preset_index(QuestJointPreset::LAST_B), 2U);
}

TEST(QuestJointPreset, HeldAtStartupRequiresObservedRelease)
{
  QuestJointPresetSelector selector;
  EXPECT_EQ(selector.update(true, false, true, false), QuestJointPreset::NONE);
  EXPECT_EQ(selector.update(true, false, true, false), QuestJointPreset::NONE);
  EXPECT_EQ(selector.update(true, false, false, false), QuestJointPreset::NONE);
  EXPECT_EQ(selector.update(true, false, true, false), QuestJointPreset::SECOND_A);
}

TEST(QuestJointPreset, SimultaneousOrSwitchedButtonsRequireFullRelease)
{
  QuestJointPresetSelector selector;
  selector.update(true, false, false, false);
  EXPECT_EQ(selector.update(true, true, true, false), QuestJointPreset::CONFLICT);
  EXPECT_EQ(selector.update(true, true, false, false), QuestJointPreset::CONFLICT);
  EXPECT_EQ(selector.update(true, false, false, false), QuestJointPreset::NONE);
  EXPECT_EQ(selector.update(true, true, false, false), QuestJointPreset::FIRST_X);
  EXPECT_EQ(selector.update(true, false, true, false), QuestJointPreset::CONFLICT);
  EXPECT_EQ(selector.update(true, false, true, false), QuestJointPreset::CONFLICT);
  EXPECT_EQ(selector.update(true, false, false, false), QuestJointPreset::NONE);
  EXPECT_EQ(selector.update(true, false, true, false), QuestJointPreset::SECOND_A);
}

}  // namespace
}  // namespace rm65_teleop_adapter
