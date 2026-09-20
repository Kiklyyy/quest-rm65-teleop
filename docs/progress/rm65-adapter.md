# B — RM65 Adapter Progress

- 负责人：B 同学
- 建议分支：`feat/rm65-adapter`
- 当前状态：**尚未实现**

## 职责边界

新建独立 ROS 2 包：`rm65_teleop_adapter`。

- 不修改 A 同学负责的 Quest bridge、状态逻辑或 TCP Endpoint 源码。
- 只消费双方在 `docs/INTERFACE.md` 已对齐的虚拟目标和 enable/validity 接口。
- 不把 `/quest_right_target_pose` 的新 timestamp 当作用户授权。

## 实现前必须确认

- 实际 RM65 驱动、唯一命令源和允许的 topic/action。
- 当前机器人位姿读取方式和启用时锚定规则。
- Quest/world 到机器人 base frame 的经现场验证变换。
- 限速、限位、碰撞约束、控制频率、接收 watchdog 和停止策略。
- 断线、Inputs 丢失、rearm、节点退出和驱动异常时的安全状态。

## 安全默认值

- 真机写入默认关闭。
- 未经现场操作者明确授权，不创建或发送真实控制命令。
- 不直接执行虚拟初始目标 `(0.5, 0.0, 0.5)` 或 identity 姿态。
- 一只机械臂同一时刻只允许一套指定驱动/命令来源。
- 模拟输入不得混入正式控制话题。

## 进度记录

首次实现前，把计划输入、输出、失效行为和测试方式先写入 `docs/INTERFACE.md`。每个 WIP 必须给出 branch 和 commit SHA，不得标记为现场验收完成。

## 2026-09-20 B 侧启动记录

- 分支：`feat/rm65-adapter`
- 基线：`a2f48be7dfbd5b6f6e34a093707677410e178dd7`
- 独立工作目录：`~/quest2ros2_ws/.worktrees/rm65-adapter`
- A 侧运行工作区和两个上游嵌套仓库均未修改。

### 已完成的只读确认

- `rm_driver` 主函数创建 `RmArm` 与 `UdpPublisherNode`，使用 8 线程 executor；
- `Arm_Start()` 只初始化 SDK、查询版本并创建机器人连接，不含运动命令；
- 右臂必须使用 `/right` namespace 和 `rm_65_right_config.yaml` 对应参数；
- 右臂型号实测为 `RM65-BI`，控制器版本为 3；
- `/right/joint_states` 与 `/right/rm_driver/udp_arm_position` 实测约 197 Hz；
- 主动状态查询实测 `err=0`、`dof=6`。

### 已完成的真机最小验证

- 仅右臂 driver，无 MoveIt、CuRobo、比赛程序或第二命令源；
- `+Z 3 mm` 连续 Cartesian 目标实测移动 `+3.007 mm`；
- `move_stop_cmd` 返回成功；
- 低跟随运动中 stop 存在约 `0.5 mm` 后续位移；
- 高跟随对比测试的停止后余量约 `0.063 mm`；
- 临时 Python 发送器出现 `17.5 ms` 最大发送间隔，高跟随周期要求尚未满足。

上述仅是受控微动证据，不等于 Quest 遥操作、watchdog 或最终安全验收完成。

### 下一项实现

1. 新建独立 C++ ROS 2 包 `rm65_teleop_adapter`；
2. 默认 `dry_run=true`、`hardware_write_enabled=false`、`mapping_verified=false`；
3. 实现双锚点、固定姿态、映射、限速、单步限制、workspace 和 rearm 状态机；
4. 记录控制周期和最大发送间隔，超限进入 latched fault；
5. 使用 remap 后的测试 topic 完成 dry-run 自动化测试；
6. A 侧实现并对齐 `/quest_right_teleop_enable` 后，才进行 Quest 真机连续控制。
