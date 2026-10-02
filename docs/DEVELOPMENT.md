# 开发说明

面向接手者的关键流程、模块地图与最小验证方式。运行与复现见 [REPRODUCING.md](REPRODUCING.md)，验证范围见 [VALIDATION.md](VALIDATION.md)。

## 关键流程：模型选择 → 确定性复核 → 新提案 → 用户确认 → 读回

1. **研究/规划**：`engine.research` / `engine.refine` 解析需求、过滤硬约束，返回 top-3 候选，并把候选快照写入提案证据。
2. **选择候选**：用户可以直接点候选卡选择，也可以把候选资料交给本地 Agent 审阅、再把固定 6 字段 JSON 粘贴回网页。两条路径都调用 `engine.select_candidate`。
3. **确定性复核**：服务端不信任客户端传来的商品字段，改用研究阶段保存的候选快照，重新校验来源提案、revision、`merchant_version`、白名单、截止时间、当前报价/库存与硬约束。
4. **新提案**：校验通过才生成新提案，递增 revision 并把旧提案标为 SUPERSEDED，保留原截止时间，**不写 reservation**。
5. **用户确认**：`engine.approve` 再次校验版本、有效期与当前报价，才写入 SQLite 草稿。
6. **独立读回**：写入后从 `store` 重新读取 reservation 并逐字段核对，才报告成功。

## 模块地图

- `shop_agent/server.py`：标准库 `http.server`，只绑定回环。路由：
  - `GET /`、`/api/health`、`/api/cases`、`/api/session/<sid>`、`/api/history`
  - `POST /api/research`、`/api/refine`、`/api/approve`、`/api/reject`、`/api/select-candidate`、`/api/simulate-quote`
  - 静态资源来自 `shop_agent/static/`。
- `shop_agent/engine.py`：`ShopAgentEngine` 是核心，负责受限需求解析、研究/重规划、提案创建、候选选择、确认/拒绝、报价与库存变更、读回核对。`AgentError(status, code, message)` 承载错误。
- `shop_agent/store.py`：`Store` 封装 SQLite（session / proposal / reservation / quote / event），读取经行映射，写入用参数化 SQL。
- `shop_agent/static/`：`index.html` + `style.css` + `app.js`；品牌 TraceShop，阶段条“需求 → 证据 → 提案 → 核验”。候选卡有“选择此候选，生成待确认提案”按钮；导入区接受固定 6 字段 JSON 并调用 `select-candidate`。
- `native/agent-review/`：可选的 Rinx 本地导入包（`main.splash` + `manifest.json` + `README.md`），返回可复制的固定 6 字段 JSON，与 Web 服务相互独立，不由 `server.py` 加载。
- `vendor/project_a/`：可复用的 CPU 检索管线（受限解析、硬约束、BM25 排序、证据 guard、可选 CLIP 与重排适配器）。本应用只经适配器调用，未修改其源码。
- `demo/`：`catalog.jsonl`（14 条自编合成商品）与 `cases.json`（5 个固定验收用例）。
- `tests/test_shopping_flow.py`：标准库 `unittest` 工作流检查。

## 状态与不变量

- **生成提案不落草稿**：`select_candidate` 只生成待确认（PROPOSED）提案，`creates_reservation` 恒为 false；只有 `approve` 在用户显式确认后写入 reservation。
- **幂等确认**：同一 proposal 重复 `approve` 返回同一 reservation，不产生第二行。
- **版本与失效**：提案记录 revision、`merchant_version` 与有效期。选择候选会递增 revision 并取代旧提案；`simulate-quote` 或版本变化后，旧提案进入待复核/过期，`approve` 被 409 拒绝，必须重新研究。
- **快照为准**：候选选择使用服务端候选快照，不接受客户端自报商品属性；Agent 建议的 reason 标为“非目录事实”。
- **读回优先于返回**：`approve` 成功前从 `store` 读回并核对 `reservation_id`、`proposal_id`、`item_id`、`price_usd`、`status`。
- **所有者隔离**：查询与写入均以 `owner` 作用域。

## 有用的最小检查

```bash
python3 -m unittest discover -s tests -v          # 工作流检查
python3 -m shop_agent.server                       # 起服务后手动走查
```

快速手工路径：`/api/research` → `/api/select-candidate`（应生成新提案且无草稿）→ `/api/approve` → `GET /api/session/<sid>` 读回核对 → `/api/simulate-quote` 后再 `approve` 或采纳旧建议应被 409 拦下 → `/api/refine` 重规划。

## 当前局限

- Web 决策层是确定性规则策略与受限解析，不是通用 LLM，也不连接任何外部 octos / LLM 服务，默认零出站。
- 可选的原生 Agent 审阅把用户主动复制的资料发送到**宿主配置的 provider**；它只给建议、不自动批准，且为独立 Rinx 本地 peer，未经签名或 App Hub 上架。
- 模型建议仍可能出错；v0.3.0 候选采纳与真实 M3 建议已实测通过，范围见作业 180215（见 [VALIDATION.md](VALIDATION.md)）。
- 库存/报价变更为演示事件；历史目录价格不是实时报价。
- 图片入口在后端资源缺失时保持禁用；图片相关性未验证。
- 公开交付重点是源码与可运行页面；本机回环服务不是公网服务器，本交付不安排公网部署。
