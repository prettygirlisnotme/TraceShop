# 开发接手

更新：2026-10-11。先读[产品首页](../README.md)、[验证范围](VALIDATION.md)和[复现说明](REPRODUCING.md)。

## 代码与执行流程

- [main.splash](../bundle/main.splash)：`research_core` 执行预算/硬关键词筛选并保留原始字段证据，`create_proposal_at` 绑定需求与版本，`confirm_draft_core` 在写入时再次校验并读回。
- [tools.json](../bundle/tools.json)：七个宿主应用工具。`app_tool` 分派到共享业务核心；界面按钮和工具不维护两套采购逻辑。
- [AGENT.md](../bundle/AGENT.md)：模型办理顺序、证据引用、保存批准、任务绑定与失败语义。商品字段是数据，不是开发指令。
- `agent_task_sync_reply` 读取本次任务历史；`agent_task_cancel` 明确结束。历史文字不提供 turn 终态，不能代替宿主完成信号。
- `agent_task_binding` 只由 `agent_task_launch` 捕获（`task_id` + 需求/预算/硬关键词/目录来源/商户版本/起始研究版本），写工具须携带匹配 `task_id`；它是应用本地快照，**不是宿主身份认证**。
- 界面：`selection_summary_text`（选择摘要前置）、`refresh_proposal`/`proposal_state_text`（独立状态标题）、完整回复原文页；详细证据仍在原页面滚动区。

保存工具为 `risk=destructive`、`confirm=host`、`auto_approvable=false`。调用保存是在请求批准；执行时的版本、输入和时效校验仍须保留。

## 理解已验证的批准分支

```mermaid
sequenceDiagram
    participant A as 宿主 Agent
    participant T as 应用工具与共享核心
    participant H as 宿主批准
    participant S as 本地存储
    A->>T: 读状态、研究、创建提案（携带 task_id）
    T-->>A: 原始字段证据与绑定版本的提案
    A->>H: draft.save 请求
    H->>T: 用户批准后分派保存
    T->>T: 再检输入、版本与有效期
    T->>S: 检查通过才写入并核验
    A->>T: draft.read
    T->>S: 独立读取实际草稿
    T-->>A: 实际字段与一致性结果
```

宿主拒绝时不分派保存；状态校验失败时不写入。人工界面也复用研究和保存核心，但界面人工确认与 Agent 路径的宿主批准是两种入口。学习时先沿 `research_core → create_proposal_at → confirm_draft_core → draft_read_result` 阅读，再看 `app_tool` 如何分派到这些函数。

## 运行证据怎么对应源码（版本分开）

- **当前候选 0.5.1**：main `18647a97…`、tools `e3f0e0f5…`、AGENT `f02c135f…`、manifest `93096796…`、listing `21de8b0e…`；集群执行位置 `release/v0.5.1-staging/bundle`。
- **198242 RC5 人工 UI**：候选私有测试副本，官方未修改 Linux RC5 真实 Store Get/Install/Open，现有 13 项检查全通过，零模型、无录像（COMPLETED 0:0、CPU4、2:51）；测试副本 manifest 有 Linux/测试 publisher/签名改动，listing 有私有测试说明，**不继承原候选字节全通过**。
- **198215 历史旧包**：main `18647a97…`、AGENT `f02c135f…`、manifest `af045121…`、listing `9944a0d7…`，人工 UI 13 项通过（2:05）；包字节验证不继承。
- **197799 历史旧包**：main `fc005b81…`、AGENT `06a058…`、manifest `af045121…`、listing `9944a0d7…`，真实 MiniMax-M3 完成 5 个工具调用、宿主 `Approve once`、保存与八字段读回（M240 $22.99、预算 23、quiet）；之后不仅改 AGENT 文字，还改 UI 摘要及状态、未重跑模型。
- **197305 历史包**：main `4c3a5daa…`，其 94 秒视频与四张截图仅作历史。

198273 是候选上的新真实 M3 作业，已提交但首次授权待主控操作时 SSH 失联，未取回终态，不能称通过；模型请求数/退出码待取回。精确摘要、CPU 位置与未测项见 [VALIDATION](VALIDATION.md)。

当前是 14 条合成 + 3 条官网快照（整理摘要、非实时、仅商品价）的规则决策，不包含真实下单、支付、物流或真实检索模型效果。

## RC5 兼容与打包发布

- 官方 RC5 于 2026-10-11 发布（源码 `83d356c2…`），App Flow 更名为 OctoSense-App-Flow；将能力/network 声明改为用途披露由 **RC4 引入、RC5 延续**，保留设备同意/账户/人工写批准/存储隔离，新增 charts/Wasm 与 HTTPS 修复（本应用不使用）。**不宣称 60 秒超时已修复。** 当前候选 RC5 人工 UI 由 198242 覆盖，真实模型 198273 待取回。
- 官方 `stamp/check` 197371 对应旧包（main `4c3a5daa…`），**不适用当前候选**；当前候选只经旧 CLI `655114c4`（契约 1.8.0）`stamp/check --allow-unsigned` 结构检查，**不是**新 Hub `38635915`（1.12）工具链或 GitHub attestation 验证。
- 已有[官方发布工作流](../.github/workflows/publish-app.yml)由版本 tag 触发，生成 GitHub 证明、封存包与发布回执；**已由主控更新为官方 App Flow `45174df…` 模板、Hub pin `38635915…`，未跑 CI、未发布**。发布**逐次授权**。本工作树**尚未 push**。

## 条件变化后的重办入口

`proposal_change_summary` 比较提案快照与当前报价/输入/时钟；`agent_replan` 检查真实失效且未保存、未拒绝、无任务运行，再由共同的 `agent_task_launch` 发起新任务。上下文只是旧/新事实，不是批准；Agent 必须取得新研究版本并建立新提案。保存时再次校验，不能重用旧批准。

```mermaid
flowchart LR
  O[旧待确认提案] -->|报价或需求变化| S[旧确认被拒绝]
  S -->|明确点击重新办理| R[Agent重新研究]
  R --> N[新提案]
  N --> H[新的宿主批准]
  H --> W[保存新草稿]
  W --> V[独立读回字段]
```

## 后续优先级

先保证可复现交付和清楚的答辩。当前成熟候选已整合，界面已提供完整回复原文页，不再把“补长回复展开显示”列为待办。研发优先定位首次授权重试与宿主回调超时；预算冲突或其他路径只在新增需求/故障需要时验证，不机械扩测。接入实时商品目录或在线检索服务时保持业务核心与宿主适配分离，并单独报告数据来源和检索效果。新实录/答辩定稿与对外发布继续暂缓，等各自明确批准。


原六项顺序仍保留：0 中文/README/发布流程反馈已整合但未发布；1 宿主 Agent dispatch 可行性已有 RC1 证据；2 共享业务工具闭环已有 RC1 单用例；3 有出处报价、条件取舍、选择记录与界面表达已整合，198242 通过 RC5 人工 UI，198273 模型终态待取回；4 宿主超时最小复现与私有反馈完成，未提交或被接收；5 新求职/答辩素材暂缓。A/生成式搜广推、Jev、AgenticOS、全双工研究另行推进。

本轮网络恢复后先查询 **198273** 实际终态与 `live-result.json` / `live-wrapper.json`，再取 **198242** 小型结果和源码副本。首次授权尚无成功点击证据；不要跳过原生批准或重复提交模型。应用运行包留在集群，当前本地文档不包含尚未回传的原始结果。
