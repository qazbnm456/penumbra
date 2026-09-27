// The Penumbra extension: capture what this browser shows into the Horizon of the Penumbra running
// on this computer. It holds a capture key from pairing (`chrome.storage.local`), which opens three
// routes on the local server and nothing else: status, the orbits' names, and capture.
//
// What it captures, and why the server alone could not: a whole page as rendered here (behind a
// login, or drawn by JavaScript, the server's own fetch sees neither), a selected passage together
// with the page it came from (dragging text loses the address), and a link, which the server
// fetches like any pasted URL.

const MENU_ROOT = "penumbra";
const MENU_HORIZON = "horizon";
const MENU_CONNECT = "connect";
const ORBIT_PREFIX = "orbit:";
const CONTEXTS = ["page", "selection", "link"];
const COPPER = "#d9853b";

const msg = (key, ...subs) => chrome.i18n.getMessage(key, subs) || key;

async function pairing() {
  const { base, token } = await chrome.storage.local.get(["base", "token"]);
  return base && token ? { base, token } : null;
}

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
    throw new Error(msg("errorServer"));
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

// --- the menu -----------------------------------------------------------------------------------

async function rebuildMenus() {
  await chrome.contextMenus.removeAll();
  chrome.contextMenus.create({ id: MENU_ROOT, title: msg("menuRoot"), contexts: CONTEXTS });
  if (!(await pairing())) {
    chrome.contextMenus.create({ id: MENU_CONNECT, parentId: MENU_ROOT, title: msg("menuConnect"), contexts: CONTEXTS });
    return;
  }
  chrome.contextMenus.create({ id: MENU_HORIZON, parentId: MENU_ROOT, title: msg("menuHorizon"), contexts: CONTEXTS });
  let orbits = [];
  try {
    orbits = (await api("/extension/orbits")).orbits || [];
  } catch {
    // The server may be closed; the Horizon item still works once it is open again.
  }
  if (!orbits.length) return;
  chrome.contextMenus.create({ id: "sep", parentId: MENU_ROOT, type: "separator", contexts: CONTEXTS });
  orbits.slice(0, 30).forEach((orbit) => {
    chrome.contextMenus.create({
      id: `${ORBIT_PREFIX}${orbit.id}`,
      parentId: MENU_ROOT,
      title: msg("menuOrbit", orbit.title || orbit.id),
      contexts: CONTEXTS,
    });
  });
}

chrome.runtime.onInstalled.addListener(() => {
  void rebuildMenus();
  chrome.alarms.create("orbits", { periodInMinutes: 15 });
});
chrome.runtime.onStartup.addListener(() => void rebuildMenus());
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "orbits") void rebuildMenus();
});

// --- saying what happened -----------------------------------------------------------------------

async function flash(tabId, ok, detail = "") {
  await chrome.action.setBadgeBackgroundColor({ tabId, color: ok ? COPPER : "#b3261e" });
  await chrome.action.setBadgeText({ tabId, text: ok ? "✓" : "!" });
  await chrome.action.setTitle({ tabId, title: ok ? msg("done") : `${msg("failed")}: ${detail}` });
  setTimeout(() => {
    chrome.action.setBadgeText({ tabId, text: "" }).catch(() => {});
    chrome.action.setTitle({ tabId, title: msg("actionTitle") }).catch(() => {});
  }, ok ? 2500 : 8000);
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

async function capture(tab, { kind, orbit = null, link = "", selectionText = "" }) {
  const tabId = tab && tab.id;
  try {
    let body;
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
      const read = await inTab(tabId, readPage);
      body = { kind: "page", ...read };
    }
    if (orbit) body.orbit = orbit;
    await api("/extension/capture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (tabId) await flash(tabId, true);
  } catch (err) {
    if (tabId) await flash(tabId, false, err.message);
    if (!(await pairing())) chrome.runtime.openOptionsPage();
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

// --- pairing ------------------------------------------------------------------------------------

//: The pairing page's content script hands over the key it found in the page's fragment, with the
//: page's own origin, which is the server's address. The key is kept only if the server accepts it.
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (!message || message.type !== "pair") return false;
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
      await rebuildMenus();
      reply({ ok: true });
    } catch {
      reply({ ok: false });
    }
  })();
  return true;
});

chrome.storage.onChanged.addListener((changes) => {
  if (changes.token || changes.base) void rebuildMenus();
});
