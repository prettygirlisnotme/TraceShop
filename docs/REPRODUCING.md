# 运行与复现

TraceShop 是 **OctoScript / Splash** 应用，唯一入口是 [`bundle/`](../bundle/)（版本 **0.5.4**），声明**八个**应用工具。需要支持 `script-tools-v1` 与 `app_tools.dispatch@1` 的宿主；应用不含 Rust/native 代码，不训练模型，也不携带任何模型密钥——模型服务由宿主提供方配置。

## 环境与依赖

- **作者实测环境**：Linux、4 CPU / 12 GiB / 0 GPU，运行证据来自Slurm；这不是使用者必须接入学校集群的要求，其他平台未据此验证。
- **宿主**：源码 bundle 可用官方 card-host 开发预览运行，但**开发预览不等于完整的宿主 Agent / 商店安装验收**。完整验收需使用兼容的官方 **RC6** 宿主；最新官方桌面版为 [`desktop-v0.1.0-rc.6`](https://github.com/OctoSense-org/OctoSense/releases/tag/desktop-v0.1.0-rc.6)（source `f9f6fea9`）。
- **官方工具链与发布流程**：[OctoSense-App-Flow](https://github.com/OctoSense-org/OctoSense-App-Flow)。

## 数据来源

目录来源可在会话内切换（`shopping.catalog.select`）：

- `synthetic_demo`（默认）：**14 条**纯虚构 USD 演示商品。
- `official_snapshot`：**3 条**人工核对的官网页面价格快照（Logitech，US/USD）。是整理摘要而非整页原文，**非实时**，只有**商品价**，运费、税费与配送未核验，也不保证库存或可配送。快照内嵌于脚本，运行时不联网抓取。

没有接入原生 Project A 检索、实时目录或真实交易；**没有真实下单、支付或物流**。

## 复现当前闭环

1. 开发时按官方App Flow用card-host预览可编辑`bundle/`，这不包含完整宿主Agent验收。完整使用须在兼容RC6中安装已获准入的包；商店不会直接接受未签名源码。发布与准入分别查看实际Release和App Hub #71；作者的私有测试安装不代表公开商店已准入。
2. 在**宿主侧**配置兼容工具调用的模型提供方（密钥由宿主管理，应用不带密钥）。作者真实CN M3证据使用隔离的非流式→SSE传输适配，不改工具/参数/返回、不注入答案；不能据此宣称厂商原生SSE兼容问题已修复。
3. 输入需求、USD 预算与硬关键词，或使用预设按钮（只预填条件，不研究、不保存）。
4. 手动研究/选择/确认，或委托宿主 Agent 办理。无候选且只读替代项超预算时，Agent策略最多申请一次预算修订（处理器没有强制总次数上限），**只有宿主批准后才改预算并强制重新研究**；保存另需一次宿主批准，随后由 Agent 独立 `draft.read` 读回核对。
5. 宿主 **60 秒回调仍可能超时**；超时不会伪造成功或跳过确认，需通过**显式历史同步**取回回复并明确结束任务（助手文字不是任务终态）。

## 已运行的证据

- **当前RC6真实模型闭环**：[202120视频与回执](../evidence/rc6-budget-202120/README.md)，使用业务源码`main 43b89dde… / tools 4d10e50b… / AGENT d079839b…`。官方未修改Linux RC6、私有测试安装下，真实CN MiniMax-M3以8次请求完成：预算20无解→原生批准22.99→同任务重研究→M240提案→另批保存→独立读回匹配。原始汇总器ID配对错误保留，零API独立复核原17项全部成立。不是八工具全覆盖或公开商店准入证明。
- **RC6 固定协议兼容**：[199373](../evidence/rc6-budget-199373/README.md) 在官方未修改 Linux RC6、真实 Store 安装下，以固定 loopback 协议、**零真实模型**验证预算批准、旧预算拒绝、强制重研究与待确认提案；**无草稿保存**，不能当作真实模型或自主决策证据。
- **最终结构检查**：[202195](../evidence/rc6-package-202195/README.md)用固定App Hub `38635915`对最终十文件输入stamp私有派生包后`check --allow-unsigned` PASSED，原始输入未改。这**只是未签名结构检查**，不是正式签名、封存或发布证明；201964仅是先前输入的历史检查。

## 正式发布

候选自带 [`.github/workflows/publish-app.yml`](../.github/workflows/publish-app.yml)，按版本tag触发，固定App Hub `38635915`。在真实public仓库打tag后，由GitHub OIDC提供证明，**开发者无需生产签名secret**；工作流产出`app.bundle.pack.json` / `octosense-app-manifest.json` / `release-receipt.json`。**Release不等于App Hub准入**；以实际工作流回执和Hub审核为准。

## 局限

- 八工具并非逐个真实模型覆盖；202120未调用`catalog.select` / `proposal.read`。
- 60 秒宿主回调限制仍在，真实 final 经一次显式历史同步取回。
- 目录为合成与人工整理快照，无实时目录、真实检索模型、真实交易或质量提升证据。
- 应用本地任务绑定不是宿主身份认证；门控与来源核对不等于通用语义正确性。
- 模型原回复存在未限定范围的“唯一硬条件匹配”说法，证据不支持其扩展到全目录；视频字幕不重复该断言，原回复保留。字段一致不保证解释或推荐质量正确。
- 比赛要求使用**最新 OctoSense**；截止 **2026-10-14 北京时间 09:00**。
