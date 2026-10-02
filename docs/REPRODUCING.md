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

## 可选原生 Agent 审阅

Web 页面研究会话中的“复制给 Agent 审阅”把候选、约束、证据、报价版本与有效期导出到剪贴板。要把它交给宿主 `octos`，需要一个能导入本地 mini-app 的 Rinx，并自行准备官方打包的 `octos` 内核。

导入目录就是仓库内的 [`native/agent-review/`](../native/agent-review/)（`README.md` + `main.splash` + `manifest.json`）。在 Rinx 中走 **Discover → Mini apps → Import**，选中该目录，Review 后 Run。`manifest.json` 的 `integrity.bundle_blake3` 必须由官方打包工具生成；**修改包里任何文件后都必须重新用官方工具盖章**，不能手填校验值。

本仓库记录的固定组合是：

- Rinx 提交 `5a9e2af2433a04129f2ad0c11acafb187c66f649`；
- `octos` 内核提交 `fe08d8e6b3b32e672b0f956a2b692c3c8205b167`（`2.0.3-rc.13`），需用上游官方工具打包；
- 构建当前 Rinx 二进制（宿主自行准备 Rust 工具链与上游 Linux 原生依赖）：

  ```bash
  git clone https://github.com/hagency-org/Rinx.git traceshop-host
  cd traceshop-host
  git checkout 5a9e2af2433a04129f2ad0c11acafb187c66f649
  cargo build --locked --features agent_chat --bin rinx --profile fast
  ```

内核见 [octos 固定源码](https://github.com/octos-org/octos/tree/fe08d8e6b3b32e672b0f956a2b692c3c8205b167)，宿主打包入口为 [tools/package-octos.py](https://github.com/hagency-org/Rinx/blob/5a9e2af2433a04129f2ad0c11acafb187c66f649/tools/package-octos.py)。编译固定内核后，在 Rinx 源码目录运行此次使用的官方打包命令（替换内核绝对路径）：

```bash
python3 tools/package-octos.py desktop --kernel /absolute/path/to/octos --app-binary target/fast/rinx
./target/fast/rinx
```

此步骤会校验上游锁定版本并将内核放到宿主可发现的位置；只构建 Rinx 不会自动提供内核。本仓库不附带这些二进制。

运行约定：

- **standalone Rinx，用自己的本地 Agent peer**：不是宿主注入的 OctoSense System Agent，也不是 Web URL 卡片的自动 bridge，未经签名或 App Hub 上架。
- provider/model/密钥在**宿主自己的 UI**里配置（例如 “Use this device” 表单），由宿主写成规范 profile；TraceShop 应用不接收、不保存密钥。密钥应由使用者本人提供，无需发给任何人。
- Web 页面不会自动调用 `octos`；必须由用户手动复制、粘贴并明确点击发起审阅。返回的只是文字建议，仍由用户在 Web 确认或拒绝。
- 这是**精确固定提交**的复现，不承诺最新移动中的 main，也不承诺 Windows 或其它未测试平台。
- Linux 上若 `XDG_RUNTIME_DIR` 缺失或其 socket 路径过长，Octos 可能启动失败；请使用已存在、路径短、权限 0700 且归当前用户所有的运行时目录，数据目录保持单独配置。

该组合的实测证据见 [VALIDATION.md](VALIDATION.md#1-原生-agent-审阅作业-1800452026-10-02) 与 `evidence/`。

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
