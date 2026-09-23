#include "gtest/gtest.h"
#include "rm65_teleop_adapter/quest_face_button.hpp"

namespace
{
using rm65_teleop_adapter::QuestFaceButtonField;
using rm65_teleop_adapter::parse_quest_face_button_field;
using rm65_teleop_adapter::quest_face_button_pressed;

struct FakeInputs {bool button_upper{false}; bool button_lower{false};};

TEST(QuestFaceButton, ParsesOnlySupportedFields)
{
  EXPECT_EQ(parse_quest_face_button_field("upper"), QuestFaceButtonField::UPPER);
  EXPECT_EQ(parse_quest_face_button_field("lower"), QuestFaceButtonField::LOWER);
  EXPECT_FALSE(parse_quest_face_button_field("unverified"));
  EXPECT_FALSE(parse_quest_face_button_field(""));
}

TEST(QuestFaceButton, SelectsRequestedWireField)
{
  FakeInputs input;
  input.button_upper = true;
  EXPECT_TRUE(quest_face_button_pressed(input, QuestFaceButtonField::UPPER));
  EXPECT_FALSE(quest_face_button_pressed(input, QuestFaceButtonField::LOWER));
  input.button_upper = false;
  input.button_lower = true;
  EXPECT_FALSE(quest_face_button_pressed(input, QuestFaceButtonField::UPPER));
  EXPECT_TRUE(quest_face_button_pressed(input, QuestFaceButtonField::LOWER));
}
}  // namespace
