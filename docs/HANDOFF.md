# 开发接手

更新：2026-10-13。当前 **0.5.4** 优先完成北京时间 **10月14日09:00** 的比赛交付。先读[产品首页](../README.md)、[验证范围](VALIDATION.md)和[运行说明](REPRODUCING.md)。当前真实模型主证据为[RC6实录202120](../evidence/rc6-budget-202120/README.md)：两次业务批准、同任务重研究、保存和独立读回均有实际工具回执。

## 唯一业务入口

| 文件/函数 | 职责 |
| --- | --- |
| [bundle/main.splash](../bundle/main.splash) · `app_tool` | 八工具分派；界面和Agent共用采购业务核心 |
| `research_core` | 按预算/硬关键词筛选，保留字段证据；候选与只读替代分开 |
| `revise_task_budget` | 宿主批准后校验task/旧预算/输入，更新当前预算、保留初始预算，使旧研究失效 |
| `create_proposal_at` | 绑定需求、研究和商户版本，保存选择依据快照 |
| `confirm_draft_core` / `draft_read_result` | 保存时再校验；实际写入后核验，并支持独立读回 |
| [bundle/tools.json](../bundle/tools.json) / [bundle/AGENT.md](../bundle/AGENT.md) | 工具契约与模型办理指引 |

阅读主链：`app_tool → research_core → revise_task_budget → research_core → create_proposal_at → confirm_draft_core → draft_read_result`。不为录制更改业务三文件或强制模型选择。

## 必须保留的行为

- 首次Allow是准许此应用使用宿主Agent；预算修改和草稿保存是随后两个独立业务批准。`confirm=host`、`auto_approvable=false`不能被模型文字或之前的批准替代。
- 写调用须匹配active的`task_id`及当前需求/硬词/目录/版本；预算修改只更新预算，强制重新研究，不能把超预算替代直接变成可保存提案。
- `selection_record`记录当时需求、预算、字段依据和相邻研究比较，随草稿落盘；它不是用户对所有语义逐项认可。隐私处理见[PRIVACY](../PRIVACY.md)。
- UI办理记录只来自实际应用工具返回，内存缓存最多12条（不是API预算声明）；完整回复保留原文。助手文字、记录条数和文件存在都不能单独证明任务成功。
- `agent_task_sync_reply`读取历史，`agent_task_cancel`明确结束；回调超时与宿主turn结束分开判断，不能靠改文字隐藏运行失败。

## 版本与证据衔接

业务来源`d0883be2…`的三文件摘要为`43b89dde… / 4d10e50b… / d079839b…`。最终十文件由[202195](../evidence/rc6-package-202195/README.md)的固定Hub `38635915` stamp派生包和allow-unsigned检查通过，输入未变；它不产生正式签名、GitHub证明或Hub准入。RC5/固定协议/201964历史范围见[VALIDATION](VALIDATION.md)。

202120使用8次M3请求、7次工具调用（6种），119574tokens；原汇总器完整ID连接失败，Slurm FAILED4:0和原报告保留。仅两前缀唯一suffix配对、canonical和顺序一致的零API复核沿用原17判据，17/17成立；不代表修复宿主超时或提升推荐质量。失败尝试与原片保留，当前视频不拼接其他运行。

最终视频为112.74秒、965943字节，SRT末cue112.740秒；原分辨率四图与同次原片一致。最终截图/说明与摘要已更新，最终commit和正式发布证明分别记账；无需为纯媒体/文档变化机械重跑M3。

## 打包与发布接手

- 原始候选、私有测试部署副本、官方发布工作流派生包必须区分。临时测试签名不代表生产身份或App Hub准入，密钥不入仓库/证据。
- [publish-app.yml](../.github/workflows/publish-app.yml)固定Hub `386359153ed6377b5f047bd9ed2767a6a2ac2bc7`，版本tag触发GitHub证明与Release；最终公开commit、tag和媒体须具体审阅批准后操作。
- App Hub #71仍须更新确切版本/Release并由维护者审核，Release成功不能写成比赛受理。当前八工具是规则/快照目录上的LLM编排，独立研究结果不继承为原生生成式搜广推效果。
- 当前仅收口交付，不继续Jev/语义研究、训练、UI扩张或机械回归矩阵。所有作者运行证据来自Slurm；本机只编辑、控制与取小结果。
