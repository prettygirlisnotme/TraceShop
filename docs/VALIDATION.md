# 运行范围与证据

更新：2026-10-11。本轮运行与素材编码在离线 CPU 作业内完成；本预览不包含密钥、私有签名材料、完整会话日志或模型权重。

## 真实 Agent 办理（运行 197305，最新事实源）

未修改官方 OctoSense Linux 0.1.0-rc.1 包，隔离私有 Store 安装，未更改全局信任。

场景：人工建立一份**待确认旧提案**（12.99 USD）。报价变化到 **14.94 USD** 后，旧提案确认被**拒绝，且没有产生草稿**（`stale_confirmation_rejected_no_draft=true`）。随后用户明确把任务交给 Agent 重办。

真实 CN MiniMax-M3 自主执行 `status.read → catalog.research → proposal.create`，经宿主 **Approve once** 后执行 `draft.save → draft.read → final`。6 次模型请求、5 个工具调用。批准前无草稿，批准后才写入；独立读回的 **8 个草稿字段与提案一致**（`save_read_draft_fields_consistent=true`）。

结果：选中 item4 VicTsing Wireless Mouse，**14.94 USD**，预算余量 **15.06**；`draft_id=d-p-1791648896-2`，`proposal_id=p-1791648896-2`，`revision=2`，`research_revision=2`，`merchant_version=2`。静音依据为 `description` 的 Quiet 原文与 `features` 的 Silent click（`documented`）；item1/item2 为 `not_documented`，不据此声称它们不支持静音。

本轮 final 的价格说明与目录原始价格一致（`prices_correct_in_this_run=true`）。同步的本次任务历史文字与 provider final **逐字相同**（`history_equals_provider_final=true`），并已显式结束。源码与紧凑界面均在本次 197305 运行中验证。

## 源码对应

真实模型运行源码：main.splash `4c3a5daabb267dfe05586802f66aed70400f80f312920844986b2946a8292c53`；AGENT.md `dd5f1e9ebc57bf488a1cb05e5fd8a4e1cd658ad7d7a0419c8eaca545244dd90d`；tools.json `c51e4df96eef9f719b874a49fc330ea63cfb282eba3dc76bce4e07728f0174f3`（六工具定义未变）。

## 演示与打包证据

- [94秒节选](../evidence/native-agent-excerpt-197305.mp4)剪去等待、裁出完整应用窗口，保留原生批准弹窗；[字幕](../evidence/native-agent-excerpt-197305.zh-CN.srt)和[来源](../evidence/native-agent-media-197305.json)随附。
- 完整连续原片368.169秒/368帧/零错误，保存在私有集群；本候选不包含该大文件，不能把节选称连续录屏。
- 四张包内截图来自197305同次真实采集。裁切990×646（x84,y100），逐张核对裁切前后RGBA像素一致。
- 原生批准由测试控制器按真实界面显式点击；基线走人工UI入口，重新办理的研究、选择、建提案、保存请求和读回由MiniMax自主完成。
- 官方开发包检查197371（CPU2、COMPLETED0:0）通过，最终10文件与[检查摘要](../evidence/bundle-check-replan.json)逐项一致。[原始输出](../evidence/bundle-check-replan.txt)明确unsigned及保存工具每次等待宿主批准，不代表正式发布证明。


## 仍有的限制

- 宿主 **60 秒回调超时**仍存在；本轮通过显式同步本次任务历史取回真实 final，历史不提供 turn 终态，**仍需用户明确结束**。
- 首次工具授权后立即重试的时序根因**未定位**；观察到的延后成功不能算根因修复。
- 六工具未逐一实测：本序列调用 5 个，`proposal.read` 未单独调用；预算 13 场景未测；拒绝/无变化/进行中任务等路径未全覆盖。
- 本次最终开发包检查已通过（197371，不继承b3结论）；生产签名、Release与App Hub更新未执行。
- 目录为 14 条合成 USD 商品，未接入真实商品/检索服务或原生 Project A，无真实下单、支付、物流。

## 历史证据（不作新版主证据）

- 早期人工 UI 录像 197066（78.24 秒，零模型调用）与 196923 早期模型运行仅作历史记录。
- 196923 的 final 曾出现一处价格比较错误；本轮 197305 的价格说明与目录一致，但旧文字记录不可修改，仅作历史。
