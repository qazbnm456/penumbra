// The Penumbra extension: capture what this browser shows into the Horizon of the Penumbra running
// on this computer. It holds a capture key from pairing (`chrome.storage.local`), which opens only
// the capture routes on the local server: status, the orbits' names, capture, and filing or taking
// back a capture it just made.
//
// What it captures, and why the server alone could not: a whole page as rendered here (behind a
// login, or drawn by JavaScript, the server's own fetch sees neither), a selected passage together
// with the page it came from (dragging text loses the address), and a link, which the server
// fetches like any pasted URL, following a shortener hop by hop under its SSRF guard.
//
// It answers on the page, with a card (`card.js`), and it knows whether Penumbra is running: when it
// is not, the icon is greyed and a capture is kept here and sent when Penumbra is back.

importScripts("card.js");

const MENU_ROOT = "penumbra";
const MENU_HORIZON = "horizon";
const MENU_CONNECT = "connect";
const ORBIT_PREFIX = "orbit:";
const CONTEXTS = ["page", "selection", "link"];
//: What may wait here while Penumbra is closed: `chrome.storage.local` holds 10 MB, and a page's
//: HTML without its scripts and media is well under the per-item bound.
const QUEUE_MAX = 50;
const QUEUE_ITEM_BYTES = 2 * 1024 * 1024;

const msg = (key, ...subs) => chrome.i18n.getMessage(key, subs) || key;

//: The moon on the card, as a data URL: a page cannot load an image from the extension unless the
//: extension lists it as web-accessible, which would let any site detect that it is installed.
let iconData = "";
async function icon() {
  if (!iconData) {
    const blob = await (await fetch(chrome.runtime.getURL("icons/48.png"))).blob();
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let binary = "";
    bytes.forEach((b) => { binary += String.fromCharCode(b); });
    iconData = `data:image/png;base64,${btoa(binary)}`;
  }
  return iconData;
}

async function pairing() {
  const { base, token } = await chrome.storage.local.get(["base", "token"]);
  return base && token ? { base, token } : null;
}

//: A failure to reach the server, as distinct from the server refusing: only the first is a reason
//: to keep the capture for later.
class Unreachable extends Error {}

async function api(path, init = {}) {
  const paired = await pairing();
  if (!paired) throw new Error(msg("errorNotPaired"));
  let resp;
  try {
    resp = await fetch(`${paired.base}${path}`, {
      ...init,
      headers: { ...(init.headers || {}), Authorization: `Bearer ${paired.token}` },
    });
  } catch {
    throw new Unreachable(msg("errorServer"));
  }
  if (resp.status === 401) throw new Error(msg("errorUnpaired"));
  if (!resp.ok) {
    let detail = `${resp.status}`;
    try {
      detail = (await resp.json()).detail || detail;
    } catch {
      // not JSON
    }
    throw new Error(typeof detail === "string" ? detail : `${resp.status}`);
  }
  return resp.json();
}

// --- is Penumbra running? -----------------------------------------------------------------------

let online = null;

//: The icon, greyed while Penumbra cannot be reached or this browser is not paired, drawn from the
//: colour one so there is a single icon to keep.
async function paintIcon(on) {
  if (on) {
    await chrome.action.setIcon({ path: { 16: "icons/16.png", 32: "icons/32.png" } });
    return;
  }
  const imageData = {};
  for (const size of [16, 32]) {
    const bitmap = await createImageBitmap(await (await fetch(chrome.runtime.getURL(`icons/${size}.png`))).blob());
    const canvas = new OffscreenCanvas(size, size);
    const ctx = canvas.getContext("2d");
    ctx.filter = "grayscale(1) opacity(0.45)";
    ctx.drawImage(bitmap, 0, 0, size, size);
    imageData[size] = ctx.getImageData(0, 0, size, size);
  }
  await chrome.action.setIcon({ imageData });
}

async function checkOnline() {
  let now = false;
  if (await pairing()) {
    try {
      await api("/extension/status");
      now = true;
    } catch {
      now = false;
    }
  }
  const changed = now !== online;
  online = now;
  if (changed) {
    await paintIcon(now);
    await chrome.action.setTitle({ title: now ? msg("actionTitle") : msg((await pairing()) ? "offlineTitle" : "errorNotPaired") });
    await rebuildMenus();
  }
  if (now) await flushQueue();
  await paintQueueBadge();
  return now;
}

// --- the menu -----------------------------------------------------------------------------------

//: One rebuild at a time. Tab switches, window focus and the status alarm all ask for one, and two
//: running together each removed everything and then created the same ids, which the browser
//: reported as "Cannot create item with duplicate id".
let menuChain = Promise.resolve();

function rebuildMenus() {
  menuChain = menuChain.then(buildMenus, buildMenus);
  return menuChain;
}

function addMenu(item) {
  chrome.contextMenus.create(item, () => void chrome.runtime.lastError);
}

async function buildMenus() {
  await chrome.contextMenus.removeAll();
  const paired = await pairing();
  const title = !paired ? msg("menuRoot") : online ? msg("menuRoot") : msg("menuRootOffline");
  addMenu({ id: MENU_ROOT, title, contexts: CONTEXTS });
  if (!paired) {
    addMenu({ id: MENU_CONNECT, parentId: MENU_ROOT, title: msg("menuConnect"), contexts: CONTEXTS });
    return;
  }
  addMenu({ id: MENU_HORIZON, parentId: MENU_ROOT, title: msg("menuHorizon"), contexts: CONTEXTS });
  let orbits = [];
  if (online) {
    try {
      orbits = (await api("/extension/orbits")).orbits || [];
      await chrome.storage.local.set({ orbits });
    } catch {
      // keep the last list
    }
  }
  if (!orbits.length) orbits = (await chrome.storage.local.get("orbits")).orbits || [];
  if (!orbits.length) return;
  addMenu({ id: "sep", parentId: MENU_ROOT, type: "separator", contexts: CONTEXTS });
  orbits.slice(0, 30).forEach((orbit) => {
    addMenu({
      id: `${ORBIT_PREFIX}${orbit.id}`,
      parentId: MENU_ROOT,
      title: msg("menuOrbit", orbit.title || orbit.id),
      contexts: CONTEXTS,
    });
  });
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("status", { periodInMinutes: 0.5 });
  void checkOnline();
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create("status", { periodInMinutes: 0.5 });
  void checkOnline();
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "status") void checkOnline();
});
chrome.tabs.onActivated.addListener(() => void checkOnline());
chrome.windows.onFocusChanged.addListener(() => void checkOnline());

// --- kept while Penumbra is closed ----------------------------------------------------------------

async function queued() {
  return (await chrome.storage.local.get("queue")).queue || [];
}

async function paintQueueBadge() {
  const count = (await queued()).length;
  await chrome.action.setBadgeBackgroundColor({ color: "#7a6f66" });
  await chrome.action.setBadgeText({ text: count ? String(count) : "" });
}

async function keepForLater(body) {
  const size = new Blob([JSON.stringify(body)]).size;
  if (size > QUEUE_ITEM_BYTES) throw new Error(msg("errorTooLargeToKeep"));
  const queue = await queued();
  if (queue.length >= QUEUE_MAX) throw new Error(msg("errorQueueFull"));
  queue.push({ body, at: Date.now() });
  await chrome.storage.local.set({ queue });
  await paintQueueBadge();
  return queue.length;
}

let flushing = false;

async function flushQueue() {
  if (flushing) return;
  flushing = true;
  try {
    let queue = await queued();
    while (queue.length) {
      try {
        await api("/extension/capture", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(queue[0].body),
        });
      } catch (err) {
        if (err instanceof Unreachable) break; // closed again: keep the rest
        // Refused for a reason of its own (an orbit since deleted): drop it rather than retry it forever.
      }
      queue = queue.slice(1);
      await chrome.storage.local.set({ queue });
    }
  } finally {
    flushing = false;
    await paintQueueBadge();
  }
}

// --- the card on the page ------------------------------------------------------------------------

async function card(tabId, state) {
  if (!tabId) return false;
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: penumbraCard,
      args: [{ icon: await icon(), closeLabel: msg("close"), ...state }],
    });
    return true;
  } catch {
    return false; // a page extensions may not touch (the browser's own pages, the web store)
  }
}

async function badge(tabId, ok, detail = "") {
  if (!tabId) return;
  // The tab may have closed while the capture was on its way; that is not an error worth a report.
  try {
    await chrome.action.setBadgeBackgroundColor({ tabId, color: ok ? "#d9853b" : "#b3261e" });
    await chrome.action.setBadgeText({ tabId, text: ok ? "✓" : "!" });
    await chrome.action.setTitle({ tabId, title: ok ? msg("done") : `${msg("failed")}: ${detail}` });
  } catch {
    return;
  }
  setTimeout(() => {
    chrome.action.setBadgeText({ tabId, text: "" }).catch(() => {});
  }, ok ? 2500 : 8000);
}

async function tell(tabId, state) {
  if (!(await card(tabId, state))) await badge(tabId, !state.bad, state.note || state.status);
}

//: Captures on their way, by tab: a second press on the same page while the first is still going
//: says so instead of sending the page twice. The last capture's request is kept, by tab, for the
//: card's "keep another copy".
const inFlight = new Set();
const lastBody = new Map();

//: Where a capture went, or where automatic filing will take it: the card's second line.
async function placement(got, chosenTitle) {
  const orbits = await orbitList();
  const names = (got.orbits || []).map((id) => (orbits.find((o) => o.id === id) || {}).title).filter(Boolean);
  // Only with automatic filing is there something that might have moved it; say that it will not.
  const kept = got.filing_mode === "auto" ? msg("autoWontMove") : "";
  if (chosenTitle && got.filed) return { status: msg("savedInto", chosenTitle), note: kept };
  if (names.length) return { status: msg("savedInto", names.join("、")), note: "" };
  const note = got.filing_mode === "auto" ? msg("autoFilingNote") : "";
  return { status: msg("saved"), note };
}

// --- capturing ----------------------------------------------------------------------------------

//: Runs in the page: its rendered HTML without the parts that are not text (scripts, styles,
//: media), which keeps the upload small, plus its visible text as the fallback for an app-like page.
function readPage() {
  const clone = document.documentElement.cloneNode(true);
  clone.querySelectorAll("script,style,noscript,template,iframe,svg,canvas,video,audio,picture,img")
    .forEach((node) => node.remove());
  return {
    html: clone.outerHTML,
    text: document.body ? document.body.innerText : "",
    title: document.title,
    url: location.href,
  };
}

function readSelection() {
  return { text: String(window.getSelection() || ""), title: document.title, url: location.href };
}

async function inTab(tabId, func) {
  try {
    const [result] = await chrome.scripting.executeScript({ target: { tabId }, func });
    return result && result.result;
  } catch {
    throw new Error(msg("errorRestricted"));
  }
}

//: What a filing the reader asked for came to, in words: the server says why when it did not
//: happen, so the card states that reason rather than guessing one.
function filingNote(got, orbitTitle) {
  if (!got || got.filed === true) return "";
  if (got.filed === null || got.filed === undefined) return orbitTitle ? msg("fileWhenRead", orbitTitle) : "";
  if (got.outcome === "cap") {
    const lang = chrome.i18n.getUILanguage();
    const size = lang.startsWith("zh") ? `${Math.round(got.cap / 10000)} 萬` : got.cap.toLocaleString(lang);
    return msg("notFiledCap", size);
  }
  if (got.outcome === "gone") return msg("notFiledGone");
  return msg("notFiledOther");
}

async function orbitList() {
  return (await chrome.storage.local.get("orbits")).orbits || [];
}

async function capture(tab, { kind, orbit = null, link = "", selectionText = "" }) {
  const tabId = tab && tab.id;
  const paired = await pairing();
  if (!paired) {
    await tell(tabId, { status: msg("errorNotPaired"), note: msg("pairHowShort"), bad: true });
    chrome.runtime.openOptionsPage();
    return;
  }
  try {
    if (tab && tab.url && new URL(tab.url).origin === paired.base && kind !== "link") {
      await tell(tabId, { status: msg("ownPage"), bad: true });
      return;
    }
  } catch {
    // not a URL we can read; the capture itself will say
  }
  let body;
  try {
    if (kind === "link") {
      body = { kind, url: link, title: "" };
    } else if (kind === "selection") {
      const read = await inTab(tabId, readSelection).catch(() => null);
      body = {
        kind,
        url: (read && read.url) || tab.url,
        title: (read && read.title) || tab.title || "",
        text: (read && read.text.trim()) || selectionText,
      };
    } else {
      body = { kind: "page", ...(await inTab(tabId, readPage)) };
    }
  } catch (err) {
    await tell(tabId, { status: msg("failed"), note: err.message, bad: true });
    return;
  }
  if (orbit) body.orbit = orbit;
  await send(tab, body);
}

async function send(tab, body) {
  const tabId = tab && tab.id;
  const shown = body.title || body.url;
  if (inFlight.has(tabId)) {
    await tell(tabId, { status: msg("saving"), title: shown, busy: true, note: msg("stillSaving") });
    return;
  }
  inFlight.add(tabId);
  lastBody.set(tabId, body);
  await tell(tabId, { status: msg("saving"), title: shown, busy: true, stay: true });
  try {
    const got = await api("/extension/capture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const orbits = await orbitList();
    const into = body.orbit ? (orbits.find((o) => o.id === body.orbit) || {}).title : "";
    if (got.duplicate) {
      const where = await placement(got, "");
      await tell(tabId, {
        status: msg("alreadyKept"),
        title: (got.node && (got.node.title || (got.node.preview || {}).title)) || shown,
        note: where.status === msg("saved") ? msg("alreadyKeptNote") : where.status,
        nodeId: got.node && got.node.id,
        orbits: into ? [] : orbits,
        fileLabel: msg("fileInto"),
        againLabel: msg("keepAnother"),
      });
      return;
    }
    const where = await placement(got, into);
    await tell(tabId, {
      status: where.status,
      title: shown,
      note: into && !got.filed
        ? [filingNote(got, into), got.filing_mode === "auto" ? msg("autoWontMove") : ""].filter(Boolean).join(" ")
        : where.note,
      nodeId: got.node && got.node.id,
      orbits: into || (got.orbits || []).length ? [] : orbits,
      fileLabel: msg("fileInto"),
      undoLabel: msg("undo"),
    });
  } catch (err) {
    if (err instanceof Unreachable) {
      try {
        const count = await keepForLater(body);
        await tell(tabId, { status: msg("keptOffline"), title: shown, note: msg("keptOfflineNote", String(count)) });
      } catch (kept) {
        await tell(tabId, { status: msg("failed"), note: kept.message, bad: true });
      }
      void checkOnline();
      return;
    }
    await tell(tabId, { status: msg("failed"), title: shown, note: err.message, bad: true });
  } finally {
    inFlight.delete(tabId);
  }
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === MENU_CONNECT) {
    chrome.runtime.openOptionsPage();
    return;
  }
  const id = String(info.menuItemId);
  if (id !== MENU_HORIZON && !id.startsWith(ORBIT_PREFIX)) return;
  const orbit = id.startsWith(ORBIT_PREFIX) ? id.slice(ORBIT_PREFIX.length) : null;
  const kind = info.selectionText ? "selection" : info.linkUrl ? "link" : "page";
  void capture(tab, { kind, orbit, link: info.linkUrl || "", selectionText: info.selectionText || "" });
});

chrome.action.onClicked.addListener((tab) => void capture(tab, { kind: "page" }));
chrome.commands.onCommand.addListener((command, tab) => {
  if (command === "capture-page" && tab) void capture(tab, { kind: "page" });
});

// --- messages: the pairing page, and the card's two buttons ----------------------------------------

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (!message) return false;
  const tabId = sender.tab && sender.tab.id;
  if (message.type === "card-again") {
    const body = lastBody.get(tabId);
    if (body && sender.tab) void send(sender.tab, { ...body, force: true });
    return false;
  }
  if (message.type === "card-file" || message.type === "card-undo") {
    (async () => {
      try {
        if (message.type === "card-file") {
          const got = await api("/extension/file", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node_id: message.nodeId, orbit: message.orbit }),
          });
          const title = ((await orbitList()).find((o) => o.id === message.orbit) || {}).title || "";
          const kept = got.filing_mode === "auto" ? msg("autoWontMove") : "";
          await tell(tabId, got.filed === false
            ? { status: msg("notFiled", title), note: filingNote(got, title), bad: true }
            : got.filed === true ? { status: msg("savedInto", title), note: kept }
            : { status: msg("saved"), note: [filingNote(got, title), kept].filter(Boolean).join(" ") });
        } else {
          await api("/extension/undo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node_id: message.nodeId }),
          });
          await tell(tabId, { status: msg("undone") });
        }
      } catch (err) {
        await tell(tabId, { status: msg("failed"), note: err.message, bad: true });
      }
    })();
    return false;
  }
  if (message.type !== "pair") return false;
  // The pairing page's content script hands over the key it found in the page's fragment, with the
  // page's own origin, which is the server's address. The key is kept only if the server accepts it.
  const origin = sender.origin || (sender.url ? new URL(sender.url).origin : "");
  const local = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(origin);
  if (!local || !message.code) {
    reply({ ok: false });
    return false;
  }
  (async () => {
    try {
      const resp = await fetch(`${origin}/extension/status`, { headers: { Authorization: `Bearer ${message.code}` } });
      if (!resp.ok) throw new Error(String(resp.status));
      await chrome.storage.local.set({ base: origin, token: message.code });
      online = null;
      await checkOnline();
      reply({ ok: true });
    } catch {
      reply({ ok: false });
    }
  })();
  return true;
});

chrome.storage.onChanged.addListener((changes) => {
  if (changes.token || changes.base) {
    online = null;
    void checkOnline();
  }
});
