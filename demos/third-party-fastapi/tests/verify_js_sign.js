/*
 * Verifies that the Node.js signing snippet in SIGNING.md matches the
 * Python known-answer vectors from tests/test_sign.py.
 *
 * Run: node tests/verify_js_sign.js
 */
const crypto = require("crypto");

// Keep this function aligned with the Node.js snippet in SIGNING.md.
function sign(secret, ts, method, path, body = "") {
  return crypto.createHmac("sha256", secret).update(ts + method.toUpperCase() + path + body).digest("base64");
}

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
  console.log(`${pass ? "[ok]" : "[fail]"} ${name}: ${got}${pass ? "" : `  (expected ${want})`}`);
}

if (!ok) {
  console.error("\nNode.js signing snippet does not match Python baseline.");
  process.exit(1);
}
console.log("\nNode.js signing snippet matches Python baseline.");
