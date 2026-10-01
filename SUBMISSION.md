# TraceShop · 初赛作品入口

本页面向评委与用户，汇总场景、任务、固定版本、演示素材、验证证据与已知边界。当前交付是**源码与材料**，供评委在本机复现，并不代表主办方已完成正式运行验收。

- 队伍：**TraceShop**
- 唯一成员 ID：**TraceShop-Felix**（微信群昵称；队伍仅此一人）
- 赛道：**OctoSense 购物与物流**
- 许可证：**Apache-2.0**（见 [LICENSE](LICENSE)）
- 支持与问题反馈：<https://github.com/prettygirlisnotme/TraceShop/issues>

## 一句话

一个证据驱动、可确认、可读回的购物决策 Web 原型：把文字需求变成候选研究、硬约束过滤、可审阅的采购提案、用户明确确认、本地 SQLite 草稿写入与独立读回；报价或库存变化会让旧提案失效并强制重新研究。规则型决策，不产生真实订单。

## 固定版本与一条命令启动

固定源码版本：**[v0.1.1](https://github.com/prettygirlisnotme/TraceShop/tree/v0.1.1)**。该版本的 `shop_agent/` 与 `vendor/project_a/` 源码与 v0.1.0（提交 `8c0ef8ac`）**完全一致**，本次仅补充文档与材料入口。

需要 Python 3.10 或更新版本，仅使用标准库：

```bash
git clone --branch v0.1.1 --depth 1 https://github.com/prettygirlisnotme/TraceShop.git
cd TraceShop
python3 -m shop_agent.server
```

打开 <http://127.0.0.1:8088/>。服务只绑定回环，默认使用随仓库的 14 条自编演示商品，不下载模型或数据。

## 场景与任务

用户用自然语言提出购物需求，希望得到**可解释、可确认**的建议，并在确认后看到一个明确、不涉及扣款的采购草稿。作品把重点放在决策闭环与状态可信度：提案必须绑定候选、证据、版本与有效期；按钮点击不等于执行成功，必须从持久层读回核对。

建议复现路径（操作顺序，与现有录像的镜头顺序分开）：

1. **研究候选**：解析需求，硬约束过滤并返回 top 3 候选与目录证据 —— [research.png](evidence/research.png)
2. **模拟报价变化** —— [quote-changed.png](evidence/quote-changed.png)
3. **旧提案 409 受阻**：提案转入 NEEDS_REVIEW，确认被 `quote_changed` 拦下
4. **重新规划**：在多轮细化输入框填写 `prefer gaming`，生成新 revision，旧提案被取代
5. **显式确认**：只有用户确认才写入本地草稿，重复确认幂等
6. **SQLite 独立读回**：重新读取草稿并逐字段核对后才报告成功 —— [draft-verified.png](evidence/draft-verified.png)
7. **用户复制回执回聊天**：预览并复制结果，由用户回到聊天自行决定是否发送 —— [host-share.png](evidence/host-share.png)

现有 [一分钟录像](evidence/demo.webm) 的实际顺序是：研究 → 确认 → 独立读回 → 复制 → 模拟涨价并清除旧分享结果 → 重新规划。它没有录制重新规划后的再次确认；旧提案 409 拦截由 [HTTP 验证](evidence/public-checks.json) 与单元检查证明。宿主发送与回传使用独立截图，录像只包含 Web 前端。

## 五个固定验收用例

来源：[demo/cases.json](demo/cases.json)。证据只引用仓库内已有内容，不新增测试结果。

| 用例 | 输入 | 操作 | 预期结果 | 证据 |
| --- | --- | --- | --- | --- |
| 正常确认 + 幂等 + 重启可读 | `wireless mouse under 30 dollars` | 研究 → 确认 → 再次确认 | 首次确认写入一条持久草稿并读回；重复确认返回同一 `reservation_id` 且不新增；重开数据库仍可见 | [tests/test_shopping_flow.py](tests/test_shopping_flow.py)；[public-checks.json](evidence/public-checks.json)（`reapprove_idempotent` / `same_reservation_id` / `readback_one_reservation`） |
| 拒绝不产生预订 | `wireless mouse under 30 dollars` | 研究 → 拒绝 → 尝试确认 | 记录拒绝、无草稿行；后续确认被 409 `proposal_rejected` 拦下 | [tests/test_shopping_flow.py](tests/test_shopping_flow.py)；`reject_then_approve_409` |
| 预算内无可行商品 | `wireless mouse under 3 dollars` | 以不可行预算研究 | 无推荐、无提案，返回确定性协商项，不创建草稿 | [tests/test_shopping_flow.py](tests/test_shopping_flow.py) |
| 提案后报价变化被拦截 | 同首行，模拟 +5.0 USD | 研究 → 模拟报价变化 → 尝试确认 | 提案转 NEEDS_REVIEW；确认 409 `quote_changed`；不创建草稿、不自动重新确认 | [tests/test_shopping_flow.py](tests/test_shopping_flow.py)；`quote_change_409` |
| 提案过期被拦截 | 同首行，注入时钟越过有效期 | 研究 → 前进时钟 → 尝试确认 | 确认 409 `proposal_expired`，不创建草稿。**仅由注入时钟的单元检查覆盖，未在网页端手动演示** | [tests/test_shopping_flow.py](tests/test_shopping_flow.py) |

## 图标、截图与演示

- 应用图标：[shop_agent/static/icon.svg](shop_agent/static/icon.svg)（购物袋 + 确认勾，原始 SVG）
- 截图：[研究](evidence/research.png) · [草稿读回](evidence/draft-verified.png) · [报价变化](evidence/quote-changed.png) · [宿主发送卡片](evidence/host-card-sent.png) · [结果回到聊天](evidence/host-result-return.png) · [分享预览](evidence/host-share.png)
- 约一分钟 Web 演示录像：[evidence/demo.webm](evidence/demo.webm)

## URL 卡片与宿主接入

Web 卡片使用 `rs.robius.robrix.mini_app` 消息类型，内容示例见 [demo/robrix2-card.example.json](demo/robrix2-card.example.json)（它不是 manifest，也不授予聊天或账号权限）。接收方需在自己的电脑上运行本应用，并在兼容宿主的 Web mini-app 表单中填写 `http://127.0.0.1:8088/`。

已验证宿主为官网示例链接的历史固定提交 [`05daf9b`](https://github.com/hagency-org/Rinx/tree/05daf9bdb05fafc6d8f04dcb312a35f1d46a661e)，Linux 编译与启动步骤见 [docs/REPRODUCING.md](docs/REPRODUCING.md#历史宿主版本)，宿主工作流检查见 [evidence/workflow-checks.json](evidence/workflow-checks.json)。局限：Linux 无桌面时「Open in browser」经由**透明 headless URL 打开器适配器**完成，不是桌面默认 GUI 浏览器；这证明地址与操作路径，不代表最新 Rinx main 或官方受理。

## 验证证据

- 公开目录复验（作业 **178861**，2026-10-01，CPU-only，12 秒，COMPLETED 0:0）：以 `python -I -S -B` 运行标准库 11 项检查与回环 HTTP 闭环（研究 / 显式确认 / 独立读回 / 幂等 / 拒绝 409 / 报价变化 409）。见 [evidence/public-checks.json](evidence/public-checks.json)。
- 私有集群宿主工作流实测（作业 **178695**）：固定旧宿主独立编译，私有回环合成 fixture，10 项结构化检查通过。见 [evidence/workflow-checks.json](evidence/workflow-checks.json)。
- 汇总说明：[docs/VALIDATION.md](docs/VALIDATION.md)。

## 登记状态与官方规则来源

本仓库地址已在官方 issue #13 登记：<https://github.com/gosimfoundation/hackathon-agenticapp26/issues/13#issuecomment-5924172633>（队伍名 TraceShop、GitHub 仓库地址两行）。当前通过该官方入口递交仓库，源码与材料集中在本页面；**不代表主办方已经验收或确认晋级**。

初赛官方规则以 2026-10-01 核验的官网组件为准：赛程 [EventSchedule.vue](https://github.com/gosimfoundation/hackathon-agenticapp26/blob/main/src/components/EventSchedule.vue)、作品提交 [AppHubSubmission.vue](https://github.com/gosimfoundation/hackathon-agenticapp26/blob/main/src/components/AppHubSubmission.vue)（官网页面 <https://create.gosim.org/agenticapp26/>）。初赛提交截止 **10/4 23:59（北京时间）**；Web 交付为源码 + 可运行页面 + URL 卡片，**App Hub 上架非必需**。

## 已知边界

当前限制集中如下，请以此为准：

- 决策层是**确定性规则策略与受限解析，不是通用 LLM**，也未连接 octos 或任何外部模型服务。
- 确认为**本地采购草稿，不下单、不扣款**；随仓库的是 **14 条自编合成商品**。
- 报价与库存变化是**模拟事件**，历史价格不是实时报价。
- **暂无公网服务**，仅回环 `127.0.0.1`；接收方需自己运行 localhost，本地 URL 是否被赛方受理尚未确认。
- **最新 Rinx main 与真实 octos 集成尚未验证**。
- 图片入口在后端资源缺失时保持禁用，图片相关性未验证。

## 许可证

项目自有代码采用 [Apache-2.0](LICENSE)。`vendor/project_a/` 复用已有购物检索管线并保留其 Apache-2.0 许可证与逐文件校验；宿主协议参考保留 MIT 声明，见 [NOTICE](NOTICE)。真实商品目录与模型权重不在仓库中。
