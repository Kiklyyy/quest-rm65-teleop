# Right-arm 6DoF orientation control design

- 日期：2026-09-22
- 状态：已批准需求的正式设计；production implementation 尚未开始
- 基线：`origin/main` at `f4693121c8a0943039d393323b2da44de985c56e`
- 范围：Quest 右手腕姿态到右 RM65 姿态的扩展，同时保留已验证的 XYZ 平移链路

## 1. 目标与成功标准

当前系统已把真实 Quest 右手位置映射为右 RM65 的 XYZ 平移。本功能把同一段 Grip 操作升级为一个 6DoF 相对 Pose 控制会话：

- 按住右手中指 Grip，即 `/q2r_right_hand_inputs.press_middle`，手的位置控制平移，手腕姿态同时控制机械臂姿态；两者可以在同一控制周期共同变化。
- 松开 Grip 后停止机器人 teleop，并保留现有 stop 与 `REARM_REQUIRED` 语义。
- 重新握住时同时重采集平移锚点和姿态锚点；松开期间的移动、旋转不进入下一段命令，重握首帧不能产生位置或姿态跳变。
- 最终仍只生成一个 `geometry_msgs/Pose` 形式的 RM65 command；姿态不得建立第二条绕过安全门的命令路径。

本设计中的旋转尚未经过真实 Quest quaternion probe 或真实 RM65 旋转验收。已验证的硬件事实只包括现有右臂 XYZ 平移链路。

## 2. 当前代码事实

基线代码与接口契约给出以下事实：

1. 真实 Quest → ROS 2 → right target bridge → adapter → 右 RM65 的 XYZ 平移已现场跑通。
2. deadman 是 `press_middle`，按下/松开阈值为 `0.60 / 0.40`，中间区保持前一语义状态。
3. `quest_right_target_bridge` 只读取 raw Quest Pose 的 position；`/quest_right_target_pose` 的 orientation 固定为 identity。
4. `rm65_teleop_adapter` 已直接订阅 `/q2r_right_hand_pose`，但当前 callback 只检查 position 是否有限，没有保存 raw Quest orientation。
5. 当前 `AdapterLogic` 在 ACTIVE 时计算相对平移，每周期把 `last_command.orientation` 固定回 robot anchor orientation。
6. adapter 将 preview 的 `geometry_msgs/Pose` 直接写入 `rm_ros_interfaces/Cartepos.pose`；RM65 command 因而使用 Pose quaternion。
7. 当前 motion profiles 只覆盖 `translation_scale`、`max_velocity_mps`、`max_step_m`、`max_anchor_distance_m`。

设计前 baseline 在隔离 worktree 中通过：四个相关 package 构建成功；adapter 为 37 个功能测试加 4 个 CTest wrapper、零失败；Quest bridge 为 63 个 pytest、零失败。没有启动 RM driver 或真实机械臂。

## 3. 架构边界

### 3.1 保持既有 translation path

现有链路和职责不变：

```text
Quest position
  -> quest_right_target_bridge
  -> /quest_right_target_pose.position
  -> rm65_teleop_adapter translation logic
```

`/quest_right_target_pose` 继续主要承担已验证的平移 target。bridge 不接管机器人姿态，不改变其 identity orientation，不改变 50 Hz 发布、deadman、watchdog 或 re-anchor 行为。本功能不修改 Quest translation bridge 的 production source、现有语义或测试期望。

### 3.2 Orientation 直接进入 adapter

新增姿态链路为：

```text
/q2r_right_hand_pose.pose.orientation
  -> rm65_teleop_adapter raw Quest pose subscription
  -> quaternion validation / relative orientation mapping
  -> existing AdapterLogic safety state machine
  -> the same preview and optional Cartepos Pose command
```

adapter 的 raw Quest Pose callback 必须保留 quaternion，而不能再只保留 position validity。orientation 计算与 translation 计算在同一 ACTIVE cycle 完成，最终组成同一个 Pose command。任何姿态错误都必须在现有安全状态机和唯一 command publisher 之前被拦截。

## 4. 坐标系与 quaternion 约定

### 4.1 Rotation 表示

核心计算使用单位 quaternion 或 3×3 rotation matrix，不使用 Euler angle 做累计、插值或内部状态。

本设计采用以下固定约定：

- ROS quaternion 存储顺序为 `(x, y, z, w)`。
- quaternion 乘法为 Hamilton product，记为 `⊗`。
- `R(q)` 是 column-vector、active rotation matrix。
- Quest 的 `R_Q` 把右手柄局部坐标中的向量旋转到 Quest world。
- Robot 的 `R_R` 把末端工具局部坐标中的向量旋转到 RM base。
- Pose header 不用于推导变换；以上语义必须由真实 Quest dry-run probe 验证。

`q` 与 `-q` 表示完全相同的 orientation。所有角距离和插值都必须使用 shortest path。

### 4.2 Quest → RM base 映射

沿用已经真机确认的平移映射：

```text
    [ 0  0  1]
M = [-1  0  0]
    [ 0 -1  0]
```

其物理含义为：

```text
Quest +X forward -> RM65 -Y
Quest +Y left    -> RM65 -Z
Quest +Z up      -> RM65 +X
```

`M M^T = I` 且 `det(M) = +1`，所以它是 proper rotation。实现 orientation 前必须验证配置中的 mapping 仍满足有限、正交和正行列式要求；不能把 reflection 当作 rotation 使用。

## 5. 双锚点与相对旋转数学

Grip 上升沿从 ARMED 进入 ACTIVE 时，同时采集：

- translation 的既有 Quest target position anchor 与 robot position anchor；
- raw Quest orientation anchor `q_Q0`；
- robot feedback orientation anchor `q_R0`。

归一化后的矩阵分别记为 `R_Q0 = R(q_Q0)` 和 `R_R0 = R(q_R0)`。当前 Quest orientation 为 `q_Q`，矩阵为 `R_Q`。

### 5.1 明确的 relative rotation 顺序

Quest world-frame 相对旋转定义为：

```text
Delta R_Q = R_Q * R_Q0^T
```

等价的 Hamilton quaternion 顺序是：

```text
q_delta_Q = q_Q ⊗ inverse(q_Q0)
```

因为该定义满足：

```text
R_Q = Delta R_Q * R_Q0
```

它表示“在 Quest world 中，把 anchor orientation 左乘旋转到当前 orientation”。本设计不采用 `R_Q0^T * R_Q` 的 body-frame delta，也不允许两种语义混用。

### 5.2 rotation scale

第一版：

```text
rotation_scale = 1.0
```

相对旋转先走 shortest-path axis-angle / quaternion log-exp 缩放：若 `Delta R_Q` 的最短旋转为单位轴 `u_Q`、角度 `theta_Q in [0, pi]`，则缩放结果为绕同一轴旋转 `rotation_scale * theta_Q`。这不是 Euler angle 分量缩放。第一版因此保持 1:1：手腕相对转约 30°，机器人 desired 相对转约 30°。

### 5.3 映射和 robot anchor composition

缩放后的 Quest 相对旋转映射到 RM base：

```text
Delta R_RM = M * Delta R_Q_scaled * M^T
```

最终 desired robot orientation 固定为：

```text
R_des = Delta R_RM * R_R0
```

即 mapped relative rotation **左乘** robot anchor。它是 RM base/world-frame relative rotation：Quest 在 Quest world 绕某物理轴旋转多少，RM65 就在 RM base 绕 `M` 映射后的物理轴产生相同的相对旋转。

正向 basis rotation 的预期是：

```text
Quest +X 右手定则旋转 -> RM base -Y 轴旋转
Quest +Y 右手定则旋转 -> RM base -Z 轴旋转
Quest +Z 右手定则旋转 -> RM base +X 轴旋转
```

实现前必须用包含非交换旋转的单元测试同时固定 `Delta R_Q` 的乘法顺序和 `R_des` 的左乘顺序；只测试 identity anchor 不足以发现左右乘错误。

## 6. Quaternion 输入安全

每个 raw Quest Pose 样本都必须经过以下流程：

1. 四个分量全部为 finite；NaN 或 Inf 立即判为 invalid。
2. 用数值稳定的方法计算 norm；norm 小于 `1e-6` 判为 invalid。
3. 合法 quaternion 归一化后才进入 anchor、jump guard、mapping 或 command 计算。
4. 与比较基准的 dot 小于 0 时取反，统一到同一 hemisphere。
5. 角距离使用 `2 * acos(clamp(abs(dot), 0, 1))`，所以 `q -> -q` 的距离为 0，不会被判为 360° jump。
6. robot feedback anchor quaternion 和每个生成的 command quaternion 同样必须 finite、可归一化且最终保持单位长度。

raw pose callback 必须逐个处理收到的 quaternion 样本，不能只在 200 Hz control timer 中抽样最终缓存值而跳过中间帧。可测试的 quaternion helper/continuity tracker负责产生 latest normalized orientation 和 invalid/jump event；最终是否进入 FAULT、stop 和 rearm 仍由 `AdapterLogic` 决定。

新收到的 invalid quaternion 不更新上一帧合法 orientation。若 ACTIVE 中收到 invalid quaternion：

- 本周期不产生 preview 或真实 RM command；
- 进入 latched `FAULT`，reason 明确为 orientation data invalid；
- 请求既有 stop path；
- 只能沿现有 clear-fault、release、再 press 流程恢复。

缺失或超时仍走现有 freshness watchdog 与 `REARM_REQUIRED`，不与“收到 invalid 数据”混为同一故障。

## 7. ACTIVE 状态行为

### 7.1 激活与无跳变

从 ARMED 进入 ACTIVE 时：

- 要求 target、raw Quest pose、Inputs 和 robot feedback 全部 fresh，command path ready；
- 捕获 position 与 orientation 双锚点；
- `last_command` 设为当前 robot feedback Pose，其中 orientation 归一化为 `q_R0`；
- orientation continuity baseline 设为 `q_Q0`；
- 首个 command 等于 robot anchor，不产生位置或姿态跳变。

Grip 松开立即退出 ACTIVE、请求 stop，且不再发送 command。松开期间的位置和姿态变化只更新最新输入缓存，不改变 frozen command。下一次 release → press 使用当时最新的合法 Quest orientation 和 robot feedback orientation 建立新锚点。

### 7.2 同周期组合

每个有效 ACTIVE cycle 依次完成：

1. 检查所有既有 freshness、command-path 和 control-period 条件；
2. 验证本次 raw Quest quaternion 与连续帧 jump；
3. 计算既有 translation desired 和 translation safety envelope；
4. 计算 orientation desired、anchor angle guard 和 angular limiter；
5. 只有 translation 与 orientation 都通过时，才原子地更新一个 `last_command` 并发布同一个 Pose。

任一分量触发 safety violation 时，本周期两者都不发布；不能在姿态 fault 时继续发平移，也不能在平移 fault 时继续发姿态。

## 8. Rotation safety envelope

### 8.1 Anchor angle limit

从本次 Grip orientation anchor 到当前 Quest orientation 的 shortest relative rotation，经 `rotation_scale` 和 `M` 映射后，其角度不得超过：

```text
max_anchor_angle_rad = pi / 2
```

mapping conjugation 本身保持角度；第一版 `rotation_scale=1.0` 时，Quest 和 RM mapped relative angle 相同。边界等于 90° 时允许，严格大于 90° 时进入 latched FAULT、请求 stop，且不再发送越来越大的 orientation command。该 guard 对应 translation 的 `max_anchor_distance_m`。

### 8.2 Unexpected orientation jump guard

维护上一帧合法 raw Quest orientation。ACTIVE 中每两个连续收到的合法样本计算 shortest angular distance。严格超过：

```text
unexpected_orientation_jump_rad = pi / 4
```

即超过 45° 时，视为 unexpected orientation jump：本周期无 command、进入 latched FAULT、请求 stop。等于阈值允许。`q -> -q` 因 hemisphere/absolute-dot 处理不会触发此 guard。

非 ACTIVE 期间的旋转不触发 jump fault；进入 ACTIVE 时 baseline 重置为 `q_Q0`，保证松开期间转腕后重握不误报跳变。

45° 是第一版可配置安全参数，不是已完成真机验证的数值。

### 8.3 Per-cycle angular limiting

`desired.orientation` 不得一步直接发送。以单位 quaternion `q_last` 和 `q_des` 为例：

1. 若 `dot(q_last, q_des) < 0`，取 `q_des = -q_des`，锁定 shortest path。
2. 计算 shortest angle `theta_cmd = 2 * acos(clamp(dot, 0, 1))`。
3. 计算本周期允许角度：

```text
allowed_angle = min(
    max_angular_step_rad,
    max_angular_velocity_rad_s * dt
)
```

4. `theta_cmd <= allowed_angle` 时直接到 `q_des`。
5. 更远时使用 shortest-path SLERP：`slerp(q_last, q_des, allowed_angle / theta_cmd)`。
6. 结果归一化后写回 `last_command.orientation`。

第一版参数：

```text
max_angular_velocity_rad_s = pi / 2
max_angular_step_rad       = 0.01
```

0.01 rad 是第一版建议的 per-cycle cap，不是真机调优结论。在 200 Hz 名义周期 `dt=0.005 s` 时，速度项约为 `0.00785 rad`，因此取两者较小值。非有限、非正 `dt` 或非有限、非正 allowed angle 沿用现有 invalid-control/motion-limit fault 风格。

## 9. Translation 与既有安全行为保持不变

以下行为和参数不因 orientation 功能改变：

- mapping `RM(dx,dy,dz) = (Qdz, -Qdx, -Qdy)`；
- `translation_scale`；
- `safe / normal / fast` motion profiles 及其当前值；
- `max_velocity_mps`、`max_step_m`、`max_anchor_distance_m`；
- workspace bounds 与 unexpected translation target jump；
- `press_middle` 的 `0.60 / 0.40` hysteresis；
- release stop 与 release → press rearm；
- Inputs、raw Quest pose、target、robot feedback 四个 watchdog；
- command-path uniqueness；
- control-period fault；
- `stop_repeat_count`；
- dry-run 时不创建 hardware command publisher 的保证。

姿态功能复用同一个 ACTIVE gate、preview publisher、hardware publisher 和 stop publisher，不新增绕过 gate 的 topic、timer 或命令源。

## 10. 参数与配置归属

新增 adapter 参数采用 rad 和 rad/s：

| 参数 | 第一版值 | 语义 |
|---|---:|---|
| `rotation_scale` | `1.0` | shortest relative angle 的比例 |
| `max_angular_velocity_rad_s` | `pi / 2` | 角速度上限 |
| `max_angular_step_rad` | `0.01` | 单 control cycle 最大角步长 |
| `max_anchor_angle_rad` | `pi / 2` | 单次 Grip mapped relative angle 上限 |
| `unexpected_orientation_jump_rad` | `pi / 4` | 连续 raw Quest orientation 的 jump guard |

实现中 YAML 使用十进制 rad 数值，README 可同时标注 90°、45° 方便阅读。所有参数必须 finite；scale 和三个 limit 必须为正，jump/anchor angle 还必须不大于 `pi`。

这些参数属于 orientation envelope，放入 adapter 的 `dry_run.yaml` 与 `hardware.yaml` base config。它们不加入 translation motion profile allowlist，不改变 profile 文件或 profile 选择语义。translation 和 orientation 继续共用已验证的 `mapping` 矩阵。

## 11. 状态机、watchdog 与 command path

已有状态机保持 `DISABLED -> ARMED -> ACTIVE`、`REARM_REQUIRED` 和 latched `FAULT`：

- timeout、deadman release 的状态语义保持现状；
- invalid quaternion、orientation jump、anchor angle violation 属于数据/运动 envelope violation，使用 latched FAULT；
- 从 ACTIVE 进入上述 fault 时 `stop_requested=true`，且没有本周期 command；
- fault clear 仍要求 deadman released，随后继续要求 release → press 重采锚点；
- orientation 不改变 hardware triple gate，也不改变 command/stop topic 的 publisher/subscriber uniqueness 检查。

当前 `mapping_verified=true` 的历史证据是 translation mapping 验收，不能描述成 orientation 已真机验证。代码完成不等于授权真实旋转；真实 RM65 rotation 仍受现有硬件 gate、现场操作者授权和第 13 节验证顺序约束。

## 12. TDD 与自动测试要求

未来 implementation 必须先写失败测试，再写 production code。至少覆盖：

### A. Quaternion math

- identity delta；
- 已知 90° rotations；
- 非交换 anchor/current 组合，固定 `q_Q ⊗ inverse(q_Q0)` 顺序；
- `q` 与 `-q` 等价；
- normalization 与单位输出；
- zero/too-small norm、NaN、Inf；
- shortest angular distance；
- shortest-path SLERP，包括跨 hemisphere。

### B. Mapping

- Quest +X、+Y、+Z basis rotation 分别映射到 RM -Y、-Z、+X；
- `M * R * M^T` 的正交性、`det=+1` 和旋转方向；
- 非 identity `R_R0` 场景固定 `R_des = Delta R_RM * R_R0` 左乘顺序。

### C. Anchoring

- first press 的 position/orientation 都无 jump；
- release freeze/stop；
- released 时 move/rotate 被忽略；
- repress 同时重采 position/orientation anchor 且无 jump；
- translation 与 rotation 同周期组成一个 Pose。

### D. Safety

- `max_anchor_angle_rad` 的边界值和超限；
- angular velocity limit；
- angular step limit；
- 两个 angular limit 同时存在时取较小值；
- orientation jump guard 边界、超限与 `q -> -q`；
- invalid/nonfinite quaternion；
- invalid orientation 时无 preview/hardware command；
- Quest pose timeout、stop、fault clear 和 release → press rearm；
- control-period、command-path 和既有 watchdog 回归。

### E. Regression

- 现有 XYZ translation tests 不改行为且保持 green；
- 现有 deadman tests 保持 green；
- motion profile tests 保持 green，profile allowlist 仍为四个 translation 参数；
- Quest bridge tests 保持 green，bridge 仍忽略 input orientation 并输出 identity orientation；
- dry-run 产生 orientation preview，但 `/right/rm_driver/movep_canfd_cmd` publisher count 仍为 0。

## 13. 首轮真实输入与真机验证策略

用户尚未亲自确认 Quest quaternion 语义；实验室此前有相关系统成功运行，所以这不阻塞 TDD 和 dry-run implementation，但会阻塞真实 RM65 rotation。

真实 Quest dry-run probe 必须先完成并留存证据：

1. echo/观察 `/q2r_right_hand_pose.pose.orientation`；
2. 静止时 quaternion 稳定；
3. 转动手腕时 quaternion 连续变化；
4. norm 合理，归一化后稳定；
5. `q/-q` 不引起 preview jump；
6. preview orientation 按预期物理轴和方向变化。

之后才能在现场授权下按以下顺序测试真实机械臂：

1. no tool / no payload；
2. 单轴约 ±5°；
3. 单轴约 ±10°；
4. 三个物理旋转方向逐个确认；
5. 组合旋转；
6. translation + rotation 同时操作。

禁止首次测试就做大幅度或快速转腕。45° jump guard、90° anchor limit 和 0.01 rad step 都是第一版安全 envelope 参数，不得写成真机已验证结论。

## 14. 明确不在范围内

本功能不包含：gripper、`press_index`、A/B button actions、Home、Recenter button、left arm、dual arm、MoveIt/CuRobo collision avoidance integration、tool task 或 box opening logic。

本轮 checkpoint 只包含本设计文档，不包含 production source、test、config 或 launch 修改，也不启动 RM driver 或真实机械臂。

## 15. 实现验收边界

未来实现达到可评审状态时，应同时满足：

- quaternion 乘法、frame mapping 和 robot anchor 左乘顺序已由数学测试锁定；
- orientation 的 invalid/jump/anchor/limiter 均位于现有 safety gate 内；
- translation 行为和 motion profiles 零回归；
- dry-run 可观察 6DoF preview 且没有 hardware command publisher；
- 真实 Quest probe 完成前，不执行真实 RM65 rotation；
- 真实硬件结果只按实际完成的逐级测试记录，不把 preview 或数学测试描述成硬件验证。
