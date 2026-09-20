# Source Provenance

本仓库是 2026-09-20 从实验室现场目录导出的源码快照。来源 SHA 用于追溯，不表示这些 SHA 构成新仓库的原生提交历史，也没有改写任何上游历史。

## 来源对应关系

| 新仓库路径 | 现场来源 | 上游/来源身份 |
|---|---|---|
| `src/Quest2ROS2/` | `/home/lh/quest2ros2_ws/.worktrees/quest-right-target-bridge` | `https://github.com/Taokt/Quest2ROS2.git`，feature HEAD `9ca76a808d4cebecbb633e231071301259d71cd9` |
| `src/quest2ros/` | `/home/lh/quest2ros2_ws/src/quest2ros` | 非 Git 的现场自定义消息包 |
| `src/ros_tcp_communication/` | `/home/lh/quest2ros2_ws/src/ros_tcp_communication` | `https://github.com/guguroro/ros_tcp_communication.git`，HEAD `5c5f08956d4bc7a045c321214b0bc03c63eb20a7` |

## Quest2ROS2

原 feature 分支：`feat/quest-right-target-bridge`。

关键来源提交：

- `4f792342c69c90e62921b661ef97b5ff57f572b8` — bridge 设计规范；
- `af42473083f02289d73da7d27759cdd63f27ebee` — implementation plan；
- `fe9b945a3a3ca71688ce7cb756990d4edb2054cf` — 纯状态逻辑；
- `8ca4a21902c9c46b37e39ac1a0964e3377d812a3` — ROS bridge；
- `d61ac060e2e538aa9cc3635f4e1c1ab9488af39e` — endpoint 数量测试补强；
- `9ca76a808d4cebecbb633e231071301259d71cd9` — NaN/±inf 时间防御。

HEAD archive 之后精确覆盖了现场 working tree 的两项必要 compatibility 修改：

- `package.xml`：依赖 `quest2ros2_msg` 改为 `quest2ros`；
- `q2r2_bringup/ros2quest.py`：消息 import 从 `quest2ros2_msg.msg` 改为 `quest2ros.msg`。

最终导入清单：24 个文件，相对路径 SHA-256 聚合值：

```text
e1a4fbbdcc6d23aa34ddac88d14de26788ebdb0aabb18f1487170d83f4224bc8
```

`src/Quest2ROS2/LICENSE` 保留原 Apache License 2.0。

## quest2ros

完整导入：

- `CMakeLists.txt`
- `package.xml`
- `msg/OVR2ROSInputs.msg`
- `msg/OVR2ROSHapticFeedback.msg`

最终导入清单：4 个文件，相对路径 SHA-256 聚合值：

```text
b7dd57f63caa04656864809e2ef05e8ae4c2cab3b2fe53ad374201ea83c863e8
```

该目录没有独立 LICENSE，且 `package.xml` 中仍为 `TODO: License declaration`。本次导入不推断或改写其授权状态；协作方在对外再分发前必须先确认许可证。

## ros_tcp_communication

以 HEAD archive 为基础，精确覆盖现场 working tree 的三个补丁文件：

- `ros_tcp_endpoint/publisher.py`：检测 ROS 2 CDR encapsulation header；CDR 使用 `deserialize_message`，其他数据走 legacy converter；
- `ros_tcp_endpoint/ros_msg_converter.py`：解析 legacy ROS1-style Header、动态计算 Pose 偏移并验证长度；
- `ros_tcp_endpoint/server.py`：JSON decode 后去除尾部 NUL。

未导入现场未跟踪文件 `ros_tcp_endpoint/ros_msg_converter.py.bak`。

剔除上游跟踪的编辑器 swap 文件后，最终导入清单为 31 个文件，相对路径 SHA-256 聚合值：

```text
2ed915c5c6ad8326e9bc7bd8f706ddd92a0ef6ab46b62f9c806580c6c40aa530
```

`src/ros_tcp_communication/LICENSE` 保留原 Apache License 2.0。

## 导出卫生处理

导出前先核对完整来源快照与本地副本的文件数量和聚合哈希，随后只在发布副本中剔除：嵌套 `.git`、build/install/log、`.worktrees`、`.superpowers`、`__pycache__`、`*.pyc`、`.pytest_cache`、`.vs`、`*.bak`、编辑器 swap 文件及临时归档。现场来源未删除、清理、切换分支或修改 remote。
