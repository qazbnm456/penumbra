// Loads the SHIPPED penumbra/extension/background.js with a fake `chrome`, fetch and canvas, and
// drives the icon's per-tab state machine. Driven by tests/test_extension.py.
import { readFileSync } from "node:fs";

const code = readFileSync(new URL("../../penumbra/extension/background.js", import.meta.url), "utf8");

const listeners = [];
const hook = () => ({ addListener: (fn) => listeners.push(fn) });
const session = new Map();
const local = new Map([["base", "http://127.0.0.1:9"], ["token", "k"]]);
const store = (map) => ({
  async get(keys) {
    if (keys === null) return Object.fromEntries(map);
    const list = Array.isArray(keys) ? keys : [keys];
    return Object.fromEntries(list.filter((k) => map.has(k)).map((k) => [k, map.get(k)]));
  },
  async set(obj) { Object.entries(obj).forEach(([k, v]) => map.set(k, v)); },
  async remove(key) { map.delete(key); },
});
let tabUrl = "https://x.example/a";
const cards = [];
const chrome = {
  storage: { session: store(session), local: store(local), onChanged: hook() },
  action: new Proxy({}, { get: (_t, name) => (name.startsWith("on") ? hook() : async () => {}) }),
  tabs: { onUpdated: hook(), onRemoved: hook(), onActivated: hook(), get: async (id) => ({ id, url: tabUrl }) },
  windows: { onFocusChanged: hook() },
  runtime: { onInstalled: hook(), onStartup: hook(), onMessage: hook(), getURL: (p) => `ext://${p}`, openOptionsPage() {} },
  contextMenus: { onClicked: hook(), removeAll: (cb) => cb && cb(), create() {} },
  commands: { onCommand: hook() },
  alarms: { onAlarm: hook(), create() {}, clear: async () => {} },
  i18n: { getMessage: (key) => key, getUILanguage: () => "en" },
  scripting: {
    async executeScript({ func, args }) {
      if (func && func.name === "readPage") return [{ result: { html: "<p>x</p>", text: "x", title: "T", url: "https://x.example/a" } }];
      if (args && args[0]) cards.push(args[0].status);
      return [{}];
    },
  },
};

const requests = [];
let captureGate = null;
async function fetch(url, init = {}) {
  const path = String(url).replace(/^http:\/\/127\.0\.0\.1:9/, "");
  if (String(url).startsWith("ext://")) return { blob: async () => ({ arrayBuffer: async () => new ArrayBuffer(1) }) };
  requests.push(path);
  if (path === "/extension/capture" && captureGate) await captureGate;
  const body = path === "/extension/capture" ? { node: { id: "nd-1" }, duplicate: false, orbits: [] } : {};
  return { ok: true, status: 200, json: async () => body };
}
class OffscreenCanvas {
  getContext() {
    return new Proxy({}, { get: (_t, n) => (n === "getImageData" ? () => ({}) : () => {}), set: () => true });
  }
}

const api = new Function(
  "chrome", "fetch", "OffscreenCanvas", "createImageBitmap", "importScripts", "penumbraCard",
  `${code}\nreturn { pressIcon, tabState, settleOrphans, setTabState, inFlight };`,
)(chrome, fetch, OffscreenCanvas, async () => ({}), () => {}, function penumbraCard() {});

const flush = (ms = 0) => new Promise((resolve) => setTimeout(resolve, ms));
const tab = { id: 7, url: "https://x.example/a", title: "T" };
const results = {};

// Press: captured and marked kept. Press again: taken back.
await api.pressIcon(tab);
results.afterCapture = (await api.tabState(7)) || null;
await api.pressIcon(tab);
results.withdrawn = { undo: requests.includes("/extension/undo"), state: await api.tabState(7) };

// Pressed again while on its way: taken back the moment it lands.
requests.length = 0;
let release;
captureGate = new Promise((resolve) => { release = resolve; });
const first = api.pressIcon(tab);
await flush(20);
await api.pressIcon(tab);
results.cancelFlag = Boolean((await api.tabState(7)) && (await api.tabState(7)).cancel);
release();
await first;
captureGate = null;
results.cancelled = { undo: requests.includes("/extension/undo"), state: await api.tabState(7) };

// A capture left `saving` by a stopped worker becomes a failure to retry.
await chrome.storage.session.set({ "tab:9": { state: "saving", url: "https://x.example/z", tabId: 9, startedAt: Date.now() } });
await api.settleOrphans();
results.orphan = (await api.tabState(9)).state;

// A capture that lands after the tab moved on marks nothing.
tabUrl = "https://x.example/elsewhere";
await api.pressIcon({ ...tab, id: 11 });
results.movedOn = await api.tabState(11);

console.log(JSON.stringify(results));
process.exit(0);
