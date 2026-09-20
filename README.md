# Quest–RM65 Teleoperation Collaboration Snapshot

这是一个用于两位同学及各自 GPT/Codex 协作的私有源码快照仓库。它汇集当前实验室实际使用的 Quest2ROS2、`quest2ros` 自定义消息包和带现场补丁的 ROS TCP Endpoint，并记录接口、验证状态和分工。

> **当前安全边界：** 已实现的链路止于 Quest 右手柄到虚拟 Pose/Marker。尚未打通、验收或授权 RM65 真机遥操作。任何 push 都只是代码同步，不代表部署、重启或启用机器人。

## 目录结构

| 路径 | 作用 |
|---|---|
| `src/Quest2ROS2/` | Quest 输入、模拟输入、右手虚拟目标 bridge 及其单元测试 |
| `src/quest2ros/` | `OVR2ROSInputs` 与 `OVR2ROSHapticFeedback` 自定义消息定义 |
| `src/ros_tcp_communication/` | Unity/Quest 到 ROS 2 的 TCP Endpoint，包含当前现场通信补丁 |
| `docs/` | 来源追溯、接口契约和 A/B 两条开发进度线 |

详细状态见 [STATUS.md](STATUS.md)，接口与安全约束见 [docs/INTERFACE.md](docs/INTERFACE.md)，版本变化见 [CHANGELOG.md](CHANGELOG.md)。

## 环境基线

- Ubuntu 22.04
- ROS 2 Humble
- 系统 Python 3.10：`/usr/bin/python3`
- 现场使用 `ROS_DOMAIN_ID=42`

不要使用 Conda Python 运行 `rclpy` 或 `colcon`。

## 在独立工作空间构建

以下命令只用于新的 clone，不要在实验室现场已有工作目录中覆盖执行：

```bash
git clone https://github.com/Kiklyyy/quest-rm65-teleop.git
cd quest-rm65-teleop

conda deactivate 2>/dev/null || true
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42
test "$(command -v python3)" = "/usr/bin/python3"

/usr/bin/colcon build \
  --symlink-install \
  --packages-select quest2ros ros_tcp_endpoint q2r2_bringup

source install/setup.bash
```

构建后可在不加载任何 RM65 controller 的情况下运行虚拟目标 bridge：

```bash
ros2 run q2r2_bringup quest_right_target_bridge
```

运行新增自动化测试：

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
/usr/bin/python3 -m pytest -p no:cacheprovider -q \
  src/Quest2ROS2/test/test_quest_right_target_logic.py \
  src/Quest2ROS2/test/test_quest_right_target_bridge.py
```

本次发布只在 Windows 独立目录整理和审计源码，没有在这个新 clone 中重新运行 ROS 构建或测试；此前机器人 worktree 的验证证据及其边界记录在 [STATUS.md](STATUS.md)。

## 新旧路径

| 含义 | 现场旧路径 | 新仓库路径 |
|---|---|---|
| Quest2ROS2 | `/home/lh/quest2ros2_ws/.worktrees/quest-right-target-bridge` | `src/Quest2ROS2/` |
| 自定义消息 | `/home/lh/quest2ros2_ws/src/quest2ros` | `src/quest2ros/` |
| ROS TCP Endpoint | `/home/lh/quest2ros2_ws/src/ros_tcp_communication` | `src/ros_tcp_communication/` |

新仓库是源码快照导入，不保留三个来源的 Git 历史拓扑。历史 SHA 仅用于来源追溯，详见 [docs/SOURCES.md](docs/SOURCES.md)。

## 许可证

- `src/Quest2ROS2/LICENSE`：Apache License 2.0。
- `src/ros_tcp_communication/LICENSE`：Apache License 2.0。
- `src/quest2ros/` 没有独立 LICENSE，且其 `package.xml` 许可证字段仍为 `TODO`；本仓库不擅自补写授权声明。
