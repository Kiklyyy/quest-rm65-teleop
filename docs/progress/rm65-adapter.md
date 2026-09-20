# B — RM65 Adapter Progress

- 负责人：B 同学
- 建议分支：`feat/rm65-adapter`
- 当前状态：**尚未实现**

## 职责边界

新建独立 ROS 2 包：`rm65_teleop_adapter`。

- 不修改 A 同学负责的 Quest bridge、状态逻辑或 TCP Endpoint 源码。
- 只消费双方在 `docs/INTERFACE.md` 已对齐的虚拟目标和 enable/validity 接口。
- 不把 `/quest_right_target_pose` 的新 timestamp 当作用户授权。

## 实现前必须确认

- 实际 RM65 驱动、唯一命令源和允许的 topic/action。
- 当前机器人位姿读取方式和启用时锚定规则。
- Quest/world 到机器人 base frame 的经现场验证变换。
- 限速、限位、碰撞约束、控制频率、接收 watchdog 和停止策略。
- 断线、Inputs 丢失、rearm、节点退出和驱动异常时的安全状态。

## 安全默认值

- 真机写入默认关闭。
- 未经现场操作者明确授权，不创建或发送真实控制命令。
- 不直接执行虚拟初始目标 `(0.5, 0.0, 0.5)` 或 identity 姿态。
- 一只机械臂同一时刻只允许一套指定驱动/命令来源。
- 模拟输入不得混入正式控制话题。

## 进度记录

首次实现前，把计划输入、输出、失效行为和测试方式先写入 `docs/INTERFACE.md`。每个 WIP 必须给出 branch 和 commit SHA，不得标记为现场验收完成。
