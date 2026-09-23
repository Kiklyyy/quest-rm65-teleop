#pragma once

#include <array>
#include <optional>
#include <string>
#include <vector>

namespace rm65_teleop_adapter
{
struct HomeTrajectoryConfig
{
  std::array<double, 6> target_degrees{};
  std::array<std::string, 6> joint_names{};
  double speed_deg_s{15.0};
  double hold_seconds{1.5};
};

struct HomeTrajectoryPlan
{
  std::array<std::string, 6> joint_names{};
  std::array<double, 6> target_radians{};
  double duration_seconds{0.0};
};

bool home_trajectory_config_valid(const HomeTrajectoryConfig & config);
std::optional<std::array<double, 6>> reorder_joint_positions(
  const std::vector<std::string> & message_names,
  const std::vector<double> & message_positions,
  const std::array<std::string, 6> & required_names);
std::optional<HomeTrajectoryPlan> make_home_trajectory_plan(
  const std::array<double, 6> & current_radians,
  const HomeTrajectoryConfig & config);
}  // namespace rm65_teleop_adapter
