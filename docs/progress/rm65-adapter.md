# B — RM65 Adapter Progress

- 负责人：B 同学
- 分支：`feat/rm65-adapter`
- 当前状态：**RM65 adapter 已实现；真实 Quest → 右 RM65 首次平移联调成功，完整安全验收仍待继续。**

## 已完成

- 确认右 RM65 runtime 接口与反馈。
- 新建独立 ROS 2 包 `rm65_teleop_adapter`。
- dry-run 默认安全模式。
- gated hardware output。
- 使用 `button_lower` deadman，并独立监测 Inputs、原始 Quest Pose、virtual target 和 robot feedback。
- 双锚点相对控制，固定当前机器人末端姿态。
- 坐标映射：`rm_x=quest_z`、`rm_y=-quest_x`、`rm_z=-quest_y`。
- 速度、单步、workspace、突跳、NaN/Inf、rearm、latched fault 和 control-period guard。
- ACTIVE 退出时停止发送 CANFD 点并重复普通 stop。
- 独立构建成功；此前报告 12 项 GTest 全部通过，`colcon test-result` 为 13 tests、0 failures。
- 隔离硬件模式验证完成，正式真机 topic 在隔离测试中未被误写。
- 真实 Quest 输入曾测得平均约 76.9 Hz，观察到最大间隔约 165 ms。
- **现场操作者已确认真实 Quest 右手柄可以通过当前 adapter 驱动右 RM65 产生实际运动。**

## 已确认 runtime

- `/right/joint_states`：约 197 Hz。
- `/right/rm_driver/udp_arm_position`：约 197 Hz。
- command：`/right/rm_driver/movep_canfd_cmd`。
- stop：`/right/rm_driver/move_stop_cmd`。
- 单独右臂 driver，无第二命令源。

## 已记录的微动/停止证据

- `+Z 3 mm` 连续 Cartesian 目标实测约 `+3.007 mm`。
- 普通 stop 返回成功。
- 低跟随停止后仍可能有约 `0.5 mm` 后续位移。
- 高跟随对比停止余量约 `0.063 mm`。
- high-follow 调度间隔在当前主机负载下不稳定，因此当前硬件 profile 使用低跟随方案。

## 参数说明

远端提交的 `hardware.yaml` 保持：

- `translation_scale: 0.2`
- `max_velocity_mps: 0.005`
- `max_anchor_distance_m: 0.03`

现场曾使用未提交值：

- `0.5 / 0.010 / 0.10`

这些现场调参值没有作为仓库默认值合入。

## 仍待验收

- 三轴真机方向的系统化记录。
- deadman release 后的真机停止余量记录。
- Pose、Inputs、robot feedback 各自断流的完整真机测试。
- 长时间 Quest 网络抖动。
- 参数调优。
- 旋转、夹爪、左臂与双臂。

不要把“首次真机能动”描述成完整生产安全验收完成。
