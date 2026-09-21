# A — VR Mapping Progress

- 负责人：A 同学
- 建议分支：`feat/vr-mapping`

## 当前基线

- Quest2ROS2 来源：`9ca76a808d4cebecbb633e231071301259d71cd9`。
- 已有右手虚拟目标 bridge、纯状态逻辑、Pose/Marker 输出和测试。
- 当前映射为仅平移、1:1、identity 轴映射。

## 已完成

- `button_lower` deadman：按住跟随、松开冻结、重按重新锚定。
- Pose gap 严格 `>0.2s` 后锁定并要求 release→press。
- press-before-pose、stale pose、重复回调、非单调和 NaN/±inf 时间防御。
- `world` 下 50 Hz 虚拟 Pose/Marker。
- 最终源码基线包含 47 项逻辑测试和 9 项 adapter 测试。
- 真实 Quest + RViz deadman 验收：未按时冻结、按住时跟随、松开后冻结、重新按下无跳变并重新锚定。
- 真实 Quest 物理方向验收：`+X=前、+Y=左、+Z=上`；当前 identity mapping 无需为 Quest 自身修改。
- RM65 示教器当前所选工作坐标系人工点动确认：`+X=上、+Y=后、+Z=右`。
- 候选 translation delta mapping：`RM(dx,dy,dz) = (Qdz,-Qdx,-Qdy)`。

## 待现场验收/确认

- 网络抖动和真实断流体验。
- B 侧 adapter 实际笛卡尔命令 frame 是否等于示教器当前所选工作坐标系。
- B 侧实际控制接口使用 meter 还是 mm。

## 待实现/对齐

- 明确的 enable/validity 接口。
- Inputs 独立 watchdog。
- 与 B 同学共同确认候选 delta mapping、单位和机器人当前位姿锚定契约，但不在 bridge 中直接写 RM65 命令。
- Quest 旋转映射；第一版真机平移 demo 保持机器人当前末端姿态。

## 当前 demo 范围

当前关键路径是右手柄到右臂的平移 demo。旋转、左臂、夹爪、视觉和优化不属于本轮关键路径；当前进展仍止于 virtual target，不表示 RM65 真机遥操作已完成。

## 更新规则

每次可验证变更写明 branch、commit、测试命令与结果、未验证部分。接口变更先更新 `docs/INTERFACE.md` 并与 B 同学对齐。
