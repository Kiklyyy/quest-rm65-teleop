#pragma once

#include <optional>
#include <string_view>

namespace rm65_teleop_adapter
{
enum class QuestFaceButtonField {UPPER, LOWER};

inline std::optional<QuestFaceButtonField> parse_quest_face_button_field(std::string_view value)
{
  if (value == "upper") return QuestFaceButtonField::UPPER;
  if (value == "lower") return QuestFaceButtonField::LOWER;
  return std::nullopt;
}

template<typename InputsT>
bool quest_face_button_pressed(const InputsT & input, QuestFaceButtonField field)
{
  return field == QuestFaceButtonField::UPPER ?
         static_cast<bool>(input.button_upper) : static_cast<bool>(input.button_lower);
}
}  // namespace rm65_teleop_adapter
