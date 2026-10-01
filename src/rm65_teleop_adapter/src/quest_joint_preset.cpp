#include "rm65_teleop_adapter/quest_joint_preset.hpp"

namespace rm65_teleop_adapter
{

const char * quest_joint_preset_name(const QuestJointPreset preset)
{
  switch (preset) {
    case QuestJointPreset::NONE: return "NONE";
    case QuestJointPreset::FIRST_X: return "X_FIRST";
    case QuestJointPreset::SECOND_A: return "A_SECOND";
    case QuestJointPreset::LAST_B: return "B_LAST";
    case QuestJointPreset::CONFLICT: return "CONFLICT";
  }
  return "UNKNOWN";
}

std::optional<unsigned int> quest_joint_preset_index(const QuestJointPreset preset)
{
  switch (preset) {
    case QuestJointPreset::FIRST_X: return 0U;
    case QuestJointPreset::SECOND_A: return 1U;
    case QuestJointPreset::LAST_B: return 2U;
    case QuestJointPreset::NONE:
    case QuestJointPreset::CONFLICT:
      return std::nullopt;
  }
  return std::nullopt;
}

QuestJointPreset QuestJointPresetSelector::update(
  const bool samples_ready, const bool x_pressed, const bool a_pressed, const bool b_pressed)
{
  if (!samples_ready) {
    return conflict_latched_ ? QuestJointPreset::CONFLICT : held_;
  }

  const unsigned int pressed_count =
    static_cast<unsigned int>(x_pressed) +
    static_cast<unsigned int>(a_pressed) +
    static_cast<unsigned int>(b_pressed);
  if (pressed_count == 0U) {
    release_observed_ = true;
    conflict_latched_ = false;
    held_ = QuestJointPreset::NONE;
    return QuestJointPreset::NONE;
  }
  if (!release_observed_) return QuestJointPreset::NONE;
  if (conflict_latched_) return QuestJointPreset::CONFLICT;
  if (pressed_count != 1U) {
    conflict_latched_ = true;
    held_ = QuestJointPreset::NONE;
    return QuestJointPreset::CONFLICT;
  }

  const QuestJointPreset selected = x_pressed ? QuestJointPreset::FIRST_X :
    a_pressed ? QuestJointPreset::SECOND_A : QuestJointPreset::LAST_B;
  if (held_ != QuestJointPreset::NONE && held_ != selected) {
    conflict_latched_ = true;
    held_ = QuestJointPreset::NONE;
    return QuestJointPreset::CONFLICT;
  }
  held_ = selected;
  return selected;
}

}  // namespace rm65_teleop_adapter
