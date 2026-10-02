# TraceShop · 初赛作品入口

本页面向评委与用户，汇总场景、任务、固定版本、演示素材、验证证据与已知边界。当前交付是**源码与材料**，供评委在本机复现，并不代表主办方已完成正式运行验收。当前材料版本 **v0.3.0**；新增候选选择和真实 Agent 建议采纳已实测，证据见下方与 [验证记录](docs/VALIDATION.md)。

- 队伍：**TraceShop**
- 唯一成员 ID：**TraceShop-Felix**（微信群昵称；队伍仅此一人）
- 赛道：**OctoSense 购物与物流**
- 许可证：**Apache-2.0**（见 [LICENSE](LICENSE)）
- 支持与问题反馈：<https://github.com/prettygirlisnotme/TraceShop/issues>

## 一句话

一个证据驱动、可确认、可读回的购物决策 Web 原型：把文字需求变成候选研究、硬约束过滤、可审阅的采购提案、用户明确确认、本地 SQLite 草稿写入与独立读回；报价或库存变化会让旧提案失效并强制重新研究。v0.3.0 起，用户可以直接选择 top-3 候选，或把可选本地 Agent 审阅返回的固定字段 JSON 粘贴回网页；两条路径走同一个服务端选择流程。规则型决策，不产生真实订单。

## 固定版本与一条命令启动

固定源码版本：**v0.3.0**。它在 v0.2.1 的确定性 Web 工作流与可选原生审阅包之上，加入候选直接选择与 Agent 建议采纳：新提案由服务端候选快照重建，绑定来源 `proposal_id`、revision、`merchant_version`、白名单、截止时间与当前报价/库存硬约束；生成时递增 revision、把旧提案标为 SUPERSEDED、保留原截止时间，且**不创建 reservation**，仍需用户点击确认。原生审阅包 **0.3.0** 返回可复制的固定 6 字段 JSON。

需要 Python 3.10 或更新版本，仅使用标准库：

```bash
git clone --branch v0.3.0 --depth 1 https://github.com/prettygirlisnotme/TraceShop.git
cd TraceShop
python3 -m shop_agent.server
```

打开 <http://127.0.0.1:8088/>。服务只绑定回环，默认使用随仓库的 14 条自编演示商品，不下载模型或数据。

## 场景与任务

用户用自然语言提出购物需求，希望得到**可解释、可确认**的建议，并在确认后看到一个明确、不涉及扣款的采购草稿。作品把重点放在决策闭环与状态可信度：提案必须绑定候选、证据、版本与有效期；按钮点击不等于执行成功，必须从持久层读回核对。

建议复现路径（操作顺序，与录像镜头顺序分开）：

1. **研究候选**：解析需求，硬约束过滤并返回 top 3 候选与目录证据；候选卡显示预算余量与目录字段 —— [候选选择](evidence/candidate-selected.png)
2. **选择候选**：点击“选择此候选，生成待确认提案”，由服务端候选快照生成新提案（不创建草稿）
3. **（可选）Agent 审阅**：复制资料到本机 Rinx 审阅包，取回固定 6 字段 JSON 粘贴采纳，走同一服务端选择流程 —— [建议采纳](evidence/agent-adopted.png)
4. **显式确认**：只有用户确认才写入本地草稿，重复确认幂等
5. **SQLite 独立读回**：重新读取草稿并逐字段核对后才报告成功 —— [核验结果](evidence/workflow-verified.png)
6. **报价变化拦截**：模拟涨价后，旧提案与旧 Agent 建议都不能再采纳/确认，必须重新研究 —— [报价拦截与重新确认实录](evidence/agent-workflow.webm)
7. **用户复制回执回聊天**：预览并复制结果，由用户回到聊天自行决定是否发送

## 候选选择与 Agent 建议采纳（v0.3.0）

- 入口一（人工）：候选卡“选择此候选，生成待确认提案”（`POST /api/select-candidate`，`selection_source=human`）。
- 入口二（Agent）：网页导出候选与提案资料 → 本机 Rinx 审阅包返回 `{"schema_version":1,"proposal_id":…,"revision":…,"merchant_version":…,"selected_item_id":…,"reason":…}` → 用户粘贴回网页采纳（`selection_source=agent_review`）。只接受这 6 个字段（允许 ```json 围栏），其他格式拒绝。
- 服务端校验：来源提案必须为待确认且未过期；会话 revision 与 `merchant_version` 必须匹配；`selected_item_id` 必须在服务端候选白名单内；必须存在研究阶段保存的候选快照；当前报价与快照一致且库存可用；硬约束在当前报价下仍满足。Agent 建议另带 `review_revision` / `review_merchant_version`，过时即拒。
- 结果：新提案取代旧提案（旧提案转 SUPERSEDED，其后确认被 409 `proposal_superseded` 拦下），revision 递增，保留原有效期，**不创建 reservation**；仍需用户在原确认按钮确认，确认后才写 SQLite 并独立读回。
- 标注：目录字段与出处是事实；选择理由若来自模型，会明确标为“Agent 建议（非目录事实）”。

v0.3.0 已由作业 180215（CPU 8，2 分 09 秒，COMPLETED 0:0）跑通上述采纳与重新确认流程；[脱敏结果](evidence/agent-workflow-checks.json)记录 10 项相关检查。已有 11 项标准库检查在该作业通过。

## 可选原生 Agent 审阅（包版本 0.3.0）

Web 页面在研究会话中提供“复制给 Agent 审阅”。用户把复制出的候选、硬/软约束、证据、报价版本、有效期与时间上下文粘贴进 Rinx 导入的 [`native/agent-review/`](native/agent-review/) 包，由用户点击“发起审阅”，得到宿主 `octos` 的只读建议；随后用户复制固定 6 字段 JSON 回到 Web 采纳，再回到 Web 由自己确认或拒绝。

- v0.2.1 已验证的固定组合为 `octos` 内核（`2.0.3-rc.13`）与固定 Rinx `5a9e2af`：导入 stamped bundle、Review 能力恰为 `octos.session.open`、`octos.turn.start`、`octos.turn.interrupt` 且无 room；assistant 关闭时返回真实错误；配置本机 provider 后经真实 Splash 回调完成并显示“审阅完成（建议未执行）”。
- 包版本 0.3.0 返回可复制的固定 6 字段 JSON；`manifest.json` 的 `integrity.bundle_blake3` 必须由官方打包工具重新生成，不能手填。
- 这是 **standalone Rinx 自己的本地 Agent peer**，**不是**宿主注入的 OctoSense System Agent，也不是 Web URL 卡片的自动 bridge，未经签名或 App Hub 上架。Web 与原生包之间由用户手动复制粘贴，没有自动桥接。
- Web 核心保持确定性、默认零出站；只有用户明确确认才会写入本地草稿，不存在自动批准。
- 模型建议只是只读文本、仍可能出错；选择理由标注为建议而非目录事实。权威判断是 Web 的确定性时钟、版本与报价检查。

v0.3.0 真实原生终态与 Web 采纳通过；官方包 BLAKE3 为 80b72b23174a2d3123e8c6798d4cc19db35f9984e0bb6a7f733089453078ef63。[原生回复](evidence/agent-workflow-native.png) · [运行记录](evidence/agent-workflow-checks.json)。

## 五个固定验收用例

来源：[demo/cases.json](demo/cases.json)。证据只引用仓库内已有内容，不新增测试结果。

| 用例 | 输入 | 操作 | 预期结果 | 证据 |
| --- | --- | --- | --- | --- |
| 正常确认 + 幂等 + 重启可读 | `wireless mouse under 30 dollars` | 研究 → 确认 → 再次确认 | 首次确认写入一条持久草稿并读回；重复确认返回同一 `reservation_id` 且不新增；重开数据库仍可见 | [tests/test_shopping_flow.py](tests/test_shopping_flow.py)；[public-checks.json](evidence/public-checks.json)（`reapprove_idempotent` / `same_reservation_id` / `readback_one_reservation`） |
| 拒绝不产生预订 | `wireless mouse under 30 dollars` | 研究 → 拒绝 → 尝试确认 | 记录拒绝、无草稿行；后续确认被 409 `proposal_rejected` 拦下 | [tests/test_shopping_flow.py](tests/test_shopping_flow.py)；`reject_then_approve_409` |
| 预算内无可行商品 | `wireless mouse under 3 dollars` | 以不可行预算研究 | 无推荐、无提案，返回确定性协商项，不创建草稿 | [tests/test_shopping_flow.py](tests/test_shopping_flow.py) |
| 提案后报价变化被拦截 | 同首行，模拟 +5.0 USD | 研究 → 模拟报价变化 → 尝试确认 | 提案转 NEEDS_REVIEW；确认 409 `quote_changed`；不创建草稿、不自动重新确认 | [tests/test_shopping_flow.py](tests/test_shopping_flow.py)；`quote_change_409` |
| 提案过期被拦截 | 同首行，注入时钟越过有效期 | 研究 → 前进时钟 → 尝试确认 | 确认 409 `proposal_expired`，不创建草稿。**仅由注入时钟的单元检查覆盖，未在网页端手动演示** | [tests/test_shopping_flow.py](tests/test_shopping_flow.py) |

候选选择与 Agent 采纳由新增的实际演示覆盖，见 [运行记录](evidence/agent-workflow-checks.json)；未增加测试套件。

## 图标、截图与演示

- 应用图标：[shop_agent/static/icon.svg](shop_agent/static/icon.svg)（购物袋 + 确认勾，原始 SVG）
- v0.3.0：[当前界面](evidence/presentation.png)、[演示短片](evidence/agent-workflow.webm)、[候选选择](evidence/candidate-selected.png)、[建议采纳](evidence/agent-adopted.png)、[核验结果](evidence/workflow-verified.png)。
  - `evidence/agent-workflow.webm` 计划为真实 Web 录屏并裁去模型等待，配合真实原生截图剪辑；两者为**独立片段**，不得写成一段连续桌面录像。
- 历史 v0.2.1 素材（旧版本实录，不能证明 v0.3.0 新流程）：[研究](evidence/research.png) · [草稿读回](evidence/draft-verified.png) · [报价变化](evidence/quote-changed.png) · [宿主发送卡片](evidence/host-card-sent.png) · [结果回到聊天](evidence/host-result-return.png) · [分享预览](evidence/host-share.png) · 原生审阅 [结果](evidence/agent-review-result.png) / [assistant 关闭](evidence/agent-review-off.png) / [导出](evidence/agent-review-export.png) · 约一分钟 Web 录像 [demo.webm](evidence/demo.webm)。

## URL 卡片与宿主接入

Web 卡片使用 `rs.robius.robrix.mini_app` 消息类型，内容示例见 [demo/robrix2-card.example.json](demo/robrix2-card.example.json)（它不是 manifest，也不授予聊天或账号权限）。接收方需在自己的电脑上运行本应用，并在兼容宿主的 Web mini-app 表单中填写 `http://127.0.0.1:8088/`。

已验证宿主为官网示例链接的历史固定提交 [`05daf9b`](https://github.com/hagency-org/Rinx/tree/05daf9bdb05fafc6d8f04dcb312a35f1d46a661e)，Linux 编译与启动步骤见 [docs/REPRODUCING.md](docs/REPRODUCING.md#历史宿主版本)，宿主工作流检查见 [evidence/workflow-checks.json](evidence/workflow-checks.json)。局限：Linux 无桌面时「Open in browser」经由**透明 headless URL 打开器适配器**完成，不是桌面默认 GUI 浏览器；这证明地址与操作路径，不代表最新 Rinx main 或官方受理。该宿主实测对应历史 Web 版本，不能替代 v0.3.0 新流程证据。

原生 Agent 审阅使用**另一个**固定提交 `5a9e2af`；它需要单独构建宿主并准备官方打包的 `octos` 内核，步骤见 [docs/REPRODUCING.md](docs/REPRODUCING.md#可选原生-agent-审阅)。两段宿主证据对应不同提交，不能互相替代。

## 验证证据

- **v0.3.0 已实测**：作业 180215，CPU 8，2 分 09 秒，COMPLETED 0:0。已有 11 项检查通过，真实 M3 终态、候选采纳、报价变化拦截和重新确认读回通过。
  - [脱敏结构化结果](evidence/agent-workflow-checks.json)、[演示短片](evidence/agent-workflow.webm)、[当前界面](evidence/presentation.png)。
  - 原生包 0.3.0 已由官方工具重新盖章；详情见 [VALIDATION.md](docs/VALIDATION.md)。
- 历史基线（v0.2.1，不代表新流程）：
  - 原生 Agent 审阅作业 **180063**（2026-10-02，CPU-only，1 分 52 秒，COMPLETED 0:0）：固定 Rinx 与固定 `octos` 下获得真实 M3 文字建议；脱敏 aggregate 见 [evidence/agent-review-checks.json](evidence/agent-review-checks.json)。此前同组合 v0.2.0 为作业 180045。
  - 公开目录复验作业 **180053**（2026-10-02，CPU-only，6 秒，COMPLETED 0:0）：对 v0.2.0 公开检出以 `python -I -S -B` 运行标准库 11 项检查与回环 HTTP 闭环，全部通过。见 [evidence/public-checks.json](evidence/public-checks.json)。更早 v0.1.1 复验为作业 178861。
  - 私有宿主工作流实测（作业 178695）：固定旧宿主独立编译，私有回环合成 fixture，10 项结构化检查通过。见 [evidence/workflow-checks.json](evidence/workflow-checks.json)。
- 汇总与证据边界见 [docs/VALIDATION.md](docs/VALIDATION.md)。

## 登记状态与官方规则来源

本仓库地址已在官方 issue #13 登记：<https://github.com/gosimfoundation/hackathon-agenticapp26/issues/13#issuecomment-5924172633>（队伍名 TraceShop、GitHub 仓库地址两行）。当前通过该官方入口递交仓库，源码与材料集中在本页面；**不代表主办方已经验收或确认晋级**。

初赛官方规则以 2026-10-01 核验的官网组件为准：赛程 [EventSchedule.vue](https://github.com/gosimfoundation/hackathon-agenticapp26/blob/main/src/components/EventSchedule.vue)、作品提交 [AppHubSubmission.vue](https://github.com/gosimfoundation/hackathon-agenticapp26/blob/main/src/components/AppHubSubmission.vue)（官网页面 <https://create.gosim.org/agenticapp26/>）。初赛提交截止 **10/4 23:59（北京时间）**；Web 交付为源码 + 可运行页面 + URL 卡片，**App Hub 上架非必需**。

## 已知边界

当前限制集中如下，请以此为准：

- Web 决策层是**确定性规则策略与受限解析，不是通用 LLM**。它本身不连接任何外部模型服务，也不发起出站请求。
- 生成新提案（选择候选或采纳 Agent 建议）**不创建草稿**；只有用户显式确认才写入本地 SQLite 草稿，且不下单、不扣款。
- Agent 建议只是只读文本、可能出错；理由标注为建议而非目录事实。权威判断是 Web 的确定性有效期、版本与报价检查。
- 可选的原生 Agent 审阅会把你主动复制的审阅资料发送到**宿主配置的 provider**；这是独立 Rinx 本地 peer，非官方签名/上架，也非自动 Web bridge。
- 随仓库的是 **14 条自编合成商品**、USD 计价；报价与库存变化是**模拟事件**，历史价格不是实时报价。
- 本交付**不安排公网部署**，服务仅回环 `127.0.0.1`；接收方需自己运行 localhost，本地 URL 是否被赛方受理尚未确认。
- v0.3.0 的证据是一条真实流程，不能据此推断稳定推荐准确率。
- 原生审阅已对固定 Rinx `5a9e2af` 与固定 `octos` 的组合验证（v0.2.1 只读建议）；**不承诺最新移动中的 main、Windows 或其它未测试平台**。
- 图片入口在后端资源缺失时保持禁用，图片相关性未验证。

## 许可证

项目自有代码采用 [Apache-2.0](LICENSE)。`vendor/project_a/` 复用已有购物检索管线并保留其 Apache-2.0 许可证与逐文件校验；宿主协议参考保留 MIT 声明，见 [NOTICE](NOTICE)。真实商品目录与模型权重不在仓库中。
