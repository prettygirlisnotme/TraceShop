# 验证说明

本仓库区分几类证据：随包可自行运行的标准库检查、公开检出目录的复验、交付包验收、私有集群宿主工作流实测，以及可选的 Rinx 原生 Agent 审阅。它们证明的范围不同，不能互相替代。当前材料版本 **v0.3.0**；新增流程的真实结果见第 0 节，旧作业保持各自证据范围。

## 0. v0.3.0 候选选择与真实 Agent 采纳

2026-10-02，作业 180215，CPU 8，2 分 09 秒，COMPLETED 0:0。已有 11 项标准库检查通过；同一真实浏览器会话与固定 Rinx / octos 完成以下流程：

- 规则研究推荐候选 3；用户选择候选 4，生成新提案，采购草稿数仍为 0。
- 真实 MiniMax-M3 经原生终态回调返回 JSON，比较价格、DPI 和静音特征后选择候选 4；用户粘贴并采纳，生成另一新提案，草稿数仍为 0。
- 模拟涨价后，旧建议被 409 拒绝，旧提案确认被 quote_changed 拦截；重新规划后用户再次确认，独立读回商品、提案、价格和状态一致。
- 10 项相关操作检查均通过，无页面错误；这是一条实测流程，未据此宣称稳定推荐准确率。

证据：[结构化结果](../evidence/agent-workflow-checks.json) · [候选选择](../evidence/candidate-selected.png) · [建议采纳](../evidence/agent-adopted.png) · [重新确认与核验](../evidence/workflow-verified.png) · [真实原生回复](../evidence/agent-workflow-native.png)。原生包 0.3.0 的官方 BLAKE3 为 80b72b23174a2d3123e8c6798d4cc19db35f9984e0bb6a7f733089453078ef63。

[演示短片](../evidence/agent-workflow.webm)由本次真实网页录屏与独立原生截图剪辑，裁掉模型等待；不是连续原生桌面录像。最初保存步骤在 Playwright 关闭后取视频路径失败，随后作业 180221 直接整理已录制文件，没有重复模型请求或业务流程。

最后的界面整理把 Agent 复制/采纳工具默认折叠、优先显示商品特征，作业 180223 在同一后端下实际点击候选并展开工具，生成[当前界面](../evidence/presentation.png)。这两项仅为素材/界面整理，没有新增模型调用。

以下为各自版本的历史基线。

## 1. 历史：原生 Agent 审阅（作业 180063，2026-10-02，v0.2.1）

CPU-only，1 分 52 秒（112 秒），COMPLETED 0:0。使用**未修改**的固定 Rinx（`5a9e2af`，二进制 SHA-256 `60431b16b8e67f2167eae951bec306ca0a554f02264c798e3cf1ef78ec29a720`）与官方打包的固定 `octos` 内核（`fe08d8e…`，`2.0.3-rc.13`），真实浏览器导出与原生 Rinx 导入在同一次作业内闭环：

- 浏览器导出检查：研究 200、复制不新增草稿、导出字段逐项匹配（候选 3 条、硬/软约束、报价版本、有效期），并校验 `time_context`——`proposal_created_at_utc` 与服务端一致、`current_time_utc` 为 `null`；报价变化后旧导出被清除、新研究可再导出、无禁止字段、无页面错误（[agent-review-browser-checks.json](../evidence/agent-review-browser-checks.json)）。
- 原生导入：stamped bundle `0.2.1`（BLAKE3 `3051f8f0f988d79f5a275b90d98a4ce1fde3b317b84cc5f4737e5410e6f807e0`），Review 能力恰为 `octos.session.open`、`octos.turn.start`、`octos.turn.interrupt`，无 room。
- assistant 关闭时返回真实宿主错误 `The assistant is off. Choose this device or a server in the assistant settings.`
- 经真实宿主 UI 配置本机 provider（CN `minimax-cn`，`MiniMax-M3`）后，`session.open` 与 `turn.start` 经真实 Splash 回调完成，终态标签“审阅完成（建议未执行）”，返回非空建议；源码与 `Cargo.lock` 未改。
- 脱敏截图：[结果](../evidence/agent-review-result.png)、[assistant 关闭](../evidence/agent-review-off.png)、[导出](../evidence/agent-review-export.png)；aggregate JSON 见 [agent-review-checks.json](../evidence/agent-review-checks.json)。

**边界**：这是 standalone Rinx 的本地 Agent peer，不是宿主注入的 OctoSense System Agent，也不是 Web 的自动 bridge；未经签名或 App Hub 上架。模型建议可能出现错误，权威判断仍是 Web 的确定性有效期与版本检查。v0.2.1 提示明确区分创建/截止/当前时间、并说明空数组表示“用户未设置”后，本次回复不再把未过期提案判为过期、也不再把空数组说成缺失；但这是**单次用例改善，不是稳定的准确率成功**。此前同组合的 v0.2.0 运行为作业 **180045**，其误判保留在 [v0.2.0 的 agent-review-checks.json](https://github.com/prettygirlisnotme/TraceShop/blob/v0.2.0/evidence/agent-review-checks.json)。

## 2. 历史：公开检出目录复验（作业 180053，2026-10-02）

CPU-only，6 秒，COMPLETED 0:0。对 **v0.2.0 公开目录**使用系统 Python `-I -S -B`、清理继承环境，标准库导入、11 项检查及 HTTP 确认/读回/幂等/拒绝/报价变化路径全部通过；自测服务已停止。摘要见 [public-checks.json](../evidence/public-checks.json)。同一复验此前也用于 v0.1.1（作业 **178861**，2026-10-01，12 秒）。

v0.2.1 只改 Web 导出与原生审阅包，后端与 `vendor/` 未变，因此该 11 项检查 + HTTP 基线继续适用。它**不覆盖 v0.3.0** 的候选选择与 Agent 采纳路径。

## 3. 随包标准库检查（任何人可复跑）

```bash
python3 -m unittest discover -s tests -v
```

工作流/行为检查覆盖：正常确认与幂等重开、拒绝不产生草稿、无可行预算、提案后涨价被拦、过期提案被拦、重规划取代旧提案并推进版本、输入校验与 owner 绑定、按当前报价重规划且守住预算、重规划排除缺货项、目录健康、以及 HTTP 研究/确认与错误结构。这些是行为检查，不是检索质量基准。

## 4. 历史：交付包验收（作业 178692）

在独立解压目录、以系统 Python、禁用第三方包并清理环境变量的方式运行：**11 项标准库检查 + HTTP 闭环 + 真实浏览器**（含图标 SVG 响应）全部通过。HTTP 闭环覆盖研究、确认、读回、拒绝后确认被拦、涨价后确认被拦（HTTP 409）等。作业 COMPLETED 0:0。

## 5. 历史：私有集群宿主工作流实测（作业 178695）

在私有回环合成 fixture 内，使用官网示例链接的历史固定宿主 `05daf9bdb05fafc6d8f04dcb312a35f1d46a661e`（独立编译），完成 **10 项**结构化检查：

- 宿主原生登录、接收并渲染 incoming URL 卡片、原生「Open in browser」调用真实 URL 打开器；
- 宿主 UI 自行发送卡片，且新卡片发送者与 incoming 卡片发送者不同、正文包含应用 URL；
- 浏览器加载原生打开器记录的原始地址，研究/确认/独立读回字段逐字一致；
- 应用真实剪贴板复制成功，复制文本与页面文本一致；
- 模拟涨价后可分享入口被清除，重规划可行；
- 原生结果回传事件的正文 UTF-8 哈希与真实剪贴板内容一致。

该作业为 CPU-only、COMPLETED 0:0。演示截图与浏览器实录见 `evidence/`。

## 6. 证据的边界

- `evidence/` 中的浏览器截图与约 60 秒 WebM 是**历史 v0.2.1 Web 原型**的实录；宿主截图与原生 Agent 审阅截图是**独立定格**，两者不是同一段连续录屏。这些都不证明 v0.3.0 新流程。
- v0.3.0 的 [agent-workflow.webm](../evidence/agent-workflow.webm) 为真实 Web 录屏并裁去模型等待 + 真实原生截图，须明确标注为独立片段。
- 上述宿主实测使用的是**合成 fixture 与小型合成目录**，**不能**证明公开线上商户、实时报价、主办方受理或晋级结果。
- 原生 Agent 审阅针对固定 Rinx `5a9e2af` 与固定 `octos`（v0.2.1 为只读建议）；不承诺最新移动中的 main、Windows 或其它未测试平台。
- 模型建议只是只读文本，仍可能在其它用例出错；Web 的确定性时钟与版本检查始终是权威。
- 「Open in browser」经由透明 headless URL 打开器适配器完成，不是桌面默认 GUI 浏览器。
- 本包不包含历史目录、模型、数据库、凭据或认证日志；随包目录为自编合成数据。
