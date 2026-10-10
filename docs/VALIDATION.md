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

当前源码（文字修正与紧凑界面）：main.splash e344068d5b8f885dadada682c9be69965a212fe3c30ffe6b1560ddf6a2c88467；
AGENT.md 40d292cfcf15afa0a84cfe807e24ba093924e1a91c96b17595fd56b005db8c39。
两者工具定义均为 c51e4df96eef9f719b874a49fc330ea63cfb282eba3dc76bce4e07728f0174f3。
元数据与截图可能在打包时更新，最终摘要以检查及发布回执为准。

## 当前源码的人工UI录像（197066 紧凑界面）

官方RC1私有Store安装，CPU作业197066为CPU8、1分47秒、COMPLETED 0:0。当前main e344068d/tools c51e4df9/AGENT 40d292cf完成界面流程，16个记录项（含总通过项与未发送Agent请求项）全部为true。三个候选中item4具有静音原始字段证据，item1/item2未证实；保存草稿并独立读回；模拟报价上涨15%后拒绝旧提案，已有草稿未被覆盖。全程零Agent请求、零外部模型调用。

217帧连续采集，首末帧跨度77.8363秒；按实际帧间时长编码为VFR H.264，MP4实际时长78.24秒、1400×900、556698字节；无剪切、无音轨，不新增模型调用。[录像](../evidence/native-ui-197066.mp4) · [中文字幕](../evidence/native-ui-197066.zh-CN.srt) · [当前候选截图](../evidence/native-candidates-197066.png) · [摘要](../evidence/native-ui-197066.json)。

只改从 `let ink = #x1c1c1e` 起的UI声明；此前67944字节与布局调整前的main.splash 539bdc05逐字节相同，工具、业务函数、确认、写入、独立读回与21个按钮处理器不变。同一990×613窗口内候选容器由原版257px增至实测445px（约增加73%），三张候选选择按钮无需滚动，完整提案与确认按钮同屏。

最终开发bundle由CPU作业197113在2秒内完成官方stamp/check --allow-unsigned，COMPLETED 0:0。[检查输出](../evidence/bundle-check-compact.txt)与[文件摘要](../evidence/bundle-check-compact.json)对应当前源码、listing和四张197066截图。保留两项警告：尚无publisher签名，draft.save每次等待宿主批准。开发检查不生成GitHub证明、封存包、Release或App Hub准入。

上一轮196958（main539bdc05）的人工UI录像、编码196987及其素材保留为历史证据。当前四张bundle截图均来自197066；03-readback截于保存核心已完成写入后核验的页面，录像随后还单独点击了读回按钮。读回通过只证明业务字段一致，不证明自然语言每句准确。
