# RC5 办理记录与完整回复 198504

2026-10-11。原始小型结果从集群回传；`accounting.txt` 为 COMPLETED 0:0、CPU4、12GiB、0 GPU、4:56，官方未修改 Linux RC5（`appimage-metadata.txt`：`unmodified_official=true`）真实 Store 安装。本作业用**固定 loopback 协议输入、零真实模型**（`activity-result.json`：`real_model=false`、`fixture=true`、`model_requests=0`、`video_recorded=false`），验证界面把**实际应用工具返回**记入“办理记录”，并与“完整回复”原文分开、可切换。

## 实际范围

`activity-result.json` 为 25 项 UI 断言 + `fixture-checks.json` 12 项协议断言，全部 `true`、`errors=[]`、`passed=true`：

- 页面为“办理记录 · 完整回复”两个切换区，各 360px（`bundle/main.splash` `switch_reply_view`、`activity_records_section`/`activity_reply_section`），默认打开“办理记录”，切换按钮在内容之前。
- `first_reply_visible_without_scroll=true`、`second_reply_visible_without_scroll=true`：完成主 main `17bb585a…` 后，两条回复均**无需滚动**即完整可见（此前 198494 的 raw reply 空值因屏幕外 widget 不在 snap 中，真实滚动后 106/57 字符逐字一致，是取景问题而非内容丢失）。
- 逐字一致：`first_reply_is_exact_fixture_text=true`、`second_reply_is_exact_fixture_text=true`、`first_reveal`/`second_reveal` 的 `text_before==text_after`，原文不改写。
- 五个**实际 tool return** 逐条记为记录（`records_after_task`）：`status` 读取、`proposal.read` **无提案真实失败**（记录明确写“未确认成功”）、`research` 返回 1 候选、`proposal.create` 生成待确认提案 `p-1791723264-1`、`proposal.read` 读到待确认提案。`records_no_draft_save=true`、`no_draft_written=true`。
- `manual_research_not_recorded=true`：本次手动研究**不**计入记录；实现仅包装应用工具完成回调。
- `refresh_preserves_records_and_reply=true`：刷新保持记录与回复。
- `new_task_clears_records=true`、`second_task_no_tools_recorded=true`：新任务先清空办理记录。
- 记录**先原样 `app_tools.complete` 再记录结果**，最多保留最近 12 条（`activity_record_limit=12`）、仅内存（`activity_records`）；不是宿主认证、不是模型推理、不是完整审计，也不作为批准或任务终态凭据。

## 与 198494 的关系

布局修正前作业 **198494**（main `05764fd4…`）（官方未修改 Linux RC5、CPU4/12GiB/0GPU/3:19，固定 loopback 协议零真实模型，23 UI + 12 协议通过）先证实两次 raw reply 空值因屏幕外 widget 不在 snap，真实滚动后 106/57 字符逐字一致。随后 main 改为 `17bb585a6dc6abce1f10f02181ab06e1544414c622de457f12e0741a63668170`（记录/原文切换、各 360px、默认记录），198504 在该 main 上通过 25 UI + 12 协议。

## 脱敏与限制

- `source-at-run/` 为作业运行时源码：`activity_ui.py`（UI 驱动与断言）、`activity_fixture.py`（固定协议流量）、`run.sbatch`、`expected-sha256.json`；`activity-replies.jsonl` 为原始控制回执（click_xy/resume），`fixture.jsonl` 含固定协议输入与实际工具返回，均无密钥、无模型权重。`candidate-sha.txt` 记录运行时应用 `main.splash`/`tools.json` 摘要，与 `source-at-run/expected-sha256.json` 一致。
- 本作业是**固定协议流量**，不是 LLM 自主证据（7 次固定协议请求、`NO REAL MODEL`）；不证明模型在真实任务中的行为。
- **未动态驱动**的分支：保存/读回摘要记录、超过 12 条的淘汰、进程重启后清空（记录本身仅内存）。`synthetic_demo` 已中文翻译；本次未调用目录切换工具。
- 安装副本 manifest 版本仍为 **0.5.2 + 私有测试 publisher/签名**（`unsigned-check.txt` 打印 0.5.2、`signing-scope.txt`：`approved_test_only=true`、3 枚已批准测试密钥、未改全局信任）；`unsigned-check.txt` 仅旧 CLI `655114c4`（契约 1.8.0）结构检查，**不是**新 Hub `38635915`（1.12）工具链、发布 CI 或 GitHub attestation 验证。**新 0.5.3 十文件整包尚未运行官方发布检查。**
- **无真实 M3 对新 main**：真实模型闭环 **198316** 仍对应 0.5.1 基线（main `18647a97…`）；0.5.3 新 main 只有本作业的零模型 UI/协议证据。
- 完整运行目录与大日志保留在集群，不回传本仓库。

本候选把 manifest/listing 元数据更新为 0.5.3；本目录旧 CLI 日志不覆盖这次元数据更新，最终十文件仍须运行官方发布检查。证据已复制本目录，可读核对，**不据间接信息编造结果**。
