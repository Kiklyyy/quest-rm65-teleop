# Interface Contract

## 双臂 Quest 一键启动契约

`dual_quest_teleop.launch.py` 是左右 RM65、左右 Quest adapter 和可选右 O7
灵巧手的统一父 launch。它复用已安装的
`rm_driver/launch/rm_65_dual_driver.launch.py` 与
`rm_control/launch/rm_65_dual_control.launch.py`，不复制左右机械臂 IP、UDP
端口或 Action 参数。硬件模式下形成 `/left/rm_driver`、`/right/rm_driver`、
`/left/rm_control`、`/right/rm_control` 四个现有身份；子 launch 的
`start_rm_driver` 固定传入 `false`，禁止重复启动单臂 driver。

统一入口参数：

```text
mode:=dry_run|hardware                 # 默认 dry_run
motion_profile:=safe|normal            # 默认 safe；双臂不允许 fast
start_drivers:=true|false               # 仅 hardware 生效，默认 true
start_controls:=true|false              # 仅 hardware 生效，默认 true
start_tcp:=true|false                   # 默认 true；只由右子 launch 启动一次
start_bridges:=true|false               # 默认 true
start_status:=true|false                # 默认 true
start_linkerhand:=true|false            # 默认 false
linkerhand_connect_only:=true|false      # 默认 false
use_right_rviz:=true|false              # 默认 false
use_left_rviz:=true|false               # 默认 false
```

`mode:=dry_run` 时父 launch 不启动任何 RM driver 或 `rm_control`，两个 adapter
继续使用各自 dry-run 配置。`mode:=hardware` 且启动开关为 true 时，父 launch
启动上述双臂 driver/control，然后并行启动左右遥操作链。右子 launch 拥有唯一
ROS TCP endpoint；左子 launch 始终收到 `start_tcp:=false`。两侧 target bridge、
adapter、monitor 和 RViz 使用既有独立节点名、topic 与参数。

父 launch 在创建任何子进程前验证左右硬件参数和共享 profile，并检查拟启动的
driver、control、adapter 是否已有运行实例，以及 TCP 10000 端口是否空闲。
检查失败时整套启动直接报错，不会先启动部分节点；若要复用外部 driver/control，
分别使用 `start_drivers:=false` / `start_controls:=false`。

右 O7 保持显式 opt-in。`start_linkerhand:=true` 才启动 `/right_linkerhand`；
`linkerhand_connect_only:=true` 还必须同时满足 `mode:=hardware` 和
`start_linkerhand:=true`。已观察到的“RM driver 与第二 API2/工具 RS485 连接共存时，
右 Grip 首次可能向旧位姿跳动”问题尚未关闭，因此不得把 O7 自动启动改为默认 true，
也不得把一键启动的软件验证写成双臂+灵巧手真机验收。

## 右手 LinkerHand L7 Quest toggle（软件完成，集成真机待测）

独立节点 `/right_linkerhand` 只订阅 `/q2r_right_hand_inputs`
（`quest2ros/msg/OVR2ROSInputs`）的 `press_index`。`>=0.60` 为按下，
`<=0.40` 为松开，中间区间保持上一扳机状态。每次有效松开→按下上升沿切换一次：
第一次为 CLOSED `[73,0,0,0,0,0,156]`，第二次为 OPEN
`[73,0,255,255,255,255,156]`，之后交替。七轴顺序由现场 SDK
`O7_JOINT_KEYS` 确认为 `Thumb_Pitch, Thumb_Yaw, Index_Pitch,
Middle_Pitch, Ring_Pitch, Little_Pitch, Thumb_Roll`。节点启动逻辑状态为
OPEN，但 `target=null`、不自动发 OPEN；连接后先读 `get_state()` 和
`get_fault()`。数据 stale 或 NaN/Inf 时保持手位、不切换并撤销按压资格；
恢复后须先有有效松开样本，下一次按下才能切换。此节点不读取 Grip、Home、
摇杆或 Quest Pose，也不改变右 RM65 adapter 的状态机。

`right_quest_teleop.launch.py` 的 `start_linkerhand:=false|true` 默认
`false`。显式 `true` 且 `mode:=dry_run` 不导入或连接 SDK；`mode:=hardware`
由该节点独占实例化现场
`LinkerHandApi(hand_type="right", hand_joint="L7", modbus="RML")`。
诊断参数 `connect_only:=true` 只允许与 `dry_run:=false`、
`hardware_write_enabled:=true` 同用：仍建立 SDK 连接、轮询
`get_state()`/`get_fault()`，但无论 Quest 输入如何都禁止 `finger_move()`。
右臂 launch 提供 `linkerhand_connect_only:=true` 传入该参数；单独运行
`right_linkerhand_node` 可在不启动 arm adapter 的情况下诊断。
SDK 固定路径为 `/home/lh/quest2ros2_ws/linkerhand/linker_hand_python_sdk`，
使用现场 RealMan API2 工具端 RS485 适配。硬件启动会配置右臂工具端电压/Modbus；
同一时刻只能有一个灵巧手 SDK 控制进程。右 RM driver 仍由原启动链管理。

`/right/linkerhand/status` 为 `std_msgs/msg/String` JSON：`stamp`、
`trigger_value`、`trigger_pressed`、`trigger_armed`、
`hand_toggle_state`（OPEN/CLOSED）、`target`、`actual`、`fault_codes`、
`communication_ok`、`input_fresh`、`dry_run`、`state`、`error`、
`invalid_input_count`、`connect_only`。只连接状态为 `CONNECT_ONLY`，
`target=null`；启动未按压时 `target=null`；dry-run 的 `actual`、
`fault_codes` 为 null、`communication_ok=false`。输入 stale 不产生新命令；
故障码或通信异常阻止硬件写入，日志限流。`get_force()`、`get_current()`
不用于本版反馈或闭环。

现场操作者已人工确认 SDK 连接、真实反馈和手指张合方向。本版 toggle
软件尚未做双 RM65 + 右 LinkerHand 同场真机验收。

本文件区分“当前代码已经存在的接口”和“计划/尚未完全验收的接口”。不要把计划接口写成当前能力。

## 当前已经存在

### 输入

| Topic | 类型 | 当前使用字段 |
|---|---|---|
| `/q2r_right_hand_pose` | `geometry_msgs/msg/PoseStamped` | `pose.position.{x,y,z}` 供 bridge 使用；`pose.orientation.{x,y,z,w}` 由 adapter 直接使用 |
| `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | `press_middle` teleop deadman; A=`button_lower` selects `quest_right_second`; B=`button_upper` selects `quest_right_last` |
| `/q2r_left_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | X=`button_lower` selects right-arm `quest_right_first`; the left adapter independently consumes the same message for left teleop/Home |

输入 Pose 的 header、frame 和 stamp 不作为机器人坐标依据。现有
`quest_right_target_bridge` 仍只处理 position；orientation 不经过该 bridge，而由
`rm65_teleop_adapter` 直接读取原始 Quest Pose。当前仍不使用摇杆、
`press_index` is used only by the separate right L7 node when explicitly started.
Right X/A/B joint presets have no Cartesian authority and use only the guarded
right `FollowJointTrajectory` path.

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
- `button_lower` 不再参与右 RM65 teleop deadman；`press_index` 只供独立右手 L7 节点使用，arm adapter 仍不读取它；
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
| `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | `press_middle` teleop deadman; A/B select right joint presets; independent Inputs watchdog |
| `/q2r_left_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | X selects the first right joint preset; separate freshness watchdog while a right preset is requested |
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

右臂硬件 `max_anchor_angle_rad` 设为 `4.71238898038469`（270°）；左臂仍为
`1.5707963267948966`（90°）。当前锚点相对角使用四元数最短角，数学范围
只有 0–180°，因此右臂的 270° 阈值不会触发 `anchor_angle_violation`，
也不表示系统能追踪完整的 270° 累积转动。连续样本的 45° 跳变检查、
角速度与每周期角步长限制仍生效；本次不改变平移、Home 或 watchdog。

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

## Right-arm X/A/B joint preset interface (software validated; hardware pending)

- X is `/q2r_left_hand_inputs.button_lower`, A is
  `/q2r_right_hand_inputs.button_lower`, and B is
  `/q2r_right_hand_inputs.button_upper`. They select `quest_right_first`,
  `quest_right_second`, and `quest_right_last`, respectively. The old single
  right B/Home target is superseded; left Y/Home is unchanged.
- All three targets are six joint degrees in `hardware.yaml`, ordered
  `joint1..joint6`. `home_hold_seconds=1.5`, right presets use
  `quest_joint_preset_speed_deg_s=50.0`, matching the current left Y/Home
  `home_speed_deg_s=50.0`; joint-name
  reordering and the right Action
  `/right/rm_group_controller/follow_joint_trajectory` are shared.
- A request starts only from `ARMED` with Grip released, both Quest input streams
  fresh, fresh/valid joints, an available Action server and exclusive right
  movep/movej/stop ownership. Exactly one button must remain held for 1.5 s.
  Simultaneous buttons, a held-at-startup button, or switching buttons without
  a complete release cannot create a goal.
- The Action goal retains four synchronized smoothstep points. No Cartesian
  `movep_canfd_cmd` is emitted while the joint action is active. Selected-button
  release, either Quest input watchdog, joint/pose invalidity, path loss or
  control-period loss requests cancel plus stop and waits for a terminal result.
- Status adds `home_inputs_fresh`, `joint_presets_enabled`,
  `joint_preset_selection`, `joint_preset_active`, and
  `joint_preset_x_inputs_age_ms`. Isolated Action tests validate the exact X/A/B
  final joints and existing cancel/watchdog behavior. No real RM65 preset
  motion has been run for these new targets.


## Shared RM65 adapter endpoint contract (left hardware validation phase)

The same `rm65_teleop_adapter_node` executable and safety state machine serve
one configured arm per process. The right launch retains its existing endpoints;
the left launch uses a distinct node identity and separate dry-run and hardware
configurations. Hardware writes are enabled only by explicit `mode:=hardware`.

| Parameter | Right instance | Left instance |
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
| `home_action_name` | `/right/rm_group_controller/follow_joint_trajectory` | `/left/rm_group_controller/follow_joint_trajectory` (hardware only) |
| `status_topic` | `/right/rm65_teleop/status` | `/left/rm65_teleop/status` |
| `preview_topic` | `/right/rm65_teleop/preview_target_pose` | `/left/rm65_teleop/preview_target_pose` |
| `clear_fault_service` | `/right/rm65_teleop/clear_fault` | `/left/rm65_teleop/clear_fault` |
| `preview_frame_id` | `right_rm65_base` | `left_rm65_base` (preview label only) |
| `mapping` | `[0,0,1, -1,0,0, 0,-1,0]` | `[0,0,-1, -1,0,0, 0,1,0]` |

All safety-critical node identities are complete absolute names. Hardware
command ownership must match the configured adapter, driver, and controller
identities exactly; any extra publisher/subscriber or a cross-arm identity
fails closed. A dry-run instance creates preview/status only: no `movep`,
`move_stop`, or real Home Action client. Left dry-run keeps
`hardware_write_enabled=false`, `mapping_verified=false`, and
`home_enabled=false`; explicit left hardware mode uses `true` for all three.
Right Home settings and right safety gates remain unchanged.

The same guarded joint-trajectory implementation serves both arms through
per-arm configuration. Right X/A/B select right-arm presets; left physical Y
remains the only left Home button. Right X is read from the left-controller
message but has no authority over the left adapter. All joint requests require
Grip released and a continuous 1.5 s hold while `ARMED`, then send the existing
four-point smoothstep
`FollowJointTrajectory` at the configured joint speed (currently 50 deg/s
for left Y and right X/A/B). During `HOMING`,
Cartesian commands are suppressed. Releasing the Home button requests Action
cancel plus physical stop; the adapter stays `HOMING` until a terminal result.
Success or acknowledged cancel enters `REARM_REQUIRED`, and a fresh Grip press
after released inputs is required to resume teleop. The shared RealMan
compatibility rule reports terminal vendor success as `CANCELED` only when a
local cancel was already pending. Left hardware uses joint order
`[joint1,joint2,joint3,joint4,joint5,joint6]` and the independent operator-set
Home target `[-90.52991560598026,-7.43359734865227,-62.41522144150158,
-3.5143370089334374,-37.08400247904573,99.21228312734117]` degrees.
Left dry-run creates no real Home Action client. On 2026-09-26, the first
left-only hardware return used four trajectory points and reached the configured
target within 0.023° on all joints. A second mid-motion Y release produced
vendor terminal `SUCCEEDED` but adapter `CANCELED`, and the arm stopped before
Home. Joint 3 advanced another 6.44° after Y release before stabilizing, so
the physical stopping margin still requires acceptance review. The established
Quest input dropout issue remains open; this session did not change timeouts.

The versioned `hardware.yaml` is the single official hardware config for both
adapter nodes. Its `/**` block defines the identical gates, watchdogs, timing,
limits and workspace once. The `rm65_teleop_adapter` and
`left_rm65_teleop_adapter` blocks contain only their separate node/topic
identities, mappings, frames and Home targets. The left launch defaults to
`dry_run`; hardware mode with `motion_profile:=normal` loads the same four
motion values as the right `normal.yaml`:
`translation_scale=1.0`, `max_velocity_mps=0.20`, `max_step_m=0.00050`, and
`max_anchor_distance_m=1.0`. The right profile file is unchanged. The left
hardware workspace is `[-1,-1,0]` to `[1,1,1.5]` m, matching the right
config. This is an **operator-authorized temporary left hardware test
workspace**, not yet a final collision/workcell envelope. The 200 ms Quest
pose/inputs/target, 100 ms robot/joint feedback watchdogs, fault/rearm behavior,
Grip deadman and physical stop remain active. Left `rm_control` is started
only for an explicit Home hardware session. Left gripper and X remain unbound;
Y has only its same-arm Home binding. Only one
left adapter may publish `movep` and `move_stop` to the single left driver;
for a Home session `/left/rm_control` alone publishes `movej`, with the left
driver as its only subscriber, and the adapter alone owns the left Home Action
client. The adapter publishes stop to both left driver and left `rm_control`.

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
2026-09-25; moving-hardware evidence currently covers left +Z and -Y direction
signs. Quest +Z to left -X and all orientation axes await moving-hardware
validation. The first `normal` hardware session again confirmed physical-left
`+Z` motion, but later gestures were unlabeled and cannot complete XYZ or
orientation acceptance. Physical left
Grip maps to `press_middle`, index to `press_index`, X to `button_lower`,
and Y to `button_upper`. X has no left-arm Home, gripper, or Cartesian binding,
but the right adapter consumes it for `quest_right_first`; Y is left Home only
in explicit hardware mode. Recurring Quest Pose/Inputs dropouts remain
an open issue; they do not change the watchdog settings for this test session.

### Historical left hardware gates (2026-09-25)

Earlier left-only tests used fresh-P0 narrow workspaces and a temporary
`left_test` profile. These gates are retired by the official left hardware
config above. The first moving-hardware test confirmed Quest `+Y` → RM `+Z`
sign at small displacement. The subsequent ±70 mm XYZ session measured Quest
`+Y=56.216 mm` → stable robot `+Z=56.074 mm`, then Quest `+X=70.496 mm` →
stable robot `−Y=66.812 mm`. Test B exceeded the old 70 mm radial anchor cap;
the adapter latched `FAULT/anchor_distance_violation` before Grip release, and
the robot moved another 11.429 mm after that stop request. Test C was not run.
The complete history, trace analysis and stop timing are in
`docs/progress/left-arm-teleop.md`.
