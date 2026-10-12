# RC5 真实模型预算闭环 — 199314

2026-10-12；真实 CN MiniMax-M3，官方未修改 Linux RC5，CPU4 / 6:47 / 0 GPU。
8次真实请求、7次工具调用（6种），17项直接相关判据通过。
20美元无解 → 原生批准22.99 → 同任务、同硬条件重新研究 → M240提案 →
另一次原生保存批准 → 实际草稿即时读回 → 独立draft.read匹配。

[完整结果](live-result.json)、[实际批准事件](approval-events.json)、
[实际草稿](purchase_draft.json)、[用量](usage-summary.json)、
[执行来源十文件](source-expected-sha256.json)、[调度结果](sacct.txt)。

main/tools/AGENT与当前0.5.4候选逐字一致；manifest/listing为当时0.5.3开发候选，
0.5.4元数据尚未安装实测。不是八工具全覆盖；未调用catalog.select/proposal.read。
宿主60秒回调仍超时，真实final经一次显式历史同步取回，主控明确结束；不是已修复。
没有实时商品/下单/支付；官网来源是人工整理的历史快照。
完整脱敏日志与宿主诊断留集群native/traceshop-budget-revision/live-check/run-199314。
