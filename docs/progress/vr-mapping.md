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

## 待现场验收

- 真实 Quest + RViz：前后、左右、上下的轴与符号。
- 实际按压/松开/重新锚定连续性。
- 网络抖动和真实断流体验。

## 待实现/对齐

- 明确的 enable/validity 接口。
- Inputs 独立 watchdog。
- 与 B 同学共同确定虚拟 frame 到机器人 base frame 的契约，但不在 bridge 中直接写 RM65 命令。

## 更新规则

每次可验证变更写明 branch、commit、测试命令与结果、未验证部分。接口变更先更新 `docs/INTERFACE.md` 并与 B 同学对齐。
