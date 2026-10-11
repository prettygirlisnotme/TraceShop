> **历史资料，只读参考。** 本页七个问答是 v0.4.0 的答复，当时的“当前源码 0.4.1”现已过时；当前作品版本为 **0.5.3**，工具契约、验证范围与发布状态以 [README](../README.md) 和 [VALIDATION](VALIDATION.md) 为准。本页不描述当前包，不用于当前提交。

# TraceShop — 作者对 Hub 扫描的答复（v0.4.0 历史答复） / author answers to hub scan

> 版本范围 / Version scope: 下面七个问答是 **v0.4.0（`4cf35ca8`）** 提交 App Hub #71 时的历史答复，保留原文与对照译文。**当前作品版本为 0.5.3，工具集、界面与证据状态均已变化**；本轮对评审建议的回应见文末[评审结果与本轮回应](#评审结果与本轮回应--preliminary-result-and-current-round-response)。
> The seven answers below are the historical answers for the **v0.4.0 (`4cf35ca8`)** bundle submitted to App Hub #71. **The current app version is 0.5.3, with a different tool set, UI and evidence status.** See the current-round response at the end.

导航 / Navigation: [中文作者答复](#中文作者答复) · [English author answers](#english-author-answers) · [模型验证口径 / Model-validation wording](#模型验证口径--model-validation-wording) · [评审结果与本轮回应](#评审结果与本轮回应--preliminary-result-and-current-round-response)

> 双语对照：下方英文为原始答复，中文为对照译文，两者表达同一事实。模型验证口径以本文件、[README](../README.md) 与 [SUBMISSION](../SUBMISSION.md) 中一致的段落为准。
> Bilingual note: the English answers below are the original text; the Chinese answers are a reference translation describing the same facts. Model-validation wording follows the consistent paragraph in this file, [README](../README.md) and [SUBMISSION](../SUBMISSION.md).

## 中文作者答复

1. **应用是否履行名称、副标题和描述所宣称的功能？** 在文档说明的合成目录与本地草稿范围内是。`research` 按预算和必需词过滤；`pick` 生成待确认提案；`confirm_draft` 写入 `purchase_draft.json` 并读回；`boot` 恢复已保存草稿。源码明确写着 `本地采购草稿；无真实下单、支付或物流。`（local purchase draft; no real ordering, payment or logistics）。原生 card-host 录屏演示了这些操作。

2. **listing 的平台和分类是否匹配？** 分类 `shopping`；平台 `linux`，使用官方 card-host 测试。没有对 macOS、Windows 或移动端作兼容性声明。

3. **授予的能力是否与可见操作匹配？** `storage` 仅用于保存/读取采购草稿。`octos.session.open`、`octos.turn.start` 和 `octos.turn.interrupt` 对应请求和取消可选的宿主审阅。没有 `net` 授权、没有申请网络主机、bundle 中也没有 API 密钥。可选审阅会经由宿主配置的提供方发送用户需求和候选事实；这一点在 PRIVACY.md 中披露。

4. **界面是否有欺骗性？** 没有。它使用 TraceShop 自己的 UI，把目录标注为演示、价格标注为 USD、保存结果标注为本地采购草稿。它不模仿系统权限弹窗、登录、支付页或商户结算。

5. **源码/数据中是否含有给助手（模型）的指令？** 有。`review_payload` 包含应用自撰的只读购物审阅提示词和所要求的 JSON 响应结构。用户需求和目录事实作为输入数据提供。`adopt_suggestion` 会核对来源提案/修订、商户版本、候选归属和截止时间；采纳只生成另一个待确认提案，不会保存草稿。仍须明确确认。在本 bundle 上记录了模型验证：见下方[模型验证口径](#模型验证口径--model-validation-wording)。

6. **是否有辱骂性措辞或针对私人的内容？** 应用 UI 及其 14 条合成目录中不存在此类措辞或功能。没有身份推断，也没有针对个人的内容。

7. **路由：通过、人工审核还是拒绝？** 首投未签名，建议人工审核。核心原生操作与官方 gate 已验证；standalone Rinx 中验证了一个真实宿主审阅用例；其他 shell 和移动平台仍未验证。发布者/支持/隐私字段完整。请评审实际固定的 bundle；本作者答复不构成维护者批准。

## English author answers

1. **Does the app do what its name, subtitle and description claim?** Yes, within the documented synthetic catalog and local-draft scope. `research` filters by budget and required words; `pick` creates a pending proposal; `confirm_draft` writes `purchase_draft.json` and reads it back; `boot` restores the saved draft. The source explicitly says `本地采购草稿；无真实下单、支付或物流。` (local purchase draft; no real ordering, payment or logistics). The native card-host recording demonstrates these operations.

2. **Do the listing's platforms and category fit?** Category `shopping`; platform `linux`, tested with the official card-host. No macOS, Windows or mobile compatibility claim is made.

3. **Do the granted capabilities match visible actions?** `storage` is used only to save/read the purchase draft. `octos.session.open`, `octos.turn.start` and `octos.turn.interrupt` correspond to requesting and cancelling the optional host review. There is no `net` grant, no requested network host and no API key in the bundle. Optional review sends the user's request and candidate facts through the host's configured provider; this is disclosed in PRIVACY.md.

4. **Is the interface deceptive?** No. It uses TraceShop's own UI and labels the catalog as a demo, prices as USD, and the saved result as a local purchase draft. It does not imitate a system permission prompt, login, payment sheet or merchant checkout.

5. **Does source/data contain instructions to an assistant?** Yes. `review_payload` contains the application-authored read-only shopping review prompt and a requested JSON response shape. User requirements and catalog facts are supplied as input data. `adopt_suggestion` checks the source proposal/revision, merchant version, candidate membership and deadline; adoption creates another pending proposal and does not save a draft. Explicit confirmation remains required. One live MiniMax-M3 response, JSON adoption and explicit confirmation/readback have now been verified on the v0.4.0 bundle in unmodified standalone Rinx. Official card-host still exercises the honest no-service behavior; the OctoSense shell path is not claimed verified. See the model-validation wording below for the consistent cross-document statement.

6. **Is any wording abusive or aimed at a private individual?** No such wording or feature occurs in the application UI or its 14-item synthetic catalog. There is no identity inference or personal targeting.

7. **Route: pass, human-review or reject?** Human-review for a first unsigned submission. Core native operations and the official gate are verified; one live host review case is verified in standalone Rinx; other shells and mobile platforms remain unverified. Publisher/support/privacy fields are complete. Please assess the actual pinned bundle; this author response is not a maintainer approval.

## 模型验证口径 / Model-validation wording

> 历史口径（v0.4.0）。当前0.5.3取得198504办理记录/完整回复的固定协议零模型证据；真实M3的198316仍对应0.5.1基线（6请求5工具）。精确范围见[VALIDATION](VALIDATION.md)与[README](../README.md)。
> Historical wording (v0.4.0). Current 0.5.3 has fixed-protocol, zero-real-model activity-record/full-reply evidence from 198504; real M3 run 198316 remains scoped to the 0.5.1 baseline (six requests, five tools). See [VALIDATION](VALIDATION.md) and [README](../README.md).

以下口径与 [README](../README.md)、[SUBMISSION](../SUBMISSION.md) 保持一致（v0.4.0 当时）。
This wording was kept consistent with [README](../README.md) and [SUBMISSION](../SUBMISSION.md) at the time of v0.4.0.

- 模型实测针对 v0.4.0 的同一业务脚本；0.4.1 只改文档、截图与发布配置，没有新的模型验证。
- 官方 Linux `card-host`（固定版本）实测了人工状态流转、人工确认与独立读回；宿主不提供 `octos` 审阅服务，应用如实显示不可用。
- 未修改的 standalone Rinx（固定 `5a9e2af`）使用其打包 octos 与 CN MiniMax-M3，在同一个 v0.4.0 bundle 上完成一条真实 JSON 审阅：模型建议 → 采纳生成 v2 待确认提案 → 明确人工确认 → 写入文件并独立读回一致。
- 未验证注入式 OctoSense Shell System Agent，也未验证手机/移动端。
- 该证据在 main 分支 `f07434ff` 收录，对应 v0.4.0（`4cf35ca8`）的 bundle BLAKE3；0.4.1 的 bundle 摘要以发布工作流产出为准，目前尚未发布。
- Official Linux `card-host` (pinned revision) covered manual state transitions, human confirmation and independent readback; the host exposes no `octos` review service and the app reports that honestly.
- Unmodified standalone Rinx at the fixed `5a9e2af` used its packaged octos plus CN MiniMax-M3 on the same v0.4.0 bundle for one real JSON review: model suggestion → adoption produced a v2 pending proposal → explicit human confirmation → file write and independent readback matched.
- No injected OctoSense Shell System Agent and no mobile validation.
- The model evidence belongs to v0.4.0 and its bundle BLAKE3; the 0.4.1 bundle digest will come from the release workflow and is not yet published.

## 评审结果与本轮回应 / Preliminary result and current-round response

2026-10-09，维护者 ZhangHanDong 在 [App Hub #71 评论](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/71#issuecomment-6077956506) 给出结果：**入围，86/100，评审版本 v0.4.0（`4cf35ca8`）**。App Hub 上架与奖项待后续流程。

On 2026-10-09 reviewer ZhangHanDong posted the result: **shortlisted, 86/100, reviewed version v0.4.0 (`4cf35ca8`)**. App Hub listing and awards remain pending later stages.

评审建议与本轮回应 / Reviewer suggestions and current-round response：

1. 把 Rinx 模型建议采纳的验证结论回写 README → 已在 [README](../README.md)、[SUBMISSION](../SUBMISSION.md) 与本文件中统一记录。
   Record the Rinx model-adoption conclusion in the README → now recorded consistently in [README](../README.md), [SUBMISSION](../SUBMISSION.md) and this file.
2. 为 listing 补充「提案确认」「草稿读回」两张关键状态图 → 0.4.1 增加 `screenshots/02-proposal.png`、`screenshots/03-readback.png`，复用 v0.4.0 card-host 真实运行素材，并由 `listing.json` 引用。
   Add two key state screenshots ("proposal confirmation", "draft readback") to the listing → 0.4.1 adds `screenshots/02-proposal.png` and `screenshots/03-readback.png`, reused from the v0.4.0 card-host run and referenced by `listing.json`.
3. 后续接真实商品数据源时同步 listing 与隐私说明的数据流向 → 尚未接入真实数据源，本版 listing 与隐私说明的数据流向不变；接入时同步。
   Sync the listing and privacy notice when a real product data source is added → no real data source is integrated yet, so the data flows in the listing and privacy notice are unchanged; they will be updated when one is added.
4. 改用 `tools/octo publish-github` 并提高版本号 → 已准备官方发布工作流与 0.4.1 版本；尚未发布，sealed pack 与 GitHub 证明待发布成功后回填。
   Switch to `tools/octo publish-github` and bump the version → the official publishing workflow and version 0.4.1 are prepared; not yet released, and the sealed pack and GitHub proof will be backfilled after a successful release.
