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

本轮验证人工闭环、宿主服务缺失与重启恢复，没有调用模型。真实模型回复及建议采纳尚未在这版应用验证，也未验证手机或其他操作系统。

视频来自该作业连续捕获的真实原生窗口帧，素材作业 182141 使用已有浏览器编码器输出；以 4fps 编码，播放速度与现场操作时间不同。

包检查通过只代表基础预检通过。`tools/octo check` 另提示 `listing.json` 的发布者占位待替换；这不是 App Hub 人工审核通过或比赛受理。
