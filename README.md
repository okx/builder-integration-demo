# OKX Fast API 接入 Demo

一个**可运行**的最小参考，演示第三方应用（Broker）如何用 OKX **Fast API** 为用户创建并托管 API Key，进而代表用户调用 OKX 接口（适合交易机器人 / 量化策略）。

> 给接入方的话：这个仓库设计成"**对 AI 友好**"——你可以把整个文件夹丢给 Cursor / Claude Code 等，让 AI 照着 `INTEGRATION_GUIDE.md` 帮你接入到自己的技术栈。后端示例用 Python，但规范是语言中立的。

## 为什么是 Fast API（而不是普通 OAuth）

交易机器人需要在用户**不在场**时持续运行。普通 OAuth 的 refresh_token 只有 3 天，用户几天不来就断了。Fast API 让你一次授权就拿到**长期有效的 API Key**，机器人可 7×24 跑。详见 `INTEGRATION_GUIDE.md`。

## 目录结构

```
okx-fastapi-broker-demo/
├── README.md              ← 你在这里（人看的快速上手）
├── 接入指南.md            ← 接入指南（给人读的中文说明）
├── INTEGRATION_GUIDE.md   ← 语言中立接入规范（AI / 开发者主要读这份）
├── SIGNING.md             ← HMAC 签名多语言片段（Python / JS）+ 验证向量
├── AGENTS.md              ← 给 AI 编程助手的规则
├── errors.md              ← 错误码与排查
├── TESTING.md             ← 测试说明（单测 + Mock 模式）
├── CHANGELOG.md           ← 变更记录
├── .env.example           ← 配置模板（复制为 .env 填写）
├── requirements.txt        ← 运行依赖
├── requirements-dev.txt    ← 测试依赖（pytest）
├── backend/
│   ├── app.py             ← Flask：换 token / 删建 Key / 查余额
│   └── okx_client.py      ← 所有 OKX HTTP 调用 + HMAC 签名
├── frontend/
│   └── index.html         ← 授权页 + 回调处理（OKX Web SDK）
└── tests/                 ← 单元测试（含 Mock 模式，无需真实凭证）
```

## 前置条件

接入前需联系 BD 申请 **OAuth Broker** 并开通 **Fast API 权限 + IP 白名单**，拿到 `client_id` / `client_secret`，并把 `redirect_uri`（本 demo 默认 `http://localhost:8000/`）登记进 OKX 白名单。完整申请步骤见 `接入指南.md`，以及对外文档（待补链接：TODO）。

## 运行

```bash
cd okx-fastapi-broker-demo
cp .env.example .env          # 填 CLIENT_ID / CLIENT_SECRET / REDIRECT_URI / APIKEY_PASSPHRASE
pip install -r requirements.txt
python backend/app.py
# 打开 http://localhost:8000
```

默认 **模拟盘 + 只读权限**，安全。需要实盘/下单再改 `.env` 里的 `SIMULATED` / `APIKEY_PERM`。

## 操作流程

1. 点「授权并连接 OKX」→ 跳转 OKX 授权页（确认是"快捷 API"权限）→ 授权后回跳本页。
2. 后端自动完成：换 token → 删旧 Key → 建 Key → 存储。页面显示打码后的 apiKey。
3. 点「查询余额」→ 后端用 API Key 签名调用 `GET /api/v5/account/balance`，展示返回。

## 安全须知

- `client_secret`、`secretKey`、`passphrase` **只在后端**，不进前端 / 日志 / git。
- 本 demo 用进程内存储 Key **仅为演示**；生产必须按用户隔离、加密落库。
- `.env` 不要提交到版本库。

## 测试

仓库带有单元测试，并提供 **Mock 模式**：无需真实 `client_id` / `client_secret`，也能跑通换 token → 删建 Key → 查余额的完整流程，方便快速验证接入逻辑。运行方式与用例细节见 `TESTING.md`。

## 文档索引

| 文档 | 受众 | 用途 |
|---|---|---|
| `README.md` | 人（接入方） | 快速上手、运行与目录导航（你在这里） |
| `接入指南.md` | 人（接入方） | 中文接入指南，含申请等人工步骤 |
| `INTEGRATION_GUIDE.md` | AI / 开发者 | 语言中立的精确接入规范（改写到其它技术栈时主要读这份） |
| `SIGNING.md` | AI / 开发者 | HMAC 签名多语言片段（Python / JS）+ known-answer 验证向量 |
| `AGENTS.md` | AI 编程助手 | 帮用户接入时必须遵守的规则与易踩坑 |
| `errors.md` | 人 / AI | 错误码与排查 |
| `TESTING.md` | 人 / AI | 测试说明（单测 + Mock 模式） |
| `CHANGELOG.md` | 人 / AI | 变更记录 |
