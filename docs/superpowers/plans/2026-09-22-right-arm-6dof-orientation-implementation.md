# Right-arm 6DoF Orientation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变已验证 Quest XYZ translation path、安全状态机和唯一 RM65 command path 的前提下，把 raw Quest 右手 quaternion 映射为受锚点、jump guard、角速度和角步长约束的右 RM65 6DoF Pose command。

**Architecture:** `quest_right_target_bridge` 继续只生成 translation target；adapter 的 raw Quest Pose callback 逐样本调用纯 C++ orientation tracker。tracker 将已归一化 quaternion 与未丢失的 INVALID/UNEXPECTED_JUMP 事件交给 `AdapterLogic`，后者在同一 ACTIVE cycle 原子地计算 translation 与 orientation，并继续通过现有 preview/hardware publisher 发送唯一 Pose command。

**Tech Stack:** Ubuntu 22.04、ROS 2 Humble、C++17、`rclcpp`、`geometry_msgs`、`rm_ros_interfaces`、ament CMake/GTest、Python 3.10/pytest、YAML。

**Spec:** `docs/superpowers/specs/2026-09-22-right-arm-6dof-orientation-design.md`

## Global Constraints

- 所有实现、构建和验证都在 `ssh lh` 后的 `/home/lh/quest2ros2_ws/.worktrees/quest-orientation`、branch `feat/quest-orientation` 中执行；不新建 branch/worktree，不在 Windows 创建仓库副本。
- `/home/lh/robot` 只允许 `source /home/lh/robot/install/setup.bash`，不得修改其中任何文件。
- 每个命令环境先执行 `conda deactivate 2>/dev/null || true`、`source /opt/ros/humble/setup.bash`、`source /home/lh/robot/install/setup.bash`，并确认 `python3=/usr/bin/python3`、`colcon=/usr/bin/colcon`。
- 严格按 RED → GREEN → REFACTOR 执行；每个 task 的失败证据、通过证据、commit SHA 和 push 状态写入开发记录。
- quaternion 使用显式 `(x,y,z,w)` 类型、Hamilton product、active column-vector rotation；核心计算禁止 Euler angle 累积。
- 固定 `Delta R_Q = R_Q * R_Q0^T`、`Delta R_RM = M * Delta R_Q_scaled * M^T`、`R_des = Delta R_RM * R_R0`。
- `rotation_scale=1.0`、`max_angular_velocity_rad_s=1.5707963267948966`、`max_angular_step_rad=0.01`、`max_anchor_angle_rad=1.5707963267948966`、`unexpected_orientation_jump_rad=0.7853981633974483`。
- translation mapping、translation scale、三个 motion profiles、workspace、watchdogs、deadman `0.60/0.40` hysteresis、release/rearm、command-path uniqueness、control-period fault 和 `stop_repeat_count` 保持现状。
- `src/Quest2ROS2/q2r2_bringup/quest_right_target_bridge.py` 不改；`/quest_right_target_pose.orientation` 继续为 identity。
- `safe.yaml`、`normal.yaml`、`fast.yaml` 不加入 orientation 参数；motion profile allowlist 始终只有四个 translation 参数。
- dry-run 不创建 `/right/rm_driver/movep_canfd_cmd` publisher。真实 Quest probe 完成前，不运行真实 RM65 rotation；实现过程中不启动 RM driver。
- 每个 task 完成后执行 `git diff --check`、commit、push `origin feat/quest-orientation`；不 force-push，不 merge。

## Review Focus

1. 同一 control timer 周期前到达多个 raw Quest 样本时，第一条 invalid/jump 事件不能被后续 valid 样本覆盖；Task 2 的 `FirstFaultEventRemainsLatchedUntilConsumed` 和 Task 5 dry-run probe 固定该行为。
2. Quest runtime 把同一 orientation 从 `q` 切成 `-q` 时，jump 必须为 0 且 preview 不翻转；Task 1、Task 2、Task 4、Task 5 都有明确测试。
3. 45° jump 与 90° anchor angle 的等号边界必须允许，严格超出才 fault；Task 2 与 Task 4 分别覆盖阈值计算和状态机结果。
4. 非 identity、non-commuting anchors 最容易掩盖左右乘错误；Task 1 与 Task 3 使用 `Y90 ⊗ X90` 组合锁定 world/base-frame 左乘顺序。
5. invalid robot quaternion、raw Quest timeout、release 和 fault clear 可能走错恢复路径；Task 4 验证 AdapterLogic，Task 5 验证 Node freshness 与无 command 输出。

---

## File and module map

### New pure C++ modules

- `src/rm65_teleop_adapter/include/rm65_teleop_adapter/quaternion_math.hpp`：显式 quaternion/matrix 类型和无 ROS 依赖的旋转数学 API。
- `src/rm65_teleop_adapter/src/quaternion_math.cpp`：归一化、Hamilton product、matrix conversion、relative/world mapping、scale、SLERP 与 proper-rotation validation。
- `src/rm65_teleop_adapter/include/rm65_teleop_adapter/quest_orientation_tracker.hpp`：逐样本结果、snapshot 和 session API。
- `src/rm65_teleop_adapter/src/quest_orientation_tracker.cpp`：latest/previous quaternion、hemisphere、event latch 与 ACTIVE baseline。

### New tests and test support

- `src/rm65_teleop_adapter/test/test_quaternion_math.cpp`
- `src/rm65_teleop_adapter/test/test_quest_orientation_tracker.cpp`
- `src/rm65_teleop_adapter/test/test_adapter_config.cpp`
- `src/rm65_teleop_adapter/test/dry_run_6dof_probe.py`：只在隔离 ROS domain 中使用的发布/观察 harness，不安装为 production executable。

### Existing implementation files to modify

- `src/rm65_teleop_adapter/include/rm65_teleop_adapter/adapter_logic.hpp`
- `src/rm65_teleop_adapter/src/adapter_logic.cpp`
- `src/rm65_teleop_adapter/src/adapter_node.cpp`
- `src/rm65_teleop_adapter/CMakeLists.txt`
- `src/rm65_teleop_adapter/config/dry_run.yaml`
- `src/rm65_teleop_adapter/config/hardware.yaml`

### Existing tests to modify

- `src/rm65_teleop_adapter/test/test_adapter_logic.cpp`
- `src/rm65_teleop_adapter/test/test_input_deadman.cpp`
- `src/rm65_teleop_adapter/test/test_motion_profiles.py`

### Documentation changed only after matching evidence exists

- `docs/INTERFACE.md`
- `STATUS.md`
- `CHANGELOG.md`
- `src/rm65_teleop_adapter/README.md`
- `docs/progress/right-arm-6dof-orientation.md`（新增）

### Files explicitly unchanged

- `src/Quest2ROS2/q2r2_bringup/quest_right_target_bridge.py`
- `src/Quest2ROS2/q2r2_bringup/quest_right_target_logic.py`
- `src/rm65_teleop_adapter/config/motion_profiles/safe.yaml`
- `src/rm65_teleop_adapter/config/motion_profiles/normal.yaml`
- `src/rm65_teleop_adapter/config/motion_profiles/fast.yaml`

---

### Task 1: Quaternion math helper

**Checkpoint:** `feat: add quaternion math primitives`

**Files:**
- Create: `src/rm65_teleop_adapter/include/rm65_teleop_adapter/quaternion_math.hpp`
- Create: `src/rm65_teleop_adapter/src/quaternion_math.cpp`
- Create: `src/rm65_teleop_adapter/test/test_quaternion_math.cpp`
- Modify: `src/rm65_teleop_adapter/CMakeLists.txt`

**Interfaces:**
- Consumes: C++17 standard library only；`Matrix3RowMajor` 按 `m[row * 3 + column]` 存储。
- Produces:

```cpp
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

bool quaternion_is_finite(const QuaternionXyzw & q);
std::optional<QuaternionXyzw> normalize_quaternion(const QuaternionXyzw & q);
QuaternionXyzw conjugate_quaternion(const QuaternionXyzw & q);
QuaternionXyzw inverse_unit_quaternion(const QuaternionXyzw & q);
QuaternionXyzw hamilton_product(const QuaternionXyzw & lhs, const QuaternionXyzw & rhs);
double quaternion_dot(const QuaternionXyzw & lhs, const QuaternionXyzw & rhs);
QuaternionXyzw align_quaternion_hemisphere(
  const QuaternionXyzw & reference, const QuaternionXyzw & candidate);
double shortest_angular_distance(
  const QuaternionXyzw & from, const QuaternionXyzw & to);
QuaternionXyzw slerp_shortest(
  const QuaternionXyzw & from, const QuaternionXyzw & to, double fraction);
Matrix3RowMajor quaternion_to_rotation_matrix(const QuaternionXyzw & q);
std::optional<QuaternionXyzw> rotation_matrix_to_quaternion(const Matrix3RowMajor & matrix);
QuaternionXyzw relative_world_rotation(
  const QuaternionXyzw & current, const QuaternionXyzw & anchor);
QuaternionXyzw scale_shortest_rotation(const QuaternionXyzw & delta, double scale);
QuaternionXyzw map_relative_rotation(
  const QuaternionXyzw & delta, const Matrix3RowMajor & mapping);
QuaternionXyzw compose_world_relative_rotation(
  const QuaternionXyzw & mapped_delta, const QuaternionXyzw & robot_anchor);
bool is_proper_rotation_matrix(
  const Matrix3RowMajor & matrix, double tolerance = 1.0e-9);
}  // namespace rm65_teleop_adapter
```

- 所有接受 orientation 的函数要求输入已归一化，只有 `normalize_quaternion` 接受 raw quaternion；返回 quaternion 的函数再次归一化。
- `slerp_shortest` 要求 `fraction` finite 且位于 `[0,1]`，否则抛出 `std::invalid_argument`。

- [ ] **Step 1.1: Add the explicit public types and write failing validation/normalization tests**

在 header 中先声明上述 API，在 `test_quaternion_math.cpp` 写出这些用例：

```cpp
TEST(QuaternionMath, RejectsNonFiniteAndNearZeroNorm)
{
  EXPECT_FALSE(normalize_quaternion({NAN, 0.0, 0.0, 1.0}).has_value());
  EXPECT_FALSE(normalize_quaternion({0.0, 0.0, 0.0, 0.0}).has_value());
  EXPECT_FALSE(normalize_quaternion({1.0e-8, 0.0, 0.0, 0.0}).has_value());
}

TEST(QuaternionMath, NormalizesXyzwWithoutChangingOrientation)
{
  const auto value = normalize_quaternion({0.0, 0.0, 0.0, 2.0});
  ASSERT_TRUE(value.has_value());
  EXPECT_DOUBLE_EQ(value->x, 0.0);
  EXPECT_DOUBLE_EQ(value->w, 1.0);
}
```

- [ ] **Step 1.2: Run RED for the new target**

Before the first RED build, add target_sources(adapter_logic PRIVATE src/quaternion_math.cpp) beside the existing adapter_logic declaration. Inside if(BUILD_TESTING), add exactly:

~~~cmake
ament_add_gtest(test_quaternion_math test/test_quaternion_math.cpp)
target_link_libraries(test_quaternion_math adapter_logic)
target_include_directories(test_quaternion_math PRIVATE include)
~~~

```bash
/usr/bin/colcon --log-base log build \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter \
  --cmake-args -DBUILD_TESTING=ON
```

Expected RED: compile/link failure naming the declared quaternion functions because `quaternion_math.cpp` has not supplied them.

- [ ] **Step 1.3: Implement finite and stable normalization minimally**

Use a scaled norm so large finite components cannot overflow during the norm calculation:

```cpp
const double scale = std::max({std::abs(q.x), std::abs(q.y), std::abs(q.z), std::abs(q.w)});
if (!quaternion_is_finite(q) || scale == 0.0) return std::nullopt;
const double scaled_norm = std::hypot(std::hypot(q.x / scale, q.y / scale),
  std::hypot(q.z / scale, q.w / scale));
const double norm = scale * scaled_norm;
if (!std::isfinite(norm) || norm < kMinimumQuaternionNorm) return std::nullopt;
return QuaternionXyzw{q.x / norm, q.y / norm, q.z / norm, q.w / norm};
```

- [ ] **Step 1.4: Run the focused tests GREEN**

```bash
./build/rm65_teleop_adapter/test_quaternion_math \
  --gtest_filter='QuaternionMath.RejectsNonFiniteAndNearZeroNorm:QuaternionMath.NormalizesXyzwWithoutChangingOrientation'
```

Expected GREEN: 2 tests pass.

- [ ] **Step 1.5: Write RED tests for product order, matrices and non-commuting anchors**

Use `s = sqrt(0.5)`, `q_x90={s,0,0,s}`, `q_y90={0,s,0,s}` and the verified mapping:

```cpp
constexpr Matrix3RowMajor kMapping{
  0.0, 0.0, 1.0,
 -1.0, 0.0, 0.0,
  0.0,-1.0, 0.0};

TEST(QuaternionMath, RelativeWorldRotationUsesCurrentTimesInverseAnchor)
{
  const QuaternionXyzw anchor = q_x90();
  const QuaternionXyzw expected_delta = q_y90();
  const auto current = hamilton_product(expected_delta, anchor);
  const auto actual = relative_world_rotation(current, anchor);
  EXPECT_NEAR(shortest_angular_distance(actual, expected_delta), 0.0, 1.0e-12);
}

TEST(QuaternionMath, RobotAnchorCompositionIsMappedDeltaTimesAnchor)
{
  const auto expected = hamilton_product(q_z90(), q_x90());
  const auto actual = compose_world_relative_rotation(q_z90(), q_x90());
  EXPECT_NEAR(shortest_angular_distance(actual, expected), 0.0, 1.0e-12);
}
```

同时加入并明确命名：

- `HamiltonProductUsesXyzwStorage`
- RelativeWorldRotationAtAnchorIsIdentity
- ShortestAngularDistanceReturnsKnownNinetyDegrees
- RotationScaleOnePreservesAngle
- `QuaternionAndNegativeQuaternionHaveZeroDistance`
- `ShortestSlerpDoesNotTakeTheLongArc`
- `QuaternionMatrixRoundTripPreservesRotation`
- `ScaleShortestRotationMapsNinetyDegreesToFortyFiveDegrees`
- `QuestBasisRotationsMapToRmMinusYMinusZPlusX`
- `VerifiedMappingIsProperRotation`
- `RejectsReflectionScaledAndNonFiniteMappings`

- [ ] **Step 1.6: Run the expanded test binary and confirm RED**

```bash
./build/rm65_teleop_adapter/test_quaternion_math --gtest_color=yes
```

Expected RED: the new product/matrix/mapping/SLERP cases fail or remain unresolved while normalization cases stay green.

- [ ] **Step 1.7: Implement the remaining math with the fixed order**

Core formulas must appear literally in `quaternion_math.cpp`:

```cpp
QuaternionXyzw relative_world_rotation(const QuaternionXyzw & current,
  const QuaternionXyzw & anchor)
{
  return normalized_or_throw(hamilton_product(current, inverse_unit_quaternion(anchor)));
}

QuaternionXyzw map_relative_rotation(const QuaternionXyzw & delta,
  const Matrix3RowMajor & mapping)
{
  const auto mapped = multiply_matrix(
    multiply_matrix(mapping, quaternion_to_rotation_matrix(delta)),
    transpose_matrix(mapping));
  return normalized_matrix_quaternion_or_throw(mapped);
}

QuaternionXyzw compose_world_relative_rotation(const QuaternionXyzw & mapped_delta,
  const QuaternionXyzw & robot_anchor)
{
  return normalized_or_throw(hamilton_product(mapped_delta, robot_anchor));
}
```

`scale_shortest_rotation` 先把 `delta` 对齐到 identity hemisphere，再用 shortest axis-angle/log-exp 缩放；接近零角时直接返回 identity。`is_proper_rotation_matrix` 检查全部 finite、`M*M^T` 每项与 identity 的误差不超过 tolerance、`abs(det(M)-1)<=tolerance`。

- [ ] **Step 1.8: Run GREEN and regression**

```bash
./build/rm65_teleop_adapter/test_quaternion_math --gtest_color=yes
/usr/bin/colcon --log-base log test \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter \
  --event-handlers console_direct+
/usr/bin/colcon test-result --test-result-base build --all --verbose
```

Expected GREEN: all quaternion cases pass; existing adapter/deadman/status/profile suites remain at zero failures.

- [ ] **Step 1.9: Refactor, whitespace check, commit and push**

Remove duplicated matrix loops, keep helper functions private to `.cpp`, then:

```bash
git diff --check
git add src/rm65_teleop_adapter/CMakeLists.txt \
  src/rm65_teleop_adapter/include/rm65_teleop_adapter/quaternion_math.hpp \
  src/rm65_teleop_adapter/src/quaternion_math.cpp \
  src/rm65_teleop_adapter/test/test_quaternion_math.cpp
git commit -m "feat: add quaternion math primitives"
git push origin feat/quest-orientation
```

---

### Task 2: Quest orientation sample continuity tracker

**Checkpoint:** `feat: track Quest orientation continuity`

**Files:**
- Create: `src/rm65_teleop_adapter/include/rm65_teleop_adapter/quest_orientation_tracker.hpp`
- Create: `src/rm65_teleop_adapter/src/quest_orientation_tracker.cpp`
- Create: `src/rm65_teleop_adapter/test/test_quest_orientation_tracker.cpp`
- Modify: `src/rm65_teleop_adapter/CMakeLists.txt`

**Interfaces:**
- Consumes: Task 1 `QuaternionXyzw`、`normalize_quaternion`、`align_quaternion_hemisphere`、`shortest_angular_distance`。
- Produces:

```cpp
enum class OrientationSampleStatus {VALID, INVALID, UNEXPECTED_JUMP};

struct OrientationSnapshot
{
  QuaternionXyzw latest_orientation{};
  bool has_valid_orientation{false};
  bool latest_sample_valid{false};
  OrientationSampleStatus status{OrientationSampleStatus::VALID};
  double jump_angle_rad{0.0};
};

class QuestOrientationTracker
{
public:
  explicit QuestOrientationTracker(double unexpected_jump_rad);
  void ingest(const QuaternionXyzw & raw_orientation);
  OrientationSnapshot consume_snapshot();
  void begin_active_session(const QuaternionXyzw & normalized_anchor);
  void end_active_session();
  bool active_session() const;
};
```

- `ingest` 在每个 raw Quest callback 调用；INVALID 不覆盖 `latest_orientation`，但把 `latest_sample_valid=false` 并 latch 第一条 pending fault event。
- 非 ACTIVE 时 valid 样本可以更新 latest 和 hemisphere，但绝不生成 UNEXPECTED_JUMP。
- `begin_active_session` 把 continuity previous 重置为 normalized Quest anchor 并清除非 ACTIVE 阶段的 pending event。
- ACTIVE 中严格 `jump > threshold` 才产生 UNEXPECTED_JUMP；等于阈值为 VALID。unexpected 样本不推进 accepted previous。
- `consume_snapshot` 返回并清除 pending status/jump，latest orientation 与 last-sample validity 保留；多个 callback 先于 timer 时保留第一条 fault event。

- [ ] **Step 2.1: Write all tracker tests before implementation**

测试名与断言固定为：

```cpp
TEST(QuestOrientationTracker, NormalizesAndStoresFirstValidSample);
TEST(QuestOrientationTracker, InvalidSampleDoesNotReplaceLatestValidOrientation);
TEST(QuestOrientationTracker, QuaternionSignFlipHasZeroJump);
TEST(QuestOrientationTracker, InactiveFastRotationNeverEmitsJump);
TEST(QuestOrientationTracker, ActiveJumpExactlyAtThresholdIsValid);
TEST(QuestOrientationTracker, ActiveJumpAboveThresholdIsUnexpected);
TEST(QuestOrientationTracker, FirstFaultEventRemainsLatchedUntilConsumed);
TEST(QuestOrientationTracker, ConsumeClearsEventButPreservesLatestOrientation);
TEST(QuestOrientationTracker, BeginActiveSessionResetsBaselineToAnchor);
TEST(QuestOrientationTracker, EndActiveSessionDisablesJumpFaulting);
```

关键边界测试使用：

```cpp
const double threshold = 0.7853981633974483;
tracker.begin_active_session(identity());
tracker.ingest(axis_angle_z(threshold));
EXPECT_EQ(tracker.consume_snapshot().status, OrientationSampleStatus::VALID);

tracker.begin_active_session(identity());
tracker.ingest(axis_angle_z(threshold + 1.0e-6));
const auto result = tracker.consume_snapshot();
EXPECT_EQ(result.status, OrientationSampleStatus::UNEXPECTED_JUMP);
EXPECT_GT(result.jump_angle_rad, threshold);
```

多 callback latch 测试先 ingest NaN quaternion，再 ingest identity，确认 snapshot 仍为 INVALID 且 latest 已恢复为 valid；下一次 consume 才返回 VALID。

- [ ] **Step 2.2: Register the target and run RED**

Add target_sources(adapter_logic PRIVATE src/quest_orientation_tracker.cpp) beside the Task 1 source list. Inside if(BUILD_TESTING), add exactly:

~~~cmake
ament_add_gtest(test_quest_orientation_tracker test/test_quest_orientation_tracker.cpp)
target_link_libraries(test_quest_orientation_tracker adapter_logic)
target_include_directories(test_quest_orientation_tracker PRIVATE include)
~~~

```bash
/usr/bin/colcon --log-base log build \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter \
  --cmake-args -DBUILD_TESTING=ON
```

Expected RED: `QuestOrientationTracker` symbols unresolved or assertions fail because event/session storage尚未实现。

- [ ] **Step 2.3: Implement the smallest state model**

Private state must be equivalent to：

```cpp
double unexpected_jump_rad_;
std::optional<QuaternionXyzw> latest_valid_;
std::optional<QuaternionXyzw> previous_active_;
bool latest_sample_valid_{false};
bool active_session_{false};
OrientationSampleStatus pending_status_{OrientationSampleStatus::VALID};
double pending_jump_angle_rad_{0.0};
```

`ingest` 的顺序固定为 validate/normalize → hemisphere alignment → ACTIVE jump calculation → cache update。仅当 `pending_status_==VALID` 时写入新的 INVALID 或 UNEXPECTED_JUMP，保证第一条 fault event 不丢失。

- [ ] **Step 2.4: Run tracker GREEN**

```bash
./build/rm65_teleop_adapter/test_quest_orientation_tracker --gtest_color=yes
```

Expected GREEN: 10 个 tracker tests 全部通过。

- [ ] **Step 2.5: Run math and full adapter regression**

```bash
./build/rm65_teleop_adapter/test_quaternion_math --gtest_color=yes
/usr/bin/colcon --log-base log test \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter \
  --event-handlers console_direct+
/usr/bin/colcon test-result --test-result-base build --all --verbose
```

Expected GREEN: Task 1 与现有 adapter suites 全部零失败。

- [ ] **Step 2.6: Refactor, whitespace check, commit and push**

```bash
git diff --check
git add src/rm65_teleop_adapter/CMakeLists.txt \
  src/rm65_teleop_adapter/include/rm65_teleop_adapter/quest_orientation_tracker.hpp \
  src/rm65_teleop_adapter/src/quest_orientation_tracker.cpp \
  src/rm65_teleop_adapter/test/test_quest_orientation_tracker.cpp
git commit -m "feat: track Quest orientation continuity"
git push origin feat/quest-orientation
```

---

### Task 3: Extend AdapterLogic with anchored 6DoF mapping and limiting

**Checkpoint:** `feat: add anchored 6DoF adapter logic`

**Files:**
- Modify: `src/rm65_teleop_adapter/include/rm65_teleop_adapter/adapter_logic.hpp`
- Modify: `src/rm65_teleop_adapter/src/adapter_logic.cpp`
- Modify: `src/rm65_teleop_adapter/test/test_adapter_logic.cpp`
- Modify: `src/rm65_teleop_adapter/test/test_input_deadman.cpp`

**Interfaces:**
- Consumes: Task 1 quaternion API；Task 2 `OrientationSampleStatus`。
- Changes `Pose3.orientation` from anonymous `std::array<double,4>` to explicit `QuaternionXyzw`。
- Extends `AdapterConfig` exactly as follows：

```cpp
struct AdapterConfig
{
  Matrix3RowMajor mapping{1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
  double translation_scale{1.0};
  double max_velocity_mps{0.01};
  double max_step_m{0.0001};
  double max_anchor_distance_m{0.03};
  double unexpected_target_jump_m{0.10};
  double rotation_scale{1.0};
  double max_angular_velocity_rad_s{1.5707963267948966};
  double max_angular_step_rad{0.01};
  double max_anchor_angle_rad{1.5707963267948966};
  double unexpected_orientation_jump_rad{0.7853981633974483};
  std::array<double, 3> workspace_min{-1.0, -1.0, 0.0};
  std::array<double, 3> workspace_max{1.0, 1.0, 1.5};
};
```

- Extends `CycleInput` exactly as follows while preserving every existing field：

```cpp
QuaternionXyzw quest_orientation{};
bool quest_orientation_valid{false};
bool robot_orientation_valid{false};
OrientationSampleStatus quest_orientation_status{OrientationSampleStatus::VALID};
double quest_orientation_jump_rad{0.0};
```

- quest_pose_fresh and robot_fresh remain the existing transport watchdog results; the two orientation-valid flags are separate semantic gates. all_fresh() requires both valid flags without changing any timeout.
- Adds private `QuaternionXyzw quest_orientation_anchor_`。`robot_anchor_.orientation` remains the robot orientation anchor。
- `CycleOutput` and `AdapterLogic::update/clear_fault/state/fault_reason` signatures remain unchanged。

- [ ] **Step 3.1: Update test fixtures for explicit valid orientation input**

Both `fresh_input()` helpers in `test_adapter_logic.cpp` and `test_input_deadman.cpp` must set：

```cpp
input.quest_orientation = QuaternionXyzw{0.0, 0.0, 0.0, 1.0};
input.quest_orientation_valid = true;
input.robot_orientation_valid = true;
input.quest_orientation_status = OrientationSampleStatus::VALID;
input.quest_orientation_jump_rad = 0.0;
input.robot_pose.orientation = QuaternionXyzw{0.0, 0.0, 0.0, 1.0};
```

This preserves all existing translation/deadman test preconditions after `all_fresh()` includes orientation validity。

- [ ] **Step 3.2: Write failing anchoring, composition and combined-command tests**

Add these exact GTest cases to `test_adapter_logic.cpp`：

```cpp
TEST(AdapterLogic, FirstPressCapturesNormalizedRobotOrientationWithoutJump);
TEST(AdapterLogic, WorldFrameDeltaUsesMappedLeftComposition);
TEST(AdapterLogic, TranslationAndOrientationShareOneCommand);
TEST(AdapterLogic, DeadmanRepressCapturesNewOrientationAnchorsWithoutJump);
TEST(AdapterLogic, RotationWhileReleasedIsIgnored);
```

The non-commuting composition case uses：

```cpp
config.mapping = verified_mapping();
config.rotation_scale = 1.0;
config.max_angular_velocity_rad_s = 100.0;
config.max_angular_step_rad = 3.141592653589793;
config.max_anchor_angle_rad = 3.141592653589793;
input.robot_pose.orientation = q_x90();
activate(logic, input);
input.quest_orientation = q_y90();  // Quest +Y maps to RM -Z.
const auto output = logic.update(input);
const auto expected = hamilton_product(q_minus_z90(), q_x90());
ASSERT_TRUE(output.command.has_value());
EXPECT_NEAR(shortest_angular_distance(output.command->orientation, expected), 0.0, 1.0e-12);
```

The same-cycle case changes both `target_pose.position` and `quest_orientation`, then asserts one `output.command` contains both the mapped position and mapped quaternion。Repress case releases, supplies a new Quest orientation and new robot feedback orientation while released, returns to ARMED, presses again, and asserts the first command equals the new normalized robot Pose。

- [ ] **Step 3.3: Run RED**

```bash
/usr/bin/colcon --log-base log build \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter \
  --cmake-args -DBUILD_TESTING=ON
./build/rm65_teleop_adapter/test_adapter_logic \
  --gtest_filter='AdapterLogic.FirstPressCapturesNormalizedRobotOrientationWithoutJump:AdapterLogic.WorldFrameDeltaUsesMappedLeftComposition:AdapterLogic.TranslationAndOrientationShareOneCommand:AdapterLogic.DeadmanRepressCapturesNewOrientationAnchorsWithoutJump:AdapterLogic.RotationWhileReleasedIsIgnored'
```

Expected RED: the new orientation command assertions fail because current logic fixes command orientation to robot anchor；compile failures caused by the new explicit type also count as RED and must be recorded before implementation。

- [ ] **Step 3.4: Implement only anchors and desired orientation mapping**

On ARMED → ACTIVE：

```cpp
const auto normalized_robot = normalize_quaternion(input.robot_pose.orientation);
if (!normalized_robot) return fault_output("invalid_robot_orientation", false);
quest_anchor_ = input.target_pose;
quest_orientation_anchor_ = input.quest_orientation;
robot_anchor_ = input.robot_pose;
robot_anchor_.orientation = *normalized_robot;
last_command_ = robot_anchor_;
last_target_ = input.target_pose;
output.command = last_command_;
output.anchor_captured = true;
```

On a valid ACTIVE cycle, compute exactly：

```cpp
const auto delta_q = relative_world_rotation(
  input.quest_orientation, quest_orientation_anchor_);
const auto scaled_delta_q = scale_shortest_rotation(delta_q, config_.rotation_scale);
const auto mapped_delta_q = map_relative_rotation(scaled_delta_q, config_.mapping);
desired.orientation = compose_world_relative_rotation(
  mapped_delta_q, robot_anchor_.orientation);
```

Do not alter the existing position desired formula or its mapping loop。

- [ ] **Step 3.5: Run anchoring/mapping tests GREEN and existing translation tests**

```bash
./build/rm65_teleop_adapter/test_adapter_logic --gtest_color=yes
./build/rm65_teleop_adapter/test_input_deadman --gtest_color=yes
```

Expected GREEN: new anchor/composition tests pass；`RelativeTranslationUsesAnchorsAndFixedOrientation` must be renamed to `RelativeTranslationUsesAnchorsAndUnchangedIdentityOrientation` and still prove unchanged orientation when Quest delta is identity。

- [ ] **Step 3.6: Write failing angular limiter tests**

Add：

```cpp
TEST(AdapterLogic, AngularVelocityLimitIsApplied);
TEST(AdapterLogic, AngularStepLimitIsApplied);
TEST(AdapterLogic, SmallerAngularLimitWins);
```

Concrete setups：

- Velocity case: `max_angular_velocity_rad_s=0.5`、`max_angular_step_rad=1.0`、`dt=0.1`、desired 0.2 rad；expected command distance from previous is 0.05 rad。
- Step case: `max_angular_velocity_rad_s=10.0`、`max_angular_step_rad=0.01`、`dt=0.1`、desired 0.2 rad；expected 0.01 rad。
- Minimum case: run one subcase where velocity gives 0.02 rad and step is 0.01, and a second where velocity gives 0.005 rad and step is 0.01；expected 0.01 and 0.005 respectively。

All comparisons use `shortest_angular_distance(last_anchor_orientation, output.command->orientation)` rather than quaternion component equality。

- [ ] **Step 3.7: Run limiter RED**

```bash
./build/rm65_teleop_adapter/test_adapter_logic \
  --gtest_filter='AdapterLogic.AngularVelocityLimitIsApplied:AdapterLogic.AngularStepLimitIsApplied:AdapterLogic.SmallerAngularLimitWins'
```

Expected RED: output jumps directly to desired orientation or stays at anchor instead of advancing by the allowed angle。

- [ ] **Step 3.8: Implement shortest-path per-cycle orientation limiting**

Keep position and orientation candidates local until both calculations complete：

```cpp
Pose3 next_command = last_command_;
// Existing position ratio updates next_command.position only.
const double angular_distance = shortest_angular_distance(
  last_command_.orientation, desired.orientation);
const double allowed_angle = std::min(
  config_.max_angular_step_rad,
  config_.max_angular_velocity_rad_s * input.dt_seconds);
if (angular_distance <= allowed_angle) {
  next_command.orientation = desired.orientation;
} else {
  next_command.orientation = slerp_shortest(
    last_command_.orientation, desired.orientation, allowed_angle / angular_distance);
}
last_command_ = next_command;
output.command = last_command_;
```

When `angular_distance` is numerically zero, copy desired orientation and do not divide。Assignment to `last_command_` occurs once, after both position and orientation paths succeed。

- [ ] **Step 3.9: Run GREEN and full adapter regression**

```bash
./build/rm65_teleop_adapter/test_adapter_logic --gtest_color=yes
./build/rm65_teleop_adapter/test_input_deadman --gtest_color=yes
/usr/bin/colcon --log-base log test \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter \
  --event-handlers console_direct+
/usr/bin/colcon test-result --test-result-base build --all --verbose
```

Expected GREEN: all new core 6DoF tests and all pre-existing translation/deadman/pytest suites pass。

- [ ] **Step 3.10: Refactor, whitespace check, commit and push**

Keep translation calculations byte-for-byte equivalent where practical, extract only small local helpers needed to keep `update()` readable：

```bash
git diff --check
git add src/rm65_teleop_adapter/include/rm65_teleop_adapter/adapter_logic.hpp \
  src/rm65_teleop_adapter/src/adapter_logic.cpp \
  src/rm65_teleop_adapter/test/test_adapter_logic.cpp \
  src/rm65_teleop_adapter/test/test_input_deadman.cpp
git commit -m "feat: add anchored 6DoF adapter logic"
git push origin feat/quest-orientation
```

---

### Task 4: Orientation safety, atomic faults and startup config validation

**Checkpoint:** `feat: enforce orientation safety envelope`

**Files:**
- Create: `src/rm65_teleop_adapter/test/test_adapter_config.cpp`
- Modify: `src/rm65_teleop_adapter/CMakeLists.txt`
- Modify: `src/rm65_teleop_adapter/src/adapter_logic.cpp`
- Modify: `src/rm65_teleop_adapter/test/test_adapter_logic.cpp`

**Interfaces:**
- Consumes: Task 3 `CycleInput`/`AdapterConfig` and Task 1 `is_proper_rotation_matrix`。
- Locks these new `CycleOutput.reason` values：
  - `invalid_quest_orientation`
  - `unexpected_orientation_jump`
  - `anchor_angle_violation`
  - `invalid_robot_orientation`
- Preserves existing reasons including `input_not_fresh`、`deadman_released`、`unexpected_target_jump`、`anchor_distance_violation`、`workspace_violation`、`control_period_exceeded`、`invalid_control_period`、`invalid_motion_limit`、`command_path_not_ready`。
- `AdapterLogic(AdapterConfig)` becomes the single testable startup validator. It throws `std::invalid_argument` before any state transition when orientation limits or mapping are invalid；`adapter_node.cpp` will rely on this in Task 5。

- [ ] **Step 4.1: Write failing ACTIVE safety and exact-boundary tests**

Add these exact tests to `test_adapter_logic.cpp`：

```cpp
TEST(AdapterLogic, InvalidQuestOrientationFaultsStopsAndEmitsNoCommand);
TEST(AdapterLogic, UnexpectedOrientationJumpFaultsStopsAndEmitsNoCommand);
TEST(AdapterLogic, JumpExactlyFortyFiveDegreesIsAllowed);
TEST(AdapterLogic, QuaternionSignFlipDoesNotFaultOrMove);
TEST(AdapterLogic, AnchorAngleExactlyNinetyDegreesIsAllowed);
TEST(AdapterLogic, AnchorAngleAboveNinetyDegreesFaultsAndStops);
TEST(AdapterLogic, OrientationFaultDoesNotPublishTranslationCandidate);
TEST(AdapterLogic, TranslationFaultDoesNotPublishOrientationCandidate);
TEST(AdapterLogic, InvalidRobotOrientationCannotBecomeAnchor);
TEST(AdapterLogic, TimeoutAndReleaseRearmSemanticsRemainUnchanged);
TEST(AdapterLogic, ClearOrientationFaultStillRequiresReleaseThenPress);
```

Use the exact event fields：

```cpp
input.quest_orientation_valid = false;
input.quest_orientation_status = OrientationSampleStatus::INVALID;
// Expected: FAULT, reason invalid_quest_orientation, stop_requested, no command.

input.robot_orientation_valid = false;
// Expected on attempted activation: FAULT, reason invalid_robot_orientation, no command.

input.quest_orientation_valid = true;
input.robot_orientation_valid = true;
input.quest_orientation_status = OrientationSampleStatus::UNEXPECTED_JUMP;
input.quest_orientation_jump_rad = config.unexpected_orientation_jump_rad + 1.0e-6;
// Expected reason unexpected_orientation_jump.
```

For 45° equality, status is VALID and `quest_orientation_jump_rad` equals `0.7853981633974483`；for `q/-q`, current quaternion is the exact negation of anchor。For atomicity, change both translation and orientation, then trigger one side’s violation and assert `output.command.has_value()==false`。

- [ ] **Step 4.2: Run safety RED**

```bash
/usr/bin/colcon --log-base log build \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter \
  --cmake-args -DBUILD_TESTING=ON
./build/rm65_teleop_adapter/test_adapter_logic \
  --gtest_filter='AdapterLogic.InvalidQuestOrientationFaultsStopsAndEmitsNoCommand:AdapterLogic.UnexpectedOrientationJumpFaultsStopsAndEmitsNoCommand:AdapterLogic.JumpExactlyFortyFiveDegreesIsAllowed:AdapterLogic.QuaternionSignFlipDoesNotFaultOrMove:AdapterLogic.AnchorAngleExactlyNinetyDegreesIsAllowed:AdapterLogic.AnchorAngleAboveNinetyDegreesFaultsAndStops:AdapterLogic.OrientationFaultDoesNotPublishTranslationCandidate:AdapterLogic.TranslationFaultDoesNotPublishOrientationCandidate:AdapterLogic.InvalidRobotOrientationCannotBecomeAnchor:AdapterLogic.TimeoutAndReleaseRearmSemanticsRemainUnchanged:AdapterLogic.ClearOrientationFaultStillRequiresReleaseThenPress'
```

Expected RED: missing event faults、anchor guard and normalized robot-anchor behavior cause the new assertions to fail。

- [ ] **Step 4.3: Implement safety ordering and exact threshold semantics**

ACTIVE ordering must be: deadman release -> Quest validity -> robot orientation validity -> Quest jump -> freshness -> command path -> control period -> translation jump/envelope -> orientation anchor envelope -> both limiters -> single command assignment. In ARMED, validate both orientations before capturing either anchor; in DISABLED/REARM_REQUIRED, invalid or fast controller motion cannot create a command or a robot fault.

```cpp
if (!input.enable) {
  enter_rearm(false, "deadman_released");
  output.stop_requested = true;
} else if (!input.quest_orientation_valid ||
  input.quest_orientation_status == OrientationSampleStatus::INVALID)
{
  enter_fault("invalid_quest_orientation");
  output.stop_requested = true;
} else if (!input.robot_orientation_valid) {
  enter_fault("invalid_robot_orientation");
  output.stop_requested = true;
} else if (input.quest_orientation_status == OrientationSampleStatus::UNEXPECTED_JUMP ||
  input.quest_orientation_jump_rad > config_.unexpected_orientation_jump_rad)
{
  enter_fault("unexpected_orientation_jump");
  output.stop_requested = true;
} else if (!all_fresh(input)) {
  enter_rearm(true, "input_not_fresh");
  output.stop_requested = true;
}
```

Compute the scaled anchor angle before converting it back to a possibly wrapped quaternion：

```cpp
const double raw_anchor_angle = shortest_angular_distance(identity_quaternion(), delta_q);
const double mapped_anchor_angle = config_.rotation_scale * raw_anchor_angle;
if (mapped_anchor_angle > config_.max_anchor_angle_rad) {
  enter_fault("anchor_angle_violation");
  output.stop_requested = true;
  return without_command();
}
```

Use strict `>` for both jump and anchor guards。Exactly 45° and exactly 90° continue to the limiter。

- [ ] **Step 4.4: Run safety GREEN and existing state-machine regression**

```bash
./build/rm65_teleop_adapter/test_adapter_logic --gtest_color=yes
./build/rm65_teleop_adapter/test_input_deadman --gtest_color=yes
```

Expected GREEN: all safety tests pass；startup release、timeout、clear-fault and deadman tests keep their previous states/reasons。

- [ ] **Step 4.5: Write failing constructor/config validation tests**

Register `test_adapter_config.cpp` as a new GTest target linked to `adapter_logic`。Tests：

Add this exact block inside if(BUILD_TESTING):

~~~cmake
ament_add_gtest(test_adapter_config test/test_adapter_config.cpp)
target_link_libraries(test_adapter_config adapter_logic)
target_include_directories(test_adapter_config PRIVATE include)
~~~

```cpp
TEST(AdapterConfigValidation, AcceptsVerifiedMappingAndOrientationEnvelope);
TEST(AdapterConfigValidation, RejectsNonFiniteMappingEntry);
TEST(AdapterConfigValidation, RejectsNonOrthogonalScaledMapping);
TEST(AdapterConfigValidation, RejectsReflectionWithNegativeDeterminant);
TEST(AdapterConfigValidation, RejectsNonFiniteOrNonPositiveRotationScale);
TEST(AdapterConfigValidation, RejectsNonFiniteOrNonPositiveAngularVelocity);
TEST(AdapterConfigValidation, RejectsNonFiniteOrNonPositiveAngularStep);
TEST(AdapterConfigValidation, RejectsAnchorAngleOutsideZeroToPi);
TEST(AdapterConfigValidation, RejectsJumpAngleOutsideZeroToPi);
```

Concrete invalid matrices：identity with `[0]=2.0` for scaled/nonorthogonal；`diag(1,1,-1)` for reflection；verified mapping with one NaN for nonfinite。Use `EXPECT_THROW(AdapterLogic(config), std::invalid_argument)` and check exception substrings：`proper rotation matrix`、parameter name、`(0, pi]`。

- [ ] **Step 4.6: Run config validation RED**

```bash
/usr/bin/colcon --log-base log build \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter \
  --cmake-args -DBUILD_TESTING=ON
./build/rm65_teleop_adapter/test_adapter_config --gtest_color=yes
```

Expected RED: invalid configs construct successfully because the current constructor does not validate them。

- [ ] **Step 4.7: Add constructor validation minimally**

At the start of `AdapterLogic` construction：

```cpp
if (!is_proper_rotation_matrix(config_.mapping)) {
  throw std::invalid_argument("mapping must be a finite proper rotation matrix");
}
require_finite_positive("rotation_scale", config_.rotation_scale);
require_finite_positive("max_angular_velocity_rad_s", config_.max_angular_velocity_rad_s);
require_finite_positive("max_angular_step_rad", config_.max_angular_step_rad);
require_angle_in_zero_pi("max_anchor_angle_rad", config_.max_anchor_angle_rad);
require_angle_in_zero_pi(
  "unexpected_orientation_jump_rad", config_.unexpected_orientation_jump_rad);
```

Do not add orientation validation to motion profile selection；these values belong to base config only。

- [ ] **Step 4.8: Run GREEN, full adapter regression and refactor**

```bash
./build/rm65_teleop_adapter/test_adapter_config --gtest_color=yes
/usr/bin/colcon --log-base log test \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter \
  --event-handlers console_direct+
/usr/bin/colcon test-result --test-result-base build --all --verbose
git diff --check
```

Expected GREEN: config target、AdapterLogic、deadman and both Python suites report zero failures。

- [ ] **Step 4.9: Commit and push the safety checkpoint**

```bash
git add src/rm65_teleop_adapter/CMakeLists.txt \
  src/rm65_teleop_adapter/src/adapter_logic.cpp \
  src/rm65_teleop_adapter/test/test_adapter_logic.cpp \
  src/rm65_teleop_adapter/test/test_adapter_config.cpp
git commit -m "feat: enforce orientation safety envelope"
git push origin feat/quest-orientation
```

---

### Task 5: Integrate raw Quest orientation in `AdapterNode`, add base parameters, and prove the dry-run command path

**Checkpoint commit:** `feat: integrate raw Quest orientation in adapter node`

**Files:**

- Modify: `src/rm65_teleop_adapter/src/adapter_node.cpp`
- Modify: `src/rm65_teleop_adapter/config/dry_run.yaml`
- Modify: `src/rm65_teleop_adapter/config/hardware.yaml`
- Modify: `src/rm65_teleop_adapter/test/test_motion_profiles.py`
- Create: `src/rm65_teleop_adapter/test/dry_run_6dof_probe.py`

Do not modify either Quest bridge Python file or any file under
`src/rm65_teleop_adapter/config/motion_profiles/`. The node remains the sole owner of the RM65
command publisher, and dry-run mode must continue to create no hardware command publisher.

- [ ] **Step 5.1: Add RED base-config assertions for the complete orientation envelope**

Extend test_motion_profiles.py with this exact helper and test:

~~~python
def load_yaml_parameters(path: Path):
    with path.open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    return document["rm65_teleop_adapter"]["ros__parameters"]


def test_base_configs_define_exact_orientation_envelope():
    expected = {
        "rotation_scale": 1.0,
        "max_angular_velocity_rad_s": 1.5707963267948966,
        "max_angular_step_rad": 0.01,
        "max_anchor_angle_rad": 1.5707963267948966,
        "unexpected_orientation_jump_rad": 0.7853981633974483,
    }
    for config_name in ("dry_run.yaml", "hardware.yaml"):
        params = load_yaml_parameters(PACKAGE_ROOT / "config" / config_name)
        for key, value in expected.items():
            assert params[key] == pytest.approx(value, abs=1.0e-12)
~~~

Keep the existing test_profile_contains_only_allowed_motion_parameters unchanged. Its safe, normal and fast parameterization must continue to assert ALLOWED_PROFILE_KEYS and the exact EXPECTED_PROFILES dictionaries.

Run RED:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /usr/bin/python3 -m pytest -q \
  src/rm65_teleop_adapter/test/test_motion_profiles.py
```

Expected RED: both base YAML files lack all five orientation keys. The translation-profile test
must already pass, proving no profile expansion is needed.

- [ ] **Step 5.2: Add the RED isolated dry-run 6DoF probe**

Create `dry_run_6dof_probe.py` as a bounded `rclpy` executable. It must use only these topics:

| Direction | Topic | Message |
|---|---|---|
| publish | `/quest_right_target_pose` | `geometry_msgs/msg/PoseStamped` |
| publish | `/q2r_right_hand_pose` | `geometry_msgs/msg/PoseStamped` |
| publish | `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` |
| publish | /right/rm_driver/udp_arm_position | geometry_msgs/msg/Pose |
| subscribe | `/right/rm65_teleop/preview_target_pose` | `geometry_msgs/msg/PoseStamped` |
| subscribe | `/right/rm65_teleop/status` | `std_msgs/msg/String` |

Do not publish to `/right/rm_driver/movep_canfd_cmd`. Before any motion phase, assert:

```python
assert probe.count_publishers("/right/rm_driver/movep_canfd_cmd") == 0
```

Implement these exact helpers in the probe:

- quaternion_from_axis_angle(axis_xyz: Sequence[float], angle_rad: float) -> list[float]: normalize the nonzero axis and return normalized ROS-order [x, y, z, w].
- quaternion_norm(quaternion_xyzw: Sequence[float]) -> float: return sqrt(x*x + y*y + z*z + w*w).
- shortest_angle(lhs_xyzw: Sequence[float], rhs_xyzw: Sequence[float]) -> float: normalize both and return 2*acos(clamp(abs(dot), 0, 1)).
- assert_quaternion_close(actual_xyzw: Sequence[float], expected_xyzw: Sequence[float], tolerance_rad: float) -> None: fail with both values and angular error when shortest_angle exceeds tolerance.
- wait_for(predicate: Callable[[], bool], timeout_sec: float, description: str) -> None: call rclpy.spin_once until predicate succeeds or a monotonic deadline raises AssertionError containing description.

The probe publishes every input stream at 100 Hz and executes these bounded phases:

1. `released_baseline`: `press_middle = 0.0`; publish a fixed target position, identity Quest
   orientation and fixed robot feedback until status is `ARMED`.
2. `press_anchor`: switch to `press_middle = 1.0`; wait for the first preview and assert its
   position and orientation equal the robot feedback anchor within `1e-9 m` and `1e-9 rad`.
3. `quest_x_rotation`: keep the target position fixed and publish Quest `+X` axis-angle samples
   ramped from `0.0` to `0.04 rad` in increments no larger than `0.005 rad`; wait until preview
   converges and assert the robot preview is a `-Y` rotation of `0.04 rad` from its robot anchor.
4. `combined_motion`: ramp translation and a non-commuting Quest rotation while still pressed;
   assert both preview position and preview orientation change and every preview quaternion is
   finite, normalized within `1e-9`, and continuous by shortest angular distance.
5. `release_freeze`: set `press_middle = 0.0`, record the preview count, continue moving and
   rotating Quest inputs for `0.25 s`, and assert the preview count does not increase.
6. `repress_anchor`: publish a different robot feedback pose and the current Quest pose, press
   again, and assert the first preview equals the new robot feedback pose without position or
   orientation jump.
7. `final_checks`: assert all observed status JSON parses, contains the existing `state` and
   `reason` keys, and the hardware command publisher count remains zero.

Use the existing message field names discovered in `adapter_node.cpp` and the installed
`quest2ros/msg/OVR2ROSInputs`; do not invent a second status schema or a second command path.
Return exit code zero only when every phase completes within its deadline.

Build the current package, start only the adapter in an isolated ROS domain, and run RED:

```bash
conda deactivate 2>/dev/null || true
source /opt/ros/humble/setup.bash
source /home/lh/robot/install/setup.bash
/usr/bin/colcon --log-base log build \
  --build-base build --install-base install \
  --symlink-install --packages-select rm65_teleop_adapter
source install/setup.bash
export ROS_DOMAIN_ID=142
export ROS_LOCALHOST_ONLY=1
ros2 run rm65_teleop_adapter rm65_teleop_adapter_node \
  --ros-args \
  --params-file install/rm65_teleop_adapter/share/rm65_teleop_adapter/config/dry_run.yaml \
  > /tmp/quest_orientation_adapter.log 2>&1 &
adapter_pid=$!
trap 'kill "$adapter_pid" 2>/dev/null || true; wait "$adapter_pid" 2>/dev/null || true' EXIT
/usr/bin/python3 src/rm65_teleop_adapter/test/dry_run_6dof_probe.py
```

Expected RED: the current node does not feed raw Quest orientation into `AdapterLogic`, so the
`quest_x_rotation` phase times out or observes unchanged orientation. It must not fail because a
hardware publisher appeared. Stop only `adapter_pid`; never use a broad process-kill command.

- [ ] **Step 5.3: Declare and load the five orientation parameters**

In `AdapterNode` constructor declarations, add exactly:

```cpp
config.rotation_scale = this->declare_parameter<double>("rotation_scale", 1.0);
config.max_angular_velocity_rad_s = this->declare_parameter<double>(
  "max_angular_velocity_rad_s", 1.5707963267948966);
config.max_angular_step_rad = this->declare_parameter<double>(
  "max_angular_step_rad", 0.01);
config.max_anchor_angle_rad = this->declare_parameter<double>(
  "max_anchor_angle_rad", 1.5707963267948966);
config.unexpected_orientation_jump_rad = this->declare_parameter<double>(
  "unexpected_orientation_jump_rad", 0.7853981633974483);
```

Keep code/config units in radians. Add the same exact scalar values to the
`rm65_teleop_adapter.ros__parameters` map in both base YAML files. Do not add these keys beneath a
motion profile and do not change any translation parameter value.

Include rm65_teleop_adapter/quest_orientation_tracker.hpp and add these private members to AdapterNode:

~~~cpp
std::unique_ptr<QuestOrientationTracker> orientation_tracker_;
bool robot_orientation_valid_{false};
~~~

Construct exactly one tracker after AdapterLogic has validated the shared config:

~~~cpp
orientation_tracker_ = std::make_unique<QuestOrientationTracker>(
  config.unexpected_orientation_jump_rad);
~~~

- [ ] **Step 5.4: Feed every raw Quest orientation sample into the tracker**

In the existing quest_pose_subscription_ callback:

1. Convert `msg->pose.orientation` to `QuaternionXyzw`.
2. Call `orientation_tracker_->ingest(raw_orientation)` for every received message, including an
   invalid quaternion; this is required so invalid input cannot silently reuse a stale orientation.
3. Keep the current finite-position validity flag and receipt timestamp behavior unchanged; do not add a raw Quest position cache.

Do not transform orientation in the node callback. Relative rotation, conjugation by `M`, scaling,
anchor composition and limiting remain owned by `AdapterLogic` and the Task 1 math layer.

- [ ] **Step 5.5: Normalize robot feedback orientation without overwriting the last valid pose**

In the robot-feedback callback:

```cpp
robot_received_ = true;
robot_time_ = SteadyClock::now();
Pose3 candidate = from_ros_pose(*message);
const auto normalized = normalize_quaternion(candidate.orientation);
if (!normalized.has_value()) {
  robot_orientation_valid_ = false;
  return;
}
candidate.orientation = *normalized;
robot_pose_ = candidate;
robot_orientation_valid_ = true;
```

Keep the previously cached valid robot pose intact on invalid input. The next timer input must set:

```cpp
input.robot_fresh = is_fresh(robot_received_, robot_time_, robot_timeout_);
input.robot_orientation_valid = robot_orientation_valid_;
```

This uses the existing `robot_timeout_` gate and causes the already specified
`invalid_robot_orientation` fault while ACTIVE. It does not create a separate watchdog.

- [ ] **Step 5.6: Populate `CycleInput` atomically and synchronize tracker session state**

In the control timer, call `consume_snapshot()` once and use that one snapshot for the full cycle:

```cpp
const OrientationSnapshot orientation = orientation_tracker_->consume_snapshot();
input.quest_orientation = orientation.latest_orientation;
input.quest_orientation_valid =
  orientation.has_valid_orientation && orientation.latest_sample_valid;
input.quest_orientation_status = orientation.status;
input.quest_orientation_jump_rad = orientation.jump_angle_rad;
```

Retain the existing order in which deadman state, watchdog freshness, target, robot feedback and
control-period state are sampled. Call AdapterLogic::update exactly once, then synchronize tracker session state:

```cpp
const AdapterState previous = logic_->state();
const CycleOutput output = logic_->update(input);
if (output.anchor_captured) {
  orientation_tracker_->begin_active_session(input.quest_orientation);
}
if (previous == AdapterState::ACTIVE && output.state != AdapterState::ACTIVE) {
  orientation_tracker_->end_active_session();
}
```

Release handling remains dominant: if the
same timer observes a release and an orientation jump, the existing release stop/rearm transition
wins and the jump is not emitted as a robot command. A later press captures a fresh Quest and robot
anchor.

Publish `output.command` through the existing preview/hardware branch only. Do not add another
publisher, executor callback, timer, or safety bypass. Keep status JSON backward compatible;
orientation faults are exposed through the existing `reason` value.

- [ ] **Step 5.7: Run GREEN unit/config tests and the isolated dry-run probe**

```bash
conda deactivate 2>/dev/null || true
source /opt/ros/humble/setup.bash
source /home/lh/robot/install/setup.bash
test "$(command -v python3)" = /usr/bin/python3
test "$(command -v colcon)" = /usr/bin/colcon
/usr/bin/colcon --log-base log build \
  --build-base build --install-base install \
  --symlink-install --packages-select rm65_teleop_adapter
source install/setup.bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /usr/bin/python3 -m pytest -q \
  src/rm65_teleop_adapter/test/test_motion_profiles.py
./build/rm65_teleop_adapter/test_quaternion_math --gtest_color=yes
./build/rm65_teleop_adapter/test_quest_orientation_tracker --gtest_color=yes
./build/rm65_teleop_adapter/test_adapter_logic --gtest_color=yes
./build/rm65_teleop_adapter/test_adapter_config --gtest_color=yes
./build/rm65_teleop_adapter/test_input_deadman --gtest_color=yes
export ROS_DOMAIN_ID=142
export ROS_LOCALHOST_ONLY=1
ros2 run rm65_teleop_adapter rm65_teleop_adapter_node \
  --ros-args \
  --params-file install/rm65_teleop_adapter/share/rm65_teleop_adapter/config/dry_run.yaml \
  > /tmp/quest_orientation_adapter.log 2>&1 &
adapter_pid=$!
trap 'kill "$adapter_pid" 2>/dev/null || true; wait "$adapter_pid" 2>/dev/null || true' EXIT
/usr/bin/python3 src/rm65_teleop_adapter/test/dry_run_6dof_probe.py
```

Expected GREEN: all five unit targets and config tests pass; the probe confirms mapped orientation,
simultaneous translation/rotation, release freeze, jump-free re-anchoring and zero hardware command
publishers. This proves only an isolated synthetic dry-run, not live Quest or RM65 rotation.

- [ ] **Step 5.8: Inspect the command path and commit the node/config checkpoint**

```bash
rg -n 'movep_canfd_cmd|preview_target_pose|create_publisher' \
  src/rm65_teleop_adapter/src/adapter_node.cpp
git diff --check
git diff -- \
  src/rm65_teleop_adapter/src/adapter_node.cpp \
  src/rm65_teleop_adapter/config/dry_run.yaml \
  src/rm65_teleop_adapter/config/hardware.yaml \
  src/rm65_teleop_adapter/test/test_motion_profiles.py \
  src/rm65_teleop_adapter/test/dry_run_6dof_probe.py
git add src/rm65_teleop_adapter/src/adapter_node.cpp \
  src/rm65_teleop_adapter/config/dry_run.yaml \
  src/rm65_teleop_adapter/config/hardware.yaml \
  src/rm65_teleop_adapter/test/test_motion_profiles.py \
  src/rm65_teleop_adapter/test/dry_run_6dof_probe.py
git commit -m "feat: integrate raw Quest orientation in adapter node"
git push origin feat/quest-orientation
```

The review must show one existing hardware command publisher, one existing preview publisher, and
no new orientation-specific command publisher.

---

### Task 6: Update factual documentation, run the complete regression, and hold the real-hardware gate

**Checkpoint commit:** `docs: document right-arm 6DoF orientation implementation`

**Files:**

- Modify: `docs/INTERFACE.md`
- Modify: `STATUS.md`
- Modify: `CHANGELOG.md`
- Modify: `src/rm65_teleop_adapter/README.md`
- Create: `docs/progress/right-arm-6dof-orientation.md`

Documentation may describe only evidence produced by Tasks 1–5. It must keep live Quest orientation
and real RM65 rotation explicitly unverified until the human-only validation sequence below has
actually been performed.

- [ ] **Step 6.1: Run a RED documentation-contract audit**

Before editing documentation, run:

```bash
test -f docs/progress/right-arm-6dof-orientation.md
rg -n 'q_Q0|q_R0|Delta R_Q|M.*Delta R_Q.*M\^T' docs/INTERFACE.md
rg -n 'rotation_scale|max_angular_velocity_rad_s|max_angular_step_rad|max_anchor_angle_rad|unexpected_orientation_jump_rad' \
  src/rm65_teleop_adapter/README.md
```

Expected RED: the progress file is absent and the current interface/README contract does not yet
contain the complete orientation mapping and envelope.

- [ ] **Step 6.2: Update `docs/INTERFACE.md` with the implemented 6DoF contract**

Record these facts without rewriting interface history:

1. `/quest_right_target_pose` remains the already verified translation target; its identity
   orientation remains intentionally ignored for robot orientation control.
2. `/q2r_right_hand_pose.pose.orientation` is the raw orientation source consumed directly by
   `rm65_teleop_adapter` under the existing deadman/watchdog/command gate.
3. Quaternions use ROS `x, y, z, w` storage, are normalized, use hemisphere unification, and never
   use Euler accumulation.
4. Define the world-frame relative convention exactly:

   ```text
   Delta R_Q = R_Q * R_Q0^T
   Delta R_RM = M * Delta R_Q * M^T
   R_desired = scale(Delta R_RM, rotation_scale) * R_R0
   ```

5. State that left multiplication is deliberate: a Quest-world relative rotation is conjugated
   into an RM-base relative rotation and applied in the RM base/world frame to the robot anchor.
6. Copy the unchanged matrix and physical-axis mapping:

   ```text
   M = [ 0  0  1
        -1  0  0
         0 -1  0 ]

   Quest +X forward -> RM65 -Y
   Quest +Y left    -> RM65 -Z
   Quest +Z up      -> RM65 +X
   ```

7. Document `allowed_angle = min(max_angular_step_rad,
   max_angular_velocity_rad_s * dt)` and shortest-path SLERP from the last command.
8. Document anchor-angle, consecutive-sample jump, invalid quaternion and non-finite quaternion
   transitions into stop/fault/rearm through the existing safety state machine.
9. State that translation mapping, translation motion profiles, workspace and all watchdogs remain
   unchanged.

- [ ] **Step 6.3: Update operator-facing README and project status documents**

In `src/rm65_teleop_adapter/README.md`, add one orientation-envelope table with these exact rows:

| Parameter | Code/config value | Human-readable value |
|---|---:|---:|
| `rotation_scale` | `1.0` | one-to-one relative angle |
| `max_angular_velocity_rad_s` | `1.5707963267948966` | 90 deg/s |
| `max_angular_step_rad` | `0.01` | about 0.57 deg/cycle |
| `max_anchor_angle_rad` | `1.5707963267948966` | 90 deg |
| `unexpected_orientation_jump_rad` | `0.7853981633974483` | 45 deg |

Also describe the existing middle-finger Grip behavior: press captures both anchors, translation and
rotation can occur simultaneously, release stops, and repress re-anchors without a jump. List the
isolated dry-run probe command, and place an explicit warning immediately before any hardware launch
example: automated success does not authorize real robot rotation.

Update `STATUS.md` with separate evidence lines:

- quaternion/mapping/anchor/limiter/safety unit tests passed;
- existing translation/deadman/motion-profile/Quest bridge regressions passed;
- isolated synthetic dry-run proved preview behavior and zero hardware command publisher;
- live Quest quaternion probe is pending;
- real RM65 rotation has not been run and is not verified.

Add a dated `CHANGELOG.md` entry that names the five radian parameters, direct raw Quest orientation
path, unchanged translation bridge, test additions, and documentation-only truth about hardware
validation.

- [ ] **Step 6.4: Create the exact implementation evidence record**

Create `docs/progress/right-arm-6dof-orientation.md` with these sections:

```markdown
# Right-arm 6DoF orientation progress

## Scope and base
## Implemented architecture
## Quaternion convention and equations
## Safety envelope
## Automated evidence
## Synthetic dry-run evidence
## Preserved translation and command path
## Pending human validation
## Checkpoint commits
```

Under “Scope and base”, record branch `feat/quest-orientation`, design base
`9445bf54deef3a23fd14b0e267107bb309ca3ba5`, the actual implementation checkpoint SHAs, and the
exact Ubuntu worktree path. Under “Automated evidence”, copy command lines and pass counts from the
fresh Task 6.6 output, never estimates. Under “Synthetic dry-run evidence”, state the isolated ROS
domain, adapter-only process, preview checks, and zero command-publisher result. Under “Pending human
validation”, state plainly that live Quest probing and all real RM65 rotation remain pending.

- [ ] **Step 6.5: Re-run the documentation-contract audit GREEN**

```bash
test -f docs/progress/right-arm-6dof-orientation.md
rg -n 'q_Q0|q_R0|Delta R_Q|M.*Delta R_Q.*M\^T' docs/INTERFACE.md
rg -n 'rotation_scale|max_angular_velocity_rad_s|max_angular_step_rad|max_anchor_angle_rad|unexpected_orientation_jump_rad' \
  src/rm65_teleop_adapter/README.md
rg -n 'live Quest.*pending|real RM65 rotation.*not.*verified' \
  STATUS.md docs/progress/right-arm-6dof-orientation.md
```

Expected GREEN: every command exits zero and no text claims a live Quest or hardware result.

- [ ] **Step 6.6: Run the complete four-package build and test suite from the clean ROS environment**

```bash
conda deactivate 2>/dev/null || true
source /opt/ros/humble/setup.bash
source /home/lh/robot/install/setup.bash
test "$(command -v python3)" = /usr/bin/python3
test "$(command -v colcon)" = /usr/bin/colcon
/usr/bin/colcon --log-base log build \
  --build-base build --install-base install \
  --symlink-install \
  --packages-select quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter
source install/setup.bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /usr/bin/colcon --log-base log test \
  --build-base build --install-base install \
  --packages-select quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter \
  --event-handlers console_direct+
/usr/bin/colcon test-result --test-result-base build --all --verbose
```

Expected GREEN: the build exits zero; all reported tests have zero errors and zero failures. Record
the actual totals in the progress document after this run.

- [ ] **Step 6.7: Run the focused math, state-machine and Python regressions**

```bash
./build/rm65_teleop_adapter/test_quaternion_math --gtest_color=yes
./build/rm65_teleop_adapter/test_quest_orientation_tracker --gtest_color=yes
./build/rm65_teleop_adapter/test_adapter_logic --gtest_color=yes
./build/rm65_teleop_adapter/test_adapter_config --gtest_color=yes
./build/rm65_teleop_adapter/test_input_deadman --gtest_color=yes
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /usr/bin/python3 -m pytest -q \
  src/rm65_teleop_adapter/test/test_motion_profiles.py \
  src/rm65_teleop_adapter/test/test_teleop_status_logic.py \
  src/Quest2ROS2/test/test_quest_right_target_logic.py \
  src/Quest2ROS2/test/test_quest_right_target_bridge.py
```

Expected GREEN: every focused binary and all four Python files exit zero. In particular, the Quest
bridge tests must continue to assert identity orientation on `/quest_right_target_pose`; that is a
regression guarantee, not a missing feature.

- [ ] **Step 6.8: Re-run the isolated dry-run proof with no driver and no robot**

```bash
export ROS_DOMAIN_ID=142
export ROS_LOCALHOST_ONLY=1
ros2 run rm65_teleop_adapter rm65_teleop_adapter_node \
  --ros-args \
  --params-file install/rm65_teleop_adapter/share/rm65_teleop_adapter/config/dry_run.yaml \
  > /tmp/quest_orientation_adapter.log 2>&1 &
adapter_pid=$!
trap 'kill "$adapter_pid" 2>/dev/null || true; wait "$adapter_pid" 2>/dev/null || true' EXIT
/usr/bin/python3 src/rm65_teleop_adapter/test/dry_run_6dof_probe.py
```

Expected GREEN: mapped orientation and simultaneous 6DoF preview pass, release/repress semantics
pass, no hardware command publisher exists, and only `adapter_pid` is stopped. Do not start the
Quest bridge, RM driver, RViz or any robot launch file for this automated gate.

- [ ] **Step 6.9: Prove the verified translation path and motion profiles were not edited**

```bash
git diff --exit-code 9445bf54deef3a23fd14b0e267107bb309ca3ba5 -- \
  src/Quest2ROS2/q2r2_bringup/quest_right_target_bridge.py \
  src/Quest2ROS2/q2r2_bringup/quest_right_target_logic.py
git diff --exit-code 9445bf54deef3a23fd14b0e267107bb309ca3ba5 -- \
  src/rm65_teleop_adapter/config/motion_profiles
rg -n 'IDENTITY_QUATERNION|orientation' \
  src/Quest2ROS2/test/test_quest_right_target_bridge.py
```

Expected GREEN: both diffs are empty and the existing bridge identity-orientation assertion remains
present.

- [ ] **Step 6.10: Perform the final safety and repository review**

```bash
git diff --check
git status --short --branch
git diff --stat 9445bf54deef3a23fd14b0e267107bb309ca3ba5
git diff --name-only 9445bf54deef3a23fd14b0e267107bb309ca3ba5
if rg -n '添加.*测试|实现.*逻辑|待补充|待定' \
  docs/INTERFACE.md STATUS.md CHANGELOG.md \
  src/rm65_teleop_adapter/README.md \
  docs/progress/right-arm-6dof-orientation.md \
  src/rm65_teleop_adapter/include \
  src/rm65_teleop_adapter/src \
  src/rm65_teleop_adapter/test; then exit 1; fi
git diff 9445bf54deef3a23fd14b0e267107bb309ca3ba5 -- \
  src/rm65_teleop_adapter/src/adapter_node.cpp | \
  rg -n 'movep_canfd_cmd|preview_target_pose|create_publisher'
```

Review the complete diff against the five `Review Focus` questions at the top of this plan. Confirm
that changed files are limited to the listed implementation, test, base-config and documentation
paths; no generated build artifact, credential or unrelated user change is staged.

- [ ] **Step 6.11: Commit documentation, push, and verify the remote branch**

```bash
git add docs/INTERFACE.md STATUS.md CHANGELOG.md \
  src/rm65_teleop_adapter/README.md \
  docs/progress/right-arm-6dof-orientation.md
git commit -m "docs: document right-arm 6DoF orientation implementation"
git push origin feat/quest-orientation
git fetch origin
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/feat/quest-orientation)"
git status --short --branch
```

Expected GREEN: local and remote SHAs match and the worktree is clean. Do not merge the branch.

---

## Human-only validation gate after implementation review

Automated completion of this plan does not authorize real RM65 rotation. A human operator must
explicitly authorize a later session and complete the following sequence before hardware rotation
can be described as verified.

### Live Quest dry-run probe

1. Observe `/q2r_right_hand_pose.pose.orientation` with no RM driver running.
2. Confirm the quaternion is finite, near unit norm and stable while the controller is still.
3. Rotate one wrist axis at a time and confirm continuous quaternion change.
4. Confirm any `q`/`-q` sign change causes no preview jump.
5. Run the adapter in dry-run and confirm preview axes, direction, anchor behavior, jump guard and
   orientation limiter agree with the documented convention.

### Staged RM65 validation, only after the dry-run probe is accepted

1. Remove tool and payload and clear the robot workspace.
2. Test one physical axis at about `+5 deg` and `-5 deg`.
3. Repeat at about `+10 deg` and `-10 deg`.
4. Confirm all three physical rotation directions independently.
5. Test a slow combined rotation.
6. Finally test simultaneous translation and rotation.

Do not begin with a large or fast wrist rotation. Any invalid quaternion, unexpected jump, anchor
angle violation, watchdog failure or direction mismatch ends the session in stop/rearm and requires
investigation before another attempt.

---

## Execution handoff

The implementation is intentionally split into six pushed checkpoints. Execute Tasks 1–6 in order
because each task consumes the exact interfaces and evidence created by the preceding task. Review
this plan before implementation, then choose either native sequential execution in the current
task or explicitly authorized subagent-driven execution. Neither choice changes the human-only
hardware gate.
