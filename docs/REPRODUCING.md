# 运行与复现

应用入口 bundle/，需要支持 script-tools-v1 与 app_tools.dispatch@1 的宿主。已测宿主为未修改的官方Linux RC1 Debian包；应用不附带Rust/native代码，也不要求训练模型。

按[官方App Flow](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/README.zh-CN.md)和[PUBLISHING指南](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/PUBLISHING.zh-CN.md)准备工具，检查源码bundle，再使用兼容宿主。未配置模型时仍可使用人工研究、选择、确认、读回。不能把旧card-host里缺失octos服务的结果当成真实Agent办理。

开发包中的integrity摘要需要在最终文件确定后由官方hub stamp更新。当前开发 bundle 的 main.splash 为 e344068d5b8f885dadada682c9be69965a212fe3c30ffe6b1560ddf6a2c88467（紧凑原生界面，只改UI声明），tools.json 与 AGENT.md 及业务核心未变；最终manifest.integrity已由官方stamp更新，当前bundle的文件SHA见[检查摘要](../evidence/bundle-check-compact.json)。发布走官方GitHub证明工作流，不在应用内放模型密钥或生产签名密钥。正式封存包与回执从Releases获取，以成功工作流产物为准。

真实模型需在宿主侧配置模型提供方；应用Agent必须支持工具调用。先用合成需求与小预算跑一个用例，留意宿主授权与保存确认；详情见[实测范围](VALIDATION.md)。当前已知宿主回调超时不能通过伪造成功或跳过确认规避。

现有运行是LinuxCPU软件渲染，不代表Android、Windows或macOS已验证。
