> 2026-10-13：版本0.5.4作品说明。发布与准入以官方Release及App Hub #71为准。历史 **86/100** 评语仅对应 **v0.4.0**，不针对当前 **0.5.4**。

# TraceShop · OctoSense 购物与物流

队伍：TraceShop。唯一成员：TraceShop-Felix。赛道：OctoSense 购物与物流。

## 作品

TraceShop 是 **OctoScript / Splash** 应用，唯一入口 [`bundle/`](bundle/)（版本 **0.5.4**，**八个**应用工具）。它把一次采购决策拆成可核对、可回溯的步骤：Agent 读取状态、切换目录来源、研究候选、创建提案；无候选且只读替代项超预算时，按Agent策略可在同一任务中申请一次预算修订（不是处理器硬限次），**只有用户经宿主批准后才改预算并强制重新研究**；**保存必须另经宿主批准**，写入宿主私有存储中的本地草稿，并由 Agent 独立 `draft.read` 读回核对。界面与八个应用工具共用同一套研究/提案/保存核心。

目录由 **14 条**合成演示商品与 **3 条**人工整理的官网价格快照（Logitech，US/USD）组成；快照是整理摘要、**非实时**、仅商品价，运费/税费/配送未核验。结果是宿主私有存储中的采购草稿，**没有真实下单、支付或物流**。

产品主线是“有证据、能应对条件变化的个人采购决策”：预算与硬关键词是强约束，软偏好只认目录原始字段证据，候选与只读替代严格分开，条件变化会阻止旧提案保存并要求重新研究、重新批准、重新核验。

## 材料（均在仓库内）

- [产品首页](README.md) · [OctoScript 源码](bundle/main.splash) · [工具声明](bundle/tools.json) · [应用 Agent 指引](bundle/AGENT.md)
- [验证范围](docs/VALIDATION.md) · [复现说明](docs/REPRODUCING.md) · [开发者接手](docs/HANDOFF.md) · [演示提纲](docs/DEMO.zh-CN.md)
- [隐私说明](PRIVACY.md) · [Apache-2.0](LICENSE)

## 证据状态

- **当前候选 0.5.4**：业务源码 `main 43b89dde…` / `tools 4d10e50b…` / `AGENT d079839b…`；十文件摘要见 [package-inputs.json](package-inputs.json)（本地摘要**不是**官方签名）。
- **RC6真实模型闭环 202120**：[同次原生视频与证据](evidence/rc6-budget-202120/README.md)。官方未修改Linux RC6、私有测试安装，真实CN MiniMax-M3完成预算20无解→单独原生批准22.99→同任务重新研究→M240提案→另一次原生批准保存→独立读回匹配。8次模型请求、7次工具调用、6种工具；非八工具全覆盖。原始汇总器ID配对错误及独立17项复核详见证据说明。
- **最终结构检查 [202195](evidence/rc6-package-202195/README.md)**：固定App Hub `38635915`对最终截图/文案的十文件输入stamp私有派生包并`check --allow-unsigned` PASSED，输入未改；**不是**正式签名、封存或发布证明。
- **当前素材**：**112.74秒、965943字节**，同次202120原片顺序剪去等待，内嵌中文字幕并提供独立SRT；原分辨率截图来自同次原生帧。旧0.5.0视频保留为历史，不混入本次视频。
- 未接入实时商品目录、在线检索服务或原生 Project A；不把未实现能力写成已有功能。

## 发布与审核

- 公开仓库：[prettygirlisnotme/TraceShop](https://github.com/prettygirlisnotme/TraceShop)。确切版本、证明与封存包以该仓库的实际Release为准。
- App Hub：[提交项 #71](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71)；上架与奖项状态以该页面当前显示为准。
- 发布走候选自带的 [.github/workflows/publish-app.yml](.github/workflows/publish-app.yml)，版本 tag 触发，固定 App Hub `38635915`；真实 public 仓库 tag 由 OIDC 证明，**无需生产签名 secret**，产出 `app.bundle.pack.json` / `octosense-app-manifest.json` / `release-receipt.json`。**Release 不等于 App Hub 准入**。
- 截至本次材料准备时的检查与发布状态见[VALIDATION](docs/VALIDATION.md)，不以演示或本地摘要替代正式证明。

## 视频与截止

比赛要求使用**最新 OctoSense**；截止 **2026-10-14 北京时间09:00**。本次使用官方最新桌面RC6，提供GitHub上的[真实原生视频](evidence/rc6-budget-202120/demo.mp4)与[中文字幕](evidence/rc6-budget-202120/demo.zh-CN.srt)，精确时长及来源见证据目录。视频展示获授权控制端操作首次Allow和两次业务批准，不宣称模型代替用户批准。
