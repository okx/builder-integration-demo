# 测试指南

本 demo 提供三层测试，覆盖从"没有任何 Broker 凭证"到"拿到测试 Broker 真机联调"的完整路径。

- (a) **单元测试** —— 不发网络，验证签名 / 时间戳逻辑正确（known-answer 回归）。
- (b) **Mock 模式** —— 不发真实 HTTP，用预置假响应把整条前端流程跑通看效果。
- (c) **真机验证清单** —— 拿到测试 Broker 后，按模拟盘 checklist 逐项核对。

> 安全：测试与 Mock 都不涉及任何真实密钥。Mock 里用的 `mock-secret` 是假占位串，
> 不是凭证；secret / passphrase 不会出现在任何前端响应、日志或 git 里。

---

## (a) 单元测试：`pytest`

安装开发依赖并运行：

```bash
cd okx-fastapi-broker-demo
python -m venv .venv && source .venv/bin/activate     # 可选，推荐隔离环境
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

预期输出类似 `10 passed`。

测什么（见 `tests/`）：

- **`tests/test_sign.py`** —— 核心签名逻辑：
  - `_sign` 的 **known-answer 回归**：固定 `secret/timestamp/method/path/body` 断言出固定签名，
    任何改动改变签名都会被发现。
  - prehash 拼接顺序严格为 `timestamp + METHOD(大写) + requestPath(含 query) + body`。
  - GET **带 query** 时 path 含 `?ccy=...`，签名因此不同于不带 query（防止有人误用 `params=`）。
  - 结果是合法 `base64(HMAC-SHA256)`，解码后为 32 字节。
  - `_now_iso_ms` 为 ISO8601 **毫秒 UTC**，形如 `2020-12-08T09:08:57.715Z`，以 `Z` 结尾、毫秒 3 位。
- **`tests/test_mock_flow.py`** —— MOCK 模式下用 Flask test client 跑
  `/api/connect → /api/balance`，断言 `ok=True`、apiKey 打码返回、
  且 **secret/secretKey/passphrase 不出现在任何响应里**。

> `tests/conftest.py` 会把 `backend/` 加进 `sys.path`，所以在仓库根目录直接 `pytest` 即可，
> 无需设置 `PYTHONPATH`。

---

### 多语言签名片段的正确性验证

`SIGNING.md` 给的 Python / Node-JS 签名片段，用**同一组 known-answer 向量**交叉校验：让 JS 片段算出的签名，与 Python 单测里的基准值（`tests/test_sign.py` 的 `KNOWN_SIG_*`）逐字节比对，一致即证明两种语言实现**算法等价**——而非靠肉眼 review。

```bash
node tests/verify_js_sign.js     # 需本机有 node；输出全 ✅、退出码 0 即通过
```

> 注意：这一步只证明 JS 与 Python **算法等价**；算法本身是否被 OKX 接受，与 Python 一样要靠真机（见 (c)）。
> 验证链：真机验证 Python 有效 → known-answer 钉死 Python 基准 → JS 比对一致 → JS 正确。
> 改动任何语言的签名片段后，请重跑本校验与 `pytest` 保持同步。

---

## (b) Mock 模式：本地跑通整条流程（无需 Broker 凭证）

设置环境变量 `MOCK=1` 启动后端。此时 `exchange_token` / `delete_oauth_apikey` /
`create_oauth_apikey` / `get_account_balance` **都不发真实 HTTP**，直接返回预置的 OKX 假响应。

```bash
cd okx-fastapi-broker-demo
pip install -r requirements.txt
MOCK=1 python backend/app.py
# 打开 http://localhost:8000
```

页面顶部模式标签会显示 `MOCK`。注意：

- **授权按钮仍会跳真实 OKX SDK**。要纯本地不跳转看后端流程，可直接打后端接口：

  ```bash
  # 1) 连接（任意假 code 即可，MOCK 不校验上游）
  curl -s -c cookies.txt -X POST http://localhost:8000/api/connect \
       -H 'Content-Type: application/json' -d '{"code":"mock-code"}'
  # → {"ok":true,"api_key_masked":"mock****3333","perm":"read_only","simulated":true}

  # 2) 查余额（带上一步的 session cookie）
  curl -s -b cookies.txt http://localhost:8000/api/balance
  # → {"ok":true,"raw":{"code":"0","data":[{"totalEq":"1200.0","details":[...]}]}}
  ```

- 关闭 Mock：不设 `MOCK`（或 `MOCK=0`）即恢复真实路径，行为与原来完全一致（零侵入）。
- 默认仍是 **模拟盘 + read_only**。

---

## (c) 真机验证清单（拿到测试 Broker 后）

前提：已从 BD 拿到 `client_id` / `client_secret`、开通 **Fast API 权限 + IP 白名单**、
`redirect_uri` 已登记进白名单。**全程先在模拟盘（`SIMULATED=1`）跑，不要直接上实盘。**

配置 `.env`（不要提交）：

```
CLIENT_ID=...
CLIENT_SECRET=...
REDIRECT_URI=http://localhost:8000/
APIKEY_PASSPHRASE=...        # 你自定义的 passphrase
SIMULATED=1                  # 模拟盘
APIKEY_PERM=read_only        # 只读
# 不要设 MOCK（或设 MOCK=0）
```

按顺序核对：

1. [ ] **授权页正常**：点「授权并连接」跳转 OKX，授权页能看到 **「快捷 API」** 权限项
       （看不到 → 检查 `scope=fast_api`）。
2. [ ] **回跳带 code**：授权后回跳本页，日志出现 `检测到授权回跳：code=...`。
3. [ ] **state 校验通过**：日志没有 `state 校验失败`。
4. [ ] **换 token 成功**：`/api/connect` 没有 `step=exchange_token` 错误。
5. [ ] **删旧 Key 放行**：`code=0`（删除成功）或 `59506`（不存在）都算正常。
6. [ ] **建 Key 成功**：页面显示打码 apiKey、`perm=read_only`、`simulated=true`。
7. [ ] **查余额成功**：点「查询余额」返回 `code=0`，结构含 `totalEq` / `details[]`。
8. [ ] **敏感字段不外泄**：检查浏览器响应 / 后端日志，**没有** secretKey / passphrase 明文。
9. [ ] **错误码对照**：遇到 50116/50117/50118/53018 等照 `errors.md` 排查。

跑通模拟盘只读后，再考虑按需调 `SIMULATED` / `APIKEY_PERM`（实盘 / 下单需更谨慎）。

### 两个必须真机敲死的待验证项

这两点开发文档/SDK 行为不一致，**只能用真测试 Broker 在浏览器里确认**，请重点验证：

1. **换 token 路径：`/api/v5/...` vs `/v5/...`**
   - 现状：`okx_client.py` 的 `PATH_OAUTH_TOKEN` 默认用 `"/api/v5/users/oauth/token"`
     （与删/建 Key 接口一致）；但开发者文档"获取令牌"段落写的是 `"/v5/users/oauth/token"`。
   - 验证：若步骤 4 换 token **报 404**，把 `PATH_OAUTH_TOKEN` 在这两个值之间切换后重试。
     `exchange_token` 已对 404 给出指向性提示（不静默重试，避免掩盖真实错误）。
   - **敲死哪个对**：联调成功后把正确路径固定下来，并更新该文件注释。

2. **`redirect_uri` 是否被 SDK 二次 encode（双重编码）**
   - 现状：`frontend/index.html` 按官方示例传 `redirect_uri: encodeURIComponent(CONFIG.redirect_uri)`，
     **未经真机验证**。如果 SDK 内部又 encode 一次，就会双重编码导致 `redirect_uri 不匹配 / 回跳丢失`。
   - 验证：跳转后打开浏览器 **Network**，看实际授权请求 URL 里的 `redirect_uri=` 值：
     - 正常：`http%3A%2F%2Flocalhost%3A8000%2F`（`:` → `%3A`）。
     - **双重编码特征**：出现 `%253A`（即 `%3A` 里的 `%` 又被编码成 `%25`）、`%252F` 等。
   - **若看到 `%253A`**：说明 SDK 又 encode 了一次。把那行改成直接传 `redirect_uri: CONFIG.redirect_uri`
     （去掉 `encodeURIComponent`），重试直到 Network 里只有单层编码、授权页 `redirect_uri` 匹配。
   - **敲死结论**：确认到底该不该 `encodeURIComponent`，固定写法并更新该行注释。
