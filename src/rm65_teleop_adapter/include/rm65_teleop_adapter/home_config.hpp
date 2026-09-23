#pragma once

#include <optional>
#include <string>
#include <vector>

#include "rm65_teleop_adapter/home_trajectory.hpp"
#include "rm65_teleop_adapter/quest_face_button.hpp"

namespace rm65_teleop_adapter
{
struct HomeParameterSet
{
  bool dry_run{true};
  bool enabled{false};
  std::string button_field;
  std::string action_name;
  std::vector<double> joint_degrees;
  std::vector<std::string> joint_names;
  double speed_deg_s{0.0};
  double hold_seconds{0.0};
};

struct ResolvedHomeConfig
{
  HomeTrajectoryConfig trajectory;
  QuestFaceButtonField button_field{QuestFaceButtonField::UPPER};
  std::string action_name;
};

std::optional<ResolvedHomeConfig> resolve_home_config(const HomeParameterSet & parameters);
}  // namespace rm65_teleop_adapter
