#include "rm65_teleop_adapter/home_config.hpp"

#include <algorithm>

namespace rm65_teleop_adapter
{
std::optional<ResolvedHomeConfig> resolve_home_config(const HomeParameterSet & parameters)
{
  if (!parameters.enabled || parameters.dry_run ||
      parameters.action_name.empty() || parameters.action_name.front() != '/' ||
      parameters.joint_degrees.size() != 6 || parameters.joint_names.size() != 6) {
    return std::nullopt;
  }
  const auto field = parse_quest_face_button_field(parameters.button_field);
  if (!field) return std::nullopt;
  ResolvedHomeConfig resolved;
  resolved.button_field = *field;
  resolved.action_name = parameters.action_name;
  std::copy(parameters.joint_degrees.begin(), parameters.joint_degrees.end(),
    resolved.trajectory.target_degrees.begin());
  std::copy(parameters.joint_names.begin(), parameters.joint_names.end(),
    resolved.trajectory.joint_names.begin());
  resolved.trajectory.speed_deg_s = parameters.speed_deg_s;
  resolved.trajectory.hold_seconds = parameters.hold_seconds;
  if (!home_trajectory_config_valid(resolved.trajectory)) return std::nullopt;
  return resolved;
}
}  // namespace rm65_teleop_adapter
