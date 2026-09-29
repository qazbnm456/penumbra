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
  await chrome.action.setIcon({ imageData: await drawIcon({ grey: true }) });
}

const bitmaps = {};
async function iconBitmap(size) {
  if (!bitmaps[size]) {
    bitmaps[size] = await createImageBitmap(await (await fetch(chrome.runtime.getURL(`icons/${size}.png`))).blob());
  }
  return bitmaps[size];
}

//: The moon at 16 and 32 pixels, greyed while offline, with this tab's mark in the lower right: a
//: turning arc while a capture is on its way, a tick once kept, a cross when it failed.
async function drawIcon({ grey = false, mark = "", frame = 0 } = {}) {
  const imageData = {};
  for (const size of [16, 32]) {
    const canvas = new OffscreenCanvas(size, size);
    const ctx = canvas.getContext("2d");
    if (grey) ctx.filter = "grayscale(1) opacity(0.45)";
    ctx.drawImage(await iconBitmap(size), 0, 0, size, size);
    ctx.filter = "none";
    if (mark) {
      const r = size * 0.3;
      const cx = size - r;
      const cy = size - r;
      const line = Math.max(1.5, size / 11);
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = mark === "saved" ? "#d9853b" : mark === "failed" ? "#b3261e" : "#2a211c";
      ctx.fill();
      ctx.strokeStyle = mark === "saving" ? "#d9853b" : "#ffffff";
      ctx.lineWidth = line;
      ctx.lineCap = "round";
      ctx.beginPath();
      if (mark === "saved") {
        ctx.moveTo(cx - r * 0.45, cy);
        ctx.lineTo(cx - r * 0.1, cy + r * 0.35);
        ctx.lineTo(cx + r * 0.5, cy - r * 0.35);
      } else if (mark === "failed") {
        const d = r * 0.4;
        ctx.moveTo(cx - d, cy - d);
        ctx.lineTo(cx + d, cy + d);
        ctx.moveTo(cx + d, cy - d);
        ctx.lineTo(cx - d, cy + d);
      } else {
        const start = (frame % 8) * (Math.PI / 4);
        ctx.arc(cx, cy, r * 0.55, start, start + Math.PI * 1.4);
      }
      ctx.stroke();
    }
    imageData[size] = ctx.getImageData(0, 0, size, size);
  }
  return imageData;
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

// --- this tab's capture, on the icon -------------------------------------------------------------
//
// A page capture's state, by tab, in `chrome.storage.session` so it outlives a service-worker restart
// but not the browser: `saving`, `saved` (with the node it made, and whether this press made it) or
// `failed`. Pressing the icon again acts on it: while saving it cancels (the capture is taken back
// the moment it lands), once saved it takes it back, after a failure it tries again. Chrome resets a
// tab's icon when the tab navigates, and the state is dropped then too.

const tabKey = (tabId) => `tab:${tabId}`;

async function tabState(tabId) {
  if (!tabId) return null;
  return (await chrome.storage.session.get(tabKey(tabId)))[tabKey(tabId)] || null;
}

async function setTabState(tabId, state) {
  if (!tabId) return;
  if (state) await chrome.storage.session.set({ [tabKey(tabId)]: state });
  else await chrome.storage.session.remove(tabKey(tabId));
  await paintTab(tabId, state);
}

const spinning = new Set();
let spinTimer = null;
let spinFrame = 0;

async function paintTab(tabId, state) {
  const mark = state ? state.state : "";
  if (mark === "saving") spinning.add(tabId);
  else spinning.delete(tabId);
  if (spinning.size && !spinTimer) {
    spinTimer = setInterval(() => {
      spinFrame += 1;
      spinning.forEach((id) => {
        drawIcon({ grey: online === false, mark: "saving", frame: spinFrame })
          .then((imageData) => chrome.action.setIcon({ tabId: id, imageData }))
          .catch(() => spinning.delete(id));
      });
    }, 125);
  } else if (!spinning.size && spinTimer) {
    clearInterval(spinTimer);
    spinTimer = null;
  }
  try {
    if (!mark) {
      if (online === false) await chrome.action.setIcon({ tabId, imageData: await drawIcon({ grey: true }) });
      else await chrome.action.setIcon({ tabId, path: { 16: "icons/16.png", 32: "icons/32.png" } });
      await chrome.action.setTitle({ tabId, title: msg(online === false ? "offlineTitle" : "actionTitle") });
      return;
    }
    await chrome.action.setIcon({ tabId, imageData: await drawIcon({ grey: online === false, mark, frame: spinFrame }) });
    await chrome.action.setTitle({ tabId, title: msg(mark === "saving" ? "titleSaving" : mark === "saved" ? "titleSaved" : "titleFailed") });
  } catch {
    // the tab closed meanwhile
  }
}

chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.status === "loading") void setTabState(tabId, null);
});
chrome.tabs.onRemoved.addListener((tabId) => {
  spinning.delete(tabId);
  void chrome.storage.session.remove(tabKey(tabId));
});

//: The icon pressed on a page: capture it, or act on the capture already made from it.
async function pressIcon(tab) {
  const tabId = tab && tab.id;
  const state = await tabState(tabId);
  const here = state && (!state.url || !tab.url || state.url === tab.url);
  if (here && state.state === "saving") {
    await setTabState(tabId, { ...state, cancel: true });
    await tell(tabId, { status: msg("cancelling"), title: state.title, busy: true, stay: true });
    return;
  }
  if (here && state.state === "saved") {
    await withdraw(tab, state);
    return;
  }
  await capture(tab, { kind: "page" });
}

async function withdraw(tab, state) {
  const tabId = tab && tab.id;
  if (!state.mine || !state.nodeId) {
    await tell(tabId, { status: msg("notMine"), title: state.title, note: msg("notMineNote"), bad: true });
    return;
  }
  try {
    await api("/extension/undo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node_id: state.nodeId }),
    });
  } catch (err) {
    const late = /not a capture this browser just made/.test(err.message);
    await tell(tabId, { status: msg("failed"), title: state.title, note: late ? msg("tooLateNote") : err.message, bad: true });
    return;
  }
  await setTabState(tabId, null);
  await tell(tabId, { status: msg("undone"), title: state.title, recaptureLabel: msg("captureAgain") });
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
  // Only a whole page is this tab's capture; a passage or a link is not the page the icon stands for.
  const mine = body.kind === "page";
  if (mine) await setTabState(tabId, { state: "saving", url: body.url, title: shown });
  await tell(tabId, { status: msg("saving"), title: shown, busy: true, stay: true });
  try {
    const got = await api("/extension/capture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const orbits = await orbitList();
    const into = body.orbit ? (orbits.find((o) => o.id === body.orbit) || {}).title : "";
    if (mine) {
      const nodeId = got.node && got.node.id;
      const before = await tabState(tabId);
      await setTabState(tabId, { state: "saved", url: body.url, title: shown, nodeId, mine: !got.duplicate });
      // Pressed again while it was on its way: take it back now that it has landed.
      if (before && before.cancel) {
        await withdraw(tab, { state: "saved", url: body.url, title: shown, nodeId, mine: !got.duplicate });
        return;
      }
    }
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
    if (mine) await setTabState(tabId, err instanceof Unreachable ? null : { state: "failed", url: body.url, title: shown });
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

chrome.action.onClicked.addListener((tab) => void pressIcon(tab));
chrome.commands.onCommand.addListener((command, tab) => {
  if (command === "capture-page" && tab) void pressIcon(tab);
});

// --- messages: the pairing page, and the card's two buttons ----------------------------------------

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (!message) return false;
  const tabId = sender.tab && sender.tab.id;
  if (message.type === "card-recapture") {
    if (sender.tab) void capture(sender.tab, { kind: "page" });
    return false;
  }
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
          const state = await tabState(tabId);
          if (state && state.nodeId === message.nodeId) await setTabState(tabId, null);
          await tell(tabId, { status: msg("undone"), recaptureLabel: msg("captureAgain") });
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
