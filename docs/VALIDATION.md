# 运行范围与证据

更新：2026-10-11。本页区分**多个精确版本**、**CPU 执行位置**，以及证据属于**人工 UI**、**真实 Agent** 还是**外部效果**。应用与检查均在集群 Slurm CPU 作业内执行；真实模型作业会访问 MiniMax API，界面在私有 Xvfb 中软件渲染；本预览不含密钥、私有签名材料、完整会话日志或模型权重。

## 精确版本（分开看，不要混用）

| 版本 | main.splash | tools.json | AGENT.md | manifest.json | listing.json | 用途 |
| --- | --- | --- | --- | --- | --- | --- |
| **当前候选 0.5.3**（本仓库 `bundle/`） | `17bb585a…` | `e3f0e0f5…` | `f02c135f…` | `7d690683…` | `2861915c…` | 待发布；十文件摘要见 [`../package-inputs.json`](../package-inputs.json) |
| **198504 私有测试副本** | `17bb585a…` | `e3f0e0f5…` | `f02c135f…` | 0.5.2 + Linux/测试 publisher/签名 | 私有测试说明 | **0.5.3 当前 main** 的 RC5 办理记录/完整回复切换（25 UI + 12 协议断言、固定协议零真实模型、4:56、无保存）；布局调整前 **198494**（main `05764fd4…`）（23 UI + 12 协议、3:19）证实 raw reply 空值因屏幕外 widget 不在 snap、真实滚动后 106/57 字符逐字一致 |
| **198377 私有测试副本（0.5.2 基线）** | `7e0c08e1…` | `e3f0e0f5…` | `f02c135f…` | Linux/测试 publisher/签名 | 私有测试说明 | **0.5.2 基线**的 RC5 首次使用流程（22 断言、零模型、1:05、未跑 Agent 分支）；**不继承 0.5.1 基线模型结论** |
| **198242 私有测试副本（0.5.1 基线）** | `18647a97…` | `e3f0e0f5…` | `f02c135f…` | Linux/测试 publisher/签名 | 私有测试说明 | 0.5.1 基线的 RC5 人工 UI 运行；**不继承原候选字节全通过，不适用于 0.5.3 main** |
| **198316 私有测试副本（0.5.1 基线）** | `18647a97…` | `e3f0e0f5…` | `f02c135f…` | 私有测试签名范围 | 私有测试说明 | 0.5.1 基线的 RC5 真实模型运行（`passed=true`）；`source-at-run` 业务文件与该基线一致，安装经私有测试签名范围（`approved_test_only`）；**不继承原 unsigned 候选全字节准入，不适用于 0.5.3 main** |
| **198215 实测包** | `18647a97…` | `e3f0e0f5…` | `f02c135f…` | `af045121…` | `9944a0d7…` | 历史旧包；manifest/listing 与当前候选不同 |
| **197799 实测包** | `fc005b81…` | `e3f0e0f5…` | `06a058…` | `af045121…` | `9944a0d7…` | 历史旧包；真实模型闭环，较早业务 |
| **197305 历史包** | `4c3a5daa…`（base `b3ac9f79…`） | `c51e4df9…` | `dd5f1e9e…` | 旧 | 旧 | 历史素材来源，不对应当前包 |

- 简写为完整 SHA256 前缀；完整值以 [`../package-inputs.json`](../package-inputs.json) 与各自运行目录内的 `expected-sha256.json` 为准。198215 与 197799 的 `main.splash` 不同（`18647a97` vs `fc005b81`），必须分开引用，两者都属历史旧包。
- 当前候选 0.5.3 相对 0.5.2 基线只改 `bundle/main.splash`（原“完整回复”页扩为“办理记录 / 完整回复”切换区）与 manifest/listing 文档字段，所以 **198377 的包字节或 UI 验证不继承到 0.5.3 main**（其 main 为 0.5.2 基线 `7e0c08e1`）。198504 用的是**私有测试副本**，其 manifest/listing 含测试 publisher/签名改动（结构检查打印 0.5.2）、listing 配私有测试说明，**不是原 unsigned 包全字节准入**。198215/198242/198316 都用 0.5.1 基线的 `main.splash 18647a97` 或更早业务，同样不适用于 0.5.3 main。

## CPU 位置与执行边界

- 控制位置（编辑、调度、查看）：`/home/a/myprojects/workspaces/03_competitions/active/gosim-agentic-app-2026`（WSL 只编辑、控制与查看）。
- 存放位置：集群 `/projects/user007ssd/projects/gosim-agentic-app-2026/native/traceshop-activity/bundle`（0.5.3 当前 main）；198377实际在 `/projects/user007ssd/projects/gosim-agentic-app-2026/native/traceshop-onboarding` 的Slurm CPU作业内运行。0.5.1/0.5.2基线证据仍见对应release与reports目录。
- 界面均为 CPU 软件渲染；真实模型调用需外网；**不代表 Android、Windows 或 macOS 已验证**。相关作业号：197754（CPU4，1:46）、197860（CPU4，1:38）、197799（CPU4，4:44）、198215（CPU4，2:05）、198242（CPU4，2:51）、198316（CPU4，7:43，真实 M3）、198377（CPU4、12GiB、0 GPU、1:05，零模型首次使用流程）、198494（CPU4、12GiB、0 GPU、3:19，固定协议零模型）、198504（CPU4、12GiB、0 GPU、4:56，固定协议零模型办理记录）；198273 为真实 M3 历史失败（首次授权未批准、无 live-result）；历史 197305 为 CPU8、6:48。
- 办理记录/完整回复证据在集群 `/projects/user007ssd/projects/gosim-agentic-app-2026/native/traceshop-activity/check/run-198504/`，小型副本在候选 `evidence/rc5-activity-198504/`（含 `source-at-run/` 脚本与 `expected-sha256.json`）；首次使用流程证据在集群 `/projects/user007ssd/projects/gosim-agentic-app-2026/native/traceshop-onboarding/check/run-198377/`（含 `onboarding-first-screen.png`），小型副本在候选 `evidence/rc5-onboarding-198377/`；0.5.1 基线人工 UI 证据 `reports/20261011-upstream-alignment/run-198242/`，小型副本在候选 `evidence/rc5-ui-198242/`；真实 M3 证据 `reports/20261011-upstream-alignment/live/run-198316/`，小型副本见候选 `evidence/rc5-agent-198316/`；失败材料保留在 `live/run-198273/`。本仓库不含完整集群运行目录，**不虚构对应文件**。

## 人工 UI vs 真实 Agent vs 外部效果

- **办理记录 / 完整回复（RC5，198504，0.5.3 当前 main）**：官方未修改 Linux RC5（`unmodified_official=true`）真实 Store 安装，**固定 loopback 协议输入、零真实模型**（`real_model=false`、`fixture=true`、`model_requests=0`）。25 项 UI 断言 + 12 项协议断言全通过、`errors=[]`、`passed=true`；页面为“办理记录/完整回复”两个切换区（各 360px、默认记录、按钮在内容前）。`first/second_reply_visible_without_scroll` 与逐字一致均为 true；五个实际 tool return 逐条记录（`status`、`proposal.read` **无提案真实失败**、`research` 1 候选、`proposal.create p-1791723264-1`、`proposal.read` 待确认）；`refresh_preserves_records_and_reply`、`new_task_clears_records`、`manual_research_not_recorded` 均 true；`records_no_draft_save`、`no_draft_written` true。记录先原样 `app_tools.complete` 再记录结果，最多最近 12 条、仅内存；**不是 LLM 自主证据**（7 次固定协议请求）。保存/读回摘要分支、>12 条淘汰与重启清空**未动态驱动**。安装副本 manifest 版本为 0.5.2 + 测试 publisher/签名，**不继承原 unsigned 包字节准入**。
- **布局修正前诊断（RC5，198494，main `05764fd4…`）**：官方未修改 Linux RC5、CPU4/12GiB/0GPU/3:19、固定协议零真实模型，23 UI + 12 协议断言通过；证实两次 raw reply 空值因屏幕外 widget 不在 snap，真实滚动后 106/57 字符逐字一致，**非内容丢失**。
- **首次使用流程（RC5，198377，0.5.2 基线 main）**：官方未修改 Linux RC5 真实 Store Get/Install/Open，控制器点击一条首次使用流程。首页新“预算取舍 $20”按钮只把需求/预算/硬关键词填好并切到官网快照，**不自动研究、不启动 Agent、不生成提案、不保存**；点击前后无草稿、无候选、无提案。预算 20 时 M170 $14.99 满足预算与 wireless、静音缺快照证据；M240 $22.99 超原预算 $2.99，只作只读替代；用户明确改预算到 23 后 M240 变为可选（预算余 $0.01），确认按钮首屏可见但未点击保存。22 项相关断言通过、`errors=[]`、`passed=true`。**零模型、无 fixture、无录像；仅走未运行 Agent 的入口分支，`agent_task_active` 守卫未动态驱动；不继承 198242/198316 的 0.5.1 基线结论。** 同 main 的 198373 因检查脚本仍匹配旧提示文案 FAILED（目录/输入检查已通过），失败与源码保留在根项目，不回填为成功。
- **人工 UI（RC5，198242，0.5.1 基线）**：官方未修改 Linux RC5、真实 Store Get/Install/Open，控制器点击一条人工 UI 流程，现有 13 项检查全部通过，零模型请求、无录像；COMPLETED 0:0、CPU4、2:51。私有测试副本 manifest 含 Linux/测试 publisher/签名改动，listing 含测试说明，**不继承原候选字节全通过**；旧 CLI `655114c4`（契约 1.8.0）`stamp/check --allow-unsigned` 仅结构检查，不是新 Hub `38635915`（1.12）工具链或 GitHub attestation 验证。**只适用于 0.5.1 基线。**此步**不驱动真实模型**。
- **人工 UI（198215，历史旧包）**：未修改官方 Linux RC1、真实 Store 安装，13 项相关检查通过，零模型请求、无录像；manifest/listing 其后已改，**不继承包字节验证**。覆盖：待确认提案、保存并独立读回一致、报价变化后旧确认被拒绝且旧 M240 草稿全字段不变、拒绝新提案不删除旧草稿；顶部独立说明 Agent 回合状态（不会把“草稿已核验”或历史文字回复当成宿主终态）。此步**不驱动真实模型**。
- **真实 Agent（197799，历史旧包）**：真实 CN MiniMax-M3，CPU4、4:44、6 次请求、5 个应用工具；未修改官方 RC1 真实 Store 安装。先以预算 20 研究、用户明确改 23，再启动绑定任务；模型选 M240 $22.99，静音字段有证据、预算余 0.01。`research`/`create`/`save` 全部携带同一原始 `task_id`；主控真实点击宿主 `Approve once`；`draft.read` 返回 `read_ok=true`、`matches_current_proposal=true`、`verification_scope=proposal_fields`；`quote` 与 `selection_record` 在落盘文件与工具结果中一致；973 字符最终回复经一次显式历史同步显示，主控显式结束。**该次 main 为 `fc005b81…`（较早业务），且之后又改了 AGENT 文字与 UI 摘要及状态、未重跑模型，仅作较早业务对照；0.5.1 基线的真实模型验收见 198316；0.5.3 新 main 没有真实模型证据，只有 198504 的固定协议零模型办理记录/完整回复（及布局调整前198494（main `05764fd4…`） 的滚动取景）。**
- **真实 Agent（198316，0.5.1 基线，已通过）**：0.5.1 基线源码（main `18647a97…`/tools `e3f0e0f5…`/AGENT `f02c135f…`，与 `source-at-run` 一致），官方未修改 Linux RC5（`octosense_0.1.0-rc.5_amd64.deb`，`unmodified_official=true`）真实 Store 安装，真实 CN MiniMax-M3，非流上游转标准 SSE 适配器不变，CPU4、7:43、6 次请求、5 个应用工具（`status`/`research`/`proposal.create`/`draft.save`/`draft.read`）。原生 Allow 与宿主 `Approve once` 均主控按本次实际画面点击；批准前草稿不存在，批准后保存 M240 $22.99（预算 23、`wireless` 硬命中、`quiet` 由 title+features 字段证据），`research`/`create`/`save` 携带同一原始 `task_id`；`draft.read` 返回 `read_ok=true`、`matches_current_proposal=true`、`verification_scope=proposal_fields`；693 字符真实 final 经一次显式历史同步显示，主控明确结束后状态已结束。`live-result passed=true`、10 项 observed 全 true。**未调用 `catalog.select`/`proposal.read`，不代表七工具或全平台全覆盖。**
- **真实 Agent（198273，历史失败，材料保留）**：0.5.1 基线上首次真实 M3 作业；首次授权待主控操作时 SSH 失联，**无 `live-result.json`、无 relay 请求日志、模型请求 0，未通过**；wrapper 超时被误映射为 Slurm exit0，已在 198316 修正。恢复 VPN 后只取回失败材料，不盲目重提。
- **零模型夹具 / 界面检查**：`197754`（13 项工具断言 + 6 项控制/UI 检查）与 `197860`（选择摘要前置 7 项检查，main `ca293739…`）提供支持性局部证据；`197786` 真实 M3（7 请求）曾暴露读回 `parse_failed` 与研究结果被宿主按 4 KB 截断，失败原样保留，不将后续修复回填成 197786 成功。
- **外部效果**：本应用**没有**任何真实外部效果。目录为 14 条合成 + 3 条官网快照（整理摘要、非实时、仅商品价），**没有真实下单、支付、物流**，也未接入实时商品目录或在线检索服务；检索/推荐质量未做独立评估。

## 当前候选的证据边界

- 十文件本地摘要与当前 `bundle/` 一致（[`../package-inputs.json`](../package-inputs.json)）；本地摘要**不是**官方签名。
- 官方 `stamp/check` 作业 **197371** 的十文件（main `4c3a5daa…`、listing `f4059e51…` 等）属于**旧包**，**不适用于当前候选**。198504 私有测试副本（manifest仍为0.5.2）经旧 CLI `655114c4`（契约 1.8.0）`stamp/check --allow-unsigned` 结构检查（在私有测试副本上执行，输出仍打印 0.5.2），**不是**新 Hub `38635915`（1.12）工具链或 GitHub attestation 验证；0.5.3 新 main 的 RC5 办理记录/完整回复由 **198504** 覆盖（25 UI + 12 协议、固定协议零模型），布局调整前 **198494**（main `05764fd4…`） 覆盖滚动取景与逐字一致。0.5.2 基线的 RC5 首次使用流程由 **198377** 覆盖（22 断言、零模型、未跑 Agent 分支）；0.5.1 基线的 RC5 人工 UI 由 198242 覆盖，真实模型闭环由 **198316** 覆盖（`passed=true`），**均不适用于 0.5.3 main**。
- 四张 `bundle/screenshots/01–04` 与 94 秒节选（`../evidence/native-agent-excerpt-197305.mp4`）全部来自 **197305 旧合成目录**流程，**仅历史、本版未更新**，不得当作当前包实拍。

## RC5 兼容验证：0.5.3 办理记录 / 完整回复，与 0.5.2 / 0.5.1 基线

官方 OctoSense 桌面 **RC5** 已于 2026-10-11 发布：

- 源码 `83d356c261f755fe4bb446e331c1508a78ee29f2`，release `desktop-v0.1.0-rc.5`；App Flow 更名为 **OctoSense-App-Flow**（旧名重定向）。
- 将能力/network 声明改为**用途披露**由 **RC4 引入、RC5 延续**；设备同意、账户 scope、人工写批准与存储隔离**仍保留**。RC5 新增 charts/Wasm 与 HTTPS 修复——**本应用不使用这些新能力**。
- 宿主 60 秒服务超时仍为默认值；本应用**不宣称 60 秒问题已修复**，最终回复仍靠显式历史同步取回。
- **198504**（COMPLETED 0:0、CPU4、12GiB、0 GPU、4:56，**0.5.3 新 main**）：官方未修改 Linux RC5（`unmodified_official=true`）真实 Store 安装，**固定 loopback 协议、零真实模型**（7 次固定协议请求、无 fixture 录像）；办理记录/完整回复两个 360px 切换区（默认记录、按钮在内容前），25 UI + 12 协议断言全过、`errors=[]`、`passed=true`；`first/second_reply_visible_without_scroll`、逐字一致、五个实际 tool return 逐条、`refresh_preserves_records_and_reply`、`new_task_clears_records`、`manual_research_not_recorded`、`records_no_draft_save`/`no_draft_written` 均 true。安装副本 manifest 为 0.5.2 + 测试 publisher/签名，**不继承原 unsigned 包准入**；保存/读回摘要、>12 条淘汰与重启清空未动态驱动。
- **198494**（COMPLETED 0:0、CPU4、12GiB、0 GPU、3:19，**0.5.3 当前 main 前序**）：官方未修改 Linux RC5、固定协议零真实模型，23 UI + 12 协议断言通过；证实 raw reply 空值因屏幕外 widget 不在 snap、真实滚动后 106/57 字符逐字一致。
- **198377**（COMPLETED 0:0、CPU4、12GiB、0 GPU、1:05，**0.5.2 基线 main**）：官方未修改 Linux RC5 真实 Store Get/Install/Open，一条首次使用流程通过 22 项断言、`errors=[]`、`passed=true`，零模型、无 fixture、无录像、未保存；只走未跑 Agent 的入口分支，`agent_task_active` 守卫未动态驱动，**不继承 0.5.1 基线结论**；同 main 的 198373 因旧提示文案断言 FAILED，失败与源码保留在根项目。
- **198242**（COMPLETED 0:0、CPU4、2:51，**0.5.1 基线**）：官方未修改 Linux RC5 真实 Store Get/Install/Open，现有 13 项人工 UI 检查全通过，零模型请求、无录像；私有测试副本 manifest 含测试 publisher/签名改动，listing 含测试说明，**不继承原候选字节全通过**。
- **198316**（COMPLETED 0:0、CPU4、7:43，**0.5.1 基线**）：官方未修改 Linux RC5（`unmodified_official=true`）真实 Store 安装，真实 CN MiniMax-M3，6 请求 5 工具；原生 Allow 与宿主 Approve once 均主控按实际画面点击，批准前草稿不存在、批准后保存 M240 $22.99 并独立读回；`passed=true`、10 项 observed 全 true。**未调用 `catalog.select`/`proposal.read`。**
- **198273**（历史失败，材料保留，0.5.1 基线）：首次授权待主控操作时 SSH 失联，**无 live-result、无 relay 请求、模型请求 0，未通过**；wrapper 超时误映射为 exit0，已在 198316 修正。
- 兼容性是**源码/文档级判断**（`script-tools-v1` / `app_tools.dispatch@1` / `confirm=host` 路径），与上述运行证据分开。发布工作流已由主控更新为官方 App Flow `45174df…` 模板、Hub pin `38635915…`；**未跑 CI、未发布**。

## 仍有的限制

- 宿主 **60 秒回调超时**仍存在；历史不提供 turn 终态，**仍需用户明确结束**。
- 首次工具授权后立即重试的时序根因**未定位**；观察到的延后成功不能算根因修复。
- 七工具未逐一实测：真实 M3 只覆盖 0.5.1 基线（198316 调用 5 个，未调用 `catalog.select` / `proposal.read`），197799 亦为较早业务 5 工具；**0.5.3 新 main 没有真实模型证据**（198504/198494 都是固定协议零模型）；办理记录的保存/读回摘要分支、>12 条淘汰与重启清空未动态驱动，预算冲突/无变化/进行中任务等路径未全覆盖，0.5.2 的 `agent_task_active` 守卫也未动态驱动。
- 研究输出已精简（`decision` 省略与候选重复的 `candidate_checks`，候选只保留 `features` 与命中字段证据、软偏好证据、完整 `quote` 与版本）；197799 该次紧凑 UTF8 重序列化 2920 字节，是本次具体输入的长度，**不保证**更长查询或三候选结果都低于宿主上限。
- 原生仍是规则 + 目录，未接入实时商品目录或在线检索服务（合成目录 + 3 条官网快照）或原生 Project A；无真实交易。
- 不把 Jev、生成式搜广推、AgenticOS、全双工写成本应用已实现能力。

## 历史证据（不作新版主证据）

- 人工 UI 录像 197066（78.24 秒，零模型）、早期模型运行 196923、以及 197305 合成目录“变价后重办”（94 秒节选 + 4 张截图）均为历史记录。
- 196923 的 final 曾出现一处价格比较错误；这些旧文字记录不可修改，仅作历史。


本轮0.5.3在 198504 实跑当前 main（固定协议零模型），并把已测 main 的 manifest/listing 元数据更新为 0.5.3，未新增真实模型调用、保存路径或官方整包检查。正式发布前仍需锁定工作流检查最终十文件；198504 旧 CLI 结构检查日志不替代这一步。
