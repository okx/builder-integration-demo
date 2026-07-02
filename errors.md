# 常见错误码与排查

> 来自 OKX OAuth2.0 / Fast API 开发者文档。联调时对照本表先自查。

## Fast API / OAuth 相关

| 错误码 | 含义 | 处理 |
|---|---|---|
| 50116 | Fast API 只能创建一个 API Key | 创建前先调 `delete-apikey`（本 demo 已自动处理） |
| 50117 | 只有 API 经纪商才能用 Fast API 创建 Key | 联系 BD 确认已开通 Fast API 权限 |
| 50118 | API Key 绑定 APP 需要 Broker 提供 IP 白名单 | 先开通 IP 白名单，再用 `bindApp=true` |
| 59506 | API Key 不存在 | 删除步骤遇到属正常，**忽略并继续**创建 |
| 53018 | 未获得 my.okx.com 站点授权 | 需先从 BD 获得该站点授权 |

## 授权流程相关

- **授权页不显示"快捷 API"**：检查 `scope` 是否为 `fast_api`。
- **授权失败 / redirect 报错**：`redirect_uri` 必须在 OKX 注册的白名单内；编码方式（是否 `encodeURIComponent`、有无双重编码）见 `TESTING.md` 的待验证项。
- **回跳后 state 不一致**：丢弃该回跳，可能是 CSRF；重新发起授权。

## 签名 / 调用业务接口相关

签名报错（如 401、`OK-ACCESS-SIGN` 校验失败）逐项核对：
1. `timestamp` 为 ISO8601 **毫秒 UTC**，如 `2020-12-08T09:08:57.715Z`，且与请求头一致。
2. prehash 顺序严格为 `timestamp + method(大写) + requestPath(含 query) + body`。
3. GET 请求 body 用空字符串参与签名；带 query 时 requestPath 要含 `?ccy=...`。
4. 模拟盘请求必须带头 `x-simulated-trading: 1`；实盘不要带。
5. `OK-ACCESS-PASSPHRASE` 用创建 Key 时的 passphrase。

## 令牌有效期（备查）

| 凭证 | 有效期 |
|---|---|
| 授权码 code | 10 分钟 |
| access_token | 1 小时 |
| refresh_token | 3 天（Fast API 无此项） |
| Fast API Key | 长期，直到用户解绑/撤销 |
