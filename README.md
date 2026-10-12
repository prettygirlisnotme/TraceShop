# TraceShop 采购助手（私有 0.5.4 候选，未发布）

> 有证据、能应对条件变化的个人采购决策：研究 → 证据 → 约束 → 预算批准 → 执行 → 读回。

TraceShop 是一个 **OctoScript / Splash** 应用，作品唯一入口是 [`bundle/`](bundle/)。它把一次采购决策拆成可核对、可回溯的步骤：Agent 读取状态、研究候选、创建提案；当无候选且替代项超预算时，Agent 可在**同一任务中申请预算修订（Agent策略最多请求一次）**，**只有用户经宿主批准后才更新预算并强制重新研究**；**Agent 发起的保存必须另经宿主批准**，写入的是宿主私有存储中的本地草稿，并由 Agent 独立 `draft.read` 读回核对。界面按钮与八个应用工具共用同一套研究/提案/保存业务核心，不维护两套逻辑。

目录由合成演示商品与人工整理的官网快照组成。结果是宿主私有存储中的采购草稿，没有真实下单、支付或物流。

> **本轮只是业务整合与文档，不代表 0.5.4 已实测**：`bundle/main.splash`、`bundle/tools.json`、`bundle/AGENT.md` 与已实测的 [已测预算候选证据](evidence/rc5-budget-199314/README.md) 同业务源码（`main 43b89dde…` / `tools 4d10e50b…` / `AGENT d079839b…`），但**未对新十文件整包运行官方发布检查，也未在本机运行、测试或调用比赛模型**。少量原始证据已整理到本仓库的evidence/，完整诊断留在集群。

## 为什么做“购物”

购物天然带三条线：**检索**（在约束下找候选）、**推荐/证据**（候选为什么合适）、**可确认的执行**（真正写下一份东西前必须由人批准）。TraceShop 只做这条窄而完整的链路，并把每一步留下可核验证据：

- 预算与硬关键词是强约束，**不会自动放宽、删除或用软偏好替代**；预算唯一变更入口是经宿主批准的 `shopping.task.budget.set`，且只在用户明确同意后发生；
- 软偏好（安静/游戏/便携）只认目录原始字段证据；`not_documented` 只表示“本目录未证实”，不代表商品不支持；
- 候选与只读替代严格分开，替代项不能直接变成提案；
- 保存是后果性操作：模型调用工具**不等于**用户批准，预算修订工具同理，各自有独立的宿主批准。

这套候选、证据、任务版本、批准与回执的边界，可供采购审批或旅行预订等场景适配复用。业务约束、数据来源与权限仍需按场景设计。

## 唯一入口与目录来源

- 入口：[`bundle/main.splash`](bundle/main.splash) · [`bundle/tools.json`](bundle/tools.json) · [`bundle/AGENT.md`](bundle/AGENT.md) · [`bundle/manifest.json`](bundle/manifest.json)（版本 **0.5.4**）。
- 目录来源（会话内切换，`shopping.catalog.select`）：
  - `synthetic_demo`（默认）：14 条纯虚构 USD 演示商品。
  - `official_snapshot`：3 条人工核对的官网页面价格快照（US/USD）。是**整理摘要，不是整页原文**；**非实时**；只有**商品价**，**运费、税费与配送未核验**，不保证库存或可配送。快照已内嵌于脚本，**程序运行时不联网抓取**；`net` 仅按官方规则披露已有来源 URL。
- 历史/复用代码：[`shop_agent/`](shop_agent/)（v0.3.0 Web 原型）、[`native/agent-review/`](native/agent-review/)（旧 Rinx 审阅包）、[`vendor/project_a/`](vendor/project_a/)。它们**不是**本次应用入口，只作学习与复用。

## 核心闭环（八个应用工具）

1. `shopping.status.read`：读状态、目录来源与本地任务绑定摘要。
2. `shopping.catalog.select`：在两种固定来源间切换；切换递增 `merchant_version` 并清除旧研究/选择/变价，旧待确认提案保留展示但会被版本守卫拒绝保存。
3. `shopping.catalog.research`：规则检索，最多 3 个候选及原始字段证据；**每次返回（含失败）**都带确定性 `decision`（`state`/`request`/`alternatives`/`clarification_required`/`question`），只读替代项 `currently_eligible=false`，不能直接建提案。
4. `shopping.proposal.create`：为某候选创建待确认提案，绑定研究版本、商户版本与请求快照，并保存结构化 `selection_record`（选择依据快照）。
5. `shopping.proposal.read`：只读当前待确认提案。
6. `shopping.draft.save`：`risk=destructive`、`confirm=host`、不可自动批准；宿主批准后写入草稿并**即时独立读回**（`readback_ok`）。
7. `shopping.draft.read`：独立读回草稿，分别报告 `read_ok`、`current_proposal_present`、`matches_current_proposal` 与 `verification_scope`。
8. `shopping.task.budget.set`：`risk=destructive`、`confirm=host`、不可自动批准；**申请**宿主批准/拒绝调整当前应用发起任务的 USD 预算（新预算 0.01–100000）。只有宿主批准后才改绑定/界面预算、保留 `initial_budget_usd`、推进 `start_research_revision` 并**强制全新研究**。

继承自 0.5.1 的界面与绑定能力：应用发起任务时，把起始条件（`task_id` + 需求/预算/硬关键词/目录来源/商户版本/起始研究版本）绑定到本进程，写工具必须原样携带匹配的 `task_id`，否则拒绝。**该绑定是应用本地快照，不是宿主身份认证，也不承诺任意回合隔离**。研究回复已压缩（`decision` 不再重复候选核对）。界面提供“办理记录 / 完整回复”切换区、选择摘要前置、首屏确认，并把“Agent 回合状态”与“提案业务状态”用独立标题分开显示。

## 预算批准链路（0.5.4 增量）

相对 0.5.3 基线，0.5.4 增量是 `bundle/main.splash`、`bundle/tools.json`、`bundle/AGENT.md` 增加第八个预算工具及其链路；`manifest.json`/`listing.json` 更新版本与说明字段。界面仍保留 0.5.3 的“办理记录 / 完整回复”切换区（只登记实际应用工具返回，最多最近 12 条、仅内存、新任务先清空、刷新保持，不作为批准或任务终态），以及 0.5.2 的“预算取舍 $20”预填按钮（只准备输入，不研究、不启动 Agent、不保存）。

链路（对应 [`199314` 真实 M3 运行](evidence/rc5-budget-199314/live-result.json)）：

1. 无候选且只读替代项超预算时，研究结果的 `decision.next_action` 只补一个**操作提示**（给出原生预算批准工具及建议参数、`approved=false`），不自动执行、不升级替代为候选。
2. Agent 调用 `shopping.task.budget.set`（`task_id`、`expected_budget_usd`、新 `budget_usd`、`reason`）；**调用本身不是批准**。
3. 用户在宿主原生弹层批准后，工具返回 `changed=true`、`before/after_budget_usd`、`initial_budget_usd` 与 `fresh_research_required=true`。
4. 应用只在批准后改绑定/界面预算并强制重新研究；需求/硬关键词/目录来源/商户版本/`task_id` 不变，**已存草稿不写动，旧 pending 提案仍可展示但已失效**。
5. Agent 用新预算重新研究、从新研究候选创建提案，再对 `shopping.draft.save` 单独申请宿主批准并独立读回。

“最多一次”是Agent办理策略；应用记录修订次数，但未以硬计数拒绝第二次经宿主批准的有效修订。强保证是每次修改都须宿主批准并校验预期旧预算，不能把提示写成内核限次保证。

## 失效与拒绝行为

- `expected_budget_usd` 不等于当前绑定预算、输入非法、前后预算相同、`task_id` 不符 → 预算工具拒绝且不改任何状态。
- 用户拒绝或取消批准 → 处理器不执行、预算不变、不重试；调用只是请求，不能当同意。
- 预算修订后旧提案版本失效，保存会被版本守卫拒绝；旧草稿保持原样，不因改预算而变更。
- 改需求 / 硬关键词 / 目录来源，或已关闭任务的后续编辑，仍走结束—修改—重办；Agent 必须取得新研究版本、建立新提案并重新批准，不能重用旧批准。

## 已运行的范围

| 版本与源码 | 运行证据 | 实际范围 |
| --- | --- | --- |
| **0.5.4 当前 bundle** main `43b89dde…` | 上游 [native 预算修订 README](../../native/traceshop-budget-revision/README.md)；[199314 RC5 真实 M3](evidence/rc5-budget-199314/live-result.json)、[199373 RC6 固定协议](evidence/rc6-budget-199373/budget-result.json) | 同业务源码：199314 官方未修改 Linux RC5、真实 Store 安装、CPU4/12GiB、6:47、0 GPU，8 次真实 M3 请求、7 次工具调用（6 种），17 项直接相关判据全过；预算与保存各取得一次原生宿主批准，草稿独立读回匹配。199373 官方未修改 Linux RC6 真实 Store 安装、CPU4/12GiB、5:38、0 GPU、**零真实模型**，17 项 UI + 23 项协议通过（预算 20→23、旧预算重试拒绝、强制重研究、待确认提案），未保存草稿 |
| 0.5.3 基线 main `17bb585a…` | [198504](evidence/rc5-activity-198504/README.md)，官方 Linux RC5，CPU4、4:56 | 办理记录/完整回复切换：25 UI + 12 协议断言全过；固定协议零真实模型、无保存 |
| 0.5.2 基线 main `7e0c08e1…` | [198377](evidence/rc5-onboarding-198377/README.md)，官方 Linux RC5，CPU4、65秒 | 一条首次使用流程 22 项检查；零模型、未保存、无新录像 |
| 0.5.1 基线 main `18647a97…` | 198242 人工 UI；[198316 真实 M3](evidence/rc5-agent-198316/) | 13 项 UI 检查；另有 6 次 M3 请求、5 种工具、宿主批准保存与独立读回的一条任务 |
| 历史 197305 | 仓库内 94 秒视频与四张截图 | 旧合成目录流程，保留作历史素材 |

0.5.4 当前 bundle 的业务源码与上游 `native/traceshop-budget-revision` 一致，本候选只是把它们连带既有 0.5.3 界面与文档整理为单一可接手候选并改版本号；**尚未对新十文件整包运行官方发布检查**。上游 199314/199373 的私有测试副本 manifest/listing 与正式 publisher/签名范围不同，其结构检查不等于当前 GitHub attestation 验证。完整摘要见 [package-inputs.json](package-inputs.json)，版本与失败记录见 [VALIDATION](docs/VALIDATION.md)。

## 证据源码精确范围

- 当前 0.5.4 业务源码：`main.splash 43b89dde90a4…`、`tools.json 4d10e50be3c4…`、`AGENT.md d079839b96bf…`（完整值见 [expected-sha256.json](expected-sha256.json)）。
- `199314`（RC5 真实 M3）与 `199373`（RC6 固定协议）都直接使用上述业务源码；199314 的精确源码副本见其运行目录 `source-at-run/`。
- 更早的确定性协议/失败证据（199222、199271）业务源码是 `main fa1a3e15c766…`、`tools c33cfc323930…`，**与当前修订不同**，失败/旧协议证据不改写。
- `199373` 与 `199360` 的 RC6 包固定，见 [rc6-20261012 范围 JSON](../../reports/20261011-upstream-alignment/upstream-refresh/rc6-20261012.json)；其中 199360 因运行器 280 秒总时限 FAILED（CPU4/6:05），仅把演练时限改 480 秒后 199373 通过，**未改业务**。

## 使用位置与运行边界（集群）

- 本地只编辑、调度与查看小型结果：`/home/a/myprojects/workspaces/03_competitions/active/gosim-agentic-app-2026/release/v0.5.4-staging`。
- 实际运行在 NTU Slurm CPU 作业内、上游私有目录：`/projects/user007ssd/projects/gosim-agentic-app-2026/native/traceshop-budget-revision`。宿主安装、应用检查、真实模型调用与浏览器截图都在作业内；作业内 HTTP 仅回环私有使用，结束后停止，不提供公网 endpoint。
- WSL **不在本机安装宿主、不下载运行资产**。真实模型作业 CPU4/12GiB，单次 completion ≤2048，私有 loopback 随作业结束；主控必须查看当次原生弹层截图后才发送点击，禁止硬编码坐标或自动批准。见上游 [`live-check/README.md`](../../native/traceshop-budget-revision/live-check/README.md)。

## 使用

1. 输入需求、USD 预算与硬关键词，或使用预设；也可点首页“预算取舍 $20”按钮，预填一个官网快照示例条件（只填条件，不研究、不保存）。
2. 手动研究/选择/确认，或点“交给 Agent 办理采购草稿”委托宿主 Agent。
3. 无候选且替代项超预算时，Agent 最多申请一次预算修订；宿主批准后才改预算并强制重新研究。
4. Agent 保存会触发宿主确认；批准后才写本地草稿。
5. 报价/条件变化后旧提案不能保存；在提案页明确点击重新办理，由 Agent 重新研究、重新批准、重新核验。

需要支持 `script-tools-v1` / `app_tools.dispatch@1` 的宿主。应用不持有模型 API 密钥；模型服务由宿主配置。见[复现说明](docs/REPRODUCING.md)。

## 发布与合规状态（本地，未发布）

- 公开仓库：[prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop)；本工作树**尚未 push**。
- App Hub 提交：[OctoSense-App-Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71)；其中 86/100 为**历史初赛评语**，不针对当前版本。
- 本轮候选尚未 push/tag/Release/更新 App Hub；对外发布逐次批准。**无新正式实录或答辩素材**；`bundle/screenshots/01–04` 与 94 秒视频仍是历史版本素材，未更新、不代表 0.5.4 实拍。

## 文档

| 文件 | 作用 |
| --- | --- |
| [main.splash](bundle/main.splash) | 界面、研究/提案/保存/预算共享业务核心、任务绑定与恢复 |
| [tools.json](bundle/tools.json) · [AGENT.md](bundle/AGENT.md) | 八个工具定义 / 办理顺序、证据、预算与保存批准、失败语义 |
| [VALIDATION.md](docs/VALIDATION.md) | 精确版本、CPU 位置、人工 UI vs 真实 Agent vs 外部效果 |
| [REPRODUCING.md](docs/REPRODUCING.md) | 复现环境与命令边界 |
| [HANDOFF.md](docs/HANDOFF.md) | 开发者接手与发布边界 |
| [DEMO.zh-CN.md](docs/DEMO.zh-CN.md) | 既有演示提纲与问答，未定稿新版 |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | 开发说明与历史 Web 原型 |
| [SUBMISSION.md](SUBMISSION.md) · [PRIVACY.md](PRIVACY.md) | 提交草稿 / 隐私说明 |

[English overview](README.en.md) · [Apache-2.0](LICENSE)。发布者：TraceShop-Felix。支持：[GitHub Issues](https://github.com/prettygirlisnotme/TraceShop/issues)。
