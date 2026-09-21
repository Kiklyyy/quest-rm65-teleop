# Changelog

## 2026-09-20 — Real Quest translation validation

- 真实 Quest + RViz 的 deadman、release freeze 和无跳变重新锚定现场测试通过。
- Quest 物理方向确认：`+X=前、+Y=左、+Z=上`；bridge 的 identity mapping 无需为 Quest 自身修改。
- 用户通过 RM65 示教器在当前所选工作坐标系中实际点动确认：`+X=上、+Y=后、+Z=右`。
- 得到候选平移增量映射：`RM(x,y,z) = (Qz,-Qx,-Qy)`；这不是绝对位置变换。
- RM65 adapter、实际控制 frame 和命令单位仍待 B 侧验证；本次仅更新文档，没有重新运行 56 项测试。

## 2026-09-20 — Private collaboration snapshot

- 将三个现场源码来源导入普通单仓库结构，保留上游 LICENSE 和完整来源追溯。
- 保留 Quest2ROS2 的 `quest2ros2_msg -> quest2ros` manifest/import compatibility 修改。
- 保留 ROS TCP Endpoint 的当前现场补丁：
  - `publisher.py`：ROS 2 CDR 与 legacy Quest 数据分流；
  - `ros_msg_converter.py`：legacy Header、动态 Pose 偏移和长度校验；
  - `server.py`：JSON 末尾 NUL 清理。
- 导入右手虚拟目标 bridge：相对 1:1 平移、deadman、严格 `>0.2s` Pose watchdog、rearm 锁定、50 Hz Pose/Marker。
- 导入 56 项最终测试；review 补强 endpoint 数量约束和 NaN/±inf 时间防御。
- 新增 STATUS、接口契约、来源追溯、A/B 进度文件和 AGENTS 协作规则。

## 后续记录要求

每个可验证功能至少记录：

1. 改了什么；
2. 为什么修改；
3. 如何测试及实际结果；
4. 未验证内容和剩余安全限制；
5. 未合并时所在 branch 与 commit SHA。

不要把 WIP、模拟结果或计划描述写成已验收事实。
