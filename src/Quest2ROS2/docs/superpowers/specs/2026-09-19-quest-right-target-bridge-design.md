# Quest 右手虚拟目标桥设计规范

- 日期：2026-09-19
- 状态：已批准设计
- 阶段：Stage 2 第一版
- 环境：Ubuntu 22.04、aarch64、ROS 2 Humble
- ROS 域：ROS_DOMAIN_ID=42

## 1. 项目目的

本设计定义独立 ROS 2 节点 quest_right_target_bridge，在 Quest 右手柄输入与未来机器人控制适配层之间建立稳定、安全、可测试的虚拟目标中间层。

当前阶段的数据流仅为：

~~~text
Quest
  -> ROS 2
  -> quest_right_target_bridge
  -> virtual Pose / Marker
  -> RViz
~~~

当前阶段只验证 Quest 右手柄到虚拟三维平移目标的映射，不连接、启动或控制 RM65。

未来可以形成以下完整链路：

~~~text
Quest
  -> 安全映射层
  -> MoveIt / CuRobo / 其他机器人控制适配层
  -> RM65
~~~

但本设计只负责其中的“Quest -> 安全虚拟目标”部分。后续控制适配层不属于本阶段范围，虚拟目标与 RM65 必须保持完全断开。

本设计的目标是：

- 使用 Quest 右手 position 生成连续的虚拟目标 position；
- 使用 button_lower 作为 deadman 授权；
- 使用相对位移，避免把 Quest 绝对坐标直接作为目标绝对坐标；
- 在 Pose 数据中断时冻结并锁定，禁止数据恢复后自动恢复授权；
- 以固定频率持续发布 Pose 和 Marker，便于 RViz 随时观察；
- 分离纯状态逻辑与 ROS 2 adapter，以便确定性单元测试。

## 2. 安全边界与非目标

/home/lh/robot 完全不属于本任务范围。

本阶段禁止：

- 修改 /home/lh/robot；
- source /home/lh/robot/install/setup.bash 作为本阶段运行依赖；
- 启动 rm_driver；
- 启动 rm_control；
- 启动 MoveIt；
- 启动 CuRobo；
- 启动 left_arm_controller；
- 启动 right_arm_controller；
- 启动任何真实机械臂 controller；
- 创建或调用 FollowJointTrajectory；
- 创建或调用 GripperCommand；
- 控制夹爪；
- 向任何 /left/*、/right/* 或其他 RM65 控制 topic/action 发布消息；
- 将虚拟目标直接连接到真实机器人执行接口。

本阶段结束时，以下两段必须完全断开：

~~~text
Quest -> virtual target

virtual target -/-> RM65
~~~

bridge 不得包含、导入或复用 robot_arm_controller_base.py 中的机器人控制逻辑。

## 3. 输入接口

bridge 只订阅以下两个右手 topic：

| Topic | 类型 |
|---|---|
| /q2r_right_hand_pose | geometry_msgs/msg/PoseStamped |
| /q2r_right_hand_inputs | quest2ros/msg/OVR2ROSInputs |

quest2ros/msg/OVR2ROSInputs 的实际字段为：

~~~text
bool button_upper
bool button_lower
float32 thumb_stick_horizontal
float32 thumb_stick_vertical
float32 press_index
float32 press_middle
~~~

第一版只使用：

- PoseStamped.pose.position；
- OVR2ROSInputs.button_lower。

第一版明确忽略：

- 输入 PoseStamped.header.stamp；
- 输入 PoseStamped.header.frame_id；
- 输入 orientation；
- twist；
- button_upper；
- 摇杆；
- 扳机及其他输入字段。

Quest/TCP 的不同序列化路径可能产生不同 header，因此 bridge 的运动映射和 watchdog 都不得依赖输入消息的 stamp 或 frame。当前只做右手三维平移验证。

## 4. 输出接口

bridge 只发布以下两个虚拟目标 topic：

| Topic | 类型 |
|---|---|
| /quest_right_target_pose | geometry_msgs/msg/PoseStamped |
| /quest_right_target_marker | visualization_msgs/msg/Marker |

两种输出均满足：

- header.frame_id = "world"；
- header.stamp 来自 node.get_clock().now().to_msg()；
- 不沿用 Quest 输入的 stamp 或 frame。

虚拟目标初始 position 为：

~~~text
x = 0.5
y = 0.0
z = 0.5
~~~

虚拟目标 orientation 始终固定为 identity：

~~~text
x = 0.0
y = 0.0
z = 0.0
w = 1.0
~~~

Marker 必须满足：

- 使用固定 namespace；
- 使用固定 id；
- action = ADD；
- 尺寸明显但不过大；
- position 与同一发布周期的 target Pose 完全一致；
- orientation 固定为 identity；
- 持续发布，使 RViz 在任意时刻加入后都能看到当前目标。

## 5. 第一版运动映射

第一版只映射平移，不映射旋转。

~~~text
scale = 1.0
axis mapping = identity
~~~

对应关系为：

~~~text
target Δx = Quest Δx
target Δy = Quest Δy
target Δz = Quest Δz
~~~

不得将 Quest 的绝对坐标直接赋给虚拟目标。目标必须通过 deadman 按下时建立的 Quest 锚点 Q0 和目标锚点 T0，使用相对位移计算。

后续通过真实 Quest 与 RViz 标定前/后、左/右、上/下分别对应 Quest 的轴和符号，再决定是否修改映射矩阵。坐标轴交换和符号取反不属于第一版。

## 6. Deadman 状态机

状态机至少包含：

- INACTIVE
- ACTIVE
- REARM_REQUIRED

初始状态：

~~~text
state = INACTIVE
target = (0.5, 0.0, 0.5)
~~~

### 6.1 INACTIVE

当 button_lower=false 时，Quest Pose 可以继续更新内部最新输入，但不能改变 target。

当 button_lower 出现 false -> true 上升沿时：

~~~text
Q0 = 当前 Quest position
T0 = 当前 target position
state = ACTIVE
~~~

完成锚定的这一帧必须保持当前 target，不允许发生位置跳变。

### 6.2 ACTIVE

持续按住 button_lower 时，目标计算为：

~~~text
target = T0 + (Qcurrent - Q0)
~~~

该公式已经包含第一版的 scale=1.0 和 identity axis mapping。

当 button_lower 出现 true -> false 时：

- 立即退出 ACTIVE；
- 进入 INACTIVE；
- target 保持最后位置。

松开期间，无论 Quest 如何移动，都不能改变 target。

### 6.3 重新锚定

下一次 button_lower 再次出现 false -> true 上升沿时：

~~~text
Q0 = 当前 Quest position
T0 = 当前 target position
state = ACTIVE
~~~

重新按下的这一帧 target 必须连续且无跳变。松开期间的 Quest 位移由新锚点吸收，不得反映为 target 跳变。

### 6.4 重复回调

- 重复收到相同 Pose 不得产生额外位移；
- 重复收到 button_lower=false 不得改变冻结 target；
- 重复收到 button_lower=true 不得被当成新的上升沿，也不得重置 Q0/T0；
- 只有明确的 false -> true 边沿可以建立新锚点并授权进入 ACTIVE。

## 7. Pose Watchdog

Pose timeout 固定为 0.2 秒。

watchdog 使用本机接收 Pose 的单调时间或等价可靠方式，不使用 Quest 消息中的 stamp。

watchdog 只在 ACTIVE 状态下判断。当且仅当：

~~~text
current_time - last_pose_receive_time > 0.2s
~~~

才发生 timeout。边界语义为：

- pose age 恰好等于 0.2s：不 timeout；
- pose age 严格大于 0.2s：timeout。

timeout 后必须：

- 立即冻结 target；
- state = REARM_REQUIRED。

### 7.1 REARM_REQUIRED

进入 REARM_REQUIRED 后，即使 Pose 恢复，只要 button_lower 从超时前一直保持 true，就不得自动回到 ACTIVE。

解除锁定必须经过完整授权序列：

~~~text
button_lower -> false
state = INACTIVE

随后：

false -> true
重新记录 Q0/T0
state = ACTIVE
~~~

因此，网络恢复不等于自动恢复控制授权。

异常或非单调时间输入不得用于计算空间位移，也不得造成 target 突然运动。时间接口的具体防御性处理由实现计划精确定义，但必须保持冻结优先和无跳变原则。

## 8. 发布频率

bridge 内部使用 50 Hz timer。

Quest 输入当前实测约 75 Hz。输入回调保存最新 Pose、按钮状态和接收时间；50 Hz timer 持续发布当前虚拟 target Pose 和 Marker。

发布 timer 不改变状态机的相对位移语义。每次发布使用当前 ROS clock 生成输出 timestamp，并保证同一周期的 Pose 与 Marker 表示相同 target。

## 9. 软件结构

### 9.1 纯逻辑模块

新增：

~~~text
q2r2_bringup/quest_right_target_logic.py
~~~

职责：

- 保存 INACTIVE、ACTIVE、REARM_REQUIRED 状态；
- 保存当前 target、Q0、T0、最新 Quest position 和 Pose 接收时间；
- 处理按钮边沿；
- 计算相对位移；
- 执行严格 >0.2s 的 watchdog；
- 保证冻结、重新锚定和无跳变语义。

约束：

- 不依赖 rclpy.Node；
- 不构造或发布 ROS 消息；
- 时间值可以从调用方注入；
- 状态转换和 target 输出可由纯 Python pytest 确定性验证。

具体 Python 接口、类型命名和返回值由实现计划进一步精确定义。

### 9.2 ROS 2 Adapter

新增：

~~~text
q2r2_bringup/quest_right_target_bridge.py
~~~

职责：

- 创建两个指定 subscription；
- 创建两个指定 publisher；
- 从消息中提取 position 和 button_lower；
- 为纯逻辑模块提供可靠接收时间；
- 创建 50 Hz timer；
- 使用 ROS clock 构造输出 header；
- 构造 PoseStamped 和 Marker；
- 持续发布当前虚拟目标。

该模块不得包含 RM65、夹爪、轨迹、MoveIt、CuRobo 或任何真实机器人控制逻辑。

### 9.3 测试

新增：

~~~text
test/test_quest_right_target_logic.py
~~~

该文件测试纯状态机与相对位移逻辑，不依赖真实 Quest 或真实机器人。

### 9.4 包入口

修改：

~~~text
setup.py
~~~

只增加以下 console script：

~~~text
quest_right_target_bridge = q2r2_bringup.quest_right_target_bridge:main
~~~

第一版预计不修改：

~~~text
package.xml
q2r2_bringup/SimulationInput.py
q2r2_bringup/CheckTCPconnection.py
q2r2_bringup/ros2quest.py
q2r2_bringup/robot_arm_controller_base.py
../quest2ros/*
../ros_tcp_communication/*
~~~

## 10. 单元测试验收条件

纯逻辑 pytest 至少覆盖：

1. 初始 target 等于 (0.5, 0.0, 0.5)；
2. button_lower=false 时，Quest Pose 移动不能改变 target；
3. 第一次 false -> true 只建立锚点，target 不跳变；
4. ACTIVE 时 Quest x 增加 0.1m，target x 增加 0.1m，y/z 同理；
5. release 后立即冻结 target；
6. release 期间 Quest 移动不能改变 target；
7. 再次 press 时以当前 Quest/current target 作为新的 Q0/T0，target 不跳变；
8. ACTIVE 下 pose age 严格大于 0.2s 时进入 REARM_REQUIRED；
9. pose age 恰好等于 0.2s 时不 timeout；
10. REARM_REQUIRED 且按钮持续为 true 时，Pose 恢复不能重新进入 ACTIVE；
11. release 使 REARM_REQUIRED -> INACTIVE；
12. 下一次 press 可以重新锚定并进入 ACTIVE；
13. 多轴同时位移；
14. 零位移；
15. repeated Pose callbacks；
16. repeated button-state callbacks；
17. 异常或非单调时间输入不能导致 target 突然运动。

## 11. ROS Adapter 验收条件

bridge 只订阅：

~~~text
/q2r_right_hand_pose
/q2r_right_hand_inputs
~~~

bridge 只发布：

~~~text
/quest_right_target_pose
/quest_right_target_marker
~~~

Pose 验收：

- frame_id = "world"；
- timestamp 来自当前 ROS clock；
- position 等于当前 target；
- orientation 固定为 identity。

Marker 验收：

- frame_id = "world"；
- timestamp 来自当前 ROS clock；
- position 与 target Pose 一致；
- orientation 固定为 identity；
- namespace/id 固定；
- action = ADD；
- 以 50 Hz 持续发布。

bridge 不得创建任何 /left/*、/right/*、RM driver、rm_control、FollowJointTrajectory、GripperCommand 或其他 robot controller 相关 publisher、client 或 action。

## 12. 验证策略

### 12.1 第一层：纯 Python pytest

使用可注入时间完整验证 deadman、watchdog、状态转换、相对映射、冻结和重新锚定。全部安全语义以这一层为主要自动化证据。

### 12.2 第二层：ROS 2 Bridge Smoke Test

数据流仅为：

~~~text
Quest 或模拟输入
  -> quest_right_target_bridge
  -> /quest_right_target_pose
  -> /quest_right_target_marker
~~~

这一层只验证订阅、adapter、持续发布和消息字段。

现有 SimulationInput.py 将 button_lower 永久设为 True，因此只能用于验证 bridge 能收到 Pose、ACTIVE 时持续更新和输出 topic 正常。它不能验证 release、re-anchor 或 timeout 后重新授权；不得为了本任务修改该文件。

完整状态语义必须由纯逻辑单元测试验证。

### 12.3 第三层：真实 Quest + RViz

在不加载 RM65 的情况下观察：

- 初始 Marker 位于 (0.5, 0.0, 0.5)；
- 未按 deadman 时目标不动；
- 按住 button_lower 后目标随 Quest 相对位移移动；
- 松开后立即冻结；
- 再次按下无跳变；
- XYZ 与真实物理方向的对应关系。

第一版完成后，再根据真实 Quest + RViz 观察结果决定是否调整轴映射矩阵。

## 13. 已有本地修改保护

当前 Quest2ROS2 working tree 已存在 package.xml、q2r2_bringup/ros2quest.py 和若干 .pyc 修改或未跟踪文件。这些内容必须原样保留，不得重置、覆盖、清理或误加入本设计文档的 commit。

ros_tcp_communication 已存在本地补丁和未跟踪的 ros_msg_converter.py.bak，不得修改、删除、重置或提交。

quest2ros 不是 Git 仓库，本阶段不需要且不得修改。

本设计文档的 commit 只能包含：

~~~text
docs/superpowers/specs/2026-09-19-quest-right-target-bridge-design.md
~~~

不得包含任何已有 dirty working tree 内容。

## 14. 成功定义

Stage 2 第一版成功必须同时满足：

- RViz 中存在初始目标 (0.5, 0.0, 0.5)；
- 松开 button_lower 时目标保持；
- 按住 button_lower 时目标按 Quest 相对三维平移 1:1 移动；
- 松开后目标立即冻结；
- 松开期间手柄移动到任意位置后重新按下，目标连续且无跳变；
- Pose 数据丢失严格超过 0.2s 后，目标冻结并进入 REARM_REQUIRED；
- 数据恢复但按钮仍保持按下时，目标不能自动恢复运动；
- 完整执行 release 后再次 press，可以重新锚定并恢复虚拟目标控制；
- 整个过程中不启动、连接或控制 RM65；
- Quest 到虚拟目标的链路与虚拟目标到 RM65 的链路保持完全断开。
