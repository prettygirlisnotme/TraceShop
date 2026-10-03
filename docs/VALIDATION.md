# 验证范围 · 2026-10-03

独立脚本应用 `traceshop.shopping 0.4.0` 在官方 `card-host` / Linux 中完成真实原生操作。CPU 作业 182121 退出 0；源码和宿主运行时未通过替身服务改变行为。

## 已观察到

- 无效预算和无结果显示原因，未生成采购草稿。
- 办公预设检索到 VicTsing 静音鼠标等候选，展示实际演示目录事实。
- 选择候选仅生成待确认提案。
- 点击审阅得到真实 `no service answers "octos" on this device`；当时没有草稿。
- 模拟报价上涨后旧提案被拒绝；重新研究与确认后保存 $14.94 USD 草稿。
- 写入后从文件独立读回，关键字段一致；重启后恢复同一草稿。
- 原生脚本运行记录没有应用错误行；官方 `hub check --allow-unsigned` 输出 PASSED。

数据与操作摘要见 [native-workflow.json](../evidence/native-workflow.json)。

## 固定官方源码

| 组件 | commit |
| --- | --- |
| App Design Flow | `0e59346e810ed694702b1df48f4283dc8104358c` |
| App Hub | `2bcb8985bc1d2c8856f2a61e65baa7ed443ae817` |
| makepad | `c155f61d0e1600d2ec474209374444a38a09a470` |
| octoscript | `5991dfae9344589e732b2605b530f788e8bbcd11` |
| octoscript-makepad | `2cc5ef37d7d6a3d2992673389ce74488f7bb2d87` |

## 范围与局限

182121 验证人工闭环、宿主服务缺失与重启恢复，本身没有调用模型。其后 182276 在同一份已提交 bundle 上补充真实模型建议采纳，范围如下；手机与其他操作系统仍未验证。

视频来自该作业连续捕获的真实原生窗口帧，素材作业 182141 使用已有浏览器编码器输出；以 4fps 编码，播放速度与现场操作时间不同。

发布者、支持入口和隐私说明定稿后，仅因 listing 变化执行必要包检查：CPU 作业 **182240 COMPLETED 0:0**，hub stamp/check、tools/octo check 和 hub scan 均退出 0。占位已清除，只剩首次未签名警告。源码与上述原生流程/录屏一致，没有重复业务或调用模型。最终摘要见 [native-gate.json](../evidence/native-gate.json)，作者答复见 [APP_HUB_REVIEW.md](APP_HUB_REVIEW.md)。

包检查通过不代表 App Hub 人工审核通过或比赛受理。

## 真实 Agent 流程（提交后补充）

CPU 作业 **182276 COMPLETED 0:0**：固定且未修改的 Rinx `5a9e2af2433a04129f2ad0c11acafb187c66f649`，二进制 SHA `60431b16b8e67f2167eae951bec306ca0a554f02264c798e3cf1ef78ec29a720`，实际 packaged octos 与 CN MiniMax-M3。五项 bundle 文件 SHA 和最终 BLAKE3 与 v0.4.0 提交一致；新应用自己产生资料，没有 Web 导出或复制粘贴。

实际观察：assistant OFF 时显示宿主真实错误；启用本设备助手后，真实请求返回非空 JSON，选中 item_id 4，并依据 Silent click、2.4GHz 无线和 $12.99 / $30 预算说明理由。采纳后生成 v2 待确认提案，确认前没有采购草稿；明确确认后写入并独立读回一致。

[实际结果](../evidence/native-agent-workflow.json) · [真实回复截图](../evidence/native-agent-review.png) · [采纳状态](../evidence/native-agent-adoption.png) · [保存读回](../evidence/native-agent-draft.png)。这些是独立真实原生截图，不把它们冒充成已有购物视频中的镜头。

首次 182258 因审阅控件位于裁剪范围外，未正确触发或观察服务；修正驱动的滚动后 182276 成功，应用源码与固定宿主未修改。该次失败不能作为模型失败证据。

这是 standalone Rinx 自己的本地 Agent peer，未验证 OctoSense Shell 注入的 System Agent。只有一个合成目录用例，不代表推荐准确率或总体效果。
