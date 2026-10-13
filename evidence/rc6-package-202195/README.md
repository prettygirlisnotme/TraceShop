# 最终输入字节结构检查 · 202195

2026-10-13，COMPLETED 0:0，4 CPU / 12 GiB / 4秒，0 GPU、0 API；同作业完成最终媒体编码。复用已编译官方App Hub固定源码`386359153ed6377b5f047bd9ed2767a6a2ac2bc7`。

- [输入十文件摘要](input-sha256.json)与最终候选bundle逐项一致；在私有派生副本stamp后执行官方`check --allow-unsigned`， [检查输出](check-unsigned.txt)为PASSED，[结果摘要](summary.json)记录输入未改。
- [盖章派生manifest](stamped-manifest.json)、[派生十文件摘要](checked-sha256.json)、[stamp回执](stamp.txt)用于区分原始输入与实际被check的派生包；不把派生完整性字段强行回填源码。
- unsigned警告保留，预算与保存工具都等待宿主批准。没有签名/读钥、宿主运行、模型请求、GitHub attestation或Hub准入；它是最终字节的结构检查，不是正式发布、完整安装或比赛受理证明。

正式封存与证明由实际tag发布工作流产生。业务实录见[202120](../rc6-budget-202120/README.md)，完整范围见[VALIDATION](../../docs/VALIDATION.md)。
