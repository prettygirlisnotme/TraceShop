# TraceShop · OctoSense 购物与物流

队伍：TraceShop。唯一成员 ID：TraceShop-Felix。

## 当前交付

- 公开仓库：https://github.com/prettygirlisnotme/TraceShop
- 应用包：[`bundle/`](bundle/)，id `traceshop.shopping`，版本 `0.4.1`（待发布；v0.4.0 为初赛评审版本）。
- 入口：[README](README.md)；程序：[main.splash](bundle/main.splash)。
- [原生购物操作录屏](evidence/native-shopping.webm) · [重启恢复录屏](evidence/native-restart.webm)。
- [官方预检](evidence/native-hub-check.txt) · [实际运行范围](docs/VALIDATION.md)。

独立 OctoScript 应用完成候选比较、提案、人工确认、本地草稿写入和独立读回。模型审阅是可选宿主能力；已完成 card-host 服务缺失后的完整人工流程，并在未修改的 standalone Rinx（固定 `5a9e2af`）加打包 octos 与 CN MiniMax-M3 下，于 v0.4.0 bundle 验证一条真实 JSON 建议采纳、人工确认和保存读回流程。见[实际回复与结果](evidence/native-agent-workflow.json)。未验证注入式 OctoSense Shell System Agent，也未验证手机。

## 模型验证口径

以下口径在 [README](README.md)、[SUBMISSION](SUBMISSION.md) 和 [作者答复](docs/APP_HUB_REVIEW.md) 三处保持一致。

- 模型实测针对 v0.4.0 的同一业务脚本；0.4.1 只改文档、截图与发布配置，没有新的模型验证。
- 官方 Linux `card-host`（固定版本）实测了人工状态流转、人工确认与独立读回；宿主不提供 `octos` 审阅服务，应用如实显示不可用。
- 未修改的 standalone Rinx（固定 `5a9e2af`）使用其打包 octos 与 CN MiniMax-M3，在同一个 v0.4.0 bundle 上完成一条真实 JSON 审阅：模型建议 → 采纳生成 v2 待确认提案 → 明确人工确认 → 写入文件并独立读回一致。
- 未验证注入式 OctoSense Shell System Agent，也未验证手机/移动端。
- 该证据在 main 分支 `f07434ff` 收录，对应 v0.4.0（`4cf35ca8`）的 bundle BLAKE3；0.4.1 的 bundle 摘要以发布工作流产出为准，目前尚未发布。

## 提交状态

初赛提交历史：

- 仓库已按官方 issue #13 登记。2026-10-03 群通知要求 10 月 6 日提交代码仓库、App Hub 材料与应用录屏，具体截止时刻未说明。
- 发布者、支持入口和[隐私说明](PRIVACY.md)已补齐。已提交 [App Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71)，固定 [v0.4.0](https://github.com/prettygirlisnotme/TraceShop/releases/tag/v0.4.0)，commit `4cf35ca84c04a7549b8adad9e621860b57d53ebf`。
- 2026-10-09，维护者 ZhangHanDong 在 [App Hub #71 评论](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71#issuecomment-6077956506) 给出结果：**入围，86/100，评审版本 v0.4.0（`4cf35ca8`）**。App Hub 上架与奖项待后续流程。

下一轮：用户 2026-10-09 转述复赛提交为 10 月 14 日、分组答辩为 10 月 15 日。具体时刻与线下安排尚未确认。

## 0.4.1 发布配置（待发布）

- 已准备官方 `tools/octo publish-github` 生成的 GitHub 发布工作流；尚未创建 tag、尚未触发工作流。
- 0.4.1 仅改动文档、截图与发布配置，`main.splash` 应用逻辑不变。
- sealed pack、GitHub attestation 证明与 release-receipt 须在发布成功后回填，本文不声称已验证或已发布。
