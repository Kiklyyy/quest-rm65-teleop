#pragma once

#include <optional>

namespace rm65_teleop_adapter
{

enum class QuestJointPreset {NONE, FIRST_X, SECOND_A, LAST_B, CONFLICT};

const char * quest_joint_preset_name(QuestJointPreset preset);
std::optional<unsigned int> quest_joint_preset_index(QuestJointPreset preset);

class QuestJointPresetSelector
{
public:
  QuestJointPreset update(bool samples_ready, bool x_pressed, bool a_pressed, bool b_pressed);

private:
  bool release_observed_{false};
  bool conflict_latched_{false};
  QuestJointPreset held_{QuestJointPreset::NONE};
};

}  // namespace rm65_teleop_adapter
