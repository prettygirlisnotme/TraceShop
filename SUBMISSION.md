# TraceShop · OctoSense 购物与物流

队伍：TraceShop。唯一成员：TraceShop-Felix。赛道：OctoSense购物与物流。

## 作品与材料

TraceShop将采购需求变成可审阅的提案：Agent研究目录证据，用户批准后保存本地草稿，再独立读回。六个应用工具与界面共用业务核心；目录包含14条合成USD商品，没有真实下单、支付或物流。

- [中文首页](README.md) · [OctoScript源码](bundle/main.splash) · [工具声明](bundle/tools.json)
- [紧凑原生连续录像78.24秒](evidence/native-ui-197066.mp4) · [中文字幕](evidence/native-ui-197066.zh-CN.srt) · [当前候选界面截图](evidence/native-candidates-197066.png)
- [真实MiniMax-M3运行摘要](evidence/agent-run-196923.json) · [宿主保存批准](evidence/agent-host-approval-196923.png)
- [验证范围与局限](docs/VALIDATION.md) · [三分钟答辩稿](docs/DEMO.zh-CN.md) · [隐私说明](PRIVACY.md)

录像（78.24秒、217帧）是自动化操作人工UI，零应用模型调用；当前main.splash为 e344068d（紧凑界面）。真实模型自主证据来自独立运行196923的较早文字快照（main ed412c2c/AGENT b6f28f03），业务文字修正与紧凑界面未重跑模型。[完整提案](bundle/screenshots/02-proposal.png)、[草稿核验](bundle/screenshots/03-readback.png)与[旧提案拒绝](bundle/screenshots/04-requote.png)均来自同次197066；版本与验证范围在材料中分别标明。

## 发布与审核

公开仓库：[prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop)。正式版本、封存包与发布回执见[Releases](https://github.com/prettygirlisnotme/TraceShop/releases)。

2026-10-10：最终0.5.0开发bundle经官方stamp/check --allow-unsigned通过（CPU作业197113，2秒），[输出](evidence/bundle-check-compact.txt)与[文件摘要](evidence/bundle-check-compact.json)随仓库保存。正式GitHub证明、封存包与回执须由发布工作流产生；工作流产出不等于App Hub准入。App Hub当前审核状态见[提交项#71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71)。

初赛[官方评语](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71#issuecomment-6077956506)确认入围，86/100，评审版本v0.4.0（4cf35ca8）。下一轮收到的群通知为10月14日提交、15日分组答辩；具体时刻和线下安排以主办方通知为准。
