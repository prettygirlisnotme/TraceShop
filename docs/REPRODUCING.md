# 运行与宿主复现

## 应用

Python 3.10+，仅标准库。在仓库根目录运行：

```bash
python3 -m shop_agent.server \
  --catalog demo/catalog.jsonl \
  --db .local-state/demo.sqlite3 \
  --host 127.0.0.1 --port 8088 \
  --proposal-ttl 900
```

浏览器打开 <http://127.0.0.1:8088/>。省略参数时也使用该地址和随仓库的演示目录。`--db` 指定 SQLite 路径，`--proposal-ttl` 指定提案有效期。未提供本地图片编码/重排资源时，图片查询禁用。

```bash
python3 -m unittest discover -s tests -v
```

## Web 卡片

在支持 Web mini-app 的宿主中登录 Matrix 测试账号。宿主需要支持原生 Sliding Sync 的 homeserver；应用不读取、保存或代管聊天账号的凭据。

1. 在宿主 Web mini-app 表单填写 `http://127.0.0.1:8088/` 和标题 `TraceShop`。
2. 选择测试会话发送卡片，接收方打开卡片并查看地址。在已测试的 Linux 版本中点击 **Open in browser**。
3. 在应用中研究商品、审阅提议并确认，等待草稿读回通过。
4. 预览回执，点击“复制结果到聊天”，由用户返回宿主审阅并发送。复制本身不发消息。

消息内容示例见 [robrix2-card.example.json](../demo/robrix2-card.example.json)，它不是 App Hub manifest，也不授予聊天或账号权限。

`127.0.0.1` 指接收者自己的电脑；接收者须同时运行本应用。它不能作为其他电脑访问的公网演示地址，本地 URL 是否被赛方接受仍待确认。

## 历史宿主版本

本次测试的固定提交为 `05daf9bdb05fafc6d8f04dcb312a35f1d46a661e`，来自官网仍链接的历史 robrix2 分支。宿主独立构建，不属于本应用，不随本仓库提供二进制。

在自己的已授权开发环境准备 Rust 1.98.1、CMake 和[上游 Linux 原生依赖](https://github.com/hagency-org/Rinx/blob/05daf9bdb05fafc6d8f04dcb312a35f1d46a661e/README.md)，然后：

```bash
git clone https://github.com/hagency-org/Rinx.git traceshop-host
cd traceshop-host
git checkout 05daf9bdb05fafc6d8f04dcb312a35f1d46a661e
cargo build --locked --features agent_chat --bin robrix --profile fast
./target/fast/robrix
```

锁定的 matrix-sdk 0.18 要求 rustc >= 1.95；1.94 不足。无桌面时，本次使用 Xvfb + Mesa llvmpipe 软件 GL，原生点击产生的 URL 经记录适配器交给 headless Chromium。它证明地址与操作路径，不能当作默认桌面浏览器的测试。

最新 Rinx main 未验证，旧提交是否满足正式评审要求仍待确认。应用本身不依赖本项目使用的私有集群、临时 fixture、真实目录或模型。
