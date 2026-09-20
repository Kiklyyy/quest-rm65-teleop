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

具体 RM65 command topic/action、控制频率和停止接口仍待 B 同学基于实际驱动确认，当前不得猜测。
