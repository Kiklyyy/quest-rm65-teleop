# Quest Right Target Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 实现 Quest 右手到安全虚拟 target Pose/Marker 的 1:1 相对平移映射，具有 deadman 与 Pose watchdog，且不连接任何 RM65 控制接口。

**Architecture:** 实现分为两层：纯 Python 的 QuestRightTargetLogic 负责三态状态机、pending activation、相对位移和 watchdog；ROS 2 的 QuestRightTargetBridge adapter 只负责消息订阅、单调时钟输入、ROS clock 输出、50 Hz 发布和消息构造。纯逻辑不依赖 ROS 消息，adapter 不包含任何机器人控制能力。

**Tech Stack:** Ubuntu 22.04.5；aarch64；ROS 2 Humble；Python 3.10（/usr/bin/python3）；rclpy；geometry_msgs；visualization_msgs；quest2ros/msg/OVR2ROSInputs；pytest。

**Spec:** docs/superpowers/specs/2026-09-19-quest-right-target-bridge-design.md

## Global Constraints

- 只操作 /home/lh/quest2ros2_ws。
- 不修改 /home/lh/robot。
- 不 source /home/lh/robot/install/setup.bash。
- 不启动 RM driver、rm_control、MoveIt、CuRobo。
- 不启动 left_arm_controller 或 right_arm_controller。
- 不发布任何 /left/* 或 /right/* RM65 控制命令。
- ROS 2 Humble 必须使用系统 Python /usr/bin/python3。
- ROS_DOMAIN_ID 必须显式设置为 42。
- 不使用 Conda Python 运行 rclpy 或 colcon。
- 当前已有 package.xml、q2r2_bringup/ros2quest.py、.pyc 等 dirty files 必须原样保留。
- quest2ros 和 ros_tcp_communication 不属于本任务修改范围。
- 不删除、重置、清理或误提交任何现有 dirty file。
- 不创建 ActionClient，不导入任何机器人控制模块，不连接夹爪或轨迹接口。
- 每个实现 commit 只暂存该 Task 明确列出的文件。
- 第一版只映射平移，scale=1.0，三轴 identity；不在本阶段修改轴映射。
- 输入 Pose 的 header、orientation 和 stamp 一律忽略；输出 timestamp 由 ROS node clock 生成。

## Review Focus

1. **button press 先于第一帧 Pose：** test_press_before_first_pose_enters_pending_without_jump、test_first_pose_after_pending_press_anchors_without_jump 和 test_pending_activation_times_out_and_locks 覆盖 pending、无假锚点与超时锁定。
2. **deadman 上升沿遇到 stale Pose：** test_stale_pose_cannot_be_used_as_anchor 覆盖 stale Pose 转 pending、新 Pose 才能锚定。
3. **timeout 边界恰好 0.2 秒与严格大于 0.2 秒：** test_timeout_at_exact_boundary_does_not_trigger、test_timeout_above_boundary_requires_rearm 和 test_pose_age_at_exact_boundary_is_fresh_for_press 覆盖两侧边界。
4. **timeout 后按钮持续按住且 Pose 恢复：** test_pose_recovery_while_held_stays_rearm_required 与 test_late_pose_itself_locks_before_target_update 覆盖不能自动恢复和不能先跳一次。
5. **异步重复 Pose/Input 回调：** test_repeated_true_does_not_reset_anchor、test_repeated_false_is_harmless、test_repeated_identical_pose_does_not_change_target 和 test_non_monotonic_time_is_ignored 覆盖不重锚、不跳变和时间回退。

---

## File Map and Locked Interfaces

实施期间只涉及以下产品与测试文件：

| 路径 | 操作 | 单一职责 |
|---|---|---|
| q2r2_bringup/quest_right_target_logic.py | Create | 纯 Python 三态状态机、pending activation、相对位移、watchdog |
| test/test_quest_right_target_logic.py | Create | 确定性验证纯逻辑和所有安全边界 |
| q2r2_bringup/quest_right_target_bridge.py | Create | ROS 2 subscriptions、publishers、时钟、消息构造、50 Hz timer |
| test/test_quest_right_target_bridge.py | Create | 验证 adapter 常量、消息 helper、入口和静态安全边界 |
| setup.py | Modify | 只增加 quest_right_target_bridge console script |

package.xml 已声明 rclpy、geometry_msgs、visualization_msgs、quest2ros 和 python3-pytest，第一版不修改。

### Spec Traceability

| Spec 范围 | 实施与验证位置 |
|---|---|
| 目的、安全边界、RM65 完全断开 | Global Constraints；Task 2 静态安全测试；Task 3 ROS graph 检查 |
| 两个输入 topic 与忽略字段 | Task 2 constants、callback wiring 测试与 adapter 实现 |
| Pose/Marker 输出字段 | Task 2 message helper 测试；Task 3 无输入 smoke test |
| 1:1 identity 相对平移 | Task 1 x/y/z、多轴、scale 测试 |
| INACTIVE/ACTIVE/REARM_REQUIRED | Task 1 全部状态转换测试 |
| 严格 >0.2s watchdog 与重新授权 | Task 1 边界、late-pose、recovery、release/re-press 测试 |
| 50 Hz 持续发布 | Task 2 timer wiring；Task 3 ros2 topic hz |
| 纯逻辑与 ROS adapter 分层 | Task 1 与 Task 2 文件边界和 locked interfaces |
| 自动化、模拟输入、真实 Quest/RViz 验证 | Task 1/2 pytest；Task 3 三层验证 |
| 已有 dirty files 保护 | 每个 Task 的 status、限定 git add、diff-tree 复核 |
| Stage 2 成功定义 | Task 3 Implementation Completion Gate |

### QuestRightTargetLogic API

q2r2_bringup/quest_right_target_logic.py 必须提供：

~~~text
BridgeState.INACTIVE
BridgeState.ACTIVE
BridgeState.REARM_REQUIRED

QuestRightTargetLogic(
    initial_target: tuple[float, float, float] = (0.5, 0.0, 0.5),
    scale: float = 1.0,
    timeout_s: float = 0.2,
) -> QuestRightTargetLogic

QuestRightTargetLogic.update_pose(
    position: tuple[float, float, float],
    now_s: float,
) -> None

QuestRightTargetLogic.update_deadman(
    pressed: bool,
    now_s: float,
) -> None

QuestRightTargetLogic.check_timeout(now_s: float) -> None
QuestRightTargetLogic.target -> tuple[float, float, float]
QuestRightTargetLogic.state -> BridgeState
QuestRightTargetLogic.activation_pending -> bool
~~~

activation_pending 是只读诊断属性，用于确定性验证 press-before-pose 与 stale-pose 分支；它不是第四个公开状态。业务状态始终只有 BridgeState 的三个成员。

### Locked State Semantics

- 初始 state=INACTIVE、target=(0.5, 0.0, 0.5)、activation_pending=False。
- update_pose 始终接收纯 float 三元 tuple；target 内部保存为独立 immutable tuple。
- INACTIVE 且未按 deadman 时，Pose 只更新 latest pose 和接收时间，不移动 target。
- false -> true 且 latest pose age <= timeout_s 时，立即以 latest pose 为 Q0、当前 target 为 T0，进入 ACTIVE，target 不跳变。
- false -> true 且没有 Pose 或 latest pose age > timeout_s 时，保持 INACTIVE、activation_pending=True，并以该 press 的 now_s 作为 pending 起点。
- pending 期间第一帧新 Pose 若满足 pending age <= timeout_s，则以该 Pose 为 Q0、当前 target 为 T0，进入 ACTIVE，target 不跳变。
- pending age 严格大于 timeout_s 时进入 REARM_REQUIRED；晚到 Pose 本身也必须在计算 target 前执行该判断。
- ACTIVE 时 target=anchor_target+scale*(current_pose-anchor_pose)，第一版逐轴 identity。
- release 立即清除 pending/anchor、冻结 target，并从 ACTIVE 或 REARM_REQUIRED 回到 INACTIVE。
- REARM_REQUIRED 时 Pose 可以刷新 latest pose，但按钮持续 true 不得激活；必须先 false，再出现新的 false -> true。
- repeated true 不重置 anchor 或 pending 起点；repeated false 不改变 target。
- check_timeout 和 update_pose 都必须能捕获严格大于 0.2 秒的 ACTIVE Pose gap，避免 timer 与晚到 Pose 的执行顺序造成一次跳变。
- 所有 age 使用 max(0.0, now_s - reference_time)。
- 维护最后接受的单调时间；时间回退的 update_pose 和 pressed=True 事件全部忽略，不更新 cache、target 或 anchor；时间回退的 check_timeout 不触发 timeout。
- pressed=False 是安全冻结事件，即使 now_s 回退也必须被接受：冻结 target、清除 pending/anchor 并进入 INACTIVE；该事件不得把最后接受时间倒退。
- now_s 恰好使 age==timeout_s 时仍然有效；只有 age>timeout_s 才锁定。

### ROS Adapter API and Constants

q2r2_bringup/quest_right_target_bridge.py 必须提供：

~~~text
POSE_TOPIC = "/q2r_right_hand_pose"
INPUTS_TOPIC = "/q2r_right_hand_inputs"
TARGET_POSE_TOPIC = "/quest_right_target_pose"
TARGET_MARKER_TOPIC = "/quest_right_target_marker"
WORLD_FRAME = "world"
TIMER_PERIOD_S = 0.02
MARKER_NAMESPACE = "quest_right_target"
MARKER_ID = 0
MARKER_SCALE_M = 0.06
MARKER_COLOR_RGBA = (0.1, 1.0, 0.2, 0.9)


build_target_pose(
    target: tuple[float, float, float],
    stamp,
) -> PoseStamped

build_target_marker(
    target: tuple[float, float, float],
    stamp,
) -> Marker

QuestRightTargetBridge(Node)
main(args=None) -> None
~~~

stamp 故意保持 duck-typed，不直接 import builtin_interfaces.msg.Time，从而不为 q2r2_bringup 增加新的直接 manifest dependency；测试使用 ROS 已有的 Time 消息验证字段透传。

---

### Task 1: Pure State Machine + Unit Tests

**Files:**
- Create: q2r2_bringup/quest_right_target_logic.py
- Create: test/test_quest_right_target_logic.py

**Interfaces:**
- Consumes: Python 3.10 标准库 enum；不依赖 rclpy 或 ROS message。
- Produces: BridgeState、QuestRightTargetLogic、update_pose(position, now_s)、update_deadman(pressed, now_s)、check_timeout(now_s)、target、state、activation_pending，供 Task 2 adapter 使用。

- [ ] **Step 1: 确认工作树基线并只观察已有 dirty files**

~~~bash
cd /home/lh/quest2ros2_ws/src/Quest2ROS2
git status --short --branch
git diff -- package.xml q2r2_bringup/ros2quest.py
~~~

Expected: 仍看到用户已有的 package.xml、q2r2_bringup/ros2quest.py 和 .pyc 状态；不要暂存、修改或清理它们。

- [ ] **Step 2: 创建完整失败测试文件**

创建 test/test_quest_right_target_logic.py，内容如下：

~~~python
import pytest

from q2r2_bringup.quest_right_target_logic import (
    BridgeState,
    QuestRightTargetLogic,
)


INITIAL_TARGET = (0.5, 0.0, 0.5)
ANCHOR_POSE = (1.0, 2.0, 3.0)


def make_active() -> QuestRightTargetLogic:
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=1.0)
    logic.update_deadman(True, now_s=1.0)
    assert logic.state is BridgeState.ACTIVE
    return logic


def test_initial_target():
    logic = QuestRightTargetLogic()

    assert logic.target == pytest.approx(INITIAL_TARGET)
    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is False


def test_inactive_pose_movement_is_ignored():
    logic = QuestRightTargetLogic()

    logic.update_pose((8.0, 9.0, 10.0), now_s=1.0)

    assert logic.target == pytest.approx(INITIAL_TARGET)
    assert logic.state is BridgeState.INACTIVE


def test_first_normal_press_does_not_jump():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=1.0)

    logic.update_deadman(True, now_s=1.1)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_active_x_movement():
    logic = make_active()

    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)

    assert logic.target == pytest.approx((0.6, 0.0, 0.5))


def test_active_y_movement():
    logic = make_active()

    logic.update_pose((1.0, 2.1, 3.0), now_s=1.1)

    assert logic.target == pytest.approx((0.5, 0.1, 0.5))


def test_active_z_movement():
    logic = make_active()

    logic.update_pose((1.0, 2.0, 3.1), now_s=1.1)

    assert logic.target == pytest.approx((0.5, 0.0, 0.6))


def test_active_multi_axis_movement():
    logic = make_active()

    logic.update_pose((1.1, 1.8, 3.3), now_s=1.1)

    assert logic.target == pytest.approx((0.6, -0.2, 0.8))


def test_active_zero_displacement():
    logic = make_active()

    logic.update_pose(ANCHOR_POSE, now_s=1.1)

    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_release_freezes_target():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    frozen = logic.target

    logic.update_deadman(False, now_s=1.2)

    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(frozen)


def test_movement_while_released_is_ignored():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    logic.update_deadman(False, now_s=1.2)
    frozen = logic.target

    logic.update_pose((9.0, 9.0, 9.0), now_s=1.3)

    assert logic.target == pytest.approx(frozen)


def test_repress_reanchors_without_jump():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    logic.update_deadman(False, now_s=1.2)
    frozen = logic.target
    logic.update_pose((5.0, 6.0, 7.0), now_s=1.3)

    logic.update_deadman(True, now_s=1.31)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(frozen)

    logic.update_pose((5.1, 6.0, 7.0), now_s=1.4)
    assert logic.target == pytest.approx(
        (frozen[0] + 0.1, frozen[1], frozen[2])
    )


def test_repeated_true_does_not_reset_anchor():
    logic = make_active()
    original_anchor = logic._anchor_pose
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    target_before_repeat = logic.target

    logic.update_deadman(True, now_s=1.15)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(target_before_repeat)
    assert logic._anchor_pose == original_anchor


def test_repeated_false_is_harmless():
    logic = QuestRightTargetLogic()

    logic.update_deadman(False, now_s=1.0)
    logic.update_deadman(False, now_s=1.1)

    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(INITIAL_TARGET)
    assert logic.activation_pending is False


def test_timeout_at_exact_boundary_does_not_trigger():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)

    logic.check_timeout(now_s=0.2)

    assert logic.state is BridgeState.ACTIVE


def test_timeout_above_boundary_requires_rearm():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)

    logic.check_timeout(now_s=0.200001)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pose_recovery_while_held_stays_rearm_required():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)
    logic.check_timeout(now_s=0.21)

    logic.update_pose((4.0, 5.0, 6.0), now_s=0.22)
    logic.update_deadman(True, now_s=0.23)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_release_from_rearm_required_returns_inactive():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)
    logic.check_timeout(now_s=0.21)

    logic.update_deadman(False, now_s=0.22)

    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_repress_after_rearm_required_activates():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)
    logic.check_timeout(now_s=0.21)
    logic.update_deadman(False, now_s=0.22)
    logic.update_pose((4.0, 5.0, 6.0), now_s=0.23)

    logic.update_deadman(True, now_s=0.24)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_press_before_first_pose_enters_pending_without_jump():
    logic = QuestRightTargetLogic()

    logic.update_deadman(True, now_s=0.0)

    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is True
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_first_pose_after_pending_press_anchors_without_jump():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose(ANCHOR_POSE, now_s=0.1)

    assert logic.state is BridgeState.ACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pending_activation_times_out_and_locks():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.check_timeout(now_s=0.2)
    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is True

    logic.check_timeout(now_s=0.200001)
    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.activation_pending is False


def test_stale_pose_cannot_be_used_as_anchor():
    logic = QuestRightTargetLogic()
    logic.update_pose((9.0, 9.0, 9.0), now_s=0.0)

    logic.update_deadman(True, now_s=0.3)

    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is True
    assert logic.target == pytest.approx(INITIAL_TARGET)

    logic.update_pose(ANCHOR_POSE, now_s=0.4)

    assert logic.state is BridgeState.ACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pending_release_cancels_activation():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_deadman(False, now_s=0.1)
    logic.update_pose(ANCHOR_POSE, now_s=0.15)

    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pending_repeated_true_does_not_extend_deadline():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_deadman(True, now_s=0.19)
    logic.check_timeout(now_s=0.200001)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.activation_pending is False


def test_pending_pose_at_exact_boundary_activates():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose(ANCHOR_POSE, now_s=0.2)

    assert logic.state is BridgeState.ACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pending_late_pose_itself_locks_without_jump():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose((9.0, 9.0, 9.0), now_s=0.200001)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_non_monotonic_time_is_ignored():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    stable_target = logic.target
    stable_anchor = logic._anchor_pose

    logic.update_pose((9.0, 9.0, 9.0), now_s=1.05)
    logic.check_timeout(now_s=1.0)
    logic.update_deadman(True, now_s=1.02)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(stable_target)
    assert logic._anchor_pose == stable_anchor

    logic.update_deadman(False, now_s=0.9)
    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(stable_target)

    logic.update_deadman(True, now_s=1.0)
    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(stable_target)


def test_repeated_identical_pose_does_not_change_target():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    stable_target = logic.target

    logic.update_pose((1.1, 2.0, 3.0), now_s=1.15)
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.19)

    assert logic.target == pytest.approx(stable_target)


def test_pose_age_at_exact_boundary_is_fresh_for_press():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)

    logic.update_deadman(True, now_s=0.2)

    assert logic.state is BridgeState.ACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_late_pose_itself_locks_before_target_update():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose((9.0, 9.0, 9.0), now_s=0.21)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_non_default_scale_is_applied_per_axis():
    logic = QuestRightTargetLogic(scale=2.0)
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose((1.1, 1.9, 3.2), now_s=0.1)

    assert logic.target == pytest.approx((0.7, -0.2, 0.9))


def test_custom_initial_target_is_preserved_on_activation():
    logic = QuestRightTargetLogic(initial_target=(1.0, -1.0, 2.0))
    logic.update_pose(ANCHOR_POSE, now_s=0.0)

    logic.update_deadman(True, now_s=0.1)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx((1.0, -1.0, 2.0))
~~~

说明：test_repeated_true_does_not_reset_anchor 与时间回退测试读取 _anchor_pose，是为了验证“不能重锚”这一内部安全不变量；生产 adapter 不使用该私有字段。

- [ ] **Step 3: 运行测试并确认红灯原因正确**

~~~bash
cd /home/lh/quest2ros2_ws/src/Quest2ROS2
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest \
  -p no:cacheprovider -q \
  test/test_quest_right_target_logic.py
~~~

Expected: FAIL during collection with ModuleNotFoundError for q2r2_bringup.quest_right_target_logic。失败必须来自尚未创建的模块，而不是 Conda、路径或其他环境错误。

- [ ] **Step 4: 编写最小纯逻辑实现**

创建 q2r2_bringup/quest_right_target_logic.py，按以下实现锁定行为：

~~~python
from enum import Enum, auto


Position = tuple[float, float, float]


class BridgeState(Enum):
    INACTIVE = auto()
    ACTIVE = auto()
    REARM_REQUIRED = auto()


class QuestRightTargetLogic:
    def __init__(
        self,
        initial_target: Position = (0.5, 0.0, 0.5),
        scale: float = 1.0,
        timeout_s: float = 0.2,
    ) -> None:
        self._target = self._as_position(initial_target)
        self._scale = float(scale)
        self._timeout_s = float(timeout_s)
        self._state = BridgeState.INACTIVE

        self._latest_pose = None
        self._last_pose_time = None
        self._anchor_pose = None
        self._anchor_target = None

        self._deadman_pressed = False
        self._activation_pending = False
        self._pending_since = None
        self._last_accepted_time = float("-inf")

    @staticmethod
    def _as_position(position: Position) -> Position:
        x, y, z = position
        return (float(x), float(y), float(z))

    def _accept_time(self, now_s: float):
        now = float(now_s)
        if now < self._last_accepted_time:
            return None
        self._last_accepted_time = now
        return now

    def _age(self, now_s: float, reference_s: float) -> float:
        return max(0.0, now_s - reference_s)

    def _activate(self, pose: Position) -> None:
        self._anchor_pose = pose
        self._anchor_target = self._target
        self._activation_pending = False
        self._pending_since = None
        self._state = BridgeState.ACTIVE

    def _enter_rearm_required(self) -> None:
        self._state = BridgeState.REARM_REQUIRED
        self._activation_pending = False
        self._pending_since = None
        self._anchor_pose = None
        self._anchor_target = None

    def update_pose(self, position: Position, now_s: float) -> None:
        now = self._accept_time(now_s)
        if now is None:
            return

        pose = self._as_position(position)
        previous_pose_time = self._last_pose_time
        self._latest_pose = pose
        self._last_pose_time = now

        if self._state is BridgeState.ACTIVE:
            if (
                previous_pose_time is not None
                and self._age(now, previous_pose_time) > self._timeout_s
            ):
                self._enter_rearm_required()
                return

            self._target = tuple(
                self._anchor_target[index]
                + self._scale * (pose[index] - self._anchor_pose[index])
                for index in range(3)
            )
            return

        if self._activation_pending and self._deadman_pressed:
            if self._age(now, self._pending_since) > self._timeout_s:
                self._enter_rearm_required()
                return
            self._activate(pose)

    def update_deadman(self, pressed: bool, now_s: float) -> None:
        pressed = bool(pressed)
        if not pressed:
            now = float(now_s)
            if now > self._last_accepted_time:
                self._last_accepted_time = now
            self._deadman_pressed = False
            self._state = BridgeState.INACTIVE
            self._activation_pending = False
            self._pending_since = None
            self._anchor_pose = None
            self._anchor_target = None
            return

        now = self._accept_time(now_s)
        if now is None:
            return

        if self._deadman_pressed:
            return

        self._deadman_pressed = True

        if self._state is BridgeState.REARM_REQUIRED:
            return

        pose_is_fresh = (
            self._latest_pose is not None
            and self._last_pose_time is not None
            and self._age(now, self._last_pose_time) <= self._timeout_s
        )

        if pose_is_fresh:
            self._activate(self._latest_pose)
            return

        self._state = BridgeState.INACTIVE
        self._activation_pending = True
        self._pending_since = now

    def check_timeout(self, now_s: float) -> None:
        now = self._accept_time(now_s)
        if now is None:
            return

        if (
            self._state is BridgeState.ACTIVE
            and self._last_pose_time is not None
            and self._age(now, self._last_pose_time) > self._timeout_s
        ):
            self._enter_rearm_required()
            return

        if (
            self._activation_pending
            and self._pending_since is not None
            and self._age(now, self._pending_since) > self._timeout_s
        ):
            self._enter_rearm_required()

    @property
    def target(self) -> Position:
        return self._target

    @property
    def state(self) -> BridgeState:
        return self._state

    @property
    def activation_pending(self) -> bool:
        return self._activation_pending
~~~

- [ ] **Step 5: 运行 Task 1 测试并确认全绿**

~~~bash
cd /home/lh/quest2ros2_ws/src/Quest2ROS2
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest \
  -p no:cacheprovider -q \
  test/test_quest_right_target_logic.py
~~~

Expected: 32 passed，0 failed。

- [ ] **Step 6: 做 Task 1 范围与格式检查**

~~~bash
git diff --check -- \
  q2r2_bringup/quest_right_target_logic.py \
  test/test_quest_right_target_logic.py

git status --short
git diff -- \
  q2r2_bringup/quest_right_target_logic.py \
  test/test_quest_right_target_logic.py
~~~

Expected: Task 1 diff 只包含两个新文件；原有 dirty files 仍存在且未改变。

- [ ] **Step 7: 只提交 Task 1 文件**

~~~bash
git add -- \
  q2r2_bringup/quest_right_target_logic.py \
  test/test_quest_right_target_logic.py

git diff --cached --name-status
git commit -m "feat: add Quest right target state logic" -- \
  q2r2_bringup/quest_right_target_logic.py \
  test/test_quest_right_target_logic.py

git diff-tree --no-commit-id --name-only -r HEAD
~~~

Expected staged names 与 commit 文件列表均仅为上述两个文件。提交后 package.xml、ros2quest.py、.pyc 仍保持未暂存。

---

### Task 2: ROS 2 Adapter + Entry Point

**Files:**
- Create: q2r2_bringup/quest_right_target_bridge.py
- Create: test/test_quest_right_target_bridge.py
- Modify: setup.py

**Interfaces:**
- Consumes: Task 1 的 BridgeState 与 QuestRightTargetLogic API；geometry_msgs.msg.PoseStamped；visualization_msgs.msg.Marker；quest2ros.msg.OVR2ROSInputs。
- Produces: build_target_pose(target, stamp)、build_target_marker(target, stamp)、QuestRightTargetBridge、main(args=None)，以及 console script quest_right_target_bridge。

- [ ] **Step 1: source 系统 ROS 环境并确认 Python**

~~~bash
cd /home/lh/quest2ros2_ws/src/Quest2ROS2
conda deactivate 2>/dev/null || true
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
export PYTHONDONTWRITEBYTECODE=1

command -v python3
test "$(command -v python3)" = "/usr/bin/python3"
/usr/bin/python3 --version
~~~

Expected: command -v python3 输出 /usr/bin/python3；版本为 Python 3.10.x。

- [ ] **Step 2: 创建 adapter 失败测试**

创建 test/test_quest_right_target_bridge.py：

~~~python
import inspect
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest
from builtin_interfaces.msg import Time
from geometry_msgs.msg import PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.node import Node
from visualization_msgs.msg import Marker

from q2r2_bringup.quest_right_target_bridge import (
    INPUTS_TOPIC,
    MARKER_COLOR_RGBA,
    MARKER_ID,
    MARKER_NAMESPACE,
    MARKER_SCALE_M,
    POSE_TOPIC,
    TARGET_MARKER_TOPIC,
    TARGET_POSE_TOPIC,
    TIMER_PERIOD_S,
    WORLD_FRAME,
    QuestRightTargetBridge,
    build_target_marker,
    build_target_pose,
)


TARGET = (0.6, -0.2, 0.8)


def make_stamp() -> Time:
    return Time(sec=12, nanosec=345)


def test_topic_and_timer_constants_are_exact():
    assert POSE_TOPIC == "/q2r_right_hand_pose"
    assert INPUTS_TOPIC == "/q2r_right_hand_inputs"
    assert TARGET_POSE_TOPIC == "/quest_right_target_pose"
    assert TARGET_MARKER_TOPIC == "/quest_right_target_marker"
    assert TIMER_PERIOD_S == 0.02
    assert WORLD_FRAME == "world"


def test_build_target_pose_fields():
    stamp = make_stamp()

    message = build_target_pose(TARGET, stamp)

    assert message.header.frame_id == "world"
    assert message.header.stamp.sec == stamp.sec
    assert message.header.stamp.nanosec == stamp.nanosec
    assert message.pose.position.x == TARGET[0]
    assert message.pose.position.y == TARGET[1]
    assert message.pose.position.z == TARGET[2]
    assert message.pose.orientation.x == 0.0
    assert message.pose.orientation.y == 0.0
    assert message.pose.orientation.z == 0.0
    assert message.pose.orientation.w == 1.0


def test_build_target_marker_fields():
    stamp = make_stamp()

    marker = build_target_marker(TARGET, stamp)

    assert marker.header.frame_id == "world"
    assert marker.header.stamp.sec == stamp.sec
    assert marker.header.stamp.nanosec == stamp.nanosec
    assert marker.ns == MARKER_NAMESPACE == "quest_right_target"
    assert marker.id == MARKER_ID == 0
    assert marker.type == Marker.SPHERE
    assert marker.action == Marker.ADD
    assert marker.pose.position.x == TARGET[0]
    assert marker.pose.position.y == TARGET[1]
    assert marker.pose.position.z == TARGET[2]
    assert marker.pose.orientation.x == 0.0
    assert marker.pose.orientation.y == 0.0
    assert marker.pose.orientation.z == 0.0
    assert marker.pose.orientation.w == 1.0
    assert marker.scale.x == MARKER_SCALE_M == 0.06
    assert marker.scale.y == MARKER_SCALE_M
    assert marker.scale.z == MARKER_SCALE_M
    assert (
        marker.color.r,
        marker.color.g,
        marker.color.b,
        marker.color.a,
    ) == pytest.approx(MARKER_COLOR_RGBA)
    assert marker.lifetime.sec == 0
    assert marker.lifetime.nanosec == 0


def test_node_name_topics_types_and_timer_are_wired_exactly():
    with (
        patch.object(Node, "__init__", return_value=None) as node_init,
        patch.object(Node, "create_subscription") as create_subscription,
        patch.object(Node, "create_publisher") as create_publisher,
        patch.object(Node, "create_timer") as create_timer,
    ):
        bridge = QuestRightTargetBridge()

    node_init.assert_called_once_with("quest_right_target_bridge")
    assert create_subscription.call_count == 2
    assert create_subscription.call_args_list[0].args == (
        PoseStamped,
        POSE_TOPIC,
        bridge._pose_callback,
        10,
    )
    assert create_subscription.call_args_list[1].args == (
        OVR2ROSInputs,
        INPUTS_TOPIC,
        bridge._inputs_callback,
        10,
    )
    assert create_publisher.call_count == 2
    assert create_publisher.call_args_list[0].args == (
        PoseStamped,
        TARGET_POSE_TOPIC,
        10,
    )
    assert create_publisher.call_args_list[1].args == (
        Marker,
        TARGET_MARKER_TOPIC,
        10,
    )
    create_timer.assert_called_once_with(
        TIMER_PERIOD_S,
        bridge._timer_callback,
    )


def test_pose_callback_passes_only_xyz_and_monotonic_time():
    bridge = QuestRightTargetBridge.__new__(QuestRightTargetBridge)
    bridge._logic = Mock()
    message = PoseStamped()
    message.header.frame_id = "ignored"
    message.pose.position.x = 1.0
    message.pose.position.y = 2.0
    message.pose.position.z = 3.0
    message.pose.orientation.w = 0.25

    with patch(
        "q2r2_bringup.quest_right_target_bridge.time.monotonic",
        return_value=10.0,
    ):
        bridge._pose_callback(message)

    bridge._logic.update_pose.assert_called_once_with(
        (1.0, 2.0, 3.0),
        10.0,
    )
    source = inspect.getsource(QuestRightTargetBridge._pose_callback)
    assert "msg.header" not in source
    assert "orientation" not in source


def test_inputs_callback_passes_only_button_lower_and_monotonic_time():
    bridge = QuestRightTargetBridge.__new__(QuestRightTargetBridge)
    bridge._logic = Mock()
    message = OVR2ROSInputs()
    message.button_lower = True
    message.button_upper = True
    message.thumb_stick_horizontal = 0.75
    message.press_index = 1.0

    with patch(
        "q2r2_bringup.quest_right_target_bridge.time.monotonic",
        return_value=11.0,
    ):
        bridge._inputs_callback(message)

    bridge._logic.update_deadman.assert_called_once_with(True, 11.0)
    source = inspect.getsource(QuestRightTargetBridge._inputs_callback)
    assert "button_upper" not in source
    assert "thumb_stick" not in source
    assert "press_index" not in source
    assert "press_middle" not in source


def test_timer_checks_watchdog_and_continuously_publishes_same_target():
    bridge = QuestRightTargetBridge.__new__(QuestRightTargetBridge)
    bridge._logic = Mock()
    bridge._logic.target = TARGET
    bridge._target_pose_publisher = Mock()
    bridge._target_marker_publisher = Mock()
    stamp = make_stamp()
    clock = Mock()
    clock.now.return_value.to_msg.return_value = stamp

    with (
        patch.object(QuestRightTargetBridge, "get_clock", return_value=clock),
        patch(
            "q2r2_bringup.quest_right_target_bridge.time.monotonic",
            return_value=12.0,
        ),
    ):
        bridge._timer_callback()
        bridge._timer_callback()

    assert bridge._logic.check_timeout.call_args_list == [
        call(12.0),
        call(12.0),
    ]
    assert bridge._target_pose_publisher.publish.call_count == 2
    assert bridge._target_marker_publisher.publish.call_count == 2

    pose = bridge._target_pose_publisher.publish.call_args_list[0].args[0]
    marker = bridge._target_marker_publisher.publish.call_args_list[0].args[0]
    assert (pose.pose.position.x, pose.pose.position.y, pose.pose.position.z) == TARGET
    assert (
        marker.pose.position.x,
        marker.pose.position.y,
        marker.pose.position.z,
    ) == TARGET
    assert pose.header.stamp.sec == marker.header.stamp.sec == stamp.sec
    assert (
        pose.header.stamp.nanosec
        == marker.header.stamp.nanosec
        == stamp.nanosec
    )


def test_bridge_source_has_no_robot_control_interface():
    module_path = Path(inspect.getfile(QuestRightTargetBridge))
    source = module_path.read_text(encoding="utf-8")
    forbidden = (
        '"/left/',
        '"/right/',
        "rm_driver",
        "rm_control",
        "FollowJointTrajectory",
        "GripperCommand",
        "robot_arm_controller_base",
        "ActionClient",
        "rclpy.action",
        "control_msgs",
    )

    for token in forbidden:
        assert token not in source


def test_setup_entry_point_is_added_without_removing_existing_entries():
    setup_path = Path(__file__).resolve().parents[1] / "setup.py"
    source = setup_path.read_text(encoding="utf-8")

    expected_entries = (
        "ros2quest = q2r2_bringup.ros2quest:main",
        "SimulationInput = q2r2_bringup.SimulationInput:main",
        "CheckTCPconnection = q2r2_bringup.CheckTCPconnection:main",
        "left_arm_controller = q2r2_bringup.left_arm_controller:main",
        "right_arm_controller = q2r2_bringup.right_arm_controller:main",
        (
            "quest_right_target_bridge = "
            "q2r2_bringup.quest_right_target_bridge:main"
        ),
    )

    for entry in expected_entries:
        assert entry in source
~~~

- [ ] **Step 3: 运行 adapter 测试并确认红灯原因正确**

~~~bash
cd /home/lh/quest2ros2_ws/src/Quest2ROS2
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest \
  -p no:cacheprovider -q \
  test/test_quest_right_target_bridge.py
~~~

Expected: FAIL during collection with ModuleNotFoundError for q2r2_bringup.quest_right_target_bridge。不得通过启动真实 Quest 或 ROS 节点来绕过该失败。

- [ ] **Step 4: 创建 ROS 2 adapter**

创建 q2r2_bringup/quest_right_target_bridge.py：

~~~python
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.node import Node
from visualization_msgs.msg import Marker

from .quest_right_target_logic import QuestRightTargetLogic


POSE_TOPIC = "/q2r_right_hand_pose"
INPUTS_TOPIC = "/q2r_right_hand_inputs"
TARGET_POSE_TOPIC = "/quest_right_target_pose"
TARGET_MARKER_TOPIC = "/quest_right_target_marker"

WORLD_FRAME = "world"
TIMER_PERIOD_S = 0.02

MARKER_NAMESPACE = "quest_right_target"
MARKER_ID = 0
MARKER_SCALE_M = 0.06
MARKER_COLOR_RGBA = (0.1, 1.0, 0.2, 0.9)


def build_target_pose(
    target: tuple[float, float, float],
    stamp,
) -> PoseStamped:
    message = PoseStamped()
    message.header.frame_id = WORLD_FRAME
    message.header.stamp = stamp
    message.pose.position.x = target[0]
    message.pose.position.y = target[1]
    message.pose.position.z = target[2]
    message.pose.orientation.x = 0.0
    message.pose.orientation.y = 0.0
    message.pose.orientation.z = 0.0
    message.pose.orientation.w = 1.0
    return message


def build_target_marker(
    target: tuple[float, float, float],
    stamp,
) -> Marker:
    marker = Marker()
    marker.header.frame_id = WORLD_FRAME
    marker.header.stamp = stamp
    marker.ns = MARKER_NAMESPACE
    marker.id = MARKER_ID
    marker.type = Marker.SPHERE
    marker.action = Marker.ADD

    marker.pose.position.x = target[0]
    marker.pose.position.y = target[1]
    marker.pose.position.z = target[2]
    marker.pose.orientation.x = 0.0
    marker.pose.orientation.y = 0.0
    marker.pose.orientation.z = 0.0
    marker.pose.orientation.w = 1.0

    marker.scale.x = MARKER_SCALE_M
    marker.scale.y = MARKER_SCALE_M
    marker.scale.z = MARKER_SCALE_M

    marker.color.r = MARKER_COLOR_RGBA[0]
    marker.color.g = MARKER_COLOR_RGBA[1]
    marker.color.b = MARKER_COLOR_RGBA[2]
    marker.color.a = MARKER_COLOR_RGBA[3]
    return marker


class QuestRightTargetBridge(Node):
    def __init__(self) -> None:
        super().__init__("quest_right_target_bridge")
        self._logic = QuestRightTargetLogic()

        self._pose_subscription = self.create_subscription(
            PoseStamped,
            POSE_TOPIC,
            self._pose_callback,
            10,
        )
        self._inputs_subscription = self.create_subscription(
            OVR2ROSInputs,
            INPUTS_TOPIC,
            self._inputs_callback,
            10,
        )

        self._target_pose_publisher = self.create_publisher(
            PoseStamped,
            TARGET_POSE_TOPIC,
            10,
        )
        self._target_marker_publisher = self.create_publisher(
            Marker,
            TARGET_MARKER_TOPIC,
            10,
        )

        self._timer = self.create_timer(
            TIMER_PERIOD_S,
            self._timer_callback,
        )

    def _pose_callback(self, msg: PoseStamped) -> None:
        position = (
            msg.pose.position.x,
            msg.pose.position.y,
            msg.pose.position.z,
        )
        self._logic.update_pose(position, time.monotonic())

    def _inputs_callback(self, msg: OVR2ROSInputs) -> None:
        self._logic.update_deadman(
            bool(msg.button_lower),
            time.monotonic(),
        )

    def _timer_callback(self) -> None:
        self._logic.check_timeout(time.monotonic())
        stamp = self.get_clock().now().to_msg()
        target = self._logic.target

        self._target_pose_publisher.publish(
            build_target_pose(target, stamp)
        )
        self._target_marker_publisher.publish(
            build_target_marker(target, stamp)
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = QuestRightTargetBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
~~~

该文件不得增加其他 topic、service、action、TF 或机器人依赖。Marker lifetime 保持默认零值，表示 forever。

- [ ] **Step 5: 只在 setup.py 的 console_scripts 列表增加新入口**

保持所有已有 entry point，最终列表为：

~~~python
entry_points={
    'console_scripts': [
        'ros2quest = q2r2_bringup.ros2quest:main',
        'SimulationInput = q2r2_bringup.SimulationInput:main',
        'CheckTCPconnection = q2r2_bringup.CheckTCPconnection:main',
        'left_arm_controller = q2r2_bringup.left_arm_controller:main',
        'right_arm_controller = q2r2_bringup.right_arm_controller:main',
        'quest_right_target_bridge = q2r2_bringup.quest_right_target_bridge:main',
    ],
},
~~~

不得改动 setup.py 的其他字段和已有 entry point 顺序。

- [ ] **Step 6: 运行 Task 2 测试并确认全绿**

~~~bash
cd /home/lh/quest2ros2_ws/src/Quest2ROS2
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest \
  -p no:cacheprovider -q \
  test/test_quest_right_target_bridge.py
~~~

Expected: 9 passed，0 failed。

- [ ] **Step 7: 运行 Task 1 + Task 2 全套单元测试**

~~~bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest \
  -p no:cacheprovider -q \
  test/test_quest_right_target_logic.py \
  test/test_quest_right_target_bridge.py
~~~

Expected: 41 passed，0 failed。

- [ ] **Step 8: 检查 adapter 安全边界与 Task 2 diff**

~~~bash
git diff --check -- \
  q2r2_bringup/quest_right_target_bridge.py \
  test/test_quest_right_target_bridge.py \
  setup.py

git diff -- \
  q2r2_bringup/quest_right_target_bridge.py \
  test/test_quest_right_target_bridge.py \
  setup.py

git status --short
~~~

逐行确认：

- 只有两个允许的输入 topic 和两个允许的输出 topic；
- 没有 ActionClient；
- 没有机器人控制 import；
- setup.py 所有原有 entry point 均保留；
- package.xml、ros2quest.py 和 .pyc 仍未暂存且未被清理。

- [ ] **Step 9: 只提交 Task 2 文件**

~~~bash
git add -- \
  q2r2_bringup/quest_right_target_bridge.py \
  test/test_quest_right_target_bridge.py \
  setup.py

git diff --cached --name-status
git commit -m "feat: add Quest right target ROS bridge" -- \
  q2r2_bringup/quest_right_target_bridge.py \
  test/test_quest_right_target_bridge.py \
  setup.py

git diff-tree --no-commit-id --name-only -r HEAD
~~~

Expected staged names 与 commit 文件列表均仅为上述三个文件，不包含 package.xml、ros2quest.py 或任何 .pyc。

---

### Task 3: Build + Isolated ROS Smoke Verification

**Files:**
- Create: none
- Modify: none
- Test: Task 1 与 Task 2 的两个 pytest 文件

**Interfaces:**
- Consumes: Task 1/2 commits、现有 quest2ros install overlay、ROS 2 Humble。
- Produces: 单元测试、限定包构建、无输入发布、SimulationInput、真实 Quest/RViz 的验证证据；不产生产品代码 commit。

- [ ] **Step 1: 建立明确且隔离的系统 Python/ROS 环境**

~~~bash
conda deactivate 2>/dev/null || true
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
export PYTHONDONTWRITEBYTECODE=1

command -v python3
test "$(command -v python3)" = "/usr/bin/python3"
/usr/bin/python3 --version
head -n 1 /usr/bin/colcon
printenv ROS_DOMAIN_ID
~~~

Expected:

~~~text
/usr/bin/python3
Python 3.10.x
#!/usr/bin/python3
42
~~~

如果 command -v python3 不是 /usr/bin/python3，停止，不运行 rclpy、pytest 或 colcon，先修正 shell 环境。

- [ ] **Step 2: 审计 commits 与保留的 dirty working tree**

~~~bash
cd /home/lh/quest2ros2_ws/src/Quest2ROS2
git log -4 --oneline --decorate
git status --short
git show --name-status --oneline HEAD
git show --name-status --oneline HEAD^
~~~

Expected:

- Task 1 commit 只含 quest_right_target_logic.py 与 test_quest_right_target_logic.py；
- Task 2 commit 只含 quest_right_target_bridge.py、test_quest_right_target_bridge.py 与 setup.py；
- 原有 package.xml、ros2quest.py 和 .pyc dirty 状态仍存在；
- 没有 quest2ros、ros_tcp_communication 或 /home/lh/robot 内容进入 commits。

- [ ] **Step 3: 从 workspace root 运行完整单元测试**

~~~bash
cd /home/lh/quest2ros2_ws

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest \
  -p no:cacheprovider -q \
  src/Quest2ROS2/test/test_quest_right_target_logic.py \
  src/Quest2ROS2/test/test_quest_right_target_bridge.py
~~~

Expected: 41 passed，0 failed。

- [ ] **Step 4: 只构建 q2r2_bringup**

~~~bash
cd /home/lh/quest2ros2_ws

ros2 pkg prefix quest2ros
ros2 interface show quest2ros/msg/OVR2ROSInputs

/usr/bin/colcon build \
  --symlink-install \
  --packages-select q2r2_bringup
~~~

Expected: 两条依赖检查先成功，随后 q2r2_bringup 构建成功。若 quest2ros prefix 或 interface 检查失败，立即停止并报告，不得转而构建、修改或重新创建 quest2ros，也不得构建 /home/lh/robot。

- [ ] **Step 5: 验证已安装 executable**

~~~bash
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42

ros2 pkg executables q2r2_bringup \
  | grep quest_right_target_bridge
~~~

Expected:

~~~text
q2r2_bringup quest_right_target_bridge
~~~

- [ ] **Step 6: 无输入安全 smoke test**

确保真实 Quest、SimulationInput 和所有机器人 controller 均未运行。先只读检查输入 topic：

~~~bash
ros2 topic info /q2r_right_hand_pose -v
ros2 topic info /q2r_right_hand_inputs -v
~~~

Expected: 两个输入 topic 均无 publisher。若存在 publisher，停止本步骤并由操作者确认其归属；不得终止不属于本任务的进程。随后 Terminal A 只启动 bridge：

~~~bash
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
ros2 run q2r2_bringup quest_right_target_bridge
~~~

Terminal B：

~~~bash
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42

ros2 node info /quest_right_target_bridge
ros2 topic info /quest_right_target_pose -v
ros2 topic info /quest_right_target_marker -v
ros2 topic echo /quest_right_target_pose --once
~~~

Expected:

- node 只订阅 /q2r_right_hand_pose 与 /q2r_right_hand_inputs；
- node 只发布两个目标 topic，另有 ROS 自动创建的参数/日志接口；
- 两个目标 topic 的唯一产品 publisher 为 /quest_right_target_bridge；
- Pose frame_id 为 world；
- position 为 x=0.5、y=0.0、z=0.5；
- orientation 为 x=0.0、y=0.0、z=0.0、w=1.0；
- timestamp 非零且来自当前 ROS clock；
- 不存在 RM65 endpoint。

观察 5 至 10 秒发布频率并用 Ctrl-C 结束命令：

~~~bash
ros2 topic hz /quest_right_target_pose
~~~

Expected: 稳定在约 50 Hz。随后在 Terminal A 用 Ctrl-C 停止 bridge。

- [ ] **Step 7: SimulationInput 隔离 smoke test**

先使用 ros2 topic info -v 确认真实 Quest 暂时断开、两个输入 topic 没有其他 publisher。若存在未知 publisher，停止并协调，不得 kill 未归属节点。不得修改 SimulationInput.py。

Terminal A 启动 bridge：

~~~bash
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
ros2 run q2r2_bringup quest_right_target_bridge
~~~

Terminal B 只启动右手 teleop 模拟输入：

~~~bash
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
ros2 run q2r2_bringup SimulationInput \
  --ros-args \
  -p side:=right \
  -p mode:=teleop
~~~

Terminal C：

~~~bash
source /opt/ros/humble/setup.bash
source /home/lh/quest2ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
ros2 topic echo /quest_right_target_pose
~~~

Expected:

- SimulationInput 每周期先发布 button_lower=True，再发布 Pose；
- bridge 首次 press 进入 pending，随后首帧 Pose 无跳变锚定并进入 ACTIVE；
- target x/y 随 30 Hz 圆周输入连续变化；
- target z 保持约 0.5；
- bridge 输出继续约 50 Hz；
- 未创建任何机器人控制 endpoint。

该 smoke test 不验证 release、re-anchor 或 watchdog rearm；这些语义由 Task 1 单元测试提供证据。

依次用 Ctrl-C 停止 echo、SimulationInput 和 bridge。然后执行：

~~~bash
ros2 node list \
  | grep -E 'quest_right_target_bridge|quest_simulator_node' || true
~~~

Expected: 无输出。

- [ ] **Step 8: 真实 Quest + RViz 人工验证**

本步骤只在操作者明确准备好真实 Quest 且确认未加载 RM65 后执行，不在实施计划编写阶段执行。

1. 只启动现有 ros_tcp_endpoint。
2. Quest 连接 192.168.5.55:10000。
3. 启动 quest_right_target_bridge。
4. 启动 RViz2。
5. 设置 Fixed Frame=world。
6. Add -> Marker，Topic=/quest_right_target_marker。
7. 可选 Add -> Pose，Topic=/quest_right_target_pose。
8. 验证初始 marker=(0.5, 0.0, 0.5)。
9. 验证未按 button_lower 时目标不动。
10. 按住 button_lower，验证目标跟随相对位移。
11. 松开，验证目标立即冻结。
12. 松开期间移动手柄，再次按下，验证无跳变。
13. 分别向现实前/后、左/右、上/下移动并记录 Quest dx/dy/dz 的方向和符号。
14. 只记录标定结果；本阶段不修改 axis mapping。

整个过程不得 source /home/lh/robot/install/setup.bash，不得启动 RM driver、rm_control、MoveIt、CuRobo、left_arm_controller、right_arm_controller 或夹爪控制。

- [ ] **Step 9: 最终验证与停止条件**

~~~bash
cd /home/lh/quest2ros2_ws/src/Quest2ROS2

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest \
  -p no:cacheprovider -q \
  test/test_quest_right_target_logic.py \
  test/test_quest_right_target_bridge.py

git diff --check
git status --short --branch
~~~

Expected:

- 41 tests passed；
- 没有格式错误；
- 原有 dirty files 仍存在；
- Task 1/2 实现文件已经分别提交；
- Task 3 不创建文件、不创建空 commit；
- 所有启动的 bridge、SimulationInput、ros_tcp_endpoint 和 RViz 进程均已由操作者停止；
- 没有启动、连接或控制 RM65。

## Implementation Completion Gate

只有以下证据同时满足，才可以声明实现完成：

- Task 1 首次测试确实因缺少模块失败，随后 32 个纯逻辑测试通过；
- Task 2 首次测试确实因缺少 adapter 模块失败，随后 9 个 adapter 测试通过；
- 全套 41 个测试从仓库目录和 workspace root 均通过；
- q2r2_bringup 限定构建成功；
- 安装后的 quest_right_target_bridge executable 可见；
- 无输入时持续发布初始 Pose/Marker，Pose 约 50 Hz；
- SimulationInput smoke test 证明 press-before-pose 路径无跳变；
- 静态安全测试与 ROS graph 检查均未发现 RM65 控制接口；
- git show 证明两个实现 commits 均未带入原有 dirty files；
- 真实 Quest/RViz 人工验证结果被记录，轴标定留给下一阶段。
