# TraceShop 采购助手

> 有证据、能应对条件变化的个人采购决策：研究 → 证据 → 约束 → 批准 → 执行 → 读回。

TraceShop 是一个 **OctoScript / Splash** 应用，作品唯一入口是 [`bundle/`](bundle/)。它把一次采购决策拆成可核对、可回溯的步骤：Agent 读取状态、研究候选、创建提案；**保存必须经宿主批准**，写入的是宿主私有存储中的本地草稿，并由 Agent 独立 `draft.read` 读回核对。界面按钮与七个应用工具共用同一套研究/提案/保存业务核心，不维护两套逻辑。

目录是演示数据，草稿写入宿主私有存储，**没有真实下单、支付或物流**。

## 为什么做“购物”

购物天然带三条线：**检索**（在约束下找候选）、**推荐/证据**（候选为什么合适）、**可确认的执行**（真正写下一份东西前必须由人批准）。TraceShop 只做这条窄而完整的链路，并把每一步留下可核验证据：

- 预算与硬关键词是强约束，**不会自动放宽、删除或用软偏好替代，只有用户明确修改才更新**；
- 软偏好（安静/游戏/便携）只认目录原始字段证据；`not_documented` 只表示“本目录未证实”，不代表商品不支持；
- 候选与只读替代严格分开，替代项不能直接变成提案；
- 保存是后果性操作：模型调用工具**不等于**用户批准。

这条“检索 → 证据 → 约束 → 批准 → 执行 → 读回”的动线，可以直接迁移到其它需要“有据可查的自动化决策 + 人类把关”的场景。本应用**不做生成式搜广推、不是全双工 Agent、未接入 AgenticOS 或 Jev 推荐/向量检索**，只演示上述可核验闭环。

## 唯一入口与目录来源

- 入口：[`bundle/main.splash`](bundle/main.splash) · [`bundle/tools.json`](bundle/tools.json) · [`bundle/AGENT.md`](bundle/AGENT.md) · [`bundle/manifest.json`](bundle/manifest.json)（版本 **0.5.1**）。
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

0.5.1 整合的界面与绑定能力：应用发起任务时，把起始条件（`task_id` + 需求/预算/硬关键词/目录来源/商户版本/起始研究版本）绑定到本进程，写工具必须原样携带匹配的 `task_id`，否则拒绝。**该绑定是应用本地快照，不是宿主身份认证，也不承诺任意回合隔离**。研究回复已压缩（`decision` 不再重复候选核对）。界面提供完整回复原文页、选择摘要前置、首屏确认，并把“Agent 回合状态”与“提案业务状态”用独立标题分开显示。

## 证据状态（版本必须分开看）

| 运行 | 精确源码 | 类型 | 结论 |
| --- | --- | --- | --- |
| **198242** | 候选 0.5.1（本仓库 `bundle/` 的私有测试副本） | RC5 人工 UI，13 项检查，零模型，2:51，Slurm CPU4 | 官方未修改 Linux RC5 真实 Store Get/Install/Open；现有 13 项人工 UI 检查全通过，无录像；测试副本 manifest 有 Linux/测试 publisher/签名改动，listing 有私有测试说明，**不继承原候选字节全通过** |
| **198215** | main `18647a97…`、旧 manifest/listing（较早候选） | 人工 UI，13 项检查，零模型，2:05，CPU4 | 历史旧包；manifest/listing 其后已改，**不继承包字节验证** |
| **197799** | main `fc005b81…`、AGENT `06a058…`（较早业务） | 真实 CN MiniMax-M3，6 请求 5 工具，宿主 Approve once，4:44，CPU4 | **较早业务对照**；M240 $22.99（预算 23、quiet）保存并独立读回，其后改 AGENT 文字与 UI 摘要/状态且未重跑模型 |
| **198316** | 候选 0.5.1（本仓库 `bundle/` 的私有测试副本） | 真实 CN MiniMax-M3，6 请求 5 工具，原生 Allow + 宿主 Approve once，7:43，CPU4 | 官方未修改 Linux RC5 真实 Store 安装；M240 $22.99（预算 23、wireless、quiet 有字段证据）保存并独立读回；`passed=true`、10 项 observed 全 true、`draft.read` `matches_current_proposal=true` `scope=proposal_fields`；693 字符真实 final 经一次显式历史同步显示，明确结束后状态已结束；**未调用 `catalog.select`/`proposal.read`** |
| **198273** | 候选 0.5.1 | 真实 CN MiniMax-M3（历史失败，材料保留） | 首次授权待主控操作时 SSH 失联，**无 live-result、无 relay 请求、模型请求 0，未通过**；wrapper 超时被误映射为 exit0，已在 198316 修正 |
| **197305** | main `4c3a5daa…` | 历史：合成目录“变价后重办”，94 秒节选 + 4 张截图 | **仅历史证据**，不对应当前包 |
| 197754 / 197860 | 较早业务 | 零模型夹具 / 人工 UI 检查 | 支持性局部检查 |

- 当前候选十文件摘要见 [`package-inputs.json`](package-inputs.json)（本地开发摘要，非官方签名）。
- 官方 `stamp/check` 作业 197371 对应旧包（main `4c3a5daa…`），**不适用于当前候选**；当前候选只经旧 CLI `655114c4`（契约 1.8.0）`stamp/check --allow-unsigned` 结构检查，**不是**新 Hub `38635915`（1.12）工具链或 GitHub attestation 验证。

### RC5 兼容验证：198242 人工 UI 与 198316 真实模型均已通过

官方 OctoSense 桌面 RC5 已于 2026-10-11 发布（源码 `83d356c2…`），App Flow 更名为 **OctoSense-App-Flow**。能力/network 声明改为**用途披露**由 **RC4 引入、RC5 延续**；设备同意、账户 scope、人工写批准与存储隔离保留；RC5 新增 charts/Wasm 与 HTTPS 修复——**本应用不使用这些新能力，也不宣称 60 秒宿主超时问题已修复**。

- **198242**（COMPLETED 0:0、CPU4、2:51）：官方未修改 Linux RC5 真实 Store Get/Install/Open，现有 13 项人工 UI 检查全通过，零模型请求、无录像；只经旧 CLI `655114c4`（契约 1.8.0）结构检查，**不是**新 Hub `38635915`（1.12）工具链或 GitHub attestation 验证。
- **198316**（COMPLETED 0:0、CPU4、7:43）：官方未修改 Linux RC5（`octosense_0.1.0-rc.5_amd64.deb`，`unmodified_official=true`）真实 Store 安装，真实 CN MiniMax-M3，非流上游转标准 SSE 适配器不变，6 请求 5 工具（`status`/`research`/`proposal.create`/`draft.save`/`draft.read`）；原生 Allow 与宿主 Approve once 均主控按本次实际画面点击，批准前草稿不存在、批准后成功保存 M240 $22.99（预算 23、wireless、quiet 有字段证据）。`live-result passed=true`，10 项 observed 全 true，research/create/save 同一 `task_id`，`draft.read` `read_ok=true`/`matches_current_proposal=true`/`verification_scope=proposal_fields`；693 字符真实 final 经一次显式历史同步显示，明确结束后状态已结束。**未调用 `catalog.select`/`proposal.read`，不代表七工具或全平台全覆盖。**
- **198273**（历史失败，材料保留）：候选上首次真实 M3 作业；首次授权待主控操作时 SSH 失联，**无 live-result、无 relay 请求日志、模型请求 0，未通过**；wrapper 超时错误被误映射为 Slurm exit0，已在 198316 修正。恢复 VPN 后仅取回失败材料，不盲目重提。
- 发布工作流已由主控更新为官方 App Flow `45174df…` 模板、Hub pin `38635915…`；**未跑 CI、未发布**。

## 边界与已知限制

- **原生仍是规则 + 目录**：检索是合成目录与 3 条官网快照上的确定性规则，不是完整语义理解，也**未接入实时商品目录或在线检索服务，未原生接入 Project A**。
- **无真实交易**：没有真实下单、支付或物流；草稿只写本地私有存储。
- **真实模型覆盖有限**：当前候选 198316 调用 5 个工具（未调用 `catalog.select` / `proposal.read`），不代表七工具、所有平台或拒绝路径全覆盖；197799 仅作较早业务对照。
- **宿主限制仍在**：60 秒回调超时仍存在；最终回复经显式同步本次任务历史取回，历史没有回合终态，仍需用户明确结束；首次授权后立即重试的时序根因未定位。
- **历史素材**：仓库内 94 秒视频（`evidence/native-agent-excerpt-197305.mp4`）与 `bundle/screenshots/01–04` 均来自 **197305 旧合成目录**流程，**不是当前候选的实拍**，仅作历史保留。

## 使用

1. 输入需求、USD 预算与硬关键词，或使用预设。
2. 手动研究/选择/确认，或点“交给 Agent 办理采购草稿”委托宿主 Agent。
3. Agent 保存会触发宿主确认；批准后才写本地草稿。
4. 报价/条件变化后旧提案不能保存；在提案页明确点击重新办理，由 Agent 重新研究、重新批准、重新核验。

需要支持 `script-tools-v1` / `app_tools.dispatch@1` 的宿主。应用不持有模型 API 密钥；模型服务由宿主配置。见[复现说明](docs/REPRODUCING.md)。

## 发布与合规状态（本地，未发布）

- 公开仓库：[prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop)；本工作树**尚未 push**。
- App Hub 提交：[OctoSense-App-Hub #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71)；其中 86/100 为**历史初赛评语**，不针对当前版本。
- 本目录内容（含 `bundle/`、历史截图与历史视频）**全部保持本地**，未 push/tag/Release/评论；本届正式提交材料暂缓，需单独批准。

## 文档

| 文件 | 作用 |
| --- | --- |
| [main.splash](bundle/main.splash) | 界面、研究/提案/保存共享业务核心、任务绑定与恢复 |
| [tools.json](bundle/tools.json) · [AGENT.md](bundle/AGENT.md) | 七个工具定义 / 办理顺序、证据、确认与失败语义 |
| [VALIDATION.md](docs/VALIDATION.md) | 精确版本、CPU 位置、人工 UI vs 真实 Agent vs 外部效果 |
| [REPRODUCING.md](docs/REPRODUCING.md) | 复现环境与命令边界 |
| [HANDOFF.md](docs/HANDOFF.md) | 开发者接手与发布边界 |
| [DEMO.zh-CN.md](docs/DEMO.zh-CN.md) | 三分钟答辩稿与常见问答 |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | 开发说明与历史 Web 原型 |
| [SUBMISSION.md](SUBMISSION.md) · [PRIVACY.md](PRIVACY.md) | 提交草稿 / 隐私说明 |

[English overview](README.en.md) · [Apache-2.0](LICENSE)。发布者：TraceShop-Felix。支持：[GitHub Issues](https://github.com/prettygirlisnotme/TraceShop/issues)。
