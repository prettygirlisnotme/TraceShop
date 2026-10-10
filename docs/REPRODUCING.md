# 运行与复现

应用入口 `bundle/`，需要支持 `script-tools-v1` 与 `app_tools.dispatch@1` 的宿主。已测宿主为未修改的官方 Linux RC1 包；应用不附带 Rust/native 代码，也不要求训练模型。

按[官方 App Flow](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/README.zh-CN.md)和[PUBLISHING 指南](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/PUBLISHING.zh-CN.md)准备工具，检查源码 bundle，再使用兼容宿主。未配置模型时仍可使用人工研究、选择、确认、读回。不能把旧 card-host 里缺失 octos 服务的结果当成真实 Agent 办理。

当前开发 bundle 源码为 main.splash `4c3a5daa`、AGENT.md `dd5f1e9e`、tools.json `c51e4df9`（六工具未变），与运行 197305 所用源码一致。修改文件后需重新进行官方 `stamp/check`：本次最终开发包已通过官方197371检查（unsigned），[10文件摘要](../evidence/bundle-check-replan.json)与本地包一致，不继承旧b3结论。发布走官方 GitHub 证明工作流，不在应用内放模型密钥或生产签名密钥；正式封存包与回执从 Releases 获取，以成功工作流产物为准。

真实模型需在宿主侧配置模型提供方；应用 Agent 必须支持工具调用。先用合成需求与小预算跑一个用例，留意宿主授权与保存确认。运行 197305 复现的是“报价变化后旧确认被拒绝 → 用户交给 Agent 重办 → 新研究 → 宿主 Approve once → 保存 → 独立读回”的流程；详情见[实测范围](VALIDATION.md)。当前已知宿主回调超时不能通过伪造成功或跳过确认规避。

现有运行是离线 CPU 软件渲染，不代表 Android、Windows 或 macOS 已验证。
