# TraceShop

购物决策与回执小程序。输入需求后，比较候选商品和目录证据；确认后保存采购草稿，读回核对结果，再由用户把回执带回聊天。报价或库存发生变化时，旧提案失效，需要重新研究和确认。

> **初赛作品入口：[SUBMISSION.md](SUBMISSION.md)** — 场景、任务、固定版本、材料链接、验证证据与已知边界。当前材料版本 v0.1.1。

- 队伍：**TraceShop**
- 唯一成员 ID：**TraceShop-Felix**（微信群昵称）
- 赛道：**OctoSense 购物与物流**
- 已加入参赛群

## 运行

需要 Python 3.10 或更新版本，仅使用标准库。

```bash
git clone https://github.com/prettygirlisnotme/TraceShop.git
cd TraceShop
python3 -m shop_agent.server
```

打开 <http://127.0.0.1:8088/>。默认使用 14 条自编演示商品，不需要下载模型或商品数据。图片入口在未配置本地模型时禁用。

```bash
python3 -m unittest discover -s tests -v
```

## 工作流

1. 解析文字条件，过滤硬约束，返回三个候选及目录证据。
2. 提案绑定商品、会话版本、报价版本与有效期。
3. 用户确认或拒绝；确认后创建 SQLite 采购草稿，重复确认返回同一草稿。
4. 从数据库独立读回，核对商品、价格和状态。
5. 模拟涨价或缺货，拦截旧提案；重新规划后仍需用户确认。
6. 预览并复制确认回执，由用户回到聊天决定是否发送。

![确认后读回](evidence/draft-verified.png)

[浏览器演示（约一分钟）](evidence/demo.webm) · [宿主发送卡片](evidence/host-card-sent.png) · [结果回到聊天](evidence/host-result-return.png) · [报价变化](evidence/quote-changed.png)

## 宿主接入

Web 卡片使用 `rs.robius.robrix.mini_app` 消息类型。[消息示例](demo/robrix2-card.example.json)与[复现步骤](docs/REPRODUCING.md)说明如何在兼容宿主打开本机地址。

官网示例链接的历史宿主提交 `05daf9bdb05fafc6d8f04dcb312a35f1d46a661e` 已在 Linux 测试：发送卡片、打开应用、确认草稿、读回、复制，再通过宿主发送回执。浏览器使用透明的 headless URL 打开器适配器；截图和浏览器录像分别提供。11 项标准库检查与 10 项宿主工作流检查通过，详见[验证记录](docs/VALIDATION.md)。

当前使用确定性规则策略，尚未连接 octos 模型服务。采购结果是本地草稿，不会向商户下单或扣款；报价和库存变化为模拟事件。最新 Rinx main 未验证，历史版本与本机 URL 的赛方受理口径尚待确认。

## 开发与来源

模块入口、状态约束和下一步见[开发说明](docs/DEVELOPMENT.md)，本地数据说明见[PRIVACY.md](PRIVACY.md)。

本项目采用 [Apache-2.0](LICENSE)。`vendor/project_a/` 复用已有购物检索管线，保留原许可证与逐文件校验；宿主协议参考保留 MIT 声明，见 [NOTICE](NOTICE)。真实商品目录和模型权重不在仓库中。
