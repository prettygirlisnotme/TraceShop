# TraceShop · OctoSense 购物与物流（提交草稿）

> **状态：本地草稿，尚未正式提交。** 本文件用于整理材料，不代表赛方已审核或认可本版本；2026-10-09 的 86/100 为**历史初赛评语**，对应 v0.4.0，不针对当前 0.5.1。本届正式提交与对外发布需单独明确批准。

队伍：TraceShop。唯一成员：TraceShop-Felix。赛道：OctoSense 购物与物流。

## 作品

TraceShop 把一次采购决策拆成可核对、可回溯的步骤：Agent 读取状态、研究候选、创建提案；**保存必须经宿主批准**，写入宿主私有存储中的本地草稿，并由 Agent 独立 `draft.read` 读回核对。作品唯一入口是 [`bundle/`](bundle/)（OctoScript / Splash，版本 0.5.1），界面与七个应用工具共用同一套研究/提案/保存核心。目录为演示数据，**没有真实下单、支付或物流**。

产品主线是“有证据、能应对条件变化的个人采购决策”：预算与硬关键词是强约束，软偏好只认目录原始字段证据，候选与只读替代分开，条件变化（报价/需求/版本）会阻止旧提案保存并要求重新研究、重新批准、重新核验。

## 材料（均在仓库内）

- [中文首页](README.md) · [OctoScript 源码](bundle/main.splash) · [工具声明](bundle/tools.json) · [应用 Agent 指引](bundle/AGENT.md)
- [验证范围与版本](docs/VALIDATION.md) · [复现说明](docs/REPRODUCING.md) · [开发者接手](docs/HANDOFF.md) · [三分钟答辩稿](docs/DEMO.zh-CN.md)
- [隐私说明](PRIVACY.md) · [Apache-2.0](LICENSE)

## 证据状态（简洁版）

- **当前候选 0.5.1**（main `18647a97…` / tools `e3f0e0f5…` / AGENT `f02c135f…` / manifest `93096796…` / listing `21de8b0e…`）：十文件本地摘要见 [`package-inputs.json`](package-inputs.json)；本地摘要**不是**官方签名。
- **RC5 人工 UI 198242**：官方未修改 Linux RC5 真实 Store Get/Install/Open，现有 13 项人工 UI 检查全通过，零模型、无录像（COMPLETED 0:0、CPU4、2:51）。私有测试副本 manifest 含 Linux/测试 publisher/签名改动，listing 含私有测试说明，**不继承原候选字节全通过**。
- **真实模型闭环 197799**（较早业务 main `fc005b81…`、AGENT `06a058…`）：真实 CN MiniMax-M3 6 请求 5 工具，经宿主 Approve once 保存 M240 $22.99 并独立读回通过；因后续不仅改 AGENT 文字，还改 UI 摘要及状态且未重跑模型，**不能当作当前 0.5.1 的模型验收**。
- **真实模型 198273**（候选 0.5.1）：已提交；首次授权待主控操作时 SSH 失联，**未取回终态，不能称通过**；模型请求数/退出码待取回。恢复 VPN 后先读结果，不盲目重提。
- **历史素材**：94 秒节选（`evidence/native-agent-excerpt-197305.mp4`）与 `bundle/screenshots/01–04` 均来自 **197305 旧合成目录**流程，仅作历史，不对应当前包。
- **RC5 与官方检查**：将能力/network 声明改为用途披露由 **RC4 引入、RC5 延续**；官方 RC5 于 2026-10-11 发布（源码 `83d356c2…`），本应用不使用 RC5 新增 charts/Wasm，也不宣称 60 秒宿主超时已修复。此前 197371 官方检查对应旧包，不适用于当前候选；当前候选只经旧 CLI `655114c4`（契约 1.8.0）`stamp/check --allow-unsigned` 结构检查，**不是**新 Hub `38635915`（1.12）工具链或 GitHub attestation 验证。
- 未接入实时商品目录或在线检索服务（已有 3 条官网快照）或原生 Project A；不把生成式搜广推、AgenticOS、全双工等未实现能力写成已有功能。

## 发布与审核（本地，未发布）

- 公开仓库：[prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop)；本工作树**尚未 push**，未 tag、未建 Release。
- App Hub：[提交项 #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71)；上架与奖项状态以该页面当前显示为准。
- 发布工作流为版本 tag 触发；已由主控更新为官方 App Flow `45174df…` 模板、Hub pin `38635915…`，**未跑 CI、未发布**。正式封存包、GitHub 证明与发布回执须由发布工作流成功产出，工作流产出不等于 App Hub 准入。
- 正式提交材料与对外动作**暂缓**，每次需单独批准。
