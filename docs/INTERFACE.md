# Interface Contract

本文件区分“当前代码已经存在的接口”和“计划/尚未完全验收的接口”。不要把计划接口写成当前能力。

## 当前已经存在

### 输入

| Topic | 类型 | 当前使用字段 |
|---|---|---|
| `/q2r_right_hand_pose` | `geometry_msgs/msg/PoseStamped` | `pose.position.{x,y,z}` |
| `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | `press_middle` |

第一版忽略输入 Pose 的 header、frame、stamp 和 orientation，也不使用摇杆、`press_index`、`button_lower` 或 `button_upper`。

### 输出

| Topic | 类型 |
|---|---|
| `/quest_right_target_pose` | `geometry_msgs/msg/PoseStamped` |
| `/quest_right_target_marker` | `visualization_msgs/msg/Marker` |

输出行为：

- 仅右手、仅平移；
- 比例 1:1，第一版轴映射为 identity；
- 初始 position 为 `(0.5, 0.0, 0.5)`；
- orientation 固定为 `(0, 0, 0, 1)`；
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
| `/q2r_right_hand_pose` | `geometry_msgs/msg/PoseStamped` | 独立 Quest Pose 接收 watchdog |
| `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | `press_middle` 迟滞 deadman 与独立 Inputs watchdog |
| `/right/rm_driver/udp_arm_position` | `geometry_msgs/msg/Pose` | 机器人真实末端 Pose、锚点和反馈 watchdog |

### B 侧输出（已实现）

| Topic | 类型 | 条件 |
|---|---|---|
| `/right/rm65_teleop/preview_target_pose` | `geometry_msgs/msg/PoseStamped` | dry-run 和真机模式均可发布 |
| `/right/rm65_teleop/status` | `std_msgs/msg/String` | 发布状态、freshness、fault 和硬件写入锁状态 |
| `/right/rm_driver/movep_canfd_cmd` | `rm_ros_interfaces/msg/Cartepos` | 仅非 dry-run、硬件写入显式启用、现场映射确认且状态为 ACTIVE |
| `/right/rm_driver/move_stop_cmd` | `std_msgs/msg/Empty` | 真机 ACTIVE 退出或 watchdog/fault 时 |

dry-run 默认值：

```text
dry_run=true
hardware_write_enabled=false
```

硬件模式必须同时显式配置 `dry_run=false`、`hardware_write_enabled=true`、`mapping_verified=true`。任一安全门不满足时，adapter 拒绝启动或不创建真实运动命令发布路径。ACTIVE 还要求命令 topic 只有 adapter 一个 publisher，且 driver command/stop 各有且只有一个订阅端点。

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

enable 上升沿同时采集：

```text
quest_anchor = 当前 /quest_right_target_pose.position
robot_anchor = 当前 /right/rm_driver/udp_arm_position
```

第一阶段命令：

```text
p_robot_cmd = p_robot_anchor
              + R_mapping * translation_scale
              * (p_quest_now - p_quest_anchor)

q_robot_cmd = q_robot_anchor
```

要求：

- 不把 Quest `world` 中的绝对 `(0.5, 0.0, 0.5)` 当作机器人坐标；
- 第一阶段禁止 Quest orientation、夹爪、左臂和双臂控制；
- 每次重新授权都重新采集双锚点，恢复时不得跳变。

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
