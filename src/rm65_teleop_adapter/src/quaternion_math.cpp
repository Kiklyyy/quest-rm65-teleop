#include "rm65_teleop_adapter/quaternion_math.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace rm65_teleop_adapter
{

bool quaternion_is_finite(const QuaternionXyzw & quaternion)
{
  return std::isfinite(quaternion.x) && std::isfinite(quaternion.y) &&
         std::isfinite(quaternion.z) && std::isfinite(quaternion.w);
}

std::optional<QuaternionXyzw> normalize_quaternion(const QuaternionXyzw & quaternion)
{
  if (!quaternion_is_finite(quaternion)) return std::nullopt;
  const double scale = std::max(
    {std::abs(quaternion.x), std::abs(quaternion.y),
      std::abs(quaternion.z), std::abs(quaternion.w)});
  if (scale == 0.0) return std::nullopt;

  const double scaled_norm = std::hypot(
    std::hypot(quaternion.x / scale, quaternion.y / scale),
    std::hypot(quaternion.z / scale, quaternion.w / scale));
  const double norm = scale * scaled_norm;
  if (!std::isfinite(norm) || norm < kMinimumQuaternionNorm) return std::nullopt;

  return QuaternionXyzw{
    quaternion.x / norm, quaternion.y / norm,
    quaternion.z / norm, quaternion.w / norm};
}

namespace
{

QuaternionXyzw normalized_or_throw(const QuaternionXyzw & quaternion)
{
  const auto normalized = normalize_quaternion(quaternion);
  if (!normalized) {
    throw std::invalid_argument("invalid quaternion");
  }
  return *normalized;
}

Matrix3RowMajor transpose(const Matrix3RowMajor & matrix)
{
  return Matrix3RowMajor{
    matrix[0], matrix[3], matrix[6],
    matrix[1], matrix[4], matrix[7],
    matrix[2], matrix[5], matrix[8]};
}

Matrix3RowMajor multiply(const Matrix3RowMajor & lhs, const Matrix3RowMajor & rhs)
{
  Matrix3RowMajor result{};
  for (std::size_t row = 0; row < 3; ++row) {
    for (std::size_t column = 0; column < 3; ++column) {
      for (std::size_t index = 0; index < 3; ++index) {
        result[row * 3 + column] += lhs[row * 3 + index] * rhs[index * 3 + column];
      }
    }
  }
  return result;
}

double determinant(const Matrix3RowMajor & matrix)
{
  return
    matrix[0] * (matrix[4] * matrix[8] - matrix[5] * matrix[7]) -
    matrix[1] * (matrix[3] * matrix[8] - matrix[5] * matrix[6]) +
    matrix[2] * (matrix[3] * matrix[7] - matrix[4] * matrix[6]);
}

}  // namespace

QuaternionXyzw conjugate_quaternion(const QuaternionXyzw & quaternion)
{
  return QuaternionXyzw{-quaternion.x, -quaternion.y, -quaternion.z, quaternion.w};
}

QuaternionXyzw inverse_unit_quaternion(const QuaternionXyzw & quaternion)
{
  return conjugate_quaternion(normalized_or_throw(quaternion));
}

QuaternionXyzw hamilton_product(
  const QuaternionXyzw & lhs, const QuaternionXyzw & rhs)
{
  const auto left = normalized_or_throw(lhs);
  const auto right = normalized_or_throw(rhs);
  return normalized_or_throw(QuaternionXyzw{
    left.w * right.x + left.x * right.w + left.y * right.z - left.z * right.y,
    left.w * right.y - left.x * right.z + left.y * right.w + left.z * right.x,
    left.w * right.z + left.x * right.y - left.y * right.x + left.z * right.w,
    left.w * right.w - left.x * right.x - left.y * right.y - left.z * right.z});
}

double quaternion_dot(const QuaternionXyzw & lhs, const QuaternionXyzw & rhs)
{
  const auto left = normalized_or_throw(lhs);
  const auto right = normalized_or_throw(rhs);
  return left.x * right.x + left.y * right.y + left.z * right.z + left.w * right.w;
}

QuaternionXyzw align_quaternion_hemisphere(
  const QuaternionXyzw & reference, const QuaternionXyzw & candidate)
{
  const auto normalized_candidate = normalized_or_throw(candidate);
  if (quaternion_dot(reference, normalized_candidate) < 0.0) {
    return QuaternionXyzw{
      -normalized_candidate.x, -normalized_candidate.y,
      -normalized_candidate.z, -normalized_candidate.w};
  }
  return normalized_candidate;
}

double shortest_angular_distance(
  const QuaternionXyzw & from, const QuaternionXyzw & to)
{
  const auto relative = hamilton_product(to, inverse_unit_quaternion(from));
  const double vector_norm = std::hypot(relative.x, relative.y, relative.z);
  return 2.0 * std::atan2(
    vector_norm, std::clamp(std::abs(relative.w), 0.0, 1.0));
}

QuaternionXyzw slerp_shortest(
  const QuaternionXyzw & from, const QuaternionXyzw & to, const double fraction)
{
  if (!std::isfinite(fraction) || fraction < 0.0 || fraction > 1.0) {
    throw std::invalid_argument("SLERP fraction must be finite and in [0, 1]");
  }

  const auto start = normalized_or_throw(from);
  const auto finish = align_quaternion_hemisphere(start, to);
  const double dot = std::clamp(quaternion_dot(start, finish), 0.0, 1.0);
  if (dot > 0.9995) {
    return normalized_or_throw(QuaternionXyzw{
      start.x + fraction * (finish.x - start.x),
      start.y + fraction * (finish.y - start.y),
      start.z + fraction * (finish.z - start.z),
      start.w + fraction * (finish.w - start.w)});
  }

  const double theta = std::acos(dot);
  const double inverse_sine = 1.0 / std::sin(theta);
  const double start_weight = std::sin((1.0 - fraction) * theta) * inverse_sine;
  const double finish_weight = std::sin(fraction * theta) * inverse_sine;
  return normalized_or_throw(QuaternionXyzw{
    start_weight * start.x + finish_weight * finish.x,
    start_weight * start.y + finish_weight * finish.y,
    start_weight * start.z + finish_weight * finish.z,
    start_weight * start.w + finish_weight * finish.w});
}

Matrix3RowMajor quaternion_to_rotation_matrix(const QuaternionXyzw & quaternion)
{
  const auto q = normalized_or_throw(quaternion);
  return Matrix3RowMajor{
    1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    2.0 * (q.x * q.y - q.z * q.w),
    2.0 * (q.x * q.z + q.y * q.w),
    2.0 * (q.x * q.y + q.z * q.w),
    1.0 - 2.0 * (q.x * q.x + q.z * q.z),
    2.0 * (q.y * q.z - q.x * q.w),
    2.0 * (q.x * q.z - q.y * q.w),
    2.0 * (q.y * q.z + q.x * q.w),
    1.0 - 2.0 * (q.x * q.x + q.y * q.y)};
}

bool is_proper_rotation_matrix(const Matrix3RowMajor & matrix, const double tolerance)
{
  if (!std::isfinite(tolerance) || tolerance < 0.0) return false;
  for (const double value : matrix) {
    if (!std::isfinite(value)) return false;
  }

  const auto identity_candidate = multiply(matrix, transpose(matrix));
  for (std::size_t row = 0; row < 3; ++row) {
    for (std::size_t column = 0; column < 3; ++column) {
      const double expected = row == column ? 1.0 : 0.0;
      if (std::abs(identity_candidate[row * 3 + column] - expected) > tolerance) {
        return false;
      }
    }
  }
  return std::abs(determinant(matrix) - 1.0) <= tolerance;
}

std::optional<QuaternionXyzw> rotation_matrix_to_quaternion(
  const Matrix3RowMajor & matrix)
{
  if (!is_proper_rotation_matrix(matrix)) return std::nullopt;

  QuaternionXyzw result;
  const double trace = matrix[0] + matrix[4] + matrix[8];
  if (trace > 0.0) {
    const double scale = 2.0 * std::sqrt(trace + 1.0);
    result = QuaternionXyzw{
      (matrix[7] - matrix[5]) / scale,
      (matrix[2] - matrix[6]) / scale,
      (matrix[3] - matrix[1]) / scale,
      0.25 * scale};
  } else if (matrix[0] > matrix[4] && matrix[0] > matrix[8]) {
    const double scale = 2.0 * std::sqrt(1.0 + matrix[0] - matrix[4] - matrix[8]);
    result = QuaternionXyzw{
      0.25 * scale,
      (matrix[1] + matrix[3]) / scale,
      (matrix[2] + matrix[6]) / scale,
      (matrix[7] - matrix[5]) / scale};
  } else if (matrix[4] > matrix[8]) {
    const double scale = 2.0 * std::sqrt(1.0 + matrix[4] - matrix[0] - matrix[8]);
    result = QuaternionXyzw{
      (matrix[1] + matrix[3]) / scale,
      0.25 * scale,
      (matrix[5] + matrix[7]) / scale,
      (matrix[2] - matrix[6]) / scale};
  } else {
    const double scale = 2.0 * std::sqrt(1.0 + matrix[8] - matrix[0] - matrix[4]);
    result = QuaternionXyzw{
      (matrix[2] + matrix[6]) / scale,
      (matrix[5] + matrix[7]) / scale,
      0.25 * scale,
      (matrix[3] - matrix[1]) / scale};
  }
  return normalize_quaternion(result);
}

QuaternionXyzw relative_world_rotation(
  const QuaternionXyzw & current, const QuaternionXyzw & anchor)
{
  return hamilton_product(current, inverse_unit_quaternion(anchor));
}

QuaternionXyzw scale_shortest_rotation(
  const QuaternionXyzw & relative_rotation, const double scale)
{
  if (!std::isfinite(scale) || scale < 0.0) {
    throw std::invalid_argument("rotation scale must be finite and non-negative");
  }
  const QuaternionXyzw identity{};
  const auto relative = align_quaternion_hemisphere(identity, relative_rotation);
  const double half_angle = std::acos(std::clamp(relative.w, 0.0, 1.0));
  const double sine_half_angle = std::hypot(relative.x, relative.y, relative.z);
  if (sine_half_angle < 1e-15 || scale == 0.0) return identity;

  const double scaled_half_angle = scale * half_angle;
  const double scaled_sine = std::sin(scaled_half_angle);
  return normalized_or_throw(QuaternionXyzw{
    relative.x * scaled_sine / sine_half_angle,
    relative.y * scaled_sine / sine_half_angle,
    relative.z * scaled_sine / sine_half_angle,
    std::cos(scaled_half_angle)});
}

QuaternionXyzw map_relative_rotation(
  const QuaternionXyzw & quest_relative_rotation,
  const Matrix3RowMajor & quest_to_robot_mapping)
{
  if (!is_proper_rotation_matrix(quest_to_robot_mapping)) {
    throw std::invalid_argument("Quest-to-robot mapping must be a proper rotation");
  }
  const auto quest_rotation = quaternion_to_rotation_matrix(quest_relative_rotation);
  const auto mapped_rotation = multiply(
    multiply(quest_to_robot_mapping, quest_rotation),
    transpose(quest_to_robot_mapping));
  const auto mapped = rotation_matrix_to_quaternion(mapped_rotation);
  if (!mapped) throw std::invalid_argument("mapped rotation is invalid");
  return *mapped;
}

QuaternionXyzw compose_world_relative_rotation(
  const QuaternionXyzw & mapped_relative_rotation,
  const QuaternionXyzw & robot_anchor)
{
  return hamilton_product(mapped_relative_rotation, robot_anchor);
}

}  // namespace rm65_teleop_adapter
