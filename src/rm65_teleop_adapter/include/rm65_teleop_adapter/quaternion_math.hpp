#pragma once

#include <array>
#include <optional>

namespace rm65_teleop_adapter
{

struct QuaternionXyzw
{
  double x{0.0};
  double y{0.0};
  double z{0.0};
  double w{1.0};
};

using Matrix3RowMajor = std::array<double, 9>;
constexpr double kMinimumQuaternionNorm = 1.0e-6;

bool quaternion_is_finite(const QuaternionXyzw & quaternion);
std::optional<QuaternionXyzw> normalize_quaternion(const QuaternionXyzw & quaternion);
QuaternionXyzw conjugate_quaternion(const QuaternionXyzw & quaternion);
QuaternionXyzw inverse_unit_quaternion(const QuaternionXyzw & quaternion);
QuaternionXyzw hamilton_product(
  const QuaternionXyzw & lhs, const QuaternionXyzw & rhs);
double quaternion_dot(const QuaternionXyzw & lhs, const QuaternionXyzw & rhs);
QuaternionXyzw align_quaternion_hemisphere(
  const QuaternionXyzw & reference, const QuaternionXyzw & candidate);
double shortest_angular_distance(
  const QuaternionXyzw & from, const QuaternionXyzw & to);
QuaternionXyzw slerp_shortest(
  const QuaternionXyzw & from, const QuaternionXyzw & to, double fraction);
Matrix3RowMajor quaternion_to_rotation_matrix(const QuaternionXyzw & quaternion);
std::optional<QuaternionXyzw> rotation_matrix_to_quaternion(
  const Matrix3RowMajor & matrix);
QuaternionXyzw relative_world_rotation(
  const QuaternionXyzw & current, const QuaternionXyzw & anchor);
QuaternionXyzw scale_shortest_rotation(
  const QuaternionXyzw & delta, double scale);
QuaternionXyzw map_relative_rotation(
  const QuaternionXyzw & delta, const Matrix3RowMajor & mapping);
QuaternionXyzw compose_world_relative_rotation(
  const QuaternionXyzw & mapped_delta, const QuaternionXyzw & robot_anchor);
bool is_proper_rotation_matrix(
  const Matrix3RowMajor & matrix, double tolerance = 1.0e-9);

}  // namespace rm65_teleop_adapter
