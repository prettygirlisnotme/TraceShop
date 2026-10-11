# RC5 首次使用引导 198377

2026-10-11。原始小型结果从集群回传；COMPLETED 0:0、CPU4、12GiB、0 GPU、1:05。一条首次使用流程通过 22 项相关断言，零模型请求、无 fixture、无录像。与 0.5.1 基线的人工 UI / 真实 Agent 证据分开。

`onboarding-ui-result.json` 只走未运行 Agent 的入口分支（`fill_quote_tradeoff` 非活跃分支）：点击新按钮前后无草稿、无候选、无提案、无自动 Agent；预算 20 时 M170 $14.99 满足预算与 wireless，静音缺快照证据；M240 $22.99 超旧预算 $2.99，只作只读替代；用户明确改预算到 23 后 M240 变为可选，确认按钮首屏可见但未点击保存。**`agent_task_active` 守卫实现已审阅，未在本作业动态驱动。**

同 main 的首次作业 **198373**（45 秒）在目录/输入检查已通过后，被检查脚本仍匹配旧提示文案而 FAILED；其失败结果与源码保留在根项目 `native/traceshop-onboarding/check/run-198373/`，不因本次通过而回填为成功。删除该文案断言后 198377 通过，应用 `main.splash` 字节未变（`7e0c08e1…`）。

`sacct.txt` 同时列出 198373 FAILED 与 198377 COMPLETED。

## 脱敏与限制

- 未修改官方 Linux RC5（`appimage-metadata.txt`：`unmodified_official=true`），通过私有测试目录真实 Store Get/Install/Open。**私有 Linux 测试副本的 manifest/listing 含有测试发布者/签名/平台改动，不声称原始未签名整包已获官方准入。**
- `source-at-run/` 为作业运行时源码：`bundle/` 三文件（`main.splash` 摘要 `7e0c08e1…`）与 `check/` 四个检查脚本。`run.sbatch` 与 `appimage-metadata.txt` 内保留集群绝对路径，无密钥、无 relay、无大日志、无 PNG。
- `unsigned-check.txt` 仅代表旧 CLI `655114c4`（契约 1.8.0）结构检查；不代表新 Hub `38635915`（1.12）工具链、发布 CI 或 GitHub attestation 验证。`checker-source.txt` 仅为检查器来源说明。
- 本作业是 0.5.1 基线（main `18647a97…`）之外的**新 main**（`7e0c08e1…`），只有这一条 UI 流程证据，**不能继承** 198242 人工 UI 或 198316 真实 M3 的结论；`catalog.select` / `proposal.read`、保存与拒绝路径均未在本 main 动态覆盖。
- 完整运行目录、首屏诊断图与大日志保留在集群，不回传本仓库。

本候选随后把manifest.version改为0.5.2并更新listing说明；本目录旧CLI日志不覆盖这次元数据更新，最终十文件尚未运行官方发布检查。198377实际运行位置为集群项目的 `native/traceshop-onboarding`，不是新建的release/0.5.2目录。
