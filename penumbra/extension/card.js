// The confirmation card, drawn on the page the reader captured from: what happened, the title that
// was kept, and the next step (put it into an orbit, or take it back). Pocket and Readwise answer a
// save the same way, on the page, because a toolbar badge is too small to notice.
//
// Injected with `chrome.scripting.executeScript({func: penumbraCard, args: [state]})`, so it must be
// self-contained: it runs in the extension's isolated world of the page, where it keeps one card and
// updates it. A closed shadow root keeps the page's styles out and the card's styles in.
function penumbraCard(state) {
  const HOST_ID = "__penumbra_card";
  let host = document.getElementById(HOST_ID);
  // A card left by an earlier copy of the extension (reloaded, updated) belongs to a world this one
  // cannot reach, so it would stay on the page forever; it is replaced.
  if (host && !window.__penumbraRoot) {
    host.remove();
    host = null;
  }
  if (!host) {
    host = document.createElement("div");
    host.id = HOST_ID;
    host.style.cssText = "position:fixed;top:16px;right:16px;z-index:2147483647;";
    (document.body || document.documentElement).appendChild(host);
    const root = host.attachShadow({ mode: "closed" });
    window.__penumbraRoot = root;
    const style = document.createElement("style");
    style.textContent = `
      :host { all: initial; }
      .card { box-sizing: border-box; width: 320px; padding: 14px 16px; border-radius: 14px;
        background: #1c1714; color: #efe6da; border: 1px solid #3a2f28;
        box-shadow: 0 16px 40px -12px rgba(0,0,0,.6), 0 2px 8px rgba(0,0,0,.35);
        font: 13px/1.5 -apple-system, BlinkMacSystemFont, "PingFang TC", "Segoe UI", sans-serif;
        transform: translateY(-8px); opacity: 0; transition: transform .22s cubic-bezier(.2,.9,.25,1), opacity .18s ease; }
      .card.is-in { transform: none; opacity: 1; }
      .head { display: flex; align-items: center; gap: 10px; }
      .moon { width: 22px; height: 22px; border-radius: 6px; flex: none; }
      .status { flex: 1; font-weight: 600; font-size: 14px; }
      .status.is-bad { color: #f2a07b; }
      .close { all: unset; cursor: pointer; color: #9c8f82; font-size: 16px; line-height: 1; padding: 2px 4px; border-radius: 6px; }
      .close:hover { color: #efe6da; background: #2a221d; }
      .title { margin: 8px 0 0; color: #cfc3b5; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
      .note { margin: 6px 0 0; color: #9c8f82; font-size: 12px; }
      .actions { display: flex; gap: 8px; margin-top: 12px; }
      select, button.act { all: unset; box-sizing: border-box; height: 30px; padding: 0 10px; border-radius: 8px;
        border: 1px solid #3a2f28; background: #26201b; color: #efe6da; cursor: pointer; font-size: 12.5px; }
      select { flex: 1; min-width: 0; line-height: 28px; }
      button.act { line-height: 28px; }
      button.act:hover, select:hover { border-color: #d9853b; }
      .pulse { width: 8px; height: 8px; border-radius: 50%; background: #d9853b; animation: p 1s ease-in-out infinite; }
      @keyframes p { 50% { opacity: .3; } }
      @media (prefers-reduced-motion: reduce) { .card { transition: none; } .pulse { animation: none; } }
    `;
    root.appendChild(style);
  }
  const root = window.__penumbraRoot;
  clearTimeout(window.__penumbraTimer);
  root.querySelectorAll(".card").forEach((old) => old.remove());

  const card = document.createElement("div");
  card.className = "card";
  card.setAttribute("role", "status");
  const head = document.createElement("div");
  head.className = "head";
  const moon = document.createElement("img");
  moon.className = "moon";
  moon.src = state.icon;
  moon.alt = "";
  head.appendChild(moon);
  const status = document.createElement("div");
  status.className = `status${state.bad ? " is-bad" : ""}`;
  status.textContent = state.status;
  head.appendChild(status);
  if (state.busy) {
    const pulse = document.createElement("div");
    pulse.className = "pulse";
    head.appendChild(pulse);
  }
  const close = document.createElement("button");
  close.className = "close";
  close.textContent = "✕";
  close.setAttribute("aria-label", state.closeLabel || "Close");
  head.appendChild(close);
  card.appendChild(head);
  if (state.title) {
    const title = document.createElement("div");
    title.className = "title";
    title.textContent = state.title;
    card.appendChild(title);
  }
  if (state.note) {
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = state.note;
    card.appendChild(note);
  }
  if ((state.nodeId && (state.orbits || []).length + (state.undoLabel || state.againLabel ? 1 : 0)) || state.recaptureLabel) {
    const actions = document.createElement("div");
    actions.className = "actions";
    if ((state.orbits || []).length) {
      const pick = document.createElement("select");
      pick.appendChild(new Option(state.fileLabel, ""));
      state.orbits.forEach((o) => pick.appendChild(new Option(o.title, o.id)));
      pick.addEventListener("change", () => {
        if (pick.value) chrome.runtime.sendMessage({ type: "card-file", nodeId: state.nodeId, orbit: pick.value });
      });
      actions.appendChild(pick);
    }
    if (state.againLabel) {
      const again = document.createElement("button");
      again.className = "act";
      again.textContent = state.againLabel;
      again.addEventListener("click", () => chrome.runtime.sendMessage({ type: "card-again" }));
      actions.appendChild(again);
    }
    if (state.recaptureLabel) {
      const recapture = document.createElement("button");
      recapture.className = "act";
      recapture.textContent = state.recaptureLabel;
      recapture.addEventListener("click", () => chrome.runtime.sendMessage({ type: "card-recapture" }));
      actions.appendChild(recapture);
    }
    if (state.undoLabel) {
      const undo = document.createElement("button");
      undo.className = "act";
      undo.textContent = state.undoLabel;
      undo.addEventListener("click", () => chrome.runtime.sendMessage({ type: "card-undo", nodeId: state.nodeId }));
      actions.appendChild(undo);
    }
    card.appendChild(actions);
  }
  root.appendChild(card);
  requestAnimationFrame(() => card.classList.add("is-in"));

  const leave = () => {
    card.classList.remove("is-in");
    setTimeout(() => card.remove(), 220);
  };
  close.addEventListener("click", leave);
  // Stays while the pointer is on it or a choice is open; otherwise leaves on its own.
  const arm = () => {
    clearTimeout(window.__penumbraTimer);
    // A card that waits for an answer still leaves in the end: if the answer never comes (the
    // extension restarted mid-request), "Keeping it…" must not stay on the page for good.
    window.__penumbraTimer = setTimeout(leave, state.stay ? 30000 : state.bad ? 7000 : 4500);
  };
  card.addEventListener("mouseenter", () => clearTimeout(window.__penumbraTimer));
  card.addEventListener("mouseleave", arm);
  card.addEventListener("focusin", () => clearTimeout(window.__penumbraTimer));
  arm();
}
