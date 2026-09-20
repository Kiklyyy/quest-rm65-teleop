# Collaboration Rules for Humans and Agents

## 开始工作前

1. 读取 `STATUS.md`。
2. 读取 `docs/INTERFACE.md`。
3. 读取自己负责的 `docs/progress/*.md`。
4. 报告当前 branch 与 commit。新仓库事实优先于旧聊天记录。

## 分支与工作目录

- A 同学使用 `feat/vr-mapping`。
- B 同学使用 `feat/rm65-adapter`。
- 每人使用独立 clone 或 worktree，以及独立的 build/install/log。
- 不同时编辑同一工作目录，不随意切换他人正在使用的分支。
- 未 merge 的变化必须报告 branch 与完整 commit SHA。

## 职责与接口

- A 负责 Quest/TCP、VR mapping、enable/validity 输入侧定义和现场方向验收。
- B 负责新的 `rm65_teleop_adapter`，不修改 A 的 bridge/TCP 源码。
- 只在自己的职责范围修改；接口变化先更新 `docs/INTERFACE.md` 并完成双方对齐。
- 每个可验证改动必须配套测试、清晰 commit 和自己的 progress 更新。
- 总体 `STATUS.md` 由合并负责人更新，避免双方抢改。
- WIP、模拟结果和计划不能标记为验收完成。

## 现场安全

- Push 是代码版本同步，绝不自动部署、重启或启用现场机器人。
- 禁止把模拟输入混入正式控制话题。
- 真机写入默认关闭，必须有现场操作者明确授权。
- 一只机械臂同一时刻只能有一套指定驱动和命令来源。
- 不执行大范围 `pkill`，不终止无法确认归属的进程。
- 不替他人修改网络、Conda、系统或机器人驱动环境。
- SSH 私钥、GitHub token、`.env`、机器人凭据和个人配置不得写入仓库。

## 提交和验证

- 提交前检查 `git status`、暂存文件、大文件和敏感字符串。
- 测试报告必须给出实际命令和结果；没有运行就明确写“未运行”。
- 保留上游 LICENSE、来源和本地补丁说明。
- 不强推共享分支；发现分歧先同步和 review。
