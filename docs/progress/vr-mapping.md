# A — VR Mapping Progress

- 负责人：A 同学
- 分支：`feat/vr-mapping`

## 已完成

- 右手虚拟目标 bridge。
- `button_lower` deadman：按住跟随、松开冻结、重按重新锚定。
- Pose gap watchdog 与 rearm。
- `world` 下 50 Hz 虚拟 Pose/Marker。
- 真实 Quest + RViz deadman 验收通过。
- 真实 Quest 物理方向：`+X=前、+Y=左、+Z=上`。
- RM65 当前物理方向：`+X=上、+Y=后、+Z=右`。
- translation delta mapping：`RM(dx,dy,dz)=(Qdz,-Qdx,-Qdy)`。
- A/B 联调后，真实 Quest 已成功驱动右 RM65 产生实际平移运动。

## 待实现/优化

- Quest rotation。
- 网络抖动与真实断流的更完整验收。
- 左臂、夹爪、视觉和更高级交互。

A 侧当前平移 demo 任务可视为已完成；后续进入体验与能力扩展阶段。
