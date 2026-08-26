const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "frontend", "index.html"), "utf8");
const script = html.match(/<script>\n([\s\S]*)\n<\/script>/)[1];

class Element {
  constructor(id) {
    this.id = id;
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.textContent = "";
    this.listeners = {};
  }

  addEventListener(type, handler) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(handler);
  }

  async dispatch(type) {
    for (const handler of this.listeners[type] || []) {
      await handler({ type, target: this });
    }
  }
}

function jsonResponse(body) {
  return { json: async () => body };
}

async function setup({ perm = "trade", helperFields, connectResponses = null }) {
  const elements = {};
  const document = {
    getElementById(id) {
      if (!elements[id]) elements[id] = new Element(id);
      return elements[id];
    },
  };
  for (const id of [
    "btn-balance",
    "btn-fill-demo-fields",
    "btn-spot-open",
    "btn-spot-close",
    "btn-swap-open",
    "btn-swap-close",
  ]) {
    document.getElementById(id).disabled = true;
  }

  const fetchCalls = [];
  const authorizeCalls = [];
  const localStore = {};
  const responses = connectResponses ? [...connectResponses] : null;
  // Fake OKX Web SDK so the btn-auth handler can run in the sandbox (the real SDK
  // does a full-page redirect). authorize() records its options instead of navigating.
  const oauthSdk = {
    init() {},
    generateState: () => "generated-state",
    authorize: (opts) => { authorizeCalls.push(opts); },
  };
  const sandbox = {
    console,
    document,
    window: { OKEXOAuthSDK: oauthSdk },
    OKEXOAuthSDK: oauthSdk,
    localStorage: {
      getItem: (k) => (k in localStore ? localStore[k] : null),
      setItem: (k, v) => { localStore[k] = String(v); },
      removeItem: (k) => { delete localStore[k]; },
    },
    history: { replaceState() {} },
    location: { search: "", pathname: "/" },
    URLSearchParams,
    confirm: () => true,
    fetch: async (url) => {
      fetchCalls.push(url);
      if (url === "/config") {
        return jsonResponse({
          client_id: "mock-client",
          redirect_uri: "http://localhost:8000/",
          scope: "fast_api",
          okx_base_url: "https://www.okx.com",
          simulated: true,
          ai_builder_code: "ABCD1234",
        });
      }
      if (url === "/api/connect") {
        if (responses) {
          return jsonResponse(responses.shift());
        }
        return jsonResponse({
          ok: true,
          api_key_masked: "mock****key",
          perm,
          simulated: true,
        });
      }
      if (url === "/api/demo-workflow-fields") {
        return jsonResponse(helperFields);
      }
      throw new Error(`unexpected fetch: ${url}`);
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(script, sandbox, { filename: "frontend/index.html" });
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));

  async function click(id) {
    await elements[id].dispatch("click");
    await new Promise((resolve) => setImmediate(resolve));
  }

  // A-plan test hook: call the production runConnect() directly (it is a top-level
  // function in the page script, exposed on the vm context) instead of clicking
  // btn-auth. The real btn-auth path (OAuth SDK authorize + full-page redirect)
  // cannot run in this sandbox and is covered by real-environment (L3) testing.
  async function connect(code = "fake-code", state = "test-state") {
    await sandbox.runConnect(code, null, state);
    await new Promise((resolve) => setImmediate(resolve));
  }

  return { elements, fetchCalls, click, connect, authorizeCalls, localStore };
}

const fullHelperFields = {
  ok: true,
  simulated: true,
  account: { acctLv: "3", posMode: "long_short_mode" },
  fields: {
    spot: {
      available: true,
      instId: "BTC-USDT",
      quoteAmount: "10",
      tdMode: "cross",
    },
    swap: {
      available: true,
      instId: "BTC-USDT-SWAP",
      quoteAmount: "10",
      tdMode: "cross",
      mgnMode: "cross",
      posSide: "long",
    },
  },
};

async function testQuoteEditsDoNotInvalidateFilledFields() {
  const { elements, click, connect } = await setup({ helperFields: fullHelperFields });
  await connect();
  assert.strictEqual(elements["btn-balance"].disabled, false);
  assert.strictEqual(elements["btn-fill-demo-fields"].disabled, false);
  assert.strictEqual(elements["btn-spot-open"].disabled, true);

  await click("btn-fill-demo-fields");
  assert.strictEqual(elements["spot-td-mode"].value, "cross");
  assert.strictEqual(elements["swap-pos-side"].value, "long");
  assert.strictEqual(elements["btn-spot-open"].disabled, false);
  assert.strictEqual(elements["btn-swap-close"].disabled, false);

  elements["spot-quote"].value = "15";
  await elements["spot-quote"].dispatch("input");
  assert.strictEqual(elements["btn-spot-open"].disabled, false);
  assert.strictEqual(elements["btn-swap-open"].disabled, false);

  elements["spot-inst"].value = "ETH-USDT";
  await elements["spot-inst"].dispatch("input");
  assert.strictEqual(elements["btn-spot-open"].disabled, true);
  assert.strictEqual(elements["btn-spot-close"].disabled, true);
  assert.strictEqual(elements["btn-swap-open"].disabled, true);
  assert.strictEqual(elements["btn-swap-close"].disabled, true);
}

async function testReadOnlyCanFillButCannotRunOrders() {
  const { elements, click, connect } = await setup({ perm: "read_only", helperFields: fullHelperFields });
  await connect();
  await click("btn-fill-demo-fields");

  assert.strictEqual(elements["spot-inst"].value, "BTC-USDT");
  assert.strictEqual(elements["swap-pos-side"].value, "long");
  assert.strictEqual(elements["btn-spot-open"].disabled, true);
  assert.strictEqual(elements["btn-swap-open"].disabled, true);
}

async function testSpotOnlyAccountKeepsSpotButtonsAvailable() {
  const spotOnlyHelperFields = {
    ok: true,
    simulated: true,
    account: { acctLv: "1", posMode: "net_mode" },
    fields: {
      spot: {
        available: true,
        instId: "BTC-USDT",
        quoteAmount: "10",
        tdMode: "cash",
      },
      swap: {
        available: false,
        unavailableReason: "swap workflows require account mode acctLv=2, 3, or 4; current acctLv=1",
        instId: "BTC-USDT-SWAP",
        quoteAmount: "10",
        tdMode: "cross",
        mgnMode: "cross",
        posSide: "net",
      },
    },
  };
  const { elements, click, connect } = await setup({ helperFields: spotOnlyHelperFields });
  await connect();
  await click("btn-fill-demo-fields");

  assert.strictEqual(elements["spot-td-mode"].value, "cash");
  assert.strictEqual(elements["btn-spot-open"].disabled, false);
  assert.strictEqual(elements["btn-spot-close"].disabled, false);
  assert.strictEqual(elements["btn-swap-open"].disabled, true);
  assert.strictEqual(elements["btn-swap-close"].disabled, true);
}

async function testFailedReconnectDisablesOldWorkflowButtons() {
  const { elements, click, connect } = await setup({
    helperFields: fullHelperFields,
    connectResponses: [
      {
        ok: true,
        api_key_masked: "mock****key",
        perm: "trade",
        simulated: true,
      },
      {
        ok: false,
        step: "exchange_token",
        msg: "invalid code",
      },
    ],
  });
  await connect();
  await click("btn-fill-demo-fields");
  assert.strictEqual(elements["btn-balance"].disabled, false);
  assert.strictEqual(elements["btn-spot-open"].disabled, false);

  await connect();
  assert.strictEqual(elements["btn-balance"].disabled, true);
  assert.strictEqual(elements["btn-fill-demo-fields"].disabled, true);
  assert.strictEqual(elements["btn-spot-open"].disabled, true);
  assert.strictEqual(elements["btn-swap-open"].disabled, true);
}

// Covers the btn-auth authorize handler (SDK present path): the pre-authorize
// /config refresh, state fallback + localStorage persistence, and single-encoded
// redirect_uri. The connect() tests above drive runConnect directly; this drives
// the click path with a fake SDK so the handler body is exercised offline.
async function testAuthorizeButtonInvokesSdkWithEncodedRedirect() {
  const { click, authorizeCalls, localStore } = await setup({ helperFields: fullHelperFields });
  await click("btn-auth");

  assert.strictEqual(authorizeCalls.length, 1, "btn-auth should call OKEXOAuthSDK.authorize once");
  const opts = authorizeCalls[0];
  assert.strictEqual(opts.client_id, "mock-client");
  assert.strictEqual(opts.response_type, "code");
  assert.strictEqual(opts.scope, "fast_api");
  // redirect_uri must be encoded exactly once (single-encoded, not double).
  assert.ok(opts.redirect_uri.includes("%3A%2F%2F"), "redirect_uri should be URL-encoded");
  assert.ok(!opts.redirect_uri.includes("%253A"), "redirect_uri must not be double-encoded");
  // The outbound state is persisted to localStorage for the callback CSRF check.
  assert.ok(opts.state, "authorize must carry a state");
  assert.strictEqual(localStore["oauth_state"], opts.state);
}

(async () => {
  await testQuoteEditsDoNotInvalidateFilledFields();
  await testReadOnlyCanFillButCannotRunOrders();
  await testSpotOnlyAccountKeepsSpotButtonsAvailable();
  await testFailedReconnectDisablesOldWorkflowButtons();
  await testAuthorizeButtonInvokesSdkWithEncodedRedirect();
  console.log("[ok] frontend workflow state checks passed");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
