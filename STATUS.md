# Project Status

更新日期：2026-09-21

## 当前总体阶段

右手 Quest 到右 RM65 的**平移 demo 已首次端到端打通**。现场已确认真实 Quest 能通过 ROS2、right target bridge 和 `rm65_teleop_adapter` 驱动右 RM65 产生实际运动。

当前结论只覆盖第一阶段右手/右臂平移 demo，不代表旋转、夹爪、左臂、双臂或完整安全验收已经完成。

## V0.2 启动与观察体验

`feat/right-teleop-bringup` 已实现统一右臂遥操作 launch：默认 dry-run，统一启动 TCP endpoint、右手 target bridge、adapter、只读状态监控，并可选启动预配置 RViz。

- 默认 launch 不创建 `/right/rm_driver/movep_canfd_cmd` publisher。
- `mode:=hardware` 先加载既有 `hardware.yaml` 安全基础，再加载选定的版本化 motion profile；adapter 三重硬件 gate 不变。
- 状态监控仅观察 Quest Pose、Inputs、target、robot feedback 和 adapter JSON，不参与控制或安全判断。
- 控制机安装包含双臂 launch，但没有已验证的 right-only launch；通用单臂 launch 也不是右臂参数。因此本轮不自动启动 RM driver，现场仍需单独使用已验证方式启动右臂 driver。
- 隔离控制机 worktree 中四包构建成功；adapter 的 12 项 GTest 与 8 项 pytest、Quest bridge 56 项测试通过。
- dry-run smoke 观察到四个预期节点，状态监控在无 Quest/robot feedback 时稳定显示 `LOST`，硬件 command publisher 数量为 0。
- 本轮没有启动或控制真实 RM65，也没有重新完成真机验收。

## 已完成

- Quest → ROS2 TCP 真实通信。
- 右手虚拟 target bridge。
- `button_lower` deadman、release freeze、无跳变 re-anchor。
- A 侧真实 Quest + RViz 现场验收。
- Quest 物理方向：`+X=前、+Y=左、+Z=上`。
- RM65 物理方向：`+X=上、+Y=后、+Z=右`。
- 平移映射：`RM(dx,dy,dz)=(Qdz,-Qdx,-Qdy)`。
- B 侧独立 `rm65_teleop_adapter`：dry-run、硬件 gated output、双锚点、独立 watchdog、限速/限位/突跳/非有限值检查、rearm 和 stop 通路。
- B 侧独立构建成功；此前报告 12 项 GTest 全部通过，`colcon test-result` 为 13 tests、0 failures。
- 隔离硬件模式联调已完成，模拟 command/stop 与正式真机 topic 隔离。
- **首次真实 Quest → 右 RM65 真机平移运动已经现场成功。**

## 版本化 motion profiles

默认始终为 `safe`。`hardware.yaml` 保留硬件安全配置，motion profile 只覆盖
`translation_scale`、`max_velocity_mps`、`max_step_m` 和
`max_anchor_distance_m`。

| Profile | translation_scale | max_velocity_mps | max_step_m | max_anchor_distance_m | 当前状态 |
|---|---:|---:|---:|---:|---|
| `safe` | 0.2 | 0.005 | 0.00005 | 0.03 | 已有真机基线参数；默认档 |
| `normal` | 1.0 | 0.20 | 0.00050 | 1.0 | 已完成一次真实 Quest → 右 RM65 手感测试 |
| `fast` | 0.5 | 0.040 | 0.00020 | 0.10 | experimental；未真机验证，暂不用于真实机械臂 |

现场操作者使用真实 Quest 和真实右 RM65 测试了当前 `normal` 参数。真机能够
正常跟随；相比旧参数，跟手性明显改善，平移幅度明显更合理。操作者认为
`max_step_m` 增大对跟手改善最明显。XYZ 平移链路此前已经打通，并在本次测试
中保持可用。

这只是定性手感验证，并未系统测量精确速度、stopping distance、overshoot、
长时间稳定性或 1.0 m anchor 范围的安全边界。`max_anchor_distance_m=1.0` 是
field-tested tuning value / pending workspace and stopping-margin review，不能
写成推荐安全边界。按 200 Hz 名义控制频率，0.0005 m 步长对应约 0.10 m/s 的
理论步长上限；这不是实测速度。正常调度下，步长限制会先于 0.20 m/s 速度
限制生效。

`safe` 保持不变并继续作为默认档。`fast` 参数暂时保持不变，但完全没有真机
验证，属于 experimental / not for hardware use yet，不建议启动真实机械臂。

## 尚未完成/仍需验证

- Quest orientation → RM65 orientation。
- 夹爪。
- 左臂与双臂。
- 全部真实断流场景和长期网络抖动。
- 真机 deadman 停止余量的系统化验收。
- 更完整的工作空间/碰撞约束。
- `normal` 的精确速度、overshoot、长时间稳定性和 anchor=1.0 安全边界验证。
- `fast` 真机表现及是否应继续保留/调整。
- 生产级安全设计。

## 当前 demo 关键链路

```text
Quest 右手柄
  -> ROS TCP
  -> /q2r_right_hand_pose + /q2r_right_hand_inputs
  -> quest_right_target_bridge
  -> /quest_right_target_pose
  -> rm65_teleop_adapter
  -> /right/rm_driver/movep_canfd_cmd
  -> 右 RM65
```

## 基线来源

- Quest2ROS2 原 feature 基线：`9ca76a808d4cebecbb633e231071301259d71cd9`。
- ros_tcp_communication 原现场基线：`5c5f08956d4bc7a045c321214b0bc03c63eb20a7`。
- B 侧 adapter 分支原提交序列：`90171ab`、`1586d51`、`a619e76`。

来源和上游补丁详情见 `docs/SOURCES.md`。
