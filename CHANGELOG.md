# Changelog

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
