# Interface Contract

本文件区分“当前代码已经存在的接口”和“计划/尚未完全验收的接口”。不要把计划接口写成当前能力。

## 当前已经存在

### 输入

| Topic | 类型 | 当前使用字段 |
|---|---|---|
| `/q2r_right_hand_pose` | `geometry_msgs/msg/PoseStamped` | `pose.position.{x,y,z}` 供 bridge 使用；`pose.orientation.{x,y,z,w}` 由 adapter 直接使用 |
| `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | `press_middle` teleop deadman; `button_upper` Home; `button_lower` reserved |

输入 Pose 的 header、frame 和 stamp 不作为机器人坐标依据。现有
`quest_right_target_bridge` 仍只处理 position；orientation 不经过该 bridge，而由
`rm65_teleop_adapter` 直接读取原始 Quest Pose。当前仍不使用摇杆、
`press_index` remains unused; physical A=`button_lower` is reserved without motion authority; physical B=`button_upper` controls Home.

### 输出

| Topic | 类型 |
|---|---|
| `/quest_right_target_pose` | `geometry_msgs/msg/PoseStamped` |
| `/quest_right_target_marker` | `visualization_msgs/msg/Marker` |

输出行为：

- 仅右手、仅平移；
- 比例 1:1，第一版轴映射为 identity；
- 初始 position 为 `(0.5, 0.0, 0.5)`；
- orientation 固定为 `(0, 0, 0, 1)`，只作为既有平移 target 的占位值，不承担机器人姿态控制；
- `frame_id = "world"`；
- `press_middle >= 0.60` 后按相对位移跟随，`press_middle <= 0.40` 时立即冻结，再次达到按下阈值时以当前位置重新锚定；
- `0.40 < press_middle < 0.60` 时保持上一 deadman 状态；非有限值按 release 处理；
- ACTIVE 下 Pose 接收间隔严格大于 0.2 秒进入 `REARM_REQUIRED`；必须先 release，再 press 才能重新授权；
- Pose 与 Marker 由 50 Hz timer 持续发布；
- 输出 stamp 使用当前 ROS node clock，不沿用 Quest 输入 header。

### 已完成的真实 Quest 物理方向验收

现场使用真实 Quest 手柄逐轴移动并观察 `/quest_right_target_pose`：

| 真实手柄运动 | Virtual target 变化 | Quest/virtual world 物理含义 |
|---|---|---|
| 向前 | X 增加 | `+X = 前` |
| 向右 | Y 减少 | `+Y = 左` |
| 向上 | Z 增加 | `+Z = 上` |

真实 Quest + RViz 也已验证未按 deadman 时冻结、按住时跟随、松开后冻结，以及松开期间移动后重新按下不跳变。当前 bridge 的 identity mapping 无需为 Quest 自身修改。

## Unified launch 参数契约

统一入口 `right_quest_teleop.launch.py` 提供：

```text
mode:=dry_run|hardware
motion_profile:=safe|normal|fast
```

`motion_profile` 默认值为 `safe`。非法值必须拒绝启动，不得静默回退到
`safe`。

hardware 模式按以下顺序加载 ROS 2 参数文件：

```text
hardware.yaml
+ motion_profiles/<motion_profile>.yaml
```

后加载的 motion profile 只能覆盖：

- `translation_scale`
- `max_velocity_mps`
- `max_step_m`
- `max_anchor_distance_m`

hardware gate、mapping、watchdog、workspace、控制周期、follow、stop 行为和
topic 名称均不属于 motion profile。dry-run 始终只加载 `dry_run.yaml`；指定
`motion_profile:=normal` 或 `fast` 不会启用硬件写入路径。launch 日志会显示
当前 `mode` 和 `motion_profile`。

## 关键安全含义

> **冻结的目标仍会由 50 Hz timer 持续刷新 timestamp。不能仅根据 `/quest_right_target_pose` 的新鲜度判断 Quest 在线、deadman 正在按下或用户允许机器人运动。**

其他限制：

- A 侧 bridge 的 watchdog 只监测 Pose；B 侧 adapter 因此独立监测 Inputs、原始 Quest Pose、虚拟 target 和机器人反馈。
- `world` 只是虚拟观察参考系，不是 RM65 base frame。
- 原始 Quest Pose header 不是机器人坐标依据。
- 约 50 Hz 是虚拟目标发布频率，不是 RM65 控制周期。

## A/B 最小接口约定

### 第一阶段显式 enable

第一阶段直接使用 `/q2r_right_hand_inputs` 的 `press_middle` 作为显式 deadman：

- `press_middle >= 0.60` 将语义状态置为 pressed，`press_middle <= 0.40` 将其置为 released，中间迟滞区保持上一状态；
- `press_middle` 为 NaN/Inf 时安全置为 released；
- `button_lower` 不再参与右 RM65 teleop deadman，`press_index` 当前仍未使用；
- B 侧独立检查 Inputs 接收时间、原始 Quest Pose、虚拟 target 和机器人反馈；
- 任一路超时、非有限数据、工作空间违规或突跳都会退出 ACTIVE；
- 数据恢复不得自动继续，必须先看到语义 deadman released，再由下一次 released → pressed 重新采集双锚点；
- B 侧不得用 `/quest_right_target_pose` 持续刷新的 header stamp 代替原始输入 watchdog。

未来如 A 侧增加聚合后的 `/quest_right_teleop_enable`，可作为可选接口另行对齐；它不是第一阶段 adapter 的前置条件。

### B 侧第一阶段输入

| Topic | 类型 | 用途 |
|---|---|---|
| `/quest_right_target_pose` | `geometry_msgs/msg/PoseStamped` | A 侧映射后的虚拟右手目标，只使用相对平移 |
| `/q2r_right_hand_pose` | `geometry_msgs/msg/PoseStamped` | 独立 Quest Pose 接收 watchdog；`pose.orientation` 是机器人相对姿态控制的直接输入 |
| `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | `press_middle` teleop deadman, `button_upper` Home, independent Inputs watchdog |
| `/right/joint_states` | `sensor_msgs/msg/JointState` | Home joint positions reordered by name, with independent freshness/validity checks |
| `/right/rm_driver/udp_arm_position` | `geometry_msgs/msg/Pose` | 机器人真实末端 Pose、锚点和反馈 watchdog |

### B 侧输出（已实现）

| Topic | 类型 | 条件 |
|---|---|---|
| `/right/rm65_teleop/preview_target_pose` | `geometry_msgs/msg/PoseStamped` | dry-run 和真机模式均可发布 |
| `/right/rm65_teleop/status` | `std_msgs/msg/String` | 发布状态、freshness、fault 和硬件写入锁状态 |
| `/right/rm_driver/movep_canfd_cmd` | `rm_ros_interfaces/msg/Cartepos` | 仅非 dry-run、硬件写入显式启用、现场映射确认且状态为 ACTIVE |
| `/right/rm_driver/move_stop_cmd` | `std_msgs/msg/Empty` | 真机 ACTIVE 退出或 watchdog/fault 时 |
| `/right/rm_group_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | Hardware Home only while `HOMING`; cancel terminal result required before teleop rearm |

dry-run 默认值：

```text
dry_run=true
hardware_write_enabled=false
```

硬件模式必须同时显式配置 `dry_run=false`、`hardware_write_enabled=true`、`mapping_verified=true`。任一安全门不满足时，adapter 拒绝启动或不创建真实运动命令发布路径。

硬件命令图按节点身份和端点类型检查，额外端点或重复端点均不通过。`command_path_ready` 表示 Cartesian 路径可用：`/rm65_teleop_adapter` 是唯一 `movep_canfd_cmd` 发布者，`/right/rm_driver` 是唯一订阅者；adapter 是唯一 `move_stop_cmd` 发布者。仅 driver 运行时，stop 订阅者只能是 driver；right-only `rm_control` 运行时，stop 订阅者必须恰为 driver 和 `/right/rm_control`。

`home_command_path_ready` 还要求：`/right/rm_control` 是唯一 `movej_canfd_cmd` 发布者，driver 是唯一订阅者；Action status 只有该 controller 发布，FollowJointTrajectory server 可用，且图中恰有一个 `/right/rm_control` 节点。Home 启动和执行期间同时要求 Cartesian 与 Home 路径可用。`home_movej_topic` 参数默认为 `/right/rm_driver/movej_canfd_cmd`，仅用于检查命令所有权；adapter 自身不发布 movej。dry-run 不建立真实运动发布端点，也不创建真实 Home Action client。

## 坐标与锚定

A 侧现场验证：

```text
Quest world: +X=前，+Y=左，+Z=上
```

右 RM65 base 物理方向确认：`+X=上，+Y=后，+Z=右`。B 侧使用：

```text
[rm_x]   [ 0  0  1] [quest_x]
[rm_y] = [-1  0  0] [quest_y]
[rm_z]   [ 0 -1  0] [quest_z]

Quest 向前 (+X) -> RM65 -Y
Quest 向右 (-Y) -> RM65 +Z
Quest 向上 (+Z) -> RM65 +X
```

enable 上升沿同时采集平移与姿态双锚点：

```text
quest_anchor = 当前 /quest_right_target_pose.position
robot_anchor = 当前 /right/rm_driver/udp_arm_position
q_Q0 = 当前 /q2r_right_hand_pose.pose.orientation
q_R0 = 当前 /right/rm_driver/udp_arm_position.orientation
```

四元数使用 ROS 存储顺序 `(x, y, z, w)`、Hamilton product 和主动列向量旋转。
所有合法输入先正规化；`q` 与 `-q` 通过 hemisphere 统一视作同一姿态，核心计算不做
Euler 角累积。world/base-frame 相对旋转约定与实现顺序固定为：

```text
Delta R_Q = R_Q * R_Q0^T
Delta R_Q_scaled = shortest-axis-angle-scale(Delta R_Q, rotation_scale)
Delta R_RM = M * Delta R_Q_scaled * M^T
R_desired = Delta R_RM * R_R0
```

`R_desired` 的左乘是有意的：Quest world 中的相对旋转经 `M` 共轭后成为
RM base/world-frame 相对旋转，再左乘机器人姿态锚点。不得把这个约定与
body-frame 右乘混用。矩阵保持与已验证平移物理轴映射相同：

```text
M = [ 0  0  1
     -1  0  0
      0 -1  0 ]

Quest +X forward -> RM65 -Y
Quest +Y left    -> RM65 -Z
Quest +Z up      -> RM65 +X
```

同一控制周期原子组成一个 Pose：

```text
p_robot_desired = p_robot_anchor
              + R_mapping * translation_scale
              * (p_quest_now - p_quest_anchor)
q_robot_desired = quaternion(R_desired)
```

要求：

- 不把 Quest `world` 中的绝对 `(0.5, 0.0, 0.5)` 当作机器人坐标；
- 每次重新授权都重新采集平移与姿态锚点，恢复时不得跳变；
- translation mapping、translation scale、motion profiles、workspace 和全部既有
  watchdog 保持不变；
- 夹爪、左臂和双臂仍不在当前范围。

姿态命令从上一条已提交命令走 shortest-path SLERP。每周期允许角度为：

```text
allowed_angle = min(max_angular_step_rad,
                    max_angular_velocity_rad_s * dt)
```

从 Quest 姿态锚点的相对角超过 `max_anchor_angle_rad`、连续合法 Quest
sample 的 shortest angular distance 超过
`unexpected_orientation_jump_rad`，或收到无效/非有限/近零范数四元数时，
ACTIVE 状态通过既有 stop/fault/rearm 状态机退出，且该周期不提交平移或旋转命令。
deadman release 的优先级高于同周期 orientation event；正常松手保持既有
release stop 和 release → press rearm 语义。

## 已确认的右 RM65 runtime 接口

控制机环境实测：ROS 2 Humble，`ROS_DOMAIN_ID=42`，右臂地址 `169.254.128.19:8080`，UDP 回传 `169.254.128.100:8090`。

| Topic | 类型 | 实测/源码结论 |
|---|---|---|
| `/right/joint_states` | `sensor_msgs/msg/JointState` | 6 关节，实测约 197 Hz |
| `/right/rm_driver/udp_arm_position` | `geometry_msgs/msg/Pose` | 实测约 197 Hz |
| `/right/rm_driver/get_current_arm_state_cmd` | `std_msgs/msg/Empty` | 只读主动查询 |
| `/right/rm_driver/get_current_arm_state_result` | `rm_ros_interfaces/msg/Armstate` | 实测 `err=0`、`dof=6` |
| `/right/rm_driver/movep_canfd_cmd` | `rm_ros_interfaces/msg/Cartepos` | 连续 Cartesian CANFD 透传 |
| `/right/rm_driver/move_stop_cmd` | `std_msgs/msg/Empty` | 调用 `rm_set_arm_stop()`，轨迹急停，不是控制柜 emergency stop |

driver 必须以 `/right` namespace 和右臂参数单独启动。启动 driver 本身只连接 SDK、配置 UDP 和创建 ROS 接口，不包含自动运动。

## 2026-09-20 真机微动与停止证据

- 低跟随首次 `+Z 3 mm`：实际 `+3.007 mm`，普通 stop 返回 `true`；
- 低跟随运动中 stop：停止时仍落后最后指令约 `0.5 mm`，随后继续到最后一个目标点附近；
- 高跟随小位移 stop：停止后余量约 `0.063 mm`；
- 临时 Python 高跟随发送器最大发送间隔实测 `17.5 ms`，不满足高跟随周期不超过 `10 ms` 的要求；
- 正式 adapter 使用 C++ 并监测实际控制周期；
- high-follow 隔离联调观察到 `13.48 ms` 和 `21.87 ms` 调度间隔，均被 `10 ms` guard 正确停止；
- 现场授权后硬件配置改用低跟随模式，仍保持 200 Hz 名义 timer，并以 `50 ms` 作为严重控制卡顿 fault；
- 隔离 ROS 联调实测 Quest `+X 10 mm` 生成 RM65 `-Y 2.0 mm` 目标，输入断流发布 3 次 stop，数据恢复不自动 ACTIVE，release→press 后才重新锚定。

## 2026-09-20 首次端到端真机联调

现场操作者确认：真实 Quest 右手柄已经通过当前 A+B 链路驱动右 RM65 产生实际运动，说明“Quest → ROS2 → target bridge → RM65 adapter → 右 RM65”平移链路已首次端到端打通。

这只证明首次真机运动链路成立；尚不等于旋转、左臂、夹爪、所有断流场景、最终停止余量或完整安全验收已完成。

## Right-arm Home interface (hardware validated)

- Physical A=`button_lower` is reserved. Physical B=`button_upper` is selected by `home_button_field: upper`. Grip remains the `press_middle >=0.60` / `<=0.40` teleop deadman; a new Grip press recaptures Quest/RM anchors.
- `hardware.yaml` has `home_enabled: true`; `dry_run.yaml` has `home_enabled: false`. A separate dry-run node graph check found no real Home action client. Isolated synthetic testing uses only `/test/home/*` topics/action and starts no RM driver.
- Operator-confirmed 2026-09-24 right-arm Home target in degrees, ordered `joint1` through `joint6`: `[68.3241063822369, -8.489398369548377, 60.14265142722264, 31.52005176840807, 51.634258495569824, -144.10081659391062]`. The previous temporary target `[-95.605, 4.406, -80.034, -22.695, -48.462, 97.570]` is retired. `home_hold_seconds: 1.5`; `home_speed_deg_s: 15.0`. Joint target/names, hold, and speed are startup parameters. JointState is reordered by name; missing/duplicate names, length mismatch, NaN, or Inf block Home.
- Home starts only from `ARMED`, with Grip released, B held continuously for 1.5 s, fresh/valid inputs and joints, an available action server, and an exclusive command/stop path. The hardware Action goal has four synchronized points at fractions 0, 1/3, 2/3, and 1 of a smoothstep path, each with six positions, velocities, accelerations, and `time_from_start`. The first point uses current joint feedback and the last retains the configured Home target. RealMan `rm_control` applies a zero-end-velocity cubic spline to goals with more than three points; duration is at least 1.5 × farthest joint angular distance / `home_speed_deg_s` (minimum 0.1 s), so the ideal spline peak remains at or below 15 deg/s for the default speed.
- `HOMING` permits only this joint action and emits no `/right/rm_driver/movep_canfd_cmd`. B release, input/joint watchdog, invalid feedback, or exclusive-path/control-period failure requests cancel+stop; `HOMING` persists until the action terminal result. Success or acknowledged cancel -> `REARM_REQUIRED`, followed by B release and Grip release-to-press. Rejection or abort -> `FAULT`.
- `/right/rm65_teleop/status` retains `state`, `deadman_pressed`, `command_path_ready`, and `reason`; adds `quest_pose_age_ms`, `inputs_age_ms`, `robot_age_ms`, `joint_state_age_ms`, `rearm_count`, `watchdog_count`, `home_button_pressed`, `home_hold_progress`, and `home_action_state`. The read-only monitor displays `JOINTS=OK|LOST` and concise `HOME` state.
- Complete automated result after new Home target: 206 tests, 0 errors, 0 failures, 0 skipped. Synthetic result: 5 test-action goals, 4 cancels, 1 success, 0 Cartesian hardware commands. Subsequent operator-confirmed real tests validated multiple four-point Home returns from away-from-Home postures (about 5–7 s), physical stop on mid-motion B release, and terminal `home_action_state=CANCELED`. The RealMan controller can report successful completion after a stop; `HomeActionClient` maps that terminal success to `CANCELED` only when a local cancel was already pending. The final sampled adapter state was `ARMED` with Grip and B released, both command paths ready, and no automatic transition to `ACTIVE`. Quest pose and inputs still have occasional simultaneous >200 ms gaps (previous maximum about 343 ms), causing watchdog/rearm; input stability remains open.


## Shared RM65 adapter endpoint contract (left dry-run phase)

The same `rm65_teleop_adapter_node` executable and safety state machine serve
one configured arm per process. The right launch retains its existing endpoints;
the left launch uses a distinct node identity and dry-run configuration. No
hardware write is authorized for the left arm in this phase.

| Parameter | Right instance | Left dry-run instance |
|---|---|---|
| `expected_adapter_node` | `/rm65_teleop_adapter` | `/left_rm65_teleop_adapter` |
| `expected_driver_node` | `/right/rm_driver` | `/left/rm_driver` |
| `expected_control_node` | `/right/rm_control` | `/left/rm_control` |
| `quest_pose_topic` | `/q2r_right_hand_pose` | `/q2r_left_hand_pose` |
| `inputs_topic` | `/q2r_right_hand_inputs` | `/q2r_left_hand_inputs` |
| `target_topic` | `/quest_right_target_pose` | `/quest_left_target_pose` |
| `robot_pose_topic` | `/right/rm_driver/udp_arm_position` | `/left/rm_driver/udp_arm_position` |
| `joint_state_topic` | `/right/joint_states` | `/left/joint_states` |
| `command_topic` | `/right/rm_driver/movep_canfd_cmd` | `/left/rm_driver/movep_canfd_cmd` |
| `home_movej_topic` | `/right/rm_driver/movej_canfd_cmd` | `/left/rm_driver/movej_canfd_cmd` |
| `stop_topic` | `/right/rm_driver/move_stop_cmd` | `/left/rm_driver/move_stop_cmd` |
| `home_action_name` | `/right/rm_group_controller/follow_joint_trajectory` | unset; Home disabled |
| `status_topic` | `/right/rm65_teleop/status` | `/left/rm65_teleop/status` |
| `preview_topic` | `/right/rm65_teleop/preview_target_pose` | `/left/rm65_teleop/preview_target_pose` |
| `clear_fault_service` | `/right/rm65_teleop/clear_fault` | `/left/rm65_teleop/clear_fault` |
| `preview_frame_id` | `right_rm65_base` | `left_rm65_base` (preview label only) |
| `mapping` | `[0,0,1, -1,0,0, 0,-1,0]` | `[0,0,-1, -1,0,0, 0,1,0]` |

All safety-critical node identities are complete absolute names. Hardware
command ownership must match the configured adapter, driver, and controller
identities exactly; any extra publisher/subscriber or a cross-arm identity
fails closed. A dry-run instance creates preview/status only: no `movep`,
`move_stop`, or real Home Action client. Left `hardware_write_enabled=false`,
`mapping_verified=false`, and `home_enabled=false` remain mandatory until a
separate hardware acceptance stage. Right Home settings and right safety gates
remain unchanged.

The Quest target bridge is shared through parameters for hand pose/inputs,
target pose/marker, `world` frame, and marker namespace. It publishes a
Quest-world relative target; RM base mapping belongs only in the adapter.
For the left instance these topics are `/q2r_left_hand_pose`,
`/q2r_left_hand_inputs`, `/quest_left_target_pose`, and
`/quest_left_target_marker`.

Operator-confirmed physical axes: Quest world `+X=forward`, `+Y=left`,
`+Z=up`; left RM65 base `+X=down`, `+Y=back`, `+Z=left`. The mathematically
derived left mapping is `dx=-Quest_dz`, `dy=-Quest_dx`, `dz=Quest_dy`, with
`M_left=[[0,0,-1],[-1,0,0],[0,1,0]]`, `M M^T=I`, and `det(M)=+1`.
Orientation uses the existing world/base-frame convention:
`DeltaR_Q=R_Q R_Q0^T`, `DeltaR_L=M_left DeltaR_Q M_left^T`, and
`R_desired=DeltaR_L R_L0`. Real Quest plus real left robot-anchor dry-run
preview passed the three XYZ signs and a small quaternion comparison on
2026-09-25; moving-hardware evidence currently covers only the left +Z
direction sign. Physical left
Grip maps to `press_middle`, index to `press_index`, X to `button_lower`,
and Y to `button_upper`. X/Y have no left Home, gripper, or motion binding.
Left Home button/pose and general absolute workspace remain pending. Recurring
Quest Pose/Inputs dropouts ended the initial dry-run preflight at NO-GO.

### Left first Cartesian movement gate (2026-09-25)

The onsite operator has separately authorized one left-only Cartesian
microtest: Quest left-hand physical left (`+Y`) to left RM base `+Z`
(robot physical left), with about 50 mm requested robot TCP travel. This
authorization accepts the known Quest input interruption risk for this one
test; the existing 200 ms Pose/Inputs watchdogs and stop/rearm behavior are
unchanged. It does not authorize other axes, wrist rotation, Home, face-button
actions, or dual-arm operation.

The left launch defaults to dry-run. Hardware mode requires an explicit
session-specific config file with a fresh robot TCP anchor and a narrow
absolute workspace; left hardware accepts only `motion_profile:=safe` or the
explicit test-only `motion_profile:=left_test`. Left Home remains disabled, and no `rm_control` or Home
Action client is present. The Cartesian command topic is
`/left/rm_driver/movep_canfd_cmd`; the adapter must be its sole publisher,
and the left driver its sole subscriber. The adapter must be the sole
`/left/rm_driver/move_stop_cmd` publisher, with the driver its sole subscriber.
The left movej topic must have no publisher.

The prepared one-session workspace used a fresh TCP `P0`: X and Y each within
5 mm of P0, and Z from P0 − 5 mm to P0 + 50 mm. Translation scale,
Cartesian velocity and step cap are the existing safe values (0.2,
0.005 m/s, 0.00005 m). `max_anchor_distance_m` measures the **desired robot
target** distance from the captured robot anchor, before rate limiting;
the previous 0.03 m cap cannot reach +50 mm. A minimal 0.051 m cap covers
the narrow box corner while the absolute workspace still limits the target.
`rotation_scale=0` is rejected by the current adapter validator, so this
test retains its existing orientation mapping and requires the operator to
keep the wrist approximately fixed. Real hardware orientation response is
outside this test's acceptance claim.

The first prepared session on 2026-09-25 stopped **before Grip or robot
movement** because raw Quest input stopped for 236.648 s and the Ubuntu SSH
observation link became unreliable. A subsequent fresh-P0 retest produced one
real left Cartesian movement: Quest left-hand `+Y` drove left RM base `+Z`.
The measured post-release TCP delta was `(+3.420, +0.515, +4.176) mm` in
left-base `(X,Y,Z)`; peak `+Z` was `+5.562 mm`. Thus only the **+Z direction
sign** has moving-hardware evidence. The operator's gesture also changed
Quest Z and produced material left-base X motion, so pure single-axis tracking,
the 50 mm target, the other axes and orientation remain unvalidated. The
temporary session config does not establish a reusable left hardware workspace.

### Left XYZ Cartesian test profile (test-only)

`left_test` is an **explicit, left-hardware-validation-only** profile. It is
never the launch default or automatically selected, and right launch keeps
its separate `safe|normal|fast` allowlist and unchanged profile files. Left
dry-run still loads only `left_dry_run.yaml`. Left hardware starts from an
explicit fresh-P0 session config; choosing `left_test` overlays only these
four values for `/left_rm65_teleop_adapter`:

| Parameter | `left_test` |
|---|---:|
| `translation_scale` | `1.0` |
| `max_velocity_mps` | `0.03` |
| `max_step_m` | `0.00015` |
| `max_anchor_distance_m` | `0.070` |

The session config must still pass the existing left endpoint, hardware gate,
Home-disabled, mapping, watchdog and session-specific absolute workspace checks. The
profile may not override any of those fields. For each fresh session robot
anchor P0, the temporary absolute workspace is a local Cartesian cube:
each left-base axis from P0−70 mm to P0+70 mm. The 70 mm anchor-distance
cap further bounds each Grip-anchored desired target radially. This envelope
is only for sequential, individually re-anchored XYZ translation validation;
it is not a general left-arm workspace. Quest +Y, +X and +Z displacements of
about 40–50 mm can respectively request left-base +Z, −Y and −X movement,
subject to the unchanged 200 ms input watchdogs, 100 ms robot watchdog and
Grip release-to-press rearm rules. At 200 Hz nominal, the 0.15 mm step cap
and 0.03 m/s velocity cap both correspond to at most 30 mm/s. This profile
does not authorize intentional orientation motion, Home, gripper or dual-arm
hardware use.
