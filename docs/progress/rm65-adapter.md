# B — RM65 Adapter Progress

- 负责人：B 同学
- 建议分支：`feat/rm65-adapter`
- 当前状态：**硬件写入已实现并通过隔离联调；Quest 真机运动验收尚未完成**

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

### C++ adapter v2

- 新建 `src/rm65_teleop_adapter`，dry-run 仍为默认模式；
- 硬件 publisher 只在 `dry_run=false`、`hardware_write_enabled=true`、
  `mapping_verified=true` 同时成立时创建；
- 使用 `button_lower`、四路独立 watchdog、双锚点、固定姿态和已确认方向矩阵；
- 已实现速度、单步、workspace、突跳、NaN/Inf、rearm 和 latched fault；
- 新增 3 cm 锚点半径、控制周期 guard 和唯一 command/stop 通路检查；
- ACTIVE 退出时停止发送 CANFD 点并重复发布 3 次普通 stop；
- 独立构建成功，12 项 GTest 全部通过，`colcon test-result` 为
  13 tests、0 failures；
- 10 秒 live dry-run 正常启动/退出，命令 topic publisher 始终为 0；
- A 侧现场确认 `+X=前、+Y=左、+Z=上`；右 RM65 base 为
  `+X=上、+Y=后、+Z=右`；
- 最终矩阵为 `rm_x=quest_z`、`rm_y=-quest_x`、`rm_z=-quest_y`。

### 2026-09-20 隔离硬件模式验证

- 所有模拟数据和 command/stop 均 remap 到 `/test/rm65_adapter/*`，正式真机
  command topic 在测试前后均为 0 publisher；
- release 后进入 ARMED，press 后进入 ACTIVE；
- Quest `+X 10 mm` 生成 RM65 `-Y 2.0 mm` 命令，姿态与另外两轴保持不变；
- 一秒内观察到 196 个 command callback；
- Inputs 断流后进入 REARM_REQUIRED 并收到 3 个 stop；
- 数据恢复且按键仍按住时不自动继续；release→press 后重新 ACTIVE；
- high-follow 的 10 ms guard 在当前负载下捕获 `13.48 ms`/`21.87 ms`
  抖动。经现场操作者明确授权，硬件 profile 改为低跟随，名义 200 Hz、
  50 ms 严重卡顿 guard；隔离联调峰值约 `22.79 ms`，测试通过。

### 真机 Quest 启动检查

- 启动前右臂 `err=0`、`dof=6`，command topic 为 0 publisher / 1 driver subscriber；
- Quest Inputs 恢复后实测平均约 76.9 Hz、最大间隔约 165 ms，低于当前
  200 ms watchdog，但仍需继续观察稳定性；
- 真机 adapter 成功启动到 ARMED，命令通路为 1 publisher / 1 subscriber；
- 30 秒观察期内操作者未按下 `button_lower`，command 数为 0，随后已发送
  普通 stop 并关闭 adapter；
- 因此尚不能宣称 Quest 真机运动方向和 deadman 停止已完成验收。

### 下一项实现

1. 重新启动 hardware profile，由操作者完成首次 `button_lower` press、小位移、release；
2. 实测并记录三条物理映射、deadman stop 和停止余量；
3. 分别执行 Pose、Inputs、robot feedback 断流的真机安全测试；
4. 观察 Quest Inputs 最大间隔，必要时先修复 A 侧链路稳定性再继续验收；
5. 完成全部验收后才提高尺度/速度或扩展旋转、夹爪和左臂。
