# 开发说明

面向接手者的模块地图、状态不变量与最小验证方式。运行与复现见
[REPRODUCING.md](REPRODUCING.md)，验证范围见 [VALIDATION.md](VALIDATION.md)。

## 模块地图

- `shop_agent/server.py`：标准库 `http.server` 封装，只绑定回环。路由以 `GET`/`POST` 前缀区分：
  - `GET /`、`GET /api/health`、`GET /api/cases`、`GET /api/session/<sid>`、`GET /api/history`
  - `POST /api/research`、`/api/refine`、`/api/approve`、`/api/reject`、`/api/simulate-quote`
  - 静态资源来自 `shop_agent/static/`。
- `shop_agent/engine.py`：`ShopAgentEngine` 是核心。负责受限需求解析、研究/重规划、提案创建、
  确认/拒绝、报价与库存变更、读回核对。`AgentError(status, code, message)` 承载错误。
- `shop_agent/store.py`：`Store` 封装 SQLite。表级操作包括 session、proposal、reservation、quote、
  event；所有读取都经 `_loads`/行映射，写入用参数化 SQL。
- `shop_agent/static/`：`index.html` + `style.css` + `app.js`，纯前端状态机，调用上述 JSON API；
  其中“复制给 Agent 审阅”把候选/约束/证据/版本/有效期与 `time_context`（提案创建时间 UTC、`current_time_utc` 为 `null`）导出到剪贴板，不调用 `octos`、不创建草稿。
- `native/agent-review/`：可选的 Rinx 本地导入包（`main.splash` + `manifest.json` + `README.md`），
  与 Web 服务相互独立，不由 `server.py` 加载。
- `vendor/project_a/`：可复用的 CPU 检索管线（受限解析、硬约束、BM25 排序、证据 guard、可选 CLIP
  与重排适配器）。本应用只通过适配器调用，未修改其源码。
- `demo/`：`catalog.jsonl`（14 条自编合成商品）与 `cases.json`（5 个固定验收用例）。
- `tests/test_shopping_flow.py`：11 项标准库 `unittest` 工作流检查。

## 状态与不变量

- **确认才写入**：`approve` 只在用户显式确认后创建 `reservation`（本地草稿行）；`reject` 不创建草稿。
- **幂等确认**：对同一 proposal 的重复 `approve` 返回同一 reservation，不产生第二行。
- **报价版本失效**：提案记录创建时的报价版本与有效期。`simulate-quote` 或报价版本变化后，提案进入
  待复核状态，`approve` 被拒（HTTP 409），必须重新 `refine` 生成新 revision。
- **读回优先于返回**：`approve` 成功前会从 `Store` 重新读取 reservation，并逐字段核对
  `reservation_id`、`proposal_id`、`item_id`、`price_usd`、`status`；不一致即失败。
- **所有者隔离**：查询与写入均以 `owner` 作用域，跨 owner 不可见。
- **事件留痕**：session/proposal/reservation 与关键动作写入 `event` 表，可回看。
- **复制不发送**：前端的「复制结果到聊天」只写入剪贴板并展示可审阅文本，不调用任何发送接口，
  也不创建新草稿；报价变化后该分享入口被清除，直到重新复核。

## 有用的最小检查

```bash
python3 -m unittest discover -s tests -v          # 11 项工作流检查
python3 -m shop_agent.server                       # 起服务后手动走查
```

快速手工路径：`/api/research` → 取 proposal → `/api/approve` → `GET /api/session/<sid>` 读回核对 →
`/api/simulate-quote` 后再次 `approve` 应被拦下 → `/api/refine` 重规划。

## 当前局限

- Web 决策层是确定性规则策略与受限解析，不是通用 LLM，也不连接任何外部 octos / LLM 服务，默认零出站。
- 可选的原生 Agent 审阅把用户主动复制的资料发送到**宿主配置的 provider**；它只给建议、不自动批准，
  且为独立 Rinx 本地 peer，未经签名或 App Hub 上架。
- 模型建议仍可能出错；v0.2.1 提示修正只改善了创建/截止/当前时间与空数组的表述（180063 单次用例），Web 的确定性有效期/版本检查才是权威。
- 库存/报价变更为演示事件；历史目录价格不是实时报价。
- 图片入口在后端资源缺失时保持禁用；图片相关性未验证。
- 公开交付重点是源码与可运行页面；本机回环服务不是公网服务器。

## 下一步优先级

固定 Rinx `5a9e2af` + 固定 `octos` 的原生审阅已在 v0.2.1 复验（作业 180063，见 [VALIDATION.md](VALIDATION.md)）。
提案创建时间现在由后端真实时间携带（`time_context.proposal_created_at_utc`），当前时间显式为未知；
下一步优先是在**短视频**中演示一次真实审阅，并在预算允许时多测几个用例，而不是继续重构或补基础设施。
部署为公网服务或提供稳定公共 URL 仍未做。现有 Web 原型作为可复现载体保持不变；文档只描述当前确实
存在的 API，不预先编造接口。
