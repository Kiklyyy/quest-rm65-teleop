# Right Teleop Bringup Progress

- 分支：`feat/right-teleop-bringup`
- 基线：`b2bb9c879b7d566fd1f466c096eaccda4d5540cf`
- 范围：右臂 Quest 遥操作启动与只读观察体验；不修改运动控制。

## 已实现

- 统一 launch，默认 `mode:=dry_run`。
- 复用 ROS TCP endpoint、`quest_right_target_bridge` 和既有 adapter 节点。
- 模式只选择既有 `dry_run.yaml` / `hardware.yaml`，不复制参数。
- 只读状态监控：变化立即输出，约 1 Hz heartbeat，异常/stale JSON 降级为 `UNKNOWN`。
- 可选最小 RViz 配置：`world`、Grid、右 target Marker/Pose。
- `start_rm_driver` 安全默认关闭；没有经过验证的 right-only launch 时拒绝自动启动。

## 验证

- Ubuntu 22.04 / ROS 2 Humble，系统 `/usr/bin/python3` 与 `/usr/bin/colcon`。
- `quest2ros`、`ros_tcp_endpoint`、`q2r2_bringup`、`rm65_teleop_adapter` 构建成功。
- adapter：12 项既有 GTest + 8 项状态模型测试，0 failures。
- Quest bridge：56 项测试，0 failures。
- dry-run smoke：`UnityEndpoint`、`quest_right_target_bridge`、`rm65_teleop_adapter`、`teleop_status_monitor` 均出现。
- `/right/rm_driver/movep_canfd_cmd` publisher 数量：0。
- 无 Quest、无 robot feedback 时 monitor 持续输出 `LOST`，无运行期崩溃。

## 安全边界与限制

- 未修改映射、运动参数、状态机、deadman、rearm、watchdog、command-path 或 stop 行为。
- 未启动或控制真实 RM65；本轮结果不是新的真机验收。
- 已安装 `rm_65_driver.launch.py` 使用通用/左臂默认地址；已验证右臂参数只存在于 `rm_65_right_config.yaml`，现有使用该配置的 launch 会同时启动左右臂。因此没有把 RM driver 加入统一启动。
