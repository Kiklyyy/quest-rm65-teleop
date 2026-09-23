#include "rm65_teleop_adapter/home_trajectory.hpp"

#include <algorithm>
#include <cmath>
#include <unordered_map>
#include <unordered_set>

namespace rm65_teleop_adapter
{
namespace
{
constexpr double kRadiansPerDegree = 3.14159265358979323846 / 180.0;
}

bool home_trajectory_config_valid(const HomeTrajectoryConfig & config)
{
  if (!std::isfinite(config.speed_deg_s) || config.speed_deg_s <= 0.0 ||
      !std::isfinite(config.hold_seconds) || config.hold_seconds <= 0.0) return false;
  std::unordered_set<std::string> names;
  for (std::size_t i = 0; i < 6; ++i) {
    if (!std::isfinite(config.target_degrees[i]) || config.joint_names[i].empty() ||
        !names.insert(config.joint_names[i]).second) return false;
  }
  return true;
}

std::optional<std::array<double, 6>> reorder_joint_positions(
  const std::vector<std::string> & message_names,
  const std::vector<double> & message_positions,
  const std::array<std::string, 6> & required_names)
{
  if (message_names.size() != message_positions.size()) return std::nullopt;
  std::unordered_map<std::string, double> positions;
  for (std::size_t i = 0; i < message_names.size(); ++i) {
    if (message_names[i].empty() || !std::isfinite(message_positions[i]) ||
        !positions.emplace(message_names[i], message_positions[i]).second) return std::nullopt;
  }
  std::array<double, 6> result{};
  for (std::size_t i = 0; i < result.size(); ++i) {
    const auto found = positions.find(required_names[i]);
    if (found == positions.end()) return std::nullopt;
    result[i] = found->second;
  }
  return result;
}

std::optional<HomeTrajectoryPlan> make_home_trajectory_plan(
  const std::array<double, 6> & current_radians,
  const HomeTrajectoryConfig & config)
{
  if (!home_trajectory_config_valid(config)) return std::nullopt;
  HomeTrajectoryPlan plan;
  plan.joint_names = config.joint_names;
  double farthest_delta = 0.0;
  for (std::size_t i = 0; i < 6; ++i) {
    if (!std::isfinite(current_radians[i])) return std::nullopt;
    plan.target_radians[i] = config.target_degrees[i] * kRadiansPerDegree;
    farthest_delta = std::max(farthest_delta,
      std::abs(plan.target_radians[i] - current_radians[i]));
  }
  plan.duration_seconds = std::max(
    farthest_delta / (config.speed_deg_s * kRadiansPerDegree), 0.1);
  if (!std::isfinite(plan.duration_seconds)) return std::nullopt;
  return plan;
}
}  // namespace rm65_teleop_adapter
