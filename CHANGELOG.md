# 变更记录（CHANGELOG）

本参考对应 OKX OAuth2.0 / Fast API 开发者文档（对外版）。后续若上游接口（端点、参数、签名规则等）变更，请同步更新本仓库与相关文档。

## v0.1.0 (2026-06-30)

- 初始版本：Fast API 接入参考（Python / Flask + HTML / JS），含 Mock 模式与单元测试。
- 待真机钉死项：换 token 路径 `/api/v5/...` vs `/v5/...`；`redirect_uri` 是否被 SDK 二次编码。
