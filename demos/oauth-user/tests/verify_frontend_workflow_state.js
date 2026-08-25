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
  const responses = connectResponses ? [...connectResponses] : null;
  const sandbox = {
    console,
    document,
    window: {},
    localStorage: {
      getItem() { return null; },
      setItem() {},
      removeItem() {},
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
          mock: true,
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

  return { elements, fetchCalls, click };
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
  const { elements, click } = await setup({ helperFields: fullHelperFields });
  await click("btn-auth");
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
  const { elements, click } = await setup({ perm: "read_only", helperFields: fullHelperFields });
  await click("btn-auth");
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
  const { elements, click } = await setup({ helperFields: spotOnlyHelperFields });
  await click("btn-auth");
  await click("btn-fill-demo-fields");

  assert.strictEqual(elements["spot-td-mode"].value, "cash");
  assert.strictEqual(elements["btn-spot-open"].disabled, false);
  assert.strictEqual(elements["btn-spot-close"].disabled, false);
  assert.strictEqual(elements["btn-swap-open"].disabled, true);
  assert.strictEqual(elements["btn-swap-close"].disabled, true);
}

async function testFailedReconnectDisablesOldWorkflowButtons() {
  const { elements, click } = await setup({
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
  await click("btn-auth");
  await click("btn-fill-demo-fields");
  assert.strictEqual(elements["btn-balance"].disabled, false);
  assert.strictEqual(elements["btn-spot-open"].disabled, false);

  await click("btn-auth");
  assert.strictEqual(elements["btn-balance"].disabled, true);
  assert.strictEqual(elements["btn-fill-demo-fields"].disabled, true);
  assert.strictEqual(elements["btn-spot-open"].disabled, true);
  assert.strictEqual(elements["btn-swap-open"].disabled, true);
}

(async () => {
  await testQuoteEditsDoNotInvalidateFilledFields();
  await testReadOnlyCanFillButCannotRunOrders();
  await testSpotOnlyAccountKeepsSpotButtonsAvailable();
  await testFailedReconnectDisablesOldWorkflowButtons();
  console.log("[ok] frontend workflow state checks passed");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
