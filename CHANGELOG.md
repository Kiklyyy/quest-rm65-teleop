# Changelog

## 2026-09-22 — Right-arm 6DoF orientation control

- 新增 raw `/q2r_right_hand_pose.pose.orientation` → `rm65_teleop_adapter` 的相对姿态路径；既有 `/quest_right_target_pose` bridge 继续只承担已验证平移 target。
- 固定 ROS `(x,y,z,w)`、Hamilton product、`Delta R_Q = R_Q * R_Q0^T`、矩阵 `M` 共轭和 `R_desired = Delta R_RM * R_R0` 左乘约定，不使用 Euler 累积。
- 新增 `rotation_scale=1.0`、`max_angular_velocity_rad_s=1.5707963267948966`、`max_angular_step_rad=0.01`、`max_anchor_angle_rad=1.5707963267948966`、`unexpected_orientation_jump_rad=0.7853981633974483`。
- 新增 quaternion math、Quest orientation tracker、anchoring/mapping/limiter/safety/config tests，以及 adapter-only `ROS_DOMAIN_ID=142` synthetic dry-run probe。
- 保持 translation bridge、translation mapping、motion profiles、workspace、deadman、watchdogs、stop/rearm 和单一 Pose command path 不变。
- 自动化测试与 synthetic dry-run 已验证。
- 真实 Quest live orientation mapping 已完成现场验证：约 70.7–72.1 Hz，quaternion norm 接近 1，未出现 NaN/Inf；首次 Grip 与 repress 均无姿态跳变，release 后不再发布 preview；自然观察到 202 次 q/-q sign flip，shortest-path 处理正常。
- 真实右 RM65 已完成首次 orientation smoke test。先用临时低速 envelope 验证，再恢复批准的 V1 正式姿态参数（1:1、90 deg/s、0.01 rad/cycle、90 deg anchor）；操作者反馈恢复后跟手性明显改善并接受进入下一阶段。
- 真机姿态结果目前仍为定性现场验收，未系统量化逐轴 tracking error、overshoot、stopping distance、长时间 jitter 或 repeatability。

## 2026-09-21 — Middle-grip teleop deadman

- 将右 RM65 teleop deadman 来源从 `/q2r_right_hand_inputs.button_lower` 切换为中指 Grip 模拟量 `/q2r_right_hand_inputs.press_middle`。
- 加入迟滞：`press_middle >= 0.60` 为 ON，`press_middle <= 0.40` 为 OFF，中间区保持上一状态；NaN/Inf 安全置为 OFF。
- A 侧 bridge 与 B 侧 adapter 使用同一阈值语义；`button_lower` 不再触发右臂 teleop，`press_index` 当前仍未使用。
- 保持既有状态机、平移映射、motion profiles、运动参数、watchdog、release stop 和 release → press rearm 行为不变。
- adapter status 改为发布 `deadman_pressed` 与 `deadman_source=press_middle`；状态监控优先读取语义字段并兼容旧 `button_lower` 数据。

## 2026-09-21 — Versioned teleop motion profiles

- 将现场直接编辑 tracked `hardware.yaml` 的调速方式迁移为版本化 `safe`、`normal`、`fast` motion profiles。
- `safe` 保持现有安全基线并作为默认；`normal` 更新为现场真实 Quest → 右 RM65 手感测试使用的 `1.0 / 0.20 / 0.0005 / 1.0`；`fast` 仅保留实验配置，未经真机验证且暂不用于真实机械臂。
- hardware 模式按 `hardware.yaml` → profile override 顺序加载，profile 只包含四个运动体验参数。
- 非法 profile 会拒绝启动；dry-run 不会因 profile 选择创建硬件命令发布路径。
- 隔离 worktree 中四包构建成功；adapter 与 Quest bridge 自动测试通过，三档 dry-run smoke 的 hardware command publisher 均为 0。
- 真实测试确认当前 `normal` 能正常跟随，且相对旧参数明显更跟手、平移幅度更合理；操作者认为增大 `max_step_m` 的改善最明显。
- 本次结果仅为定性手感验证，未系统量化精确速度、stopping distance、overshoot、长时间稳定性或 anchor=1.0 的安全边界。
- 200 Hz 下 0.0005 m 步长对应约 0.10 m/s 的理论上限，这不是实测速度；1.0 m anchor 仅是 field-tested tuning value，仍待 workspace 与 stopping-margin review。

## 2026-09-21 — Unified right-arm teleop bringup

- 新增 `right_quest_teleop.launch.py`，统一启动 ROS TCP endpoint、右手 target bridge、RM65 adapter、状态监控和可选 RViz。
- 默认仍为 `dry_run`；硬件模式继续直接加载既有 `hardware.yaml`，不绕过任何 hardware gate。
- 新增只读 `teleop_status_monitor`，状态变化立即输出并约 1 Hz heartbeat；异常 JSON 显示 `UNKNOWN`。
- 新增最小 RViz 配置，固定 `world` frame，并预配右手 target Marker/Pose。
- 控制机现有安装没有已验证的 right-only RM65 launch，因此 `start_rm_driver` 默认关闭且显式请求会安全失败；不调用双臂 launch。
- 隔离 ROS 2 Humble worktree 中四包构建成功，adapter 12 项 GTest、状态监控 8 项测试和 Quest bridge 56 项测试通过。
- dry-run smoke 中四个预期节点正常运行，硬件命令 topic publisher 数量为 0；本轮未启动或控制真实 RM65。

## 2026-09-21 — First end-to-end Quest → RM65 translation demo

- 合入 A 侧真实 Quest/RViz 验证和 B 侧 `rm65_teleop_adapter`。
- 真实 Quest 右手柄已通过当前链路驱动右 RM65 产生实际平移运动。
- 当前 demo 范围仅为右手/右臂平移；旋转、夹爪、左臂和完整安全验收仍未完成。
- GitHub 默认 `hardware.yaml` 保持较保守参数；现场未提交的 `0.5 / 0.010 / 0.10` 调参值未作为默认值合入。

## 2026-09-20 — Real Quest translation validation

- 真实 Quest + RViz 的 deadman、release freeze 和无跳变重新锚定现场测试通过。
- Quest 物理方向确认：`+X=前、+Y=左、+Z=上`。
- RM65 当前坐标方向现场点动确认：`+X=上、+Y=后、+Z=右`。
- 得到平移增量映射：`RM(x,y,z) = (Qz,-Qx,-Qy)`。

## 2026-09-20 — Private collaboration snapshot

- 导入 Quest2ROS2、quest2ros 与 ros_tcp_communication 现场源码快照。
- 保留现场通信 compatibility 补丁和来源追溯。
- 导入右手虚拟目标 bridge、测试和 A/B 协作文档。

## 后续记录要求

每个可验证功能至少记录：改了什么、为什么修改、如何测试及实际结果、未验证内容和剩余安全限制、未合并时所在 branch 与 commit SHA。
