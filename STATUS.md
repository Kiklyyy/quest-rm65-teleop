# Project Status

更新日期：2026-09-25

## 当前总体阶段

右手 Quest 到右 RM65 的**平移 demo 已首次端到端打通**。现场已确认真实 Quest 能通过 ROS2、right target bridge 和 `rm65_teleop_adapter` 驱动右 RM65 产生实际运动。

右臂 6DoF orientation extension 已完成自动化验证、隔离 synthetic dry-run、
真实 Quest live quaternion/preview 验证，以及实际右 RM65 的首次人工姿态跟随测试。
当前正式姿态参数恢复为 rotation_scale=1.0、90 deg/s、0.01 rad/cycle、90 deg
单次 Grip anchor 上限。夹爪、左臂、双臂和完整安全验收仍未完成。

## Left RM65 Quest teleop (dry-run with real feedback; no robot motion)

- Branch `feat/left-rm65-teleop` depends on right Home closeout `074e0fa3b7b727fd39c4a2818a22114efe6ec1f3`; `origin/main` did not yet include that work at branch creation.
- The right adapter executable/safety state machine now has explicit per-arm node identities, topics and preview/status/service endpoints. Right endpoint and Home configuration remain unchanged. A parameterized Quest target bridge and read-only monitor support a separate left dry-run launch.
- Operator-confirmed left physical axes yield the mathematically proper matrix `[[0,0,-1],[-1,0,0],[0,1,0]]`; software tests cover XYZ and the existing world-frame orientation convention. Real Quest plus real robot-anchor **dry-run preview** has now passed; validation with actual left-arm movement is pending.
- Left configuration is dry-run only: `hardware_write_enabled=false`, `mapping_verified=false`, `home_enabled=false`. Left Home target/button, absolute workspace, payload/cable limits, and mutual collision boundaries are not accepted. The large finite left preview bounds are synthetic placeholders, not hardware limits. The operator reported a gripper attached and all directions clear; a single selected first-test direction and numerical displacement limit remain unsupplied.
- Isolated `ROS_DOMAIN_ID=143`, localhost-only left Quest/feedback probe produced target, status and preview, with zero real left movep/movej/stop publishers and no Home Action client. That software phase did not start a driver or real motion.
- On 2026-09-25, a single left RM driver supplied real six-joint and TCP feedback at about 198 Hz, and the onsite operator confirmed both arms remained stationary. The left adapter/TCP/bridge/monitor were started in `dry_run` on domain 42. Live graph checks before, during and after Quest gestures showed **zero publishers** on left movep, movej, and stop topics and zero Home Action clients. The first driver attempt revealed that global `__node:=rm_driver` also renames its internal UDP node; restarting only that driver without the node remap produced unique `/left/rm_driver` and `/left/udp_publish_node`. No left `rm_control`, Home goal, or robot motion was started.
- Real Quest left physical fields were confirmed: Grip=`press_middle`, index=`press_index`, X=`button_lower`, Y=`button_upper`; X/Y remain unbound. With the headset worn, dry-run preview signs against the real left TCP anchor passed forward `Quest +X→left -Y`, left `Quest +Y→left +Z`, and up `Quest +Z→left -X`. A small wrist rotation produced 27.418° raw Quest and 27.435° preview rotation, with 0.088° error versus the mapped quaternion prediction. An earlier forward trial without wearing the headset was excluded as invalid physical-direction evidence. No q/-q flip occurred in the live rotation interval.
- **First left micro-motion remains NO-GO:** Quest Pose/Inputs repeatedly went stale together; in 532 s of the connected gesture window `watchdog_count` rose 0→42, and the longer connected window contained raw receive gaps up to about 1.425 s against 200 ms timeouts. Robot feedback remained fresh near these events, while the target bridge kept publishing. Timeouts were not changed. Operator-approved numerical displacement and other site-specific safety facts are still missing. The left dry-run/TCP/driver were stopped after the preflight; the domain-42 graph and TCP port 10000 were clear.
- Four-package build and final automated regression passed: `colcon test-result --all` reported 220 tests, 0 errors, 0 failures, 0 skipped (includes 14 CTest wrapper records). Quest/TCP simultaneous input gaps remain open.

## Right RM65 Home + stability branch (hardware validated; input stability open)

- Branch `feat/recenter-home` locks physical A=`button_lower` (reserved) and B=`button_upper` (Home). Grip `press_middle` remains the 0.60/0.40 teleop deadman.
- Hardware Home configuration: J1..J6 names `joint1` through `joint6`, operator-confirmed 2026-09-24 target degrees `[68.3241063822369, -8.489398369548377, 60.14265142722264, 31.52005176840807, 51.634258495569824, -144.10081659391062]`, hold 1.5 s, nominal maximum average joint speed 15 deg/s, action `/right/rm_group_controller/follow_joint_trajectory`. The old temporary target `[-95.605, 4.406, -80.034, -22.695, -48.462, 97.570]` is retired.
- Home starts only from `ARMED` with released Grip, fresh inputs/joints, an available action server, and the existing exclusive command/stop path. `HOMING` suppresses Cartesian output. B release, watchdog/invalid feedback, control-period loss, or command-path loss requests cancel+stop and retains `HOMING` until an action terminal result. Success/cancel requires B release and normal Grip release-to-press reauthorization; reject/abort enters `FAULT`.
- Four-package worktree build and automated suite after new Home configuration: 206 tests, 0 errors, 0 failures, 0 skipped (`/usr/bin/colcon test-result --test-result-base build --all --verbose`).
- `ROS_DOMAIN_ID=143`, `ROS_LOCALHOST_ONLY=1` synthetic integration: 5 test-only Home goals, 4 cancels (B release, stale Quest pose, invalid joint feedback, shutdown), 1 success, 0 Cartesian commands, 0 real command publishers. A separate dry-run node exposed no real Home action client. No RM driver was started.
- Whole-branch safety review fixed RED-to-GREEN findings for Home rearm/button race, invalid feedback, command-path and cycle guards, invalid-joint diagnostics, and shutdown cancel+stop delivery.
- **Right Home execution and B-release cancel hardware validated.** The 2026-09-24 operator confirmed the new target after fresh samples differed from the earlier preflight posture; the read-only post-restart delta was within 0.008 deg on all six joints. An initial one-point goal crashed `rm_control`; the four-point RealMan-compatible trajectory subsequently returned from clearly away-from-Home postures multiple times in about 5–7 s. During a later mid-motion B release, the arm physically stopped. Because RealMan can report terminal `SUCCEEDED` after `/move_stop_cmd`, commit `ce371c0` maps that result to adapter `CANCELED` only when a local cancel was pending. The final operator-provided status sample showed `home_action_state=CANCELED`, state `ARMED`, Grip and B released, both command paths ready, and no automatic `ACTIVE`. This checkpoint records the operator’s hardware observations; no robot motion was initiated by the documentation update.
- **Quest/TCP input stability remains open (2026-09-24 observation):** A 135.0 s read-only run found three recurring watchdog events, `120 -> 123`, all `input_not_fresh`. Quest Pose and Inputs simultaneously had 311–343 ms receive gaps beyond their 200 ms timeouts, and status briefly entered `REARM_REQUIRED` three times. Robot/joint feedback stayed below 100 ms; the target bridge kept publishing about 50 Hz during raw Quest gaps. No timeout or motion setting was changed. This remains a separate stability issue after Home hardware validation.

- The targeted Ubuntu adapter build and `test_home_action_client` after the cancel compatibility change passed: CTest 1/1 executable, GTest 8/8 cases. The existing normal-success case remains `SUCCEEDED`; pending-local-cancel plus vendor success becomes `CANCELED`. The full suite was not rerun for the documentation closeout.

## Right-arm 6DoF orientation implementation

- quaternion、frame mapping、双姿态锚点、angular limiter 和 orientation safety
  单元测试已通过；
- 既有 XYZ translation、middle-grip deadman、motion profile 和 Quest bridge
  regressions 已通过；
- `ROS_DOMAIN_ID=142`、`ROS_LOCALHOST_ONLY=1` 的 adapter-only synthetic
  dry-run 已验证 preview 的轴映射、同时平移/旋转、release/repress 无跳变，并确认
  `/right/rm_driver/movep_canfd_cmd` publisher count 为 0；
- live Quest quaternion probe 已通过：/q2r_right_hand_pose 实测约 70.7–72.1 Hz，
  quaternion norm 约 0.9999999753–1.0000000714；未观察到 NaN/Inf；
- 首次 Grip ACTIVE 与 repress 首帧 orientation error 均为 0.0°，release 后
  preview_after_release=0；
- live session 自然观察到 202 次 q/-q sign flip，shortest-path 处理未造成 preview
  跳变或 orientation jump fault；
- 两段主要真实手腕旋转的 expected-preview orientation error 均为 0.0°；
- real RM65 orientation 已进行现场人工 smoke test。首次以临时低速 envelope 验证后，
  恢复正式 V1 姿态参数，操作者反馈跟手性明显改善并认为当前表现可接受。该硬件结果
  目前仍是定性人工验收，没有保存逐轴精确角度、跟踪误差、overshoot 或停止距离数据。

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
- 中指 Grip `press_middle` deadman：`>=0.60` 按下、`<=0.40` 松开、中间区保持；release freeze、无跳变 re-anchor。
- A 侧真实 Quest + RViz 现场验收。
- Quest 物理方向：`+X=前、+Y=左、+Z=上`。
- RM65 物理方向：`+X=上、+Y=后、+Z=右`。
- 平移映射：`RM(dx,dy,dz)=(Qdz,-Qdx,-Qdy)`。
- B 侧独立 `rm65_teleop_adapter`：dry-run、硬件 gated output、双锚点、独立 watchdog、限速/限位/突跳/非有限值检查、rearm 和 stop 通路。
- B 侧独立构建成功；此前报告 12 项 GTest 全部通过，`colcon test-result` 为 13 tests、0 failures。
- 隔离硬件模式联调已完成，模拟 command/stop 与正式真机 topic 隔离。
- **首次真实 Quest → 右 RM65 真机平移运动已经现场成功。**
- raw Quest orientation 直接进入 adapter 的 6DoF 相对姿态链路已经实现；使用
  world-frame delta、已确认矩阵共轭、robot anchor 左乘和 shortest-path SLERP。
- **真实 Quest live orientation mapping 已现场通过；真实右 RM65 姿态 smoke test
  已完成并由现场操作者接受。**

## 当前 deadman 输入

- 来源：`/q2r_right_hand_inputs.press_middle`。
- 按下阈值：`press_middle >= 0.60`；松开阈值：`press_middle <= 0.40`。
- `0.40 < press_middle < 0.60` 保持上一状态；NaN/Inf 安全视为 released。
- `button_lower` 不再控制右 RM65 teleop；`press_index` 当前仍未使用。
- 安全状态机语义不变：release 立即退出 ACTIVE/stop，数据恢复仍必须 release → press 重新授权。

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

- 真实 RM65 orientation 的定量验收：逐轴精确角度、tracking error、overshoot、
  stopping distance、长时间静止抖动和更长时间连续运行记录。
- 更系统的组合 rotation 与 translation + rotation 定量验证。
- 夹爪。
- 左臂真实运动与双臂。
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
  -> /q2r_right_hand_pose.position
  -> quest_right_target_bridge -> /quest_right_target_pose (translation)
  -> rm65_teleop_adapter

/q2r_right_hand_pose.orientation + /q2r_right_hand_inputs
  -------------------------------> rm65_teleop_adapter
  -> /right/rm_driver/movep_canfd_cmd
  -> 右 RM65
```

## 基线来源

- Quest2ROS2 原 feature 基线：`9ca76a808d4cebecbb633e231071301259d71cd9`。
- ros_tcp_communication 原现场基线：`5c5f08956d4bc7a045c321214b0bc03c63eb20a7`。
- B 侧 adapter 分支原提交序列：`90171ab`、`1586d51`、`a619e76`。

来源和上游补丁详情见 `docs/SOURCES.md`。
