/*
 * verify_js_sign.js — 校验 SIGNING.md 里的 Node/JS 签名片段是否正确。
 *
 * 原理：用与 Python 单测 (tests/test_sign.py) 完全相同的固定向量（known-answer），
 *       让 JS 片段算出签名，断言与 Python 算出的基准值逐字节一致。
 *       一致 ⇒ JS 与 Python 实现等价（Python 那份有 OKX 标准签名的回归测试兜底）。
 *
 * 运行：node tests/verify_js_sign.js   （需要本机有 node；退出码非 0 表示不一致）
 * 说明：JS 片段若被改动，请重跑本脚本确保仍与基准一致。
 */
const crypto = require("crypto");

// === 下面 sign() 必须与 SIGNING.md 的 Node/JS 片段逐字一致 ===
function sign(secret, ts, method, path, body = "") {
  return crypto.createHmac("sha256", secret).update(ts + method.toUpperCase() + path + body).digest("base64");
}

// === 固定向量与基准，与 tests/test_sign.py 保持同步 ===
const SECRET = "mock-secret";
const TS = "2020-12-08T09:08:57.715Z";
const PATH = "/api/v5/account/balance";
const KNOWN_SIG_NO_QUERY = "tpQYvXdaAfU8ae6zI1rJ2xVcyMIk9BKWK/fysaanweQ=";
const KNOWN_SIG_WITH_QUERY = "pS6nHuBl6Qc9S0h+soCkCVHaVHZzS19KqFpeI/doTlE=";

const cases = [
  ["no_query", sign(SECRET, TS, "GET", PATH, ""), KNOWN_SIG_NO_QUERY],
  ["with_query", sign(SECRET, TS, "GET", PATH + "?ccy=BTC", ""), KNOWN_SIG_WITH_QUERY],
];

let ok = true;
for (const [name, got, want] of cases) {
  const pass = got === want;
  ok = ok && pass;
  console.log(`${pass ? "✅" : "❌"} ${name}: ${got}${pass ? "" : `  (期望 ${want})`}`);
}

if (!ok) {
  console.error("\nJS 签名片段与 Python 基准不一致！请检查 sign() 实现。");
  process.exit(1);
}
console.log("\n✅ JS 签名片段与 Python 基准完全一致。");
