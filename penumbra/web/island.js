// The island's behaviour. Zero-build, like the rest of `web/`, and it talks to the same server the
// workspace does, over HTTP with the same token (invariants 77 and 81).
//
// The SHELL owns geometry: it watches the pointer, sizes this window and calls
// `island.setState(...)`. The page owns everything drawn, and asks the shell for things only by
// navigating to one of four fixed paths (`/__shell/open`, `/menu`, `/rest`, `/note`), which the
// shell intercepts and refuses. None of them carries any data.

(() => {
  const TOKEN_KEY = "penumbra-api-token";
  let token = "";

  // The shell opens this page at `island.html#token=…`, the same way it opens the workspace. The
  // fragment never reaches the server's log; it is read here and cleared from the address.
  try {
    const params = new URLSearchParams(window.location.hash.slice(1));
    token = params.get("token") || "";
    if (token) {
      try {
        localStorage.setItem(TOKEN_KEY, token);
      } catch {
        // storage blocked: this page keeps the token in memory, which is all it needs
      }
      window.history.replaceState(null, "", window.location.pathname);
    } else {
      token = localStorage.getItem(TOKEN_KEY) || "";
    }
  } catch {
    // no URL/history here: requests will say the token is missing
  }

  const say = (key, fallback, vars) => (typeof t === "function" ? t(key, fallback, vars) : fallback);
  const hole = document.getElementById("hole");
  const motes = document.getElementById("motes");
  const live = document.getElementById("live");

  // Pin the shape to the resting window's size in pixels at once. Left at `100%`, a window the
  // shell enlarges before its first `setState` arrives would drag the shape with it in one jump.
  hole.style.width = `${window.innerWidth}px`;
  hole.style.height = `${window.innerHeight}px`;

  if (typeof applyStaticI18n === "function") applyStaticI18n();
  document.documentElement.lang = typeof uiLang === "function" ? uiLang() : "en";

  // No visible words: what a state means is spoken to a screen reader instead.
  function announce(key, fallback, vars) {
    live.textContent = say(key, fallback, vars);
  }

  // A result is shown by the ring itself: a flash for "taken in", a red shake for "refused".
  function result(kind) {
    document.body.dataset.result = kind;
    setTimeout(() => {
      if (document.body.dataset.result === kind) delete document.body.dataset.result;
    }, 900);
  }

  // --- states, set by the shell --------------------------------------------------------------------

  const LINES = {
    armed: ["island.release", "Let go to send it into the Horizon"],
  };
  // A swallow owns its own words until the island closes; a late `armed` from the shell must not
  // put it back into the armed look while it is still taking something in.
  let swallowing = false;

  window.island = {
    setState(state, edge, inset, width, height) {
      if (edge) document.body.dataset.edge = edge;
      if (typeof inset === "number") document.body.style.setProperty("--inset", `${inset}px`);
      // The shape's size is explicit and TRANSITIONED, so it grows out of the notch and shrinks back
      // into it. The window around it is already at least this big (the shell grows the window
      // first and shrinks it last), so the animation always has room.
      if (typeof width === "number" && typeof height === "number") {
        hole.style.width = `${width}px`;
        hole.style.height = `${height}px`;
      }
      if (state === "swallow") swallowing = true;
      if (state === "collapsed") swallowing = false;
      if (swallowing && state === "armed") return;
      document.body.dataset.state = state;
      const words = LINES[state];
      if (words) announce(...words);
      if (state === "hover") startGlance();
      else stopGlance();
      if (state === "note") beginNote();
      else if (state === "listen") beginListen();
      else endNoteFocus();
      if (state === "peek") {
        listenHint.textContent = peekLine;
        live.textContent = peekLine;
        void glance();
      }
      if (state !== "hover" && state !== "listen") pen.classList.remove("is-hot");
    },
    // The shell tells the page where the pointer is, because a window in the background gets no
    // mouse-moved events and `:hover` never matches there. The page decides what is under it.
    pointer(x, y) {
      const box = pen.getBoundingClientRect();
      const pad = 6;
      pen.classList.toggle("is-hot",
        x >= box.left - pad && x <= box.right + pad && y >= box.top - pad && y <= box.bottom + pad);
    },
  };

  // --- the status glyph: what the Horizon is doing, read while the pointer rests here -------------

  const arc = document.getElementById("duo-arc");
  const dots = [...document.querySelectorAll(".duo-dot")];
  let glanceTimer = null;
  let litBefore = 0;
  let lastSpoken = "";

  let glancing = false;

  async function glance() {
    // One glance at a time, so a slow server is not asked again while it is still answering.
    if (glancing) return;
    glancing = true;
    try {
      await glanceOnce();
    } finally {
      glancing = false;
    }
  }

  async function glanceOnce() {
    let status;
    let topo;
    let suggested;
    try {
      [status, topo, suggested] = await Promise.all([
        send("/horizon/status", {}),
        send("/horizon/topology", {}),
        send("/horizon/suggestions", {}),
      ]);
    } catch {
      return; // the glyph keeps what it last showed; the island still works without it
    }
    const total = (topo.total && topo.total.count) || 0;
    const done = (topo.total && topo.total.distilled) || 0;
    document.body.style.setProperty("--done", String(total ? Math.round((done / total) * 100) : 0));
    if (done) delete document.body.dataset.noneDone;
    else document.body.dataset.noneDone = "";
    const distil = status.distil || {};
    if (distil.running || (status.align && status.align.running)) document.body.dataset.summarising = "";
    else delete document.body.dataset.summarising;
    if (status.current || status.pending) document.body.dataset.reading = "";
    else delete document.body.dataset.reading;
    // What waits to be filed, the same thing the map's waiting card counts: captures in no orbit,
    // or, when an orbit is assigned, the suggestions for captures only in it.
    const toFile = Math.max((topo.loose && topo.loose.count) || 0, suggested.count || 0);
    const lit = Math.min(4, toFile);
    dots.forEach((dot, i) => {
      dot.classList.toggle("is-lit", i < lit);
      dot.classList.toggle("is-new", i < lit && i >= litBefore);
    });
    litBefore = lit;
    // The glyph says nothing a screen reader can see, so its facts are spoken instead, and only
    // when they change: a live region repeated every four seconds is noise.
    const spoken = `${done}/${total}/${toFile}`;
    if (spoken !== lastSpoken) {
      lastSpoken = spoken;
      announce("island.glance", `${done} of ${total} summarised, ${toFile} to file`,
        { done, total, n: toFile });
    }
  }

  function startGlance() {
    if (glanceTimer) return;
    void glance();
    glanceTimer = setInterval(glance, 4000);
  }

  function stopGlance() {
    clearInterval(glanceTimer);
    glanceTimer = null;
  }

  // --- a pass finished: the one notice that reaches a closed workspace -------------------------------
  //
  // Read every few seconds whatever the island is doing, because a pass started from the workspace
  // or by a capture can end while the workspace is closed and nothing else would say so. When one
  // ends the ring is brought up to date and the shell is asked to show it briefly (`/__shell/peek`);
  // it goes back into the notch by itself. Only from rest: a hover, a drop or a note is left alone.
  let passWasRunning = null;
  let peekLine = "";

  async function watchPasses() {
    let status;
    try {
      status = await send("/horizon/status", {});
    } catch {
      return;
    }
    const distil = status.distil || {};
    const running = Boolean(distil.running || (status.align && status.align.running));
    const finished = passWasRunning === true && !running;
    passWasRunning = running;
    const done = distil.done || 0;
    const failed = distil.failed || 0;
    if (!finished || !(done || failed) || document.body.dataset.state !== "collapsed") return;
    peekLine = failed
      ? say("island.peekFailed", `${done} summarised, ${failed} could not be`, { n: done, failed })
      : say("island.peekDone", `${done} summarised`, { n: done });
    await glance();
    window.location.href = "/__shell/peek";
  }

  setInterval(watchPasses, 5000);
  void watchPasses();

  // --- open the workspace --------------------------------------------------------------------------

  function openWorkspace() {
    window.location.href = "/__shell/open";
  }

  hole.addEventListener("click", (event) => {
    // While it is a field, a click inside it is the reader placing the caret, not a request to
    // open the workspace.
    if (document.body.dataset.state === "note") return;
    if (event.target.closest(".pen")) return;
    openWorkspace();
  });
  // Right-click: the shell's menu (open, configure, restart, quit). In the background there is no
  // menu bar and no Dock icon, so this is the only place to quit from.
  window.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    window.location.href = "/__shell/menu";
  });
  hole.addEventListener("keydown", (event) => {
    // Keys typed into the note field are the reader's words. They bubbled up to here, so every
    // Return in the field, including the one that picks a Zhuyin candidate, also opened the
    // workspace, which took the keyboard away mid-thought.
    if (event.target.closest(".note")) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openWorkspace();
    }
  });

  // --- a thought, written straight into the Horizon ------------------------------------------------
  //
  // The pen (or the menu's "Write a Thought…") asks the shell for the note state with a fourth fixed
  // path, `/__shell/note`, which carries nothing. The shell opens the island into a one-line field
  // and lets this window take the keyboard. Return sends the line to the server over HTTP with the
  // token, the same way a drop is sent; Escape, or clicking anywhere else, puts it away. A line not
  // sent is kept for the next time, so putting the island away never loses a thought.

  const pen = document.getElementById("pen");
  const note = document.getElementById("note");
  const noteInput = document.getElementById("note-input");
  const DRAFT_KEY = "penumbra-island-draft";
  let sendingNote = false;

  pen.addEventListener("click", (event) => {
    event.stopPropagation();
    window.location.href = "/__shell/note";
  });

  function keepDraft() {
    try {
      if (noteInput.value.trim()) localStorage.setItem(DRAFT_KEY, noteInput.value);
      else localStorage.removeItem(DRAFT_KEY);
    } catch {
      // storage blocked: the draft lives only as long as this page
    }
  }

  function syncNoteLook() {
    note.classList.toggle("has-text", Boolean(noteInput.value.trim()));
  }

  function beginNote() {
    try {
      if (!noteInput.value) noteInput.value = localStorage.getItem(DRAFT_KEY) || "";
    } catch {
      // no storage
    }
    noteInput.tabIndex = 0;
    syncNoteLook();
    // The window becomes key a moment after the shell asks; focusing now and again on `focus`
    // covers either order.
    setTimeout(() => noteInput.focus(), 40);
    // The pointer no longer closes the island while it is a field, so a window that never got the
    // keyboard would stay open with nothing able to close it. It puts itself away instead.
    setTimeout(() => {
      if (document.body.dataset.state === "note" && !document.hasFocus()) putNoteAway();
    }, 2000);
  }

  // Listening: the island has the keyboard but keeps its hover shape, with a line saying typing
  // works. The first character opens the note field, carrying what was typed.
  const listenHint = document.getElementById("listen-hint");

  function beginListen() {
    listenHint.textContent = say("island.listenHint", "Or just start typing to keep a thought");
    announce("island.listenHint", "Or just start typing to keep a thought");
    noteInput.value = "";
    noteInput.tabIndex = 0;
    setTimeout(() => noteInput.focus(), 40);
  }

  function endNoteFocus() {
    noteInput.tabIndex = -1;
    if (document.activeElement === noteInput) noteInput.blur();
  }

  function putNoteAway() {
    keepDraft();
    window.location.href = "/__shell/rest";
  }

  window.addEventListener("focus", () => {
    const now = document.body.dataset.state;
    if (now === "note" || now === "listen") noteInput.focus();
  });
  // Clicking anywhere else takes the keyboard away from this window: that is the reader moving on.
  // Checked a moment later, not on the event: opening the field and an input method's candidate
  // window can each bounce key status for an instant, and closing on that lost the line.
  window.addEventListener("blur", () => {
    setTimeout(() => {
      if (document.hasFocus() || composing) return;
      const now = document.body.dataset.state;
      if ((now === "note" && !sendingNote) || now === "listen") putNoteAway();
    }, 250);
  });
  noteInput.addEventListener("input", () => {
    syncNoteLook();
    // Typing while listening is the reader choosing to write: the island opens into the field.
    // Not on each composing keystroke's commit alone; any non-empty value is enough.
    if (document.body.dataset.state === "listen" && noteInput.value) {
      window.location.href = "/__shell/note";
      return;
    }
    keepDraft();
  });
  // Composition is tracked here rather than read off each key: with Zhuyin, Pinyin or Kana, Return
  // and Escape belong to the input method until it commits, and WebKit can deliver the committing
  // Return after `compositionend`, reporting it as keyCode 229 or not at all as composing. A key
  // within a moment of the end is still the input method's.
  let composing = false;
  let composedAt = 0;
  noteInput.addEventListener("compositionstart", () => { composing = true; });
  noteInput.addEventListener("compositionend", () => {
    composing = false;
    composedAt = Date.now();
  });
  const imeOwns = (event) => composing || event.isComposing || event.keyCode === 229
    || Date.now() - composedAt < 80;

  noteInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (imeOwns(event)) return; // it cancels the candidate, not the note
      event.preventDefault();
      putNoteAway();
      return;
    }
    if (document.body.dataset.state === "listen") return;
    if (event.key === "Enter" && !imeOwns(event)) {
      event.preventDefault();
      void sendNote();
    }
  });
  // Implicit submission is not used: it cannot tell a composing Return from a real one.
  note.addEventListener("submit", (event) => event.preventDefault());

  async function sendNote() {
    const line = noteInput.value.trim();
    if (!line) {
      putNoteAway();
      return;
    }
    if (sendingNote) return;
    sendingNote = true;
    const link = /^https?:\/\/\S+$/i.test(line);
    const box = noteInput.getBoundingClientRect();
    document.body.dataset.busy = "";
    try {
      await send("/horizon", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(link ? { urls: [line], texts: [] } : { urls: [], texts: [line] }),
      });
      noteInput.value = "";
      keepDraft();
      syncNoteLook();
      fall([line], box.left + 24, box.top + box.height / 2);
      result("ok");
      announce("island.noted", "Kept in the Horizon");
      setTimeout(() => {
        sendingNote = false;
        window.location.href = "/__shell/rest";
      }, 900);
    } catch (err) {
      sendingNote = false;
      result("bad");
      const why = whyNot(err);
      live.textContent = why ? `${say("island.failed", "Could not take that in")}: ${why}` : say("island.failed", "Could not take that in");
      noteInput.focus();
    } finally {
      delete document.body.dataset.busy;
    }
  }

  // --- capture -------------------------------------------------------------------------------------

  async function send(path, init = {}) {
    const headers = { ...(init.headers || {}), Authorization: `Bearer ${token}` };
    if (typeof uiLangName === "function") headers["X-Penumbra-Interface-Language"] = uiLangName();
    const resp = await fetch(path, { ...init, headers });
    if (!resp.ok) {
      let detail = `${resp.status}`;
      try {
        detail = (await resp.json()).detail || detail;
      } catch {
        // not JSON
      }
      const failure = new Error(typeof detail === "string" ? detail : `${resp.status}`);
      failure.status = resp.status;
      throw failure;
    }
    return resp.json();
  }

  // What a drag carries, in the order a person means it: files first, then links, then text.
  function readDrop(data) {
    const files = [...(data.files || [])];
    if (files.length) return { files, urls: [], texts: [], names: files.map((f) => f.name) };
    const uris = (data.getData("text/uri-list") || "")
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#") && /^https?:\/\//i.test(l));
    if (uris.length) return { files: [], urls: uris, texts: [], names: uris.map(hostOf) };
    const text = (data.getData("text/plain") || "").trim();
    if (!text) return null;
    if (/^https?:\/\/\S+$/i.test(text)) return { files: [], urls: [text], texts: [], names: [hostOf(text)] };
    return { files: [], urls: [], texts: [text], names: [text.slice(0, 40)] };
  }

  function hostOf(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return url.slice(0, 40);
    }
  }

  //: What a screen reader hears after "Could not take that in". This printed the server's raw
  //: detail, an English sentence with an HTTP status and sometimes a Python class name, or
  //: "[object Object]" for a validation error whose detail is a list. Only a reason the reader can
  //: act on is said; anything else leaves the plain sentence alone.
  function whyNot(err) {
    if (err && err.names) return `${say("island.couldNotRead", "these could not be read")} (${err.names.join(", ")})`;
    if (err instanceof TypeError) return say("island.noServer", "Penumbra is not answering. Right-click here to restart it.");
    if (err && err.status === 413) return say("island.tooBig", "that file is too large");
    if (err && err.status === 401) return say("island.restarted", "Penumbra was just restarted. Drop it again.");
    return "";
  }

  async function capture(item) {
    if (item.files.length) {
      const form = new FormData();
      item.files.forEach((file) => form.append("file", file, file.name));
      const out = await send("/horizon/upload", { method: "POST", body: form });
      const refused = (out.refused || []).length;
      if (refused && !(out.nodes || []).length) {
        const failure = new Error("refused");
        failure.names = out.refused.map((r) => r.filename);
        throw failure;
      }
      return { landed: (out.nodes || []).length, refused };
    }
    const out = await send("/horizon", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls: item.urls, texts: item.texts }),
    });
    return { landed: (out.nodes || []).length, refused: 0 };
  }

  // One pill per thing dropped, starting where it was let go and spiralling into the horizon.
  function fall(names, x, y) {
    const centre = document.querySelector(".core").getBoundingClientRect();
    const cx = centre.left + centre.width / 2;
    const cy = centre.top + centre.height / 2;
    names.slice(0, 6).forEach((name, i) => {
      const mote = document.createElement("span");
      mote.className = "mote";
      mote.dataset.name = name;
      mote.style.setProperty("--cx", `${cx}px`);
      mote.style.setProperty("--cy", `${cy}px`);
      mote.style.setProperty("--dx", `${x - cx + i * 14}px`);
      mote.style.setProperty("--dy", `${y - cy + i * 8}px`);
      mote.style.animationDelay = `${i * 70}ms`;
      motes.appendChild(mote);
      mote.addEventListener("animationend", () => mote.remove());
    });
  }

  // The page must claim the drag or the webview treats a dropped file as a navigation.
  window.addEventListener("dragover", (event) => {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  });

  // The file types the server reads today. Anything else is refused HERE, with a sentence that
  // says so, instead of reaching the server and coming back as a bare "could not take that in".
  // The same list the server accepts (`ingest._ALLOWED_UPLOAD_SUFFIXES`).
  const ACCEPTED = /\.(pdf|txt|md)$/i;

  // **The page decides when the island closes after a drop, not the shell.** The shell used to
  // infer "that was a drop" from the mouse button being released over the island, and during a
  // macOS drag session that state does not reliably follow the drop: the island went back to
  // "armed" and wrote "Let go…" over the result. The page is the one that received the drop.
  const SWALLOW_MIN = 1300;

  function settle(startedAt) {
    const wait = Math.max(0, SWALLOW_MIN - (Date.now() - startedAt));
    setTimeout(() => {
      window.location.href = "/__shell/rest";
    }, wait);
  }

  window.addEventListener("drop", async (event) => {
    event.preventDefault();
    const item = event.dataTransfer && readDrop(event.dataTransfer);
    if (!item) return;
    const startedAt = Date.now();
    window.island.setState("swallow");
    const unsupported = item.files.filter((f) => !ACCEPTED.test(f.name));
    item.files = item.files.filter((f) => ACCEPTED.test(f.name));
    if (unsupported.length && !item.files.length) {
      result("bad");
      announce("island.unsupported", "Only PDF, TXT and Markdown files for now");
      settle(startedAt);
      return;
    }
    fall(item.files.length ? item.files.map((f) => f.name) : item.names, event.clientX, event.clientY);
    // The pull keeps running while the server works, so a slow PDF still looks alive.
    document.body.dataset.busy = "";
    announce("island.swallowing", "Working on it…");
    settle(startedAt);
    try {
      const { landed, refused } = await capture(item);
      // **Nothing chosen may disappear quietly.** A drop of a PDF and a picture used to flash "ok"
      // with the picture silently left out; any refusal, here or by the server, is shown as one.
      const turnedAway = refused + unsupported.length;
      result(turnedAway ? "bad" : "ok");
      announce(
        turnedAway ? "island.partial" : "island.swallowedCount",
        turnedAway ? `${landed} sent into the Horizon, ${turnedAway} could not be read`
          : `${landed} sent into the Horizon`,
        { n: landed, refused: turnedAway }
      );
    } catch (err) {
      result("bad");
      const why = whyNot(err);
      live.textContent = why ? `${say("island.failed", "Could not take that in")}: ${why}` : say("island.failed", "Could not take that in");
    } finally {
      delete document.body.dataset.busy;
    }
  });
})();
