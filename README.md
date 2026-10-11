# TraceShop 采购助手

> 有证据、能应对条件变化的个人采购决策：研究 → 证据 → 约束 → 批准 → 执行 → 读回。

TraceShop 是一个 **OctoScript / Splash** 应用，作品唯一入口是 [`bundle/`](bundle/)。它把一次采购决策拆成可核对、可回溯的步骤：Agent 读取状态、研究候选、创建提案；**Agent发起的保存必须经宿主批准**，写入的是宿主私有存储中的本地草稿，并由 Agent 独立 `draft.read` 读回核对。界面按钮与七个应用工具共用同一套研究/提案/保存业务核心，不维护两套逻辑。

目录由合成演示商品与人工整理的官网快照组成。结果是宿主私有存储中的采购草稿，没有真实下单、支付或物流。

## 为什么做“购物”

购物天然带三条线：**检索**（在约束下找候选）、**推荐/证据**（候选为什么合适）、**可确认的执行**（真正写下一份东西前必须由人批准）。TraceShop 只做这条窄而完整的链路，并把每一步留下可核验证据：

- 预算与硬关键词是强约束，**不会自动放宽、删除或用软偏好替代，只有用户明确修改才更新**；
- 软偏好（安静/游戏/便携）只认目录原始字段证据；`not_documented` 只表示“本目录未证实”，不代表商品不支持；
- 候选与只读替代严格分开，替代项不能直接变成提案；
- 保存是后果性操作：模型调用工具**不等于**用户批准。

这套候选、证据、任务版本、批准与回执的边界，可供采购审批或旅行预订等场景适配复用。业务约束、数据来源与权限仍需按场景设计。

## 唯一入口与目录来源

- 入口：[`bundle/main.splash`](bundle/main.splash) · [`bundle/tools.json`](bundle/tools.json) · [`bundle/AGENT.md`](bundle/AGENT.md) · [`bundle/manifest.json`](bundle/manifest.json)（版本 **0.5.3**）。
- 目录来源（会话内切换，`shopping.catalog.select`）：
  - `synthetic_demo`（默认）：14 条纯虚构 USD 演示商品。
  - `official_snapshot`：3 条人工核对的官网页面价格快照（US/USD）。是**整理摘要，不是整页原文**；**非实时**；只有**商品价**，**运费、税费与配送未核验**，不保证库存或可配送。快照已内嵌于脚本，**程序运行时不联网抓取**；`net` 仅按官方规则披露已有来源 URL。
- 历史/复用代码：[`shop_agent/`](shop_agent/)（v0.3.0 Web 原型）、[`native/agent-review/`](native/agent-review/)（旧 Rinx 审阅包）、[`vendor/project_a/`](vendor/project_a/)。它们**不是**本次应用入口，只作学习与复用。

## 核心闭环（七个应用工具）

1. `shopping.status.read`：读状态、目录来源与本地任务绑定摘要。
2. `shopping.catalog.select`：在两种固定来源间切换；切换递增 `merchant_version` 并清除旧研究/选择/变价，旧待确认提案保留展示但会被版本守卫拒绝保存。
3. `shopping.catalog.research`：规则检索，最多 3 个候选及原始字段证据；**每次返回（含失败）**都带确定性 `decision`（`state`/`request`/`alternatives`/`clarification_required`/`question`），只读替代项 `currently_eligible=false`，不能直接建提案。
4. `shopping.proposal.create`：为某候选创建待确认提案，绑定研究版本、商户版本与请求快照，并保存结构化 `selection_record`（选择依据快照）。
5. `shopping.proposal.read`：只读当前待确认提案。
6. `shopping.draft.save`：`risk=destructive`、`confirm=host`、不可自动批准；宿主批准后写入草稿并**即时独立读回**（`readback_ok`）。
7. `shopping.draft.read`：独立读回草稿，分别报告 `read_ok`、`current_proposal_present`、`matches_current_proposal` 与 `verification_scope`。

继承自 0.5.1 的界面与绑定能力：应用发起任务时，把起始条件（`task_id` + 需求/预算/硬关键词/目录来源/商户版本/起始研究版本）绑定到本进程，写工具必须原样携带匹配的 `task_id`，否则拒绝。**该绑定是应用本地快照，不是宿主身份认证，也不承诺任意回合隔离**。研究回复已压缩（`decision` 不再重复候选核对）。界面提供“办理记录 / 完整回复”切换区、选择摘要前置、首屏确认，并把“Agent 回合状态”与“提案业务状态”用独立标题分开显示。

0.5.3 增量只在 `bundle/main.splash` 把原“完整回复”页扩为**“办理记录 / 完整回复”两个切换区**（各 360px，默认打开“办理记录”，切换按钮在内容之前）：办理记录只登记**实际应用工具返回**（先原样 `app_tools.complete` 再记录结果，最多最近 12 条、仅内存），新任务先清空，刷新保持；助手原文一字不改，**不作为宿主批准、任务终态或完整审计**，手动研究与助手文字都不计入记录。0.5.2 的“预算取舍 $20”按钮保留：选择后切到 3 条官网报价快照并预填“办公用无线鼠标，安静 / 预算 20 美元 / 必须 wireless”，**只准备输入，不自动研究、不启动 Agent、不生成提案、不保存**；静音是软偏好、wireless 是硬关键词，点击不是对商品或保存的批准。除该切换区外，工具/schema/AGENT/算法/图片/视频与 0.5.2 基线一致。

## 已运行的范围

| 版本与源码 | 运行证据 | 实际范围 |
| --- | --- | --- |
| 0.5.3 当前 main `17bb585a…` | [198504](evidence/rc5-activity-198504/README.md)，官方 Linux RC5，CPU4、4:56 | 办理记录/完整回复切换：25 UI + 12 协议断言全过；五个实际 tool return 逐条、刷新保持、新任务清空、手动研究不记录；固定协议零真实模型、无保存 |
| 0.5.2 基线 main `7e0c08e1…` | [198377](evidence/rc5-onboarding-198377/README.md)，官方 Linux RC5，CPU4、65秒 | 一条首次使用流程22项检查；预算20→用户明确改23→选择M240，确认按钮可见；零模型、未保存、无新录像 |
| 0.5.1 基线 main `18647a97…` | 198242人工UI；[198316真实M3](evidence/rc5-agent-198316/) | 13项UI检查；另有6次M3请求、5种工具、宿主批准保存与独立读回的一条任务 |
| 历史197305 | 仓库内94秒视频与四张截图 | 旧合成目录流程，保留作历史素材 |

0.5.3 当前 main 由 198504 用私有测试副本（安装副本 manifest/listing 为 0.5.2 + 测试 publisher/签名）实跑，业务 `main.splash` 与 `bundle/` 内的 `17bb585a…` 一致；本轮把 manifest/listing 元数据更新为 0.5.3，**尚未对新十文件整包运行官方发布检查**。旧 Hub CLI1.8 日志仅属测试副本，新工作流固定 Hub1.12 且未运行。完整摘要见[package-inputs](package-inputs.json)，版本与失败记录见[VALIDATION](docs/VALIDATION.md)。

新 main 未运行真实模型（198504 是固定协议零模型；布局调整前198494（main `05764fd4…`） 仅证实滚动取景与逐字一致），真实 M3 证据仍只对应 0.5.1 基线（198316）。保存/读回摘要记录、>12 条淘汰与重启清空未动态驱动。宿主 60 秒回调限制仍在，真实任务可能需要显式同步回复并结束。当前原生研究使用规则目录，Project A 接入与推荐质量评测另行推进。

## 使用

1. 输入需求、USD 预算与硬关键词，或使用预设；也可点首页“预算取舍 $20”按钮，预填一个官网快照示例条件（只填条件，不研究、不保存）。
2. 手动研究/选择/确认，或点“交给 Agent 办理采购草稿”委托宿主 Agent。
3. Agent 保存会触发宿主确认；批准后才写本地草稿。
4. 报价/条件变化后旧提案不能保存；在提案页明确点击重新办理，由 Agent 重新研究、重新批准、重新核验。

需要支持 `script-tools-v1` / `app_tools.dispatch@1` 的宿主。应用不持有模型 API 密钥；模型服务由宿主配置。见[复现说明](docs/REPRODUCING.md)。

## 发布与合规状态（本地，未发布）

- 公开仓库：[prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop)；本工作树**尚未 push**。
- App Hub 提交：[OctoSense-App-Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71)；其中 86/100 为**历史初赛评语**，不针对当前版本。
- 本轮候选尚未 push/tag/Release/更新App Hub；其中历史素材曾随旧版公开，保留原版本归属。新正式实录与答辩定稿按当前安排暂缓；对外发布逐次批准。

## 文档

| 文件 | 作用 |
| --- | --- |
| [main.splash](bundle/main.splash) | 界面、研究/提案/保存共享业务核心、任务绑定与恢复 |
| [tools.json](bundle/tools.json) · [AGENT.md](bundle/AGENT.md) | 七个工具定义 / 办理顺序、证据、确认与失败语义 |
| [VALIDATION.md](docs/VALIDATION.md) | 精确版本、CPU 位置、人工 UI vs 真实 Agent vs 外部效果 |
| [REPRODUCING.md](docs/REPRODUCING.md) | 复现环境与命令边界 |
| [HANDOFF.md](docs/HANDOFF.md) | 开发者接手与发布边界 |
| [DEMO.zh-CN.md](docs/DEMO.zh-CN.md) | 既有演示提纲与问答，未定稿新版 |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | 开发说明与历史 Web 原型 |
| [SUBMISSION.md](SUBMISSION.md) · [PRIVACY.md](PRIVACY.md) | 提交草稿 / 隐私说明 |

[English overview](README.en.md) · [Apache-2.0](LICENSE)。发布者：TraceShop-Felix。支持：[GitHub Issues](https://github.com/prettygirlisnotme/TraceShop/issues)。
