# RC5 真实 MiniMax-M3 198316

2026-10-11。sacct COMPLETED0:0、CPU4、7:43。原始 live-result.json 为 passed=true，10项observed全true；6次真实CN MiniMax-M3请求、5个应用工具。来源摘要匹配当前0.5.1候选的main/tools/AGENT；应用业务未改。

主控先根据本次实际画面点击Allow，重试应用启动；模型自主status→research→proposal.create→draft.save→draft.read→final。保存前没有草稿，主控核对原生参数后明确Approve once；M240$22.99、预算23、wireless、静音字段证据、选择记录与quote随草稿保存并独立读回匹配。研究/创建/保存同task_id且研究匹配原始UI条件。

宿主60秒回调仍超时；693字符最终回复经一次显式历史同步显示，再明确结束。ui-checkpoints.json是从完整原始控制回执选取的检查点，execution-summary.json是从原始wrapper选取的运行摘要；不是完整原始文件，也不掩盖超时。完整日志/驱动/原生诊断画面留在集群与项目私有报告。

仅Linux私有测试副本，复用三枚已批准测试签名密钥；本目录不含密钥。主控原生批准，不使用开发模式自动批准；没有模拟模型或答案回退。实际请求经过私有loopback适配器，将真实MiniMax非流式回复转换为宿主需要的标准SSE；不宣称厂商原生SSE问题已修复。

未调用catalog.select/proposal.read，不称7工具或全平台覆盖；没有真实购买、支付、物流或实时联网商品检索。旧CLI结构检查与新宿主实际安装分开，不代表最新发布CI/GitHub证明已验证。本轮无新正式录像和对外发布。
