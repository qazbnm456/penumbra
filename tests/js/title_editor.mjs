// Runs the SHIPPED `titleEditor` out of penumbra/web/app.js on a small fake DOM and reports what
// it sent. Driven by tests/test_web_behaviour.py.
import { readFileSync } from "node:fs";

const source = readFileSync(process.env.APP_JS || new URL("../../penumbra/web/app.js", import.meta.url), "utf8");
const grab = (name) => {
  const start = source.indexOf(`function ${name}(`);
  if (start < 0) throw new Error(`no function ${name}`);
  const end = source.indexOf("\n}\n", start);
  return source.slice(start, end + 2);
};

const document = { activeElement: null };
class El {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.parent = null;
    this.listeners = {};
    this.dataset = {};
    this.value = "";
    this.disabled = false;
    this.textContent = "";
    this.title = "";
    const set = new Set();
    this.classList = { add: (c) => set.add(c), remove: (c) => set.delete(c), contains: (c) => set.has(c) };
  }
  appendChild(child) { child.parent = this; this.children.push(child); return child; }
  contains(node) { for (let n = node; n; n = n.parent) if (n === this) return true; return false; }
  get isConnected() { let n = this; while (n.parent) n = n.parent; return n.connected === true; }
  setAttribute() {}
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  fire(type, extra = {}) {
    const event = { type, preventDefault() {}, stopPropagation() {}, ...extra };
    (this.listeners[type] || []).forEach((fn) => fn(event));
    return event;
  }
  focus() {
    const before = document.activeElement;
    if (before === this) return;
    document.activeElement = this;
    if (before) before.fire("blur", { relatedTarget: this });
  }
  select() {}
}
const elt = (tag, cls, text) => { const el = new El(tag); if (cls) el.className = cls; if (text) el.textContent = text; return el; };
document.createElement = (tag) => new El(tag);

const calls = [];
let script = {};
async function api(path, opts = {}) {
  calls.push({ path, method: opts.method || "GET", body: opts.body || null });
  const handler = script[path.includes("/cancel") ? "cancel" : path.endsWith("/suggestion") ? "suggest" : "put"];
  return handler ? handler() : {};
}
const t = (_key, fallback) => fallback;
const notify = () => {};
const readableError = (m) => m;
const state = { orbitId: "other" };
const store = { emit() {} };
let tokenCount = 0;
const crypto = { randomUUID: () => `tok${++tokenCount}` };

const { titleEditor } = new Function(
  "document", "elt", "api", "t", "notify", "readableError", "state", "store", "crypto",
  `${grab("suggestionRunId")}\n${grab("titleEditor")}\nreturn { titleEditor };`,
)(document, elt, api, t, notify, readableError, state, store, crypto);

const flush = (ms = 0) => new Promise((resolve) => setTimeout(resolve, ms));

function mount(current = "Old") {
  const root = new El("div");
  root.connected = true;
  const done = [];
  const editor = titleEditor("orbit-a", current, (title) => done.push(title), "slug-a");
  root.appendChild(editor);
  const [input, suggest] = editor.children;
  return { root, editor, input, suggest, done };
}

const results = {};

// Escape, then the blur its repaint causes: nothing is saved.
{
  calls.length = 0; script = {};
  const { input, done } = mount();
  await flush();
  input.value = "Half typed";
  input.fire("keydown", { key: "Escape" });
  input.fire("blur", { relatedTarget: null });
  await flush(10);
  results.escape = { puts: calls.filter((c) => c.method === "PUT").length, done };
}

// Enter, then a blur: one rename, not two.
{
  calls.length = 0;
  script = { put: async () => { await flush(20); return { title: "New" }; } };
  const { input, done } = mount();
  await flush();
  input.value = "New";
  input.fire("keydown", { key: "Enter" });
  input.fire("blur", { relatedTarget: null });
  await flush(60);
  results.enter = { puts: calls.filter((c) => c.method === "PUT").length, done };
}

// A suggestion running when the editor closes is cancelled, by the predicted run id.
{
  calls.length = 0;
  script = { suggest: () => new Promise(() => {}), cancel: async () => ({ cancelled: true }) };
  const { input, suggest } = mount();
  await flush();
  suggest.fire("click");
  await flush();
  input.fire("keydown", { key: "Escape" });
  await flush(10);
  results.close = calls.filter((c) => c.path.includes("/cancel")).map((c) => c.path);
}

// A Stop pressed before the server announced the run is asked again after a 404.
{
  calls.length = 0;
  let misses = 2;
  script = {
    suggest: () => new Promise(() => {}),
    cancel: async () => { if (misses-- > 0) { const e = new Error("404: no in-flight run"); e.status = 404; throw e; } return { cancelled: true }; },
  };
  const { suggest } = mount();
  await flush();
  suggest.fire("click");
  await flush();
  suggest.fire("click");
  await flush(1200);
  results.retry = calls.filter((c) => c.path.includes("/cancel")).length;
}

console.log(JSON.stringify(results));
process.exit(0);
