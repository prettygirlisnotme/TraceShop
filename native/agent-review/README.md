# TraceShop · Agent 审阅

Rinx 本地导入包。用户把网页中的候选证据交给宿主 octos 审阅，取得可复制的候选选择 JSON，再回网页明确采纳。

## 使用

1. 网页研究商品，点击“复制给 Agent 审阅”。
2. 在 Rinx 导入本包，粘贴资料，点击“发起审阅”。
3. 在“建议 JSON”框全选复制，回网页粘贴并点击“采纳建议，生成待确认提案”。
4. 网页校验来源提案、版本、候选、有效期、报价和硬约束。校验通过只生成新提案，仍需用户确认。
5. 报价或提案变化时，旧建议不可采纳；重新研究并取得新的审阅资料。

返回结构：

    {"schema_version":1,"proposal_id":"来源提案编号","revision":1,"merchant_version":1,"selected_item_id":"候选编号","reason":"选择理由"}

理由属于模型建议；商品事实和操作资格由网页后端核对。无可选项、错误格式或过时建议均不能创建草稿。可以直接在网页选择候选，不依赖模型。

## 运行边界

- 仅申请 octos.session.open、octos.turn.start、octos.turn.interrupt，未增加网络、聊天、存储或购买能力。
- 网页与原生包之间由用户复制粘贴，没有自动桥接；原生 Agent 不会批准、下单或发消息。
- 使用 Rinx 自己的本地 Agent peer，宿主须先配置 kernel 和模型提供方；这不是已验证的 OctoSense 注入系统 Agent，也不是 App Hub 签名发布。
- 模型失败时显示真实宿主错误，不用替身回复。
- 包版本 0.3.0；修改后必须由官方工具重新生成 integrity.bundle_blake3，再导入和审阅。实际运行证据见主 README。
