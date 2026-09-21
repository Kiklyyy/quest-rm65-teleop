# Project Status

更新日期：2026-09-20

## 基线来源

| 组件 | 来源基线 | 本地状态 |
|---|---|---|
| Quest2ROS2 | `feat/quest-right-target-bridge` @ `9ca76a808d4cebecbb633e231071301259d71cd9` | 包含两个未提交但现场必需的 `quest2ros` compatibility 修改 |
| quest2ros | 非 Git 现场包 | 完整导入 4 个构建/消息文件 |
| ros_tcp_communication | `main` @ `5c5f08956d4bc7a045c321214b0bc03c63eb20a7` | 包含 3 个现场通信补丁，排除 `.bak` |

来源、补丁和哈希见 [docs/SOURCES.md](docs/SOURCES.md)。

## 当前总体阶段

Quest 右手柄到 ROS 2 虚拟目标的 Stage 2 实现，以及真实 Quest + RViz 的右手平移交互和物理方向现场验收均已完成。当前链路仍止于 virtual target。RM65 adapter 尚未实现；实际控制 frame、命令单位、真机写入、停止行为、断线保护和命令源互斥均未验证。

## 用户已经实测

- Quest 可以连接 Ubuntu ROS TCP Endpoint。
- `/q2r_right_hand_pose`、`/q2r_right_hand_inputs`、`/q2r_right_hand_twist` 曾有真实数据。
- 右手 Pose 曾实测约 75 Hz。该数值不是延迟、可靠性或安全性保证。
- 手柄按钮、扳机和摇杆输入曾确认正常。
- 真实 Quest + RViz 已验证：`button_lower` 未按时 target 冻结，按住时跟随，松开后立即冻结，松开期间移动再按下时无位置跳变并从当前位置重新锚定。
- 真实手柄逐轴验证：现实向前使 target X 增加，向右使 target Y 减少，向上使 target Z 增加。因此 Quest/virtual world 的物理含义为 `+X=前、+Y=左、+Z=上`，现有 identity mapping 无需为 Quest 自身修改。
- 用户通过 RM65 示教器在**当前所选工作坐标系**中实际点动确认：`RM +X=上、RM +Y=后、RM +Z=右`。该结果尚不能证明 adapter 实际笛卡尔命令使用同一 frame。

## 此前 Codex 在机器人 worktree 中报告并留有命令证据

- 最终 56 项自动化测试通过：47 项纯状态逻辑、9 项 ROS adapter。
- `q2r2_bringup` 限定构建成功，bridge executable 可安装运行。
- 无输入时初始目标为 `(0.5, 0.0, 0.5)`、frame 为 `world`、姿态为 identity，输出约 50 Hz。
- SimulationInput smoke 中 x/y 连续变化、z 保持 0.5；无 RM65 endpoint。
- 非有限时间输入的安全缺陷经 review 发现，并由提交 `9ca76a8` 修复后通过 scoped re-review。

这些证据来自原机器人 feature worktree，不等同于本次 Windows 发布目录重新构建。

## 本轮发布实际执行的检查

- 只读核对三个现场来源的 HEAD、branch、dirty diff 和 remote。
- 以 HEAD archive 加精确 dirty overlay 导出源码，导出前后重新核对来源状态。
- 远端与本地按相对路径计算文件数量和 SHA-256 聚合清单，确认导出一致。
- 从发布副本排除 `.git`、build/install/log、`.worktrees`、`.superpowers`、缓存、`.bak`、编辑器临时文件和凭据类路径。
- 保留两份上游 Apache-2.0 LICENSE；如实记录 `quest2ros` 许可证未明确。
- 检查源码清单、大文件、敏感字符串、gitlink/submodule 风险与文档一致性。

本轮没有在新发布目录重新运行 ROS 构建、56 项测试、真实 Quest 或 RM65。

## 已完成

- TCP Endpoint 能接收当前 Quest 数据格式的现场补丁。
- 独立纯状态机：deadman、相对位移、Pose watchdog、rearm、异常时间防御。
- 右手虚拟 Pose/Marker bridge 与 console entry。
- 自动化测试和多轮独立 review。
- 真实 Quest + RViz 的 deadman、release freeze、无跳变重新锚定和物理 XYZ 方向现场验收。
- 基于 Quest 与 RM65 当前工作坐标方向得到候选平移增量映射：`RM(dx,dy,dz) = (Qdz,-Qdx,-Qdy)`。
- 私有协作源码快照与交接文档。

## 待验证

- 真实网络抖动和断流体验。
- RM65 adapter 实际笛卡尔命令 frame 是否与示教器当前所选工作坐标系一致。
- RM65 实际命令接口使用 meter 还是 mm。
- `world` 到 RM65 实际控制 frame 的最终变换与标定。
- 显式 enable/validity 接口及 Inputs 独立 watchdog。

## 尚未实现或验收

- `rm65_teleop_adapter`。
- Quest 旋转映射；第一版真机平移 demo 应保持机械臂当前末端姿态。
- RM65 当前位姿锚定、限速/限位、碰撞约束和控制周期。
- 真机急停、断线停止、驱动互斥和唯一命令源。
- 任何“Quest 输出直接驱动 RM65”的生产链路。

## 当前 demo 关键路径

A 侧已提供右手柄到右臂平移 demo 所需的真实 Quest 通信、right target bridge、deadman、release freeze、无跳变重新锚定、Pose watchdog 自动化验证、真实 Quest/RViz 交互验收、Quest 物理方向验收和候选 Quest→RM 工作坐标平移变换。旋转、左臂、夹爪、视觉和优化不属于本轮快速 demo 的关键路径。
