# 运行与复现

应用唯一入口是 `bundle/`，需要支持 `script-tools-v1` 与 `app_tools.dispatch@1` 的宿主。历史真实模型闭环使用**未修改的官方 Linux RC1**；当前人工 UI 与真实模型使用**未修改的官方 Linux RC5**（均为真实 Store 安装）；应用不附带 Rust/native 代码，也不要求训练模型。RC5 人工 UI 由 **198242** 覆盖（官方未修改 Linux RC5 真实 Store Get/Install/Open，现有 13 项检查全通过，零模型、无录像）；当前候选的真实 M3 闭环由 **198316** 覆盖（官方未修改 Linux RC5 真实 Store 安装，6 请求 5 工具，宿主 `Allow` + `Approve once` 后保存 M240 $22.99 并独立读回，`passed=true`、10 项 observed 全 true）。**198273** 为历史失败（首次授权未批准、无 live-result、模型请求 0），材料保留、不重提。

按[官方 OctoSense-App-Flow](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/README.zh-CN.md)和 [PUBLISHING 指南](https://github.com/OctoSense-org/OctoSense-App-Flow/blob/main/docs/PUBLISHING.zh-CN.md)准备工具、检查源码 bundle，再使用兼容宿主。未配置模型时仍可使用人工研究、选择、确认、读回。不能把旧 card-host 里缺失 octos 服务的结果当成真实 Agent 办理。

## 精确源码（三版本分开）

- 当前候选 0.5.1：main.splash `18647a97…`、tools.json `e3f0e0f5…`（七工具）、AGENT.md `f02c135f…`、manifest.json `93096796…`、listing.json `21de8b0e…`；十文件摘要见 [`../package-inputs.json`](../package-inputs.json)。
- 真实模型闭环 197799 的业务源码：main.splash `fc005b81…`、AGENT.md `06a058…`（与本候选不同）。
- 历史 197305：main.splash `4c3a5daa…`（两个旧证据文件的来源）。

修改 bundle 文件后需对**最终**文件重新进行官方 `stamp/check`；当前候选只经旧 CLI `655114c4`（契约 1.8.0）`stamp/check --allow-unsigned` 结构检查，**不是**新 Hub `38635915`（1.12）工具链或 GitHub attestation 验证。此前 197371 检查对应旧包（main `4c3a5daa…`），**不适用当前候选**。Linux 运行使用**私有测试副本**：198242 的 manifest 含 Linux/测试 publisher/签名改动，198316 业务文件与当前候选一致但安装经私有测试签名范围（`approved_test_only`）；两者均**不是**原 unsigned 候选包的全字节准入，公开 GitHub 证明/attestation 流程**未验证**。发布工作流已由主控更新为官方 App Flow `45174df…` 模板、Hub pin `38635915…`，**未跑 CI、未发布**。发布走官方 GitHub 证明工作流；应用内不放模型密钥或生产签名密钥。正式封存包与回执从 Releases 获取，以成功工作流产物为准。

## 运行方式

真实模型需在宿主侧配置模型提供方；应用 Agent 必须支持工具调用。先用合成需求与小预算跑一个用例，留意宿主授权与保存确认。已记录的闭环是“预算 20 手动研究 → 用户明确改 23 → 首次委托获原生 Allow 后明确重试 → 启动条件绑定任务 → Agent 研究并选择 M240 $22.99（预算余 0.01、quiet）→ 宿主 `Approve once` → 保存 → 独立读回 → 显式同步回复并结束”；该闭环现由当前候选 **198316** 复现（真实 CN MiniMax-M3，6 请求 5 工具，`passed=true`），197799 为较早业务对照。详情与精确源码/限制见[实测范围](VALIDATION.md)。当前已知宿主 60 秒回调超时不能通过伪造成功或跳过确认规避。

执行位置为 NTU Slurm 内 CPU 作业（控制端只编辑/调度/查看）；本仓库不含这些运行目录，私有集群路径见 [VALIDATION](VALIDATION.md)。界面为私有 Xvfb 内的 CPU 软件渲染，真实模型调用会访问 MiniMax API，不代表 Android、Windows 或 macOS 已验证。
