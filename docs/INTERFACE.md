# Interface Contract

本文件区分“当前代码已经存在的接口”和“真机接入前必须新增、但目前尚不存在的接口”。不要把计划接口写成当前能力。

## 当前已经存在

### 输入

| Topic | 类型 | 当前使用字段 |
|---|---|---|
| `/q2r_right_hand_pose` | `geometry_msgs/msg/PoseStamped` | `pose.position.{x,y,z}` |
| `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | `button_lower` |

第一版忽略输入 Pose 的 header、frame、stamp 和 orientation，也不使用摇杆、扳机或 `button_upper`。

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
- `button_lower` 按住后按相对位移跟随，松开立即冻结，再按时以当前位置重新锚定；
- ACTIVE 下 Pose 接收间隔严格大于 0.2 秒进入 `REARM_REQUIRED`；必须先 release，再 press 才能重新授权；
- Pose 与 Marker 由 50 Hz timer 持续发布；
- 输出 stamp 使用当前 ROS node clock，不沿用 Quest 输入 header。

## 关键安全含义

> **冻结的目标仍会由 50 Hz timer 持续刷新 timestamp。不能仅根据 `/quest_right_target_pose` 的新鲜度判断 Quest 在线、deadman 正在按下或用户允许机器人运动。**

其他限制：

- 当前 watchdog 只监测 Pose 接收；`/q2r_right_hand_inputs` 断流尚无独立 watchdog。
- `world` 只是虚拟观察参考系，不是已经标定的 RM65 base frame。
- 原始 Quest Pose header 不是机器人坐标依据。
- 约 50 Hz 是虚拟目标发布频率，不是已经确认的 RM65 透传或控制周期。
- 当前输出没有连接任何 RM65 command topic/action。

## 真机联调前必须补齐，但当前尚不存在

### 显式 enable / validity

需要对接双方先在本文件确定一个明确的使能和有效性契约，至少能表达：

- deadman 当前是否有效；
- Pose 是否在接收 watchdog 内；
- Inputs 是否在独立 watchdog 内；
- 是否处于必须 release→press 的 rearm 锁定状态；
- 坐标映射和现场控制是否已由操作者授权。

在契约合并前，RM65 adapter 不得把“目标 Pose timestamp 很新”当作 enable。

### RM65 adapter

计划由独立包 `rm65_teleop_adapter` 实现，不修改 A 同学负责的 bridge/TCP 源码。最低安全要求：

- 默认关闭真机写入；
- 以机器人**当前实际位姿**作为启用时的目标锚点；
- 使用经真实 Quest + RViz 和机器人坐标系共同核对的变换；
- 不能直接执行虚拟初始值 `(0.5, 0.0, 0.5)` 或 identity 姿态；
- 接收端有自己的独立 watchdog、停止策略、限速/限位与命令源互斥；
- 一只机械臂同一时刻只有一套指定驱动和命令来源；
- 任何真实控制输出都需现场操作者明确授权。

以下为 B 侧基于实际 driver 源码与现场验证确认的接口；计划新增项仍明确标注为尚未实现。

## A/B 最小接口约定

### 第一阶段显式 enable（当前已存在）

第一阶段直接使用 `/q2r_right_hand_inputs` 的 `button_lower` 作为显式 deadman：

- `button_lower=true` 只表示用户当前按住 deadman；
- B 侧独立检查 Inputs 接收时间、原始 Quest Pose、虚拟 target 和机器人反馈；
- 任一路超时、非有限数据、工作空间违规或突跳都会退出 ACTIVE；
- 数据恢复不得自动继续，必须先看到 `button_lower=false`，再由下一次 `false → true` 重新采集双锚点；
- B 侧不得用 `/quest_right_target_pose` 持续刷新的 header stamp 代替原始输入 watchdog。

未来如 A 侧增加聚合后的 `/quest_right_teleop_enable`，可作为可选接口另行对齐；它不是第一阶段 dry-run 和独立 B 侧 rearm 状态机的前置条件。

### B 侧第一阶段输入

| Topic | 类型 | 用途 |
|---|---|---|
| `/quest_right_target_pose` | `geometry_msgs/msg/PoseStamped` | A 侧映射后的虚拟右手目标，只使用相对平移 |
| `/q2r_right_hand_pose` | `geometry_msgs/msg/PoseStamped` | 独立 Quest Pose 接收 watchdog |
| `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` | `button_lower` deadman 与独立 Inputs watchdog |
| `/right/rm_driver/udp_arm_position` | `geometry_msgs/msg/Pose` | 机器人真实末端 Pose、锚点和反馈 watchdog |

### B 侧输出（当前已实现）

| Topic | 类型 | 条件 |
|---|---|---|
| `/right/rm65_teleop/preview_target_pose` | `geometry_msgs/msg/PoseStamped` | dry-run 和真机模式均可发布 |
| `/right/rm65_teleop/status` | `std_msgs/msg/String` | 发布状态、freshness、fault 和硬件写入锁状态 |
| `/right/rm_driver/movep_canfd_cmd` | `rm_ros_interfaces/msg/Cartepos` | 仅非 dry-run、硬件写入显式启用、现场映射确认且状态为 ACTIVE |
| `/right/rm_driver/move_stop_cmd` | `std_msgs/msg/Empty` | 真机 ACTIVE 退出或 watchdog/fault 时 |

dry-run 默认值必须为：

```text
dry_run=true
hardware_write_enabled=false
```

硬件模式必须同时显式配置 `dry_run=false`、`hardware_write_enabled=true`、
`mapping_verified=true`。任一安全门不满足时，adapter 拒绝启动或不创建真实
运动命令发布路径。ACTIVE 还要求命令 topic 只有 adapter 一个 publisher，且
driver command/stop 各有且只有一个订阅端点。

## 坐标与锚定

A 侧已于 2026-09-20 完成真实 Quest + RViz 现场方向验证：

```text
Quest world: +X=前，+Y=左，+Z=上
```

右 RM65 base 物理方向已确认：`+X=上，+Y=后，+Z=右`。A 侧 bridge
保持 identity，B 侧使用以下已确认矩阵：

```text
[rm_x]   [ 0  0  1] [quest_x]
[rm_y] = [-1  0  0] [quest_y]
[rm_z]   [ 0 -1  0] [quest_z]

Quest 向前 (+X) -> RM65 -Y
Quest 向右 (-Y) -> RM65 +Z
Quest 向上 (+Z) -> RM65 +X
```

因此当前配置允许 `mapping_verified=true`；这不代表 Quest 真机验收已经完成。

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
- `R_mapping` 必须是现场验证的 Quest XYZ 到 RM65 base XYZ 的带符号轴映射；
- 第一阶段禁止 Quest orientation、夹爪、左臂和双臂控制；
- 每次重新授权都重新采集双锚点，恢复时不得跳变；
- 映射确认前 `mapping_verified=false`，禁止真机写入。

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
- 高跟随小位移 stop：停止后余量约 `0.063 mm`，明显小于低跟随；
- 临时 Python 高跟随发送器最大发送间隔实测 `17.5 ms`，不满足厂商高跟随周期不超过 `10 ms` 的要求。

因此：

- 正式 adapter 已使用 C++ 实现并监测实际控制周期；
- high-follow 隔离联调在当前主机负载下分别观察到 `13.48 ms` 和 `21.87 ms`
  调度间隔，均被 `10 ms` guard 正确停止；
- 现场操作者明确授权后，硬件配置改用已验证可工作的低跟随模式，仍保持
  200 Hz 名义 timer，并以 `50 ms` 作为严重控制卡顿 fault；
- 隔离 ROS 联调实测 Quest `+X 10 mm` 生成 RM65 `-Y 2.0 mm` 目标，输入断流
  发布 3 次 stop，数据恢复不自动 ACTIVE，release→press 后才重新锚定；
- 普通 stop 返回成功不等于零制动距离，workspace 和 watchdog 设计必须保留停止余量；
- `emergency_stop_cmd` 是独立的控制柜急停/恢复接口，不用于普通 deadman 或 watchdog。
- 真机 adapter 已启动并验证停留在 ARMED，但操作者未按下 deadman，故尚无
  Quest 驱动的实际位移证据，不能标记为最终验收完成。
