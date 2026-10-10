# 运行范围与证据

2026-10-10。所有运行与素材编码在学校集群CPU作业内完成；本预览不包含密钥、私有签名材料、完整会话日志或模型权重。

## 真实 Agent 办理（已有运行196923）

未修改官方 OctoSense Linux 0.1.0-rc.1 Debian 包，源码933abbcf2737e652acd9cae2a4c9ffc16bfdaec6。包SHA256 fe23928f7c082f9105e7ab8e777d1df6290789834ab812bdef536a2a192806dc。私有测试目录安装，经真实商店 Get/Install/Open，未更改全局信任。

CN MiniMax-M3 对“办公用无线鼠标，安静”、预算30、硬词wireless自主调用 status.read → catalog.research → proposal.create → draft.save → draft.read。人工只批准宿主权限和保存，没有人工研究、选候选或建提案。6次模型请求、5个工具调用，8个草稿字段与提案一致。批准前没有草稿，批准后才写入。

选中item4 VicTsing Wireless Mouse，12.99 USD，预算余量17.01。静音依据为 description 的Quiet原文和features的Silent click；item1/item2为not_documented，不据此声称它们不支持静音。

## 仍有的限制

- 宿主60秒回调超时；历史同步取回文字与真实final逐字相同，随后明确结束。历史文字不是宿主终态证明。
- 首次工具授权后立即重试的问题未定位；观察到延后重试成功不能算根因修复。
- 真实final误称“其余两条候选价低”：item1为11.99、item2为14.99、选中商品12.99。原文在摘要完整保留。
- 当前价格措辞与draft.read字段指引是运行后的修改，未重新调用模型验证。
- 声明6个工具，本序列实际调用5个；proposal.read未单独调用。未证明所有UI、其他软偏好、手机或全部Agent路径。
- 只是规则型合成目录，不是Project A模型检索实测或真实购买。

## 源码对应

真实模型运行：main.splash ed412c2c06f743454cef036e1422f6cccefe63162c2542866243338dab547c5a；
AGENT.md b6f28f0313914bd868eac1470b6bc7cee37f58a08da9c8bfa6b2d7b8460d597e。

当前文字修正版：main.splash 539bdc0586f7ffb487fd6df52914377dcfd423e8b4cc8f9fef320ae9e2c32105；
AGENT.md 40d292cfcf15afa0a84cfe807e24ba093924e1a91c96b17595fd56b005db8c39。
两者工具定义均为 c51e4df96eef9f719b874a49fc330ea63cfb282eba3dc76bce4e07728f0174f3。
元数据与截图可能在打包时更新，最终摘要以检查及发布回执为准。

## 当前源码的人工UI录像（196958）

官方RC1私有Store安装，CPU作业196958完成0:0。当前main539bdc05/tools c51e4df9/AGENT40d292cf完成界面流程，16个记录项均true（含总通过项与未发送Agent请求项）。三个候选中item4具有静音原始字段证据，item1/item2未证实；保存草稿并独立读回；模拟报价上涨15%后拒绝旧提案，已有草稿未被覆盖。

282帧连续采集，首末帧跨度98.6386秒；采集开始到结束98.9144秒。编码专用CPU作业196987完成0:0，用实际帧间时长生成VFR H.264，文件时长98.96秒、1400×900、963423字节；无剪切、无音轨，不新增模型调用。[录像](../evidence/native-ui-196958.mp4) · [摘要](../evidence/native-ui-196958.json)。

官方hub stamp/check --allow-unsigned对最终listing、元数据与4张截图通过。保留两项警告：尚无publisher签名，draft.save每次等待宿主批准。开发检查不生成GitHub证明、封存包、Release或App Hub准入。

采集作业中缓存的精简编码器缺少PNG解码能力，原始native-showcase-result.json保留video=null；编码结果另记encoding-repair.json，不改旧结果冒充当时已完成。采集前196950只因录制器滚动跳过按钮失败，未写草稿；改录制器后196958通过，业务源码未改。它只证明人工UI流程；价格文字修改尚无新的模型验证。
