# TraceShop · Agent 审阅（Rinx 本地审阅导入包）

这是用于 **Rinx 本地导入** 的最小审阅小程序，配合 Shopping Decision Agent Web 页面的
“复制给 Agent 审阅”入口使用。它把用户主动粘贴的候选/提案资料交给宿主 `octos` 做**只读建议**。

## 这是什么 / 不是什么

- 是：一个可被 Rinx 导入的本地小程序包（`main.splash` + `manifest.json`），只申请
  `octos.session.open`、`octos.turn.start`、`octos.turn.interrupt`。
- 是：用户刻意操作的协作入口：Web 页面复制资料 → 粘贴到这里 → 明确点击“发起审阅”。
- 不是：App Hub 已上架或已签名发布的应用。
- 不是：Web URL 卡片的自动 bridge；浏览器页面不会自动调用 `octos`，也不会自动把资料送到这里。
- 不是：自动批准器。Agent 只给建议，不会修改商品、放宽约束、批准草稿、下单或发消息。

## 使用流程

1. 在 Shopping Decision Agent 网页完成研究，出现“交给 Agent 审阅”区块后，点“复制给 Agent 审阅”。
2. 在 Rinx 中导入本包并打开，把资料粘贴到输入框。
3. 由用户明确点击“发起审阅”。返回的是 `octos` 的文字建议。
4. 回到网页，由用户自己决定是否确认；提案或报价变化后需要重新审阅。

## 契约与前提

- `octos.turn.start` 只传 `text`（固定只读审阅指令 + 用户粘贴资料），不超过 32 KiB；
  不传 provider/model/session/approval，也不使用 `matrix.profile`、`net`、`storage`、`agent` 或 `os.*`。
- 出错时直接显示宿主返回的真实错误，不伪造回复、不用模型替身。
- “取消当前审阅”调用 `octos.turn.interrupt`；由宿主处理单 turn 约束与 context。
- 仅当本机宿主已配置 kernel / AI provider / 登录与授权时才会成功；未配置时显示真实错误。
- 本包的实际验证状态见项目 README。`manifest.json` 的 `integrity.bundle_blake3` 必须由官方工具生成；
  修改任何包内文件后都需重新打包和审阅，不能手填校验值。
