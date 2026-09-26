// penumbra web UI — zero-build vanilla JS, no framework, no build step (see DESIGN.md).
//
// State: a small hand-rolled evented store, not a state-management library. Event vocabulary is
// PINNED (blueprint §3.1) so later phases don't invent an incompatible convention:
//   orbit:switched  { orbitId }
//   sources:changed    { sources }
//   chat:turnAdded     { turn }
//   chat:pending       { pending }
//   notes:changed      { notes }
//   orbit:titled    { title, orbitId }
// Each pane subscribes only to what it renders from; no pane writes another pane's state directly.

function createStore() {
  const listeners = new Map();
  return {
    on(event, handler) {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event).add(handler);
    },
    emit(event, payload) {
      (listeners.get(event) || new Set()).forEach((handler) => handler(payload));
    },
  };
}

const store = createStore();

const state = {
  orbitId: null,
  // The server-side `orbit.slug(id)`, which is what `_derive_run_id` actually prefixes a run id
  // with. Building run ids from the raw id left every trace link dead for `"my orbit"` or any
  // non-Latin id (invariant 10) — found by an independent audit.
  orbitSlug: null,
  title: null,
  overview: null,
  podcast: null,
  //: The Studio guide artifacts, keyed by kind, as `{result, runId}`. On `state` rather than in a
  //: closure inside `initStudioPanel` because the References view has to collect citations from
  //: them: an independent review found every citation in a summary/FAQ/timeline/insight — and in
  //: the podcast transcript — was clickable and led to a References list that structurally could
  //: not contain it. It only LOOKED like it worked when the same `source_id|locator` happened to
  //: be cited in chat too, which for text/web sources (all locator `"whole"`) is most of the time.
  guides: {},
  sources: [],
  turns: [],
  notes: [],
};

// --- Theme ------------------------------------------------------------------------------------

function initTheme() {
  const toggle = document.getElementById("theme-toggle");
  const stored = localStorage.getItem("penumbra-theme");
  if (stored) {
    document.documentElement.setAttribute("data-theme", stored);
  }
  updateToggleGlyph();

  toggle.addEventListener("click", () => {
    const current =
      document.documentElement.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("penumbra-theme", next);
    updateToggleGlyph();
  });
}

function updateToggleGlyph() {
  const toggle = document.getElementById("theme-toggle");
  const current =
    document.documentElement.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  // U+FE0E forces TEXT presentation. Without it macOS draws these from the colour-emoji font,
  // which ignores `color` entirely (so the hover tint did nothing) and renders at its own
  // scale (so the glyph looked small however large `font-size` was). That is the whole
  // explanation for "the icon is still too small and the hover has no effect".
  // GEOMETRIC glyphs (U+25D0/U+25D1), not `☀`/`☾`. Those live in the Miscellaneous Symbols block
  // and macOS draws them from the colour-emoji font, which ignores `color` outright and sizes them
  // itself — the reason two rounds of "the icon is small and the hover does nothing" were about the
  // font, not the CSS. U+FE0E asks for text presentation, but a glyph that was never emoji in the
  // first place is one less thing depending on the platform honouring it. Same family
  // one sibling studio uses (`◐`).
  toggle.textContent = current === "dark" ? "\u25d1" : "\u25d0";
  //: **The glyph is the only thing that said which theme is on.** `aria-label="Toggle theme"` names
  //: the ACTION and never the STATE, so a screen-reader user could not tell Paper from Study — and
  //: the whole product had no `aria-pressed` anywhere. A toggle button is exactly what that
  //: attribute is for; the label stays the action, which is the convention.
  toggle.setAttribute("aria-pressed", current === "dark" ? "true" : "false");
}

// --- API token ----------------------------------------------------------------------------------
//
// Every request this page makes carries the token the server minted (invariant 77; `auth.py` has
// the reasoning — "reachable only from this machine" stopped being the same property as "reachable
// only by this app" once a second client existed). The token arrives exactly once, as `?token=` in
// the URL the server told the user to open, and lives in localStorage from then on.

const API_TOKEN_KEY = "penumbra-api-token";

//: The token for THIS page session. Kept beside localStorage rather than only in it, because a
//: private window or blocked site data makes every storage call throw or return null, and the page
//: still has to work for the session it was opened with.
let apiTokenMemo = "";

function apiToken() {
  if (apiTokenMemo) return apiTokenMemo;
  try {
    return localStorage.getItem(API_TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

//: **The way back IN.** A 401 used to leave the whole application on screen and dead, with the
//: remedy being a sentence telling the reader to hand-edit a URL — and no field anywhere in the
//: product to paste a token into, although `captureApiToken` has always persisted one. The gate
//: replaces the surface and inerts everything behind it, the same treatment the drawer gets.
let tokenGateOpen = false;

function showTokenGate(message) {
  const gate = document.getElementById("token-gate");
  if (!gate || tokenGateOpen) return;
  tokenGateOpen = true;
  gate.hidden = false;
  // The desktop app hands the window its token and prints it nowhere, so "paste the token the
  // server printed" asks for something its reader has never seen. Restarting from the menu mints
  // a new one and reloads the window with it.
  const desktop = isDesktopShell();
  gate.classList.toggle("is-desktop", desktop);
  if (desktop) {
    const menu = menuItems();
    message = t("token.desktop", `This window lost its connection to the server. Choose ${menu.restart} to reconnect.`, menu);
  }
  const error = document.getElementById("token-gate-error");
  if (error) {
    error.hidden = !message;
    error.textContent = message || "";
  }
  inertEverythingExcept(gate, []);
  const field = document.getElementById("token-gate-input");
  if (field) field.focus();
}

function installTokenGate() {
  const form = document.getElementById("token-gate-form");
  if (!form) return;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const field = document.getElementById("token-gate-input");
    const value = (field.value || "").trim();
    if (!value) return;
    apiTokenMemo = value;
    try {
      localStorage.setItem(API_TOKEN_KEY, value);
    } catch {
      // blocked storage — `apiTokenMemo` carries this page session, which is what matters
    }
    //: A RELOAD rather than re-running the failed request: a page that has been sitting on a dead
    //: token has stale everything — the orbit list, the Horizon, the settings — and re-fetching
    //: each of them in the right order from here is a second boot sequence to keep in step with
    //: the first. There is exactly one boot sequence and this is how to run it.
    window.location.reload();
  });
}

function forgetApiToken() {
  apiTokenMemo = "";
  try {
    localStorage.removeItem(API_TOKEN_KEY);
  } catch {
    // blocked storage — the in-memory copy above is already cleared, which is what matters
  }
}

function captureApiToken() {
  // The WHOLE body is guarded. This runs at top level, so anything it throws takes every
  // `init*()` below it down with it and the page renders blank — and not every context that loads
  // this file is a browser: a Node `vm` context has no `URL` global at all (it is a WHATWG
  // addition, not an ECMAScript intrinsic). Failing soft costs the reader one re-opened URL;
  // failing hard costs them the application.
  try {
    const url = new URL(window.location.href);
    // The desktop shell passes both in the FRAGMENT (`#token=…&shell=desktop`), which the browser
    // never sends, so the token stays out of the server's access log. Folded into the query view
    // here and the fragment cleared, so everything below reads one place.
    let rewritten = false;
    if (/^#(token|shell)=/.test(url.hash)) {
      new URLSearchParams(url.hash.slice(1)).forEach((value, key) => url.searchParams.set(key, value));
      url.hash = "";
      rewritten = true;
    }
    // The desktop shell opens the page with `shell=desktop`. Remembered for the session, so a
    // Reload (which no longer has the parameter) still knows, and stripped with the token.
    if (url.searchParams.get("shell") === "desktop") {
      try {
        sessionStorage.setItem("penumbra-shell", "desktop");
      } catch {
        // blocked storage: only the wording of a few error messages depends on this
      }
      url.searchParams.delete("shell");
      rewritten = true;
    }
    const menuLang = url.searchParams.get("menu");
    if (menuLang) {
      if (menuLang === "zh" || menuLang === "en") {
        try {
          sessionStorage.setItem("penumbra-menu", menuLang);
        } catch {
          // blocked storage: menu names then follow the interface language
        }
      }
      url.searchParams.delete("menu");
      rewritten = true;
    }
    const fromUrl = url.searchParams.get("token");
    if (!fromUrl) {
      // Only when something was actually removed: a bare `replaceState` would also wipe the
      // history entry's state, which the orbit router reads on Back.
      if (rewritten) window.history.replaceState(null, "", url.pathname + url.search + url.hash);
      return;
    }
    apiTokenMemo = fromUrl;
    try {
      localStorage.setItem(API_TOKEN_KEY, fromUrl);
    } catch {
      // blocked storage — this page session still works, a reload needs the URL again
    }
    // STRIPPED from the address bar the moment it has been read. A token left in the URL gets
    // bookmarked, pasted into a chat window, and sent as a `Referer` to everything the page links
    // out to. `replaceState`, not `pushState`, so Back cannot walk back onto it either.
    url.searchParams.delete("token");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  } catch {
    // no URL/history/location here — the token simply was not captured, and `api()` will say so
  }
}

captureApiToken();

function withToken(path) {
  // For the URLs the BROWSER fetches on its own rather than through `api()`: `EventSource` and
  // `<audio src>` cannot set request headers at all, so those two carry the token in the query
  // string instead. `auth.py`'s docstring records why that is forced rather than lazy.
  const token = apiToken();
  if (!token) return path;
  const joiner = path.includes("?") ? "&" : "?";
  return `${path}${joiner}token=${encodeURIComponent(token)}`;
}

// --- API helpers --------------------------------------------------------------------------------

async function api(path, options) {
  // Every request carries the interface language the reader PICKED. One choke point rather than a
  // field in five request bodies — `_resolve_language` is reached from every run-taking endpoint,
  // and a header covers them all without a schema change each. See `i18n.js`'s header for why this
  // does not merge the two language settings.
  const opts = { ...(options || {}) };
  opts.headers = { ...(opts.headers || {}), "X-Penumbra-Interface-Language": uiLangName() };
  const token = apiToken();
  if (token) opts.headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(path, opts);
  if (resp.status === 401) {
    // The server mints a fresh token each launch, so a stale one in localStorage is the ordinary
    // case here, not an attack. Drop it — otherwise every later request fails the same way and a
    // reload with a fresh `?token=` would be fighting the stored copy.
    forgetApiToken();
    //: The gate, not just a sentence: every affordance on the page is dead at this point and
    //: leaving them looking live is the lie invariant 60 is about, one layer out from a status line.
    showTokenGate(t("token.bad", "That token was not accepted. Check it is the one this server printed."));
    throw new Error(
      //: It points at the TOKEN, not at a URL: `penumbra serve` prints a token and uvicorn
      //: prints an address, deliberately (an address announced before the bind is one an occupied
      //: port then fails to serve). This used to send the reader to "the URL `penumbra serve`
      //: printed", which is not a thing that exists — at exactly the moment they are locked out.
      t(
        "err.tokenInvalid",
        "API token missing or expired. Open this page again with `?token=` and the token the server printed."
      )
    );
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // response wasn't JSON — keep statusText
    }
    //: **The STATUS travels with the error, not just inside its text.** Callers were branching on
    //: "did this throw", which cannot tell a 404 (this orbit does not exist yet) from a 409 (its
    //: file is corrupted and the server just said how to fix it) or from `fetch` rejecting because
    //: the server is gone. `openOrbit` answered all three by inventing an empty orbit.
    const err = new Error(`${resp.status}: ${detail}`);
    err.status = resp.status;
    throw err;
  }
  return resp.status === 204 ? null : resp.json();
}

// --- Reasoning-trace ticker (Phase 3) --------------------------------------------------------
//
// `ask`, each Guide-tab fetch, and the podcast generate call all pick their OWN run id
// client-side (never trust a server-generated one — it would never reach us until the request
// was already over) and open a live SSE ticker against it before/alongside firing the actual
// request. Reasoning-trace fusion is deliberately a SECONDARY, opt-in layer: the request's own
// response remains the sole source of the final answer/result (unchanged from Phase 1/2) — the
// ticker only replaces static "Thinking…"/"Generating…" copy with live-updating copy, and adds a
// small "view reasoning" affordance afterward. Losing the ticker (a network hiccup, the SSE
// connection dropping) never blocks or breaks the actual request.

//: **`tickerLogs` is GONE, and its comment was the reason to look.** It claimed `openTicker`
//: "RESOLVES with it, which is what the awaiting caller reads" — and no caller reads that
//: resolution: the five call sites are `void`, three bare, and one `.then(() => {})`. So it was a
//: `Map` accumulating every event of every run for the life of the tab, read by nobody, described
//: by a comment that named a consumer which had stopped existing when the "⌁ N steps" pill moved
//: from expanding inline to opening the Trajectory drawer (which fetches its own decomposition
//: from the server). The events themselves are still passed to `onEvent` as they arrive, which is
//: what actually drives the ticker.
//: Kinds that end a stream. Written down once so the ticker, the tests and any later consumer
//: share one answer — adding a terminal kind and missing a call site leaves a stream open forever.
const TERMINAL_KINDS = new Set(["done", "failed", "not_found"]);

//: **Every LIVE stream, so a caller that did not start one can still end it.** `openTicker`
//: returned only a promise and kept `source` in its closure, so there was no way to close a stream
//: early — fine for the four callers that await a request and get a terminal event, and a real leak
//: for `reattachInFlightRuns`, which opens one per RECOVERED run on every orbit open. Measured:
//: six opens and the page could no longer talk to its own server at all (`fetch` stalled past 8s,
//: six established sockets, Chrome's per-origin HTTP/1.1 cap), while `curl` answered in 2ms. A run
//: that outlives a few navigations is not exotic — that is the case the recovery exists for.
const tickerSources = new Map();

//: Idempotent, and safe for a run that was never opened or has already ended: `close()` on a
//: closed `EventSource` is a no-op, and the map entry is what stops a second call finding a
//: stale handle.
function closeTicker(runId, expected) {
  const source = tickerSources.get(runId);
  //: **A TEARDOWN MAY ONLY CLOSE THE STREAM IT OPENED.** `reattachInFlightRuns` mounts afresh on
  //: every orbit open, and its 2.5s poll outlives the mount that started it — so on the second
  //: Horizon↔orbit round trip during a run, the PREVIOUS mount's teardown looked the
  //: run id up, found the NEW mount's stream under it, and closed that: born at t+13324ms, killed
  //: at t+13908ms, 584ms later, with no EventSource ever created again. The row then froze at
  //: "Starting · 1 steps" while the clock and Stop kept running and the run was still alive
  //: server-side. Exactly the inverse of the collision `openTicker` was taught to avoid, through
  //: the same lookup, in the other direction.
  //:
  //: `expected` omitted still means "close whatever is here", which is what `openTicker`'s own
  //: replace and the terminal-event path want.
  if (expected && source !== expected) return;
  tickerSources.delete(runId);
  if (!source) return;
  try {
    source.close();
  } catch {
    /* a torn-down stream is already what we wanted */
  }
}

function openTicker(orbitId, runId, onEvent, onSource) {
  const events = [];
  return new Promise((resolve) => {
    let source;
    try {
      source = new EventSource(
        withToken(
          `/orbits/${encodeURIComponent(orbitId)}/runs/${encodeURIComponent(runId)}/stream`
        )
      );
    } catch {
      resolve(events);
      return;
    }
    // A second ticker for the SAME run id REPLACES the first, and the first is closed rather than
    // dropped. Overwriting the map entry orphaned an `EventSource` whose own `onerror` could no
    // longer find itself in the map (`closeTicker` looks the run up, finds the newer one or
    // nothing, and returns), so it reconnected every few seconds for the life of the tab — the
    // very leak this map was added to stop, re-entering per RUN instead of per orbit open.
    // Reachable by asking in orbit A, navigating away and coming back while it still runs.
    closeTicker(runId);
    tickerSources.set(runId, source);
    // Handed to the caller so a later teardown can prove the stream is still ITS one.
    if (onSource) onSource(source);
    source.onmessage = (message) => {
      let event;
      try {
        event = JSON.parse(message.data);
      } catch {
        return;
      }
      events.push(event);
      onEvent(event);
      // EVERY terminal kind, not just the happy one. `failed` was added when the trace mapping
      // grew a failure headline, and a check that only knew `done` would have left the stream open
      // forever on exactly the runs a user most wants to see end. Caught by a test asserting the
      // old vocabulary, which is the whole reason to pin an event vocabulary in the first place.
      if (TERMINAL_KINDS.has(event.kind)) {
        closeTicker(runId);
        resolve(events);
      }
    };
    source.onerror = () => {
      // A dropped connection ends the TICKER, never the request itself — the POST this ticker is
      // attached to keeps running and its own response is still authoritative.
      closeTicker(runId);
      resolve(events);
    };
  });
}

// A shared "something is running" surface: a pulsing dot, the live action, a ticking elapsed
// counter, and a Stop button. Same shape a sibling project's own live-status strip uses, and it exists
// because of a real report: a generation takes a minute or more, the only feedback was one line of
// text that ended on "finished" and then sat there, so the natural move is to press the button
// again — which strands the first generation behind a staleness guard and looks like nothing
// happened at all.
//
// `runIds` is a LIST because `/overview` fires two runs; cancelling per run id rather than per
// orbit is what makes Stop actually stop everything (see `cancel_run`'s docstring).
// The server's `summary` is an English convenience; `kind` is the stable thing and `detail` is the
// one specific that differs every run. Translating the KIND and keeping the detail verbatim is what
// makes the status line readable in the interface language without inventing a translation for a
// tool name or a model id.
//: The event headlines, in the interface language. The server sends `primary` in English and
//: `detail`/`meta` as the run's own specifics — a headline is a fixed vocabulary worth translating,
//: a piece of the model's reasoning or a tool's name is not.
const TRACE_HEADLINES = {
  Starting: () => t("trace.start", "Starting"),
  Step: () => t("trace.stepBare", "Step"),
  Tool: () => t("trace.tool", "Tool"),
  "Sub-model": () => t("trace.escalation", "Sub-model"),
  Finalising: () => t("trace.final", "Finalising"),
  Result: () => t("trace.result", "Result"),
  Finished: () => t("trace.done", "Finished"),
  Failed: () => t("trace.failed", "Failed"),
};

function traceHeadline(event) {
  const primary = event.primary || "";
  // `Step 3` -> the `Step` headline plus its number, so the count survives translation.
  // Interpolated, not concatenated: a translation that puts the number in the middle ("第 3 步")
  // cannot be produced by gluing a number onto a translated prefix, and the zh-Hant table had
  // duly rendered "第 3" with the counter missing.
  const numbered = primary.match(/^Step (\d+)$/);
  if (numbered) return t("trace.step", `Step ${numbered[1]}`, { n: numbered[1] });
  const known = TRACE_HEADLINES[primary];
  return known ? known() : primary;
}

// One line, the shape `cve-reverser`/`diff-sentry`'s feeds use: a translated headline, the run's own
// specific, and a compact fact. It used to be a fixed sentence per event type with the payload
// thrown away, which is why ours said so much less than theirs.
function traceLabel(event) {
  if (!event) return "";
  if (event.kind === "not_found") return t("trace.notFound", "No live progress for this run");
  // A kind with no headline at all (an event type this build has no name for): keep whatever is on
  // screen rather than overwriting a meaningful line with an internal event name — which is how
  // `run_start` once reached a user's screen as the literal string `run_start`.
  if (event.kind === "other" && !event.primary) return "";
  const parts = [traceHeadline(event)];
  //: A FAILED event's detail is the server's exception, not the model's words. Every other kind's
  //: detail is the model speaking and goes through verbatim (invariant 52) - but this one arrived
  //: as `LMInvalidRequestError('[openai/gpt-4o-mini] litellm.BadRequestError: …')`, so the live
  //: ticker printed a Python class the chat bubble beside it had already been taught not to. Same
  //: sentence, two surfaces, one of them cleaned.
  const detail = event.kind === "failed" ? readableError(event.detail) : event.detail;
  if (detail) parts.push(detail);
  return parts.filter(Boolean).join(" \u00b7 ");
}

//: orbit id -> how many runs this TAB currently has in flight against it. Answers "which
//: orbit is generating" in the picker, which is otherwise unknowable once you switch away.
//:
//: Client-side on purpose, and honest about its limit: it counts runs THIS tab started. A run
//: started in another tab (or before a reload) is invisible here. The server's own registries are
//: single-process, in-memory maps (invariant 23) with no endpoint to read them, and adding one is
//: a bigger change than the question needs.
const activeRuns = new Map();

function noteRunStarted(orbitId) {
  activeRuns.set(orbitId, (activeRuns.get(orbitId) || 0) + 1);
  store.emit("runs:changed", { activeRuns });
  syncRunGuards();
}

//: **A guard that survives a RELOAD, because the per-action ones do not.**
//:
//: Every artifact-generating control disables itself while its own run is in flight — and that
//: flag lives in this tab's memory. After F5 the worker is still going (invariant 21: it is a
//: subprocess and outlives the page), `reattachInFlightRuns` correctly puts the indicator and its
//: Stop back, and every start control comes back LIVE. One press of Generate podcast then bought a
//: SECOND worker: measured as two run ids, two `penumbra.worker` processes and two status rows
//: counting in parallel, with nothing said. On a BYOK tool that is the reader's money, twice, for
//: one press — and it is verbatim the failure `reattachInFlightRuns`' own comment says it exists to
//: prevent ("asking again simply started a SECOND run on the same orbit").
//:
//: Driven off `activeRuns`, which `runStatus` already maintains for the header dot, so a recovered
//: run counts exactly like one this tab started. It covers the other direction too: invariant 23
//: gives `_ACTIVE_RUNS` ONE SLOT PER ORBIT, so a second run started on top of a first already
//: loses the first's cancel handle server-side.
//:
//: NOT the composer — IN THIS TAB. Asking while an artifact generates is a reasonable thing to
//: want, the pending turn is its own guard, and taking the product's primary verb away over a
//: background podcast would be a worse lie than the one this fixes.
//:
//: **AFTER A RELOAD that exemption's reason is exactly what is missing.** A new tab has no pending
//: turn, so `#ask-submit` went live the instant you typed and the last turn's `↻ Regenerate` was
//: live too, each issuing a real `POST /ask` with a fresh run id — a second billed worker on the
//: same orbit. And `_run_isolated` overwrites the one slot `_ACTIVE_RUNS` keeps per orbit
//: (invariant 23), so Stop then reaches only the second and the first cannot be stopped at all.
//: Scoped to RECOVERED runs, so the argued exemption survives for the case it was argued about.
//: The controls that START an expensive artifact, and only those. `.chat-starter button` covers
//: both the chat overview's opener and the Studio's guide offer, which share that wrapper.
//: Deliberately NOT `.studio-view button.btn`, which also matches Add note — a control with its own
//: empty-field rule, and one this guard has no business touching.
const RUN_GUARDED = "#podcast-generate, #guide-regenerate, .chat-starter button";
const RUN_GUARDED_ON_RECOVERY = "#ask-submit, .turn-regenerate button";

//: Orbits with a run this tab did not start. `reattachInFlightRuns` adds; its single
//: `stopWatching` teardown removes — Stop, the poll and an orbit switch all go through that one
//: path, because a second teardown is how the first one's bookkeeping gets missed.
const recoveredRuns = new Map(); // orbit id -> the mount that owns the flag

//: **May a new question start right now?** ONE answer, asked by every path that can send: the
//: send button's own state (`autoGrow`) and the submit handler (which Enter goes through). Each used
//: to decide on its own, so a repaint (`sources:changed` runs `autoGrow`) re-enabled Send while a
//: chat or overview run held the composer, and Enter submitted past the recovery guard — both
//: starting a second paid question, one of which then had no Stop anywhere.
let composerHeld = false; // a chat question or the overview owns the composer (`chat:pending`)
//: The recovered run's status row while one is on screen; `rebuildHistory` re-attaches it.
let recoveredRow = null;
function composerLocked() {
  return composerHeld || recoveredRuns.has(state.orbitId);
}

function syncRunGuards() {
  const busy = activeRuns.has(state.orbitId);
  const recovered = recoveredRuns.has(state.orbitId);
  //: Marking reads the narrow set; RELEASING always sweeps both, or a composer guarded during a
  //: recovered run would stay disabled once the recovery flag is gone.
  const selector =
    busy && !recovered ? RUN_GUARDED : `${RUN_GUARDED}, ${RUN_GUARDED_ON_RECOVERY}`;
  //: The SELECTOR decides which controls are in scope; the branch below only decides mark-or-
  //: release. An earlier version also re-tested `control.matches(RUN_GUARDED_ON_RECOVERY)` here,
  //: which could never change an outcome — the narrow selector is used exactly when `recovered` is
  //: false — and redundant logic that looks load-bearing is a liability in a guard this small.
  document.querySelectorAll(selector).forEach((control) => {
    if (busy) {
      // **Only mark what THIS guard disables.** Marking a control another flow had already
      // disabled - Add note over an empty field, a button mid-submit - meant releasing the guard
      // re-enabled it, handing back a button that should still have been off.
      if (control.disabled) return;
      control.disabled = true;
      control.dataset.runGuarded = "1";
      control.dataset.tip = t("run.alreadyRunning", "Something is already running in this orbit.");
    } else if (control.dataset.runGuarded) {
      delete control.dataset.runGuarded;
      // **RESTORED, not deleted.** Two of these carry an author `data-tip` that `applyStaticI18n`
      // already translated at boot, and that function runs only at boot and on a language change -
      // so deleting the key left the control with NO tooltip for the rest of the session, after a
      // run it had nothing to do with. `i18nTipSource` is where the original is kept.
      const original = control.dataset.i18nTip
        ? t(control.dataset.i18nTip, control.dataset.i18nTipSource || "")
        : control.dataset.i18nTipSource;
      if (original) control.dataset.tip = original;
      else delete control.dataset.tip;
      control.disabled = false;
    }
  });
}

function noteRunFinished(orbitId) {
  const left = (activeRuns.get(orbitId) || 1) - 1;
  if (left > 0) activeRuns.set(orbitId, left);
  else activeRuns.delete(orbitId);
  store.emit("runs:changed", { activeRuns });
  syncRunGuards();
}

//: How long a single step may go without news before the wait itself becomes the message. Long
//: enough that an ordinary step never trips it, short enough to answer "is it stuck" before someone
//: has to ask. A model's FIRST response on the Claude-subscription path was measured at four
//: minutes, which is the case this exists for.
const WAITING_AFTER_SECONDS = 20;
//: When "waiting for the model's first response" has itself stopped being news. A user watched that
//: phrase for seven minutes on a subscription model and reported it as looking like a crash.
const LONG_WAIT_AFTER_SECONDS = 90;

//: The next sensible control in the panel a run was stopped in: the composer in Chat; in the Studio
//: the starter or ↻ Regenerate that the stop just brought back, else the selected tab.
function focusAfterStop(home) {
  const current = document.activeElement;
  if (current && current !== document.body && current.isConnected) return; // already placed
  const usable = (el) => el && !el.disabled && !el.hidden && el.getClientRects().length;
  const candidates = home && home.id === "col-chat"
    ? [document.getElementById("ask-input"), home.querySelector(".chat-starter button")]
    : [
        home && home.querySelector("#guide-body .chat-starter button, #podcast-generate"),
        document.getElementById("guide-regenerate"),
        home && home.querySelector('[role="tab"][aria-selected="true"]'),
      ];
  const target = candidates.find(usable);
  if (target) target.focus();
}

function runStatus({ orbitId, runIds, label, onCancel }) {
  noteRunStarted(orbitId);
  const node = document.createElement("div");
  node.className = "run-status";

  const dot = document.createElement("span");
  dot.className = "run-dot";
  node.appendChild(dot);

  const text = document.createElement("span");
  text.className = "run-text";
  text.textContent = label;
  node.appendChild(text);

  const elapsed = document.createElement("span");
  elapsed.className = "run-elapsed";
  elapsed.textContent = "0:00";
  node.appendChild(elapsed);

  const stop = document.createElement("button");
  stop.type = "button";
  stop.className = "btn run-stop";
  i18nText(stop, "run.stop", "\u23f9 Stop");
  node.appendChild(stop);

  // The step list still exists — it is what counts the steps for the pill and what tracks which
  // one is current — but it is NEVER shown inside the chat any more. It is built detached and the
  // pill opens the Trajectory drawer instead. Keeping the element (rather than only a counter) is
  // what lets the live "current step" logic below stay exactly as it was.
  const log = document.createElement("div");
  log.className = "run-log";
  log.hidden = true;

  const logToggle = document.createElement("button");
  logToggle.type = "button";
  logToggle.className = "run-log-toggle";
  logToggle.hidden = true;
  // Opens the Trajectory drawer for THIS run rather than unfolding the log in place. The inline
  // version put the planner's own reasoning prose inside the chat bubble, which a user reported as
  // unreadable and space-consuming; the drawer is the same information somewhere a reader opts
  // into, with the tool calls and the real per-turn timing the inline log never had.
  logToggle.addEventListener("click", () => openTrajectory(runIds));

  //: When the previous step landed, so each row can show how long IT took rather than only when it
  //: started. "Where is it stuck" is a question about durations, and a column of absolute stamps
  //: makes the reader subtract.
  let lastStepAt = null;

  function appendLog(event) {
    const headline = traceHeadline(event);
    if (!headline) return;
    const now = Date.now();
    const line = document.createElement("div");
    line.className = `run-log-line kind-${event.kind || "other"}`;

    // Only the newest step is "current": it carries the pulsing node on the rail and shows its
    // detail in full, while everything above it collapses to a clamped line. The shape Cursor and
    // Devin both use for an agent's step list, and the reason is the same — a finished step is a
    // record, the running one is the thing you are watching.
    const previous = log.lastElementChild;
    if (previous) {
      previous.classList.remove("is-current");
      previous.classList.add("is-past");
    }
    line.classList.add("is-current");

    const at = document.createElement("span");
    at.className = "run-log-at";
    at.textContent = formatTimecode((now - started) / 1000);
    line.appendChild(at);

    // VISIBLE, not a tooltip. It was `data-tip` on this element, which lives inside `.run-log`'s
    // own scroller — an independent review measured the tip clipped by that box, the ancestor case
    // `test_no_tooltip_host_clips_its_own_tooltip` states it cannot see. Text needs no hover, works
    // on touch, and can be copied.
    //
    // Measured from `started` for the FIRST row rather than skipped: that gap is the wait for the
    // model's first response, which is the slow one the status line already singles out.
    const gap = (now - (lastStepAt === null ? started : lastStepAt)) / 1000;
    const took = document.createElement("span");
    took.className = "run-log-took";
    // One decimal below ten seconds: most steps in a fast run are sub-second, and `+0s` on every
    // row says nothing at all.
    took.textContent = `+${gap < 10 ? gap.toFixed(1) : Math.round(gap)}s`;
    line.appendChild(took);
    lastStepAt = now;

    const what = document.createElement("span");
    what.className = "run-log-what";
    const primary = document.createElement("b");
    primary.textContent = headline;
    what.appendChild(primary);
    if (event.meta) {
      // Inside `what`, immediately after the label. It used to be a third grid column pinned to the
      // right edge, which on a wide panel left a hand's width of empty box between "啟動" and
      // "GenerateSummary" and read as a broken layout rather than as one log line.
      const meta = document.createElement("span");
      meta.className = "run-log-meta";
      meta.textContent = event.meta;
      what.appendChild(meta);
    }
    if (event.detail) {
      // The model's own words. This is the part that makes the log worth opening — and the part
      // the previous version discarded entirely.
      //
      // Named `reasoningText`, not `detail`: the hidden-toggle tripwire matches variable names
      // across the whole file, and a `detail` here collides with the reference panel's own
      // `detail.hidden = …`. It fails loudly, which is the safe direction — so the fix is the name.
      const reasoningText = document.createElement("span");
      reasoningText.className = "run-log-detail";
      // Same split as `traceLabel`: a failed event's detail is the server's exception, everything
      // else is the model's own words and goes through untouched (invariant 52).
      reasoningText.textContent =
        event.kind === "failed" ? readableError(event.detail) : event.detail;
      what.appendChild(reasoningText);
    }
    line.appendChild(what);
    // A past step opens on click. The detail is clamped rather than dropped, so the log stays
    // readable while a long run accumulates steps and nothing is actually lost.
    if (event.detail) {
      line.classList.add("is-expandable");
      line.addEventListener("click", () => line.classList.toggle("is-expanded"));
    }
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
    logToggle.hidden = false;
    const steps = log.children.length;
    logToggle.textContent = t("run.logToggle", `${steps} ${steps === 1 ? "step" : "steps"}`, { n: steps });
  }

  // A typed COUNT per kind of work, not a scrolling log. A sibling project settled on this shape
  // and its own comment says why the framing matters: a raw count climbing forever reads as
  // runaway, while a small set of named counters reads as progress. Three kinds is all our trace
  // has (`_translate_trace_event`), and three is about the ceiling before a status line becomes
  // noise — the thing the user asked to avoid.
  const counts = { tool: 0, escalation: 0 };
  const meter = document.createElement("span");
  meter.className = "run-meter";
  meter.hidden = true;
  node.appendChild(meter);

  // No `thinking` cell: the log toggle right below already says "N steps", and two counters one
  // line apart saying the same number reads as a bug. These are the kinds a step count does NOT
  // cover.
  const COUNT_LABELS = {
    tool: () => t("run.count.tool", "tools"),
    escalation: () => t("run.count.escalation", "sub-model"),
  };

  function renderMeter() {
    meter.textContent = "";
    let any = false;
    Object.entries(counts).forEach(([kind, n]) => {
      if (!n) return;  // a kind that has not happened is not information, it is clutter
      any = true;
      const cell = document.createElement("span");
      cell.className = "run-count";
      const num = document.createElement("b");
      num.textContent = String(n);
      cell.appendChild(num);
      cell.appendChild(document.createTextNode(" " + COUNT_LABELS[kind]()));
      meter.appendChild(cell);
    });
    meter.hidden = !any;
  }

  const started = Date.now();
  node.appendChild(logToggle);
  // NOT appended. `log` stays detached — it is the step bookkeeping, not a panel. Appending it is
  // what put the model's reasoning prose in the chat bubble; the pill above opens the drawer.

  // "Is it stuck?" — a user had to ask, and the honest answer was no: the run finished fine, but
  // the model's FIRST response took four minutes and the trace has nothing to emit until a step
  // completes, so the panel looked identical to a hang for four minutes.
  //
  // The interface has to answer that question itself, and the only fact it has is how long the
  // current step has been running. Below the threshold this says nothing (a step taking six
  // seconds is not news); above it, the wait becomes the message.
  let lastEventAt = started;
  let currentPhrase = label;
  let stepsSeen = 0;
  //: Whether we are still waiting on the model's FIRST reply. Separate from `stepsSeen` because
  //: `setPhase` moves the run to a stage the trace cannot see, where "waiting for the model's first
  //: response" is simply false — and `paint`'s pre-first-step branch REPLACES the phrase rather
  //: than appending to it, so a phase set at second 0 was silently gone by second 20. An
  //: independent review measured it: 26s in, a podcast mid-SYNTHESIS said it was waiting for a
  //: model, and at 2:02 the long-wait tier told the reader Stop was available while Stop was
  //: greyed out — reintroducing, in the same diff, the exact complaint that tier was added for.
  let awaitingFirstReply = true;

  function paint() {
    elapsed.textContent = formatTimecode((Date.now() - started) / 1000);
    const waiting = (Date.now() - lastEventAt) / 1000;
    if (waiting < WAITING_AFTER_SECONDS) {
      text.textContent = currentPhrase;
      node.classList.remove("is-waiting");
      return;
    }
    node.classList.add("is-waiting");
    // BEFORE the first step, "waiting" says nothing a reader did not already know — that stage IS
    // waiting. What they cannot see is WHAT it is waiting for, and that the first model response
    // is the slow one. After a step has landed, the elapsed time is the information: it is the
    // difference between a slow step and a stuck one.
    if (!awaitingFirstReply) {
      text.textContent = `${currentPhrase} \u00b7 ${t("run.waiting", `waiting ${formatTimecode(waiting)}`, { time: formatTimecode(waiting) })}`;
    } else if (waiting < LONG_WAIT_AFTER_SECONDS) {
      text.textContent = t("run.awaitingModel", `waiting for the model's first response \u00b7 ${formatTimecode(waiting)}`, { time: formatTimecode(waiting) });
    } else {
      // A SECOND tier, because the first stopped being informative: a user watched "waiting for the
      // model's first response" for seven minutes and read it as a crash. Nothing more CAN be
      // observed — no trace event exists until the model replies — so the honest move is to say
      // that, and point at Stop, rather than repeat a phrase that has already failed to reassure.
      text.textContent = t(
        "run.awaitingModelLong",
        `still waiting for the model's first response \u00b7 ${formatTimecode(waiting)} \u00b7 nothing is reported until it replies; Stop is available`,
        { time: formatTimecode(waiting) },
      );
    }
  }

  const timer = setInterval(paint, 1000);

  let stopped = false;
  function finish() {
    if (stopped) return;
    stopped = true;
    clearInterval(timer);
    node.classList.add("is-done");
    // Nothing is "current" once the run is over. Without this the last step kept its pulsing rail
    // node and its 12-line detail while the header already said Finished — a status line and a log
    // disagreeing about whether anything is still happening.
    const current = log.querySelector(".run-log-line.is-current");
    if (current) {
      current.classList.remove("is-current");
      current.classList.add("is-past");
    }
    noteRunFinished(orbitId);
  }

  stop.addEventListener("click", async () => {
    //: **Where focus goes after Stop.** Disabling the focused button drops focus to `<body>`, and
    //: the row that held it is then removed — so a keyboard reader lost their place on every Stop.
    //: Remembered BEFORE either happens; handed on once the panel has re-rendered.
    const hadFocus = document.activeElement === stop;
    const home = node.closest(".col");
    stop.disabled = true;
    text.textContent = t("run.stopping", "Stopping\u2026");
    // Cancel every run this action started, not "whatever this orbit is doing" — an orbit-
    // scoped cancel would leave `/overview`'s second run burning a model call to completion.
    // The REPLIES are read, not discarded. `finish()` used to be called unconditionally, so the
    // page declared the run over whatever the server said - including the case where the server
    // could not reach it. A status line may not claim something the page is not doing (invariant
    // 60), and "stopped" is the loudest claim this component makes.
    const replies = await Promise.all(
      runIds.map((runId) =>
        api(
          `/orbits/${encodeURIComponent(orbitId)}/runs/${encodeURIComponent(runId)}/cancel`,
          { method: "POST" }
        ).catch((err) => ({ error: err.message }))
      )
    );
    const missed = replies.filter((reply) => reply && (reply.error || reply.cancelled === null));
    if (missed.length) {
      // It is still RUNNING as far as anyone here knows. Re-enable the control rather than
      // pretending, and say so once.
      stop.disabled = false;
      text.textContent = currentPhrase;
      if (hadFocus) stop.focus();
      notify(t("run.stopFailed", "Could not stop that run. It may still be going."));
      return;
    }
    finish();
    if (onCancel) onCancel();
    if (hadFocus) queueMicrotask(() => focusAfterStop(home));
  });

  return {
    node,
    //: Rename the phase mid-run, for an action whose later stages the trace cannot see — the
    //: podcast's synthesis half is the only one today. `stoppable: false` DISABLES Stop rather than
    //: hiding it, so the control does not vanish out from under a pointer.
    setPhase(phrase, { stoppable = true } = {}) {
      if (stopped) return;
      currentPhrase = phrase;
      lastEventAt = Date.now();
      // NOT waiting on a first reply any more: this names a stage the trace cannot see.
      awaitingFirstReply = false;
      stop.disabled = !stoppable;
      // Cleared as well as set — otherwise a later stoppable phase re-enables the button while
      // leaving "this stage cannot be interrupted" hanging on it.
      if (stoppable) delete stop.dataset.tip;
      else stop.dataset.tip = t("run.notStoppable", "This stage cannot be interrupted.");
      paint();
    },
    // The whole event, not just its text: the KIND is what the counters are made of, and the
    // summary alone threw it away.
    onEvent(event) {
      if (stopped || !event) return;
      awaitingFirstReply = false;
      if (counts[event.kind] !== undefined) {
        counts[event.kind] += 1;
        renderMeter();
      }
      if (event.kind === "thinking") stepsSeen += 1;
      const phrase = traceLabel(event);
      if (phrase) {
        currentPhrase = phrase;
        lastEventAt = Date.now();
        paint();
        appendLog(event);
      }
    },
    setSummary(summary) {
      if (stopped || !summary) return;
      currentPhrase = summary;
      lastEventAt = Date.now();
      paint();
    },
    finish,
  };
}

function renderTickerAffordance(runId) {
  // The PERSISTED "⌁ N steps" pill under a finished artifact — a chat answer, the overview, a Guide
  // result, the podcast. Distinct from `runStatus`'s LIVE log, which is why moving that one into the
  // Trajectory drawer left this one still expanding the model's reasoning prose inline: a user hard-
  // reloaded, pressed it, and reported the drawer as still missing. It was a different component,
  // and the first diagnosis (a stale cached `app.js`) was wrong.
  //
  // Both open the drawer now. `runId` is all `openTrajectory` needs, and the drawer shows strictly
  // more than this ever did: the code each turn ran, the tool calls, real per-turn timing, search
  // and replay — against the same trace file this used to page through as flat rows.
  const wrapper = document.createElement("div");
  wrapper.className = "ticker-affordance";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "ticker-toggle trace-face";
  i18nText(toggle, "err.stepsLoad", "Steps");
  i18nTip(toggle, "traj.open", "Open the run's trajectory");
  // **An affordance whose only possible outcome is an apology is not an affordance.** This pill was
  // rendered unconditionally, so a run that FAILED before producing a trace still offered it - and
  // pressing it raised a native `alert()` carrying a raw run UUID. Two independent reviews found
  // the same thing, and the fix is not a better dialog: a control that cannot do its job should
  // stop claiming it can. `openTrajectory` reports whether a trajectory was there, and on a miss
  // the pill RETIRES in place - dimmed, disabled, saying so - instead of interrupting the reader.
  // It corrects itself on the first press rather than on every press.
  toggle.addEventListener("click", async () => {
    // Already retired: there is nothing to open, and `aria-disabled` does not stop a click.
    if (toggle.classList.contains("is-absent")) return;
    toggle.disabled = true;
    const opened = await openTrajectory([runId]);
    if (opened) {
      toggle.disabled = false;
      return;
    }
    //: **`aria-disabled`, not `disabled`, and the difference is where the reader is standing.**
    //: A real `disabled` blurs the focused element, so pressing this with the keyboard dropped
    //: focus to `<body>` and the next Tab restarted at the skip link — the same mechanism round ten
    //: fixed for the drawer, which the test shim models for `hidden` and not for `disabled`. The
    //: button stays focusable and inert: the click handler above already returns early because
    //: `is-absent` means there is nothing to open.
    toggle.disabled = false;
    toggle.setAttribute("aria-disabled", "true");
    toggle.classList.add("is-absent");
    //: A `role="status"` so the sentence is ANNOUNCED. The pill changing its own label is a visual
    //: event; without a live region a screen-reader user presses a button and is told nothing.
    toggle.setAttribute("role", "status");
    i18nText(toggle, "traj.none", "This run left no trace.");
    // All three, or the next language switch would put the tip back on a pill with nothing to open.
    delete toggle.dataset.tip;
    delete toggle.dataset.i18nTip;
    delete toggle.dataset.i18nTipSource;
  });

  wrapper.appendChild(toggle);
  return wrapper;
}

// above. Opened from a citation's list row (always) or a Sources-panel list item (no highlight
// target). Each open aborts any still-in-flight fetch from a PREVIOUS open, so a slower first
// response can never overwrite a faster second one's render — the same class of defect an audit
// once found in the (since-removed) citation-turn panel, guarded against here from the start with
// an AbortController instead, this fetch being worth cancelling at the network level.
let sourceViewerAbort = null;

function closeSourceViewer() {
  const overlay = document.getElementById("source-viewer-overlay");
  // `closeModal` rather than a bare `hidden = true`: it is also what lifts `inert` off the page
  // behind the scrim and returns focus to whatever opened this. See `openModal`.
  if (!overlay.hidden) closeModal(overlay);
  if (sourceViewerAbort) {
    sourceViewerAbort.abort();
    sourceViewerAbort = null;
  }
}

// Highlights AT MOST one quote inside one block's text — deliberately simpler than
// renderAnswerWithCitations's multi-citation overlap handling, since a source block only ever
// needs one highlight per viewer open.
function renderTextWithOptionalHighlight(text, quote) {
  const container = document.createElement("div");
  container.className = "source-block-text";
  if (!quote) {
    container.textContent = text;
    return container;
  }
  const at = text.indexOf(quote);
  if (at === -1) {
    container.textContent = text;
    return container;
  }
  container.appendChild(document.createTextNode(text.slice(0, at)));
  //: `source-quote`, NOT `citation`: a stroke in an answer rests UNMARKED (just its number) and
  //: washes on hover, and this span borrowed that class — so the one thing the reader opened the
  //: source to find, the cited words, was invisible unless the pointer happened to rest on them.
  //: The product's verification loop is "open the citation, see the passage highlighted".
  const mark = document.createElement("mark");
  mark.className = "source-quote";
  mark.textContent = text.slice(at, at + quote.length);
  container.appendChild(mark);
  container.appendChild(document.createTextNode(text.slice(at + quote.length)));
  return container;
}

// A source's ORIGIN is a machine string: a URL, or `pasted:<first words>#<hash>` for pasted text.
// Showing it raw as the modal's title produced the thing a user called too rough — a header reading
// `text · pasted:Voyager 1 launched on September 5, 1977. Voyager 2 launched #b2ad719a`.
//: English plurals, for the ENGLISH FALLBACKS only. The zh-Hant table has no plural form and needs
//: none, so this never touches a translated string - it fixes "1 sources \u00b7 0 turns" in the orbit
//: picker and "1 blocks \u00b7 189 characters" in the source viewer, both of which every reader opens.
function plural(n, word) {
  return `${Number(n).toLocaleString()} ${word}${Number(n) === 1 ? "" : "s"}`;
}

// **The server speaks English; the interface may not.** Injection-scan flags and a citation's
// "why unverified" reason are English sentences built on the server, so a zh-Hant reader got an
// English line inside a Chinese card. Each known sentence maps to a key; anything unrecognised is
// shown as the server wrote it, which is still true, only untranslated.
//
// Keyed on the EXACT flag text `injection_scan.py` emits. `tests/test_server_sentences.py` checks that
// every description there has an entry here, so a new pattern cannot ship untranslated silently.
const FLAG_KEYS = {
  "text telling a model to ignore its instructions": [
    "flag.ignoreInstructions", "text telling a model to ignore its instructions"],
  "text trying to reassign the model's role": ["flag.reassignRole", "text trying to reassign the model's role"],
  "a chat role label (System:/User:/Assistant:) opening a line": [
    "flag.roleLabel", "a chat role label (System:/User:/Assistant:) opening a line"],
  "text telling a model to disregard its rules": [
    "flag.disregardRules", "text telling a model to disregard its rules"],
  "text asking a model to reveal its prompt or credentials": [
    "flag.revealSecrets", "text asking a model to reveal its prompt or credentials"],
  "a long run of base64-like characters (possibly an encoded payload)": [
    "flag.base64", "a long run of base64-like characters (possibly an encoded payload)"],
};

function readableFlag(flag) {
  const known = FLAG_KEYS[flag];
  return known ? t(known[0], known[1]) : flag;
}

// The two shapes `citations.verify_citations` writes. Python's repr quotes with single quotes, and the list
// of known locators can run to hundreds of pages, so only the first few are named.
function readableReason(reason, name) {
  const text = String(reason || "");
  const unquote = (v) => v.replace(/^['"]|['"]$/g, "");
  let m = text.match(/^no source with id (.+) in this orbit$/);
  if (m) {
    const id = name || unquote(m[1]);
    return t("cite.reasonNoSource", `There is no source ${id} in this orbit. It may have been removed.`, { id });
  }
  m = text.match(/^source (.+) has no block at locator (.+); known locators: \[(.*)\]$/);
  if (m) {
    const id = name || unquote(m[1]);
    const locator = unquote(m[2]);
    const all = m[3].split(",").map((v) => unquote(v.trim())).filter(Boolean);
    const shown = all.slice(0, 6).join(", ") + (all.length > 6 ? ", …" : "");
    // `whole` is the coordinate for a one-block source; "has no whole" reads as a typo.
    if (locator === "whole") {
      return t("cite.reasonNoWhole", `${id} is split into parts, so a citation has to name one: ${shown}.`, {
        id, known: shown,
      });
    }
    return t("cite.reasonNoBlock", `Source ${id} has no ${locator}. It has: ${shown}.`, {
      id, locator, known: shown,
    });
  }
  return text;
}

// A source's KIND as a reader-facing word. The values are the schema's (`web`, `pdf`, `text`,
// `youtube`), which read as code in a Chinese interface; an unknown kind shows as stored.
function kindLabel(kind) {
  const labels = { web: "web", pdf: "pdf", text: "text", youtube: "youtube" };
  return kind in labels ? t(`kind.${kind}`, labels[kind]) : kind;
}

// **A label drawn by a renderer that a language switch does not re-run.** `applyStaticI18n`
// re-translates anything carrying `data-i18n`, so tagging the element with its key and its ENGLISH
// source is enough; the source must be the English text, not whatever `t()` returned, or switching
// back to English would fall back to the Chinese. The steps pill and the "audio is gone" line kept
// their first language until the next repaint that happened to rebuild them.
function i18nText(el, key, fallback, vars) {
  el.textContent = t(key, fallback, vars);
  if (!vars) {
    el.dataset.i18n = key;
    el.dataset.i18nSource = fallback;
  }
  return el;
}

function i18nTip(el, key, fallback) {
  el.dataset.tip = t(key, fallback);
  el.dataset.i18nTip = key;
  el.dataset.i18nTipSource = fallback;
  return el;
}

function sourceDisplayName(source) {
  //: **The scraped TITLE first, because that is the source's name.** This returned the host, so the
  //: one human-readable identifier the product has — the thing the Horizon's whole "if recall cannot
  //: be visual it has to be typographic" thesis rests on — appeared nowhere a reader could get at
  //: it: `.src-title` is line-clamped with no tooltip, the row's `aria-label` said "Open arxiv.org"
  //: and OVERRODE its own content so a screen reader never heard the title at all, and the source
  //: viewer headed itself with the host. Three surfaces, one cause.
  const previewTitle = (source.preview && source.preview.title || "").trim();
  if (previewTitle) return previewTitle;
  const origin = source.origin || "";
  if (origin.startsWith("pasted:")) {
    // Everything between the marker and the content hash IS the readable snippet `ingest_pasted_
    // text` deliberately puts there (invariant 30 — a bare hash was found to be a real regression).
    // Through `pastedExcerpt`, which is the helper that exists to MARK this cut. This call site
    // did its own slicing and returned the raw 60 characters, so the source viewer's heading read
    // "Christopher Alexander, A Pattern Language: each pattern desc" in 17px bold - with the whole
    // text four lines below it saying "each pattern describes a problem", so the reader could see
    // the title was a mutilation.
    return pastedExcerpt(origin) || t("source.pasted", "Pasted text");
  }
  try {
    const url = new URL(origin);
    // The host is what identifies a page at a glance; the path is detail, and it belongs in the
    // metadata rows below rather than in the title.
    return url.hostname.replace(/^www\./, "");
  } catch {
    return origin;
  }
}

// The metadata block above the text: what this source IS, where it came from, and how big it is.
// Every value goes in through `textContent` — an origin can carry attacker-supplied text from a
// page that was fetched (invariants 6 and 29).
function renderSourceMeta(source) {
  const meta = document.createElement("dl");
  meta.className = "source-meta";

  const rows = [];
  rows.push([t("source.kind", "Kind"), String(source.kind || "").toUpperCase()]);

  const origin = source.origin || "";
  if (/^https?:\/\//.test(origin)) {
    rows.push([t("source.url", "Address"), origin, origin]);
  } else if (origin.startsWith("pasted:")) {
    rows.push([t("source.origin", "Origin"), t("source.pastedIn", "Pasted into this orbit")]);
  } else {
    rows.push([t("source.origin", "Origin"), origin]);
  }

  const chars = (source.blocks || []).reduce((n, b) => n + (b.text ? b.text.length : 0), 0);
  rows.push([
    t("source.size", "Size"),
    t("source.sizeValue", `${plural(source.blocks.length, "block")} · ${plural(chars, "character")}`, {
      blocks: source.blocks.length,
      chars: chars.toLocaleString(),
    }),
  ]);

  if (source.flags && source.flags.length) {
    rows.push([t("source.flags", "Flagged"), source.flags.map(readableFlag).join("; ")]);
  }

  rows.forEach(([term, value, href]) => {
    const dt = document.createElement("dt");
    dt.textContent = term;
    meta.appendChild(dt);
    const dd = document.createElement("dd");
    if (href) {
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = value;
      dd.appendChild(link);
    } else {
      dd.textContent = value;
    }
    meta.appendChild(dd);
  });

  return meta;
}

async function showSourceViewer(sourceId, locator, quote) {
  if (sourceViewerAbort) sourceViewerAbort.abort();
  const controller = new AbortController();
  sourceViewerAbort = controller;

  const overlay = document.getElementById("source-viewer-overlay");
  const title = document.getElementById("source-viewer-title");
  const body = document.getElementById("source-viewer-body");
  if (overlay.hidden) openModal(overlay);
  // The row that was clicked already knows the source's name, so the heading never flashes the
  // bare id while the text loads.
  const known = (state.sources || []).find((s) => s.id === sourceId);
  title.textContent = known ? sourceDisplayName(known) : sourceId;
  body.textContent = t("cite.loading", "Loading…");

  try {
    const source = await api(
      `/orbits/${encodeURIComponent(state.orbitId)}/sources/${encodeURIComponent(sourceId)}`,
      { signal: controller.signal }
    );
    if (controller.signal.aborted) return;
    title.textContent = sourceDisplayName(source);
    body.innerHTML = "";
    body.appendChild(renderSourceMeta(source));
    let targetSection = null;
    source.blocks.forEach((block) => {
      const section = document.createElement("div");
      section.className = "source-block";
      const label = document.createElement("div");
      label.className = "source-block-locator";
      label.textContent = block.locator;
      section.appendChild(label);
      const matches = locator && block.locator === locator;
      section.appendChild(renderTextWithOptionalHighlight(block.text, matches ? quote : null));
      body.appendChild(section);
      if (matches) targetSection = section;
    });
    // The quote itself when there is one: a long block centred by its top can leave the cited
    // words below the fold.
    const hit = body.querySelector(".source-quote");
    (hit || targetSection)?.scrollIntoView({ block: "center" });
  } catch (err) {
    if (controller.signal.aborted) return;
    body.textContent = "";
    body.appendChild(failureBlock(t("sources.viewFailed", "Could not open this source"), err.message));
  }
}

function initSourceViewer() {
  document.getElementById("source-viewer-close").addEventListener("click", closeSourceViewer);
  document.getElementById("source-viewer-overlay").addEventListener("click", (event) => {
    if (event.target.id === "source-viewer-overlay") closeSourceViewer();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSourceViewer();
  });
  store.on("orbit:switched", closeSourceViewer);
}

// --- Orbit switcher ---------------------------------------------------------------------------

// Orbits are located by TITLE. The id never appears — it is an internal handle (invariant 37),
// and putting it in front of the name (with `N sources, M turns` beside it) was the whole problem:
// a user could not tell which orbit was which without reading machine metadata.
async function refreshOrbitList() {
  const menu = document.getElementById("orbit-menu");
  let data;
  try {
    data = await api("/orbits");
  } catch {
    return; // the picker keeps whatever it last showed; opening it will retry
  }
  menu.innerHTML = "";

  data.orbits.forEach((nb) => {
    menu.appendChild(renderOrbitRow(nb));
  });

  const create = document.createElement("button");
  create.type = "button";
  create.className = "orbit-row orbit-row-new";
  // ASCII `+`, matching `#facet-new` in `index.html`. U+FF0B is a FULLWIDTH plus: it belongs in a
  // CJK run and reads as a stray wide glyph in an English one. Fixed in one of its two sites a
  // round ago - and at 375 the rail is hidden, so THIS is the only route to a new orbit.
  create.textContent = t("app.newOrbitRow", "+ New orbit");
  create.addEventListener("click", async () => {
    closeOrbitMenu();
    // MINT and OPEN, the same as the rail's "New facet". `resetToNewOrbit()` alone clears state
    // and switches nothing, so from inside an orbit it emptied the orbit you were looking at
    // and left its id in the address bar - the wordmark had the identical defect and this was the
    // other caller. The id is minted here and never asked for (invariant 37).
    await openOrbit(`nb-${crypto.randomUUID().slice(0, 8)}`, { fresh: true });
  });
  menu.appendChild(create);

  if (data.unreadable.length) {
    console.warn("unreadable orbit files (flagged, not hidden):", data.unreadable);
  }
}

// Coarse on purpose: the row needs "which of these is recent", not a timestamp. Anything older
// than a week falls back to a real date, because "37 days ago" is not something anyone can place.
function relativeTime(epochSeconds) {
  const seconds = Math.max(0, Date.now() / 1000 - epochSeconds);
  if (seconds < 90) return t("time.justNow", "just now");
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return t("time.minutes", `${minutes}m ago`, { n: minutes });
  const hours = Math.round(minutes / 60);
  if (hours < 24) return t("time.hours", `${hours}h ago`, { n: hours });
  const days = Math.round(hours / 24);
  if (days <= 7) return t("time.days", `${days}d ago`, { n: days });
  return new Date(epochSeconds * 1000).toLocaleDateString(uiLang());
}

function renderOrbitRow(nb) {
  const row = document.createElement("div");
  row.className = "orbit-row";
  if (nb.id === state.orbitId) row.classList.add("is-current");
  if (activeRuns.has(nb.id)) row.classList.add("is-running");

  const open = document.createElement("button");
  open.type = "button";
  open.className = "orbit-row-open";
  //: **`role="option"` is GONE, and so is the `role="listbox"` that wrapped it.** An option may not
  //: be an interactive element and may not have interactive siblings, and this was a `<button>`
  //: with a rename `<button>` (and now a delete one) beside it inside the same row — not a valid
  //: listbox in any assistive technology, and no option ever carried `aria-selected`, so the
  //: currently-open orbit was marked by a class and nothing else. Claiming a role and keeping
  //: none of its contract is worse than claiming none: a screen reader announces a list box and
  //: then behaves like a pile of buttons.
  //:
  //: A group of buttons with `aria-current` is the honest shape, and it is what the facet rail
  //: already needed too. The tablist next door went the other way — see `show()` — because those
  //: really are tabs over panels; this is a menu of places to go.
  if (nb.id === state.orbitId) open.setAttribute("aria-current", "true");

  if (activeRuns.has(nb.id)) {
    const dot = document.createElement("span");
    dot.className = "run-dot orbit-row-dot";
    dot.dataset.tip = t("app.generating", "Generating something in this orbit");
    open.appendChild(dot);
  }

  const title = document.createElement("span");
  title.className = "orbit-row-title";
  // textContent, never innerHTML: a title is model-authored text derived from source content a
  // prompt-injected source could influence (invariants 6 and 29).
  //
  // `derived_title` is the server's own fallback (from the orbit's origins, no model call), so a
  // orbit someone has only put sources into reads as its subject rather than as "Untitled" —
  // titling is lazy now, so that is the common case, not a rare one.
  // Through the same ladder the facet rail uses. Raw, `derived_title` is a sentence cut from the
  // first source at 60 characters, so the header read "…each pattern desc" - the mid-word fragment
  // this build fixed for nodes and for the rail, still live here.
  title.textContent = facetLabel(nb) || t("app.untitled", "Untitled orbit");
  open.appendChild(title);

  const meta = document.createElement("span");
  meta.className = "orbit-row-meta";
  const parts = [
    t("app.rowMeta", `${plural(nb.source_count, "source")} · ${plural(nb.turn_count, "turn")}`, {
      sources: nb.source_count,
      turns: nb.turn_count,
    }),
  ];
  // Model-authored titles are NOT unique — a user hit three orbits with near-identical generated
  // names. With the id no longer shown anywhere, "which did I touch last" is the only thing left to
  // tell them apart, so it goes on the row rather than being something to work out.
  if (nb.updated_at) parts.push(relativeTime(nb.updated_at));
  meta.textContent = parts.join(" \u00b7 ");
  open.appendChild(meta);

  open.addEventListener("click", () => {
    closeOrbitMenu();
    openOrbit(nb.id);
  });
  row.appendChild(open);

  const rename = document.createElement("button");
  rename.type = "button";
  rename.className = "orbit-row-rename";
  rename.textContent = "\u270e\ufe0e";
  rename.dataset.tip = t("app.rename", "Rename");
  rename.addEventListener("click", (event) => {
    event.stopPropagation();
    startRename(row, nb);
  });
  row.appendChild(rename);

  //: **An orbit could not be deleted from anywhere.** No endpoint, no CLI verb, no control — so
  //: once one existed it was permanent, and emptying it left "Untitled orbit · 0" in the facet
  //: rail forever. The product ships Forget for a Horizon node and ✕ for a source, and its premise
  //: is orbits you curate on purpose; curation without deletion is not curation. This file even
  //: carried the string "a deleted orbit" for a state nothing could produce.
  //:
  //: Here rather than inside the orbit view: this row is where the reader already renames one,
  //: and it is the only surface that lists an orbit you are NOT currently in — which is where
  //: "get rid of that empty one I made by accident" actually happens.
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "orbit-row-delete";
  remove.textContent = "\u2715";
  const deleteLabel = t("app.deleteOrbit", "Delete orbit");
  remove.dataset.tip = deleteLabel;
  remove.setAttribute("aria-label", deleteLabel);
  remove.addEventListener("click", async (event) => {
    event.stopPropagation();
    const label = facetLabel(nb) || t("app.untitled", "Untitled orbit");
    //: The confirm says what SURVIVES, not just what goes. A node was copied into the orbit at
    //: promotion (invariant 78), so deleting the orbit cannot lose a capture — and a reader who
    //: does not know that will not press the button.
    const ok = await confirmAction(
      t(
        "app.deleteOrbitAsk",
        `Delete “${label}”? Its sources and conversation go with it. Anything you captured stays in the Horizon.`,
        { name: label }
      )
    );
    if (!ok) return;
    try {
      await api(`/orbits/${encodeURIComponent(nb.id)}`, { method: "DELETE" });
    } catch (err) {
      // 409 while a run is in flight is the interesting one, and the server's sentence says so.
      notify(readableError(err.message), { tone: "error" });
      return;
    }
    if (nb.id === state.orbitId) {
      closeOrbitMenu();
      showHorizon();
    } else {
      refreshOrbitList();
      // The facet rail lists the same orbits and is rendered separately.
      void renderFacets();
    }
  });
  row.appendChild(remove);

  return row;
}

// Rename in place. A PUT, never the generate endpoint: setting a title is an instant write that
// always succeeds, generating one is a model run that can fail and be superseded.
function startRename(row, nb) {
  row.innerHTML = "";
  const input = document.createElement("input");
  input.className = "orbit-rename-input";
  input.value = nb.title || "";
  input.maxLength = 120;
  row.appendChild(input);

  async function commit() {
    const value = input.value.trim();
    if (!value || value === nb.title) {
      refreshOrbitList();
      return;
    }
    try {
      const updated = await api(`/orbits/${encodeURIComponent(nb.id)}/title`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: value }),
      });
      if (nb.id === state.orbitId) {
        state.title = updated.title;
        store.emit("orbit:titled", { title: state.title, orbitId: nb.id });
      }
    } catch (err) {
      notify(t("err.rename", `Could not rename: ${err.message}`, { message: err.message }));
    }
    refreshOrbitList();
  }

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      // Mid-composition Enter COMMITS an IME candidate; stealing it renames the orbit to a
      // half-typed word. Same guard, same reason, as the ask box and the capture field.
      if (event.isComposing || event.keyCode === 229) return;
      event.preventDefault();
      commit();
    }
    if (event.key === "Escape") {
      // Detach the blur handler FIRST. Escape used to call the async refresh with `commit` still
      // listening on a focused input, so any focus change while that request was in flight sent the
      // typed value as a real rename — a cancel that could commit.
      input.removeEventListener("blur", commit);
      refreshOrbitList();
    }
  });
  input.addEventListener("blur", commit);
  input.focus();
  input.select();
}

function closeOrbitMenu({ restoreFocus = false } = {}) {
  const menu = document.getElementById("orbit-menu");
  const button = document.getElementById("orbit-current");
  const hadFocus = menu.contains(document.activeElement);
  menu.hidden = true;
  button.setAttribute("aria-expanded", "false");
  //: **Focus goes back to the trigger.** Closing with Escape from inside the list dropped it to
  //: `<body>` and the next Tab restarted at the skip link — a popover owes the same return its
  //: modals already make (`closeModal` restores, verified). Only when focus was actually IN the
  //: menu, or when the caller says so: closing it because the reader clicked elsewhere on the page
  //: must not yank them back here.
  if (restoreFocus || hadFocus) button.focus();
}

//: `fresh` says the caller just MINTED this id (invariant 37), so a 404 is expected and the
//: placeholder below is the lazy-create path. Every other caller is naming an orbit it believes
//: already exists, and for those a 404 is news.
async function openOrbit(orbitId, { push = true, fresh = false } = {}) {
  const trimmed = orbitId.trim();
  if (!trimmed) return false;
  let orbit;
  //: Whether the SERVER has this orbit, which decides whether its id may go in the address bar.
  let onDisk = true;
  try {
    orbit = await api(`/orbits/${encodeURIComponent(trimmed)}`);
  } catch (err) {
    //: **One dropped request used to fabricate the reader's orbit.** A bare `catch` here treated
    //: every failure as "does not exist yet": an orbit with four sources and two turns rendered as
    //: an empty one, with no error, no retry and the `?nb=` silently dropped from the address bar —
    //: and "Add source" from that screen writes into an orbit the reader believes is empty. It did
    //: not heal when the network came back. Four false statements about the reader's own data, which
    //: is invariant 60's rule ("a status line may not claim something the page is not doing") aimed
    //: at the data instead of the status line.
    //:
    //: It also threw away what the server had gone to the trouble of saying. Invariant 27 makes a
    //: corrupted orbit file a 409 carrying the sentence that tells you how to fix it; this
    //: reported it as an empty orbit, and the boot path reported it as "not here any more".
    if (fresh && err.status === 404) {
      onDisk = false;
      orbit = { id: trimmed, sources: [], turns: [], notes: [] };
    } else if (err.status === 404) {
      notify(t("app.orbitGone", "That orbit is not here any more."), { tone: "info" });
      return false;
    } else {
      notify(
        t("app.orbitFailed", `Could not open that orbit: ${readableError(err.message)}`, {
          message: readableError(err.message),
        }),
        { tone: "error" }
      );
      return false;
    }
  }
  orbitGeneration += 1;
  state.orbitId = orbit.id;
  state.orbitSlug = orbit.slug || orbit.id;
  state.title = orbit.title || null;
  state.derivedTitle = orbit.derived_title || null;
  state.overview = orbit.overview || null;
  state.podcast = orbit.podcast || null;
  state.sources = orbit.sources;
  state.turns = orbit.turns;
  state.notes = orbit.notes || [];
  store.emit("orbit:switched", { orbitId: orbit.id });
  store.emit("orbit:titled", { title: state.title, orbitId: orbit.id });
  store.emit("sources:changed", { sources: state.sources });
  store.emit("notes:changed", { notes: state.notes });
  state.turns.forEach((turn) => store.emit("chat:turnAdded", { turn, restoring: true }));
  refreshOrbitList();
  // **The SWITCH belongs to opening.** It used to be a separate call every caller had to remember,
  // and one of six forgot: the header picker's row loaded the orbit's state and left the Horizon
  // on screen, so on a phone - where the rail is hidden and the picker is the ONLY route - you
  // could create an orbit and never open one. The address bar did not follow a switch either,
  // so a reload silently returned you to the orbit you had left. Both were the same missing
  // line, and a missing line in five places is a function boundary in the wrong place.
  //: **NO `?nb=` FOR A ORBIT THAT IS NOT THERE YET.** "+ New orbit" mints an id client-side
  //: and an orbit is created lazily by its first source, so writing the id into the address bar
  //: straight away produced a URL that leads nowhere: reload or share it and you land on the Horizon
  //: with "That orbit is not here any more" — which is false, because it never was and nothing
  //: was lost. The boot path's comment already distinguished the two cases and then gave them one
  //: message. The link appears the moment the orbit becomes real (see `sources:changed` below),
  //: which is also the moment it is worth sharing.
  showOrbitView({ push: push && onDisk });
  void reattachInFlightRuns(orbit.id, orbitGeneration);
  return true;
}

//: **A reload used to lose a run that kept spending.** The worker is a subprocess and survives the
//: page (invariant 21), but the run id lived only in the tab that started it: after F5 there was no
//: indicator, no Stop, and no way to find either — asking again simply started a SECOND run on the
//: same orbit. Invariant 47 does not have a reload exemption.
//:
//: The server knows (`GET /orbits/{id}/runs`), so the page asks on every open. Mounted into the
//: chat column with a deliberately GENERIC label: this recovers a run whose ACTION is not knowable
//: from an id, and naming a stage the page cannot see is what invariant 60 forbids. What it does
//: know, and what matters, is that something is running and that Stop reaches it.
async function reattachInFlightRuns(orbitId, generation) {
  let runs = [];
  try {
    runs = (await api(`/orbits/${encodeURIComponent(orbitId)}/runs`)).runs || [];
  } catch {
    // An older server, or none reachable. Nothing to recover is the safe reading.
    return;
  }
  // The orbit moved on while we asked. Same generation guard every other awaiting flow here
  // uses, and for the same reason.
  if (!runs.length || generation !== orbitGeneration) return;
  const history = document.getElementById("chat-history");
  if (!history) return;
  const status = runStatus({
    orbitId,
    runIds: runs,
    label: t("run.recovered", "Something is still running in this orbit"),
    // **Without this the Stop said "Stopping…" forever.** `runStatus`'s handler sets that text
    // before the request and only `finish()` clears it; every other caller passes an `onCancel`
    // that tears its own row down, and this one passed none - so the run was cancelled server-side
    // while the page went on claiming otherwise, which is invariant 60's own rule. This runs on
    // EVERY orbit open, so it was the default shape of Stop after a reload.
    //: **Stop goes through the SAME teardown as a run ending**, and that is the whole of this
    //: comment's second life. It used to set `watching = false` and remove the row by hand — which
    //: made `done()`'s own `if (!watching) return;` swallow the only `recoveredRuns.delete` in the
    //: file. So pressing Stop on a recovered row left this orbit marked as recovering FOREVER,
    //: and every ordinary in-tab run afterwards took the composer and ↻ Regenerate away: exactly
    //: the lie the guard's own comment refuses ("asking while an artifact generates is a reasonable
    //: thing to want"). A second teardown path is how the first one's bookkeeping gets missed.
    onCancel: () => stopWatching({ gone: true }),
  });
  history.appendChild(status.node);
  recoveredRow = status.node; // so `rebuildHistory` can put it back (see there)

  //: **AND IT HAS TO END.** This was the one `runStatus` mount of five that never called
  //: `openTicker` and never called `finish()`, so after a reload the recovered row counted upward
  //: for as long as the tab stayed open: the worker exited, `GET .../runs` went empty, the trace
  //: recorded `run_end`, and the page kept saying "still running · 2:05" beside a Stop. Pressing
  //: that Stop answered 404 and the page reported "couldn't stop it, it may still be going" - the
  //: opposite of the truth, on the paid path, which is invariant 60's own sentence. `finish()` is
  //: also the only route to `noteRunFinished`, so the header's run dot leaked for the session.
  //:
  //: TWO signals, because each alone has a hole. The ticker carries the model's words and ends on a
  //: terminal event - but a run that finished between the `/runs` answer and the stream opening
  //: emits none, which is precisely the race a reload sits in. So `/runs` is polled as well, and it
  //: is the authoritative one: it is the same question, asked of the same endpoint, that said the
  //: run existed in the first place.
  //: This orbit now has a run this tab did not start, which is what turns the composer guard on
  //: (see `RUN_GUARDED_ON_RECOVERY`).
  //: The flag is THIS MOUNT's. Re-opening the orbit mounts a new recovered row, and the old
  //: mount's poll then ends with `stopWatching({ gone: true })` — which deleted the flag by
  //: orbit id, i.e. the NEW mount's: the composer unlocked, a second paid question could start,
  //: and the next rebuild dropped the row with the first run's only Stop.
  const mount = {};
  recoveredRuns.set(orbitId, mount);
  // Lock what the composer's handler owns (Send, ↻ Regenerate, Clear) while this run is recovered.
  store.emit("chat:pending", { pending: false });
  syncRunGuards();

  let watching = true;
  const stopWatching = ({ gone = false } = {}) => {
    if (!watching) return;
    watching = false;
    if (recoveredRuns.get(orbitId) === mount) recoveredRuns.delete(orbitId);
    //: Re-decide the composer now the flag is gone. A ↻ Regenerate BUILT while the lock held (a
    //: rebuild or re-mount during recovery) is disabled by construction, and `syncRunGuards` only
    //: releases what it marked itself — so it stayed dead until a switch or a reload. The handler
    //: derives the hold from its owners, so this unlocks nothing another run still holds.
    store.emit("chat:pending", { pending: false });
    //: **CLOSE THE STREAMS.** This is the only `openTicker` caller that does not await a request
    //: that ends them, so without this each orbit open left one socket per recovered run alive
    //: for the life of the tab. At six, Chrome's per-origin HTTP/1.1 cap, the page could no longer
    //: make ANY request to its own server - `fetch` stalled past eight seconds while `curl`
    //: answered the same server in two milliseconds.
    // ONLY the streams this mount opened, proven by identity — see `closeTicker`.
    for (const [runId, source] of mine) closeTicker(runId, source);
    //: `finish()` FIRST, because it is the only route to `noteRunFinished` and therefore the only
    //: thing that puts the header's run dot out.
    status.finish();
    status.node.remove();
    if (recoveredRow === status.node) recoveredRow = null;
    //: And the row is REPLACED, not just stopped. `is-done` only stills the pulsing dot: the label
    //: would still read "something is still running" and the Stop would still be there to press,
    //: answering 404 and reporting "it may still be going". A finished run has a result sitting in
    //: the orbit file that this tab has not got, so the honest row says so and offers the one
    //: action that fetches it.
    if (gone || generation !== orbitGeneration) return;
    //: **A FAILED run must not be reported as a finished one.** This said "That run has finished."
    //: and offered "Load the result" whatever had happened — so a recovered run that failed lost
    //: the reader's question, showed no reason anywhere, and handed them a button whose only
    //: outcome was nothing, on the one path that has no other channel. The call was still billed.
    //: Invariant 60's own sentence.
    //:
    //: The ticker's terminal event is where the page can learn this: `failed` carries the server's
    //: message, and the chat turn's own failure surface already knows how to render it. With no
    //: terminal event at all (the poll won the race) the honest word is ENDED, not finished — and
    //: reloading is the right offer either way, because the orbit file has whatever landed.
    if (outcome && outcome.kind === "failed") {
      history.appendChild(
        failureBlock(t("chat.askFailed", "That question did not run"), outcome.detail || "")
      );
      return;
    }
    const line = elt("div", "run-recovered-done");
    line.appendChild(elt("span", null, t("run.recoveredDone", "That run has ended.")));
    const load = elt("button", "btn btn-small", t("run.loadResult", "Load the result"));
    load.type = "button";
    load.addEventListener("click", () => openOrbit(orbitId, { push: false }));
    line.appendChild(load);
    history.appendChild(line);
  };
  //: The streams THIS mount owns, and the last terminal kind each reported. The first is what makes
  //: the teardown safe (a later mount's stream must not be closed by this one); the second is the
  //: only place the page can learn whether the run it recovered SUCCEEDED.
  const mine = new Map();
  let outcome = null;
  for (const runId of runs) {
    // Best effort: a stream that never opens must not keep the row alive on its own.
    openTicker(
      orbitId,
      runId,
      (evt) => {
        if (evt && (evt.kind === "failed" || evt.kind === "done")) outcome = evt;
        status.onEvent(evt);
      },
      (source) => mine.set(runId, source)
    ).then(() => {
      // One run ending is not all of them; the poll below decides. This only forwards the words.
    });
  }
  const poll = setInterval(async () => {
    if (!watching || generation !== orbitGeneration) {
      clearInterval(poll);
      // Leaving the orbit is not the run ending, but the row went with the repaint, so the
      // header's dot has to be released or it stays lit with nothing behind it.
      if (generation !== orbitGeneration) stopWatching({ gone: true });
      return;
    }
    let live = [];
    try {
      live = (await api(`/orbits/${encodeURIComponent(orbitId)}/runs`)).runs || [];
    } catch {
      return; // a blip is not an ending; the next tick asks again
    }
    if (runs.some((id) => live.includes(id))) return;
    clearInterval(poll);
    stopWatching();
  }, 2500);
}

// Everything that mutates an orbit acts on `state.orbitId`, which is set only by
// `openOrbit`. The id box is a REQUEST, not the current state — typing a new name in it and
// pressing "Add source" without pressing Open used to silently write into whatever orbit was
// already open, with the box on screen showing a different name entirely. Reported by a user, who
// hit it as "I can't create a second orbit without reloading the page". Two fixes, together:
// the box is now rewritten from `state` on every switch so it can never disagree with what the app
// is acting on, and the wordmark is a real button that starts an empty one.
// Asks the server to name the orbit from the sources it now holds. Fired after the FIRST
// source lands, never blocking it: ingestion must not wait on (or fail because of) a model call,
// and the source list should render the moment it exists. The generation check drops the result if
// the user has moved to another orbit while it was in flight.
//
// Silent on failure by design — the endpoint already falls back to a deterministic title, and a
// missing title is a cosmetic loss, never worth an alert over a source that was added fine.
// Title on DEMAND. Called by the actions that already run a model, never by adding a source.
// Fire-and-forget on purpose: a title must never delay or fail the thing the user actually asked
// for (the same "never lose what already succeeded" rule invariants 19 and 37 encode).
//: **Fired when a run SUCCEEDS, never alongside one.** This used to run at the start of ask,
//: overview, guide and podcast, on the reasoning that by then the reader had committed to a model
//: call anyway. They had committed to THAT call. Pressing Stop 1.8s into a question correctly
//: prevented the question - and left the title's own language pre-work and its main worker to spawn
//: six seconds later, two full round trips with no indicator and no Stop anywhere, because the
//: title run has a different id that no Stop names. Invariant 47 is absolute and its file lists
//: exactly one un-stoppable action (TTS synthesis), which it says must SAY so rather than pretend.
//:
//: Moving it after success keeps the original reasoning intact - a reader who got an answer has
//: certainly paid for one - and makes Stop mean what it says. A reader who only ever stops runs
//: never gets a generated title, which is correct: titling is lazy (invariant 37) and the picker
//: falls back to the derived label.
function ensureTitle() {
  if (!state.orbitId || state.title || !state.sources.length) return;
  void suggestTitle(state.orbitId, orbitGeneration);
}

async function suggestTitle(orbitId, generation) {
  try {
    const orbit = await api(`/orbits/${encodeURIComponent(orbitId)}/title`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: crypto.randomUUID() }),
    });
    if (generation !== orbitGeneration) return;
    state.title = orbit.title || null;
    store.emit("orbit:titled", { title: state.title, orbitId });
    refreshOrbitList();
  } catch {
    // keep whatever label is already on screen
  }
}

// --- Settings ---------------------------------------------------------------------------------
//
// PRESENTATION settings only: the language the model writes in, and the voices that read it.
// Trace retention, the upload cap and every model/credential variable are deliberately absent —
// "non-secret" is the wrong filter, since lowering retention DELETES traces holding ingested source
// text and raising the upload cap is a DoS lever. Those are safety bounds, and every holder of
// this API's token is fully privileged (invariants 25 and 77).
//
// Every row shows where its value comes from. A row pinned by an environment variable is DISABLED
// and says which one: a form that accepts a value and then quietly loses to the env would be a UI
// that lies, which is worse than not having the control.

// A FUNCTION, not a module-level const: the labels go through `t()`, and a const would freeze
// whatever language was active when the script loaded.
//: The orbits the landing row offers, fetched with the page's other choices.
let settingsOrbits = [];

function settingRows() {
  // ONE sentence, on the FIRST voice row only. The two were byte-identical and sixty pixels apart,
  // which reads as a template rather than as help - and they named `edge-tts`, `chatterbox` and the
  // `host-a`/`host-b` enum, three internal words for a reader who picked neither.
  const voiceHelp = t(
    "settings.voiceHelp",
    "Leave empty to let the orbit's language choose the pair."
  );
  return [
    {
      key: "output_language",
      choicesKey: "output_languages",
      label: t("settings.outputLanguage", "Output language"),
      placeholder: t("settings.outputLanguagePlaceholder", "e.g. Traditional Chinese"),
      help: t(
        "settings.outputLanguageHelp",
        "Leave empty to let each orbit work out its own from your interface and system language, its sources and your questions."
      ),
    },
    // Provider-aware on purpose: with chatterbox `default_voices` returns null for EVERY language,
    // so "empty" means its two shipped clips, not "follow the language" (invariant 43).
    {
      key: "tts_voice_host_a",
      choicesKey: "voices",
      label: t("settings.voiceA", "Podcast voice: host A"),
      placeholder: "e.g. zh-TW-YunJheNeural or host-a",
      help: voiceHelp,
    },
    {
      key: "tts_voice_host_b",
      choicesKey: "voices",
      label: t("settings.voiceB", "Podcast voice: host B"),
      placeholder: "e.g. zh-TW-HsiaoChenNeural or host-b",
      help: "",
    },
    // **The toggle the product decision promised and the page never had.** "Manual by default, with
    // a settings-page auto toggle" was the shape agreed for invariant 80; `GET`/`PUT /settings`
    // carried `auto_distil` from the start and `penumbra/web/` never mentioned it, so the only
    // way to turn it on was to hand-edit the settings file - and the next legitimate Save wiped it,
    // because the payload is built from the RENDERED inputs and a key with no row is a key with no
    // value. A capability reachable only by editing a file that the UI then destroys is worse than
    // one that does not exist.
    //
    // A fixed two-value choice rather than a checkbox, so it reads the same as every other row here
    // and so "use the default" stays distinguishable from "explicitly off" - which is the whole
    // point of `source` on this page.
    {
      key: "auto_distil",
      label: t("settings.autoDistil", "Summarise new captures automatically"),
      values: ["on", "off"],
      // LABELLED, not raw. Every other string on this page is translated, and the one row that
      // spends money read "使用預設 / on / off". The VALUE stays `on`/`off` - the wire format
      // `config.auto_distil_enabled` reads - and only the label is localised.
      labels: { on: t("settings.on", "On"), off: t("settings.off", "Off") },
      help: t(
        "settings.autoDistilHelp",
        "Off by default. Each summary is a model call on your own key, so a 200-bookmark import costs nothing until you turn this on."
      ),
    },
    // Every orbit is a choice, by its title. The VALUE is the orbit's slug, the filename token the
    // server files by, which is always inside the setting's own pattern even for an orbit named in
    // Chinese (invariant 10); an id outside that pattern would be refused on Save.
    {
      key: "landing_orbit",
      label: t("settings.landing", "Where new captures land"),
      values: ["off", ...settingsOrbits.map((o) => o.slug)],
      labels: Object.fromEntries([
        ["off", t("settings.landingOff", "Keep them in the Horizon only")],
        ...settingsOrbits.map((o) => [o.slug, o.label]),
      ]),
      help: t(
        "settings.landingHelp",
        "By default, everything you capture is also filed into your first orbit, so you can ask about it right away. It stays in the Horizon either way."
      ),
    },
  ];
}

// Local relations: the one setting that is a download rather than a value. Its model is fetched
// once, on a press, with its size stated beside the button; removing it deletes the model and every
// stored vector. No model call and no money, so it is not a safety bound (invariant 41).
function renderVectorsRow(body) {
  const wrap = elt("div", "setting-row vec-row");
  const head = elt("div", "vec-head");
  head.appendChild(elt("label", "", t("settings.vectors", "Local relations")));
  const pill = elt("span", "vec-pill", "");
  head.appendChild(pill);
  wrap.appendChild(head);
  wrap.appendChild(elt("div", "setting-source", t("settings.vectorsHelp",
    "Finds captures with similar content on this computer, so ones not yet summarised can be linked too. Free; the model is downloaded once.")));
  const stage = elt("div", "vec-stage");
  wrap.appendChild(stage);
  body.appendChild(wrap);
  let timer = null;
  const mb = (n) => (n / 1048576).toFixed(0);

  async function act(path, method) {
    try {
      await api(path, { method });
    } catch (err) {
      notify(readableError(err.message));
    }
    void paint();
  }

  async function paint() {
    let st;
    try {
      st = await api("/horizon/vectors");
    } catch (err) {
      stage.textContent = readableError(err.message);
      return;
    }
    if (!stage.isConnected) return;
    stage.textContent = "";
    const dl = st.download;
    const working = st.embedding && st.embedding.running;
    pill.className = "vec-pill";
    if (dl.running) {
      const pct = dl.total ? Math.min(100, Math.round((dl.done / dl.total) * 100)) : 0;
      pill.textContent = t("settings.vectorsPillDownloading", `Downloading ${pct}%`, { pct });
      pill.classList.add("is-busy");
      const bar = elt("div", "vec-bar");
      bar.setAttribute("role", "progressbar");
      bar.setAttribute("aria-valuemin", "0");
      bar.setAttribute("aria-valuemax", "100");
      bar.setAttribute("aria-valuenow", String(pct));
      bar.setAttribute("aria-label", t("settings.vectorsDownloadLabel", "Model download"));
      const fill = elt("span", "vec-bar-fill");
      fill.style.width = `${pct}%`;
      bar.appendChild(fill);
      stage.appendChild(bar);
      const meta = elt("div", "vec-meta");
      meta.appendChild(elt("span", "vec-count", t("settings.vectorsBytes", `${mb(dl.done)} of ${mb(dl.total)} MB`,
        { done: mb(dl.done), total: mb(dl.total) })));
      const stop = elt("button", "vec-link", t("settings.vectorsStop", "Stop"));
      stop.type = "button";
      stop.addEventListener("click", () => { stop.disabled = true; void act("/horizon/vectors/cancel", "POST"); });
      meta.appendChild(stop);
      stage.appendChild(meta);
    } else if (st.installed) {
      pill.textContent = working ? t("settings.vectorsPillWorking", "On, comparing") : t("settings.vectorsPillOn", "On");
      pill.classList.add(working ? "is-busy" : "is-on");
      const meta = elt("div", "vec-meta");
      meta.appendChild(elt("span", "vec-count", t("settings.vectorsCount", `${st.count || 0} captures compared`,
        { n: st.count || 0 })));
      const off = elt("button", "vec-link is-danger", t("settings.vectorsRemoveShort", "Delete the model"));
      off.type = "button";
      off.addEventListener("click", () => { off.disabled = true; void act("/horizon/vectors", "DELETE"); });
      meta.appendChild(off);
      stage.appendChild(meta);
    } else {
      pill.textContent = t("settings.vectorsPillOff", "Off");
      const go = elt("button", "vec-go", "");
      go.type = "button";
      go.appendChild(elt("span", "", t("settings.vectorsDownloadShort", "Download the model")));
      go.appendChild(elt("span", "vec-go-size", `${mb(st.bytes)} MB`));
      go.addEventListener("click", () => { go.disabled = true; void act("/horizon/vectors/download", "POST"); });
      stage.appendChild(go);
    }
    const why = dl.error || (st.embedding && st.embedding.error);
    if (why) stage.appendChild(elt("p", "vec-error", readableError(why)));
    clearTimeout(timer);
    if (dl.running || working) timer = setTimeout(paint, 700);
  }
  void paint();
}

// The INTERFACE language row. Client-side only — it never reaches the server, because it is not a
// server setting: `PN_OUTPUT_LANGUAGE` decides what the MODEL writes, this decides what the buttons
// say, and a reader who wants a Chinese interface over English papers needs both to be expressible.
function renderUiLanguageRow(body) {
  const wrap = document.createElement("div");
  wrap.className = "setting-row";

  const label = document.createElement("label");
  label.textContent = t("settings.uiLanguage", "Interface language");
  label.htmlFor = "setting-ui-language";
  wrap.appendChild(label);

  const select = document.createElement("select");
  select.id = "setting-ui-language";
  const current = uiLang();
  UI_LANGUAGES.forEach((lang) => {
    const option = document.createElement("option");
    option.value = lang.code;
    option.textContent = lang.label;
    option.selected = lang.code === current;
    select.appendChild(option);
  });
  select.addEventListener("change", () => setUiLang(select.value));
  wrap.appendChild(select);

  const help = document.createElement("div");
  // The same class every other row's help line uses; `setting-help` had no rule at all, so this one
  // line rendered at full size and full contrast, unlike the four below it.
  help.className = "setting-source";
  help.textContent = t(
    "settings.uiLanguageHelp",
    "Only affects the text on this screen, never what the model writes."
  );
  wrap.appendChild(help);

  body.appendChild(wrap);
}

//: What the server says each setting may be set to, for the provider actually configured. Empty
//: until `initSettings` fetches it; a row with no choices falls back to a free-text input, so the
//: page still works if this request fails.
let settingsChoices = {};

//: **What the reader had typed but not yet saved.** Changing the INTERFACE language re-renders this
//: dialog from server state (it has to: every label, every help line and every voice name in it is
//: translated), and that rebuild threw away every unsaved change in the same dialog. Measured: set
//: the output language to Japanese, turn on auto-summary, then correct the interface language, and
//: both revert to "use the default" with nothing said - so pressing Save now saves auto-summary
//: OFF, on the one setting that decides whether captures spend money.
//:
//: A draft rather than a "are you sure": the reader changed a presentation setting, which is not a
//: reason to ask them anything, and their other choices are still on screen where they left them.
let settingsDraft = null;

function collectSettingsDraft() {
  const draft = {};
  settingRows().forEach((row) => {
    const input = document.getElementById(`setting-${row.key}`);
    if (input && !input.disabled) draft[row.key] = input.value;
  });
  return draft;
}

function renderSettings(state_) {
  const body = document.getElementById("settings-body");
  body.textContent = "";

  if (state_.error) {
    // Surfaced, never swallowed — the reader falls back to defaults on a corrupt file, and the one
    // place that can say so is here (the same "flag, never silently drop" shape the orbit
    // listing already uses for an unparseable file).
    const warn = document.createElement("div");
    warn.className = "setting-source";
    warn.textContent = t(
      "settings.readError",
      `The saved settings could not be read (${state_.error}); showing defaults.`,
      { error: state_.error },
    );
    body.appendChild(warn);
  }

  // The first thing a desktop reader looks for here is the model and its key, which this page
  // must never hold (invariant 41). It says where they are instead.
  if (isDesktopShell()) {
    body.appendChild(elt("p", "setting-source settings-where", t(
      "settings.modelWhere",
      `The model and its API key are set in ${menuItems().config}, not here.`,
      menuItems(),
    )));
  }

  const inputs = new Map();
  renderUiLanguageRow(body);
  renderVectorsRow(body);

  settingRows().forEach((row) => {
    const entry = state_[row.key] || { value: null, source: "default", env_var: "" };
    const wrap = document.createElement("div");
    wrap.className = "setting-row";

    const label = document.createElement("label");
    label.textContent = row.label;
    label.htmlFor = `setting-${row.key}`;
    wrap.appendChild(label);

    // A SELECT when the server told us what the valid values are, a text box otherwise. Free text
    // here was a way to typo an env-var value into a setting that then fails at synthesis time —
    // and `config._VOICE_PATTERN` has to refuse a bad one anyway, so offering the choices is both
    // safer and less work for the person. The options come from `GET /settings/choices` rather than
    // a list in this file, because the answer is provider-specific and a second copy would drift.
    // `row.values` is a list written HERE (a closed, two-value setting); `row.choicesKey` is a list
    // the SERVER supplies (voices, languages) because it is provider-specific and a second copy
    // would drift. Both end up as a `<select>`; only the source of the list differs.
    const choices = row.values || settingsChoices[row.choicesKey] || [];
    const current = entry.source === "default" ? "" : entry.value || "";
    let input;
    if (choices.length) {
      input = document.createElement("select");
      const blank = document.createElement("option");
      blank.value = "";
      blank.textContent = t("settings.useDefault", "Use the default");
      input.appendChild(blank);
      // A value already stored that is NOT in the list (an env var, or a voice from another
      // provider left behind by a switch) still has to be selectable, or opening the page and
      // pressing Save would silently clear it.
      const options = choices.includes(current) || !current ? choices : [current, ...choices];
      options.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        // `row.labels` is a fixed pair written here (on/off); `settingsChoices.voice_labels` is the
        // SERVER's, because only it knows which language a provider's voice belongs to.
        option.textContent =
          (row.labels && row.labels[value]) ||
          (settingsChoices.voice_labels && settingsChoices.voice_labels[value]) ||
          value;
        option.selected = value === current;
        input.appendChild(option);
      });
    } else {
      input = document.createElement("input");
      input.type = "text";
      input.placeholder = row.placeholder;
      // textContent/value, never innerHTML — these are server-echoed, caller-writable strings.
      input.value = current;
    }
    input.id = `setting-${row.key}`;
    input.disabled = entry.source === "env";
    // The reader's unsaved value wins over the server's, because it is newer. Guarded on the option
    // still existing: a `<select>` handed a value it has no option for silently becomes "".
    if (settingsDraft && row.key in settingsDraft && !input.disabled) {
      const wanted = settingsDraft[row.key];
      const exists =
        input.tagName !== "SELECT" || [...input.options].some((o) => o.value === wanted);
      if (exists) input.value = wanted;
    }
    wrap.appendChild(input);
    inputs.set(row.key, input);

    const note = document.createElement("div");
    note.className = "setting-source";
    note.textContent =
      entry.source === "env"
        ? withShellHint(t("settings.pinnedBy", `Pinned by ${entry.env_var}. Unset it to edit here.`, { env: entry.env_var }))
        : row.help;
    wrap.appendChild(note);

    body.appendChild(wrap);
  });

  // Consumed exactly once: a draft that outlived its rebuild would overwrite the values a SAVE
  // just round-tripped through the server.
  settingsDraft = null;

  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn-primary";
  save.textContent = t("settings.save", "Save");
  save.addEventListener("click", async () => {
    save.disabled = true;
    const payload = {};
    inputs.forEach((input, key) => {
      if (!input.disabled && input.value.trim()) payload[key] = input.value.trim();
    });
    try {
      renderSettings(await api("/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }));
      // **SAY SO.** The only global, persistent write in the product reported nothing at all on
      // success: a review's MutationObserver over the whole document caught exactly two mutations,
      // 4ms apart, both the button's own `disabled` flag. The failure path notifies; a write that
      // changes behaviour for every orbit and survives a restart must not be the quieter of the
      // two. `tone: "ok"` so it fades on its own rather than needing a dismiss.
      notify(t("settings.saved", "Settings saved."), { tone: "ok", timeout: 2600 });
    } catch (err) {
      notify(t("settings.saveFailed", `Could not save settings: ${err.message}`, { message: err.message }));
    } finally {
      save.disabled = false;
    }
  });
  body.appendChild(save);
}

//: MODAL FOCUS, in one place, because the two overlays had none.
//:
//: `role="dialog"` and `aria-modal="true"` were already on both `.modal`s, which is the half that
//: is cheap. The half that was missing is the one a keyboard reader actually feels: opening
//: Settings left focus on the trigger BEHIND the scrim, and eight Tabs later an independent
//: reviewer was still walking the theme toggle, the facet rail and the capture field - typing into
//: a field they could not see, under a dialog that claimed to be modal. `aria-modal` is a promise
//: to assistive technology; it does nothing to the tab order on its own.
//:
//: `inert` does the real work: it removes a subtree from the tab order AND from the accessibility
//: tree, which is exactly the two things `aria-modal` only asserts. Supported everywhere this app
//: runs, and it degrades to "the old behaviour" rather than to a broken page where it is not.
//:
//: The trigger is remembered and restored, because returning the reader to where they were is the
//: other half of a dialog closing.
//: **`alert()` and `confirm()` are gone from this application.** Thirteen and three of them.
//:
//: Three reasons, in increasing order of weight. They cannot be styled, so a product with a
//: deliberate voice speaks in the browser's. They BLOCK — an `alert` freezes the renderer, which
//: is how one of them was found at all (a hung page during a review). And the shell this is headed
//: for is Tauri, where they become OS-level modals stacked over the window, which is a very
//: different thing from a line under the control you pressed.
//:
//: A NOTICE is for something that already happened and needs no answer. It does not steal focus
//: (`role="status"` + `aria-live="polite"` announces it without moving the caret), it stacks, and
//: an error stays until dismissed while an ordinary message leaves on its own — the reader should
//: not have to race a timer to read why something failed.
//: The SENTENCE, not the exception's class name in front of it.
//:
//: `FetchError: refused: '...' resolves to a disallowed address` and `RuntimeError: PN_MAIN_MODEL is
//: not set` both carry a message a self-hosted operator can act on and a Python type name they
//: cannot. The content is right for this audience — an independent review said so explicitly — and
//: the prefix is the product speaking in the traceback's voice.
//:
//: Stripped at the DISPLAY boundary, exactly as invariant 62 strips `[[SRC:...]]` markers: the
//: stored `Node.error` and the logged line keep the class name, where it is worth having, and
//: nothing on disk is rewritten. Only a leading `SomethingError:` / `SomethingException:` goes, so
//: a message that happens to contain a colon is untouched.
//: Two jobs: drop the exception's class name, and translate the handful of server sentences that
//: are ABOUT THE READER'S OWN ACTION rather than about a failure.
//:
//: The second one arrived from a reviewer who opened the same orbit in two tabs - which
//: `reattachInFlightRuns` actively invites - asked in one and pressed Stop in the other. The asking
//: tab then rendered `499: run 'reading-4d2662ef-79ea-4598-83a0-00a573fc9dff' was stopped before it
//: started`, or after the spawn, `502: worker for run '...' produced no output (exit -9); stderr:`.
//: Neither is an error: the reader asked for exactly that. A run id and a signal number are the
//: two things this CHANGELOG has already twice recorded as defects when they reached a reader.
//: `\b499\b` is gated on the message being about a RUN, for the same reason the provider branches
//: are gated on `FROM_PROVIDER`: a website answering 499 (nginx's "client closed request") was
//: reported to the reader as "You stopped this one." about a capture they had not touched. The
//: other three alternatives name run machinery and cannot collide.
//: **The PAGE cannot reach its own server** — a rejected `fetch`, which carries no status at all.
//: Not the same thing as `UNREACHABLE`, which is the SERVER failing to fetch a source for you.
//: Every browser spells it differently and all three spellings are internal wording that means
//: nothing to a reader: Chrome "Failed to fetch", Firefox "NetworkError when attempting to fetch
//: resource.", Safari "Load failed". They reached the reader verbatim, untranslated even in a
//: zh-Hant interface, and never said the one thing that is actually true and actionable — this all
//: runs on loopback, so the overwhelmingly likely cause is that `penumbra serve` is no longer
//: running. Anchored, because a rejected fetch's message is exactly one of these and nothing else.
const NO_SERVER =
  /^(TypeError: )?(Failed to fetch|NetworkError when attempting to fetch resource\.?|Load failed|Network request failed)$/;
const CANCELLED_RUN = /was stopped before it started|exit -9|SIGKILL/;
const CANCELLED_STATUS = /\b499\b/;
const SIZE_REFUSED = /\b413\b.*exceeding the (\d+)-byte limit/;
const NO_MODEL = /PN_MAIN_MODEL is not set|No LM is loaded/;
const NO_CLAUDE_CODE = /Claude Code not found/;
const MISCONFIGURED = /server misconfigured:\s*(.+)$/;
const CORPUS_CAP = /over the \d+ cap \(PN_MAX_CORPUS_CHARS\)/;
const REFUSED_TARGET = /is not a permitted external|resolves to a disallowed address/;
const FAKE_IP_HINT = /fake-IP proxy|PN_FETCH_ALLOW_CIDRS/;
//: Everything a fetch can fail with that the reader cannot act on: DNS, TLS, resets, timeouts. The
//: message behind these is `<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in
//: violation of protocol (_ssl.c:1028)>` — four lines of Python and OpenSSL internals, in the
//: reading column.
const UNREACHABLE = /urlopen error|SSLError|SSL:|getaddrinfo|Name or service not known|timed out|Connection (refused|reset)/i;
//: **The wall-clock backstop firing is a DESIGNED outcome, not a network fault.** `UNREACHABLE`
//: matches the bare words "timed out" anywhere and is tested above every provider branch, so a run
//: that hit `PN_RUN_TIMEOUT_SECONDS` — the thing invariant 68 exists for, since a `long` podcast
//: asking for 60-90 utterances could not fit under the 300s default — was reported to the reader as
//: "Could not reach that address." for a run in which no address was involved, after they had just
//: paid for a 5x-budget episode. `runner.py` names the knob in the message precisely so the reader
//: can act on it; this kept the knob and dropped the diagnosis.
const RUN_TIMED_OUT = /timed out after [\d.]+s and was cancelled|PN_RUN_TIMEOUT_SECONDS/;
//: The model PROVIDER not answering — a local ollama/LM Studio that is not running is the commonest
//: first-run failure for a BYOK product, and it is a different sentence from a source URL being
//: unreachable. Gated on provenance for the same reason every provider branch below is.
const PROVIDER_DOWN = /APIConnectionError|APITimeoutError|ServiceUnavailableError/;
//: A proxy or a captive portal answering a MODEL request with a web page. 645 characters of raw
//: `<!doctype html>` reached the reader in a toast; the tags carry nothing they can act on.
const HTML_BODY = /<!doctype html|<html[\s>]/i;

//: **WHERE A MESSAGE CAME FROM, decided before what it says.** A bare HTTP status is not evidence
//: of anything on its own: `403` inside a provider error is a rejected key, and `403` inside
//: `fetch error for 'https://…': HTTP Error 403: FORBIDDEN` is a page that does not want to be read
//: - the single commonest capture failure there is. Matching the number alone told a reader their
//: API key was wrong because a website had blocked a bot, and told them to go and change it.
//: `\bLM[A-Za-z]*Error\b` misses `RLMTaskError`, which is the class the CHAT path raises — there is
//: no word boundary before `LM` inside `RLMTaskError`, so the gate that decides "this came from the
//: provider" was closed on the product's primary verb. `[A-Za-z]*LM[A-Za-z]*Error` catches both.
const FROM_PROVIDER =
  /\[[a-z0-9_.-]+\/[^\]]+\]|litellm|OpenAIException|AnthropicException|\b[A-Za-z]*LM[A-Za-z]*Error\b|No LM is loaded/;
//: **A URL is never evidence of where a message came from.** Every token above is a word that can
//: appear in somebody's address: `fetch error for 'https://docs.litellm.ai/…': HTTP Error 403`
//: matched `litellm`, so a page that blocks bots was reported as "Your API key was rejected" and
//: the reader was sent to change a credential that was fine. Same shape as the `\b499\b` gate
//: directly above — a status or a word inside a URL belongs to the SITE, not to this install.
//: Stripped before the provenance question is asked, never before the message is read: the URL
//: still appears in whatever is shown.
const URL_ANYWHERE = /\bhttps?:\/\/\S+/gi;

function fromProviderNotAUrl(text) {
  return FROM_PROVIDER.test(String(text).replace(URL_ANYWHERE, " "));
}
const FROM_FETCH = /FetchError|fetch error for|HTTP Error \d{3}/;
const HTTP_STATUS = /HTTP Error (\d{3})/;

//: **The ways a BYOK install fails at the provider**, which between them are the likeliest errors
//: this product will ever show. Every one of them arrived here as raw `litellm` text - a bracketed
//: model tag, a dotted exception class, an HTTP status, a Python dict repr, and a literal
//: two-character `\n` - on the most-read surface in the product. Each is gated on `FROM_PROVIDER`,
//: because the sentence they produce names a credential or an environment variable and must never
//: be said about somebody else's web server.
//: `Missing credentials` is the FIRST-RUN failure — no key configured at all — and it was the one
//: shape this branch did not know, so the commonest thing a new BYOK install can do printed raw
//: provider text on the Horizon front page. The provider's own wording names three credentials this
//: product has no concept of (`workload_identity`, `admin_api_key`, `OPENAI_ADMIN_KEY`) and never
//: names `PN_API_KEY`, which is the variable it actually reads.
const BAD_KEY =
  /AuthenticationError|Incorrect API key|invalid_api_key|Missing credentials|\b40[13]\b/;
const OVER_QUOTA = /RateLimitError|insufficient_quota|rate.?limit|\b429\b/i;
//: `Received Model Group=` is GONE from this. It is litellm's router boilerplate and appears in
//: every router error, so a `max_tokens` refusal rendered as "your provider has no model called
//: gpt-4o-mini" - sending the reader to pick another OpenAI model, which fails identically, while
//: the Horizon strip on the same page correctly blamed the key.
const NO_SUCH_MODEL = /NotFoundError|model_not_found/;
//: Two refusals about SIZE, which are different problems with different actions: the reply this
//: build asked for is longer than the model will produce, and the sources are longer than it can
//: read. The first names `PN_MAX_TOKENS` because that is the lever.
const REPLY_TOO_LONG = /max_tokens is too large|max_tokens.{0,40}too (large|big)/i;
const CONTEXT_TOO_LONG = /ContextWindowExceededError|maximum context length|context_length_exceeded/i;
//: The model string is the one ACTIONABLE thing in a provider error: it says which credential and
//: which line of the environment to go and look at. `litellm` puts it in a leading `[vendor/model]`.
const MODEL_TAG = /\[([a-z0-9_.-]+\/[^\]]+)\]/i;

//: Two shapes a parser failure arrives in, both with an action behind them. The alternative is
//: `PdfiumError: Failed to load document (PDFium: Data format error)` and a Python LIST LITERAL of
//: extensions, which is the register this whole function exists to keep off the page.
const BAD_PDF = /PdfiumError|Failed to load document|Data format error/;
const BAD_FILE_TYPE = /unsupported file type/;

//: **Noise wherever it sits, not only at the start.** The two strips this replaced were `^`-anchored,
//: so they matched `ValueError: …` and nothing else — while the real messages are nested:
//: `[openai/gpt-4o-mini] litellm.AuthenticationError: …` leads with a bracket, `422: could not
//: ingest: PdfiumError: …` carries the class in the MIDDLE, and the Horizon's capture note wrapped the
//: whole thing in a translated sentence BEFORE cleaning it, which killed both anchors outright.
//: A dotted class name (`litellm.AuthenticationError`) did not match either.
//: **The class name is stripped BEFORE the leading noise, and both run until nothing more comes
//: off.** `LEADING_NOISE` is `^`-anchored, so a class-name prefix shielded the `[vendor/model]` tag
//: from the only rule that removes it: `LMServerError: [openai/gpt-4o-mini] litellm.…` kept its tag
//: all the way to the reader, on the front page. Alternating until the string stops changing is the
//: only order-independent answer — any fixed order has a shape that defeats it.
//:
//: `CLASS_NAME` also learned the DASH separator: `OpenAIException - ` is how litellm joins its
//: provider exceptions, and a rule that only knew `:` walked straight past it.
const LEADING_NOISE = /^(?:\[[^\]]*\]\s*|\d{3}:\s*)+/;
const CLASS_NAME = /\b[A-Za-z_][\w.]*(?:Error|Exception|Failure)\s*(?::|\s-)\s*/g;
//: A Python exception REPR, which the podcast and the overview printed whole, quotes and all.
const EXC_REPR = /^[A-Za-z_][\w.]*\((["\'])([\s\S]*)\1,?\s*\)$/;
//: A trailing dict blob: ` - {'error': {'message': …}}`. Nothing in it is for a reader.
//:
//: **BRACES ONLY, and it has to keep the character before them.** This read `[[{]` and was
//: unanchored, so it matched the FIRST `[` in the string — which in every litellm message is the
//: `[vendor/model]` tag at position 0 — and returned the empty string. A provider failure rendered
//: as a blank `.distil-error-why` and a toast whose only content was its dismiss button; the
//: message shape the CHANGELOG cites as the reason this function was rewritten was one of them.
//: A square bracket is ordinary prose here anyway (`The locator [page:3] is not in this corpus`,
//: `expected one of ['.md', '.pdf', '.txt']`), and that second case has had its own branch since
//: before this line existed.
const TRAILING_BLOB = /([^\s{])\s*[-—:]?\s*\{[\s\S]*\}\s*$/;

//: The sentence a READER can act on, from whatever the server said.
//:
//: The rule is not "make it friendly" — this is a self-hosted BYOK tool and a specific cause is
//: worth more than a soothing one. The rule is that nothing reaches this surface which the reader
//: cannot do anything with: an HTTP status code, a Python exception class, an OpenSSL source line,
//: a run UUID, a signal number, a shell command. Each branch below replaces one of those with the
//: thing it means; anything unrecognised keeps its sentence and loses only the class-name prefix
//: and a leading status code.
function isDesktopShell() {
  try {
    return sessionStorage.getItem("penumbra-shell") === "desktop";
  } catch {
    return false;
  }
}

// **An error that names an environment variable has to say where that variable lives.** In a
// terminal it is the shell's environment; in the desktop app there is no shell to set it in, and
// the settings live in a file the File menu opens. `restart` is for an error whose fix is only to
// start the server again, which the desktop app does from the same menu.
function withShellHint(text, kind = "config") {
  if (!isDesktopShell()) return text;
  const menu = menuItems();
  const hint = kind === "restart"
    ? t("err.desktopRestart", `${menu.restart} starts it again.`, menu)
    : t(
      "err.desktopWhere",
      `In the desktop app, these settings are in ${menu.config}, and ${menu.restart} applies them.`,
      menu
    );
  return `${text} ${hint}`;
}

//: The desktop menu items a message sends the reader to, spelled the way the menu bar spells them.
//: The menu follows the OS language and the page follows its own setting, so a Chinese interface on
//: an English Mac quoted 「檔案 > 開啟設定檔…」 at a menu that reads "File > Open Configuration File…".
//: The shell says which language its menu is in; without that, the interface language is the guess.
const MENU_ITEMS = {
  en: { config: "File > Open Configuration File…", restart: "File > Restart Server" },
  zh: { config: "檔案 > 開啟設定檔…", restart: "檔案 > 重新啟動伺服器" },
};

function menuItems() {
  let lang = null;
  try {
    lang = sessionStorage.getItem("penumbra-menu");
  } catch {
    // blocked storage: fall through to the interface language
  }
  if (!MENU_ITEMS[lang]) lang = uiLang().startsWith("zh") ? "zh" : "en";
  return MENU_ITEMS[lang];
}

function readableError(text) {
  //: UNWRAP FIRST, then recognise. A `litellm` failure reaches the podcast and the overview as a
  //: Python exception repr with the message inside quotes and a literal two-character `\n` in it,
  //: so every test below was being run against `LMInvalidRequestError('…` rather than against the
  //: sentence, and the printed result carried the backslash-n to the reader.
  let raw = String(text || "");
  const repr = raw.trim().match(EXC_REPR);
  if (repr) raw = repr[2];
  raw = raw.replace(/\\n/g, " ").replace(/\s+/g, " ").trim();
  if (NO_SERVER.test(raw.trim())) {
    return withShellHint(t(
      "err.noServer",
      "Lost contact with the Penumbra server. Check that it is still running, then try again."
    ), "restart");
  }
  if (CANCELLED_RUN.test(raw)) return t("run.wasStopped", "You stopped this one.");
  if (CANCELLED_STATUS.test(raw) && !FROM_FETCH.test(raw)) {
    return t("run.wasStopped", "You stopped this one.");
  }
  if (NO_MODEL.test(raw)) {
    // The env-var name stays — it is the actionable half, and this is a tool its reader installed.
    // The `set -a; . ./.env; set +a` incantation does not: a shell command in a chat bubble is the
    // product speaking in the terminal's voice.
    return withShellHint(t("err.noModel", "No model is configured. Set PN_MAIN_MODEL and restart the server."));
  }
  //: The subscription path runs the Claude Code on this computer, and the SDK's own message tells a
  //: developer to `npm install` it and edit PATH, which is not something to say in a chat bubble.
  if (NO_CLAUDE_CODE.test(raw)) {
    return withShellHint(t(
      "err.noClaudeCode",
      "A claude-agent-sdk model runs on your Claude subscription through Claude Code, which is not installed on this computer. Install Claude Code, run claude once in a terminal to log in, then restart the server."
    ), "restart");
  }
  //: **A setting the server cannot run with keeps its reason.** This fell to the generic 500 line
  //: below, "its log has the detail", over a log that had none: a typo in PN_FETCH_ALLOW_CIDRS, a
  //: provider the desktop app does not include or a malformed model id all read the same. The
  //: reason is the server's own sentence, in English, because it names the setting and the value.
  const misconfigured = raw.match(MISCONFIGURED);
  if (misconfigured) {
    return withShellHint(t("err.misconfigured", `A setting stops the server from running this: ${misconfigured[1]}`, {
      why: misconfigured[1],
    }));
  }
  if (CORPUS_CAP.test(raw)) {
    return withShellHint(t(
      "err.corpusCap",
      "This is more text than one run reads at once. Remove a source, or raise PN_MAX_CORPUS_CHARS and restart the server."
    ));
  }
  //: **A refusal that names its own fix must keep it.** Behind a fake-IP proxy (Clash, Surge,
  //: Mihomo) every public hostname resolves into a reserved range, so the guard refuses EVERY link,
  //: and the server's message says which setting fixes that (invariant 76). Collapsing it into the
  //: generic sentence below left a reader who could not add a single URL with no idea why.
  if (REFUSED_TARGET.test(raw) && FAKE_IP_HINT.test(raw)) {
    return withShellHint(t(
      "err.fakeIp",
      "This link resolved to a reserved address, which usually means a fake-IP proxy or VPN (Clash, Surge) is answering DNS. Set PN_FETCH_ALLOW_CIDRS to the range it uses, often 198.18.0.0/15, and restart the server."
    ));
  }
  if (REFUSED_TARGET.test(raw)) {
    return t("err.refusedTarget", "That address is not one this can fetch.");
  }
  if (RUN_TIMED_OUT.test(raw)) {
    return withShellHint(t(
      "err.runTimedOut",
      "This run hit the time limit and was stopped. A long podcast can need more time: raise PN_RUN_TIMEOUT_SECONDS and restart the server."
    ));
  }
  if (HTML_BODY.test(raw)) {
    return t(
      "err.htmlReply",
      "The model server answered with a web page instead of a reply. A proxy or a sign-in portal is probably in the way."
    );
  }
  if (PROVIDER_DOWN.test(raw) || (fromProviderNotAUrl(raw) && UNREACHABLE.test(raw))) {
    return withShellHint(t(
      "err.providerDown",
      "The model server did not answer. Check it is running and that PN_BASE_URL points at it."
    ));
  }
  //: Only once it is NOT about a run and NOT about the provider: this sentence is about a source
  //: URL, and saying it about anything else sends the reader to check their network for a fault
  //: that is not there.
  if (UNREACHABLE.test(raw)) {
    return t("err.unreachable", "Could not reach that address.");
  }
  const size = raw.match(SIZE_REFUSED);
  if (size) {
    return t("horizon.tooBigToUpload", `That file is larger than the ${humanBytes(+size[1])} limit.`, {
      limit: humanBytes(Number(size[1])),
    });
  }
  //: **SOMEBODY ELSE'S WEB SERVER, before anything that could name a credential.** A page answering
  //: 401/403/429 is the commonest capture failure there is, and every one of those numbers also
  //: appears in a provider error. The status is the whole diagnosis here and a reader can act on it
  //: — log in, pick another URL, wait — so it is translated into what it MEANS rather than printed.
  if (FROM_FETCH.test(raw) && !fromProviderNotAUrl(raw)) {
    const status = Number((raw.match(HTTP_STATUS) || [])[1] || 0);
    if (status === 401 || status === 403) {
      return t("err.pageRefused", "That page would not let us read it. It may need a login, or it blocks automated readers.");
    }
    if (status === 404 || status === 410) {
      return t("err.pageGone", "That page is not there any more.");
    }
    if (status === 429) {
      return t("err.pageBusy", "That site asked us to slow down. Try again in a while.");
    }
    if (status >= 500) {
      return t("err.pageBroken", "That site had an error of its own. Try again later.");
    }
    //: **ANY other status, rather than the five that were named.** 402, 406, 451 and a bare 400 are
    //: ordinary paywall and bot-block answers, and each fell through to the tail and printed
    //: `fetch error for 'https://…': HTTP Error 402: PAYMENT REQUIRED` — the status code and the
    //: URL, both of which this function exists to keep off the page, on the surface that reports a
    //: failed capture. A generic sentence is worth more than a precise number nobody can act on,
    //: and the row this appears in already shows the URL.
    if (status) {
      return t("err.pageRefused", "That page would not let us read it. It may need a login, or it blocks automated readers.");
    }
  }

  //: BEFORE the generic 500 branch. A provider rejecting a key answers 401 through a route that can
  //: surface as a 500 from here, and "something went wrong on the server" would send the reader to
  //: a log to find out what their own key is doing.
  const model = (raw.match(MODEL_TAG) || [])[1] || "";
  const fromProvider = fromProviderNotAUrl(raw);
  if (fromProvider && REPLY_TOO_LONG.test(raw)) {
    return withShellHint(t("err.replyTooLong", "This model will not produce a reply as long as Penumbra asks for. Lower PN_MAX_TOKENS and restart the server."));
  }
  if (fromProvider && CONTEXT_TOO_LONG.test(raw)) {
    return t("err.contextTooLong", "The sources are longer than this model can read at once. Remove one, or use a model with a larger context.");
  }
  if (fromProvider && BAD_KEY.test(raw)) {
    return withShellHint(model
      ? t("err.badKey", `The model provider rejected the API key for ${model}. Check PN_API_KEY and restart the server.`, { model })
      : t("err.badKeyPlain", "The model provider rejected the API key. Check PN_API_KEY and restart the server."));
  }
  if (fromProvider && OVER_QUOTA.test(raw)) {
    return t("err.overQuota", "The model provider refused: rate limit or quota. Wait and try again, or check your plan.");
  }
  if (fromProvider && NO_SUCH_MODEL.test(raw)) {
    return withShellHint(model
      ? t("err.noSuchModel", `Your provider has no model called ${model}. Check PN_MAIN_MODEL and restart the server.`, { model })
      : t("err.noSuchModelPlain", "Your provider does not have that model. Check PN_MAIN_MODEL and restart the server."));
  }
  if (BAD_FILE_TYPE.test(raw)) {
    return t("err.badFileType", "That file type is not supported. PDF, TXT and Markdown work.");
  }
  if (BAD_PDF.test(raw)) {
    return t("err.badPdf", "That PDF could not be read. It may be damaged, or not really a PDF.");
  }
  //: A LEADING status, the shape this project's own errors carry (`500: …`), not the digits
  //: anywhere. `\b500\b` matched `'code': 500` inside a provider's JSON payload and replaced a
  //: real reason with "something went wrong on the server" — sending the reader to a log that has
  //: nothing to say about their key.
  if (/(?:^|\s)500:\s/.test(raw)) {
    return t("err.serverFault", "Something went wrong on the server. Its log has the detail.");
  }
  //: Anything unrecognised keeps its SENTENCE and loses only what a reader cannot act on. The
  //: class name is stripped globally rather than at the start, because the sentence that matters is
  //: routinely nested behind one: `422: could not ingest: PdfiumError: …`.
  let cleaned = raw.replace(TRAILING_BLOB, "$1");
  // Until it stops changing, because each strip can expose the next: a class name hides a leading
  // `[vendor/model]` tag, and removing the tag can expose another class name behind it.
  for (let pass = 0; pass < 4; pass += 1) {
    const before = cleaned;
    cleaned = cleaned.replace(LEADING_NOISE, "").replace(CLASS_NAME, "").trim();
    if (cleaned === before) break;
  }
  //: **NEVER EMPTY.** Every strip above is a guess about what is noise, and a guess that eats the
  //: whole sentence leaves a blank space where the reason was - which is strictly worse than the
  //: raw text it was trying to improve on. That is not hypothetical: the previous `TRAILING_BLOB`
  //: returned "" for two of the commonest provider failures, and the page rendered an error toast
  //: whose only content was its own dismiss button.
  return cleaned || raw;
}

function humanBytes(n) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
  if (n >= 1e6) return `${Math.round(n / 1e6)} MB`;
  return `${Math.round(n / 1e3)} KB`;
}

//: `action` is one button beside the text, such as Undo; pressing it runs it and closes the notice.
function notify(message, { tone = "bad", timeout = 0, action = null } = {}) {
  const host = document.getElementById("notices");
  if (!host || !message) return;
  const note = elt("div", `notice notice-${tone}`);
  note.appendChild(elt("span", "notice-text", readableError(message)));
  if (action) {
    const act = elt("button", "notice-action", action.label);
    act.type = "button";
    act.addEventListener("click", () => {
      note.remove();
      action.run();
    });
    note.appendChild(act);
  }
  const close = elt("button", "notice-close", "\u2715");
  close.type = "button";
  close.setAttribute("aria-label", t("app.dismiss", "Dismiss"));
  close.addEventListener("click", () => note.remove());
  note.appendChild(close);
  host.appendChild(note);
  const life = timeout || (tone === "bad" ? 0 : 6000);
  if (life) setTimeout(() => note.remove(), life);
}

//: A real confirm, on the modal machinery above, so it inherits the focus handling and the inert
//: background rather than reimplementing them. Returns a promise, so every call site keeps the
//: shape it had with `confirm()` and only gains an `await`.
function confirmAction(message) {
  return new Promise((resolve) => {
    const overlay = document.getElementById("confirm-overlay");
    const yes = document.getElementById("confirm-yes");
    const no = document.getElementById("confirm-no");
    document.getElementById("confirm-text").textContent = message;
    const settle = (answer) => {
      yes.removeEventListener("click", onYes);
      no.removeEventListener("click", onNo);
      overlay.removeEventListener("keydown", onKey);
      closeModal(overlay);
      resolve(answer);
    };
    const onYes = () => settle(true);
    const onNo = () => settle(false);
    // Escape is "no". A destructive confirm that treats an interrupted gesture as consent is the
    // one dialog where the default must be the safe answer.
    const onKey = (event) => {
      if (event.key === "Escape") settle(false);
    };
    yes.addEventListener("click", onYes);
    no.addEventListener("click", onNo);
    overlay.addEventListener("keydown", onKey);
    openModal(overlay);
    // Focus lands on CANCEL, not on the destructive button, so a stray Enter cannot delete.
    no.focus({ preventScroll: true });
  });
}

let modalReturnFocus = null;
let modalInerted = [];

//: SIBLINGS, walking up - not the app shell. The first version set `.layout.inert = true`, and the
//: overlays live INSIDE `.layout`, so it made the dialog inert along with everything else: focus
//: fell to `<body>` and ten Tabs landed nowhere at all. Measured, not reasoned about; `inert` is
//: inherited by descendants, which is exactly what makes it the right tool and exactly what makes
//: "mark the ancestor" wrong.
//:
//: Every sibling at every level from the overlay up to `<body>` is marked, which leaves precisely
//: the overlay's own ancestor chain live. Remembered in a list so closing restores exactly what was
//: changed, rather than clearing `inert` from something that had it for another reason.
//: **Two siblings are NOT "the page behind", and inerting them broke things the overlay itself
//: needs.**
//:
//: `#notices` is where every toast lands. Inerted, a toast raised FROM a dialog is unreachable and
//: unannounced: its ✕ is dead (a click passes straight through to the dialog behind it) and a
//: screen reader never hears it, because `inert` removes the subtree from the accessibility tree
//: as well as from hit-testing. `notify` defaults to `tone: "bad"` with `life = 0`, so such a toast
//: never auto-dismisses either — it sits there, unreadable and undismissable, until the dialog
//: closes. `settings.saveFailed` is the only error the Settings dialog can raise and it takes
//: exactly that path.
//:
//: A panel's own BACKDROP is the other: `.traj-backdrop` carries `pointer-events: auto` and a
//: `closeTrajectory` click listener, and `inert` removes it from hit-testing — so click-outside-to-
//: close, which worked before focus management was added, silently stopped working while the CSS
//: and the listener both still promised it. Escape and ✕ still closed it, which is exactly why
//: nothing noticed.
//:
//: Neither is reachable by Tab, so sparing them gives back nothing the trap is for.
const ALWAYS_LIVE = "#notices";

function inertEverythingExcept(overlay, keep = []) {
  const spared = new Set([...document.querySelectorAll(ALWAYS_LIVE), ...keep].filter(Boolean));
  const touched = [];
  for (let node = overlay; node && node !== document.body; node = node.parentElement) {
    for (const sibling of node.parentElement ? node.parentElement.children : []) {
      if (sibling !== node && !sibling.inert && !spared.has(sibling)) {
        sibling.inert = true;
        touched.push(sibling);
      }
    }
  }
  return touched;
}

function openModal(overlay) {
  modalReturnFocus = document.activeElement;
  overlay.hidden = false;
  modalInerted = inertEverythingExcept(overlay);
  overlay.addEventListener("keydown", overlay._trap || (overlay._trap = (e) => trapTab(overlay, e)));
  // The first thing inside, so the reader is where the dialog is. Preferring a real control over
  // the close button, so Tab does not start at "leave" - and falling back to the dialog itself,
  // which carries `tabindex="-1"` for exactly this case (a body that has not loaded yet).
  const focusable = overlay.querySelector(
    "input, select, textarea, button:not(.modal-close), [tabindex]:not([tabindex='-1'])"
  );
  const target = focusable || overlay.querySelector(".modal-close") || overlay.querySelector(".modal");
  if (target) target.focus({ preventScroll: true });
}

//: Tab WRAPS at the dialog's edges. `inert` on everything outside keeps focus off the page, but it
//: does not close the cycle: tabbing past the last control inside still lands on the document for
//: one press, with no visible focus anywhere, before the browser comes back round. A reviewer
//: counted it at press 13 of a 22-press sweep. One press of nothing is small, and it is exactly the
//: kind of small that makes a dialog feel unfinished.
function trapTab(overlay, event) {
  if (event.key !== "Tab") return;
  const focusable = [...overlay.querySelectorAll(
    "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), " +
    "textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
  )].filter((el) => el.offsetParent !== null || el === document.activeElement);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function closeModal(overlay) {
  overlay.hidden = true;
  modalInerted.forEach((el) => {
    el.inert = false;
  });
  modalInerted = [];
  if (modalReturnFocus && typeof modalReturnFocus.focus === "function") {
    modalReturnFocus.focus({ preventScroll: true });
  }
  modalReturnFocus = null;
}

//: The fetch-and-render half, separated from the OPEN half. Re-rendering after an interface-language
//: change used to be done by clicking `#settings-open` again, which re-ran `openModal` on an already
//: open dialog: it re-recorded `modalReturnFocus` as the control it was about to destroy, re-inerted
//: everything, and left focus on `<body>`. Reloading is not opening.
async function loadSettings() {
  const body = document.getElementById("settings-body");
  body.textContent = t("cite.loading", "Loading…");
  try {
    // Fetched alongside the settings themselves, and tolerated failing: a row with no choices
    // falls back to free text, so a page that cannot reach this still works.
    settingsChoices = await api("/settings/choices").catch(() => ({}));
    const listed = await api("/orbits").catch(() => ({ orbits: [] }));
    settingsOrbits = (listed.orbits || []).map((o) => ({
      slug: o.slug,
      label: o.title || o.derived_title || t("app.untitled", "Untitled orbit"),
    }));
    renderSettings(await api("/settings"));
  } catch (err) {
    body.textContent = "";
    body.appendChild(failureBlock(t("settings.loadFailed", "Settings did not load"), err.message));
  }
}

function initSettings() {
  const overlay = document.getElementById("settings-overlay");
  const close = () => {
    // **The draft dies with the dialog.** `settingsDraft` is cleared inside `renderSettings`, which
    // is skipped when the reload fetch throws — so a draft could survive a failed reload, be
    // re-applied on the NEXT open and then saved, flipping `auto_distil` (the setting that decides
    // whether captures spend money) to a value the reader had abandoned. Narrow, and the fix is one
    // line at the only boundary that always runs.
    settingsDraft = null;
    closeModal(overlay);
  };

  document.getElementById("settings-open").addEventListener("click", async () => {
    closeSourceViewer(); // one overlay at a time — both carry z-index 1000, so DOM order would decide
    openModal(overlay);
    await loadSettings();
  });
  document.getElementById("settings-close").addEventListener("click", close);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) close();
  });
  // The source viewer's Escape handler is its own; without this one Escape would close that and
  // leave this open.
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !overlay.hidden) close();
  });
}

function initOrbitTitle() {
  const el = document.getElementById("orbit-title");
  const button = document.getElementById("orbit-current");
  // The header says whether the orbit you are LOOKING at is busy; the picker says which of the
  // others are. Between them "where is that generation I started" has an answer.
  const runDot = document.getElementById("orbit-run-dot");
  store.on("orbit:switched", syncRunGuards);
  store.on("runs:changed", () => {
    runDot.hidden = !activeRuns.has(state.orbitId);
    const menu = document.getElementById("orbit-menu");
    if (!menu.hidden) refreshOrbitList();
  });
  store.on("orbit:titled", ({ title, orbitId }) => {
    // textContent, never innerHTML - a title is model-authored text derived from source content
    // a prompt-injected source could influence (AGENTS.md invariants 6 and 29).
    //
    // The same CUT the picker row uses (`firstClause`), not the same RAW value. The old comment
    // here claimed they matched; they did not, and the difference was the biggest label on the
    // screen. No width cap: the header has room a 13rem rail does not, so the only thing removed is
    // the server's 60-character slice ending mid-word. The untruncated value goes on `title=`.
    const shown = title || firstClause(state.derivedTitle);
    el.textContent = orbitId
      ? shown || t("app.untitled", "Untitled orbit")
      : t("app.noOrbit", "No orbit yet");
    const full = title || state.derivedTitle || "";
    if (orbitId && full && full !== shown) el.title = full;
    else el.removeAttribute("title");
    if (document.body.dataset.view === "orbit") syncDocumentTitle(orbitId);
  });
}

function initOrbitSwitch() {
  const button = document.getElementById("orbit-current");
  const menu = document.getElementById("orbit-menu");

  button.addEventListener("click", (event) => {
    event.stopPropagation();
    const opening = menu.hidden;
    menu.hidden = !opening;
    button.setAttribute("aria-expanded", String(opening));
    if (opening) refreshOrbitList(); // always fresh: titles change, orbits appear
  });

  // Click-away and Escape both close it. Without these the panel stays open over the workspace and
  // the only way out is clicking the button again, which reads as broken.
  document.addEventListener("click", (event) => {
    if (!menu.hidden && !menu.contains(event.target)) closeOrbitMenu();
  });
  document.addEventListener("keydown", (event) => {
    //: Escape ALWAYS returns focus to the trigger, even when the reader had tabbed back out of the
    //: list: they pressed a key to dismiss this thing, so they are still here.
    if (event.key === "Escape" && !menu.hidden) closeOrbitMenu({ restoreFocus: true });
  });

  // **The wordmark is HOME.** It was labelled "Start a new orbit" and called
  // `resetToNewOrbit()`, which clears orbit state and never switches the view - so from the
  // Horizon it did nothing at all, and from an orbit it EMPTIED the orbit you were looking at
  // while leaving its id in the address bar. It is also the first tab stop. Starting an orbit
  // already has its own place, at the foot of the facet rail.
  // The Sources pane's file control, driven the way the Horizon's is.
  const sourceFile = document.getElementById("source-file");
  const sourcePick = document.getElementById("source-file-pick");
  if (sourceFile && sourcePick) {
    sourcePick.addEventListener("click", () => sourceFile.click());
    sourceFile.addEventListener("change", () => {
      // The chosen name, because a hidden input tells the reader nothing about what they picked.
      document.getElementById("source-file-name").textContent =
        sourceFile.files?.[0]?.name || "";
    });
  }

  // Home is the star map, not whichever Horizon view was last on screen: the list is a way of
  // reading the Horizon, the map is where the app starts.
  document.getElementById("new-orbit").addEventListener("click", () => {
    closeOrbitMenu();
    try {
      localStorage.setItem(MODE_KEYS.horizon, "map");
    } catch {
      /* storage blocked: the map is the default anyway */
    }
    showHorizon();
  });

  refreshOrbitList();
}

// Bumped by EVERY orbit switch (open or reset). Async renders that resolve after a switch must
// check it and drop their result: an independent review found three that didn't, and the new
// one-click wordmark made them trivially reachable — asking a question then switching had the
// answer's follow-up GET build `/orbits/null`, render `(error) 404 … 'null'` into the fresh
// blank orbit and kill the placeholder; the Guide fetch cached the OLD orbit's artifact
// UNDER the new one (so it reappeared on every later tab switch); and the podcast rendered the old
// episode after clearPlayer() had already run. The existing per-fetch guards (sourceViewerAbort,
// detailArea._requestToken) only protect against a newer request of the SAME kind, not against the
// orbit changing underneath.
let orbitGeneration = 0;

// A blank slate: no orbit selected, every panel cleared. Deliberately does NOT invent an id —
// `state.orbitId` stays null until the user names one (or, once auto-naming lands, until the
// first source is added), and every mutating call already refuses to run without one.

// --- Sources panel --------------------------------------------------------------------------------

// Built with createElement/textContent throughout, never innerHTML — `source.origin` is an
// ingested URL/path and, in principle, `source.flags` could one day carry excerpted source text
// (today's injection_scan.py flags don't, but nothing enforces that staying true), so nothing here
// assumes any of it is safe to treat as markup.
// A URL, shortened to what identifies it at a glance once the title is carrying the meaning.
function prettyOrigin(origin) {
  // Pasted text carries `pasted:{first 60 chars} #{hash}` as its origin. Rendered raw, a source row
  // read `pasted:Christopher Alexander, A Pattern Language: each pattern desc #8fe0a5cd` - a
  // sentence cut mid-word with a hash on the end. The Horizon already solved this; the same helper is
  // used here rather than a second one, so the two surfaces cannot drift apart.
  if (origin.startsWith("pasted:")) return pastedExcerpt(origin);
  try {
    const url = new URL(origin);
    const path = url.pathname === "/" ? "" : url.pathname;
    return url.hostname.replace(/^www\./, "") + path;
  } catch {
    return origin;
  }
}

function renderSourceItem(source) {
  const li = document.createElement("li");
  li.className = "source-item";
  // A DRAG THAT SELECTED SOMETHING WAS NEVER A PRESS. Same guard the Horizon row uses, and it is
  // what lets the whole row stay clickable while the description below stays selectable.
  li.addEventListener("click", (event) => {
    if (event.target.closest("button, a")) return;
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) return;
    showSourceViewer(source.id, null, null);
  });

  //: **THE HEAD IS A REAL BUTTON**, because the row was a bare `<li>` with a click handler: the
  //: only focusable control in it was the destructive ✕, so a keyboard user could DELETE a source
  //: and had no way at all to OPEN one. Two sibling rows had already been given a real control for
  //: exactly this reason - `.node-open` in the Horizon and `.ref-card-head` in the references - and
  //: this is the third row of the same kind, still unfixed. It reaches
  //: `GET /orbits/{id}/sources/{source_id}`, one of the three deliberate whole-document
  //: exposures (invariant 31), so "you can see it with a mouse" is the whole feature.
  //:
  //: The kicker, the title and the origin go INSIDE it - they are the row's identity, a few words
  //: each. `.src-description` and `.src-flags` stay outside, because a three-line description is
  //: prose a reader may want to select, which is the trap the Horizon's own comment records.
  const open = document.createElement("button");
  open.type = "button";
  open.className = "src-open";
  // Named by the source, not by "open": a rail of rows each announcing "Open" tells a screen-reader
  // user nothing about which one they are on.
  open.setAttribute(
    "aria-label",
    t("sources.open", `Open ${sourceDisplayName(source)}`, { name: sourceDisplayName(source) })
  );
  open.addEventListener("click", () => showSourceViewer(source.id, null, null));
  li.appendChild(open);

  const kind = document.createElement("div");
  kind.className = "src-kind";
  kind.textContent = kindLabel(source.kind);
  open.appendChild(kind);

  // A PREVIEW CARD when the page told us what it is: its own title, a line of its own description,
  // and its site name. Falls back to the bare origin, which is all a pasted-text or file source
  // has. Every value goes in through `textContent` — a page controls its own `<meta>` tags, so this
  // is attacker-influenceable display text (invariants 6 and 29), and it is never citable: the
  // corpus is built from `blocks` alone. Deliberately NO image: rendering `og:image` would make the
  // reader's browser fetch a URL the page author chose, handing that third party an IP and a
  // request to log, for a thumbnail.
  const preview = source.preview || {};
  if (preview.title) {
    const heading = document.createElement("div");
    heading.className = "src-title";
    heading.textContent = preview.title;
    //: Clamped to two lines, so the full title has to be reachable somehow. A NATIVE `title`, for
    //: the reason the facet rail gives: invariant 54 is about a tooltip host that clips its own
    //: tooltip, and this rail is exactly such a host (`overflow-y: auto`); the browser's own is not
    //: inside the scroller.
    heading.title = preview.title;
    open.appendChild(heading);
  }

  const origin = document.createElement("div");
  origin.className = "src-origin";
  // ALWAYS through the helper, not only when a preview happened to be scraped. The raw form was
  // reaching the panel on exactly the sources that have no preview: pasted text and local files.
  origin.textContent = prettyOrigin(source.origin);
  open.appendChild(origin);

  if (preview.description) {
    const description = document.createElement("div");
    description.className = "src-description";
    description.textContent = preview.description;
    li.appendChild(description);
  }

  if (source.flags && source.flags.length) {
    const flags = document.createElement("div");
    flags.className = "src-flags";
    // The flag is advisory and gates nothing (invariant 6), so it says what was seen and — via the
    // tooltip — what that means. It used to print the raw regex, which a user reasonably asked
    // about; a warning nobody can act on teaches people to ignore the ones that matter.
    flags.textContent = `\u26a0 ${source.flags.map(readableFlag).join(", ")}`;
    flags.dataset.tip = t(
      "sources.flagHelp",
      "Found in this source's own text, not in your question. It is not blocked and answers can still cite it. This is a heads-up that the source contains something that looks like an instruction to a model."
    );
    li.appendChild(flags);
  }

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "src-remove";
  remove.textContent = "\u2715\ufe0e";
  remove.dataset.tip = t("sources.remove", "Remove this source");
  remove.addEventListener("click", async (event) => {
    // The row itself opens the source viewer; without this the remove click would do both.
    event.stopPropagation();
    const ok = await confirmAction(
      // `sourceDisplayName`, not the raw origin: the list row two pixels away already shows the
      // readable name, and the dialog was printing `pasted:The note says ... #32c5d6b2`.
      t("sources.removeConfirm", `Remove "${sourceDisplayName(source)}" from this orbit?`, {
        origin: sourceDisplayName(source),
      })
    );
    if (!ok) return;
    remove.disabled = true;
    try {
      const orbit = await api(
        `/orbits/${encodeURIComponent(state.orbitId)}/sources/${encodeURIComponent(source.id)}`,
        { method: "DELETE" }
      );
      state.sources = orbit.sources;
      state.overview = orbit.overview || null;
      state.podcast = orbit.podcast || null;
      //: The TURNS too: the server re-verified every saved citation against the smaller corpus,
      //: and a turn still holding the old `verified: true` rendered — and Copied, and Exported —
      //: a citation to the removed source as checked. `chat:rerender` carries a running question
      //: (invariant 60); the podcast is re-stamped by `refreshReferenceView` rather than rebuilt,
      //: because rebuilding it would interrupt playback.
      state.turns = orbit.turns;
      // `sources:changed` is what marks the overview and podcast stale and re-offers the Guide
      // tabs — removing a source moves the corpus exactly as adding one does.
      store.emit("sources:changed", { sources: state.sources });
      store.emit("chat:rerender", {});
      renderChatOverview();
      refreshReferenceView();
    } catch (err) {
      remove.disabled = false;
      notify(t("err.removeSource", `Could not remove source: ${err.message}`, { message: err.message }));
    }
  });
  li.appendChild(remove);

  return li;
}

//: **A button that does nothing when pressed is a button that lied.** Add source and Add note both
//: returned silently on an empty field - no request, no notice, no disabled state - while the two
//: fields beside them, `#capture-send` and `#ask-submit`, correctly disable themselves. Two of four
//: doing it is the shape this project keeps finding.
//:
//: Which field counts depends on the open TAB, so this is re-run on a tab switch as well as on
//: typing. The file tab is satisfied by a chosen file, not by text.
function syncAddSourceSubmit() {
  const form = document.getElementById("add-source-form");
  if (!form) return;
  const tab = document.querySelector("#source-kind-tabs .tab.is-active");
  const kind = tab ? tab.dataset.kind : "url";
  const filled =
    kind === "file"
      ? !!(document.getElementById("source-file").files || []).length
      : !!(document.getElementById(kind === "url" ? "source-url" : "source-text").value || "").trim();
  const submit = form.querySelector("button[type=submit]");
  // Never re-enable mid-submit: `Adding…` disables it and the finally clause owns it from there.
  if (submit && submit.textContent !== t("sources.adding", "Adding\u2026")) submit.disabled = !filled;
}

function initSourcesPanel() {
  const tabs = [...document.querySelectorAll("#source-kind-tabs .tab")];
  //: A real tablist, like the Studio strip and the Guide strip. It carried which kind is current in
  //: a fill ALONE — three separate tab stops, no `aria-selected`, no arrow keys. See `showKind`.
  const showSourceKind = (kind) => {
    tabs.forEach((tab) => {
      const on = tab.dataset.kind === kind;
      tab.classList.toggle("is-active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    });
    document.querySelectorAll(".tab-body").forEach((kindBody) => {
      kindBody.hidden = kindBody.dataset.kindBody !== kind;
    });
    syncAddSourceSubmit();
  };
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => showSourceKind(tab.dataset.kind));
    tab.addEventListener("keydown", (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1, Home: -tabs.length, End: tabs.length }[event.key];
      if (step === undefined) return;
      event.preventDefault();
      const next = tabs[Math.min(tabs.length - 1, Math.max(0, tabs.indexOf(tab) + step))];
      showSourceKind(next.dataset.kind);
      next.focus();
    });
  });
  //: Once at init, so the strip starts as ONE tab stop. Without it every tab kept `tabindex="0"`
  //: until the first click and the roving contract was only half kept — which is the same shape as
  //: declaring a role and not fulfilling it.
  const active = tabs.find((tab) => tab.classList.contains("is-active")) || tabs[0];
  if (active) showSourceKind(active.dataset.kind);

  ["source-url", "source-text"].forEach((id) => {
    const field = document.getElementById(id);
    if (field) field.addEventListener("input", syncAddSourceSubmit);
  });
  const chosen = document.getElementById("source-file");
  if (chosen) chosen.addEventListener("change", syncAddSourceSubmit);
  syncAddSourceSubmit();

  const form = document.getElementById("add-source-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    // No orbit open? Make one. Demanding a name before the first source made the very first
    // interaction with this product a naming puzzle about a thing that didn't exist yet — the user
    // hit "Open or name an orbit first" and had to invent an id. The id is a handle now, not a
    // label: it is minted here, never shown as the primary name, and `suggestTitle()` below fills
    // in something readable once there is a source to derive it from.
    const isFirstSource = !state.orbitId;
    if (isFirstSource) {
      state.orbitId = `nb-${crypto.randomUUID().slice(0, 8)}`;
      // Already inside the slug whitelist, so it is its own slug until the
      // server confirms one on the next orbit response.
      state.orbitSlug = state.orbitId;
      orbitGeneration += 1;
    }
    const activeKind = document.querySelector("#source-kind-tabs .tab.is-active").dataset.kind;
    const nb = encodeURIComponent(state.orbitId);

    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    // Ingestion is a network fetch, a parse, and possibly OCR — seconds to tens of seconds, with
    // nothing on screen saying so. Disabling one button is not feedback: the panel simply stopped
    // responding, which a user described as feeling stuck. `is-busy` spins the button and dims the
    // form, so the pause reads as work rather than as a hang.
    form.classList.add("is-busy");
    const submitLabel = submitBtn.textContent;
    submitBtn.textContent = t("sources.adding", "Adding\u2026");
    try {
      let orbit;
      if (activeKind === "url") {
        const value = document.getElementById("source-url").value.trim();
        if (!value) return;
        orbit = await api(`/orbits/${nb}/sources`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sources: [value] }),
        });
        document.getElementById("source-url").value = "";
      } else if (activeKind === "text") {
        const value = document.getElementById("source-text").value.trim();
        if (!value) return;
        orbit = await api(`/orbits/${nb}/sources`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ texts: [value] }),
        });
        document.getElementById("source-text").value = "";
      } else {
        const fileInput = document.getElementById("source-file");
        const file = fileInput.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        // Deliberately no `headers` here — the browser must set its own multipart boundary,
        // which a manually-set Content-Type would break. `api()` never sets one itself (it's a
        // thin `fetch` wrapper; each JSON call site sets its own headers explicitly), so this
        // reuses it exactly as-is rather than needing a second, bespoke fetch call.
        orbit = await api(`/orbits/${nb}/sources/upload`, {
          method: "POST",
          body: formData,
        });
        fileInput.value = "";
        // The chosen-name label goes with it, or the pane keeps advertising a file it has sent.
        const chosen = document.getElementById("source-file-name");
        if (chosen) chosen.textContent = "";
      }
      state.sources = orbit.sources;
      state.title = orbit.title || state.title;
      state.derivedTitle = orbit.derived_title || state.derivedTitle;
      // **The overview and the podcast go STALE when the sources move, and this handler was not
      // reading them back.** The server had already flipped `overview.stale` in the response; the
      // page kept repainting the object it was still holding, whose `stale` was false, so the
      // header stayed "概覽" indefinitely and invariant 38's third state - "generated, but the
      // sources moved" - was unreachable without a reload. The REMOVE handler does both lines; only
      // the add path was missing them, which is why the comment below about the re-render flipping
      // it "on its own" was true on exactly one of the two paths.
      state.overview = orbit.overview || null;
      state.podcast = orbit.podcast || null;
      store.emit("sources:changed", { sources: state.sources });
      // ...and repaint it, the way the remove path does. Reading the stale flag back is only half
      // the fix if nothing draws it.
      renderChatOverview();
      store.emit("orbit:titled", { title: state.title, orbitId: state.orbitId });
      // Titling used to fire HERE, on the first source. That spent a real model call the moment
      // someone added a source, before they had asked for anything — a user called it too
      // aggressive and they were right. It now runs lazily, from `ensureTitle()`, which the
      // generate actions call: by then the user has already committed to a model run, so the
      // title costs nothing they were not already paying.
    } catch (err) {
      notify(t("err.addSource", `Could not add source: ${err.message}`, { message: err.message }));
    } finally {
      form.classList.remove("is-busy");
      submitBtn.textContent = submitLabel;
      // The label goes back FIRST, then the sync decides: the fields are cleared on success, so
      // re-enabling unconditionally would leave a primary button promising to add nothing.
      submitBtn.disabled = false;
      syncAddSourceSubmit();
    }
  });

  store.on("sources:changed", ({ sources }) => {
    const list = document.getElementById("source-list");
    const empty = document.getElementById("sources-empty");
    list.innerHTML = "";
    sources.forEach((source) => list.appendChild(renderSourceItem(source)));
    empty.hidden = sources.length > 0;
  });
}

// --- Chat panel -----------------------------------------------------------------------------------

// The signature interaction (blueprint §2.3): a citation is a highlighter stroke woven into the
// answer text, not a footnote number appended after it.
//
// Built with createElement/textContent/setAttribute throughout, NEVER innerHTML or a raw HTML
// string — `text` is the model's own answer prose and `citation.quote`/`source_id`/`locator` could
// in principle echo attacker-supplied content from a prompt-injected source (AGENTS.md invariant 6:
// a source's content is untrusted, and injection_scan.py's flags are advisory, not a filter). An
// early version of this function built a `<span title="...">` via string interpolation, which a
// `"` character inside `source_id`/`locator` could have broken out of; rewritten before this was
// ever shipped once that was noticed. Same discipline the sibling studios' own `app.js` files
// already enforce for exactly this reason (see penumbra/web/DESIGN.md's Do/Don't).
// `runId` is optional (Phase 1/2 call sites that predate the trace fusion, or a loaded turn saved
// before `ChatTurn.run_id` existed, pass nothing) — when given, each citation span becomes
// clickable and opens the References view at that entry (`focusReference`).
// The "+ Save as note" affordance, as a factory rather than a line inside
// `renderAnswerWithCitations`. NotebookLM's own model is that generated artifacts BECOME notes, and
// this project already has the whole mechanism (Note -> promote_note -> a real citable Source) —
// what it lacked was any way to get an overview into it.
//
// The rule this preserves (blueprint's Notes addendum, audit round 1): the button belongs to a CALL
// SITE that opts in, never to the shared renderer, which Guide tabs and the podcast transcript also
// use. The line is what the user is looking at when they click: things rendered IN the chat thread
// (an answer, the overview) are theirs to curate; a Studio tab's artifact and a podcast transcript
// are not part of that thread.
// A BOOKMARK in the answer's top-right corner, not a labelled button under the text. A full-width
// "+ Save as note" bar under every answer competed with the answer for attention and pushed the
// next turn down; a bookmark is the gesture people already know for "keep this", and it lives where
// they expect to find it. The label survives as the tooltip, so what it does is still one hover
// away — and it still says the part nobody could guess (promotion is what makes a note citable).
//: **The product had no way to hand you the thing it exists to produce.** `README.md` and
//: `AGENTS.md` both describe the purpose as "get a distilled research artifact out the other end",
//: and the only export in 8,000 lines was the podcast's download link: no copy on an answer, on the
//: overview or on a Guide kind, no orbit export, and `@media print` matched zero rules, so
//: Cmd+P printed the three-column app shell. The one remaining route — select and copy — was itself
//: broken by the citation click handler firing on the mouseup that ends a drag.
//:
//: Markdown, because that is what the reader will paste into: the prose as the model wrote it
//: (markers are already stripped server-side, invariant 62) followed by the SAME numbered reference
//: list the panel shows, so a pasted artifact carries its evidence rather than bare assertions.
//: **A printed page carried numbered marks and no list to look them up in.** `@media print` hides
//: `.col-studio` — rightly, it is chrome — and `#panel-references` lives inside it, while
//: `.citation::after` kept printing its number. The stylesheet's own comment claimed "the
//: references print with it". Un-hiding the panel cannot fix it: the panel is only BUILT while its
//: view is showing, so what printed would depend on which tab the reader last clicked.
//:
//: So the list is built at `beforeprint` from `collectReferences()` — the same order every stroke
//: on the page was stamped from, so `[3]` on paper is entry 3 — and removed at `afterprint`.
function printReferenceList() {
  const refs = collectReferences();
  if (!refs.length) return null;
  const section = elt("section", "print-references");
  section.appendChild(elt("h2", null, t("copy.references", "References")));
  const list = elt("ol");
  refs.forEach((ref) => {
    const source = (state.sources || []).find((s) => s.id === ref.source_id);
    const where = ref.locator && ref.locator !== "whole" ? ` · ${ref.locator}` : "";
    const item = elt("li", null, `${source ? sourceLabel(source) : ref.source_id}${where}`);
    // Not `<em>`: most CJK faces have no italic, so the browser slants the glyphs itself, and a
    // synthesised oblique 未驗證 reads as a rendering fault on paper. Weight carries it instead.
    if (ref.verified === false) {
      item.appendChild(elt("span", "print-unverified", t("copy.unverifiedTag", " (unverified)")));
    }
    if (ref.quote) item.appendChild(elt("blockquote", null, ref.quote));
    list.appendChild(item);
  });
  section.appendChild(list);
  return section;
}

function installPrintReferences() {
  let printed = null;
  let titled = null;
  window.addEventListener("beforeprint", () => {
    printed?.remove();
    printed = null;
    //: Only an orbit has references; the Horizon prints as the Horizon.
    if (document.body.dataset.view !== "orbit") return;
    printed = printReferenceList();
    const history = document.getElementById("chat-history");
    if (printed) history?.appendChild(printed);
    //: **The title.** The only place an orbit's name appears is the header, which print hides,
    //: so a printed orbit began with the panel label "CHAT". The document title already holds
    //: the name the reader sees.
    titled?.remove();
    titled = elt("h1", "print-title", state.title || state.derivedTitle || document.title);
    history?.prepend(titled);
  });
  window.addEventListener("afterprint", () => {
    printed?.remove();
    printed = null;
    titled?.remove();
    titled = null;
  });
}

//: **One line, always, for anything placed inside a Markdown list item.** A pasted-text source's
//: label is its opening words, blank lines included, so `1. Alpha…\n\nBeta…` ended the list item
//: and orphaned the quote beneath it — on the capture path the product leads with. A quote spanning
//: lines broke its blockquote the same way.
function markdownInline(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function referenceListMarkdown(citations) {
  const order = new Map(collectReferences().map((ref, i) => [referenceKey(ref), i + 1]));
  const seen = new Map();
  (citations || []).forEach((citation) => {
    const n = order.get(referenceKey(citation));
    if (n && !seen.has(n)) seen.set(n, citation);
  });
  return [...seen.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([n, citation]) => {
      const source = (state.sources || []).find((s) => s.id === citation.source_id);
      const name = markdownInline(source ? sourceLabel(source) : citation.source_id);
      //: `whole` means "this source has one block" and is noise in a citation, exactly as it is in
      //: the hover label.
      const where = citation.locator && citation.locator !== "whole" ? ` · ${citation.locator}` : "";
      const quote = citation.quote ? `\n   > ${markdownInline(citation.quote)}` : "";
      const unverified = citation.verified === false ? ` *(${t("copy.unverified", "unverified")})*` : "";
      return `${n}. ${name}${where}${unverified}${quote}`;
    })
    .join("\n");
}

function artifactMarkdown(text, citations, heading) {
  const refs = referenceListMarkdown(citations);
  const head = heading ? `## ${heading}\n\n` : "";
  const body = `${head}${(text || "").trim()}\n`;
  return refs ? `${body}\n### ${t("copy.references", "References")}\n\n${refs}\n` : body;
}

//: One control, used on every artifact surface. It reports back IN PLACE rather than through a
//: toast: the reader is looking at the thing they just copied.
//: The whole orbit as one document — the "research artifact" the README promises, which the
//: product could not previously hand over in any form. Built entirely from `state`, so it costs
//: nothing and works offline; a Blob download rather than the clipboard, because an orbit with
//: twenty-five turns is not something anyone pastes.
function orbitMarkdown() {
  const title = state.title || state.derivedTitle || t("app.untitled", "Untitled orbit");
  const out = [`# ${title}`, ""];

  const sources = state.sources || [];
  if (sources.length) {
    out.push(`## ${t("sources.head", "Sources")}`, "");
    //: The ORIGIN only when it is somewhere a reader can go. A pasted source's origin is the
    //: internal `pasted:<opening words> #<hash>` form the interface hides everywhere else, and its
    //: label already is those opening words.
    sources.forEach((source, i) => {
      const where = (source.origin || "").startsWith("pasted:") ? "" : `: ${source.origin}`;
      out.push(`${i + 1}. ${markdownInline(sourceLabel(source))}${where}`);
    });
    out.push("");
  }

  if (state.overview && state.overview.text) {
    out.push(artifactMarkdown(state.overview.text, state.overview.citations,
                              t("chat.overview", "Overview")), "");
  }

  const turns = state.turns || [];
  if (turns.length) {
    out.push(`## ${t("chat.head", "Conversation")}`, "");
    turns.forEach((turn) => {
      out.push(`### ${turn.question}`, "");
      out.push(artifactMarkdown(turn.answer, turn.citations, null), "");
    });
  }

  const notes = state.notes || [];
  if (notes.length) {
    out.push(`## ${t("notes.head", "Notes")}`, "");
    notes.forEach((note) => out.push(`- ${note.text}`));
    out.push("");
  }
  return out.join("\n");
}

function downloadOrbitMarkdown() {
  const title = state.title || state.derivedTitle || state.orbitId || "orbit";
  //: Slugged, not interpolated: a model-authored title reaches a filename here, and `download` is
  //: an attribute the browser turns into a path component (the same reasoning the podcast uses).
  const stem =
    title.replace(/[^\w\u4e00-\u9fff-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "orbit";
  const blob = new Blob([orbitMarkdown()], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${stem}.md`;
  link.click();
  //: Revoked on the next frame: revoking synchronously can cancel the download in WebKit, which is
  //: the engine the planned Tauri shell uses on macOS.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function copyButton(getMarkdown) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "copy-artifact";
  const label = t("copy.action", "Copy");
  btn.textContent = "\u29c9";  // U+29C9 TWO JOINED SQUARES — geometric, never emoji
  btn.setAttribute("aria-label", label);
  btn.dataset.tip = t("copy.help", "Copy this and its references as Markdown");
  btn.addEventListener("click", async (event) => {
    event.stopPropagation();
    const before = btn.dataset.tip;
    try {
      await navigator.clipboard.writeText(getMarkdown());
      btn.dataset.tip = t("copy.done", "Copied");
      btn.classList.add("is-done");
    } catch {
      //: A clipboard write can be refused (no permission, an insecure origin). Saying so beats a
      //: control that looks like it worked.
      btn.dataset.tip = t("copy.failed", "Could not copy. Select the text and copy it yourself.");
    }
    setTimeout(() => {
      btn.dataset.tip = before;
      btn.classList.remove("is-done");
    }, 1600);
  });
  return btn;
}

function saveAsNoteButton(text) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "save-as-note";
  btn.setAttribute("aria-label", t("chat.saveAsNote", "Save as note"));
  btn.textContent = "\u2606";  // U+2606 WHITE STAR — geometric, never emoji (see the theme toggle)
  btn.dataset.tip = t(
    "chat.saveAsNoteHelp",
    "Keep a copy in Notes, in the Studio on the right. Promote a note into a source later and your questions can cite it."
  );
  btn.addEventListener("click", async (event) => {
    event.stopPropagation();
    btn.disabled = true;
    try {
      await addNote(text);
      btn.classList.add("is-saved");
      btn.textContent = "\u2605";  // filled
      btn.dataset.tip = t("chat.saved", "Saved to Notes");
    } finally {
      setTimeout(() => {
        btn.classList.remove("is-saved");
        btn.textContent = "\u2606";
        btn.disabled = false;
        btn.dataset.tip = t(
          "chat.saveAsNoteHelp",
          "Keep a copy in Notes, in the Studio on the right. Promote a note into a source later and your questions can cite it."
        );
      }, 1800);
    }
  });
  return btn;
}

// --- Markdown ---------------------------------------------------------------------------------
//
// A deliberately SMALL subset, HAND-WRITTEN, built entirely with `createElement`/`textContent`.
// Answers arrived full of raw `**bold**`, `## headings` and `- lists` because the model writes
// markdown whether or not anyone asked it to, and we were rendering the source text verbatim.
//
// No library, and no `innerHTML` with an interpolated string — the same discipline a sibling
// studio states outright for the same reason: every string here came out of a model that has been
// reading source content an attacker may have written (invariants 6 and 29). The sibling studios
// build markup as HTML strings with an `esc()` helper; one missed `esc()` there is an XSS sink, and
// building nodes removes the failure mode rather than guarding it.
//
// **A link is rendered but NOT navigable**, and that is the one place this diverges from what a
// markdown renderer usually does. Invariant 1 refuses to let the model reach a URL because a
// prompt-injected source could steer it into exfiltrating orbit contents to an address of the
// attacker's choosing; an `<a href>` in an answer is the same hazard with the reader's click as the
// transport, and it would arrive looking exactly like a citation-grounded reference. The URL is
// shown on hover and COPIED on click, so reaching it stays a deliberate act with an address the
// reader has seen. One line to flip if that trade stops being worth it.
//
// Every block callback receives RAW OFFSETS into the original string and appends through `emit`,
// never by creating text nodes itself. That is what keeps the citation strokes exact: `emit` is
// where a highlighted range is split out, so markdown structure and citation ranges compose instead
// of one having to be applied on top of the other's output.

const MD_FENCE = /^\s*(```|~~~)/;
const MD_HEADING = /^(#{1,6})\s+(.*)$/;
const MD_QUOTE = /^\s*>\s?(.*)$/;
const MD_BULLET = /^(\s*)([-*+])\s+(.*)$/;
const MD_ORDERED = /^(\s*)(\d{1,9})[.)]\s+(.*)$/;
const MD_RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const MD_TABLE_DIVIDER = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/;

//: Inline markers, longest-first so `**` is tried before `*`.
const MD_INLINE = [
  { open: "`", close: "`", tag: "code", className: "md-code" },
  { open: "**", close: "**", tag: "strong" },
  { open: "__", close: "__", tag: "strong" },
  // GFM strikethrough. Models write it ("~~chunk size~~ matters less than overlap"), and printed
  // raw, the tildes read as noise and the retraction the writer meant is lost.
  { open: "~~", close: "~~", tag: "del" },
  { open: "*", close: "*", tag: "em" },
  { open: "_", close: "_", tag: "em" },
];

function mdLines(text) {
  const out = [];
  let start = 0;
  for (const line of text.split("\n")) {
    out.push({ text: line, start, end: start + line.length });
    start += line.length + 1;
  }
  return out;
}

// `[label](url)` — the label's raw range, plus the url as plain text.
function mdLinkAt(text, at, limit) {
  if (text[at] !== "[") return null;
  const close = text.indexOf("]", at + 1);
  if (close === -1 || close >= limit || text[close + 1] !== "(") return null;
  const end = text.indexOf(")", close + 2);
  if (end === -1 || end >= limit) return null;
  return { labelFrom: at + 1, labelTo: close, url: text.slice(close + 2, end), end: end + 1 };
}

//: A simplified CommonMark "flanking" rule, and it is not pedantry: without it `3 * 4 * 5` becomes
//: `3 <em>4</em> 5` and `my_var and other_var_name` becomes `my<em>var and other</em>var_name`.
//: Multiplication and snake_case identifiers both appear in this project's own subject matter.
//: Backticks are exempt — code spans have no flanking rule in CommonMark either.
const mdIsSpace = (ch) => !ch || /\s/.test(ch);
const mdIsWord = (ch) => !!ch && /[\w\u00c0-\uffff]/.test(ch);

function mdMarkerOpens(text, marker, at) {
  if (marker.tag === "code") return true;
  // An opener must hug its content: `* 4` is a bullet or a multiplication, never emphasis.
  if (mdIsSpace(text[at + marker.open.length])) return false;
  // `_` additionally never opens inside a word, which is what protects `snake_case`.
  if (marker.open.startsWith("_")) return !mdIsWord(text[at - 1]);
  return true;
}

function mdMarkerCloses(text, marker, at) {
  if (marker.tag === "code") return true;
  if (mdIsSpace(text[at - 1])) return false;
  if (marker.close.startsWith("_")) return !mdIsWord(text[at + marker.close.length]);
  return true;
}

//: The first VALID closing marker at or after `from`, or -1.
function mdFindClose(text, marker, from, limit) {
  let at = text.indexOf(marker.close, from);
  while (at !== -1 && at < limit) {
    if (at > from && mdMarkerCloses(text, marker, at)) return at;
    at = text.indexOf(marker.close, at + 1);
  }
  return -1;
}

function renderInline(parent, text, from, to, emit) {
  let cursor = from;
  let plain = from;
  const flush = (upTo) => {
    if (upTo > plain) emit(parent, plain, upTo);
  };

  while (cursor < to) {
    const link = mdLinkAt(text, cursor, to);
    if (link) {
      flush(cursor);
      const span = document.createElement("span");
      span.className = "md-link";
      // Shown, never navigable — see the note at the top of this section.
      span.dataset.tip = link.url;
      // ...and COPYABLE, which the tooltip alone is not: `[data-tip]::after` is CSS generated
      // content, which no browser lets you select, and it only appears on hover — so an
      // independent review found the "see and copy it deliberately" affordance half-missing and
      // unreachable by keyboard or touch entirely. A click copies; `tabindex` makes it reachable.
      // Still not navigable: this writes to the clipboard, it never follows anything.
      span.tabIndex = 0;
      span.setAttribute("role", "button");
      const copyUrl = () => {
        navigator.clipboard?.writeText(link.url).then(
          () => {
            const was = span.dataset.tip;
            span.dataset.tip = t("md.urlCopied", "Link address copied");
            setTimeout(() => {
              span.dataset.tip = was;
            }, 1400);
          },
          () => {},
        );
      };
      span.addEventListener("click", copyUrl);
      span.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          copyUrl();
        }
      });
      renderInline(span, text, link.labelFrom, link.labelTo, emit);
      parent.appendChild(span);
      cursor = plain = link.end;
      continue;
    }

    const marker = MD_INLINE.find(
      (m) =>
        text.startsWith(m.open, cursor)
        && mdMarkerOpens(text, m, cursor)
        && mdFindClose(text, m, cursor + m.open.length, to) !== -1
    );
    if (marker) {
      const innerFrom = cursor + marker.open.length;
      const closeAt = mdFindClose(text, marker, innerFrom, to);
      // A marker whose partner is past this block, or which wraps nothing, is literal text.
      if (closeAt !== -1 && closeAt < to && closeAt > innerFrom) {
        flush(cursor);
        const node = document.createElement(marker.tag);
        if (marker.className) node.className = marker.className;
        if (marker.tag === "code") {
          // Inline code is verbatim by definition: no nested inline parsing, but still emitted
          // through `emit` so a citation stroke can cross it.
          emit(node, innerFrom, closeAt);
        } else {
          renderInline(node, text, innerFrom, closeAt, emit);
        }
        parent.appendChild(node);
        cursor = plain = closeAt + marker.close.length;
        continue;
      }
    }
    cursor += 1;
  }
  flush(to);
}

function mdTableRowCells(line) {
  const trimmed = line.text.trim().replace(/^\|/, "").replace(/\|$/, "");
  const cells = [];
  let from = line.start + line.text.indexOf(trimmed);
  for (const piece of trimmed.split("|")) {
    // Each cell's own padding is trimmed OFF THE RANGE rather than off a string, so the offsets
    // still point at the original text and a citation stroke inside a cell lands correctly.
    const lead = piece.length - piece.trimStart().length;
    const tail = piece.length - piece.trimEnd().length;
    cells.push({ from: from + lead, to: from + piece.length - tail });
    from += piece.length + 1;
  }
  return cells;
}

// Renders `text` into `root` as blocks. `emit(parent, from, to)` appends the raw slice, and owns
// citation splitting.
function renderMarkdownInto(root, text, emit) {
  const lines = mdLines(text);
  let i = 0;

  const startsTable = (index) =>
    index + 1 < lines.length
    && lines[index].text.includes("|")
    && MD_TABLE_DIVIDER.test(lines[index + 1].text);

  const isBlockStart = (line, index) =>
    !line.text.trim()
    || MD_FENCE.test(line.text)
    || MD_HEADING.test(line.text)
    || MD_QUOTE.test(line.text)
    || MD_BULLET.test(line.text)
    || MD_ORDERED.test(line.text)
    || MD_RULE.test(line.text)
    // Without this a table written directly under a sentence — no blank line, which is how people
    // actually write one — was swallowed by the paragraph and its pipes shown raw, the exact
    // symptom this renderer exists to remove.
    || startsTable(index);

  while (i < lines.length) {
    const line = lines[i];

    if (!line.text.trim()) {
      i += 1;
      continue;
    }

    if (MD_FENCE.test(line.text)) {
      const fence = line.text.trim().slice(0, 3);
      const body = [];
      i += 1;
      while (i < lines.length && !lines[i].text.trim().startsWith(fence)) {
        body.push(lines[i]);
        i += 1;
      }
      i += 1; // the closing fence, or the end of the text
      const pre = document.createElement("pre");
      pre.className = "md-pre";
      const code = document.createElement("code");
      if (body.length) emit(code, body[0].start, body[body.length - 1].end);
      pre.appendChild(code);
      root.appendChild(pre);
      continue;
    }

    if (MD_RULE.test(line.text)) {
      root.appendChild(document.createElement("hr"));
      i += 1;
      continue;
    }

    const heading = line.text.match(MD_HEADING);
    if (heading) {
      // Shifted down two levels (h1..h6 -> h3..h6): these sit INSIDE a chat bubble, so an `<h1>`
      // would outrank the panel's own heading and read as a page title.
      const level = Math.min(6, 2 + heading[1].length);
      const node = document.createElement(`h${level}`);
      node.className = "md-head";
      const from = line.start + line.text.indexOf(heading[2], heading[1].length);
      renderInline(node, text, from, line.end, emit);
      root.appendChild(node);
      i += 1;
      continue;
    }

    if (MD_QUOTE.test(line.text)) {
      const quote = document.createElement("blockquote");
      quote.className = "md-quote";
      while (i < lines.length && MD_QUOTE.test(lines[i].text)) {
        const inner = lines[i].text.match(MD_QUOTE);
        const para = document.createElement("p");
        const from = lines[i].start + lines[i].text.length - inner[1].length;
        renderInline(para, text, from, lines[i].end, emit);
        quote.appendChild(para);
        i += 1;
      }
      root.appendChild(quote);
      continue;
    }

    if (MD_BULLET.test(line.text) || MD_ORDERED.test(line.text)) {
      i = renderMdList(root, lines, i, text, emit, 0);
      continue;
    }

    // A GitHub pipe table needs its divider row to be a table at all; without it the pipes are
    // ordinary text and rendering a table would invent structure the model did not write.
    if (startsTable(i)) {
      const table = document.createElement("table");
      table.className = "md-table";
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      mdTableRowCells(line).forEach((cell) => {
        const th = document.createElement("th");
        renderInline(th, text, cell.from, cell.to, emit);
        headRow.appendChild(th);
      });
      head.appendChild(headRow);
      table.appendChild(head);
      const body = document.createElement("tbody");
      i += 2;
      // A row must LOOK like one: leading pipe, or at least as many separators as the header has
      // columns. Otherwise ordinary prose that happens to contain a pipe was pulled into the table.
      const columns = mdTableRowCells(line).length;
      const leadingPipe = line.text.trim().startsWith("|");
      // Matched against the HEADER's own shape: a header that opens with `|` means every row does,
      // which is what keeps ordinary prose containing a single pipe out of the table.
      const looksLikeRow = (l) =>
        (leadingPipe ? l.text.trim().startsWith("|") : true)
        && (l.text.match(/\|/g) || []).length >= columns - 1;
      while (i < lines.length && lines[i].text.trim() && looksLikeRow(lines[i])) {
        const row = document.createElement("tr");
        mdTableRowCells(lines[i]).forEach((cell) => {
          const td = document.createElement("td");
          renderInline(td, text, cell.from, cell.to, emit);
          row.appendChild(td);
        });
        body.appendChild(row);
        i += 1;
      }
      table.appendChild(body);
      const scroller = document.createElement("div");
      scroller.className = "md-table-wrap";
      scroller.appendChild(table);
      root.appendChild(scroller);
      continue;
    }

    // Paragraph: everything up to a blank line or the next block starter.
    const para = document.createElement("p");
    para.className = "md-p";
    const from = line.start;
    let last = line;
    i += 1;
    while (i < lines.length && !isBlockStart(lines[i], i)) {
      last = lines[i];
      i += 1;
    }
    renderInline(para, text, from, last.end, emit);
    root.appendChild(para);
  }
}

// Lists, one nesting level at a time. `indent` is the column the current level starts at, so a
// deeper item opens a nested list and a shallower one ends this call.
function renderMdList(root, lines, start, text, emit, indent) {
  const ordered = !lines[start].text.match(MD_BULLET);
  const list = document.createElement(ordered ? "ol" : "ul");
  list.className = "md-list";
  let i = start;

  while (i < lines.length) {
    const line = lines[i];
    const match = line.text.match(MD_BULLET) || line.text.match(MD_ORDERED);
    if (!match) break;
    const depth = match[1].length;
    if (depth < indent) break;
    if (depth > indent) {
      // A level whose first item is already indented has no `<li>` to nest under, and appending to
      // the list itself produced `<ul>` directly inside `<ul>` — invalid, and it renders unindented.
      let host = list.lastElementChild;
      if (!host) {
        host = document.createElement("li");
        list.appendChild(host);
      }
      i = renderMdList(host, lines, i, text, emit, depth);
      continue;
    }
    const item = document.createElement("li");
    const body = match[match.length - 1];
    const from = line.start + line.text.length - body.length;
    renderInline(item, text, from, line.end, emit);
    list.appendChild(item);
    i += 1;
  }
  root.appendChild(list);
  return i;
}

function renderAnswerWithCitations(text, citations, runId) {
  const container = document.createElement("div");

  // Numbered from the ORBIT-WIDE reference list, not per artifact. This comment used to claim
  // that "this sentence" and "reference 2" are visibly the same thing while the code counted 1..n
  // within each artifact separately: an overview citing two sources numbered them 1 and 2, the next
  // chat answer numbered ITS first citation 1 again, and the References panel — which numbers the
  // deduped whole — called that one 3. Every artifact after the first disagreed with the panel it
  // points into. `collectReferences` is the single ordering both ends now read.
  const order = new Map(collectReferences().map((ref, i) => [referenceKey(ref), i + 1]));
  // Fallback for a citation not yet in `state` (an artifact rendered before its state assignment).
  // 0 renders no number at all, which is the honest outcome — better than a number that points at
  // the wrong row.
  const referenceNumberFor = (citation) => order.get(referenceKey(citation)) || 0;

  // Locate each citation's quote as a literal substring of the RAW answer text (never
  // pre-escaped — a DOM text node needs no escaping, only innerHTML does). The model may
  // paraphrase around a quote rather than reproducing it verbatim; when a quote can't be located,
  // the citation still surfaces in the citation list below, just not inline.
  const matches = [];
  citations.forEach((citation) => {
    // `answer_span` FIRST: the model's own words, in the reader's language, already confirmed
    // server-side to occur in this exact text (`citations.locate_answer_spans`). `quote` is the
    // fallback for turns saved before that field existed — it only ever matched when the answer and
    // the source shared a language, which stopped being the common case at invariant 39, and that
    // is why the strokes vanished.
    const needle = citation.answer_span || citation.quote;
    if (!needle) return;
    const at = text.indexOf(needle);
    if (at !== -1) matches.push({ start: at, end: at + needle.length, citation });
  });
  matches.sort((a, b) => a.start - b.start);
  // Overlapping spans: keep the first, drop the rest. Done HERE rather than inside `emit`, which
  // walks ranges per text run and would otherwise have to re-decide the same thing every time.
  const ranges = [];
  matches.forEach((match) => {
    if (ranges.length && match.start < ranges[ranges.length - 1].end) return;
    ranges.push(match);
  });

  // Every fragment emitted for a given citation, so the reference number can be stamped on the LAST
  // one after the whole answer is built. Deciding "is this the last fragment" inside `emit` — the
  // first version's `sliceTo === match.end` — is wrong whenever a span's final characters are
  // markdown syntax the renderer DROPS (a closing `**`, a backtick, a link's `](url)`): no emit
  // call ever reaches `match.end`, so no fragment qualified and the stroke got NO number at all,
  // while the References panel numbered it anyway. Found by an independent review fuzzing the
  // renderer; the invariant even reasoned about this line and had the direction backwards, since
  // duplicate numbers were the risk it guarded and zero numbers was the one that happened.
  const fragments = new Map();

  const strokeFor = (match, slice) => {
    const span = document.createElement("span");
    span.className = match.citation.verified ? "citation" : "citation is-unverified";
    // A number, so a stroke can be matched to its entry in the reference list below — and so the
    // page reads as annotated prose rather than as a block of highlighter. Set as a CSS counter
    // rather than injected text, which keeps the answer's own words exactly as the model wrote
    // them (a copy-paste must not pick up UI furniture). Only the LAST fragment carries it: a
    // stroke crossing an inline `**bold**` is emitted as more than one span, and every fragment
    // carrying the number would print it two or three times. Stamped after the render, below.
    const seen = fragments.get(match) || [];
    seen.push(span);
    fragments.set(match, seen);
    // The coordinate this stroke points at, so `focusReference` can light up every stroke sharing
    // it. `.citation.is-focused` has been in the stylesheet promising that since the References
    // view landed, with nothing ever setting it — found by an independent review.
    span.dataset.refKey = referenceKey(match.citation);
    // The SOURCE, not the raw coordinate. It used to read `s1 · whole`, which is the interface's
    // own filing system — a user pointed out that nobody can tell what `s1` is. `sourceLabel` is
    // the same title the reference card shows, so hovering a stroke and reading its row agree.
    // The locator is appended only when it says something a reader can use (a page, a timestamp);
    // `whole` means "this source has one block" and is pure noise here.
    span.title = citationHoverLabel(match.citation);
    span.textContent = slice;
    // The other half of the reciprocal highlight: pointing at a stroke lights up its reference row,
    // exactly as pointing at the row lights up the stroke. Registered whether or not the stroke is
    // clickable — a reader hovering prose is asking "which source is this", and the answer should
    // not depend on whether the turn happens to carry a run id.
    const key = referenceKey(match.citation);
    span.addEventListener("mouseenter", () => linkReference(key, true));
    span.addEventListener("mouseleave", () => linkReference(key, false));
    //: **The reciprocal highlight on FOCUS as well as hover.** Everything below is what makes this
    //: reachable without a mouse; leaving the lighting-up on `mouseenter` alone would hand a
    //: keyboard reader the destination and not the answer to "which source is this".
    span.addEventListener("focus", () => linkReference(key, true));
    span.addEventListener("blur", () => linkReference(key, false));
    if (runId) {
      span.classList.add("citation-clickable");
      //: **A `click` listener is not an affordance.** `DESIGN.md` §2 calls this stroke "the literal
      //: visual expression of the product's core value" and it was mouse-only: no `tabindex`, no
      //: `role`, no key handler. A recorded Tab walk of a whole orbit — 37 stops — reached not
      //: one citation, and a screen reader read it as ordinary prose that happened to do nothing.
      //: That is SC 2.1.1 (Keyboard) and SC 4.1.2 (Name, Role, Value), both Level A, on the one
      //: interaction the product is about. At rest the only thing marking a clickable stroke was
      //: `cursor: pointer` and a hover filter — neither of which exists for a keyboard OR on touch.
      //:
      //: The same pattern the markdown link's copy affordance already uses, and for the same reason
      //: an independent review gave there: `tabindex` makes it reachable, `role` says what it is,
      //: and Enter/Space do what a click does.
      span.tabIndex = 0;
      span.setAttribute("role", "button");
      const open = () => focusReference(match.citation);
      //: **`click` also fires on the mouseup that ends a drag-selection.** Selecting an answer to
      //: quote it therefore switched the Studio to References mid-drag — and select-and-copy is the
      //: only way a reader currently gets prose out of this product at all. The podcast transcript's
      //: line handler has had exactly this guard, with exactly this argument, since it shipped; this
      //: surface is the one it was never applied to. `getSelection`, not a pixel threshold: it
      //: answers the actual question.
      const openUnlessSelecting = () => {
        const selection = window.getSelection();
        if (selection && !selection.isCollapsed && selection.toString().trim()) return;
        open();
      };
      // Opens the References view and takes the reader to that entry, rather than expanding a
      // panel inside the paragraph they are reading — which pushed the rest of the answer down and
      // made a crowded column worse.
      span.addEventListener("click", openUnlessSelecting);
      span.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      });
    }
    return span;
  };

  // The ONE place raw text becomes nodes. The markdown renderer hands it raw offsets and never
  // creates a text node itself, which is what lets block structure and citation ranges compose:
  // a stroke that crosses a heading boundary or an inline marker is split here, not lost.
  const emit = (parent, from, to) => {
    if (to <= from) return;
    let cursor = from;
    ranges.forEach((match) => {
      if (match.end <= cursor || match.start >= to) return;
      const sliceFrom = Math.max(match.start, cursor);
      const sliceTo = Math.min(match.end, to);
      if (sliceFrom > cursor) {
        parent.appendChild(document.createTextNode(text.slice(cursor, sliceFrom)));
      }
      parent.appendChild(strokeFor(match, text.slice(sliceFrom, sliceTo)));
      cursor = sliceTo;
    });
    if (cursor < to) parent.appendChild(document.createTextNode(text.slice(cursor, to)));
  };

  renderMarkdownInto(container, text, emit);

  // Exactly one number per citation, on its last fragment — decided here, where every fragment is
  // known, rather than guessed at while emitting.
  fragments.forEach((spans, match) => {
    const n = referenceNumberFor(match.citation);
    // Absent, not "0": `content: attr(data-reference)` renders the literal character, so a 0 puts a
    // superscript zero next to the prose instead of the "no number at all" this fallback claims.
    //: `strokeEnd` marks WHICH fragment may carry the number, so `renumberStrokes` can re-stamp
    //: it later without stamping every fragment — which it did, printing ¹a ¹parametric¹.
    spans[spans.length - 1].dataset.strokeEnd = "";
    if (n) spans[spans.length - 1].dataset.reference = String(n);
    //: **ONE tab stop per citation, not one per fragment.** A stroke crossing an inline `**` is
    //: emitted as several spans, and making every stroke operable turned one reference into three
    //: identical-sounding buttons — two of them announcing no number at all, because only the last
    //: fragment carries `data-reference`. Visually they join into one mark and only one superscript
    //: renders, so this was keyboard-only, and it arrived with the keyboard fix itself.
    //:
    //: The LAST fragment keeps the stop, because that is the one the number is on. The others stay
    //: hoverable and clickable — a mouse reader points at a word, not at a fragment — and leave the
    //: accessibility tree alone.
    spans.slice(0, -1).forEach((span) => {
      if (!span.classList.contains("citation-clickable")) return;
      span.tabIndex = -1;
      span.removeAttribute("role");
      span.setAttribute("aria-hidden", "true");
    });
  });

  if (citations.length) {
    container.appendChild(renderReferenceLink(citations));
  }
  return container;
}

// One line under an answer, not a second copy of the reference list. The list itself lives in the
// References view now, where it is shared across every turn instead of repeating per answer.
function renderReferenceLink(citations) {
  const keys = new Set(citations.map(referenceKey));
  const link = document.createElement("button");
  link.type = "button";
  link.className = "reference-link";
  //: English has a singular and this printed "1 references." three times on one screen. `plural`
  //: is the helper every other count in this file already goes through; the zh-Hant string is
  //: unaffected, because Chinese has no plural and `{n} 則參考` was always right.
  link.textContent = t("cite.references", `${plural(keys.size, "reference")}`, { n: keys.size });
  link.addEventListener("click", () => focusReference(citations[0]));
  return link;
}

// A REFERENCE LIST, the way a paper carries one. It replaced a row of `✓ s3 · whole` repeated once
// per citation — four identical lines carrying no information, because a text or web source has a
// single block whose locator is literally "whole" — with one entry per DISTINCT source span,
// numbered, named, and showing the quoted evidence, which is the thing a reader actually wants to
// check.
//
// **The inline highlighter stroke (blueprint §2) cannot be drawn in cross-language mode, and this
// is the honest fallback rather than a workaround.** That stroke is located by finding the
// citation's `quote` as a substring of the answer. Since invariant 39 the answer follows the
// READER's language while the quote stays verbatim in the SOURCE's, so the two never share a
// substring and no span can be located. Restoring it needs the model to mark which part of its own
// answer each citation supports — a schema and instruction change, not something this renderer can
// recover.
// The readable name for a source, shared by the reference list and the viewer modal.
function sourceLabel(source) {
  const preview = source.preview || {};
  if (preview.title) return preview.title;
  return sourceDisplayName(source);
}

// What a reader should see when they point at a citation: the source's own name, plus a locator
// ONLY when it locates something (`page:3`, `ts:04:10`). `whole` is the locator every single-block
// source gets, so showing it says nothing and crowds out the part that does.
function citationHoverLabel(citation) {
  const source = (state.sources || []).find((s) => s.id === citation.source_id);
  const name = source ? sourceLabel(source) : citation.source_id;
  const locator = citation.locator && citation.locator !== "whole" ? citation.locator : "";
  const label = locator ? `${name} · ${locator}` : name;
  return citation.verified
    ? label
    : t("cite.unverifiedHover", `Not found in this source: ${label}`, { label });
}

//: "Ask this again, and replace the answer." A separate factory rather than something
//: `renderAnswerWithCitations` grows, for the reason `saveAsNoteButton` is one: that renderer
//: serves SIX surfaces and a Guide artifact must never sprout a chat action.
function regenerateTurnButton(question) {
  const wrapper = document.createElement("div");
  wrapper.className = "turn-regenerate";
  const button = document.createElement("button");
  button.type = "button";
  // The same `.ticker-toggle` shape as the steps pill beside it: one row, one weight.
  button.className = "ticker-toggle trace-face";
  i18nText(button, "chat.regenerateTurn", "\u21bb Regenerate");
  i18nTip(
    button,
    "chat.regenerateTurnTip",
    "Ask this question again and replace this answer. Costs a full model run.",
  );
  button.disabled = composerLocked();
  button.addEventListener("click", () => store.emit("chat:regenerate", { question }));
  wrapper.appendChild(button);
  return wrapper;
}

// **ONE footer row under an answer, not three lines.** The references link, the steps pill and
// Regenerate each sat on a line of their own (a block button, a block wrapper, then an inline-block
// after it), so the newest answer ended in three short rows of chrome. The references link moves
// out of the rendered answer only when it is that answer's last child, which is where
// `renderAnswerWithCitations` puts it; every other caller of that function keeps its own layout.
function turnFooter(content, turn) {
  const footer = elt("div", "turn-footer");
  const refs = content && content.lastElementChild;
  if (refs && refs.classList.contains("reference-link")) footer.appendChild(refs);
  if (turn.run_id) footer.appendChild(renderTickerAffordance(turn.run_id));
  footer.appendChild(regenerateTurnButton(turn.question));
  return footer;
}

function renderTurn(turn) {
  const wrapper = document.createElement("div");
  wrapper.className = "turn";

  const question = document.createElement("div");
  question.className = "turn-question";
  question.textContent = turn.question;
  wrapper.appendChild(question);

  const answer = document.createElement("div");
  answer.className = "turn-answer";
  if (turn.run_id) answer.dataset.runId = turn.run_id;
  if (turn.pending) {
    answer.classList.add("is-pending");
    //: `chat.thinking` exists and is used 600 lines below for the live ticker BESIDE this bubble —
    //: so the same pending turn read "Thinking…" in English and 思考中… in Chinese at once.
    // The live run row (status, clock, Stop) once it exists; plain text only before that.
    if (turn.statusNode) answer.appendChild(turn.statusNode);
    else answer.textContent = t("chat.thinking", "Thinking\u2026");
  } else if (turn.failed) {
    // Never through `renderAnswerWithCitations`: there is no answer here and nothing to cite. A
    // heading naming the state, then the server's own sentence, which for a BYOK tool is the
    // actionable part.
    answer.classList.add("is-failed");
    answer.appendChild(elt("div", "turn-failed-head", t("chat.askFailed", "That question did not run")));
    answer.appendChild(elt("div", "turn-failed-why", readableError(turn.answer)));
    //: **A WAY TO TRY AGAIN.** The failed branch rendered the heading, the reason and the steps
    //: pill and stopped — while the composer had already cleared, so the reader retyped their
    //: question by hand after a failure they did not cause. The Horizon's failed row has offered
    //: "Try again" the whole time: two tiers answering the same event differently.
    //:
    //: `.turn-regenerate` is hidden by a stylesheet rule on any turn but the last, so a mid-thread
    //: failure does not offer to redo an answer later turns were built on — the same rule the
    //: successful branch relies on, which is why this is the same factory and not a second button.
    answer.appendChild(turnFooter(null, turn));
  } else {
    const content = renderAnswerWithCitations(turn.answer, turn.citations || [], turn.run_id);
    answer.appendChild(content);
    // `turn.run_id` is `None`/absent for any turn saved before this field existed — degrades
    // gracefully to no affordance rather than a broken link (schema.ChatTurn.run_id's own doc).
    // Regenerate lives in the row this answer's OTHER affordances already occupy — the references
    // link and the steps pill — at the same quiet weight. Deliberately not a primary button:
    // re-answering costs a full model run, so it must not be the loudest thing under an answer the
    // reader may be perfectly happy with. The overview's own control makes the same call.
    //
    // The LAST turn only, hidden by a stylesheet rule rather than a flag passed in, because turns
    // reach the DOM through two paths (`rebuildHistory` and the `chat:turnAdded` replay) and a rule
    // that reads the DOM is right for both — the same reasoning `.turn-followups` already uses. It
    // also handles the pending row for free: a question in flight is not a moment to redo another.
    answer.appendChild(turnFooter(content, turn));
    // Appended HERE, by renderTurn itself — NOT inside renderAnswerWithCitations, which five OTHER
    // call sites (Guide/Podcast) also use and must never show this button (blueprint's Notes
    // addendum, audit round 1). `generateOverview` appends its own via the same factory, for the
    // same reason: a shared helper the CALL SITE opts into, never a button the shared renderer
    // grows on its own.
    answer.appendChild(saveAsNoteButton(turn.answer));
    //: Beside Save-as-note, because they are the two things a reader does with an answer they
    //: value: keep it here, or take it somewhere else. Only the second existed as a select-and-drag.
    answer.appendChild(
      copyButton(() => artifactMarkdown(turn.answer, turn.citations, turn.question))
    );
    // Suggested next questions, from the SAME run that produced the answer — no extra model call.
    // A user found this affordance on the overview and pointed out it appeared exactly once per
    // orbit and never again. Labelled "Ask next" rather than the overview's "Start with":
    // deliberately NOT unified, because the overview's appears before any conversation exists, and
    // "ask next" there would be asking the reader to continue something they have not begun.
    if (turn.follow_ups && turn.follow_ups.length) {
      // Wrapped so the stylesheet can show it on the LAST turn only. Every turn carries its own
      // suggestions (they are persisted per answer), and rendering all of them put a row of chips
      // under every answer in the thread — ten rows in a ten-turn conversation, nine of them
      // offering to continue a conversation that has already continued past them.
      //
      // `:last-child` rather than a flag passed in: turns reach the DOM through TWO paths
      // (`rebuildHistory` and the `chat:turnAdded` replay), and a rule that reads the DOM is right
      // for both without either having to remember. It also handles the pending row for free — a
      // question already in flight is not a moment to suggest another one.
      const block = document.createElement("div");
      block.className = "turn-followups";
      const label = document.createElement("div");
      label.className = "chat-overview-head";
      label.textContent = t("chat.askNext", "Ask next");
      block.appendChild(label);
      block.appendChild(starterQuestionRow(turn.follow_ups));
      answer.appendChild(block);
    }
  }
  wrapper.appendChild(answer);

  return wrapper;
}

// --- The chat overview: the orbit's front page ---------------------------------------------
//
// Adding a source used to leave the screen doing nothing — Chat said "ask a question once you've
// added a source", Studio said "pick a tab to generate it", and both waited on the user to discover
// the next move. The guided feel of an orbit product comes from the artifact appearing IN the
// conversation and being something you ask follow-ups about; a Summary buried in a right-hand tab
// is disconnected from the thread, so even finding it leads nowhere.
//
// THREE states, not two. The first version had only "generated in this page session" vs "not", on a
// DOM flag — so every orbit opened showing the first-run button even mid-conversation (reported
// with a screenshot), and adding a source DELETED the overview and reverted to that same button, so
// "never generated" and "generated but the sources changed" rendered identically. Confiscating an
// overview the user just paid an RLM run for, because they added a source, is worse than showing it
// with a marker: it is still true about the sources it was computed from.
//
//   never generated          ->  the Generate button
//   generated, current       ->  the overview + Save as note
//   generated, sources moved ->  the overview, marked stale, + Regenerate  (+ Save as note: a stale
//                                overview is precisely the one worth keeping before regenerating)
//
// `state.overview` comes from the server, which owns both the artifact and the `stale` verdict.
// Deliberately still an explicit button, NOT auto-generated on open: a guide run is a real RLM loop
// and Phase 2's rule (never spend one nobody asked for) is unchanged.
let overviewToken = 0;

//: True while `generateOverview` owns `#chat-overview` — its pulsing dot, its elapsed counter and
//: its Stop button live there and nowhere else.
//:
//: `renderChatOverview` CLEARS that element, and FIVE things call it for reasons that have nothing
//: to do with the run: `sources:changed`, the source-delete handler, an orbit switch, the rebuild
//: after an `ask`, and an interface-language change. (An earlier version of this comment said three
//: and listed source removal twice; invariant 71 said a DIFFERENT three. The guard is at the TOP of
//: the function, so every caller was covered either way.) So adding a source while an overview
//: generated wiped the progress indicator AND the only Stop — invariant
//: 47's rule broken by a repaint, the same class invariant 60 fixed for the pending chat turn and
//: for exactly the same reason: a repaint must carry the run in flight with it.
//:
//: Worse than it sounds. `sources:changed` deliberately does NOT bump `overviewToken` (stranding a
//: generation the server has already paid for would be the bigger bug), so the run stays live with
//: no way to see or stop it until it lands minutes later.
let overviewRunning = false;

function renderChatOverview() {
  // A run owns this element. It repaints itself when it finishes, cancels or fails, and staleness
  // is recomputed server-side at that point anyway — so there is nothing to lose by deferring.
  if (overviewRunning) return;
  const el = document.getElementById("chat-overview");
  el.textContent = "";
  el.hidden = !state.sources.length;
  if (!state.sources.length) return;

  const overview = state.overview;
  if (!overview) {
    el.appendChild(overviewStarter(t("chat.generateOverview", "Summarise and suggest questions"), t("chat.orJustAsk", "\u2026or just ask a question below.")));
    return;
  }

  const head = document.createElement("div");
  head.className = "chat-overview-head";
  head.textContent = overview.stale
    ? t("chat.overviewStale", "Overview \u00b7 sources have changed since this")
    : t("chat.overview", "Overview");
  el.appendChild(head);

  //: **The overview is PROSE, and it was the one prose surface the reading face never reached.**
  //: `.turn-answer`, `.guide-body`, `.podcast-utterance` and `.source-text` are all set in Literata
  //: under a rule that says "prose is set for reading and everything else is set for scanning" —
  //: and this renders through the very same function as `.turn-answer`, one block above it in the
  //: same scroller. Measured side by side: Public Sans 14.4/21.6 here against Literata 14.4/24.48
  //: directly below. A class rather than putting `.chat-overview` itself in that list, because the
  //: block also holds a head, a Save-as-note button and a Steps pill, which stay in the UI face.
  const body = renderAnswerWithCitations(overview.text, overview.citations || [], overview.run_id);
  body.className = "chat-overview-body";
  el.appendChild(body);
  // The same one-row footer an answer has, so the overview above the thread does not end in two
  // lines of chrome right over an answer that ends in one. No cache guard on the steps pill: it
  // loads the record from the server when this page has none, which is every run after a reload.
  const footer = elt("div", "turn-footer");
  const refs = body.lastElementChild;
  if (refs && refs.classList.contains("reference-link")) footer.appendChild(refs);
  if (overview.run_id) footer.appendChild(renderTickerAffordance(overview.run_id));
  if (footer.children.length) el.appendChild(footer);
  el.appendChild(saveAsNoteButton(overview.text));
  el.appendChild(
    copyButton(() =>
      artifactMarkdown(overview.text, overview.citations, t("chat.overview", "Overview"))
    )
  );

  // FOUR states, not three. Invariant 38 named "never generated / current / stale"; an overview
  // that is current but arrived INCOMPLETE is a fourth, because `/overview` runs Summary and FAQ
  // concurrently and persists the summary even when the FAQ half dies. It rendered as nothing, then
  // (worse) as a note telling the reader to regenerate while the regenerate button was still gated
  // behind `stale` — a message naming an action the page did not offer.
  let offerRegenerate = overview.stale;

  // Only before the conversation starts. These are an invitation to BEGIN — that is the whole
  // reason this row says "Start with" while an answer's says "Ask next" (invariant 56) — and once
  // there are turns the live suggestion is the latest answer's, at the bottom of the thread where
  // the reader actually is. Leaving both on screen put two competing rows a scroll apart.
  if (state.turns && state.turns.length) {
    // nothing: the thread's own latest answer carries the suggestions now
  } else if (overview.starter_questions && overview.starter_questions.length) {
    const label = document.createElement("div");
    label.className = "chat-overview-head";
    label.textContent = t("chat.startWith", "Start with");
    el.appendChild(label);
    el.appendChild(starterQuestionRow(overview.starter_questions));
  } else {
    // An overview with NO starter questions is a half-failure, not an empty result: `/overview`
    // fires a Summary and an FAQ concurrently and persists the summary even when the FAQ half dies
    // (invariant 38). It rendered as nothing at all, so a user whose FAQ half had timed out reported
    // the suggestions as having disappeared from the product — the same "a superseded generation
    // says so" lesson invariant 47 records, on a different path. Saying it, with the button that
    // fixes it, costs one line.
    const note = document.createElement("div");
    note.className = "chat-overview-note";
    note.textContent = t(
      "chat.noStarters",
      "No suggested questions came back with this overview. Regenerate to try again.",
    );
    el.appendChild(note);
    offerRegenerate = true;
  }

  // ONE button, whichever state asked for it — a stale overview and an incomplete one both want
  // the same action, and appending it per-branch would have produced two on an orbit that is both.
  //
  // ALWAYS OFFERED once an overview exists, which it was not: it was gated behind `stale` or
  // "incomplete", so an overview that was current and complete but simply WRONG had no way to be
  // regenerated at all. A user hit exactly that — asked how to press a button that was not on the
  // page — while looking at an overview whose five citations had all failed coordinate
  // verification. Nothing about their sources had changed, so nothing ever made it stale. The
  // podcast has offered a quiet Regenerate in this same state since invariant 42; the overview
  // simply never gained it.
  el.appendChild(
    overviewStarter(
      offerRegenerate
        ? t("chat.regenerateOverview", "\u21bb Regenerate overview")
        : t("chat.refreshOverview", "\u21bb Regenerate"),
      "",
      !offerRegenerate,
    )
  );
}

function overviewStarter(labelText, hintText, quiet) {
  //: The first-run label NAMES BOTH HALVES of what this produces, and it is deliberately not
  //: "Generate overview". `/overview` runs two tasks: a summary AND the starter questions, and the
  //: short label mentioned neither. Worse, it sat one column away from Studio's "Generate Summary",
  //: which runs the SAME summary task while keeping nothing (invariant 38 persists the overview and
  //: not the four Studio kinds), so the two read as one feature offered twice. A user asked which
  //: was which. In Chinese the collision was sharper still: 概覽 and 摘要 are near synonyms.
  //:
  //: Only the FIRST-RUN button changed. The artifact keeps its own name in its heading, where it
  //: sits in the chat thread with nothing to be confused with, and the regenerate label with it.
  //:
  //: This comment lives INSIDE the function on purpose. Above it, it fell within the slice
  //: `test_a_message_naming_an_action_ships_with_that_action` takes of `renderChatOverview`, which
  //: counts a key's occurrences to prove there is exactly one regenerate control. Naming the key in
  //: prose made it two.
  const wrap = document.createElement("div");
  wrap.className = "chat-starter";
  const btn = document.createElement("button");
  btn.type = "button";
  // SECONDARY once an overview exists. Regenerating costs two real RLM runs, so it must not be the
  // loudest thing on a panel that already holds what it makes — the same weighting the podcast's
  // own generate button uses (invariant 42), applied to the control that had been missing entirely.
  btn.className = quiet ? "btn" : "btn btn-primary";
  btn.textContent = labelText;
  // Same reason as the Studio's offer: `renderChatOverview` runs for several reasons unrelated to
  // a run, and each one builds this button fresh.
  queueMicrotask(syncRunGuards);
  btn.addEventListener("click", () => {
    btn.disabled = true;
    void generateOverview();
  });
  wrap.appendChild(btn);
  if (hintText) {
    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = hintText;
    wrap.appendChild(hint);
  }
  return wrap;
}

function starterQuestionRow(questions) {
  const row = document.createElement("div");
  row.className = "starter-questions";
  questions.forEach((question) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "starter-question";
    // textContent, never innerHTML — model-authored text derived from source content a
    // prompt-injected source could influence (invariants 6 and 29).
    chip.textContent = question;
    chip.addEventListener("click", () => {
      // `requestSubmit()` submits as if by the form, so a DISABLED submit button never blocks it;
      // the chips live outside the region `chat:pending` disables, so the guard has to be here.
      //: The LOCK, not the button's state: Send is also disabled whenever the field is EMPTY, which
      //: is exactly when a chip is pressed — so every suggested question did nothing at all.
      if (composerLocked() || !(state.sources || []).length) return;
      //: Asked DIRECTLY, not by writing into the composer and submitting it: that replaced whatever
      //: the reader had half-typed there with the chip's question, and the draft was gone.
      store.emit("chat:ask", { question });
    });
    row.appendChild(chip);
  });
  return row;
}

// One POST; the server runs Summary and FAQ concurrently and persists the result, so nothing is
// lost if this tab closes while it runs.
async function generateOverview() {
  const el = document.getElementById("chat-overview");
  const generation = orbitGeneration;
  const token = (overviewToken += 1);
  const orbitId = state.orbitId;
  if (!orbitId) return;
  const live = () => generation === orbitGeneration && token === overviewToken;
  //: **Release only what is still THIS run's.** Both paths cleared `overviewRunning` and sent
  //: `chat:pending false` before asking whose run it was, so an overview ending in orbit A
  //: unlocked B's composer mid-question (a second paid question could start) and released B's
  //: own overview, whose Stop the next repaint then wiped. An orbit switch already resets both
  //: for the new orbit; a newer overview in this one owns them itself (`token`).
  const releaseIfMine = () => {
    if (!live()) return;
    overviewRunning = false;
    store.emit("chat:pending", { pending: false });
  };

  el.hidden = false;
  el.textContent = "";
  overviewRunning = true;
  // FREEZE THE COMPOSER, at the user's request and twice asked for. It is not needed for
  // correctness — the two runs are independent, `mutate_orbit` re-reads under a per-orbit
  // lock so both writes land (invariant 34), and neither repaint can delete the other's run
  // (invariants 60 and 71). It is what the person using it wants: a question asked into a thread
  // whose overview is being rewritten reads as two things fighting, whether or not they are.
  //
  // The composer only — never the thread. Clearing the conversation was offered as an alternative
  // and is the one thing not to do: it would destroy history to signal a transient state.
  store.emit("chat:pending", { pending: true });

  // The server appends `-summary`/`-faq` to the run id it derives, so both targets are predictable:
  // the ticker follows the summary, and Stop cancels BOTH (an orbit-scoped cancel would leave the
  // FAQ run burning a model call to completion).
    const runToken = crypto.randomUUID();
  const base = `${state.orbitSlug || orbitId}-${runToken}`;
  let cancelled = false;
  const status = runStatus({
    orbitId,
    runIds: [`${base}-summary`, `${base}-faq`],
    label: t("chat.readingSources", "Reading your sources\u2026"),
    onCancel: () => {
      cancelled = true;
      // Another orbit's panel and composer are not this run's to release (see `releaseIfMine`).
      if (!live()) return;
      overviewToken += 1; // strand this generation's own response
      overviewRunning = false; // release BEFORE the repaint, or the guard above swallows it
      store.emit("chat:pending", { pending: false });
      renderChatOverview(); // straight back to the pre-run state, nothing half-written left behind
    },
  });
  el.appendChild(status.node);

  void openTicker(orbitId, `${base}-summary`, (event) => {
    if (!live()) return;
    // `/overview` runs TWO tasks and this ticker follows only the summary. Forwarding its terminal
    // event made "完成" the whole action's headline while the FAQ half was still running and the
    // POST had not returned — measured: a 63KB summary trace beside a 226-byte FAQ trace, its
    // worker still alive, and no response yet. The panel then sat on "Finished" next to a live Stop
    // button, which is invariant 60's rule ("a status line may not claim something the page is not
    // doing") broken by the second run rather than by a phase.
    //
    // `setPhase` is exactly the seam invariant 60 added for a stage the trace cannot see. STOPPABLE,
    // because it genuinely is: `runIds` carries both ids and Stop cancels each by run id.
    if (TERMINAL_KINDS.has(event.kind)) {
      status.setPhase(t("chat.overviewSecondHalf", "Summary done \u00b7 writing suggested questions\u2026"));
      return;
    }
    status.onEvent(event);
  });

  try {
    const orbit = await api(`/orbits/${encodeURIComponent(orbitId)}/overview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // `fresh` when an overview already exists — i.e. the button said Regenerate. dspy's LM cache
      // is on by default, so without this a Regenerate on an unchanged corpus replays the previous
      // run byte-identically for zero model calls, and a button that returns what you already had
      // is a UI that lies. A FIRST generate keeps the cache, where a hit is a free correct answer.
      body: JSON.stringify({ run_id: runToken, fresh: Boolean(state.overview) }),
    });
    status.finish();
    releaseIfMine();
    if (cancelled) return;
    if (!live()) {
      // SUPERSEDED, not lost. Saying nothing here is what made a real report read as "pressed
      // generate, it said Finished, then nothing ever appeared": the response arrived, this guard
      // dropped it silently, and the last ticker line just sat there looking stuck.
      //
      // But `!live()` covers TWO situations and only one of them is this panel's business. If the
      // reader has SWITCHED ORBITS, `#chat-overview` now belongs to a different orbit and
      // writing here would overwrite ITS overview with a note about a run it never started.
      // Superseding is a same-orbit event: a second press of Generate.
      if (generation === orbitGeneration) supersededNote(el);
      return;
    }
    state.overview = orbit.overview;
    ensureTitle(); // the overview arrived, so a run was paid for
    refreshReferenceView();
    renderChatOverview();
    // The thread too: a regenerated overview changes which coordinates come FIRST in the
    // orbit-wide reference order, so every stroke already on screen would keep a number that no
    // longer matches the row it points at. Cheap, and the alternative is a page that is internally
    // inconsistent until the next reload.
    store.emit("chat:rerender", {});
  } catch (err) {
    status.finish();
    releaseIfMine();
    if (cancelled) return;
    if (!live()) {
      if (generation === orbitGeneration) supersededNote(el);
      return;
    }
    //: **The overview the reader already had stays.** This cleared the element and offered only
    //: "↻ Try again", so a failed REgeneration looked like it had deleted a paid overview that was
    //: still persisted (a reload brought it back). Stop already restored it; failure now does too,
    //: with the message above it and the overview's own ↻ Regenerate as the retry.
    if (state.overview) {
      renderChatOverview();
      el.prepend(failureBlock(t("chat.overviewFailed", "The overview did not get made"), err.message));
      return;
    }
    el.textContent = "";
    el.appendChild(
      failureBlock(t("chat.overviewFailed", "The overview did not get made"), err.message)
    );
    el.appendChild(overviewStarter(t("chat.tryAgain", "\u21bb Try again"), ""));
  }
}

// A generation whose result is no longer the current one (the user regenerated, or switched
// orbits and back). The old code returned silently, which is indistinguishable from a hang.
function supersededNote(el) {
  el.textContent = "";
  const note = document.createElement("div");
  note.className = "empty-note";
  note.textContent = t("chat.overviewSuperseded", "That overview was superseded by a newer one.");
  el.appendChild(note);
  el.appendChild(overviewStarter(t("chat.generateOverview", "Summarise and suggest questions"), ""));
}

// The empty orbit's start buttons: pick the source kind, bring the Sources panel forward (it is
// a separate tab in a narrow window), and put the reader in the field. A file opens the picker.
function wireChatStart(start) {
  start.querySelectorAll("[data-start-kind]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const kind = btn.dataset.startKind;
      document.getElementById(`ktab-${kind}`).click();
      setPanel("sources");
      if (kind === "file") document.getElementById("source-file").click();
      else document.getElementById(kind === "url" ? "source-url" : "source-text").focus();
    });
  });
}

function initChatPanel() {
  const history = document.getElementById("chat-history");
  const empty = document.getElementById("chat-empty");
  const overviewEl = document.getElementById("chat-overview");
  const start = document.getElementById("chat-start");
  wireChatStart(start);

  // ONE rebuild, used by every path that redraws the thread. The overview is the thread's first
  // entry now, so a `history.innerHTML = ""` that forgot to put it back would silently delete it —
  // which is exactly what the old sibling layout was avoiding.
  // The placeholder reads "Ask a question once you've added a source" — which is only TRUE while
  // there is no source. It used to be gated on turns alone, so an orbit with eight sources and no
  // conversation still told the reader to add one; a user reported it as confusing, and it is: the
  // sentence describes a precondition they have already met. Once a source exists the invitation is
  // the overview's own button (or its starter questions), a few lines above.
  const syncEmptyNote = (turns, pending) => {
    empty.hidden = turns.length > 0 || Boolean(pending) || (state.sources || []).length > 0;
    start.hidden = empty.hidden;
    // **A thread with nothing in it is an INVITATION, not a card pinned to the top of a void.** An
    // independent review measured it: a bordered box holding one button, above about 550 pixels of
    // empty column. A conversation that has not started has no reason to be top-aligned - there is
    // nothing above for it to sit under - and centring it turns the same two elements from "a
    // widget that loaded" into "the thing to do here".
    //
    // A class on the SCROLLER rather than on the overview, because it is the scroller that has the
    // height; `.chat-overview` also loses its box in this state, which is what stops one CTA
    // reading as a card.
    history.classList.toggle("is-invitation", !turns.length && !pending);
  };

  //: "Clear conversation". Declared up here because the handlers that keep it in sync are the
  //: EXISTING `chat:turnAdded` / `chat:rerender` / `orbit:switched` subscriptions — a second
  //: handler for one event inside one init is what `test_no_event_is_subscribed_twice_inside_one_
  //: init_function` forbids, and rightly: two of them make ordering matter.
  const clearBtn = document.getElementById("chat-clear");
  const syncClearBtn = () => {
    clearBtn.hidden = !state.orbitId || !(state.turns || []).length;
  };


  //: The question currently in flight, if any. `chat:rerender` has to put it back: an independent
  //: review reproduced regenerating the overview mid-question deleting the pending row, its status
  //: and its Stop, leaving a disabled composer with no way to cancel until the answer landed
  //: minutes later — invariant 47's rule broken by a repaint.
  let pendingTurn = null;

  //: How close to the bottom still counts as "at the bottom". A couple of lines of slack, because a
  //: reader who has nudged the wheel by 30px has not left the conversation.
  const PINNED_SLACK = 48;
  const atBottom = () =>
    history.scrollHeight - history.scrollTop - history.clientHeight <= PINNED_SLACK;

  const rebuildHistory = (turns, pending) => {
    //: **A settled turn was never re-scrolled, and the error state is where that costs something.**
    //: Only `chat:turnAdded` scrolled — i.e. when the SHORT pending row appears — never when the
    //: taller real answer or failure block replaced it. Measured after a failed question at
    //: 1440x900: 83px clipped below the fold, containing both of that turn's actions, `Steps` and
    //: `↻ Regenerate`. The one affordance that recovers from the error was the one you could not
    //: see.
    //:
    //: Asked BEFORE the rebuild, because clearing the element resets `scrollTop` to 0 and the
    //: question "was the reader following along" would then always answer yes. Re-pinned only if
    //: they already were: yanking someone back to the bottom while they are reading an earlier turn
    //: is the other half of this bug, and the commoner one.
    const wasPinned = atBottom();
    history.textContent = "";
    history.appendChild(overviewEl);
    history.appendChild(empty);
    history.appendChild(start);
    syncEmptyNote(turns, pending);
    turns.forEach((turn) => history.appendChild(renderTurn(turn)));
    if (pending) history.appendChild(renderTurn(pending));
    //: ...and a RECOVERED run's row (a run found still going after a reload or a return). It lives
    //: in this element too, and every rebuild — a source removed, Clear conversation, an answer
    //: landing — wiped it: its only Stop gone while the run kept billing.
    if (recoveredRow && recoveredRuns.has(state.orbitId)) history.appendChild(recoveredRow);
    if (wasPinned) history.scrollTop = history.scrollHeight;
  };
  const form = document.getElementById("ask-form");
  const input = document.getElementById("ask-input");
  const submitBtn = document.getElementById("ask-submit");

  // Enter sends, Shift+Enter breaks a line. The convention every chat composer uses, and the reason
  // the hint row exists at all: without it this is a rule you can only find by accident.
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    // Never steal Enter mid-composition: an IME is still assembling a character, and submitting
    // there would send a half-typed word. `isComposing` is exactly what that flag is for, and this
    // matters far more here than in an English-only UI.
    if (event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    form.requestSubmit();
  });

  // The box grows with the question and stops at the CSS ceiling, then scrolls. Driven from the
  // real scrollHeight rather than a line count, so it is right for wrapped text too.
  const autoGrow = () => {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
    const filled = input.value.trim().length > 0;
    form.classList.toggle("has-text", filled);
    //: **A question needs something to ask ABOUT.** `title` and `overview` both refuse a
    //: source-less orbit and `ask` did not, so the composer accepted a question 20px from a
    //: Studio panel reading "Add a source first, then generate this" and ran a full model loop
    //: against an empty corpus — the one press in the product that spends money for nothing. The
    //: server refuses it now (422); this is the half that means the reader never has to find out.
    const grounded = (state.sources || []).length > 0;
    const send = document.getElementById("ask-submit");
    // The send control reflects whether there is a question to send, the same way the Horizon's
    // capture button does. It was never `disabled` at all, in either state.
    if (send) send.disabled = !filled || !grounded || composerLocked();
    input.placeholder = grounded
      ? t("chat.placeholder", "Ask a grounded question…")
      : t("chat.needsSource", "Add a source first, then ask about it.");
  };
  input.addEventListener("input", autoGrow);
  autoGrow();

  store.on("orbit:switched", () => {
    overviewToken += 1; // an orbit switch strands any generation still in flight
    // ...and releases the panel it owned. Without this the new orbit keeps the OLD run's
    // pulsing dot and Stop, because `renderChatOverview` defers while a run owns the element.
    overviewRunning = false;
    renderChatOverview();
    //: ...and the pending QUESTION, which belongs to the orbit that asked it. Left set, the next
    //: re-render in the new orbit drew orbit A's question as B's — pending, with A's Stop —
    //: and a failure landed in B's thread with a ↻ Regenerate that ran A's question on B's
    //: sources. Coming back to A finds the run through `reattachInFlightRuns`, Stop and all.
    pendingTurn = null;
    // ...and un-freezes the new orbit's composer. AFTER both owners above are released: the
    // handler holds the composer while either is live, so emitting first kept it locked.
    store.emit("chat:pending", { pending: false });
    // The placeholder comes back too: `chat:turnAdded` hides it, and without this a switch FROM a
    // orbit with turns TO an empty one left a blank panel with no "ask a question" prompt at all.
    rebuildHistory([]);
    syncClearBtn();
  });

  // Chat's own reaction to the corpus changing. Re-render only — deliberately NOT a token bump:
  // that would strand a generation the server has already persisted, leaving the user looking at
  // the button after paying for two RLM runs sitting on disk (adding a source while the model works
  // is the exact behaviour invariant 34 documents as real). The re-render flips the overview to
  // stale on its own, because the server's `source_ids` no longer match.
  store.on("sources:changed", ({ sources }) => {
    //: The orbit exists on the server the moment it has a source, so that is when its id becomes
    //: a link worth having — see `openOrbit`, which withholds it until then. `replace`, not
    //: push: this is the same place in history, now addressable.
    if ((sources || []).length && state.orbitId && document.body.dataset.view === "orbit") {
      syncAddressBar(state.orbitId, { replace: true });
    }
    renderChatOverview();
    // Adding the FIRST source has to retire the placeholder immediately — it is the moment its
    // sentence stops being true, and nothing else redraws the thread at that point.
    syncEmptyNote(state.turns || [], pendingTurn);
    //: ...and the composer, whose enabled state and placeholder both depend on there BEING a
    //: source. One subscriber, not two: `test_no_event_is_subscribed_twice_inside_one_init_function`
    //: refuses a second, because two handlers for one event in one function is how an ordering
    //: dependency gets written by accident.
    autoGrow();
  });
  renderChatOverview();

  store.on("chat:turnAdded", ({ turn, restoring }) => {
    empty.hidden = true;
    history.appendChild(renderTurn(turn));
    // Only a NEW turn scrolls to the bottom. Replaying a saved conversation on open used to run
    // this once per turn, so a returning reader landed with the overview — and, on an orbit with
    // turns but no overview yet, the "Generate overview" button — already a thousand pixels above
    // the fold. Invariant 57 says the overview scrolls AWAY as the conversation grows; starting
    // there is a different thing.
    if (!restoring) history.scrollTop = history.scrollHeight;
    syncClearBtn();
  });

  // Something outside the thread changed the orbit-wide reference order (regenerating the
  // overview is the one that does it today), so every turn's stroke numbers have to be recomputed.
  store.on("chat:rerender", () => {
    rebuildHistory(state.turns || [], pendingTurn);
    syncClearBtn();
  });

  store.on("chat:pending", ({ pending }) => {
    //: TWO owners, the overview and a question, and either may still be running when the other
    //: sends `pending: false` — an overview ending mid-question unlocked the composer, and so did a
    //: question ending mid-overview. Held while EITHER is live.
    composerHeld = pending || overviewRunning || Boolean(pendingTurn && pendingTurn.pending);
    document.querySelectorAll(".turn-regenerate button").forEach((button) => {
      button.disabled = composerLocked();
    });
    // While a question runs, disabled. When it finishes, disabled UNLESS there is something to
    // send: `pending: false` used to re-enable it unconditionally, which is why the button came
    // back to life over an empty composer the moment a turn completed.
    submitBtn.disabled = composerLocked() || !input.value.trim() || !(state.sources || []).length;
    input.disabled = composerHeld;
    // Clearing WHILE a question runs is a race with no upside: the server would delete the turns
    // and then `ask`'s own persist would append the answer to the empty list, so the conversation
    // the reader just cleared comes back with one entry. Stop is the control for a run in flight;
    // this one is for a conversation that has finished happening.
    // The SAME lock as Send: a recovered run's answer would bring a cleared conversation back.
    clearBtn.disabled = composerLocked();
  });

  // One flow, two entry points: the composer, and a turn's own "regenerate". Extracted rather than
  // copied — the pending row, the live ticker, the Stop button, the cancel path and the
  // rebuild-from-the-server's-own-record are the parts that would drift, and this file has already
  // paid for a duplicated affordance once (the two "N steps" pills).
  //
  // `regenerate` REPLACES the last turn server-side when the question still matches it. Only the
  // last: every later answer was produced with this one in its `history` (invariant 11), so
  // regenerating mid-thread would leave the answers after it derived from a conversation that no
  // longer exists. The button is offered on the last turn only, and the server re-checks.
  async function askQuestion(question, { regenerate = false } = {}) {
    if (!state.orbitId) {
      notify(t("err.openOrbitFirst", "Open an orbit first."));
      return;
    }
    if (!question) return;

    // The CLIENT picks the run id (blueprint P3.1) — a server-generated one would never reach us
    // until the request was already over, too late to open a live ticker against it.
    const generation = orbitGeneration;
    const askedOrbitId = state.orbitId;
    const token = crypto.randomUUID();
    const runId = `${state.orbitSlug || state.orbitId}-${token}`;

        pendingTurn = { question, pending: true, run_id: runId };
    store.emit("chat:turnAdded", { turn: pendingTurn });
    store.emit("chat:pending", { pending: true });

    // The same live surface the Studio actions use, mounted into the pending answer row. Chat had
    // no way to stop a question either, and a question against a large corpus is not quick.
    let cancelled = false;
    const answerEl = history.querySelector(`.turn-answer[data-run-id="${CSS.escape(runId)}"]`);
    const status = runStatus({
      orbitId: askedOrbitId,
      runIds: [runId],
      label: t("chat.thinking", "Thinking\u2026"),
      onCancel: () => {
        cancelled = true;
        // Nothing is in flight any more; a rebuild must not resurrect the row.
        pendingTurn = null;
        store.emit("chat:pending", { pending: false });
        const row = history.querySelector(`.turn-answer[data-run-id="${CSS.escape(runId)}"]`);
        if (row) {
          row.classList.remove("is-pending");
          row.textContent = t("chat.stopped", "(stopped)");
          // Not a later turn: the answer above keeps its ↻ Regenerate and its chips (style.css).
          row.closest(".turn")?.classList.add("is-stopped");
        }
      },
    });
    if (answerEl) {
      answerEl.textContent = "";
      answerEl.appendChild(status.node);
      //: Re-pinned AFTER the status row is in: `chat:turnAdded` scrolled to the bottom while the
      //: row still read "Thinking…", the taller status row then left the thread ~62px short of the
      //: bottom — past `PINNED_SLACK` — and so the landed answer (or failure) was never followed.
      history.scrollTop = history.scrollHeight;
    }
    //: The row travels WITH the pending turn, so a rebuild re-attaches it (see `renderTurn`'s
    //: pending branch). Removing a source emits `chat:rerender`, and the rebuild drew a bare
    //: "Thinking…" — the run's only ⏹ Stop gone while it kept billing.
    if (pendingTurn && pendingTurn.run_id === runId) pendingTurn.statusNode = status.node;

    openTicker(state.orbitId, runId, (evt) => status.onEvent(evt));

    try {
      const result = await api(`/orbits/${encodeURIComponent(state.orbitId)}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, run_id: token, regenerate }),
      });
      // Re-render the whole history from the server's own record rather than mutating the
      // pending row in place — the server is the source of truth for what actually got persisted.
      // Capture the id BEFORE awaiting: re-reading `state.orbitId` here would build
      // `/orbits/null` if the user started a new orbit while the answer was in flight.
      status.finish();
      if (cancelled) return;
      if (generation !== orbitGeneration) return;
      const orbit = await api(`/orbits/${encodeURIComponent(askedOrbitId)}`);
      if (generation !== orbitGeneration) return;
      state.turns = orbit.turns;
      // CLEARED before the rebuild: the turn is in `state.turns` now, so a later `chat:rerender`
      // that still held this object would render the same question twice.
      if (pendingTurn && pendingTurn.run_id === runId) pendingTurn = null;
      refreshReferenceView();
      rebuildHistory(state.turns);
      //: The first answer changes two things outside the thread: the overview's "Start with" row
      //: retires (the answer's own "Ask next" takes over), and Clear conversation now has something
      //: to clear. Neither re-decided itself, so a fresh orbit showed two competing chip rows and
      //: no Clear until the next question or a reload.
      renderChatOverview();
      syncClearBtn();
      ensureTitle(); // the answer arrived, so the reader has paid for a run either way
      void result; // already folded into orbit.turns above
    } catch (err) {
      status.finish();
      // `cancelled` covers Stop; `!pendingTurn` covers every other way the row can have gone away
      // before the request settled. Without it a failing run threw INSIDE its own error handler, so
      // the reader saw no error row and no alert — the question simply stopped.
      if (cancelled || !pendingTurn) return;
      //: ...and only THIS run's turn, in THIS orbit: the guard the guide and podcast catches
      //: already had. Without it a failure followed the reader into whichever orbit was open,
      //: with a ↻ Regenerate that ran this orbit's question on that one's sources.
      if (generation !== orbitGeneration || pendingTurn.run_id !== runId) return;
      pendingTurn.pending = false;
      // A FAILURE, flagged as one, rather than the exception text poured into the answer slot. It
      // used to render in the ordinary answer bubble - same surface, same reading face, no colour -
      // with a literal "(error)" prefix doing all the work, so a reader scrolling back read the
      // exception as the model's reply. Worse, the "save as note" control was attached to it, and a
      // note promotes into a real citable Source (invariant 32): the error text could become a
      // SOURCE. `renderTurn` reads this flag and gives the turn its own state.
      // A run the reader stopped is not a failed turn - it is a turn that did not happen. Dropping
      // the row entirely is what "I stopped that" should look like; `cancelled` already covers the
      // Stop pressed in THIS tab, and this covers one pressed in another.
      if (CANCELLED_RUN.test(String(err.message || ""))) {
        // SAY so. Dropping the row is right - a stopped question is not a failed one - but doing it
        // silently means a question stopped from ANOTHER TAB just vanishes, composer already
        // cleared, text unrecoverable. The in-tab Stop shows "(stopped)"; the remote one showed
        // nothing, and that asymmetry was the defect. `run.wasStopped` was written for this and was
        // unreachable on the chat path.
        pendingTurn = null;
        rebuildHistory(state.turns);
        notify(t("run.wasStopped", "You stopped this one."), { tone: "info" });
        return;
      }
      pendingTurn.failed = true;
      pendingTurn.answer = err.message;
      pendingTurn.citations = [];
      rebuildHistory(state.turns, pendingTurn);
    } finally {
      // Only in the orbit that asked: a run ending in A unlocked B's composer while B's own
      // question was still running. A switch already releases the composer for the new orbit.
      if (generation === orbitGeneration) store.emit("chat:pending", { pending: false });
    }
  }

  // The composer clears itself; `askQuestion` does not, because a regenerate has nothing to clear.
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    // The lock the send button shows; Enter reaches here without the button (see `composerLocked`).
    if (composerLocked()) return;
    //: **The same gate the send button has.** Enter submits the form whether or not the button is
    //: disabled, so with no sources the question was cleared and came back as a failed turn quoting
    //: the server's `no orbit 'nb-…' — POST sources to it first`. The question stays in the field.
    if (!(state.sources || []).length) {
      notify(t("chat.needSource", "Add a source first. Every answer is grounded in your sources."));
      setPanel("sources");
      return;
    }
    input.value = "";
    input.style.height = "auto";
    form.classList.remove("has-text");
    const sendBtn = document.getElementById("ask-submit");
    if (sendBtn) sendBtn.disabled = true;
    void askQuestion(question);
  });

  // A turn asks to be redone. Exposed on `store` rather than threaded through `renderTurn`'s six
  // call sites: the button is built far from here and this is the one flow that can run it.
  store.on("chat:ask", ({ question }) => {
    if (composerLocked() || !(state.sources || []).length) return;
    void askQuestion(question);
  });

  store.on("chat:regenerate", ({ question }) => {
    // The same lock as Send: ↻ Regenerate is a new paid question too (see `composerLocked`).
    if (composerLocked()) return;
    void askQuestion(question, { regenerate: true });
  });

  // Starting over. Turns were append-only, so a reader who wanted a fresh start had nowhere to go:
  // a source could be deleted and a note could be deleted, but a conversation could only grow.
  // Regenerate replaces the LAST answer and deliberately cannot reach further back (invariant 11);
  // this is the other end of that same fact, and the only honest way to undo a turn in the middle.
  clearBtn.addEventListener("click", async () => {
    // Irreversible, like every other delete here — and unlike removing ONE source, this discards
    // work that cost real model runs, so the confirmation names what survives as well as what goes.
    //
    // The generation is captured for the same reason every other awaiting flow here captures it
    // (`generateOverview`, `askQuestion`, `fetchKind`, the podcast): this one did not, and a
    // orbit switch during the DELETE applied the result to whichever orbit was open when it
    // landed — wiping the NEW orbit's conversation out of client state and off the screen.
    const generation = orbitGeneration;
    const n = (state.turns || []).length;
    const ok = await confirmAction(
      t(
        "chat.clearConfirm",
        `Delete all ${n} questions and answers? Sources, notes and the overview are kept.`,
        { n }
      )
    );
    if (!ok) return;
    clearBtn.disabled = true;
    try {
      const orbit = await api(`/orbits/${encodeURIComponent(state.orbitId)}/turns`, {
        method: "DELETE",
      });
      // The orbit that was cleared is not necessarily the one on screen any more.
      if (generation !== orbitGeneration) return;
      // From the server's own record, never from an assumption about what it did.
      state.turns = orbit.turns;
      refreshReferenceView();
      // `pendingTurn` is CARRIED, not dropped. Clearing is disabled while a question runs (below),
      // so this is defence rather than a live path — but `rebuildHistory(state.turns)` alone would
      // delete a running question's row along with its elapsed counter and its only Stop, which is
      // invariant 47 broken by a repaint and exactly what invariant 60 fixed for `chat:rerender`.
      // Nulling it was worse still: `askQuestion`'s own catch then threw on a null, so a run that
      // failed after a clear rendered no error row and raised no alert — it just stopped.
      rebuildHistory(state.turns, pendingTurn);
      // `refreshReferenceView` above already re-stamped every stroke on the page (`renumberStrokes`),
      // so this needs no `chat:rerender` — emitting one would only rebuild the thread a second time,
      // and `chat:rerender` has exactly one emitter for a reason (regenerating the overview is the
      // thing that changes the orbit-wide order from OUTSIDE the thread).
      //
      // The overview's starter questions come back: they are shown only before a conversation
      // exists, and one no longer does.
      renderChatOverview();
      syncClearBtn();
    } catch (err) {
      notify(t("err.generic", `${readableError(err.message)}`, { message: readableError(err.message) }));
    } finally {
      clearBtn.disabled = false;
    }
  });
  syncClearBtn();
}

// --- Studio panel: Guide tabs -----------------------------------------------------------------

// Fetched ONLY on first tab activation or an explicit regenerate click, never on every tab
// switch — a guide run is a real RLM loop (same latency class as `ask`), so re-running it on every
// idle click would burn a model call for nothing. Cached per orbit, keyed by kind; cleared on
// BOTH an orbit switch AND a source being added — a cached result is stale the moment the corpus
// it was computed from changes, not just when the orbit itself changes.
//: The four Guide kinds have three different shapes — `{text, citations}`, `{items:[{question,
//: answer, citations}]}` and `{events:[{when, what, citations}]}` — so flattening them is a small
//: switch rather than one generic walk. Every branch ends in `artifactMarkdown`, so all four carry
//: their references out in the same form.
//: Must match the tab labels in `index.html` (`#gtab-*`); pinned by a test.
const GUIDE_KIND_LABELS = { summary: "Summary", faq: "FAQ", timeline: "Timeline", insight: "Insight" };

function guideMarkdown(kind, data) {
  if (!data) return "";
  //: English has no dictionary (its words live in `index.html`), so the fallback IS the English
  //: label. Falling back to `kind` gave a copied artifact the heading `## summary`.
  const heading = t(`studio.tab.${kind}`, GUIDE_KIND_LABELS[kind] || kind);
  if (Array.isArray(data.items)) {
    const every = [];
    const body = data.items
      .map((item) => {
        every.push(...(item.citations || []));
        return `**${item.question}**\n\n${(item.answer || "").trim()}`;
      })
      .join("\n\n");
    return artifactMarkdown(body, every, heading);
  }
  if (Array.isArray(data.events)) {
    const every = [];
    const body = data.events
      .map((event) => {
        every.push(...(event.citations || []));
        //: `description`, which is what `schema.TimelineEvent` declares and what the renderer 40
        //: lines below reads. `event.what` existed exactly once in the product — here — so Copy on
        //: a Timeline produced a list of bare dates with every event's text dropped. The harness
        //: fixture was written to match THIS LINE rather than the wire, so the test asserting
        //: `"- **2012** — crossed"` passed on an input the server cannot produce.
        return `- **${event.when}**: ${(event.description || "").trim()}`;
      })
      .join("\n");
    return artifactMarkdown(body, every, heading);
  }
  return artifactMarkdown(data.text, data.citations, heading);
}

function renderGuideContent(kind, data, runId) {
  const container = document.createElement("div");
  container.className = "guide-prose";

  if (kind === "summary" || kind === "insight") {
    container.appendChild(renderAnswerWithCitations(data.text, data.citations || [], runId));
    return container;
  }

  if (kind === "faq") {
    if (!data.items || !data.items.length) {
      container.textContent = t("studio.noFaq", "No FAQ items. The sources did not give enough to ask about.");
      return container;
    }
    data.items.forEach((item) => {
      const div = document.createElement("div");
      div.className = "guide-item";
      const head = document.createElement("div");
      head.className = "guide-item-head";
      head.textContent = item.question;
      div.appendChild(head);
      div.appendChild(renderAnswerWithCitations(item.answer, item.citations || [], runId));
      container.appendChild(div);
    });
    return container;
  }

  // "timeline"
  if (!data.events || !data.events.length) {
    container.textContent = t("studio.noTimeline", "No timeline events. The sources had nothing to place in time.");
    return container;
  }
  data.events.forEach((event) => {
    const div = document.createElement("div");
    div.className = "guide-item";
    const when = document.createElement("div");
    when.className = "guide-item-when";
    when.textContent = event.when;
    div.appendChild(when);
    div.appendChild(renderAnswerWithCitations(event.description, event.citations || [], runId));
    container.appendChild(div);
  });
  return container;
}

//: What each Studio tab is FOR. Shown as the tab's own hover title and as the hint beside its
//: generate button, so the panel explains itself without a permanent paragraph of prose taking up
//: rail space — the pattern `toolscout`/`cve-reverser` already use for their own controls.
const GUIDE_LABELS = {
  summary: "summary",
  faq: "FAQ",
  timeline: "timeline",
  insight: "key insight",
};

function guideLabel(kind) {
  return t(`studio.kind.${kind}`, GUIDE_LABELS[kind] || kind);
}

const GUIDE_HINTS = {
  summary: "A few paragraphs covering what all your sources say, with citations you can check.",
  faq: "The questions your sources actually answer, each with its answer and a citation.",
  timeline: "Dated events pulled out of your sources and put in order.",
  insight: "The single most important takeaway, in one sentence.",
};

function guideHint(kind) {
  return t(`studio.tip.${kind}`, GUIDE_HINTS[kind] || "");
}

function initStudioPanel() {
  const tabs = document.querySelectorAll("#guide-tabs .tab");
  const body = document.getElementById("guide-body");
  const regenerateBtn = document.getElementById("guide-regenerate");
  // Cache VALUE widened to {result, runId} — storing the result alone (an earlier draft's shape)
  // would lose the run id the moment a user switches tabs and back, breaking citation-turn lookup
  // for a tab already left (found during this phase's own pre-implementation audit).
  // Keyed by kind, VALUE `{result, runId}` — storing the result alone would lose the run id the
  // moment a user switches tabs and back, breaking citation-turn lookup for a tab already left.
  const cache = {
    has: (kind) => kind in state.guides,
    get: (kind) => state.guides[kind],
    set: (kind, value) => {
      state.guides[kind] = value;
    },
    // `delete` was lost when this moved from a `Map` onto `state`, and `regenerateBtn` calls it —
    // so Studio's ↻ Regenerate threw `TypeError: cache.delete is not a function` and did nothing.

    delete: (kind) => {
      delete state.guides[kind];
    },
    clear: () => {
      state.guides = {};
      cacheEpoch += 1;
    },
  };
  //: Bumped whenever the cache is CLEARED (sources changed, orbit switched). A regeneration
  //: that is stopped or fails puts the previous guide back only if no clear happened in between —
  //: otherwise it would resurrect a guide made from a corpus that no longer exists.
  let cacheEpoch = 0;
  //: **A running guide OWNS its status row, not the shared panel.** Four tabs share one
  //: `#guide-body`, and every re-render (another tab, a language switch, a source change) wiped it —
  //: taking the run's only ⏹ Stop with it while the run kept billing, and later drawing the result
  //: into whichever tab happened to be open (Summary content under the FAQ label, with FAQ's Copy
  //: and Regenerate). Invariant 71's rule for `#chat-overview`, applied per kind: the row lives
  //: here, `showKind` re-attaches it, and a result lands in ITS kind's cache.
  const running = new Map(); // kind -> the run's status node
  const failures = new Map(); // kind -> the last run's error, shown above whatever that tab holds
  function markRunning(kind, on) {
    const tab = [...tabs].find((candidate) => candidate.dataset.guideKind === kind);
    if (!tab) return;
    tab.classList.toggle("is-running", on);
    tab.querySelector(".tab-busy")?.remove();
    if (on) {
      tab.setAttribute("aria-busy", "true");
      const dot = elt("span", "tab-busy");
      dot.setAttribute("aria-hidden", "true");
      tab.appendChild(dot);
    } else {
      tab.removeAttribute("aria-busy");
    }
  }
  let activeKind = "summary";

  function setActiveKind(kind) {
    activeKind = kind;
    //: **The same contract the outer strip keeps.** Round thirteen made `.studio-view-tab` a real
    //: tablist and left these — and `#source-kind-tabs`, and the podcast Length group — carrying
    //: which one is current in an underline ALONE. `DESIGN.md` §5.4 calls the two strips "the same
    //: idiom"; only one of them kept the promise, which is SC 4.1.2 fixed one level up and left
    //: open one level down inside the same panel.
    tabs.forEach((tab) => {
      const on = tab.dataset.guideKind === kind;
      tab.classList.toggle("is-active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    });
    const panel = document.getElementById("guide-body");
    //: ONE body for four tabs, so the panel says which tab owns it right now rather than carrying
    //: four `aria-labelledby` targets that are mostly wrong.
    if (panel) panel.setAttribute("aria-labelledby", `gtab-${kind}`);
  }

  function renderCached(kind, cached) {
    body.innerHTML = "";
    if (cached.stale) {
      body.appendChild(
        elt("div", "chat-overview-note", t("studio.guideStale",
          "Made from your sources as they were before they changed. ↻ Regenerate to use the current set."))
      );
    }
    body.appendChild(renderGuideContent(kind, cached.result, cached.runId));
    body.appendChild(renderTickerAffordance(cached.runId));
    //: A Guide kind is an artifact too — arguably the most artifact-shaped thing here — and it had
    //: no way out either. `guideMarkdown` flattens whichever shape this kind is.
    body.appendChild(copyButton(() => guideMarkdown(kind, cached.result)));
  }

  async function fetchKind(kind, { previous = null } = {}) {
    if (!state.orbitId) {
      body.innerHTML = "";
      body.classList.remove("is-pending");
      const note = document.createElement("p");
      note.className = "empty-note";
      note.textContent = t("studio.noOrbit", "Open an orbit with sources, then pick a tab to generate it.");
      body.appendChild(note);
      return;
    }
        const generation = orbitGeneration;
    const epoch = cacheEpoch;
    //: **Stop cancels the NEW run; it must not delete the old result.** Regenerate removed the
    //: cached guide before the run began, so Stop showed the empty offer and a failure showed only
    //: the error — and guides live only in this page's memory (invariant 38), so the one the
    //: reader had paid for was gone for good. The overview and the podcast already put their old
    //: artifact back; this is the same rule for the four guides.
    const restorePrevious = () => {
      if (!previous || generation !== orbitGeneration || epoch !== cacheEpoch) return false;
      cache.set(kind, previous);
      refreshReferenceView();
      return true;
    };
    const token = crypto.randomUUID();
    const runId = `${state.orbitSlug || state.orbitId}-${token}`;
    failures.delete(kind);
    let cancelled = false;
    //: Only THIS run's entry. A Summary ending in orbit A deleted B's running Summary — its
    //: busy dot, and after a tab round trip its only Stop — while B's run kept billing. Identity,
    //: not kind, is what says whose row it is.
    const settle = () => {
      if (running.get(kind) !== status.node) return;
      running.delete(kind);
      markRunning(kind, false);
    };
    const status = runStatus({
      orbitId: state.orbitId,
      runIds: [runId],
      label: t("studio.generating", `Generating the ${guideLabel(kind)}\u2026`, { kind: guideLabel(kind) }),
      onCancel: () => {
        cancelled = true;
        settle();
        restorePrevious();
        // Back to the previous guide if there was one, else the offer — nothing half-written.
        if (activeKind === kind) showKind(kind);
      },
    });
    running.set(kind, status.node);
    markRunning(kind, true);
    if (activeKind === kind) showKind(kind);
    openTicker(state.orbitId, runId, (evt) => status.onEvent(evt));
    try {
      const data = await api(`/orbits/${encodeURIComponent(state.orbitId)}/guide/${kind}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: token }),
      });
      status.finish();
      if (cancelled) return;
      settle();
      if (generation !== orbitGeneration) return;  // switched away — never cache into the new one
      //: `stale` when the sources changed WHILE it ran: the result is paid for, so it is kept, but
      //: it was made from a corpus that no longer exists and must not read as current (a citation
      //: to a removed source looked verified). Invariant 38's third state, for a guide.
      cache.set(kind, { result: data, runId, stale: epoch !== cacheEpoch });
      ensureTitle(); // the guide arrived, so a run was paid for
      refreshReferenceView();
      // Into ITS kind; drawn now only if the reader is looking at that tab.
      if (activeKind === kind) showKind(kind);
    } catch (err) {
      status.finish();
      if (cancelled) return;
      settle();
      if (generation !== orbitGeneration) return;
      // The guide the reader already had comes back, with the failure above it; with nothing to
      // come back, the failure sits above the offer, whose Generate button is the retry.
      restorePrevious();
      failures.set(kind, err.message);
      if (activeKind === kind) showKind(kind);
    }
  }

  // Selecting a tab SHOWS it; it never starts a run. Switching tabs used to fire a real RLM call
  // immediately, so browsing the four kinds to see what they were cost four model runs and a user
  // could not tell which click had committed them to one. The offer is explicit now, matching the
  // chat overview's own "Generate" affordance.
  //: ↻ Regenerate is shown only where there is something to regenerate. It is static markup and
  //: nothing ever toggled it, so on a tab that had generated nothing it sat above the primary
  //: "Generate the Summary" button doing the identical thing under a label implying otherwise:
  //: `cache.delete` on a key that is not there, then the same `fetchKind`. Two controls, one
  //: action, and the quieter one claiming a result exists. This is invariant 71's rule for the
  //: chat overview (the button's WEIGHT varies, its EXISTENCE follows the artifact) applied to the
  //: panel that was missing it. Hiding is safe here: `.guide-regenerate` declares no `display` of
  //: its own and `.btn` carries its own `[hidden]` guard (invariants 36 and 44).
  function showRegenerate(kind) {
    regenerateBtn.hidden = !cache.has(kind);
  }

  function showKind(kind) {
    setActiveKind(kind);
    showRegenerate(kind);
    body.classList.toggle("is-pending", running.has(kind));
    if (running.has(kind)) {
      body.innerHTML = "";
      body.appendChild(running.get(kind));
      return;
    }
    renderIdle(kind);
    if (failures.has(kind)) {
      body.prepend(failureBlock(t("studio.guideFailed", "That did not run"), failures.get(kind)));
    }
  }

  // What a tab shows when nothing is running for it: its guide, or the offer to make one.
  function renderIdle(kind) {
    if (cache.has(kind)) {
      renderCached(kind, cache.get(kind));
      return;
    }
    body.innerHTML = "";
    if (!state.orbitId || !state.sources.length) {
      const note = document.createElement("p");
      note.className = "empty-note";
      note.textContent = t("studio.addSourceFirst", "Add a source first, then generate this.");
      body.appendChild(note);
      return;
    }
    const offer = document.createElement("div");
    offer.className = "chat-starter";
    const btn = document.createElement("button");
    btn.type = "button";
    // `.btn`, not `.btn-primary`. The Studio is a secondary surface, and its Generate sat 500px
    // from the chat's "Summarise and suggest questions" in an identical copper fill at an identical
    // weight - two primary actions with near-synonymous labels on one screen. Demoting this one
    // removes a fill and makes the pair read as what they are: the thread's opener, and a Studio
    // artifact you ask for.
    btn.className = "btn";
    btn.textContent = t("studio.generate", `Generate ${guideLabel(kind)}`, { kind: guideLabel(kind) });
    btn.addEventListener("click", () => fetchKind(kind));
    offer.appendChild(btn);
    // Rebuilt on every tab switch, so the guard has to be re-applied to the NEW button.
    queueMicrotask(syncRunGuards);
    const hint = document.createElement("p");
    // `.hint`, not `.empty-note`. It describes what the button above it will MAKE; an empty state
    // reports that there is nothing here. They shared a class and therefore a voice, which is the
    // thing the References panel was pulled up on - "what this is" and "there is nothing here" have
    // to read differently or neither lands.
    hint.className = "hint";
    hint.textContent = guideHint(kind);
    offer.appendChild(hint);
    body.appendChild(offer);
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => showKind(tab.dataset.guideKind));
    //: Arrow-key roving, which a tablist owes — see the same handler on `.studio-view-tab`.
    tab.addEventListener("keydown", (event) => {
      const list = [...tabs];
      const step = { ArrowRight: 1, ArrowLeft: -1, Home: -list.length, End: list.length }[event.key];
      if (step === undefined) return;
      event.preventDefault();
      const next = list[Math.min(list.length - 1, Math.max(0, list.indexOf(tab) + step))];
      showKind(next.dataset.guideKind);
      next.focus();
    });
  });

  regenerateBtn.addEventListener("click", () => {
    const previous = cache.get(activeKind) || null;
    cache.delete(activeKind);
    // Hidden for the duration: the run has no cached result behind it any more, and `runStatus`
    // owns the panel while it is in flight (invariant 47).
    showRegenerate(activeKind);
    fetchKind(activeKind, { previous });
  });

  function invalidateCache() {
    cache.clear();
  }

  // Opening an orbit does NOT auto-fetch a Guide kind — that would burn a model call just from
  // opening an orbit. Neither does SELECTING a tab any more (see `showKind`); every run is an
  // explicit button press.
  // The other orbit's runs are not this one's: their results are refused by the generation
  // guard, so their rows and marks must not follow the reader in.
  store.on("orbit:switched", () => {
    invalidateCache();
    running.forEach((_node, kind) => markRunning(kind, false));
    running.clear();
    failures.clear();
    showKind("summary");
  });
  // A source changing invalidates the cache AND re-renders, so the panel goes back to offering a
  // fresh generation rather than silently holding a result computed from a corpus that has moved.
  //: `relabel`: a LANGUAGE switch re-emits this to redraw labels, and treating it as a corpus
  //: change threw away every generated guide — memory-only (invariant 38), so gone for good —
  //: behind a setting whose own help says it "never" touches what the model writes.
  store.on("sources:changed", ({ relabel } = {}) => {
    if (!relabel) {
      invalidateCache();
      failures.clear();
    }
    showKind(activeKind);
  });

  showKind("summary");
}

// --- Studio panel: podcast player ------------------------------------------------------------

function formatTimecode(seconds) {
  const total = Math.max(0, Math.floor(seconds));
  const ss = String(total % 60).padStart(2, "0");
  const mm = Math.floor(total / 60) % 60;
  const hh = Math.floor(total / 3600);
  // An hour component only when there is one, so a three-minute episode stays `2:41` rather than
  // `0:02:41` — but a long one no longer renders `63:05`.
  return hh ? `${hh}:${String(mm).padStart(2, "0")}:${ss}` : `${mm}:${ss}`;
}

//: The play/scrub/time controls, driving a headless `<audio>`. A real `<button>` and a real
//: `<input type="range">` rather than hand-rolled widgets: both are keyboard-operable and
//: screen-reader-nameable for free, and a slider is the one control where re-implementing the
//: interaction (drag, arrows, Home/End, page keys) buys nothing and loses a lot.
function buildTransport(player) {
  const bar = elt("div", "transport");

  const toggle = elt("button", "transport-play");
  toggle.type = "button";
  const scrub = document.createElement("input");
  scrub.type = "range";
  scrub.className = "transport-scrub";
  scrub.min = "0";
  scrub.max = "0";
  scrub.step = "0.1";
  scrub.value = "0";
  scrub.disabled = true;
  scrub.setAttribute("aria-label", t("podcast.seek", "Seek"));
  const clock = elt("span", "transport-time", "--:-- / --:--");

  const paintToggle = () => {
    const playing = !player.paused && !player.ended;
    toggle.textContent = playing ? "\u23f8" : "\u25b6";
    const label = playing ? t("podcast.pause", "Pause") : t("podcast.play", "Play");
    toggle.setAttribute("aria-label", label);
    toggle.dataset.tip = label;
  };
  const paintClock = () => {
    const total = Number.isFinite(player.duration) ? formatTimecode(player.duration) : "--:--";
    clock.textContent = `${formatTimecode(player.currentTime || 0)} / ${total}`;
    //: A range's value is a NUMBER to a screen reader ("437"), which means nothing here. The
    //: position is a TIME, so it is announced as one.
    scrub.setAttribute("aria-valuetext", clock.textContent);
  };

  toggle.addEventListener("click", () => {
    if (player.paused || player.ended) {
      // Same swallow as `seek`: the promise rejects when the media cannot start (the persisted file
      // was cleared and `audio/file` 404s, or an autoplay policy blocks it).
      const played = player.play();
      if (played && typeof played.catch === "function") played.catch(() => {});
    } else {
      player.pause();
    }
  });
  //: Live scrubbing: `input` fires throughout a drag and for every arrow key, and seeking on each
  //: one is what makes the transcript's `.is-speaking` follow the handle instead of jumping at the
  //: end. `timeupdate` then writes the same value back, so the two never fight.
  scrub.addEventListener("input", () => {
    player.currentTime = Number(scrub.value);
    paintClock();
  });

  player.addEventListener("loadedmetadata", () => {
    if (!Number.isFinite(player.duration)) return;
    scrub.max = String(player.duration);
    scrub.disabled = false;
    paintClock();
  });
  player.addEventListener("timeupdate", () => {
    scrub.value = String(player.currentTime);
    paintClock();
  });
  ["play", "pause", "ended"].forEach((kind) => player.addEventListener(kind, paintToggle));

  paintToggle();
  paintClock();
  bar.append(toggle, scrub, clock);
  return bar;
}

function renderPodcastUtterance(utterance, runId, { start = null, onSeek = null } = {}) {
  const div = document.createElement("div");
  div.className = "podcast-utterance";

  const speaker = document.createElement("div");
  speaker.className = "podcast-speaker";
  //: Translated: this repeats once per utterance down a transcript of up to 90 lines, and the
  //: product already had the Chinese term — `settings.voiceA` says 主持人 A four screens away.
  speaker.textContent =
    utterance.speaker === "host_a"
      ? t("podcast.hostA", "Host A")
      : t("podcast.hostB", "Host B");

  // A timecode only when the provider actually reported one. Without it the line stays a plain
  // transcript entry rather than showing a made-up 0:00 or becoming a seek target that lies.
  if (start !== null) {
    const stamp = document.createElement("button");
    stamp.type = "button";
    stamp.className = "podcast-timecode";
    stamp.textContent = formatTimecode(start);
    stamp.addEventListener("click", () => onSeek && onSeek(start));
    speaker.appendChild(stamp);
    div.classList.add("is-seekable");
    div.addEventListener("click", (event) => {
      // The line itself seeks, but never when the click was meant for something inside it — a
      // citation span opens its reference, the timecode has its own handler, and
      // `.reference-link` is the "N references" button `renderAnswerWithCitations` appends as a
      // SIBLING inside this same utterance. That one was MISSING while two dead classes from the
      // replaced citation-list markup were still listed — found by an independent review, and it
      // meant clicking "2 references" both jumped the player and switched the panel away.
      if (event.target.closest(".citation, .reference-link, .podcast-timecode")) {
        return;
      }
      // `click` also fires on the mouseup that ends a drag-selection, so selecting transcript prose
      // to quote it would otherwise seek and autoplay.
      const selection = window.getSelection();
      if (selection && !selection.isCollapsed && selection.toString().trim()) return;
      if (onSeek) onSeek(start);
    });
  }

  div.appendChild(speaker);
  div.appendChild(renderAnswerWithCitations(utterance.text, utterance.citations || [], runId));
  return div;
}

// Renders an episode: player, download, transcript. ONE function for both the just-generated case
// and the reopened-orbit case, so a persisted episode can never render differently from a fresh
// one — the shape the podcast was missing before it was persisted at all.
//
// `audioSrc` is a URL on this server (`GET .../audio/file`), not an object URL: the browser can
// range-request it, so seeking in a long episode doesn't re-download it, and reopening an orbit
// costs no re-synthesis. The `cacheBust` token is what makes REGENERATING visible — the path is
// stable per orbit, so without it the browser would keep serving the previous episode.
function renderPodcast(body, { utterances, runId, audioSrc, stale, suffix, offsets }) {
  body.innerHTML = "";

  //: **A persisted episode whose FILE is gone rendered a fully armed, completely dead transport.**
  //: `GET .../audio/file` 404s, `player.play()`'s promise rejects, and the rejection is swallowed
  //: (deliberately — an unhandled rejection in the console is worse) — so pressing Play produced
  //: nothing at all: no toast, no state change, no message, on the most expensive artifact the
  //: product makes (invariant 64) and the one it persists on purpose (invariant 42). Reachable by
  //: any backup restore, any `audio/` cleanup, or a desktop sync that moves the JSON without the
  //: blob. The Download link pointed at the same 404.
  //:
  //: The server already says so: `audio_suffix` is null when `find_audio` finds nothing. So the
  //: state is STATED — DESIGN §8's rule — and the transcript, which is the part that survived, is
  //: kept. A Play button that can never play is invariant 60's claim in a control.
  const missing = !suffix;

  if (stale) {
    const note = document.createElement("div");
    note.className = "chat-overview-head";
    note.textContent = t("podcast.stale", "Podcast · sources have changed since this");
    body.appendChild(note);
  }

  const player = document.createElement("audio");
  //: **Headless, with a transport built out of this product's own parts.** `controls = true` gave
  //: the most expensive artifact in the product the browser's stock black pill — play, slider,
  //: volume, a `⋮` overflow menu — sitting inside a hand-drawn ink-on-paper panel, and it was the
  //: only un-themed surface left: the native file picker was replaced for showing OS chrome in the
  //: wrong locale, and the scrollbars and `<select>`s were themed for the same reason. It is also
  //: the worst one to leave cross-platform, because a Tauri build is WKWebView on macOS, WebView2
  //: on Windows and WebKitGTK on Linux — three genuinely different players, none of them this one.
  //: The element still does all the work; only its chrome is ours.
  //: `metadata`, not `none`: `none` left the duration unknown until the reader pressed play, so the
  //: transport opened with a dead scrub bar and `--:--`. `metadata` fetches the header, not the
  //: episode, which is what the original "don't pull a multi-MB file on every orbit open" was
  //: protecting — and `audio/file` is a `FileResponse`, which serves ranges.
  if (missing) {
    const gone = elt("div", "podcast-gone");
    gone.appendChild(
      i18nText(
        elt("span", "podcast-gone-why"),
        "podcast.audioGone",
        "This episode's audio is gone. The transcript is still here."
      )
    );
    body.appendChild(gone);
  } else {
    player.preload = "metadata";
    player.src = audioSrc;
    body.appendChild(player);
    body.appendChild(buildTransport(player));
  }

  const download = document.createElement("a");
  download.className = "btn podcast-download";
  download.href = audioSrc;
  // A model-authored title reaches a filename here, so it is slugged rather than interpolated:
  // `download` is an attribute the browser turns into a path component.
  const stem = (state.title || state.orbitId || "orbit")
    .replace(/[^\w\u4e00-\u9fff-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  // The extension follows the SERVED file, not a hardcoded guess: chatterbox writes WAV and edge-tts
  // writes MP3, so naming the download `.mp3` unconditionally would mislabel half of them. An audit
  // found this listed among invariant 43's "handled" consequences when it was not.
  const ext = (suffix || "").replace(/^\./, "");
  download.download = ext ? `${stem || "orbit"}.${ext}` : stem || "orbit";
  download.textContent = ext
    ? t("podcast.download", `\u2913 Download ${ext}`, { ext })
    : t("podcast.downloadPlain", "\u2913 Download audio");
  //: Not offered when there is nothing behind it — it pointed at the same 404 as the Play button,
  //: with a `download` filename and no extension.
  if (!missing) body.appendChild(download);

  if (runId) body.appendChild(renderTickerAffordance(runId));

  const transcript = document.createElement("div");
  transcript.className = "podcast-transcript";

  // Timing is usable only when there is exactly one offset per utterance AND the offsets actually
  // advance. The length check alone is not enough: a provider that reports no boundaries at all
  // yields `[0.0, 0.0, ...]`, which is the RIGHT LENGTH and would stamp every line `0:00`, highlight
  // the second row for the whole episode and seek every click to zero (an independent review
  // simulated exactly that). A persisted episode from before offsets existed has none and falls
  // back here too — mis-aligned subtitles are worse than none, and `schema.Podcast.offsets` says so.
  const timed =
    Array.isArray(offsets) &&
    offsets.length === utterances.length &&
    offsets.every((v, i) => Number.isFinite(v) && v >= 0 && (i === 0 || v > offsets[i - 1]));
  const seek = (seconds) => {
    // `seconds`, not `t`. This parameter was RENAMED from `t` to stop it shadowing the i18n
    // function (an independent review found three such closures and warned that adding a
    // translated string inside one would throw) — and the body was not renamed with it, so every
    // seek assigned the i18n FUNCTION to `currentTime`, coerced to NaN, and did nothing. Clicking a
    // timecode silently stopped working, reported by a user.
    player.currentTime = seconds;
    // The play promise rejects when the media cannot start (the persisted file was cleared and
    // `audio/file` 404s, or autoplay policy blocks it). Seeking still worked; swallow it rather
    // than leaving an unhandled rejection in the console.
    const played = player.play();
    if (played && typeof played.catch === "function") played.catch(() => {});
  };
  const rows = utterances.map((u, i) => {
    const row = renderPodcastUtterance(u, runId, {
      start: timed ? offsets[i] : null,
      onSeek: timed ? seek : null,
    });
    transcript.appendChild(row);
    return row;
  });
  body.appendChild(transcript);

  if (!timed) return;
  // Only a timed transcript becomes its own scroll box; an untimed one has nothing following it and
  // reads better inline.
  transcript.classList.add("is-timed");

  // Subtitle behaviour: the line whose window contains the playhead is current. `timeupdate` fires
  // ~4x a second, so this runs often — it does an O(n) scan over a transcript of a few dozen lines
  // and touches the DOM only when the index actually changes.
  let current = -1;
  player.addEventListener("timeupdate", () => {
    const t = player.currentTime;
    let index = -1;
    for (let i = 0; i < offsets.length; i += 1) {
      if (offsets[i] <= t) index = i;
      else break;
    }
    if (index === current) return;
    if (rows[current]) rows[current].classList.remove("is-speaking");
    current = index;
    const row = rows[current];
    if (!row) return;
    row.classList.add("is-speaking");
    // Scroll the transcript's OWN box (it has `overflow-y: auto`), never `scrollIntoView` — that
    // walks EVERY scrollable ancestor, so a listener who had scrolled the studio column away to
    // read something else got dragged back to the podcast panel every few seconds. Measured with
    // rects rather than `offsetTop`, which is relative to whatever the offsetParent happens to be
    // and would silently mis-scroll if this box ever stops being positioned. Only move when the
    // line is actually outside the box.
    const rowBox = row.getBoundingClientRect();
    const viewBox = transcript.getBoundingClientRect();
    if (rowBox.top < viewBox.top) {
      transcript.scrollTop -= viewBox.top - rowBox.top;
    } else if (rowBox.bottom > viewBox.bottom) {
      transcript.scrollTop += rowBox.bottom - viewBox.bottom;
    }
  });
}

//: The reader's last choice, remembered across reloads. `localStorage` rather than a server
//: setting: it is a per-listen preference, not a property of the orbit, and the settings page is
//: deliberately narrow (invariant 41).
const PODCAST_LENGTH_KEY = "penumbra-podcast-length";
const PODCAST_LENGTHS = new Set(["short", "default", "long"]);

function podcastLength() {
  const stored = localStorage.getItem(PODCAST_LENGTH_KEY);
  return PODCAST_LENGTHS.has(stored) ? stored : "default";
}

function initPodcastPlayer() {
  const generateBtn = document.getElementById("podcast-generate");
  const body = document.getElementById("podcast-body");

  const lengthOpts = [...document.querySelectorAll(".podcast-length .length-opt")];
  const paintLength = () => {
    const current = podcastLength();
    //: `aria-pressed`, not `aria-selected`: these three change a VALUE the next run will use, they
    //: do not switch a view, so they are toggles rather than tabs. Which one is chosen was carried
    //: by a fill alone — and this one decides how much the next press costs (invariant 63).
    lengthOpts.forEach((opt) => {
      const on = opt.dataset.length === current;
      opt.classList.toggle("is-active", on);
      opt.setAttribute("aria-pressed", on ? "true" : "false");
    });
  };
  lengthOpts.forEach((opt) => {
    opt.addEventListener("click", () => {
      localStorage.setItem(PODCAST_LENGTH_KEY, opt.dataset.length);
      paintLength();
    });
  });
  paintLength();

  // No object-URL bookkeeping any more: the audio is a real URL on this server, so there is nothing
  // to revoke and no revocation ORDER to get right (blueprint P2.6's fix is moot rather than wrong).
  function clearPlayer() {
    body.innerHTML = "";
  }

  //: The persisted episode, rendered from `state.podcast`. Also what a STOPPED or FAILED
  //: regeneration falls back to: the panel is cleared when a run starts, and neither path put the
  //: old episode back, so pressing Stop looked like it had deleted the episode (the file on disk
  //: was fine — a reload brought it back). The overview's regenerate-then-Stop already restored
  //: its old content; now the podcast does too.
  function renderSavedEpisode() {
    const podcast = state.podcast;
    if (!podcast || !state.orbitId) return;
    renderPodcast(body, {
      utterances: podcast.utterances,
      runId: podcast.run_id,
      //: Versioned by the episode's run id, as the freshly generated path is: after a regeneration
      //: the plain URL may still be cached with the PREVIOUS episode's bytes.
      audioSrc: withToken(
        `/orbits/${encodeURIComponent(state.orbitId)}/audio/file` +
          (podcast.run_id ? `?v=${encodeURIComponent(podcast.run_id)}` : "")
      ),
      suffix: podcast.audio_suffix,
      offsets: podcast.offsets,
      stale: podcast.stale,
    });
  }

  // THREE states, the same shape the chat overview already has (invariant 38): never generated ->
  // an offer; generated -> the episode, with regeneration a quieter second action; generated but
  // STALE -> the episode, marked, and the same regenerate button reading as the obvious next move.
  // It used to be one permanent primary button sitting above a player that already existed, which
  // put the most prominent control in the panel on the one action a reader with an episode is least
  // likely to want — and made "have I already made one?" a question the button could not answer.
  //: Re-DECIDE the button rather than switching it on. A question may be running in this orbit
  //: (asking during a podcast is allowed), and `syncRunGuards` — which would keep every starter
  //: off while it does — skipped this button because it was already disabled by its own run. So
  //: Stop or a failure turned Generate back on mid-question.
  function releaseGenerate() {
    syncGenerateButton();
    queueMicrotask(syncRunGuards);
  }

  function syncGenerateButton() {
    const podcast = state.podcast;
    //: **The most expensive press in the product was live on an empty orbit.** The four Studio
    //: guide tabs are gated by `showKind` ("Add a source first, then generate this"); this button
    //: lives statically in `index.html` and its only guard was "is an orbit open". The selected
    //: Studio tab is remembered, so a reader who last used Audio presses "+ New orbit" and lands
    //: on an enabled Generate podcast — a `long` tier is `PODCAST_TIMEOUT_FACTOR` 5.0 over 60-90
    //: accumulated utterances (invariant 64), spent on a corpus that is the empty string. The
    //: server refuses it now; this is the half that means the reader never finds out that way.
    const grounded = (state.sources || []).length > 0;
    generateBtn.disabled = !grounded;
    generateBtn.dataset.tip = grounded
      ? t("podcast.generateTip", "Writes a script from your sources, then speaks it.")
      : t("podcast.needsSource", "Add a source first, then generate this.");
    if (!podcast) {
      generateBtn.textContent = t("podcast.generate", "Generate podcast");
      generateBtn.className = "btn btn-offer btn-block";
      return;
    }
    generateBtn.textContent = podcast.stale
      ? t("podcast.regenerateStale", "\u21bb Regenerate \u00b7 sources have changed")
      : t("podcast.regenerate", "\u21bb Regenerate podcast");
    // Secondary once an episode exists: regenerating costs a full model run plus synthesis
    // (invariant 43), so it must not be the loudest thing on a panel that already has what it makes.
    generateBtn.className = "btn btn-block";
  }

  // A persisted episode renders on open, which is the whole point of persisting it.
  store.on("orbit:switched", () => {
    clearPlayer();
    syncGenerateButton();
    renderSavedEpisode();
  });

  // Adding or removing a source flips `podcast.stale` server-side, and the button's LABEL carries
  // that verdict — so it has to follow. Only the button: re-rendering the panel would rebuild its
  // `<audio>` and interrupt playback, which is the same reason `renumberStrokes` re-stamps rather
  // than re-renders. The stale marker inside the player catches up on the next open.
  store.on("sources:changed", () => syncGenerateButton());

  generateBtn.addEventListener("click", async () => {
    if (!state.orbitId) {
      notify(t("err.openOrbitFirst", "Open an orbit first."));
      return;
    }
    generateBtn.disabled = true;
    const generation = orbitGeneration;
    const token = crypto.randomUUID();
    const runId = `${state.orbitSlug || state.orbitId}-${token}`;
    body.classList.add("is-pending");
    body.innerHTML = "";
    let cancelled = false;
    const status = runStatus({
      orbitId: state.orbitId,
      runIds: [runId],
      label: t("podcast.writing", "Writing the script\u2026"),
      onCancel: () => {
        cancelled = true;
        body.classList.remove("is-pending");
        clearPlayer();
        if (generation === orbitGeneration) renderSavedEpisode();
        releaseGenerate();
      },
    });
    body.appendChild(status.node);
    // TWO phases, and only the FIRST is a traced, cancellable subprocess run. When the script run
    // ends the server starts synthesizing in-process (invariant 29) — no trace events, no way to
    // stop it, and up to fifteen minutes on the local provider (invariant 43). The label said
    // "Writing the script" for that whole second stretch, which is not what was happening.
    openTicker(state.orbitId, runId, (evt) => {
      status.onEvent(evt);
      // `done` ONLY, not every terminal kind: announcing a stage that will never start — and
      // greying out Stop — is worse than saying nothing while the HTTP error lands.
      if (evt.kind === "done") {
        status.setPhase(
          t("podcast.synthesizing", "Synthesizing the audio\u2026 (this stage cannot be stopped)"),
          { stoppable: false },
        );
      }
    });
    try {
      const data = await api(`/orbits/${encodeURIComponent(state.orbitId)}/audio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // See generateOverview: `fresh` exactly when this press is a REGENERATE.
        body: JSON.stringify({
          run_id: token,
          length: podcastLength(),
          fresh: Boolean(state.podcast),
        }),
      });
      status.finish();
      if (cancelled) return;
      if (generation !== orbitGeneration) return;  // switched away — the old episode is not theirs
      body.classList.remove("is-pending");
      body.innerHTML = "";

      if (!data.utterances.length) {
        //: The server CLEARED the episode and its audio for an empty script (invariant 42), so the
        //: page must forget it too — or a later Stop would restore it with a Play that 404s.
        state.podcast = null;
        body.textContent = t("podcast.empty", "No podcast script. The sources did not give enough to discuss.");
        syncGenerateButton();
        return;
      }

      state.podcast = {
        utterances: data.utterances,
        run_id: runId,
        offsets: data.offsets,
        //: Kept, because `renderSavedEpisode` reads it to know the file exists: without it a Stop or
        //: failed REgeneration re-rendered this episode as "This episode's audio is gone" and took
        //: away Play and Download, while the mp3 sat intact on disk.
        audio_suffix: data.audio_suffix,
        stale: false,
      };
      ensureTitle(); // the episode arrived, so a run was paid for
      renderPodcast(body, {
        utterances: data.utterances,
        runId,
        // Cache-busted: the path is stable per orbit, so without this the browser would keep
        // serving the episode it already has and "Regenerate" would look like it did nothing.
        audioSrc: withToken(
          `/orbits/${encodeURIComponent(state.orbitId)}/audio/file?v=${token}`
        ),
        stale: false,
        suffix: data.audio_suffix,
        offsets: data.offsets,
      });
      // The panel now HAS an episode, so the button stops offering to make one.
      syncGenerateButton();
    } catch (err) {
      status.finish();
      if (cancelled) return;
      if (generation !== orbitGeneration) return;
      body.classList.remove("is-pending");
      body.textContent = "";
      // The episode that was there before is still there: show it under the failure.
      renderSavedEpisode();
      body.prepend(failureBlock(t("podcast.failed", "The episode did not get made"), err.message));
    } finally {
      //: Only in the orbit that pressed it. An episode ending in A switched B's Generate back ON
      //: in the middle of B's own run, and a press started a second paid run whose status row the
      //: first one's render then overwrote — no Stop for it anywhere. A switch re-decides the
      //: button for the new orbit (`syncGenerateButton`).
      if (generation === orbitGeneration) releaseGenerate();
    }
  });

  // NO second `orbit:switched` subscriber here. There used to be one (`clearPlayer`), registered
  // AFTER the render handler above — and `store.emit` runs subscribers in registration order, so it
  // blanked the panel the render handler had just filled. A persisted episode therefore never
  // appeared on orbit open, which is the entire point of persisting it. The render handler
  // clears first itself.
}

// --- Notes section (Studio panel) ----------------------------------------------------------------
//
// NotebookLM's research-loop closing feature: a manual note, or a Chat answer saved as one
// (`addNote`, wired from `renderTurn`), can later be PROMOTED into a real, independently-
// citable source — the "read a source → note something → the note becomes a source → keep going"
// loop this project had no concept of at all before this. Built with createElement/textContent
// throughout, same discipline every other list in this file already follows — a note's `text` is
// user-authored (or copied from a model answer) and never assumed safe to treat as markup.

function renderNoteItem(note) {
  const li = document.createElement("li");
  li.className = "note-item";

  const text = document.createElement("div");
  text.className = "note-text";
  text.textContent = note.text;
  li.appendChild(text);

  const actions = document.createElement("div");
  actions.className = "note-actions";

  const promoteBtn = document.createElement("button");
  promoteBtn.type = "button";
  promoteBtn.className = "btn note-promote";
  promoteBtn.textContent = t("notes.promote", "→ Promote to source");
  // `data-tip`, not the native `title`: this project's own tooltip is instant and styled, and the
  // native one's ~1s delay is what made hover help feel disconnected from the hover effect.
  promoteBtn.dataset.tip = t(
    "notes.promoteHelp",
    "Turn this note into a real source. Only then can a later question cite it; a note on its own is just text, with no citations.",
  );
  promoteBtn.addEventListener("click", async () => {
    promoteBtn.disabled = true;
    try {
      const orbit = await api(
        `/orbits/${encodeURIComponent(state.orbitId)}/notes/${encodeURIComponent(note.id)}/promote`,
        { method: "POST" }
      );
      state.sources = orbit.sources;
      state.notes = orbit.notes;
      store.emit("sources:changed", { sources: state.sources });
      store.emit("notes:changed", { notes: state.notes });
    } catch (err) {
      notify(t("err.promoteNote", `Could not promote note: ${err.message}`, { message: err.message }));
      promoteBtn.disabled = false;
    }
  });
  actions.appendChild(promoteBtn);

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "btn note-delete";
  deleteBtn.textContent = "✕";
  //: Named, and CONFIRMED like every other delete here (source, orbit, Horizon Forget): a note is
  //: the reader's own words, and one stray click removed it for good with nothing to undo.
  deleteBtn.setAttribute("aria-label", t("notes.delete", "Delete this note"));
  deleteBtn.dataset.tip = t("notes.delete", "Delete this note");
  deleteBtn.addEventListener("click", async () => {
    if (!(await confirmAction(t("notes.deleteConfirm", "Delete this note? This cannot be undone.")))) return;
    deleteBtn.disabled = true;
    try {
      const orbit = await api(
        `/orbits/${encodeURIComponent(state.orbitId)}/notes/${encodeURIComponent(note.id)}`,
        { method: "DELETE" }
      );
      state.notes = orbit.notes;
      store.emit("notes:changed", { notes: state.notes });
    } catch (err) {
      notify(t("err.deleteNote", `Could not delete note: ${err.message}`, { message: err.message }));
      deleteBtn.disabled = false;
    }
  });
  actions.appendChild(deleteBtn);

  li.appendChild(actions);
  return li;
}

async function addNote(text) {
  if (!state.orbitId) return;
  try {
    const orbit = await api(`/orbits/${encodeURIComponent(state.orbitId)}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    state.notes = orbit.notes;
    store.emit("notes:changed", { notes: state.notes });
  } catch (err) {
    notify(t("err.saveNote", `Could not save note: ${err.message}`, { message: err.message }));
    // **RETHROWN, so the caller does not clear the field.** Swallowing it here left the submit
    // handler on its success path, which does `input.value = ""` — so a failed save deleted what
    // the reader had typed and left a toast where their note used to be. Invariant 32 content,
    // gone. The add-SOURCE path gets this right: its clear is on the success line inside the try.
    throw err;
  }
}

function initNotesPanel() {
  const form = document.getElementById("add-note-form");
  // The other half of `syncAddSourceSubmit`'s reason: Add note returned silently on an empty
  // textarea too. One field, so no tab to consult.
  const noteField = document.getElementById("note-text");
  const noteSubmit = form.querySelector("button[type=submit]");
  const syncNoteSubmit = () => {
    if (noteSubmit) noteSubmit.disabled = !noteField.value.trim();
  };
  noteField.addEventListener("input", syncNoteSubmit);
  syncNoteSubmit();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.orbitId) {
      notify(t("err.openOrbitFirst", "Open an orbit first."));
      return;
    }
    const input = document.getElementById("note-text");
    const value = input.value.trim();
    if (!value) return;
    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    try {
      await addNote(value);
      input.value = "";
    } catch {
      // `addNote` has already shown the reason; this exists so the rethrow that PROTECTS the typed
      // text does not become an unhandled rejection. The field keeps what the reader wrote.
    } finally {
      // Through the sync, not a bare `false`: the field is empty again, so the button that
      // promises to add a note has nothing to add. Re-enabling it unconditionally is the same
      // small lie `syncCaptureSend` was written to stop in the Horizon.
      submitBtn.disabled = false;
      syncNoteSubmit();
    }
  });

  store.on("notes:changed", ({ notes }) => {
    const list = document.getElementById("note-list");
    const empty = document.getElementById("notes-empty");
    list.innerHTML = "";
    notes.forEach((note) => list.appendChild(renderNoteItem(note)));
    empty.hidden = notes.length > 0;
  });
}

// --- Studio rail: four views behind one switcher, collapsible ------------------------------------
//
// It used to be three sections stacked in one scrolling column, each with its own heading and body.
// An orbit with a generated guide, an episode and a few notes became a column nobody could find
// anything in — and there was nowhere to put a fourth thing. Views also give References a home.

const STUDIO_VIEW_KEY = "penumbra-studio-view";
const STUDIO_COLLAPSED_KEY = "penumbra-studio-collapsed";
const STUDIO_WIDTH_KEY = "penumbra-studio-width";

//: The panel's size limits. Below `STUDIO_COLLAPSE_AT` a drag means "put it away" rather than "make
//: it very narrow" — a 90px panel is useless, so snapping to the icon rail is what the gesture
//: actually meant.
const STUDIO_MIN_WIDTH = 240;
const STUDIO_MAX_WIDTH = 720;
const STUDIO_COLLAPSE_AT = 170;
//: HYSTERESIS, and the ORDER is the whole point: a two-state toggle driven by one continuous value
//: is stable only while the "open" threshold is at or above the "close" one. An earlier attempt put
//: it BELOW (expand at 90, collapse at 170) to make re-opening from the rail cheap, which turned
//: 90–170 into a band where every single pointermove flipped the state — the panel visibly
//: shuddering between two widths. Expanding at exactly the minimum width is the value that both
//: satisfies the ordering AND opens the panel with no jump at all: at the crossing the pointer and
//: the panel are the same number. The dead band [170, 240) is then precisely the range the panel
//: could not have honoured anyway, and `--studio-rail` below keeps it from feeling dead.
const STUDIO_EXPAND_AT = STUDIO_MIN_WIDTH;
//: 2.9rem, the collapsed track in `style.css`. Repeated here because JS has to clamp against it.
const STUDIO_RAIL_WIDTH = 46;

// --- resizable side panels ----------------------------------------------------------------------
//
// One behaviour for every side panel, the same the Studio's grip already had: drag the grip to size
// it, drag it narrower than it can be to put it away (to a strip, or a rail), double-click to
// toggle, arrow keys to size, Enter to toggle. The width follows the pointer during a drag and is
// only remembered when the drag ends open, so putting a panel away never overwrites the width the
// reader chose. The column between the panels keeps at least `PANEL_MIDDLE_MIN`: a panel stops
// growing there rather than squeezing the map or the conversation to nothing.

const PANEL_MIDDLE_MIN = 360;

function readStored(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, String(value));
  } catch {
    // blocked storage: the width lasts for this page only
  }
}

//: `side` is the edge the grip sits on: "right" for a left-hand panel (it grows as the pointer
//: moves right), "left" for a right-hand one. `others` lists the other panels in the same view, so
//: the middle column's floor can be kept. Collapse hysteresis as the Studio's: put away below
//: `collapseAt`, open again only at `min`, so no pointer position flips it back and forth.
function makePanelGrip({
  panel, handle, side, cssVar, railVar, min, max, collapseAt, railPx, key, initial = min, others = () => [],
}) {
  let applied = min;
  const isCollapsed = () => panel.classList.contains("is-collapsed");
  const setCollapsed = (value, { persist = true } = {}) => {
    if (isCollapsed() === value) return;
    panel.classList.toggle("is-collapsed", value);
    handle.setAttribute("aria-expanded", String(!value));
    if (persist) writeStored(`${key}-collapsed`, value ? "1" : null);
    window.dispatchEvent(new Event("panels-changed"));
  };
  const cap = () => {
    const taken = others().reduce((sum, el) => sum + (el && el.offsetParent ? el.getBoundingClientRect().width : 0), 0);
    return Math.max(min, Math.min(max, window.innerWidth - taken - PANEL_MIDDLE_MIN));
  };
  const applyWidth = (px) => {
    applied = Math.min(cap(), Math.max(min, px));
    document.documentElement.style.setProperty(cssVar, `${Math.round(applied)}px`);
    const span = max - min;
    handle.setAttribute("aria-valuenow", String(span ? Math.round(((applied - min) / span) * 100) : 0));
    return applied;
  };
  const edge = () => {
    const box = panel.getBoundingClientRect();
    return side === "right" ? box.left : box.right;
  };
  let dragging = false;
  handle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    dragging = true;
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add("is-resizing");
    event.preventDefault();
  });
  handle.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const width = side === "right" ? event.clientX - edge() : edge() - event.clientX;
    if (width < (isCollapsed() ? min : collapseAt)) {
      setCollapsed(true);
      // The strip follows the pointer through the dead band, so pulling always shows something.
      document.documentElement.style.setProperty(railVar, `${Math.round(Math.min(min, Math.max(railPx, width)))}px`);
      return;
    }
    setCollapsed(false);
    document.documentElement.style.removeProperty(railVar);
    applyWidth(width);
  });
  const endDrag = (event) => {
    if (!dragging) return;
    dragging = false;
    try {
      handle.releasePointerCapture(event.pointerId);
    } catch {
      // the pointer was already gone
    }
    document.body.classList.remove("is-resizing");
    document.documentElement.style.removeProperty(railVar);
    if (!isCollapsed()) writeStored(`${key}-width`, Math.round(applied));
    window.dispatchEvent(new Event("panels-changed"));
  };
  handle.addEventListener("pointerup", endDrag);
  handle.addEventListener("pointercancel", endDrag);
  handle.addEventListener("dblclick", () => setCollapsed(!isCollapsed()));
  handle.addEventListener("keydown", (event) => {
    const grow = side === "right" ? "ArrowRight" : "ArrowLeft";
    const shrink = side === "right" ? "ArrowLeft" : "ArrowRight";
    if (event.key === "Enter" || event.key === " ") {
      setCollapsed(!isCollapsed());
    } else if (event.key === grow || event.key === shrink) {
      if (isCollapsed()) setCollapsed(false);
      else applyWidth(applied + (event.key === grow ? 1 : -1) * (event.shiftKey ? 48 : 16));
      writeStored(`${key}-width`, Math.round(applied));
    } else {
      return;
    }
    event.preventDefault();
  });
  const saved = Number(readStored(`${key}-width`));
  applyWidth(Number.isFinite(saved) && saved > 0 ? saved : initial);
  setCollapsed(readStored(`${key}-collapsed`) === "1", { persist: false });
  // A window that shrank can leave a remembered width wider than there is room for.
  window.addEventListener("resize", () => applyWidth(applied));
  return { setCollapsed, isCollapsed };
}

let mapPanelGrip = null;

function initPanels() {
  const facets = document.getElementById("facets");
  const mapPanel = document.getElementById("map-panel");
  const sources = document.getElementById("col-sources");
  makePanelGrip({
    panel: facets, handle: document.getElementById("facets-grip"), side: "right",
    cssVar: "--facets-w", railVar: "--facets-rail", min: 180, max: 360, collapseAt: 110, railPx: 0, initial: 208,
    key: "penumbra-facets", others: () => [mapPanel],
  });
  mapPanelGrip = makePanelGrip({
    panel: mapPanel, handle: document.getElementById("map-panel-grip"), side: "left",
    cssVar: "--map-panel-w", railVar: "--map-panel-rail", min: 280, max: 640, collapseAt: 200, railPx: 46, initial: 320,
    key: "penumbra-map-panel", others: () => [facets],
  });
  document.getElementById("map-panel-open").addEventListener("click", () => mapPanelGrip.setCollapsed(false));
  const graphSide = document.getElementById("graph-side");
  const graphGrip = makePanelGrip({
    panel: graphSide, handle: document.getElementById("graph-panel-grip"), side: "left",
    cssVar: "--graph-panel-w", railVar: "--graph-panel-rail", min: 280, max: 640, collapseAt: 200, railPx: 46,
    initial: 340, key: "penumbra-graph-panel",
  });
  document.getElementById("graph-panel-open").addEventListener("click", () => graphGrip.setCollapsed(false));
  makePanelGrip({
    panel: sources, handle: document.getElementById("sources-grip"), side: "right",
    cssVar: "--sources-w", railVar: "--sources-rail", min: 220, max: 480, collapseAt: 150, railPx: 0, initial: 280,
    key: "penumbra-sources", others: () => [document.getElementById("col-studio")],
  });
}

function initStudioRail() {
  const col = document.getElementById("col-studio");
  const tabs = [...document.querySelectorAll(".studio-view-tab")];
  const bodies = [...document.querySelectorAll("[data-view-body]")];

  function show(view) {
    //: **`role="tablist"` is a PROMISE, and it was keeping none of it.** The four tabs declared
    //: `role="tab"` and `aria-selected` was `null` on all of them, so every tab reported NOT
    //: selected and which panel was showing was conveyed by an underline alone — there was not one
    //: `aria-selected` anywhere in the product. SC 4.1.2 Name, Role, VALUE, on the control the whole
    //: right column depends on. The same class round twelve fixed for the citation span, one
    //: element short.
    //:
    //: `tabindex` moves with the selection (roving), which is the other half a tablist owes: a tab
    //: strip is ONE tab stop and the arrow keys move within it — see the `keydown` handler below.
    tabs.forEach((tab) => {
      const on = tab.dataset.view === view;
      tab.classList.toggle("is-active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    });
    bodies.forEach((viewBody) => {
      viewBody.hidden = viewBody.dataset.viewBody !== view;
    });
    localStorage.setItem(STUDIO_VIEW_KEY, view);
    // Expanding on selection: picking a view while collapsed can only mean "show me that".
    setCollapsed(false);
    if (view === "references") renderReferenceView();
  }

  //: Arrow-key roving, which a `role="tablist"` owes and this file had nowhere: the only
  //: `ArrowLeft`/`ArrowRight` handler in it was the splitter's. Home/End too, because a four-tab
  //: strip is exactly where "jump to the last one" is cheapest to offer.
  tabs.forEach((tab) =>
    tab.addEventListener("keydown", (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1, Home: -tabs.length, End: tabs.length }[event.key];
      if (step === undefined) return;
      event.preventDefault();
      const at = tabs.indexOf(tab);
      const next = tabs[Math.min(tabs.length - 1, Math.max(0, at + step))];
      show(next.dataset.view);
      next.focus();
    })
  );

  // No separate collapse BUTTON any more: the grip resizes and collapses, and a second control for
  // the same thing was eating the width the four labels needed — they were truncating to one
  // character each.
  //: **Collapsed is a SIDE-COLUMN state, so it applies only where the Studio is one** (above
  //: 1024px — the stylesheet makes it a full-width row below that). A collapse remembered from a
  //: wide window used to follow the reader into a narrow one: the collapse grid took over the
  //: layout, squeezed the panel switch into a 280px column and left the Studio a strip of icons.
  //: The WISH is kept and re-applied when the window is wide again; only the class follows width.
  const sideColumn = window.matchMedia("(min-width: 1025px)");
  let collapsedWanted = col.classList.contains("is-collapsed");
  const applyCollapsed = () => col.classList.toggle("is-collapsed", collapsedWanted && sideColumn.matches);
  sideColumn.addEventListener("change", applyCollapsed);

  function setCollapsed(value) {
    // Only on an actual CHANGE: `pointermove` calls this on every event, and an unconditional
    // synchronous `localStorage` write there is 60-120 writes a second during a drag.
    if (collapsedWanted === value) return;
    collapsedWanted = value;
    applyCollapsed();
    localStorage.setItem(STUDIO_COLLAPSED_KEY, value ? "1" : "");
  }

  // APPLYING a width and REMEMBERING one are deliberately separate. Persisting on every pointermove
  // is what made dragging the panel away overwrite the user's own width with the 240px clamp; the
  // previous fix for that (skip `setWidth` below the minimum) then left the CSS variable holding a
  // stale width, so re-opening snapped to the OLD size before catching up to the pointer — the
  // "彈回前一次設置的寬度再快速閃現" half of the report. A drag now always follows the pointer and
  // only commits when it ends.
  let appliedWidth = STUDIO_MIN_WIDTH;

  function applyWidth(px) {
    appliedWidth = Math.min(STUDIO_MAX_WIDTH, Math.max(STUDIO_MIN_WIDTH, px));
    document.documentElement.style.setProperty("--studio-width", `${appliedWidth}px`);
    //: **`aria-valuenow` was the literal `50` in the markup and never moved.** The splitter is well
    //: built — arrows step it, Enter collapses it, `setPointerCapture` keeps a fast drag alive —
    //: and an AT user pressing those arrows was told nothing had happened, because the one attribute
    //: that reports a separator's position was a constant. Reported as a PERCENTAGE of its own
    //: range, which is what `aria-valuemin="0"`/`aria-valuemax="100"` in the markup already promise.
    const handleEl = document.getElementById("studio-resize");
    if (handleEl) {
      const span = STUDIO_MAX_WIDTH - STUDIO_MIN_WIDTH;
      const pct = span ? Math.round(((appliedWidth - STUDIO_MIN_WIDTH) / span) * 100) : 0;
      handleEl.setAttribute("aria-valuenow", String(pct));
    }
    return appliedWidth;
  }

  function rememberWidth() {
    localStorage.setItem(STUDIO_WIDTH_KEY, String(appliedWidth));
  }

  // Drag the edge to size the panel; drag it past the threshold to put it away. `setPointerCapture`
  // is what keeps the drag alive when the cursor outruns the 6px handle, which it always does.
  const handle = document.getElementById("studio-resize");
  let dragging = false;
  handle.addEventListener("pointerdown", (event) => {
    dragging = true;
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add("is-resizing");  // suppress the width transition and text selection
    event.preventDefault();
  });
  handle.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    // The panel is on the RIGHT, so its width grows as the pointer moves left.
    const width = window.innerWidth - event.clientX;
    const collapsed = col.classList.contains("is-collapsed");
    if (width < (collapsed ? STUDIO_EXPAND_AT : STUDIO_COLLAPSE_AT)) {
      setCollapsed(true);
      // The panel cannot open below its minimum, but the HANDLE can still follow you: the rail
      // stretches under the pointer through the dead band, so pulling always does something
      // visible. Without it the ordering above costs ~194px of motionless drag before the panel
      // opens, which is the "卡住" this replaced.
      const rail = Math.min(STUDIO_MIN_WIDTH, Math.max(STUDIO_RAIL_WIDTH, width));
      document.documentElement.style.setProperty("--studio-rail", `${rail}px`);
      return;
    }
    setCollapsed(false);
    document.documentElement.style.removeProperty("--studio-rail");
    applyWidth(width);
  });
  const endDrag = (event) => {
    if (!dragging) return;
    dragging = false;
    try {
      handle.releasePointerCapture(event.pointerId);
    } catch {
      // the pointer was already gone; nothing to release
    }
    document.body.classList.remove("is-resizing");
    // The stretch is a drag affordance, never a persisted size.
    document.documentElement.style.removeProperty("--studio-rail");
    // Only a drag that ended OPEN was the user choosing a width. One that ended collapsed passed
    // through the clamp on its way out, and committing that would lose the size they had picked.
    if (!col.classList.contains("is-collapsed")) rememberWidth();
  };
  handle.addEventListener("pointerup", endDrag);
  handle.addEventListener("pointercancel", endDrag);
  // Double-click the grip toggles, the shortcut every resizable panel has.
  handle.addEventListener("dblclick", () => setCollapsed(!col.classList.contains("is-collapsed")));
  // Keyboard: the handle is focusable, so it has to be operable without a pointer.
  handle.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      // Ignored while collapsed: the collapsed track reads `--studio-rail`, not `--studio-width`,
      // so this used to walk the REMEMBERED width down to the 240 clamp with nothing moving on
      // screen — and re-opening then landed at 240 instead of the size the user had chosen.
      // `endDrag` already has the equivalent guard.
      if (col.classList.contains("is-collapsed")) return;
      // No drag to end, so a key press commits immediately.
      applyWidth(appliedWidth + (event.key === "ArrowLeft" ? 24 : -24));
      rememberWidth();
    } else if (event.key === "Enter" || event.key === " ") {
      setCollapsed(!col.classList.contains("is-collapsed"));
    } else return;
    event.preventDefault();
  });

  tabs.forEach((tab) => tab.addEventListener("click", () => show(tab.dataset.view)));

  applyWidth(parseInt(localStorage.getItem(STUDIO_WIDTH_KEY) || "340", 10));
  const stored = localStorage.getItem(STUDIO_VIEW_KEY);
  show(tabs.some((tab) => tab.dataset.view === stored) ? stored : "studio");
  // AFTER `show`, which expands on purpose — restoring a collapsed panel must win over that.
  setCollapsed(localStorage.getItem(STUDIO_COLLAPSED_KEY) === "1");

  // A reference is only interesting while it exists; both of these change what there is to show.
  store.on("chat:turnAdded", () => renderReferenceView());
  store.on("sources:changed", () => renderReferenceView());
  window.addEventListener("ui-lang-changed", () => renderReferenceView());
}

function showStudioView(view) {
  //: In a narrow window the Studio is a separate panel, so a citation that opens References has to take
  //: the reader there — otherwise the click lights up a list on a screen nobody can see.
  setPanel("studio");
  const tab = document.querySelector(`.studio-view-tab[data-view="${view}"]`);
  if (tab) tab.click();
}

// Every passage cited ANYWHERE in this orbit, deduplicated and numbered — the thing a reader
// wants when they are checking work rather than reading it. Collected from the turns and the
// overview, which is everything the client holds that carries citations.
function collectReferences() {
  const byCoordinate = new Map();
  const add = (citation) => {
    const key = referenceKey(citation);
    const existing = byCoordinate.get(key);
    if (!existing) {
      byCoordinate.set(key, { ...citation, quotes: citation.quote ? [citation.quote] : [], uses: 1 });
      return;
    }
    existing.uses += 1;
    if (citation.quote && !existing.quotes.includes(citation.quote)) existing.quotes.push(citation.quote);
    existing.verified = existing.verified && citation.verified;
  };
  //: **In READING order, which is not the order the model emitted them.** The numbering the
  //: interface owns (invariant 48.5 exists so there is exactly one scheme) was assigned in array
  //: order, so a model that cited a source out of the order it wrote about it produced marks
  //: running 1, 3, 4, 6, 5 down a single answer — measured on a seeded orbit. `answer_span` is
  //: the model pointing at its own prose (invariant 49), which is precisely the coordinate needed
  //: to sort by where the reader will MEET each mark. A citation with no span keeps its array
  //: position, which is the honest fallback: nothing locates it.
  //: **A span-less citation keeps its slot; the rest are sorted INTO the slots they already
  //: occupy.** The first version of this compared `a.seen < 0 || b.seen < 0 ? a.at - b.at : …`,
  //: which is not a consistent ordering: one span-less citation dragged its neighbours back into
  //: emission order, so `[s3(Gamma), sX(none), s1(Alpha)]` came out `s3, sX, s1` and the reader met
  //: `[3] … [1]` — the same defect this function was written to fix, reintroduced in the case the
  //: product's own prompt asks for (`instructions.py` tells the model to leave `answer_span` out
  //: when it cannot point precisely, and `citations.locate_answer_spans` nulls any span it cannot
  //: find verbatim, so a MIXED array is the designed common case, not an edge one).
  //:
  //: Permuting only the locatable ones among the positions they already hold is consistent by
  //: construction, and it makes true the thing the old comment claimed: a citation with no span
  //: does not move at all.
  const inReadingOrder = (citations, prose) => {
    const all = [...(citations || [])];
    const slots = [];
    const locatable = [];
    all.forEach((citation, at) => {
      const seen = citation.answer_span ? (prose || "").indexOf(citation.answer_span) : -1;
      if (seen < 0) return;
      slots.push(at);
      locatable.push({ citation, seen, at });
    });
    locatable.sort((a, b) => (a.seen === b.seen ? a.at - b.at : a.seen - b.seen));
    slots.forEach((slot, i) => {
      all[slot] = locatable[i].citation;
    });
    return all;
  };

  inReadingOrder(state.overview?.citations, state.overview?.text).forEach(add);
  (state.turns || []).forEach((turn) =>
    inReadingOrder(turn.citations, turn.answer || turn.text).forEach(add)
  );
  // Every OTHER surface that renders a clickable citation has to be here too, or clicking one
  // opens a list that cannot contain it — see `state.guides`.
  //: Every one of these renders the SAME numbered stroke through `renderAnswerWithCitations`, so
  //: each needs the same reading-order pass against its OWN prose — the chat answer was simply
  //: where the out-of-order marks were first measured. Leaving the other five in emission order
  //: made a Timeline read `[3] … [1] … [2]` while the overview above it read `[1] [2] [3]`, and
  //: the Copy/Download artifact (which renumbers from this same list) carried that out of the
  //: product as a file.
  (state.podcast?.utterances || []).forEach((u) =>
    inReadingOrder(u.citations, u.text).forEach(add)
  );
  Object.values(state.guides || {}).forEach(({ result }) => {
    if (!result) return;
    inReadingOrder(result.citations, result.text).forEach(add);              // summary / insight
    (result.items || []).forEach((item) =>
      inReadingOrder(item.citations, item.answer).forEach(add)              // faq
    );
    (result.events || []).forEach((event) =>
      inReadingOrder(event.citations, event.description).forEach(add)       // timeline
    );
  });
  return [...byCoordinate.values()];
}

// The References view is built from a snapshot of `state`, so anything that ADDS a citation has to
// ask for a rebuild. Cheap and idempotent; a no-op when the reader is looking at another view.
// Re-stamp every stroke ON THE PAGE from the current orbit-wide order. `collectReferences`
// orders overview -> turns -> podcast -> guides, so adding one chat turn shifts the number of every
// podcast and guide coordinate — and those panels do not re-render. An independent review measured
// a podcast stroke still saying 1 while the panel called that coordinate 2.
//
// Re-stamping rather than re-rendering, deliberately: re-rendering the podcast rebuilds its
// `<audio>` and would interrupt playback, and it is the NUMBER that went stale, nothing else.
//:
//: **The VERDICT is re-stamped too, not only the number.** Removing a source re-verifies every
//: saved citation server-side (invariants 5 and 11), and the page re-rendered only the overview:
//: chat turns and the podcast transcript kept showing citations to the removed source as verified
//: until a reload, while the References panel beside them said unverified. Verification is a
//: property of the COORDINATE against the current corpus, and `referenceKey` is exactly that
//: coordinate, so every use of a key shares one verdict and `collectReferences` already ANDs them.
function renumberStrokes() {
  const refs = new Map(collectReferences().map((ref, i) => [referenceKey(ref), { ref, n: i + 1 }]));
  document.querySelectorAll(".citation[data-ref-key]").forEach((span) => {
    const hit = refs.get(span.dataset.refKey);
    //: The NUMBER only on a stroke's last fragment (`data-stroke-end`, set by the renderer). This
    //: stamped every fragment, so a claim crossing `*emphasis*` read "¹a ¹parametric¹ model" after
    //: any guide or answer triggered a re-stamp — measured by an independent review.
    // No attribute rather than "0": `content: attr(data-reference)` renders a literal 0, which is
    // the opposite of the "no number at all" the fallback claims.
    if (hit && "strokeEnd" in span.dataset) span.dataset.reference = String(hit.n);
    else delete span.dataset.reference;
    if (!hit) return;
    span.classList.toggle("is-unverified", !hit.ref.verified);
    span.title = citationHoverLabel(hit.ref);
  });
}

function refreshReferenceView() {
  const host = document.getElementById("reference-view");
  if (host && !host.closest("[data-view-body]")?.hidden) renderReferenceView();
  // Every OTHER surface's strokes are numbered from the same order, and none of them re-renders.
  renumberStrokes();
}

//: The coordinate key, and the SEPARATOR is load-bearing. It used to be U+0000, which meant every
//: `[data-ref-key="…"]` selector built from it matched NOTHING: `CSS.escape` maps U+0000 to U+FFFD
//: by spec, and so does the CSS tokenizer when it parses a selector, so there is no spelling of that
//: selector that could ever match. The reciprocal highlight was dead on arrival and `focusReference`
//: had never once focused a card — found by an independent review measuring it in a real browser
//: rather than by reading. U+001F round-trips through `CSS.escape` and is just as impossible inside
//: a source id or a locator.
const REFERENCE_KEY_SEP = "\u001f";

function referenceKey(citation) {
  return `${citation.source_id}${REFERENCE_KEY_SEP}${citation.locator}`;
}

//: A source's HOST or kind, the small grey chip Kagi and Google both put beside a reference title
//: so a row's provenance reads at a glance without opening anything.
function referenceOrigin(source) {
  if (!source) return "";
  if (source.kind === "web" || source.kind === "youtube") {
    try {
      return new URL(source.origin).hostname.replace(/^www\./, "");
    } catch {
      return kindLabel(source.kind);
    }
  }
  return kindLabel(source.kind);
}

// Reciprocal highlight: pointing at a reference lights up the strokes it backs, and pointing at a
// stroke lights up its reference. The thing the user pointed at in Kagi's assistant — without it a
// numbered stroke and a numbered row are two lists the reader has to join up by eye.
function linkReference(key, on) {
  document
    .querySelectorAll(`.citation[data-ref-key="${CSS.escape(key)}"], .ref-card[data-ref-key="${CSS.escape(key)}"]`)
    .forEach((el) => el.classList.toggle("is-linked", on));
}

function renderReferenceView() {
  const host = document.getElementById("reference-view");
  const empty = document.getElementById("references-empty");
  if (!host) return;
  const references = collectReferences();
  host.textContent = "";
  empty.hidden = references.length > 0;

  references.forEach((reference, index) => {
    const source = (state.sources || []).find((s) => s.id === reference.source_id);
    const item = document.createElement("div");
    item.className = reference.verified ? "ref-card" : "ref-card is-unverified";
    item.dataset.refKey = referenceKey(reference);
    item.addEventListener("mouseenter", () => linkReference(item.dataset.refKey, true));
    item.addEventListener("mouseleave", () => linkReference(item.dataset.refKey, false));

    const head = document.createElement("button");
    head.type = "button";
    head.className = "ref-card-head";

    const number = document.createElement("span");
    number.className = "reference-number";
    number.textContent = String(index + 1);
    head.appendChild(number);

    // Title on the first line, provenance on the second — one ROW, not a card full of quotes. The
    // previous version rendered every quote as a full blockquote, always open, so a source cited
    // eight times filled the whole column and the list stopped being scannable at all.
    const main = document.createElement("span");
    main.className = "ref-card-main";

    const name = document.createElement("span");
    name.className = "ref-card-name";
    name.textContent = source ? sourceLabel(source) : reference.source_id;
    main.appendChild(name);

    const meta = document.createElement("span");
    meta.className = "ref-card-meta";
    const origin = referenceOrigin(source);
    if (origin) {
      const chip = document.createElement("span");
      chip.className = "ref-card-chip";
      chip.textContent = origin;
      meta.appendChild(chip);
    }
    if (reference.locator && reference.locator !== "whole") {
      const locator = document.createElement("span");
      locator.className = "reference-locator";
      locator.textContent = reference.locator;
      meta.appendChild(locator);
    }
    // NOTE the locator above is model output and can be arbitrarily long. A run was observed
    // writing a whole section heading into it, which stretched this flex row until the rest of the
    // meta line was pushed out of the card — the "broken render" half of the same report the
    // pre-SUBMIT coordinate check now prevents at the source. `.reference-locator` clamps it, so a
    // future bad value is ugly in one chip instead of destroying the row.
    const uses = document.createElement("span");
    uses.className = "ref-card-uses";
    uses.textContent = t("references.uses", `${reference.uses}\u00d7`, { n: reference.uses });
    meta.appendChild(uses);
    if (!reference.verified) {
      const badge = document.createElement("span");
      badge.className = "ref-card-unverified";
      badge.textContent = t("cite.unverifiedShort", "unverified");
      meta.appendChild(badge);
    }
    main.appendChild(meta);
    head.appendChild(main);

    const caret = document.createElement("span");
    caret.className = "ref-card-caret";
    caret.textContent = "\u203a";
    head.appendChild(caret);
    item.appendChild(head);

    // One clamped line of the passage, so a row says what it is without being opened. Kagi's
    // popover and Google's card both lead with a snippet for the same reason.
    if (reference.quotes.length) {
      const snippet = document.createElement("div");
      snippet.className = "ref-card-snippet";
      snippet.textContent = reference.quotes[0];
      item.appendChild(snippet);
    }

    const cardBody = document.createElement("div");
    cardBody.className = "ref-card-body";
    cardBody.hidden = true;

    // Opening the row reveals every passage cited from this coordinate, then the original text with
    // the relevant one highlighted — the whole loop, still inside this view rather than over the
    // page. `wanted` is the quote the reader actually clicked, when they arrived by clicking a
    // stroke: a source cited eight times has eight quotes here, and landing on the card without
    // being told WHICH one was meant is the "還是得自己點開並慢慢追" a user reported.
    const openCard = async (wanted) => {
      item.classList.add("is-open");
      cardBody.hidden = false;
      const target = reference.quotes.includes(wanted) ? wanted : reference.quotes[0] || null;
      if (cardBody.dataset.loaded) {
        markWantedQuote(cardBody, target);
        return;
      }
      cardBody.textContent = "";
      // An unverified reference explains ITSELF, here, in the one place a reader who wants to know
      // is already looking. The badge in the row above says only "unverified", which a user
      // reasonably asked the meaning of — and the answer matters, because it is narrow: the
      // COORDINATE could not be found (invariant 5 verifies coordinates, never faithfulness), so
      // the quote below may still be a perfectly good quote that was filed under the wrong address.
      if (!reference.verified) {
        const why = document.createElement("p");
        why.className = "ref-card-why";
        why.textContent = t(
          "cite.unverifiedWhy",
          "This citation points at a place that does not exist in this source, so it could not be checked. The passage below may still be accurate: what failed is the address, not necessarily the claim.",
        );
        cardBody.appendChild(why);
        if (reference.reason) {
          const detail = document.createElement("p");
          detail.className = "ref-card-why-detail";
          detail.textContent = readableReason(reference.reason, source ? sourceLabel(source) : "");
          cardBody.appendChild(detail);
        }
      }
      reference.quotes.forEach((quote) => {
        const blockquote = document.createElement("blockquote");
        blockquote.className = "reference-quote";
        blockquote.dataset.quote = quote;
        blockquote.textContent = quote;
        cardBody.appendChild(blockquote);
      });
      const passage = document.createElement("div");
      passage.className = "ref-card-passage";
      passage.textContent = t("cite.loading", "Loading\u2026");
      cardBody.appendChild(passage);
      markWantedQuote(cardBody, target);
      try {
        const data = await api(
          `/orbits/${encodeURIComponent(state.orbitId)}/sources/${encodeURIComponent(reference.source_id)}`
        );
        passage.textContent = "";
        passage.appendChild(renderSourceMeta(data));
        const blocks = (data.blocks || []).filter((block) => block.locator === reference.locator);
        // An unverified coordinate matches NO block, so filtering by it would render the source
        // meta and then nothing at all — the reader gets an empty box for the citation they most
        // wanted to inspect. Fall back to the whole source and let the quote highlight find itself.
        (blocks.length ? blocks : data.blocks || []).forEach((block) => {
          passage.appendChild(renderTextWithOptionalHighlight(block.text, target));
        });
        //: Bring the cited words into view INSIDE the passage, which scrolls on its own (24rem):
        //: a quote deep in a long page sat below its fold...
        const hit = passage.querySelector(".source-quote");
        if (hit) {
          const offset = hit.getBoundingClientRect().top - passage.getBoundingClientRect().top;
          passage.scrollTop += offset - passage.clientHeight / 3;
          //: ...and then the COLUMN, to the words themselves. `focusReference` scrolled the card
          //: while it was still a collapsed head; loading the passage grows it, so a card low in
          //: the list — the newest answer's, the commonest case — left the marked words below the
          //: window at 1280×800. `nearest` moves the column only as far as the words need.
          hit.scrollIntoView({ block: "nearest" });
        }
        cardBody.dataset.loaded = "1";
      } catch (err) {
        passage.textContent = t("err.generic", `${readableError(err.message)}`, { message: readableError(err.message) });
      }
    };
    item._openCard = openCard;

    head.addEventListener("click", () => {
      if (!cardBody.hidden) {
        cardBody.hidden = true;
        item.classList.remove("is-open");
        return;
      }
      openCard(null);
    });

    item.appendChild(cardBody);
    host.appendChild(item);
  });
}

// Clicking a citation in the chat opens the References view and takes the reader to that entry,
// rather than expanding a panel inside the answer they are reading.
// Which of a card's quotes the reader asked about. A card is re-openable and already-loaded, so
// this is a separate re-stampable step rather than something decided while building the list.
function markWantedQuote(cardBody, quote) {
  cardBody.querySelectorAll(".reference-quote").forEach((el) => {
    el.classList.toggle("is-wanted", quote != null && el.dataset.quote === quote);
  });
}

function focusReference(citation) {
  showStudioView("references");
  const key = referenceKey(citation);
  const card = document.querySelector(`.ref-card[data-ref-key="${CSS.escape(key)}"]`);
  if (!card) return;
  // OPEN it, rather than only scrolling to it. Arriving at a collapsed row still left the reader
  // to click it and then work out which of its quotes was theirs.
  if (card._openCard) card._openCard(citation.quote || null);
  document.querySelectorAll(".ref-card.is-focused, .citation.is-focused")
    .forEach((el) => el.classList.remove("is-focused"));
  card.classList.add("is-focused");
  // ...and every stroke pointing at the SAME coordinate lights up with it. `.citation.is-focused`
  // has always existed in the stylesheet promising exactly this; nothing ever set it.
  document.querySelectorAll(`.citation[data-ref-key="${CSS.escape(key)}"]`)
    .forEach((el) => el.classList.add("is-focused"));
  card.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// --- Boot -------------------------------------------------------------------------------------

// Static markup FIRST, before any panel renders: every `init*` below writes copy of its own, and a
// panel that rendered against the English strings would keep them until something re-rendered it.
document.documentElement.lang = uiLang();
applyStaticI18n();

// A language change re-applies the static markup (in `setUiLang`) and re-renders every panel that
// holds generated copy. Cheaper and far less error-prone than threading a language argument through
// each renderer — and it means a renderer added later is translated by construction rather than by
// somebody remembering to subscribe.
window.addEventListener("ui-lang-changed", () => {
  renderChatOverview();
  //: `relabel`: the SOURCES did not change, only the words around them. Without the flag the Studio
  //: took this for a corpus change and discarded every generated guide.
  store.emit("sources:changed", { sources: state.sources, relabel: true });
  store.emit("notes:changed", { notes: state.notes });
  //: **AND TIER 0, which this listener had never covered.** `data-i18n` attributes are re-applied
  //: by `i18n.js` itself, so the static half of the Horizon followed the switch and the RENDERED half
  //: did not: eight seconds after switching to English the stream still read `4 則還沒摘要`,
  //: `摘要其中 4 則` (the button that spends money), `今天`, `讀不到` and `約 4 萬字`, with
  //: `documentElement.lang` already `en`. Everything a node row draws goes through `t()` at render
  //: time, so the fix is to render again - the orbit column has done exactly this since it was
  //: built, three lines up.
  //:
  //: `reset: false`: a language switch is not a reason to throw away the reader's scroll position
  //: or the pages they have already asked for.
  if (document.getElementById("view-horizon") && !document.getElementById("view-horizon").hidden) {
    refreshHorizon({ reset: false });
  }
  renderFacets();
  //: The browser tab, and the Tauri window title after it, follow the interface language too. It
  //: was the one thing this listener rebuilt nothing for: the rail read "Horizon" under
  //: `lang="en"` while the tab still said 收納袋.
  syncDocumentTitle(document.body.dataset.view === "orbit" ? state.orbitId || "" : "");
  const settingsOverlay = document.getElementById("settings-overlay");
  if (settingsOverlay && !settingsOverlay.hidden) {
    //: RELOAD, not re-open, and carry the reader's unsaved values across it. Clicking the open
    //: button re-ran `openModal` on an already-open dialog and dropped focus on the floor.
    settingsDraft = collectSettingsDraft();
    loadSettings().then(() => {
      const picker = document.getElementById("setting-ui-language");
      if (picker) picker.focus({ preventScroll: true });
    });
  }
});

initTheme();
initSettings();
initOrbitTitle();
initOrbitSwitch();
initSourcesPanel();
initChatPanel();
initStudioPanel();
initPodcastPlayer();
initSourceViewer();
initNotesPanel();
initStudioRail();

// --- Trajectory drawer ---------------------------------------------------------------------------
//
// A bottom sheet that replays one RLM run: a sibling project's own shape, brought here
// because the inline step log put the planner's own reasoning PROSE inside the chat bubble, where a
// user reported it as unreadable and space-consuming ("文鄒鄒的看不懂"). Reasoning belongs somewhere
// a reader opts into, not in the middle of the answer they came for.
//
// TWO views on the run's two clocks (`trajectory.py` explains why they are different): the left nav
// walks the planner's REPL turns, the top strip is the tool timeline where segment width is
// proportional to real elapsed time — so a slow call is visibly wide rather than a number to
// compare. Works on a RUNNING trace as well as a finished one, which is the point for a `long`
// podcast that takes minutes.

const TRAJ_SPEEDS = [1, 2, 4, 8, 16, 32, 64];
const TRAJ_DWELL_FLOOR_MS = 50;    // a stop never dwells less than this, so a tiny turn still shows
const TRAJ_NOMINAL_MS = 1500;      // a stop with no live timing gets a brief nominal length

let trajData = null;      // the fetched decomposition
let trajRunIds = [];      // every run id this drawer was opened for (an overview fires two)
let trajSel = null;       // {kind: "init"|"turn"|"tool", index}
let trajSpeed = 2;
let trajPlayTimer = null;
let trajPoll = null;      // while the run is live, re-fetch so the drawer keeps up
let trajMatches = [];
let trajMatchCur = -1;
let trajCloseTimer = null;

const trajEl = {};

function trajInit() {
  [
    "backdrop", "drawer", "name", "stat", "run", "note", "budget", "timeline", "axis-end", "search",
    "search-count", "prev", "play", "next", "speed", "steps", "detail", "expand", "close",
    "progress",
  ].forEach((name) => {
    trajEl[name.replace(/-(\w)/g, (_, c) => c.toUpperCase())] = document.getElementById(`traj-${name}`);
  });
  if (!trajEl.drawer) return;
  trajEl.close.addEventListener("click", closeTrajectory);
  trajEl.backdrop.addEventListener("click", closeTrajectory);
  trajEl.expand.addEventListener("click", () => {
    const full = trajEl.drawer.classList.toggle("is-full");
    trajEl.expand.textContent = full ? "⤡" : "⤢";
  });
  trajEl.prev.addEventListener("click", () => trajStep(-1));
  trajEl.next.addEventListener("click", () => trajStep(1));
  trajEl.play.addEventListener("click", trajTogglePlay);
  trajEl.speed.addEventListener("click", () => {
    trajSpeed = TRAJ_SPEEDS[(TRAJ_SPEEDS.indexOf(trajSpeed) + 1) % TRAJ_SPEEDS.length];
    trajEl.speed.textContent = `${trajSpeed}×`;
  });
  trajEl.run.addEventListener("change", () => openTrajectory(trajRunIds, trajEl.run.value));
  trajEl.search.addEventListener("input", () => trajSearch(trajEl.search.value));
  trajEl.search.addEventListener("keydown", (event) => {
    // A text input, so the same composition guard as every other one: Enter commits an IME
    // candidate, and jumping to the next match instead loses the word being typed.
    if (event.key === "Enter" && !event.isComposing && event.keyCode !== 229) trajCycleMatch();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !trajEl.drawer.hidden) closeTrajectory();
  });
}

//: Returns whether a trajectory was actually opened, so a control that offered it can retire
//: itself when there was none (see `renderTickerAffordance`). `false` is not an error: a trace is
//: only as durable as retention keeps it, and a run that failed before its first REPL turn never
//: had one.
//: Whose runs these are. A Horizon ask runs under its own handle (no orbit may take that prefix,
//: the server refuses it), so its trajectory is read from there even while no orbit is open.
function trajOwner(runId) {
  return runId && runId.startsWith(`${HORIZON_ASK_KEY}-`) ? HORIZON_ASK_KEY : state.orbitId;
}

async function openTrajectory(runIds, wanted) {
  const owner = trajOwner(wanted || (runIds || []).find(Boolean));
  if (!trajEl.drawer || !owner) return false;
  //: **THE TRIGGER IS RECORDED HERE, before the fetch below.** `trajTakeFocus` reads
  //: `document.activeElement` when the drawer opens — which is after an `await`, by which time the
  //: Steps pill that was pressed has been replaced by a chat re-render, so what got recorded was
  //: `<body>`. On the way IN is the only moment the real control is still there.
  trajOpenedFrom = document.activeElement;
  trajRunIds = (runIds || []).filter(Boolean);
  const runId = wanted || trajRunIds[0];
  if (!runId) return false;
  try {
    trajData = await api(
      `/orbits/${encodeURIComponent(owner)}/runs/${encodeURIComponent(runId)}/trajectory`
    );
  } catch (err) {
    // A trace is only as durable as retention keeps it (invariant 34). Losing one must degrade
    // THIS affordance, never the page.
    //
    // TWO situations, and they want opposite things. Opening the drawer from a steps pill on a run
    // with no trace should NOT open it at all: a transport, a search box and an empty timeline
    // wrapped around one sentence reads as a broken drawer rather than a missing trace, and the
    // reader asked for a trajectory that does not exist. The page is left alone and the pill
    // corrects itself — see the branch below, which also says why this is no longer the `alert`
    // that rename/save-settings/add-source use. (This paragraph went on recommending that `alert`
    // for a while after the code below stopped doing it, directly above the comment reversing it.)
    // But SWITCHING runs inside an already-open drawer cannot close it under the
    // reader, so that one clears every pane instead; leaving them would show the previous run's
    // task, notes and timeline beside a "no trajectory" line, reading as facts about this one.
    trajData = null;
    const message = t("traj.missing", `No trajectory for this run (${readableError(err.message)})`, {
      message: readableError(err.message),
    });
    if (trajEl.drawer.hidden) {
      // No dialog. The caller is told, and the control that asked corrects ITSELF - see
      // `renderTickerAffordance`. Opening a drawer with a transport, a search box and an empty
      // timeline around one sentence reads as a broken drawer rather than a missing trace, so the
      // drawer still stays shut; what changed is that the reader is no longer interrupted by a
      // modal carrying a run UUID they have no use for.
      return false;
    }
    trajEl.stat.textContent = message;
    trajEl.steps.textContent = "";
    trajEl.detail.textContent = "";
    trajEl.timeline.textContent = "";
    trajEl.name.textContent = "";
    trajEl.axisEnd.textContent = "";
    trajEl.note.textContent = "";
    trajEl.note.hidden = true;
    if (trajEl.budget) {
      trajEl.budget.textContent = "";
      trajEl.budget.hidden = true;
    }
  }
  // A drawer left open on a run with no trajectory does not need 80vh for one line.
  trajEl.drawer.classList.toggle("is-empty", !trajData);
  //: **RENDER FIRST, THEN TAKE FOCUS.** `trajShowDrawer` focuses the drawer's first focusable —
  //: which is `#traj-run` — and `renderTrajectory` then does `trajEl.run.hidden = runIds.length < 2`.
  //: Every persisted "Steps" pill opens with ONE run id, so the picker was always hidden a moment
  //: after being focused, and hiding a focused element blurs it to `<body>`. Measured on the real
  //: path: two Tab presses to reach anything, with `aria-modal="true"` hiding the page behind from
  //: a screen reader's virtual cursor the whole time — worse than an honest non-modal, which is the
  //: argument `trajTakeFocus`'s own comment makes. It stayed invisible because the drawer opened
  //: correctly from `trajShowDrawer()` alone, which is the path every test and probe used.
  if (trajData) renderTrajectory(runId);
  trajShowDrawer();
  return Boolean(trajData);
}

//: **`aria-modal="true"` is a PROMISE, and this drawer was not keeping any of it.** It took no
//: focus, marked nothing `inert`, and six consecutive Tabs walked the page behind the full-screen
//: overlay — the wordmark, the orbit picker, Settings, the theme toggle, the URL field, Add
//: source, and the destructive ✕ that removes a source. Escape closed it but could not return
//: focus to the trigger, because focus was never taken. And `aria-modal` makes it worse than an
//: honest non-modal: it hides the page behind from a screen reader's virtual cursor while leaving
//: every control on it reachable by Tab.
//:
//: The `.modal` family beside it does all three correctly and already knows about this drawer —
//: `inertEverythingExcept` marks `.traj-drawer` inert when the source viewer opens. The machinery
//: existed; it just never ran for the one surface invariant 70 calls "where a run's reasoning
//: lives".
//:
//: Its OWN pair of slots rather than `modalReturnFocus`/`modalInerted`: those are single-valued,
//: and a source viewer opened from inside this drawer would overwrite them and un-inert the page
//: on the way out.
let trajReturnFocus = null;
let trajInerted = [];
//: Set by `openTrajectory` BEFORE it awaits anything; `trajTakeFocus` prefers it over whatever
//: happens to be focused by the time the drawer actually appears, which is after the fetch.
let trajOpenedFrom = null;

function trajTakeFocus() {
  if (trajInerted.length) return; // already held; a re-render must not re-record the trigger
  trajReturnFocus = trajOpenedFrom || document.activeElement;
  trajOpenedFrom = null;
  // Its own backdrop is spared: it is this drawer's click-outside-to-close target, not the page.
  trajInerted = inertEverythingExcept(trajEl.drawer, [trajEl.backdrop]);
  trajEl.drawer.addEventListener(
    "keydown",
    trajEl.drawer._trap || (trajEl.drawer._trap = (event) => trapTab(trajEl.drawer, event))
  );
  // A real control first, so Tab does not start at "leave" - the same preference `openModal` has.
  //: `:not([hidden])` on every branch, because a hidden control is not a place to put focus even
  //: when the render order is right — `#traj-run` is hidden on any single-run trace, and the
  //: transport buttons are disabled on a trace with no turns.
  const focusable = trajEl.drawer.querySelector(
    "input:not([hidden]), select:not([hidden]), textarea:not([hidden]), " +
      "button:not(#traj-close):not(:disabled):not([hidden]), " +
      "[tabindex]:not([tabindex='-1']):not([hidden])"
  );
  const target = focusable || trajEl.close || trajEl.drawer;
  if (target && typeof target.focus === "function") target.focus({ preventScroll: true });
}

//: Where focus goes when the drawer closes. The recorded trigger FIRST — but it is very often a
//: `.ticker-toggle` inside a chat turn, and any re-render between opening and closing replaces that
//: node, leaving a detached element whose `.focus()` is a silent no-op. Measured: zero `focusin`
//: events during close and focus ending on `<body>`, which is the same "parked outside an
//: `aria-modal` dialog" state as opening on `<body>`. So a detached trigger falls back to the
//: equivalent live control, and then to the composer, which is where a reader who has just finished
//: reading a trajectory most likely wants to be.
//: **`<body>` IS NOT A RETURN TARGET**, and `document.body.contains(document.body)` is `true` — so
//: a recorded `<body>` sailed through the attachment guard and made the whole fallback chain below
//: unreachable. Measured: closing by Escape, ✕ or backdrop all called `focus()` on `<body>`, which
//: strands the reader outside the focus order with no indicator, and the next Tab restarts at the
//: wordmark. The guard now asks the question it always meant to: is this a real, attached,
//: FOCUSABLE element?
const FOCUSABLE_TARGET = "a[href], button, input, select, textarea, [tabindex]";

function trajReturnTarget() {
  const recorded = trajReturnFocus;
  //: ONE question, not two. An earlier version also tested `recorded !== document.body` — which
  //: can never change the answer, because `<body>` does not match `FOCUSABLE_TARGET` either, and
  //: two guards that mask each other mean a mutation to either one is invisible. The focusable test
  //: is the question that was always meant: is this somewhere a reader can actually be?
  if (
    recorded &&
    recorded.nodeType === 1 &&
    typeof recorded.matches === "function" &&
    recorded.matches(FOCUSABLE_TARGET) &&
    !recorded.disabled &&
    document.body.contains(recorded)
  ) {
    return recorded;
  }
  return (
    document.querySelector(".turn:last-of-type .ticker-affordance .ticker-toggle") ||
    document.querySelector(".ticker-affordance .ticker-toggle") ||
    document.getElementById("ask-input")
  );
}

function trajReleaseFocus() {
  trajInerted.forEach((el) => {
    el.inert = false;
  });
  trajInerted = [];
  const target = trajReturnTarget();
  if (target && typeof target.focus === "function") target.focus({ preventScroll: true });
  trajReturnFocus = null;
}

function trajShowDrawer() {
  clearTimeout(trajCloseTimer);
  trajEl.backdrop.hidden = false;
  trajEl.drawer.hidden = false;
  // Flush the unhide before animating: coming from `display: none`, a transition has no start
  // frame and would jump straight to its end.
  void trajEl.drawer.offsetHeight;
  trajEl.backdrop.classList.add("is-shown");
  trajEl.drawer.classList.add("is-open");
  trajTakeFocus();
}

function closeTrajectory() {
  trajStopPlay();
  clearInterval(trajPoll);
  trajPoll = null;
  // BEFORE the 280ms slide-out, not after: the reader pressed Escape and their focus has to land
  // somewhere now, not a third of a second later.
  trajReleaseFocus();
  trajEl.drawer.classList.remove("is-open", "is-full");
  trajEl.backdrop.classList.remove("is-shown");
  trajEl.expand.textContent = "⤢";
  // ≥ the drawer's own transform transition, so the slide-out is never cut short by `hidden`.
  trajCloseTimer = setTimeout(() => {
    trajEl.drawer.hidden = true;
    trajEl.backdrop.hidden = true;
  }, 280);
}

//: Family colour + glyph per timeline segment. `--fam` is what the `.seg` rules tint themselves
//: from, so one assignment drives border, background, hover and the current-state ring together.
//: A segment never narrows past this, whatever its share of the run — the strip scrolls instead.
//: Squashing every call into a sliver is what made the first version unreadable.
const TRAJ_SEG_MIN_PX = 108;

const TRAJ_FAMILIES = {
  skill: { color: "var(--accent)", glyph: "\u25a4" },
  validate: { color: "var(--ok)", glyph: "\u2713" },
  lifeline: { color: "var(--warn)", glyph: "\u21d7" },
};

//: Chip labels for `run_start`'s meta. A raw key is the wire format, not a name a reader chose —
//: and `source_chars` in particular means nothing until it says what it counts.
const TRAJ_META_LABELS = {
  main_model: "planner",
  sub_model: "sub-LM",
  max_iterations: "max turns",
  max_tokens: "max tokens",
  max_retries: "retries",
  source_chars: "corpus chars",
  output_language: "language",
  language: "language",   // `naming.SuggestTitle` names it this way
  target_length: "length",
  question: "question",
  accept_language: "Accept-Language",
  interface_language: "interface",
};

function trajFamily(entry) {
  if (entry.ok === false || entry.passed === false) return { color: "var(--bad)", glyph: "\u2715" };
  return TRAJ_FAMILIES[entry.label] || { color: "var(--text-dim)", glyph: "\u25c6" };
}

// The generation caps the run actually ran under, and what it used against them. Built with
// createElement/textContent like every other model-adjacent string here (invariants 29 and 55).
//
// THREE states, and the third is the one that matters: `budget === null` means the trace predates
// rlm-harness 1.10.0 and simply does not carry the fields. That must read "not recorded" and never
// "no truncation" — reading an absent field as a zero is how a corpus boundary gets mistaken for a
// property of the code (CHANGELOG.md forbids averaging any rate across that upgrade).
function renderTrajBudget(budget) {
  if (!trajEl.budget) return;
  trajEl.budget.textContent = "";
  const tag = document.createElement("span");
  tag.className = "note-tag";
  const body = document.createElement("span");
  body.className = "note-body";
  let tone;

  if (!budget) {
    tag.textContent = t("traj.budgetTagNone", "\u24d8 budget");
    body.textContent = t(
      "traj.budgetNone",
      "This trace does not record token usage because it predates the field. That is not the same as \"nothing was truncated\".",
    );
    tone = "is-info";
  } else if (budget.truncated) {
    tag.textContent = t("traj.budgetTagCut", "\u26a0 truncated");
    body.textContent = t(
      "traj.budgetCut",
      "A turn hit the generation cap: {used} tokens against a cap of {cap}. A truncated code cell is usually repaired by the planner's next turn; a truncated final answer ends the run.",
      { used: budget.peak_completion, cap: budget.cap },
    );
    tone = "is-cut";
  } else if (budget.cap != null && budget.peak_completion != null) {
    tag.textContent = t("traj.budgetTag", "\u25cf budget");
    body.textContent = t(
      "traj.budgetOk",
      "Busiest turn used {used} of {cap} tokens ({pct}%).",
      { used: budget.peak_completion, cap: budget.cap, pct: Math.round(budget.ratio * 100) },
    );
    tone = "is-live";
  } else if (budget.cap != null) {
    // A cap WITH no usage is its own state, not "no cap": not every provider returns a usage
    // block. Collapsing the two said a cap of 16384 had never been reported.
    tag.textContent = t("traj.budgetTagNone", "\u24d8 budget");
    body.textContent = t(
      "traj.budgetNoUsage",
      "The generation cap was {cap} tokens; this run recorded no token usage to compare against it.",
      { cap: budget.cap },
    );
    tone = "is-info";
  } else {
    tag.textContent = t("traj.budgetTagNone", "\u24d8 budget");
    body.textContent = t("traj.budgetPartial", "No generation cap was reported for this run.");
    tone = "is-info";
  }

  trajEl.budget.appendChild(tag);
  trajEl.budget.appendChild(body);

  // `dropped` means dspy rejected the budget kwargs outright and every cap reverted to its own
  // default — so the numbers above were NOT the ones applied. APPENDED, never a replacement: a run
  // can both hit the cap and have its step budgets rejected, and an earlier version overwrote the
  // truncation colour here, which is the one thing the colours exist to keep separable.
  if (budget && budget.iterations && budget.iterations.dropped) {
    const warn = document.createElement("span");
    warn.className = "note-body";
    warn.textContent = t(
      "traj.budgetDropped",
      "The step budgets were rejected and reverted to the library's defaults, so the configured caps did not apply.",
    );
    trajEl.budget.appendChild(warn);
    tone = tone === "is-cut" ? "is-cut" : "is-info";
  }
  trajEl.budget.className = `traj-note ${tone}`;
  trajEl.budget.hidden = false;
}

function renderTrajectory(runId) {
  const turns = trajData.iterations || [];
  const line = trajData.timeline || [];

  // The run's own NAME, not a slug: the reader started this action and knows it by what it makes.
  trajEl.name.textContent = trajTaskLabel(trajData.initial?.task);
  trajEl.stat.textContent = t(
    "traj.stat",
    `${turns.length} turns \u00b7 ${line.length} tool calls${
      trajData.total_s != null ? ` \u00b7 ${formatTimecode(trajData.total_s)}` : ""
    }`,
    { turns: turns.length, tools: line.length }
  );

  // The run picker only earns its space when there IS more than one — an overview fires a summary
  // run and an FAQ run, and landing in one with no way to reach the other is the same
  // "which one did I just watch" problem the orbit picker has.
  trajEl.run.hidden = trajRunIds.length < 2;
  trajEl.run.textContent = "";
  trajRunIds.forEach((id) => {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = id.split("-").slice(-1)[0];
    option.selected = id === runId;
    trajEl.run.appendChild(option);
  });

  // Built from the BOOLEAN, not from the server's sentence. `timing_note` is English prose written
  // in `trajectory.py`, and rendering it verbatim put an English line in the middle of a Chinese
  // drawer — interface copy belongs to the interface (invariant 48), and the server's job here is
  // to say WHICH case holds.
  trajEl.note.hidden = false;
  trajEl.note.textContent = "";
  const tag = document.createElement("span");
  tag.className = "note-tag";
  tag.textContent = trajData.per_turn_timing
    ? t("traj.timingTag", "\u25cf per-turn timing")
    : t("traj.timingTagOff", "\u24d8 timing");
  const noteBody = document.createElement("span");
  noteBody.className = "note-body";
  noteBody.textContent = trajData.per_turn_timing
    ? t("traj.timingLive", "Per-turn timing is live, recorded as each turn was parsed.")
    : t(
        "traj.timingStale",
        "Per-turn timing isn't available for this trace; the tool timeline still carries real times.",
      );
  trajEl.note.appendChild(tag);
  trajEl.note.appendChild(noteBody);
  trajEl.note.className = `traj-note ${trajData.per_turn_timing ? "is-live" : "is-info"}`;
  renderTrajBudget(trajData.budget);
  //: **The axis labels what the strip PARTITIONS, which is tool time — not the run's wall clock.**
  //: `renderTrajTimeline` normalises segment widths by the sum of `duration_s`, so on a 99.1s run
  //: whose four tool calls took 185ms in total, a 180ms `read_skill` was drawn as 67% of an axis
  //: reading `START … 1:39`, the 40.6s the model spent thinking between calls was drawn as nothing,
  //: and a 2.9s sub-LM call got the same 108px floor as a 2ms validator. A TRUE label over an
  //: untrue layout is what invariant 60 forbids, and it is the worse of the two halves to keep.
  //:
  //: Laying out against `total_s` instead would be the other fix and is the wrong one here: the
  //: floor (`TRAJ_SEG_MIN_PX`) exists because these calls are milliseconds, so every segment would
  //: collapse to a sliver and the strip would carry no labels at all. The run's wall clock is
  //: already on the header stat, where it is true.
  trajEl.axisEnd.textContent = trajAxisLabel(trajData);

  // A LIVE run re-renders every few seconds, so the rebuild must not throw away where the reader
  // is. Resetting unconditionally sent someone watching a long podcast back to "Start" with an
  // empty search box every 4 seconds — in the one case the live read exists to serve.
  const priorSel = trajSel;
  const priorQuery = trajEl.search.value;
  renderTrajTimeline(line, turns);
  renderTrajSteps(turns);
  trajSearch(priorQuery);
  const stillThere =
    priorSel &&
    (priorSel.kind === "init" ||
      (priorSel.kind === "turn" && priorSel.index < turns.length) ||
      (priorSel.kind === "tool" && priorSel.index < line.length));
  trajSelect(stillThere ? priorSel.kind : "init", stillThere ? priorSel.index : 0);
  trajRefreshTransport();

  clearInterval(trajPoll);
  trajPoll = trajData.running
    ? setInterval(() => {
        if (trajEl.drawer.hidden) return;
        openTrajectory(trajRunIds, runId);
      }, 4000)
    : null;
}

// `penumbra.guide:GenerateSummary` -> `GenerateSummary`. The dotted path is how the worker is
// addressed, not what the reader asked for.
function trajTaskLabel(task) {
  if (!task) return "";
  return String(task).split(":").pop();
}

//: What the axis says, as a function so a test can run the REAL one. Written inline first, and the
//: scenario written for it rebuilt the same expression by hand — so reverting the product left the
//: test green, which is the shape this project keeps finding in its own suite.
function trajAxisLabel(data) {
  const toolTotal = ((data && data.timeline) || []).reduce((sum, e) => sum + (e.duration_s || 0), 0);
  return toolTotal > 0 ? formatTrajDuration(toolTotal) : "";
}

//: Sub-second durations are the normal case on this strip, and `formatTimecode` floors to whole
//: seconds — so four calls of 2-180ms all read `0:00` and the axis claimed the run took no time.
function formatTrajDuration(seconds) {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
  return formatTimecode(seconds);
}

function renderTrajTimeline(line, turns) {
  trajEl.timeline.textContent = "";
  if (!line.length) {
    const empty = document.createElement("div");
    empty.className = "traj-empty";
    // Says WHICH empty it is (invariant 70): the model never called the pre-SUBMIT validator its
    // own instructions ask for. This used to appear on every run for a different reason — the
    // validator did not record a `tool_call` event at all — so an empty strip meant nothing.
    empty.textContent = t(
      "traj.noTools",
      "This run called no tools, not even the validator its instructions ask it to run before SUBMIT.",
    );
    trajEl.timeline.appendChild(empty);
    return;
  }
  const total = line.reduce((sum, e) => sum + (e.duration_s || 0), 0) || 1;
  // **`flex-grow` must SUM to at least 1 or the strip does not fill.** CSS distributes free space
  // in proportion to the grow values and stops at their sum: four millisecond calls floored to
  // 0.01 each sum to 0.04, so 96% of the strip stayed empty (reported, with a screenshot).
  // Normalising by the total makes the sum exactly 1 — the free space is fully distributed and the
  // RATIOS between segments are unchanged, which is the half that has to survive.
  const weight = (entry) => Math.max(entry.duration_s || 0, 0.01);
  const weightTotal = line.reduce((sum, e) => sum + weight(e), 0) || 1;
  let markedTurn = -1;
  line.forEach((entry) => {
    // A "from here = Turn N" marker wherever the owning turn changes, so the strip and the nav are
    // one story rather than two lists to correlate by eye.
    if (entry.turn_index != null && entry.turn_index !== markedTurn) {
      markedTurn = entry.turn_index;
      const mark = document.createElement("button");
      mark.type = "button";
      mark.className = "turn-mark";
      const markLabel = document.createElement("span");
      markLabel.className = "tm-lab";
      // `+ 1`, because every OTHER surface counts turns from one — the nav rail says "Turn 3" and
      // the detail head says "Turn 3" for the call this mark sits on. The trace data stays
      // 0-indexed; only the label is human. Without it the strip said T2 for what the two panes
      // beside it both called turn 3.
      markLabel.textContent = `T${entry.turn_index + 1}`;
      mark.appendChild(markLabel);
      const markArrow = document.createElement("span");
      markArrow.className = "tm-arrow";
      markArrow.textContent = "\u25b8";
      mark.appendChild(markArrow);
      mark.addEventListener("click", () => {
        trajStopPlay();
        trajSelect("turn", entry.turn_index);
      });
      trajEl.timeline.appendChild(mark);
    }

    const family = trajFamily(entry);
    const seg = document.createElement("button");
    seg.type = "button";
    seg.className = "seg";
    seg.style.setProperty("--fam", family.color);
    // `flex: <duration> 0 <floor>px`, which is the sibling's own sizing and the part a first pass
    // reimplemented from scratch and got wrong twice. GROW is what makes a run with one tool call
    // fill the strip instead of sitting at a fixed width beside empty space (reported), and the
    // basis is a floor so a fast call stays readable rather than collapsing to a sliver (also
    // reported, from the version before that, which grew against the strip's total with no basis).
    const dur = Math.max(entry.duration_s || 0, 0);
    const basis = Math.max(TRAJ_SEG_MIN_PX, Math.round((dur / total) * 720));
    seg.style.flex = `${(weight(entry) / weightTotal).toFixed(4)} 0 ${basis}px`;

    const icon = document.createElement("span");
    icon.className = "seg-ic";
    icon.textContent = family.glyph;
    seg.appendChild(icon);

    const label = document.createElement("span");
    label.className = "seg-lab";
    // The TARGET is the name a reader recognises — `corpus-navigation`, not `skill
    // corpus-navigation`. The family is already carried by the icon and the segment's own colour,
    // so repeating it in words is the redundancy a user asked about. It falls back to the family
    // for a call that has no target, and the tooltip keeps both.
    label.textContent = entry.target || entry.label;
    seg.appendChild(label);

    const durEl = document.createElement("span");
    durEl.className = "seg-dur";
    durEl.textContent = trajSecs(entry.duration_s);
    seg.appendChild(durEl);

    seg.addEventListener("click", () => {
      trajStopPlay();
      trajSelect("tool", entry.seq);
    });
    trajEl.timeline.appendChild(seg);
  });
}

function trajSecs(s) {
  if (s == null) return "";
  if (s < 1) return `${Math.round(s * 1000)}ms`;
  return s < 60 ? `${s.toFixed(1)}s` : formatTimecode(s);
}

function renderTrajSteps(turns) {
  trajEl.steps.textContent = "";
  trajEl.steps.appendChild(
    trajStepRow("init", 0, t("traj.init", "Init"), t("traj.initSub", "input + env"), null, 1)
  );
  const longest = turns.reduce((m, tn) => Math.max(m, tn.duration_s || 0), 0) || 1;
  turns.forEach((turn) => {
    trajEl.steps.appendChild(
      trajStepRow(
        "turn",
        turn.index,
        t("traj.turn", `Turn ${turn.index + 1}`, { n: turn.index + 1 }),
        turn.reasoning || turn.code || "",
        trajSecs(turn.duration_s),
        (turn.duration_s || 0) / longest
      )
    );
  });
}

function trajStepRow(kind, index, name, preview, duration, share) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = "tstep";
  row.dataset.kind = kind;
  row.dataset.index = String(index);

  const title = document.createElement("span");
  title.className = "tstep-name";
  title.textContent = name;
  row.appendChild(title);

  if (preview) {
    const line = document.createElement("span");
    line.className = "tstep-preview";
    line.textContent = preview;
    row.appendChild(line);
  }
  if (duration) {
    const dur = document.createElement("span");
    dur.className = "tstep-dur";
    dur.textContent = duration;
    row.appendChild(dur);
    // The bar is the point: a column of numbers makes the reader compare, a bar makes the slow turn
    // findable at a glance. Only where there IS a duration — an untimed trace gets no fake bars.
    const bar = document.createElement("span");
    bar.className = "tstep-bar";
    bar.style.width = `${Math.max(4, Math.round((share || 0) * 100))}%`;
    row.appendChild(bar);
  }

  row.addEventListener("click", () => {
    trajStopPlay();
    trajSelect(kind, index);
  });
  return row;
}

function trajSelect(kind, index) {
  trajSel = { kind, index };
  trajEl.steps.querySelectorAll(".tstep").forEach((row) => {
    row.classList.toggle(
      "is-current",
      row.dataset.kind === kind && Number(row.dataset.index) === index
    );
  });
  let seen = -1;
  trajEl.timeline.querySelectorAll(".seg").forEach((seg) => {
    seen += 1;
    seg.classList.toggle("is-current", kind === "tool" && seen === index);
  });
  const current = trajEl.steps.querySelector(".tstep.is-current");
  if (current) current.scrollIntoView({ block: "nearest" });
  renderTrajDetail();
}

function renderTrajDetail() {
  const host = trajEl.detail;
  host.textContent = "";
  if (!trajData || !trajSel) return;

  if (trajSel.kind === "init") {
    trajDetailHead(host, t("traj.initTitle", "Initial state"), t("traj.initSub", "input + env"));
    const chips = document.createElement("div");
    chips.className = "ini-chips";
    Object.entries((trajData.initial || {}).meta || {}).forEach(([key, value]) => {
      // `task` is already the drawer's headline. A chip repeating it is the whole reason this panel
      // read as empty when it was the only key there was.
      if (key === "task") return;
      const chip = document.createElement("span");
      chip.className = "ini-chip";
      const name = document.createElement("b");
      //: Through `t()`: these twelve chips are the whole "Initial state" panel of the drawer, and
      //: they rendered the raw English key — in the same function that REJECTS the server's
      //: `timing_note` because "interface copy belongs to the interface" (invariant 48).
      const label = TRAJ_META_LABELS[key];
      name.textContent = label ? t(`traj.meta.${key}`, label) : key;
      chip.appendChild(name);
      chip.appendChild(
        document.createTextNode(
          key === "source_chars" ? ` ${Number(value).toLocaleString()}` : ` ${value}`
        )
      );
      chips.appendChild(chip);
    });
    if (chips.children.length) {
      host.appendChild(chips);
    } else {
      // An empty panel reads as broken, so the empty STATE says which one this is. Two live causes,
      // and neither of them is "an old trace" — that was only the first one anybody hit:
      //
      //  - NOTHING WRITTEN YET. `_run_isolated` reserves `traces/{run_id}.jsonl` exclusively BEFORE
      //    spawning (invariant 29), and `run_trajectory` stops at a torn final line because the
      //    writer is mid-flush. So a run opened in its first moments, or one whose spawn failed, or
      //    one killed instantly, has a real file with zero events. `traces._is_ours` accepts an
      //    empty file for exactly this reason.
      //  - NO CONFIGURATION RECORDED. A trace written by an older build of this project, which
      //    stamped only `task`.
      //
      // An earlier wording named only the second and dated it, and a user asked what it meant;
      // deleting the old traces would have made it a sentence describing a cause nobody could hit
      // any more while the branch stayed reachable through the first.
      const note = document.createElement("div");
      note.className = "det-sub";
      note.textContent = trajData.started_at
        ? t("traj.noMeta", "No configuration was recorded for this run.")
        : t(
            "traj.notStarted",
            "Nothing has been recorded for this run yet. It may still be starting, or it never got going.",
          );
      host.appendChild(note);
    }
    if (trajData.error) trajField(host, t("traj.error", "Error"), trajData.error);
    return;
  }

  if (trajSel.kind === "turn") {
    const turn = (trajData.iterations || [])[trajSel.index];
    if (!turn) return;
    trajDetailHead(
      host,
      t("traj.turn", `Turn ${turn.index + 1}`, { n: turn.index + 1 }),
      trajSecs(turn.duration_s)
    );
    if (turn.reasoning) {
      const reason = document.createElement("div");
      reason.className = "det-reason";
      reason.textContent = turn.reasoning;
      host.appendChild(reason);
    }
    trajField(host, t("traj.code", "Code"), turn.code);
    trajField(host, t("traj.output", "Output"), turn.output);
    return;
  }

  const entry = (trajData.timeline || [])[trajSel.index];
  if (!entry) return;
  // The facts a tooltip would have carried live HERE — a `.seg` clips its own tip and sits inside
  // an `overflow-x` scroller besides (invariant 54), and clicking one lands on this pane anyway.
  trajDetailHead(
    host,
    entry.target ? `${entry.label} \u00b7 ${entry.target}` : entry.label,
    [
      entry.rel_s != null ? `+${trajSecs(entry.rel_s)}` : "",
      trajSecs(entry.duration_s),
      entry.turn_index != null
        ? t("traj.turn", `Turn ${entry.turn_index + 1}`, { n: entry.turn_index + 1 })
        : "",
    ]
      .filter(Boolean)
      .join(" \u00b7 ")
  );
  if (entry.verdict) trajField(host, t("traj.verdict", "Verdict"), entry.verdict);
  if (entry.content) trajField(host, t("traj.result", "Result"), entry.content);
  if (entry.input) trajField(host, t("traj.input", "Input"), entry.input);
  if (entry.output) trajField(host, t("traj.output", "Output"), entry.output);
  if (entry.error) trajField(host, t("traj.error", "Error"), entry.error);
  Object.entries(entry.fields || {}).forEach(([key, value]) => trajField(host, key, String(value)));
  // A way BACK to the turn whose code made this call. The head already names it, and naming a turn
  // a reader then has to find in the nav by eye is the two-lists-to-correlate problem the strip's
  // own turn marks exist to remove. On EVERY attributed segment, not only a failed one: "why was
  // this called" is the same question whether or not it worked. Absent when the trace has no live
  // per-turn timing, since nothing is attributed then and a button reading "open turn null" is
  // worse than no button.
  if (entry.turn_index != null) {
    const jump = document.createElement("button");
    jump.type = "button";
    jump.className = "btn det-jump";
    jump.textContent = t("traj.openTurn", `\u2191 Open turn ${entry.turn_index + 1}`, {
      n: entry.turn_index + 1,
    });
    jump.addEventListener("click", () => {
      trajStopPlay();
      trajSelect("turn", entry.turn_index);
    });
    host.appendChild(jump);
  }
}

function trajDetailHead(host, title, sub) {
  const head = document.createElement("div");
  head.className = "det-head";
  const h = document.createElement("h3");
  h.textContent = title;
  head.appendChild(h);
  if (sub) {
    const s = document.createElement("span");
    s.className = "det-sub";
    s.textContent = sub;
    head.appendChild(s);
  }
  host.appendChild(head);
}

function trajField(host, label, value) {
  if (value == null || value === "") return;
  const wrap = document.createElement("div");
  wrap.className = "det-field";
  const name = document.createElement("div");
  name.className = "det-field-name";
  name.textContent = label;
  wrap.appendChild(name);
  const body = document.createElement("div");
  // `textContent`, always — every string here came out of a model that has been reading source
  // content an attacker may have written (invariant 29's rule, at the surface it matters most).
  body.className = "det-field-body";
  body.textContent = value;
  wrap.appendChild(body);
  host.appendChild(wrap);
}

// ---- replay transport ----------------------------------------------------------------------
// Dwell on each stop for the time it REALLY took, divided by the speed — so watching at 1× is
// watching the run happen. A stop with no live timing gets a brief nominal length rather than
// being skipped, which would silently drop every turn of a finalize-flushed trace.

function trajStops() {
  return [{ kind: "init", index: 0 }].concat(
    (trajData?.iterations || []).map((turn) => ({ kind: "turn", index: turn.index }))
  );
}

function trajRealMs(stop) {
  if (stop.kind === "turn" && trajData?.per_turn_timing) {
    const turn = (trajData.iterations || [])[stop.index];
    return Math.max(0, (turn?.duration_s || 0) * 1000);
  }
  return TRAJ_NOMINAL_MS;
}

function trajStep(direction) {
  trajStopPlay();
  const stops = trajStops();
  // A TOOL selection is not a walkable stop, so stepping from one starts at its own turn — the
  // reader keeps moving through the run instead of being bounced back to the start.
  const from = trajSel && trajSel.kind === "tool"
    ? stops.findIndex((s) => s.kind === "turn" && s.index === trajToolTurn(trajSel.index))
    : stops.findIndex((s) => trajSel && s.kind === trajSel.kind && s.index === trajSel.index);
  const at = from < 0 ? 0 : from;
  const next = stops[Math.min(stops.length - 1, Math.max(0, at + direction))];
  if (next) trajSelect(next.kind, next.index);
}

function trajToolTurn(seq) {
  const entry = (trajData?.timeline || [])[seq];
  return entry && entry.turn_index != null ? entry.turn_index : 0;
}

function trajTogglePlay() {
  if (trajPlayTimer) return trajStopPlay();
  trajEl.play.textContent = "⏸";
  trajAdvance(true);
}

function trajAdvance(first) {
  const stops = trajStops();
  let at = stops.findIndex((s) => trajSel && s.kind === trajSel.kind && s.index === trajSel.index);
  if (at < 0) at = 0;
  if (!first) at += 1;
  if (at >= stops.length) return trajStopPlay();
  trajSelect(stops[at].kind, stops[at].index);
  const dwell = Math.max(TRAJ_DWELL_FLOOR_MS, trajRealMs(stops[at]) / Math.max(1e-9, trajSpeed));
  trajShowProgress(stops[at], dwell);
  trajPlayTimer = setTimeout(() => trajAdvance(false), dwell);
}

function trajStopPlay() {
  clearTimeout(trajPlayTimer);
  trajPlayTimer = null;
  if (trajEl.play) trajEl.play.textContent = "▶";
  if (trajEl.progress) trajEl.progress.hidden = true;
}

// The replay dwells on each stop for the time it REALLY took divided by the speed, and without a
// bar that is indistinguishable from a frozen panel — a reader watching a 7-second turn has no way
// to tell playback from a hang, which is the same complaint the run ticker's long-wait tier exists
// to answer. Names the stop as well as drawing the bar, because a bar alone says how long is left
// and not what it is waiting for.
function trajShowProgress(stop, dwell) {
  // `bar`, not `row`: `test_every_hidden_toggled_class_still_honours_the_hidden_attribute` matches
  // `<var>.hidden =` across the WHOLE file, and three other functions here build `const row =
  // document.createElement(...)`. Its documented answer to that collision is to rename the local
  // rather than loosen the tripwire, and it duly failed the build naming `orbit-row`,
  // `starter-questions` and `tstep`.
  const bar = trajEl.progress;
  if (!bar) return;
  const label = bar.querySelector(".tp-label");
  const fill = bar.querySelector(".tp-fill");
  if (!label || !fill) return;
  bar.hidden = false;
  const name =
    stop.kind === "init"
      ? t("traj.init", "Init")
      : t("traj.turn", `Turn ${stop.index + 1}`, { n: stop.index + 1 });
  label.textContent = `\u25b6 ${name} \u00b7 ${trajSecs(dwell / 1000)}`;
  // RESTART the transition rather than letting it continue: clear it, snap to zero, force a
  // reflow, then run it. Without the reflow the browser coalesces both writes into one style
  // recalculation and the bar jumps straight to 100% with no animation at all.
  fill.style.transition = "none";
  fill.style.width = "0%";
  void fill.offsetWidth;
  fill.style.transition = `width ${dwell}ms linear`;
  fill.style.width = "100%";
}

function trajRefreshTransport() {
  const off = trajStops().length <= 1;
  [trajEl.prev, trajEl.play, trajEl.next].forEach((b) => {
    if (b) b.disabled = off;
  });
  if (off) trajStopPlay();
}

// ---- search --------------------------------------------------------------------------------

function trajSearch(query) {
  const needle = (query || "").trim().toLowerCase();
  trajMatches = [];
  trajMatchCur = -1;
  trajEl.steps.querySelectorAll(".tstep").forEach((row) => {
    const kind = row.dataset.kind;
    const index = Number(row.dataset.index);
    let hay = "";
    if (kind === "turn") {
      const turn = (trajData?.iterations || [])[index] || {};
      hay = `${turn.reasoning || ""}\n${turn.code || ""}\n${turn.output || ""}`;
    } else {
      hay = JSON.stringify(trajData?.initial || {});
    }
    const hit = needle !== "" && hay.toLowerCase().includes(needle);
    row.classList.toggle("is-match", hit);
    if (hit) trajMatches.push({ kind, index });
  });
  trajEl.searchCount.textContent = needle === ""
    ? ""
    : t("traj.matches", `${trajMatches.length} matches`, { n: trajMatches.length });
}

function trajCycleMatch() {
  if (!trajMatches.length) return;
  trajMatchCur = (trajMatchCur + 1) % trajMatches.length;
  const target = trajMatches[trajMatchCur];
  trajStopPlay();
  trajSelect(target.kind, target.index);
}

trajInit();

// ==================================================================================================
// THE HORIZON (Tier 0) — the default surface
// ==================================================================================================
//
// Everything captured lands here; an orbit is a place you go INTO (invariant 78's two tiers).
//
// The design constraint that shapes this file: invariant 51 forbids rendering `og:image`, so there
// is no thumbnail to recognise a node by. Recall has to be TYPOGRAPHIC, which is why a row renders
// its title and summary as prose in the reading face and why `renderNode` spends its effort on
// those two fields rather than on a card.
//
// Never `innerHTML` (invariant 55): every node here is built with `createElement` and `textContent`.
// A captured page's title is attacker-influenced text and a summary is model output, so both are
// exactly the inputs that rule exists for.

//: A tiny element builder. The rest of this file predates it and uses raw `createElement` 168 times;
//: this is not a refactor of that, only a way to keep the new surface readable. `text` goes through
//: `textContent`, which is what makes the never-`innerHTML` rule structural here rather than a
//: convention someone has to remember at each call site.
function elt(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

const horizonState = {
  nodes: [],
  total: 0,
  undistilled: 0,
  offset: 0,
  pollTimer: null,
  open: new Set(),
  query: "",
  findTimer: null,
  //: The summary pass's last reported state, kept here rather than read straight off the poll,
  //: because `updateStreamFoot` runs from several paths that have no status in hand.
  distil: { running: false, done: 0, total: 0, failed: 0, error: "" },
  //: The ceiling a node must fit under to be usable in an orbit (invariant 8). Reported by the
  //: listing, because the upload cap is six times larger and nothing else would say so.
  corpusCharCap: 0,
};

const HORIZON_PAGE = 25;

//: Node states that mean the server is still working on it, so the stream keeps polling. Written
//: down once: a state added later and missed here would leave a row pulsing forever.
const HORIZON_BUSY_STATES = new Set(["queued", "parsing", "distilling"]);

function horizonEl(id) {
  return document.getElementById(id);
}

// --- view switching ---------------------------------------------------------------------------

//: `data-view` on <body> is what the header reads to decide whether the Horizon crumb is the only
//: route home. The rail is inside `#view-horizon`, so once an orbit is open there is no rail and no
//: sibling selector that reaches the header from here - the attribute is the seam. Set in BOTH
//: functions and nowhere else, so the two can never disagree about which view is up.
//:
//: **They also write the address bar, and that is the other half of "an orbit is a place you go
//: into".** There was no URL state at all: `location.href` was the same string whether you were
//: looking at the Horizon or three levels into an orbit, so Back navigated out of the APPLICATION
//: rather than out of the orbit, a reload always landed on the Horizon, and an orbit could not
//: be bookmarked, linked or reopened. Back is the first motion a reader reaches for once the front
//: door is somewhere else.
//:
//: `?nb=` and not a path segment, because the app is served from one route and a path would need
//: the server to know about it. `pushState` here, `replaceState` for the token (`captureApiToken`):
//: the token must never become a history entry, and an orbit must always be one.
//: The browser tab, and the Tauri window title after it. It said the product name alone on every screen,
//: so a reader with three tabs open had three identical ones and no way to tell which orbit was
//: which - the one job a title bar has.
function syncDocumentTitle(orbitId) {
  const where = orbitId
    ? state.title || firstClause(state.derivedTitle) || t("app.untitled", "Untitled orbit")
    : t("horizon.home", "Horizon");
  document.title = `${where} \u2014 Penumbra`;
}

function syncAddressBar(orbitId, { replace = false } = {}) {
  try {
    const url = new URL(window.location.href);
    if (orbitId) url.searchParams.set("nb", orbitId);
    else url.searchParams.delete("nb");
    const next = url.pathname + url.search + url.hash;
    if (next === window.location.pathname + window.location.search + window.location.hash) return;
    const how = replace ? "replaceState" : "pushState";
    window.history[how]({ nb: orbitId || "" }, "", next);
  } catch {
    // Same reasoning as `captureApiToken`: no `URL`/`history` in some contexts (a Node `vm` is
    // one), and losing the address bar must never cost the reader the application.
  }
}

//: **Keyboard shortcuts, because a window with none is a browser tab with the chrome removed.**
//: Every global `keydown` in this file handled exactly one key — `Escape` — so the product had no
//: ⌘K, no ⌘F, no ⌘,, no accesskey and no palette, and on the screen built for capture the field was
//: the SIXTEENTH tab stop (three header controls plus one per orbit, a list that grows). An
//: independent review called it the clearest "web page, not app" tell in the product, and it is the
//: one that matters most for the planned Tauri shell.
//:
//: Modifier combinations ONLY, and `metaKey || ctrlKey` so one binding serves macOS and
//: Windows/Linux. A bare-letter shortcut would have to know whether the reader is typing, and this
//: product is mostly a text field — the guessing is where that class of bug lives. `Escape` is
//: deliberately NOT here: the overlays own it, each returning focus to what opened it, and a global
//: handler would fight them.
//: **Each binding REPORTS whether it did anything, and only then is the browser's own shortcut
//: swallowed.** ⌘F is the case that forces this: the find field is hidden on an empty Horizon, so an
//: unconditional `preventDefault` would take the browser's Find away and put nothing in its place —
//: the reader presses a key they have used for thirty years and the page silently eats it. A
//: shortcut that cannot act declines, and the browser does its own thing.
const SHORTCUTS = [
  //: ⌘K goes to the primary text field of the screen you are ON — capture on the Horizon, the
  //: composer in an orbit. One key, one meaning ("start typing the thing this screen is for"),
  //: rather than two bindings a reader has to remember the difference between.
  { key: "k", run: () => focusIfUsable(viewIsHorizon() ? "capture-input" : "ask-input") },
  { key: "f", run: () => focusFind() },
  { key: ",", run: () => clickIfPresent("settings-open") },
];

function viewIsHorizon() {
  return document.body.dataset.view === "horizon";
}

//: **The first tab stop on every screen, and it pointed at a hidden element.** `#capture-input`
//: lives inside `#view-horizon`, which is `hidden` whenever an orbit is open — so in an orbit the
//: skip link moved focus nowhere, left a dead `#capture-input` fragment in the address bar, and
//: named a destination that is not on that screen. SC 2.4.1 (Bypass Blocks) unsatisfied and SC
//: 2.4.4 on the label, on the very first thing a keyboard reader meets.
//:
//: Both halves follow the view, and the press does the focusing itself rather than trusting the
//: fragment: a fragment moves focus only if the target is focusable AND rendered, which is exactly
//: the condition that failed here.
//: **The rail said the Horizon was current while you were inside an orbit.** `is-current` was
//: written into the rail's old Horizon row and nothing ever took it off, so the one control that
//: shows the two-tier model marked the wrong tier the moment you went into an orbit — and no
//: facet carried `aria-current`, so a screen reader was told nothing either way.
function syncFacetCurrent() {
  const horizon = viewIsHorizon();
  //: The rail lists orbits only. It used to open with a "Horizon" row, a second way home beside the
  //: moon and the crumb in the header, and on the Horizon it repeated the screen you were on.
  //: `page`, not `true`: these are places you navigate to, which is what the token means.
  document.querySelectorAll("#facet-list .facet").forEach((item) => {
    const on = !horizon && item.dataset.orbitId === state.orbitId;
    item.classList.toggle("is-current", on);
    if (on) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
}

function syncSkipLink() {
  const link = document.querySelector(".skip-link");
  if (!link) return;
  const horizon = viewIsHorizon();
  link.setAttribute("href", horizon ? "#capture-input" : "#ask-input");
  link.textContent = horizon
    ? t("app.skipToCapture", "Skip to capture")
    : t("app.skipToAsk", "Skip to the question box");
}

//: Focuses `id` and says whether it could. A hidden or disabled control is not somewhere focus can
//: go — `HTMLElement.focus()` is simply a no-op there — and the caller has to know, or it reports
//: having handled a key it did nothing with.
function focusIfUsable(id) {
  const field = document.getElementById(id);
  if (!field || field.disabled || !field.offsetParent) return false;
  field.focus();
  return document.activeElement === field;
}

function clickIfPresent(id) {
  const el = document.getElementById(id);
  if (!el || el.disabled || !el.offsetParent) return false;
  el.click();
  return true;
}

function focusFind() {
  //: The find field lives on the Horizon only. From an orbit, ⌘F goes home first rather than doing
  //: nothing — "find something I kept" is a Tier 0 question, and the Horizon is where it is answered.
  if (!viewIsHorizon()) showHorizon();
  return focusIfUsable("stream-search");
}

function installShortcuts() {
  const skip = document.querySelector(".skip-link");
  if (skip) {
    skip.addEventListener("click", (event) => {
      event.preventDefault();
      focusIfUsable(viewIsHorizon() ? "capture-input" : "ask-input");
    });
  }
  syncSkipLink();
  document.addEventListener("keydown", (event) => {
    if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
    const hit = SHORTCUTS.find((s) => s.key === event.key.toLowerCase());
    if (!hit) return;
    if (hit.run()) event.preventDefault();
  });
}

//: **Narrow windows: one orbit panel at a time** (`.col-switch`, below 640px only — a narrow
//: desktop window or high zoom; this is a desktop app). The data
//: attribute is inert on wider screens — the stylesheet reads it only inside that media query — so
//: every caller can set a panel without asking how wide the window is.
//:
//: Each panel keeps its own scroll position. The stacked page was one scroller, and a reader who
//: switched to Studio and back would otherwise land at the top of a long conversation.
const panelScroll = {};

function setPanel(name, { focus = false } = {}) {
  const cols = document.getElementById("view-orbit");
  if (!cols) return;
  const was = cols.dataset.panel;
  if (was && was !== name) panelScroll[was] = cols.scrollTop;
  cols.dataset.panel = name;
  document.querySelectorAll(".col-switch-tab").forEach((tab) => {
    const on = tab.dataset.panel === name;
    tab.setAttribute("aria-selected", on ? "true" : "false");
    tab.tabIndex = on ? 0 : -1;
    if (on && focus) tab.focus();
  });
  if (was !== name) cols.scrollTop = panelScroll[name] || 0;
}

function installColumnSwitch() {
  const tabs = [...document.querySelectorAll(".col-switch-tab")];
  tabs.forEach((tab, at) => {
    tab.addEventListener("click", () => setPanel(tab.dataset.panel));
    //: The WAI-ARIA tabs pattern, as the Studio's own view tabs already do: arrows move between
    //: tabs, and the tab list is ONE stop in the Tab order.
    tab.addEventListener("keydown", (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1, Home: -tabs.length, End: tabs.length }[event.key];
      if (step === undefined) return;
      event.preventDefault();
      const next = tabs[Math.min(tabs.length - 1, Math.max(0, at + step))];
      setPanel(next.dataset.panel, { focus: true });
    });
  });
  //: An orbit opens on the conversation — unless it has no sources, where the only useful
  //: thing to do is add one and the Chat panel would show a disabled composer.
  store.on("orbit:switched", () => {
    Object.keys(panelScroll).forEach((key) => delete panelScroll[key]);
    setPanel((state.sources || []).length ? "chat" : "sources");
  });
  setPanel("chat");
}

function showHorizon({ push = true } = {}) {
  orbitVisit.orbitId = null; // leaving the orbit ends the visit
  horizonEl("view-horizon").hidden = false;
  horizonEl("view-orbit").hidden = true;
  horizonEl("view-graph").hidden = true;
  horizonEl("horizon-home").classList.add("is-current");
  document.body.dataset.view = "horizon";
  if (push) syncAddressBar("");
  syncDocumentTitle("");
  refreshHorizon({ reset: true });
  //: The capture field is a drawer now, so it is NOT focused on arrival: focus would hold it open
  //: over the map for good. N opens it and puts the cursor in it from anywhere on the Horizon, and
  //: its grip is among the first tab stops, so capturing is still one key away.
  syncCaptureDock();
  syncSkipLink();
  syncFacetCurrent();
  applyViewMode();
}

function showOrbitView({ push = true } = {}) {
  horizonEl("view-horizon").hidden = true;
  horizonEl("view-orbit").hidden = false;
  horizonEl("horizon-home").classList.remove("is-current");
  document.body.dataset.view = "orbit";
  //: AFTER `dataset.view`, not before: both of these ASK which view is showing, and asking before
  //: the answer has been written gets the previous one. The first version of this ran three lines
  //: up and left the rail marking the Horizon as current from inside an orbit — the exact bug it
  //: was added to fix.
  syncSkipLink();
  syncFacetCurrent();
  if (push) syncAddressBar(state.orbitId || "");
  syncDocumentTitle(state.orbitId || "");
  stopHorizonPolling();
  beginOrbitVisit();
  applyViewMode();
}

//: Back and Forward. `push: false` on both branches, or restoring a state would push a NEW entry
//: for the one being restored and the reader could never leave.
window.addEventListener("popstate", async (event) => {
  const wanted = (event.state && event.state.nb) || new URL(window.location.href).searchParams.get("nb") || "";
  if (!wanted) {
    showHorizon({ push: false });
    return;
  }
  await openOrbit(wanted, { push: false });
});

// --- rendering ------------------------------------------------------------------------------------

//: Text pasted straight in has no title and no origin: `ingest_pasted_text` builds
//: `pasted:{first 60 chars} #{hash}`, which is a fragment cut mid-word. The first render of this
//: surface put that fragment in the TITLE slot, and rows read "Less, but bette" and "the reason I
//: cannot" - text that looks broken rather than excerpted.
//:
//: So a pasted node has no title at all. Its fragment is PROSE and goes in the prose slot, trimmed
//: at a word boundary and with no ellipsis: the skill's rule for a fixed slot is to guarantee the
//: fit, not to rescue an overflow with a glyph, and an excerpt that ends on a whole word reads as
//: an excerpt while one that ends on "bette" reads as a defect.
//: **Only a CUT value is cut**, and the first two versions of this function both got that wrong.
//:
//: `ingest_pasted_text` builds the origin as `pasted:{text[:60].strip()} #{hash}`, so the snippet
//: is truncated ONLY when the note was longer than sixty characters. Both earlier versions cut at
//: `lastIndexOf(" ")` unconditionally whenever that space fell past index 24 — which is most
//: English notes — so "Swallow test note about editorial recall." arrived complete at 41
//: characters and rendered as "Swallow test note about editorial". The last word of a note that
//: FITTED was deleted, on the default screen, under a hint promising the text is kept as written.
//: An independent review caught it by pasting a sentence and reading the row.
//:
//: **And when it IS cut, it says so with an ellipsis.** The no-glyph rule comes from `facetLabel`,
//: and it belongs there: a rail label is a NAME in a thirteen-rem slot, where a tail ellipsis costs
//: width and conveys nothing. This is PROSE in a sixty-three-character column, where an ellipsis is
//: the ordinary typographic signal that a sentence continues — and without one, the hand-written
//: list of dangling function words below produced "...is a river, not" and "...the reason I", which
//: is precisely the reads-as-broken failure that list exists to prevent.
//:
//: A note of exactly sixty characters is ellipsised although nothing was lost. That is the one
//: conservative case, it is unfixable from this side (the origin carries no length), and "there may
//: be more" is the safe direction to be wrong in.
const PASTED_SNIPPET_CAP = 60;

//: Trailing function words, dropped after a cut so the excerpt does not end on "to" or "the".
//: English-only, deliberately: Chinese has no space to cut at, so `lastIndexOf(" ")` finds nothing
//: and the whole fragment is kept, which is right for a script with no word boundaries.
const DANGLING_TAIL =
  /[ ](?:a|an|and|as|at|but|by|for|from|if|in|into|is|it|of|on|or|so|that|the|to|with)$/i;

function pastedExcerpt(origin) {
  const raw = origin.slice("pasted:".length).split(" #")[0].trim();
  // Nothing was lost: show it whole, with no mark. `<=`, not `<`: `ingest_pasted_text` is
  // `text[:60].strip()`, and the strip can drop the sixtieth character - so a cut sentence arrives
  // at 59 and `<` waved it through unmarked. The seeded data ships one ("...the reason I cannot").
  if (raw.length < PASTED_SNIPPET_CAP - 1) return raw;

  // **Truncated, so it is MARKED - whatever the script.** The word-boundary trim below is an
  // English nicety; the ellipsis is the part that carries meaning, and the first version made the
  // ellipsis depend on the trim. `lastIndexOf(" ")` returns -1 for a Chinese sentence, which has no
  // interword spaces, so the early return handed back the server's raw 60-character slice with no
  // mark at all - a cut sentence reading as a finished one, in the interface's DEFAULT language.
  const cut = raw.lastIndexOf(" ");
  if (cut <= 24) return `${raw}\u2026`;
  let text = raw.slice(0, cut);
  // Twice: "should never ask me to the" is two function words deep, which one pass leaves ending
  // on "the".
  for (let n = 0; n < 2; n += 1) text = text.replace(DANGLING_TAIL, "");
  return `${text}\u2026`;
}

//: The Horizon's failure block, in the SAME shape the chat turn and the summary pass use: a heading
//: naming the state, then the technical text in the mono face, inside a bordered tinted block.
//: Three failure surfaces reading three different ways is three chances not to recognise one.
//: **ONE SHAPE FOR A FAILURE, wherever it lands.** Four surfaces disagreed about what failure looks
//: like: the chat turn and the Horizon row each got a tinted block with a coloured head and the
//: server's sentence under it, while the guide body, the podcast panel and the chat overview got a
//: bare text node reading `（錯誤）…` — the literal "(error)" prefix round two banned, still in
//: place on the three actions that SPEND MONEY. `app.js` even carries the argument against that
//: prefix, in a comment, for the one surface it was applied to.
//:
//: `failureBlock` is that shape, with the heading as an argument because "that question did not
//: run" and "could not read this" are different sentences about the same kind of event.
function failureBlock(heading, message) {
  const block = elt("div", "failure-block");
  block.appendChild(elt("div", "failure-head", heading));
  block.appendChild(elt("div", "failure-why", readableError(message)));
  return block;
}

function nodeErrorBlock(message) {
  const block = elt("div", "node-error");
  block.appendChild(elt("span", "node-error-head", t("horizon.couldNotRead", "Could not read this")));
  block.appendChild(elt("span", "node-error-why", readableError(message)));
  return block;
}

//: The ladder: the distilled title, then the page's OWN title, then the host. The middle rung was
//: missing, and distillation is opt-in (invariant 80) so UNDISTILLED is the river's default state -
//: ten saved articles from one site were ten identical rows reading `en.wikipedia.org`. The title
//: was in hand the whole way (`preview.title`, scraped from html already fetched - invariant 51,
//: metadata never an image), and the orbit's source list already used it.
function nodeHeadline(node) {
  if (node.title) return node.title;
  const preview = node.preview || {};
  if (preview.title) return preview.title;
  const origin = node.origin || "";
  if (origin.startsWith("pasted:")) return "";
  return originLabel(origin);
}

function nodeProse(node) {
  if (node.summary) return node.summary;
  const origin = node.origin || "";
  return origin.startsWith("pasted:") ? pastedExcerpt(origin) : "";
}

//: The part of a URL that is NOT the host: `/papers/attention.pdf?v=2`. Falls back to the whole
//: origin when there is no path to show, so a bare domain still says something.
function originPath(origin) {
  try {
    const url = new URL(origin);
    const rest = `${url.pathname}${url.search}`.replace(/^\/$/, "");
    return rest || url.hostname.replace(/^www\./, "");
  } catch {
    return origin;
  }
}

function originLabel(origin) {
  try {
    const url = new URL(origin);
    return url.hostname.replace(/^www\./, "");
  } catch {
    // A path, or something that is not a URL at all. Keep the last segment, which is the part a
    // person recognises, and never more than the slot can hold without a glyph.
    const tail = origin.split("/").filter(Boolean).pop() || origin;
    return tail.length > 38 ? tail.slice(0, 38) : tail;
  }
}


function nodeMetaLine(node) {
  const meta = elt("div", "node-meta");
  const bits = [];
  // **Whenever the HEADLINE is not already the URL.** The condition was `&& node.title`, which is
  // only true after distillation - and distillation is manual by default, so the default state of
  // a captured page was a row reading `localtest.me` with an EMPTY meta line and no tooltip: three
  // captures from one host, three identical rows, the URL nowhere on the surface. The earlier fix
  // for that reached HTML pages through `preview.title` and left PDFs, text URLs and any page
  // without `og:title` exactly as they were. The origin is the one thing every capture has.
  const headlineIsHost = !node.title && !(node.preview || {}).title;
  if (node.origin && !node.origin.startsWith("pasted:") && !headlineIsHost) {
    // SHOWN, never navigable (invariant 55): a captured page's URL is exactly the transport
    // invariant 1 keeps away from the model, and a reader's click is the same transport.
    //
    // COMPACTED to the host rather than truncated with an ellipsis. A meta line is a fixed slot,
    // and a tail-truncated URL is the worst of both: it costs the width anyway and the part it
    // keeps (the scheme and the domain's first few letters) is the part you already knew. The
    // whole value stays reachable as the element's title.
    const origin = elt("span", "node-origin", originLabel(node.origin));
    origin.title = node.origin;
    bits.push(origin);
  }
  // When the headline fell back to the bare host, the PATH is what tells two captures apart. Shown
  // here rather than in the title, because a title is a name and a path is a coordinate - and with
  // the full URL on `title=` either way, nothing is hidden.
  if (node.origin && !node.origin.startsWith("pasted:") && headlineIsHost) {
    // **Only when it says something the headline did not.** An UPLOADED file's origin is its bare
    // filename, so `originLabel` (the headline's fallback) and `originPath` both return the whole
    // string and the row printed `note.txt` over `note.txt` - one fact twice, on the default state
    // of every uploaded and dropped file, since distillation is off by default (invariant 80). A
    // web capture is the case this branch was written for and still gets host + path, two facts.
    const path = originPath(node.origin);
    if (path && path !== nodeHeadline(node)) {
      const span = elt("span", "node-origin", path);
      span.title = node.origin;
      bits.push(span);
    }
  }
  // A length only when it is a fact about the DOCUMENT rather than about the sentence you can
  // already see. Below this it is noise dressed as data.
  if (node.chars > 2000) {
    // Chinese counts in 萬 above ten thousand; `約 20 千字` is not a thing anyone writes. Invariant
    // 39's own point, one level down: naming a language does not buy its idiom, so the SIZE of the
    // number picks the unit rather than one format being translated.
    const size = node.chars >= 10000
      ? t("horizon.sizeWan", `${Math.round(node.chars / 1000)}k chars`, {
          n: (node.chars / 10000).toFixed(1).replace(/\.0$/, ""),
        })
      : t("horizon.sizeK", `${Math.round(node.chars / 1000)}k chars`, {
          n: Math.round(node.chars / 1000),
        });
    bits.push(elt("span", null, size));
  }
  // Tags are on the chips row under the summary now (`nodeChips`), beside the orbits it is in.
  // Too big to ASK about. The capture is fine and the node is real; what it cannot do is be
  // promoted into an orbit and then answered from, because the assembled corpus has a hard
  // ceiling (invariant 8) six times below the upload cap. Said on the row, before the filing, as a
  // state rather than a filter - the same `.node-flag` the failure uses.
  if (horizonState.corpusCharCap && node.chars > horizonState.corpusCharCap) {
    bits.push(elt("span", "node-flag", t("horizon.tooBig", "too large to ask about")));
  }
  // A capture the reader STOPPED is not a failure, and the backend already distinguishes them: it
  // stores the reason "stopped before it was read". The row drew both as a red dot over
  // "could not read it", so a batch the reader cancelled looked like a batch that broke.
  if (node.state === "failed" && /stopped before it was read/.test(node.error || "")) {
    bits.push(elt("span", "node-flag node-flag-quiet", t("horizon.wasStopped", "you stopped this")));
  } else if (node.state === "failed" && node.error) {
    // `.node-flag`, NOT `.node-tag`. It was pixel-identical to the tag BUTTONS beside it - same
    // pill, same border, same size - so it read as a filter you could click, and an independent
    // reviewer clicked it expecting one. A state is not a filter; it gets the failure colour and no
    // pill, so the two cannot be confused before the click rather than after it.
    bits.push(elt("span", "node-flag", t("horizon.failed", "could not read it")));
  }
  bits.forEach((bit, index) => {
    if (index) meta.appendChild(elt("span", "sep", "·"));
    meta.appendChild(bit);
  });
  return meta;
}

function renderNode(node, { isNew = false } = {}) {
  const row = elt("div", "node");
  row.dataset.state = node.state;
  row.dataset.nodeId = node.id;
  row.setAttribute("role", "listitem");
  if (isNew) row.classList.add("is-new");
  // A row the reader opened STAYS open across a repaint. `horizonState.open` was written and never
  // read, so while a PDF parsed, the 900ms poll snapped every open row shut about once a second.
  // Same family as "a repaint may not delete a run": the reader's state is not the server's to
  // discard.
  const wasOpen = horizonState.open.has(node.id);
  if (wasOpen) row.classList.add("is-open");

  // The history: when, to the minute, in its own column beside a timeline rail.
  const time = elt("time", "node-time", clockTime(node.created_at));
  time.dateTime = new Date(node.created_at * 1000).toISOString();
  time.title = new Date(node.created_at * 1000).toLocaleString(uiLang());
  row.appendChild(time);

  const col = elt("div", "node-col");

  // **The disclosure is the DOT, and the prose is selectable.**
  //
  // Three shapes, each wrong in a way the next review found. It began as `<button class="node-head">`
  // wrapping an `<h3>` and four tag buttons - eight nested buttons on first paint, invalid on both
  // counts. That became a stretched overlay covering the head, which fixed the markup and made the
  // one sentence this product exists to hand back to you impossible to select: a 195px drag across
  // the summary returned an empty selection and toggled the row instead.
  //
  // So the row's left gutter - which already carried a state dot - IS the control. A real button,
  // one per row, keyboard-operable, wrapping the dot it already had. The head stays clickable for
  // convenience, but that click YIELDS to a selection: a drag that selected something was never a
  // press. `getSelection`, not a pixel threshold - it answers the actual question.
  const open = elt("button", "node-open");
  open.type = "button";
  open.setAttribute("aria-expanded", String(wasOpen));
  open.appendChild(elt("span", "node-dot"));
  open.addEventListener("click", () => toggleNode(node, row));
  row.appendChild(open);

  const head = elt("div", "node-head");
  const headline = nodeHeadline(node);
  const prose = nodeProse(node);
  open.setAttribute("aria-label", headline || prose || t("horizon.openNode", "Open this item"));

  if (headline) head.appendChild(elt("h3", "node-title", headline));
  if (prose) head.appendChild(elt("p", "node-summary", prose));
  head.appendChild(nodeMetaLine(node));
  const chips = nodeChips(node);
  if (chips) head.appendChild(chips);
  head.addEventListener("click", (event) => {
    if (event.target.closest("button, a")) return;
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) return;
    toggleNode(node, row);
  });
  col.appendChild(head);

  const body = elt("div", "node-body");
  const inner = elt("div", "node-body-inner");
  body.appendChild(inner);
  col.appendChild(body);
  // Refill it rather than making the reader wait for the same two requests again.
  if (wasOpen) fillNodeBody(node, row, inner);

  row.appendChild(col);
  return row;
}

//: A commonplace book has datelines, and so does this. They do three jobs at once: they give the
//: page the anchor it had none of when every row carried the same weight, they group the stream the
//: way a person actually looks for something ("it was that afternoon"), and they replace the
//: per-row timestamp that would otherwise have to sit in the meta line.
//:
//: They are also what let the character count go. `189 字` on a three-sentence note was noise: it
//: is not how anyone finds anything. A size only appears now when it is genuinely a fact about the
//: thing rather than about the sentence, which is why the threshold is a document, not a note.
//: "14:32", in the reader's own locale, for the history's time column.
function clockTime(epochSeconds) {
  // 24-hour: "上午 03:55" took two lines of a narrow column to say what "03:55" says in one.
  return new Date(epochSeconds * 1000).toLocaleTimeString(uiLang(), { hour: "2-digit", minute: "2-digit", hour12: false });
}

//: "9/25 14:32", for a step on a capture's trail.
function stampTime(epochSeconds) {
  const when = new Date(epochSeconds * 1000);
  return `${when.toLocaleDateString(uiLang(), { month: "numeric", day: "numeric" })} ${clockTime(epochSeconds)}`;
}

//: Where it is and what it is about, under the summary: each orbit it is in, then up to three tags.
//: A tag narrows the list to it; an orbit opens the orbit.
function nodeChips(node) {
  const orbits = node.orbits || [];
  const tags = node.tags || [];
  if (!orbits.length && !tags.length) return null;
  const row = elt("div", "node-chips");
  const orbitBySlug = new Map(starMap.orbits.map((o) => [o.slug, o]));
  orbits.forEach((m) => {
    const name = orbitTitles.get(m.orbit_id) || t("suggest.anOrbit", "an orbit");
    const orbit = orbitBySlug.get(m.orbit_id);
    const chip = elt("button", "node-orbit", name);
    chip.type = "button";
    chip.title = t("horizon.filedAt", `Filed ${stampTime(m.promoted_at)}`, { when: stampTime(m.promoted_at) });
    chip.addEventListener("click", (event) => {
      event.stopPropagation();
      if (orbit) void enterOrbit(orbit);
    });
    row.appendChild(chip);
  });
  tags.slice(0, 3).forEach((tag) => {
    const chip = elt("button", "node-tag", `#${tag}`);
    chip.type = "button";
    chip.addEventListener("click", (event) => {
      event.stopPropagation();
      setHorizonQuery(tag);
    });
    row.appendChild(chip);
  });
  if (tags.length > 3) row.appendChild(elt("span", "node-more", `+${tags.length - 3}`));
  return row;
}

//: A capture's journey, oldest first: captured, filed into each orbit, and summarised.
function nodeTrail(node, detail) {
  const steps = [[node.created_at, t("horizon.trailCaptured", "Captured")]];
  (detail.orbits || []).forEach((m) => {
    const name = orbitTitles.get(m.orbit_id) || t("suggest.anOrbit", "an orbit");
    steps.push([m.promoted_at, t("horizon.trailFiled", `Filed into ${name}`, { name })]);
  });
  const current = detail.node || node;
  if (current.state === "ready") steps.push([current.updated_at, t("horizon.trailSummarised", "Summarised")]);
  steps.sort((a, b) => a[0] - b[0]);
  const list = elt("ol", "node-trail");
  steps.forEach(([when, what]) => {
    const item = elt("li", "node-trail-step");
    item.appendChild(elt("time", "node-trail-time", stampTime(when)));
    item.appendChild(elt("span", "node-trail-what", what));
    list.appendChild(item);
  });
  return list;
}

//: The full text in the reading window the orbit's sources use, rather than poured into the list.
async function showNodeReader(node) {
  const overlay = document.getElementById("source-viewer-overlay");
  const title = document.getElementById("source-viewer-title");
  const body = document.getElementById("source-viewer-body");
  if (overlay.hidden) openModal(overlay);
  title.textContent = nodeHeadline(node) || originLabel(node.origin);
  body.textContent = t("cite.loading", "Loading…");
  try {
    const got = await api(`/horizon/${encodeURIComponent(node.id)}/source`);
    body.textContent = "";
    (got.source.blocks || []).forEach((block) => {
      const section = elt("div", "source-block");
      section.appendChild(elt("div", "source-block-locator", block.locator));
      section.appendChild(renderTextWithOptionalHighlight(block.text, null));
      body.appendChild(section);
    });
  } catch (err) {
    body.textContent = "";
    body.appendChild(failureBlock(t("sources.viewFailed", "Could not open this source"), err.message));
  }
}

function dayLabel(epochSeconds) {
  const when = new Date(epochSeconds * 1000);
  const midnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((midnight(new Date()) - midnight(when)) / 86400000);
  // The YEAR once the date leaves the current one, and the date itself always: a history is read
  // by date, and "2 days ago" alone had to be counted back from today.
  const sameYear = when.getFullYear() === new Date().getFullYear();
  const date = when.toLocaleDateString(uiLang(), {
    year: sameYear ? undefined : "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
  });
  if (days === 0) return `${t("horizon.today", "Today")} \u00b7 ${date}`;
  if (days === 1) return `${t("horizon.yesterday", "Yesterday")} \u00b7 ${date}`;
  if (days < 7) return `${t("horizon.daysAgo", `${days} days ago`, { n: days })} \u00b7 ${date}`;
  return date;
}

function updateStreamFoot() {
  const more = horizonEl("stream-more");
  more.hidden = horizonState.nodes.length >= horizonState.total;
  horizonEl("stream-foot").hidden = more.hidden;

  // Invariant 80 rendered: the count is stated and the action NAMES what it will cost, both before
  // anything is spent.
  //
  // **"Summarise them" was the wrong label, and it took an independent review to see it.** The line
  // read "324 not summarised yet" beside a button reading "Summarise them", and pressing it
  // summarised FIFTY - the real number appearing only afterwards, in the progress strip. Naming
  // 324 and spending on 50 is the same defect as naming nothing: invariant 80 is that the spend is
  // knowable BEFORE the press, and "them" was never a number. The button names the batch it will
  // actually run, and the count beside it stays the true backlog, so a reader with 324 pending can
  // see at a glance that this press is a bite out of it rather than all of it.
  const note = horizonEl("pending-note");
  const running = Boolean(horizonState.distil && horizonState.distil.running);
  // Hidden WHILE a pass runs, because the strip above is the live truth and the two disagreed in a
  // way that read as a bug: the strip said "0 / 2" while the line under it said "1 not summarised
  // yet". Both were true - a node in `distilling` has left `ready_undistilled` - and adjacent they
  // looked like a contradiction.
  note.hidden = horizonState.undistilled === 0 || running;
  if (!note.hidden) {
    horizonEl("pending-count").textContent = t(
      "horizon.pendingSummaries", `${horizonState.undistilled} not summarised yet`, {
        n: horizonState.undistilled,
      }
    );
    horizonEl("distil-btn").textContent = t("horizon.distil", `Summarise ${distilBatchSize()}`, {
      n: distilBatchSize(),
    });
    // A long capture is an RLM run, several calls rather than one, and the note says so before the
    // press (invariant 80). Fetched, not guessed: only the server knows which captures are long.
    void distilEstimate(null).then((est) => {
      if (!est || note.hidden) return;
      const base = t("horizon.pendingSummaries", `${horizonState.undistilled} not summarised yet`,
        { n: horizonState.undistilled });
      const extra = est.long
        ? t("horizon.longNote", `${est.long} are long and take several model calls each.`, { n: est.long })
        : "";
      const zh = uiLang().startsWith("zh");
      horizonEl("pending-count").textContent = `${base}${zh ? "\u3002" : ". "}${[extra,
        t("horizon.alignNote", "A pass may end by matching new entities, one more run.")]
        .filter(Boolean).join(zh ? "" : " ")}`;
    });
  }
  renderDistilError();
}

//: The server's count of what summarising would cost, cached briefly per scope so a repaint does
//: not refetch it. `null` scope is the whole Horizon.
const distilEstimates = new Map();

async function distilEstimate(slug) {
  const key = slug || "";
  const hit = distilEstimates.get(key);
  if (hit && Date.now() - hit.at < 5000) return hit.value;
  let value = null;
  try {
    value = await api(`/horizon/distil/estimate${slug ? `?orbit=${encodeURIComponent(slug)}` : ""}`);
  } catch {
    value = null;
  }
  distilEstimates.set(key, { at: Date.now(), value });
  return value;
}

//: ONE definition of how many this press will pay for, read by the label and by the request. Two
//: numbers that have to agree is how the label came to promise 324 and the request to send 50.
const DISTIL_BATCH_CAP = 50;

function distilBatchSize() {
  return Math.min(horizonState.undistilled, DISTIL_BATCH_CAP);
}

//: The summary pass's failure, shown where the reader pressed the button rather than in a log.
//:
//: Until an independent review pressed it on a machine with no credentials, this had nowhere to go
//: at all: the strip counted to 2 / 2 and vanished, the nodes were untouched, and the only record
//: was `ValueError: No LM is loaded` in the server's stdout. The message is shown VERBATIM for the
//: reason the chat surface already shows its own: this is a single-operator, BYOK tool, and
//: "PN_MAIN_MODEL is not set" is the sentence that tells them what to do. "Something went wrong"
//: would be shorter and useless.
function renderDistilError() {
  const errline = horizonEl("distil-error");
  const distil = horizonState.distil || {};
  const failed = Number(distil.failed || 0);
  const alignError = (horizonState.align && horizonState.align.error) || "";
  if ((!failed && !distil.error && !alignError) || distil.running) {
    errline.hidden = true;
    errline.textContent = "";
    return;
  }
  errline.hidden = false;
  errline.textContent = "";
  if (!failed && !distil.error) {
    // Only alignment failed: the summaries are saved, and the line says what did not happen. It
    // takes the same dismiss below, which clears both on the server.
    errline.appendChild(elt("span", "distil-error-count",
      t("horizon.alignFailed", "New entities were not matched")));
    errline.appendChild(elt("span", "distil-error-why", readableError(alignError)));
  }
  // TWO different sentences, because they are two different facts. A pass that ran and lost some
  // nodes has a COUNT; a pass that could not start has none, and saying "1 could not be summarised"
  // when nothing was attempted is the status line claiming something the page is not doing.
  if (failed || distil.error) {
    const lead = failed
      ? t("horizon.distilFailedCount", `${failed} could not be summarised`, { n: failed })
      : t("horizon.distilNoStart", "The summary pass could not start");
    errline.appendChild(elt("span", "distil-error-count", lead));
    if (distil.error) errline.appendChild(elt("span", "distil-error-why", readableError(distil.error)));
  }
  //: **A dismiss, because this was otherwise IMMORTAL.** The error is process state on the server
  //: and only the START of the next pass ever cleared it, so one failed batch installed this
  //: banner above the stream for the life of the server — for every visitor, not just the one who
  //: pressed the button. On the commonest first-run condition (BYOK, no model configured yet) that
  //: is a permanent error on the default screen with no way out. It clears on the SERVER, because
  //: a dismiss the page kept to itself would come back on the next reload.
  const dismiss = elt("button", "distil-error-dismiss", "\u2715");
  dismiss.type = "button";
  dismiss.setAttribute("aria-label", t("horizon.distilDismiss", "Dismiss"));
  dismiss.dataset.tip = t("horizon.distilDismiss", "Dismiss");
  dismiss.addEventListener("click", async () => {
    dismiss.disabled = true;
    try {
      const reply = await api("/horizon/distil/dismiss", { method: "POST" });
      horizonState.distil = reply;
      horizonState.align = { running: false, error: "" };
    } catch {
      // A pass started in another tab owns these fields (409). Leave the line alone and let the
      // next poll say what is true now.
      dismiss.disabled = false;
      return;
    }
    renderDistilError();
  });
  errline.appendChild(dismiss);
}

function renderStream({ append = false, newIds = new Set() } = {}) {
  const stream = horizonEl("stream");
  if (!append) stream.textContent = "";
  const from = append ? Number(stream.dataset.rendered || 0) : 0;
  let lastDay = append ? stream.dataset.lastDay || "" : "";
  for (const node of horizonState.nodes.slice(from)) {
    const day = dayLabel(node.created_at);
    if (day !== lastDay) {
      const line = elt("div", "dateline");
      line.appendChild(elt("span", "dateline-label", day));
      stream.appendChild(line);
      lastDay = day;
    }
    stream.appendChild(renderNode(node, { isNew: newIds.has(node.id) }));
  }
  stream.dataset.rendered = String(horizonState.nodes.length);
  stream.dataset.lastDay = lastDay;
  const empty = horizonEl("stream-empty");
  empty.hidden = horizonState.nodes.length > 0;
  empty.classList.remove("is-error");
  // "Nothing here yet" and "nothing matched what you typed" are different facts, and showing the
  // first while a query is active would tell the reader their Horizon is empty when it is not.
  if (!empty.hidden) {
    empty.textContent = horizonState.query
      ? t("horizon.noMatch", `Nothing matched \u201c${horizonState.query}\u201d.`, { q: horizonState.query })
      : t("horizon.empty", "Nothing has landed yet. Paste a link above and Penny will keep it.");
  }
  // The first-run explanation belongs to an EMPTY Horizon, not to a search that found nothing: a
  // reader who just typed a query does not need to be told what a facet is.
  const firstRun = empty.hidden === false && !horizonState.query;
  horizonEl("first-run").hidden = !firstRun;
  //: **And nor does Find belong on a Horizon with nothing in it.** "Find something you kept" over
  //: an empty river offers a search of nothing, next to a first-run note explaining that this is
  //: where things will go - the one screen where the secondary act is not merely quiet but
  //: impossible. It comes back the moment anything lands, and a query cannot be active here (that
  //: is what `firstRun` excludes), so nothing a reader typed is ever taken away.
  horizonEl("find").hidden = firstRun;

  updateStreamFoot();

  // The swallow plays once. Left on, a later repaint would replay it and the surface would twitch
  // every time anything refreshed.
  requestAnimationFrame(() => {
    stream.querySelectorAll(".node.is-new").forEach((row) => {
      row.addEventListener("animationend", () => row.classList.remove("is-new"), { once: true });
    });
  });
}

// --- loading ------------------------------------------------------------------------------------

async function refreshHorizon({ reset = false, newIds = new Set() } = {}) {
  if (reset) horizonState.offset = 0;
  // The list names the orbits each capture is in, and only the map used to load their titles.
  await ensureOrbitTitles();
  // The list's refresh is also the map's: a capture landing, a node finishing its parse or a pass
  // summarising something all change what the map draws. At most every few seconds, because this
  // runs on the Horizon's busy poll.
  if (viewIsHorizon() && viewMode("horizon") === "map" && Date.now() - (starMap.lastRender || 0) > 3000) {
    void renderStarMap();
  }
  if (viewIsHorizon()) void refreshSuggestions();
  let data;
  try {
    data = await api(
      `/horizon?limit=${HORIZON_PAGE}&offset=${reset ? 0 : horizonState.offset}${horizonQuery()}`
    );
  } catch (err) {
    const empty = horizonEl("stream-empty");
    empty.hidden = false;
    empty.classList.add("is-error");
    empty.textContent = t("horizon.loadFailed", `${readableError(err.message)}`, {
      message: readableError(err.message),
    });
    return;
  }
  horizonState.nodes = reset ? data.nodes : horizonState.nodes.concat(data.nodes);
  horizonState.offset = horizonState.nodes.length;
  horizonState.total = data.total;
  horizonState.undistilled = data.undistilled;
  if (data.corpus_char_cap) horizonState.corpusCharCap = data.corpus_char_cap;
  renderStream({ newIds });
  renderFacets();
  // **Ask the SERVER, not the page.** Starting the poll only when a LISTED node looks busy was
  // wrong twice over. A summary pass claims exactly one node at a time, so after a reload whether
  // the strip appeared was a coin flip on that node being in the first twenty-five - measured with
  // the server reporting `running: true, done: 8/20` and the strip hidden for eight straight
  // samples. And an UPLOAD lands `ready_undistilled`, which is not a busy state, so an auto pass it
  // triggered was invisible for all twenty calls. One `pollIntake()` answers the actual question
  // ("is anything running?") and starts the interval itself when the answer is yes; when it is no,
  // `pollIntake` stops it again, so this costs one request.
  if (horizonState.nodes.some((node) => HORIZON_BUSY_STATES.has(node.state))) startHorizonPolling();
  else void pollIntake();
}

// --- the running strip (invariants 47 and 60) -----------------------------------------------------

async function pollIntake() {
  let status;
  try {
    status = await api("/horizon/status");
  } catch {
    stopHorizonPolling();
    return;
  }
  const strip = horizonEl("intake-strip");
  const distil = status.distil || { running: false, done: 0, total: 0, failed: 0, error: "" };
  horizonState.distil = distil;
  horizonState.align = status.align || { running: false, error: "" };
  const parsing = Boolean(status.current) || status.pending > 0;
  const busy = parsing || distil.running;
  strip.hidden = !busy;
  if (busy) {
    // TWO things can be running and they are reported separately, because they fail, cost and stop
    // differently. Parsing wins the label when both are true: it is the one the reader just caused.
    if (parsing) {
      const current = horizonState.nodes.find((node) => node.id === status.current);
      // It says only what the server reported. `current` may be a node this page has not loaded, in
      // which case the honest line is "something", not a guessed title (invariant 60).
      horizonEl("intake-what").textContent = status.current
        ? t("horizon.reading", "Reading {what}", { what: current ? nodeHeadline(current) : "…" })
        : t("horizon.waiting", "Waiting");
      horizonEl("intake-pending").textContent = status.pending
        ? t("horizon.pending", `${status.pending} waiting`, { n: status.pending })
        : "";
    } else {
      horizonEl("intake-what").textContent = horizonState.align && horizonState.align.running
        ? t("map.aligning", "Matching new entities to known ones")
        : t("horizon.summarising", "Summarising");
      // Failures are counted IN THE STRIP too, not only after the pass. A pass where every call is
      // failing should look different at node three from one that is working, rather than reading
      // as progress right up until it disappears.
      const progress = t(
        "horizon.progress", `${distil.done} / ${distil.total}`, { done: distil.done, total: distil.total }
      );
      horizonEl("intake-pending").textContent = distil.failed
        ? `${progress} · ${t("horizon.distilFailedCount", `${distil.failed} failed`, { n: distil.failed })}`
        : progress;
    }
  }
  // PATCH, do not rebuild. `refreshHorizon({reset: true})` here emptied the stream and re-rendered
  // every row at 1.1Hz: open rows snapped shut, any text selection died, and a reader who had
  // pressed "Older" was thrown back to the first page. It also refetched `/orbits` at the same
  // rate. Only the rows whose state actually moved are touched now.
  await patchChangedNodes();
  // The foot carries the pass's outcome, so it is refreshed on every poll rather than only when the
  // stream's contents change - a pass that fails changes no row at all.
  updateStreamFoot();
  const stillWorking = busy || horizonState.nodes.some((node) => HORIZON_BUSY_STATES.has(node.state));
  // Started HERE as well as stopped here, so the single boot/refresh probe above can turn into a
  // running poll without every caller having to remember to.
  if (stillWorking) startHorizonPolling();
  else stopHorizonPolling();
}

//: Re-reads the page the reader is actually looking at and swaps ONLY the rows that changed. A
//: node's identity is its id and its visible state is `state` plus the distilled fields, so a row
//: whose serialisation is unchanged is left alone - which is what keeps an open row open, a
//: selection alive, and the scroll position where it was.
async function patchChangedNodes() {
  let data;
  try {
    data = await api(
      `/horizon?limit=${Math.max(horizonState.nodes.length, HORIZON_PAGE)}&offset=0${horizonQuery()}`
    );
  } catch {
    return;
  }
  const stream = horizonEl("stream");
  const byId = new Map(horizonState.nodes.map((node) => [node.id, node]));
  let structural = data.nodes.length !== horizonState.nodes.length;
  for (const fresh of data.nodes) {
    const known = byId.get(fresh.id);
    if (!known) {
      structural = true;
      continue;
    }
    if (JSON.stringify(known) === JSON.stringify(fresh)) continue;
    const row = stream.querySelector(`[data-node-id="${CSS.escape(fresh.id)}"]`);
    if (!row) {
      structural = true;
      continue;
    }
    row.replaceWith(renderNode(fresh));
  }
  horizonState.nodes = data.nodes;
  horizonState.total = data.total;
  horizonState.undistilled = data.undistilled;
  if (data.corpus_char_cap) horizonState.corpusCharCap = data.corpus_char_cap;
  updateStreamFoot();
  // A node appearing or disappearing changes the DATELINE grouping, which no per-row swap can fix.
  if (structural) renderStream({});
}

function startHorizonPolling() {
  if (horizonState.pollTimer) return;
  horizonState.pollTimer = setInterval(pollIntake, 900);
}

function stopHorizonPolling() {
  if (!horizonState.pollTimer) return;
  clearInterval(horizonState.pollTimer);
  horizonState.pollTimer = null;
  const strip = horizonEl("intake-strip");
  if (strip) strip.hidden = true;
}

// --- expand in place ------------------------------------------------------------------------------

async function toggleNode(node, row) {
  // `.node-open`, not `.node-head`: the head is a plain div now and `aria-expanded` belongs on the
  // control, not on its container. Left on the div it would have been announced by nothing.
  const open = row.querySelector(".node-open");
  const inner = row.querySelector(".node-body-inner");
  const wasOpen = row.classList.contains("is-open");
  row.classList.toggle("is-open", !wasOpen);
  open.setAttribute("aria-expanded", String(!wasOpen));
  if (wasOpen) {
    horizonState.open.delete(node.id);
    return;
  }
  horizonState.open.add(node.id);
  if (inner.childElementCount) return;
  await fillNodeBody(node, row, inner);
}

async function fillNodeBody(node, row, inner) {
  if (inner.childElementCount) return;
  inner.appendChild(elt("p", "node-full", t("horizon.loading", "Loading…")));

  let detail;
  try {
    detail = await api(`/horizon/${encodeURIComponent(node.id)}`);
  } catch (err) {
    inner.textContent = "";
    inner.appendChild(nodeErrorBlock(t("horizon.openFailed", `${err.message}`, {
      message: err.message,
    })));
    return;
  }

  // A node that FAILED to parse has no stored text, so asking for it returns a 404 that names an
  // internal id and the wrong cause. The node's own `error` says what actually happened - a refused
  // address, an unreadable PDF - and it was being thrown away. And because the old code returned
  // from the catch, a failed node had no actions at all: no Forget, no File into. It was stuck.
  inner.textContent = "";
  // A node still being read has no blocks yet, and asking for them returns a 404 naming an internal
  // id - which the row then showed under the heading "Could not read this", while it was being
  // read. Both halves wrong: the cause and the claim. Only `failed` avoided the fetch; every other
  // non-ready state fell through to it.
  if (node.state === "queued" || node.state === "parsing") {
    inner.appendChild(elt("p", "hint", t("horizon.stillReading", "Still reading this one\u2026")));
    inner.appendChild(await nodeActions(node, { orbits: [] }));
    return;
  }
  if (node.state === "failed") {
    inner.appendChild(
      nodeErrorBlock(node.error || t("horizon.failed", "could not read it"))
    );
  } else {
    const entities = (detail.node && detail.node.entities) || node.entities || [];
    if (entities.length) {
      inner.appendChild(elt("h4", "node-section", t("map.sectionNames", "What it talks about")));
      const names = elt("div", "node-entities");
      entities.forEach((name) => names.appendChild(elt("span", "node-entity", name)));
      inner.appendChild(names);
    }
  }
  // Its journey, and the full text one press away in the reading window rather than poured into
  // the row: a long document inside the list pushed every later capture off the screen.
  inner.appendChild(elt("h4", "node-section", t("horizon.trail", "Trail")));
  inner.appendChild(nodeTrail(node, detail));
  inner.appendChild(await nodeActions(node, detail));
}

async function nodeActions(node, detail) {
  const actions = elt("div", "node-actions");
  // A left GROUP, so the destructive action stays right even when the row wraps.
  const main = elt("div", "node-actions-main");
  if (node.state === "failed") {
    // Re-submitting the same origin is already the retry path (`intake.submit` resets a `failed`
    // node to `queued`), so this needs no new endpoint - only a way to ask for it.
    //: FIRST in the row and the SAME SIZE as Forget: it was a full `.btn` after the "nothing to
    //: file" note, so the row read as a sentence, then a big button, then a small one, and the
    //: action that recovers the capture sat in the middle of it.
    const retry = elt("button", "node-retry", t("horizon.retry", "Try again"));
    retry.type = "button";
    retry.addEventListener("click", async () => {
      retry.disabled = true;
      await captureValue(node.origin);
    });
    main.appendChild(retry);
  }

  let books = { orbits: [] };
  try {
    books = await api("/orbits");
  } catch {
    // A picker with no orbits is still usable: the field below accepts a new name.
  }
  // `facetLabels`, not `book.title || book.id`. This is the one control in the product where the
  // reader has to CHOOSE an orbit, and it was printing the raw handle - invariant 37's violation,
  // one function away from the tripwire written for it, in the worst possible place.
  const bookLabels = facetLabels(books.orbits || []);

  // **A node with no blocks cannot be filed, so it is not offered.** `promote_node` requires the
  // blocks file; a `failed`, `queued` or `parsing` node has none, and choosing an orbit returned
  // `400 no such node, or its blocks are missing` for a node visibly on screen. A control whose
  // only possible outcome contradicts what the reader can see is the "no UI control that lies about
  // what the API does" rule, and the state is knowable here without asking.
  if (node.state === "ready" || node.state === "ready_undistilled") {
    const picker = elt("select", "file-into");
    picker.setAttribute("aria-label", t("horizon.fileInto", "File into an orbit"));
    const blank = elt("option", null, t("horizon.fileIntoPlaceholder", "File into\u2026"));
    blank.value = "";
    picker.appendChild(blank);
    for (const book of books.orbits || []) {
      const option = elt("option", null, bookLabels.get(book.id));
      option.value = book.id;
      picker.appendChild(option);
    }
    const fresh = elt("option", null, t("horizon.newOrbit", "New orbit\u2026"));
    fresh.value = "__new__";
    picker.appendChild(fresh);
    picker.addEventListener("change", () => promoteNode(node, picker));
    main.appendChild(picker);
    const read = elt("button", "btn", t("map.readInList", "Read it"));
    read.type = "button";
    read.addEventListener("click", () => void showNodeReader(node));
    main.appendChild(read);
  } else {
    // Say WHY, rather than leaving a gap where a control was. A failed node still offers Try again
    // and Forget; this is the one action that is genuinely unavailable.
    main.appendChild(
      elt("span", "node-filed", t("horizon.notFilable", "Nothing to file yet: it has no text."))
    );
  }

  // Same rule as the picker: a membership names an orbit, and an orbit is named by its LABEL.
  // A membership whose orbit has since been deleted says so rather than falling back to the id.
  //: **Keyed on the SLUG, because that is what a membership stores.** `promote_node` writes
  //: `slug(orbit_id)` — deliberately, since the slug is what identifies the orbit FILE — and
  //: `facetLabels` keys on the id, so the two never met. Every node filed into an orbit whose id
  //: differs from its slug read "In a deleted orbit" while that orbit was listed, live, in
  //: this row's own picker: `--orbit "reading list"` (slug `reading-list`), and every CJK name,
  //: which invariant 10's `nb-<hash>` fallback exists to make possible. A false statement about the
  //: reader's own data whose next move is to re-file something already filed.
  const bySlug = new Map(
    (books.orbits || []).map((b) => [b.slug || b.id, bookLabels.get(b.id)])
  );
  const filed = (detail.orbits || []).map(
    (m) =>
      bySlug.get(m.orbit_id) ||
      bookLabels.get(m.orbit_id) ||
      t("horizon.filedInGone", "a deleted orbit")
  );
  // Where it is filed shows on the card's chips and in the trail above, not a third time here.
  void filed;

  actions.appendChild(main);

  const remove = elt("button", "node-danger", t("horizon.forget", "Forget"));
  remove.type = "button";
  remove.addEventListener("click", () => forgetNode(node));
  actions.appendChild(remove);
  return actions;
}

async function promoteNode(node, picker) {
  let orbitId = picker.value;
  if (!orbitId) return;
  //: **Whether this id is NEW is something only this side knows**, and the server now asks. The
  //: picker's other options come from the orbit list fetched when the Horizon rendered, so one can
  //: name an orbit that has since been deleted — and promoting through a stale option used to
  //: RE-CREATE it, same handle, holding one source and none of its title, sources, notes or turns.
  const minted = orbitId === "__new__";
  if (minted) {
    // The id is a HANDLE and the UI mints it (invariant 37): a reader is never asked to invent one.
    orbitId = `nb-${crypto.randomUUID().slice(0, 8)}`;
  }
  picker.disabled = true;
  try {
    await api(`/horizon/${encodeURIComponent(node.id)}/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ orbit_id: orbitId, create: minted }),
    });
  } catch (err) {
    notify(t("horizon.promoteFailed", `Could not file it: ${err.message}`, { message: err.message }));
    picker.disabled = false;
    picker.value = "";
    return;
  }
  picker.disabled = false;
  picker.value = "";
  await refreshHorizon({ reset: true });
}

async function forgetNode(node) {
  const ok = await confirmAction(
    t("horizon.forgetConfirm", "Forget this? Anything already filed into an orbit stays.")
  );
  if (!ok) return;
  try {
    await api(`/horizon/${encodeURIComponent(node.id)}`, { method: "DELETE" });
  } catch (err) {
    notify(t("horizon.forgetFailed", `Could not forget it: ${err.message}`, { message: err.message }));
    return;
  }
  await refreshHorizon({ reset: true });
}

// --- capture --------------------------------------------------------------------------------------

//: The send button reflects whether there is anything to send. A module function rather than a
//: closure inside `initHorizon`, because `captureValue` has to call it too - it clears the field, and
//: a clear that does not re-sync leaves a primary button promising an action on an empty field.
function syncCaptureSend() {
  const input = horizonEl("capture-input");
  const send = horizonEl("capture-send");
  if (input && send) send.disabled = !input.value.trim();
}

async function captureValue(raw) {
  const value = raw.trim();
  if (!value) return;
  // What you pasted decides what it is. One field, because deciding "is this a link or a note"
  // before you can save it is the friction this surface exists to remove.
  const looksLikeUrl = /^https?:\/\/\S+$/i.test(value);
  const payload = looksLikeUrl ? { urls: [value] } : { texts: [value] };
  const send = horizonEl("capture-send");
  send.disabled = true;
  let body;
  try {
    body = await api("/horizon", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    showCaptureError(err.message);
    // Through the SYNC, never a bare `false`. The button reflects whether there is anything to
    // send, and on the file path there never is - `captureFiles` is driven by a drop or the
    // picker, not by the textarea.
    syncCaptureSend();
    return;
  }
  showCaptureNote("");
  horizonEl("capture-input").value = "";
  // AFTER the field is cleared, and through the same sync the typing path uses. Setting
  // `disabled = false` before clearing left the button enabled over an empty field for the rest of
  // the session - a fully saturated primary that does nothing, which is the state the comment on
  // `syncSend` calls "a small lie told on first paint". The orbit's own composer gets this right
  // through `.ask-form.has-text`, so the two halves of the product disagreed.
  syncCaptureSend();
  autoGrowCapture();
  await refreshHorizon({ reset: true, newIds: new Set((body.nodes || []).map((n) => n.id)) });
  startHorizonPolling();
}

async function captureFiles(files) {
  const send = horizonEl("capture-send");
  send.disabled = true;
  const form = new FormData();
  for (const file of files) form.append("file", file);
  let body;
  try {
    body = await api("/horizon/upload", { method: "POST", body: form });
  } catch (err) {
    showCaptureError(err.message);
    // Through the SYNC, never a bare `false`. The button reflects whether there is anything to
    // send, and on the file path there never is - `captureFiles` is driven by a drop or the
    // picker, not by the textarea.
    syncCaptureSend();
    return;
  }
  // **The same defect the comment twelve lines above `captureValue` records as FIXED**, on the
  // other path. `captureFiles` set `disabled = false` over a textarea that is still empty, so after
  // any drop or file pick the send button sat fully saturated and enabled for the rest of the
  // session, doing nothing when pressed - "a small lie told on first paint", permanently.
  syncCaptureSend();
  startHorizonPolling();
  // A PARTIAL batch is the normal case for a drop: three files, one of them a `.docx` nobody has
  // taught this to read yet. The endpoint attempts every file and names the ones it refused; this
  // says so BY NAME, because "could not ingest that file" beside a stream that grew by two is a
  // sentence the reader cannot act on. It is a note, not a dialog - the successful files are
  // already on screen behind it.
  const refused = body.refused || [];
  if (refused.length) {
    showCaptureNote(
      t("horizon.someRefused", `Could not read ${refused.map((r) => r.filename).join(", ")}`, {
        names: refused.map((r) => r.filename).join("\u3001"),
      })
    );
  } else {
    showCaptureNote("");
  }
  await refreshHorizon({ reset: true, newIds: new Set((body.nodes || []).map((n) => n.id)) });
}

//: One place for "that did not work", under the capture field. `alert()` was the previous answer
//: and it is the wrong one here: a modal has to be dismissed before the reader can look at the
//: stream the message is about, and a drop that half-worked is exactly when they need to.
//: TWO functions, because two different things were being passed to one. This one takes a SENTENCE
//: this file composed (or `""` to clear) and displays it; `showCaptureError` below takes a raw
//: error and is the only thing that cleans.
function showCaptureNote(text) {
  const note = horizonEl("capture-note");
  note.textContent = text || "";
  note.hidden = !text;
}

//: **Clean, THEN wrap.** `readableError` was already being applied at the display boundary rather
//: than at each call site, which is the right place for it - but both call sites handed it
//: `收不進來：{message}`, a translated sentence with the raw error already inside. Every strip in
//: `readableError` was `^`-anchored, so cleaning the WRAPPER matched nothing at all and the note
//: printed `收不進來：422: could not ingest: PdfiumError: Failed to load document (PDFium: Data
//: format error).` The anchors are gone now, but the ordering was the actual fault: a string
//: something else has already wrapped is the wrong string to clean.
function showCaptureError(message) {
  const clean = readableError(message);
  showCaptureNote(
    clean ? t("horizon.captureFailed", `Could not capture that: ${clean}`, { message: clean }) : ""
  );
}

function autoGrowCapture() {
  const input = horizonEl("capture-input");
  input.style.height = "auto";
  input.style.height = `${input.scrollHeight}px`;
}

//: The facets. An orbit here is "one facet of yourself" (the pivot's own framing), so the rail
//: lists them by TITLE and by how much is in them. It is refreshed with the stream rather than on
//: its own timer: the only thing that changes a count is a promotion, and a promotion already
//: refreshes the stream.
//: A label has to be SHORT BY CONSTRUCTION, and a WHOLE SEGMENT is what makes it short. The rail
//: is thirteen rems wide, and `GET /orbits` offers `derived_title`, which is a whole sentence
//: cut from the first source at 60 characters. Two drafts were wrong before this one:
//:
//:   1. Rendering it raw cost the full width and told you nothing: "A note to myself about th...".
//:   2. Slicing the first three WORDS was worse, and the screenshot is why. It produced "A note to"
//:      and "Christopher Alexander, A" - labels that fit, carried no ellipsis, and so read as
//:      complete names that happened to be gibberish. An unsignalled cut is worse than a signalled
//:      one, and a cut that lands on a dangling article is worse again.
//:
//: So the cut is at the first CLAUSE boundary, which is a boundary the sentence already had:
//: "Christopher Alexander, A Pattern Language" becomes "Christopher Alexander", with no glyph and
//: nothing dangling. `fallback_title`'s own "(+2)" suffix is a boundary too, and drops out for
//: free. When the first clause is still too long there IS no boundary to use, and `.facet-name`'s
//: `text-overflow` takes it from there - an ellipsis on a DERIVED label is honest, because the
//: label is openly a fragment of something longer. The full value goes on `title=` so the fragment
//: is always resolvable without opening the orbit.
//:
//: The ladder is the title a person set, then the first clause of the derived sentence, then a
//: neutral placeholder. **The ID IS NOT ON IT**, even when a person chose it and it is short and
//: meaningful (`reading`, `work`) - which is exactly what an earlier version of this function did,
//: and what `test_the_orbit_id_never_appears_in_the_picker` caught. Invariant 37 is explicit:
//: the id is a HANDLE, and a handle is not a label. Hiding the id behind a helper would not have
//: made it a label, it would only have made the tripwire blind.
//:
//: The boundaries are a comma, a semicolon, a colon, a sentence-ending period, an em/en dash, a
//: pipe, an opening paren - and their full-width CJK counterparts, because a derived title follows
//: the source's language and a Chinese sentence breaks on U+FF0C, not on U+002C.
// Measured, not guessed: the rail is 13rem, `.facet` takes 0.55rem of padding on each side and the
// count is flex-basis auto beside it, which leaves about 26 columns of `--sans` at 0.82rem. COLUMNS
// rather than characters, because `"length"` is the wrong ruler for a label that follows the
// source's language: 24 Han characters are almost twice the width of 24 Latin ones and would sail
// past a character cap while overflowing the rail. A CJK / full-width codepoint counts as two.
const FACET_FITS = 26;
const FACET_WIDE = /[\u1100-\u115f\u2e80-\ua4cf\ua960-\ua97f\uac00-\ud7a3\uf900-\ufaff\ufe10-\ufe19\ufe30-\ufe6f\uff00-\uff60\uffe0-\uffe6]/u;

function facetWidth(text) {
  let width = 0;
  for (const ch of text) width += FACET_WIDE.test(ch) ? 2 : 1;
  return width;
}
const FACET_CLAUSE = /[,;:!?|(\u3001\uff0c\uff1b\uff1a\uff01\uff1f\uff08\u300c\u300e]|\s[\u2014\u2013]\s|\.(?:\s|$)|\u3002/u;

//: Split out of `facetLabel` because the HEADER needs the same cut without the rail's width cap.
//: The header had been rendering `derived_title` RAW - the server's 60-character slice - as the
//: largest label on the screen: "Christopher Alexander, A Pattern Language: each pattern desc",
//: ending on "desc", with no ellipsis, reading as a complete name. The comment beside it claimed it
//: used "the SAME fallback the picker row uses"; the picker row goes through `facetLabel` and shows
//: "Christopher Alexander". They disagreed, on one screen, about one orbit.
function firstClause(text) {
  return (text || "").trim().split(FACET_CLAUSE)[0].trim();
}

function facetLabel(book) {
  if (book.title) return book.title;
  const derived = (book.derived_title || "").trim();
  // A value that already fits is NOT cut. "Less, but better" is a whole title with a comma in it,
  // and cutting it to "Less" is the same unsignalled-fragment bug one size down. The clause split
  // is a remedy for not fitting, so it only runs when there is nothing to remedy otherwise.
  if (facetWidth(derived) <= FACET_FITS) return derived || t("app.untitled", "Untitled orbit");
  return firstClause(derived) || derived;
}

//: SHORTNESS is decided per orbit, above. DISTINGUISHABILITY can only be decided across the
//: whole SET, so it is a second pass, and this is the pass that was missing. The independent review
//: found three rail entries all reading "Christopher Alexander" - three orbits promoted from the
//: same book - and the picker beside them was the reason it mattered: a rail you cannot read is
//: annoying, a `<select>` you cannot read is a wrong filing.
//:
//: The rule is: as short as possible while still telling them apart. Each colliding GROUP is
//: lengthened, never the whole list, so one ambiguous pair does not make every other label longer.
//: The rungs are, in order: the clause, the whole derived sentence, then the source count, then the
//: date it last moved. Counts and dates are what the header picker already uses to separate
//: near-identical model-authored titles, so this is that answer applied one tier down.
//:
//: **The id is not a rung, and it never becomes one when the rungs run out.** Two orbits with
//: the same derived sentence, the same source count and the same modified date are indistinguishable
//: to a reader, and the honest response is to leave them indistinguishable rather than to print a
//: handle (invariant 37). `test_the_orbit_id_never_appears_in_the_picker` now slices this
//: function too.
function facetLabels(books) {
  const rungs = [
    (b) => facetLabel(b),
    (b) => (b.title ? b.title : (b.derived_title || "").trim()) || facetLabel(b),
    (b, label) =>
      `${label} · ${t("app.sourceCount", `${b.source_count} sources`, { count: b.source_count })}`,
    //: `relativeTime`, the SAME function the header picker's rows use, and not a bare
    //: `new Date(updated_at)`. Two faults in one line, and they compounded: `updated_at` is epoch
    //: SECONDS, so a `Date` built from it landed on 1970-01-22 for every orbit in the product,
    //: and a date is too coarse to separate orbits anyway - three promoted in the same minute
    //: share one. So the rung that exists BECAUSE the three above it tied printed a byte-identical
    //: false date and tied as well, which is the exact failure this ladder was written to prevent.
    //: `toLocaleDateString()` with no argument was the third: every sibling passes `uiLang()`.
    (b, label) => (b.updated_at ? `${label} · ${relativeTime(b.updated_at)}` : label),
    //: **THE TERMINAL RUNG, and the ladder needs one that cannot tie.** Every rung above reads a
    //: PROPERTY, and properties can be equal: three orbits promoted from one source in the same
    //: minute matched on all four and came out as three byte-identical rail entries - the exact
    //: failure this ladder exists to prevent, reached by running out of ladder. An ordinal is the
    //: only suffix guaranteed to differ, it is what a file manager does for the same reason, and it
    //: is not the orbit's id: invariant 37 keeps the handle off a label.
    (b, label, at) => `${label} (${at + 1})`,
  ];
  const out = new Map(books.map((b) => [b.id, rungs[0](b)]));
  for (let rung = 1; rung < rungs.length; rung += 1) {
    const groups = new Map();
    for (const b of books) {
      const key = out.get(b.id);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(b);
    }
    const tied = [...groups.values()].filter((g) => g.length > 1);
    if (!tied.length) break;
    for (const group of tied) {
      // The index WITHIN the tied group, so the terminal rung can number them 1..n. Every other
      // rung ignores it.
      group.forEach((b, at) => out.set(b.id, rungs[rung](b, out.get(b.id), at)));
    }
  }
  return out;
}

// **A workspace that was hidden is stale when it comes back.** In the desktop app the workspace is
// loaded once and then hidden and shown, not reloaded: everything captured through the island in
// between was in the Horizon and in the first orbit while this page still drew an empty stream. Its
// return (focus or visibility) is when it catches up, the Horizon and the orbit rail both.
function refreshWhenShown() {
  let last = 0;
  const catchUp = () => {
    if (document.visibilityState !== "visible" || Date.now() - last < 500) return;
    last = Date.now();
    const horizonView = document.getElementById("view-horizon");
    if (horizonView && !horizonView.hidden) refreshHorizon({ reset: false });
    renderFacets();
  };
  window.addEventListener("focus", catchUp);
  document.addEventListener("visibilitychange", catchUp);
}

refreshWhenShown();

async function renderFacets() {
  const list = horizonEl("facet-list");
  let data;
  try {
    data = await api("/orbits");
  } catch {
    list.textContent = "";
    return;
  }
  list.textContent = "";
  const labels = facetLabels(data.orbits || []);
  for (const book of data.orbits || []) {
    const item = elt("button", "facet");
    item.type = "button";
    // The handle, for `syncFacetCurrent` only — never rendered (invariant 37).
    item.dataset.orbitId = book.id;
    const label = labels.get(book.id);
    item.appendChild(elt("span", "facet-name", label));
    // A tooltip only where there is a fuller value to REVEAL. A native `title` is deliberate rather
    // than a styled one: invariant 54 is about a tooltip host that clips its own tooltip, and the
    // rail is exactly such a host (`overflow-y: auto`); the browser's own is not inside the
    // scroller.
    //
    // `book.title` only, never `derived_title`. A derived title is itself the server's 60-character
    // cut, so offering it as "the full name" showed a sentence broken mid-word ("...the reason I
    // cannot") to a reader who hovered precisely because the label looked shortened. A tooltip that
    // is also truncated is worse than none: it answers the question wrongly instead of not at all.
    // A tooltip where there is MORE to read, whether or not that more is itself complete. The rule
    // used to be "only a real title", to avoid presenting the server's 60-character cut as the full
    // name - and the result was a rail whose labels ellipsise at 154px against a 238px natural
    // width with no way to read them at all, in the one place an orbit's label IS its identity.
    // The honest middle: show whatever we have when it differs from what is drawn, and let the
    // clause cut and the ellipsis keep saying that it is a fragment.
    // MARKED if it is itself a cut. `fallback_title` caps at the same sixty characters
    // `ingest_pasted_text` does, so a derived title can be a fragment - which is why an earlier
    // rule banned it here outright, after a reviewer hovered a shortened label and got a tooltip
    // broken mid-word. Banning it left the rail's labels unreadable at 154px against a 238px
    // natural width, in the one place an orbit's label IS its identity. Show it AND say it is
    // cut: the same answer `pastedExcerpt` gives, for the same reason.
    const raw = book.title || book.derived_title || "";
    const fuller = !book.title && raw.length >= PASTED_SNIPPET_CAP - 1 ? `${raw}\u2026` : raw;
    if (fuller && fuller !== label) item.title = fuller;
    if (book.source_count) {
      item.appendChild(elt("span", "facet-count", book.source_count));
      // Unlabelled on screen is right - a column of bare integers beside a column of names reads as
      // a count without saying so. It is not right for a screen reader, which announced
      // "Christopher Alexander 2".
      item.setAttribute(
        "aria-label",
        `${label}, ${t("app.sourceCount", `${book.source_count} sources`, { count: book.source_count })}`
      );
    }
    item.addEventListener("click", async () => {
      await openOrbit(book.id);
    });
    list.appendChild(item);
  }
  syncFacetCurrent();
}

function horizonQuery() {
  return horizonState.query ? `&q=${encodeURIComponent(horizonState.query)}` : "";
}

function setHorizonQuery(text) {
  horizonState.query = text;
  const field = horizonEl("stream-search");
  field.value = text;
  horizonEl("find-clear").hidden = !text;
  refreshHorizon({ reset: true });
  // The field is where a reader looks to change or clear what they just asked for, so put the
  // caret there rather than leaving them hunting for it after a tag click.
  field.focus();
}

function initHorizon() {
  const form = horizonEl("capture-form");
  const input = horizonEl("capture-input");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    captureValue(input.value);
  });
  // The send button was never `disabled`: on an empty field it sat there as a fully saturated
  // copper block that did nothing when pressed. A control that looks primary and does nothing is a
  // small lie told on first paint, before the reader has done anything at all.
  const syncSend = syncCaptureSend;
  input.addEventListener("input", () => {
    autoGrowCapture();
    syncSend();
  });
  // Composition does not fire `input` on every platform, and a reader typing in an IME must not
  // watch the button stay dead while their sentence appears.
  input.addEventListener("compositionupdate", syncSend);
  input.addEventListener("compositionend", syncSend);
  syncSend();
  input.addEventListener("keydown", (event) => {
    // Enter captures; Shift+Enter is a newline. A capture surface whose primary key needs a
    // modifier is a surface you stop using.
    if (event.key !== "Enter" || event.shiftKey) return;
    // NEVER steal Enter mid-composition. An IME is still assembling a character, and Enter is how
    // you COMMIT a candidate - so without this, typing a thought in 注音 or 拼音 and pressing Enter
    // posts a half-formed node instead of finishing the word. This interface's own language is
    // zh-Hant, which makes it the default path rather than an edge case.
    //
    // The identical guard is at `initChatPanel`'s ask box, with the identical comment, and was
    // written for the identical reason. It did not reach here, which is the whole argument for
    // reading the code next door before writing a new surface.
    if (event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    captureValue(input.value);
  });

  // **A COUNTER, not a target check.** `dragleave` fires for every child the pointer crosses, so
  // `if (event.target === surface)` left `is-dropping` stuck whenever a drag left the window over a
  // node - which is most of the surface. The affordance is on the whole view now, because the
  // capture field is scrolled off-screen three rows into the river while the hint promises a file
  // can be dropped anywhere on the page.
  // The keyboard/touch route to the same place a drop goes. `multiple`, because the endpoint takes
  // a batch and names what it could not read (invariant 79 one layer up).
  const picker = horizonEl("capture-file");
  horizonEl("capture-pick").addEventListener("click", () => picker.click());
  picker.addEventListener("change", () => {
    if (picker.files?.length) captureFiles(picker.files);
    // Cleared so choosing the SAME file twice fires `change` both times.
    picker.value = "";
  });

  // **The WINDOW, not just the Horizon view.** The listeners were bound to `#view-horizon` only, so a
  // file dropped on the header - or anywhere in an orbit - was `defaultPrevented: false` and
  // Chrome did its default thing: replaced the app with the file, taking any unsent capture text
  // with it. The hint says "or drop one anywhere on this page" and it is now true of the page
  // rather than of one element. A drop outside the Horizon is REFUSED rather than captured: silently
  // filing something into a surface the reader is not looking at is its own surprise.
  window.addEventListener("dragover", (event) => event.preventDefault());
  window.addEventListener("drop", (event) => {
    event.preventDefault();
    // The Horizon's own handler takes a drop INSIDE `#view-horizon`. The header is a SIBLING of it, so
    // a file dropped there previously reached neither handler and did nothing at all - under a hint
    // that says "or drop one anywhere on this page". On the Horizon, anywhere means anywhere.
    if (document.body.dataset.view === "horizon") {
      if (event.target.closest("#view-horizon")) return; // already handled
      if (event.dataTransfer?.files?.length) captureFiles(event.dataTransfer.files);
      return;
    }
    //: **A drop on an open orbit means "add this source", which is what the panel 300px to the
    //: left does.** This refused and pointed the reader somewhere else — while the Sources panel's
    //: own File tab did exactly what the drop implied, through the same endpoint. Refusing an
    //: action the surface already offers is not a safety boundary, it is a dead end.
    //:
    //: One file, because `POST /orbits/{id}/sources/upload` takes one and refuses a batch with a
    //: 422 that names neither file (the Horizon's `/horizon/upload` is the batch surface). Saying so is
    //: better than sending several and reporting on one.
    if (event.dataTransfer?.files?.length) {
      void dropOntoOrbit(event.dataTransfer.files);
    }
  });

  async function dropOntoOrbit(files) {
    if (!state.orbitId) {
      notify(t("horizon.dropElsewhere", "Go to the Horizon to keep a file."), { tone: "info" });
      return;
    }
    if (files.length > 1) {
      notify(
        t("sources.oneFileOnly", "One file at a time here. Drop the rest on the Horizon."),
        { tone: "info" }
      );
      return;
    }
    const form = new FormData();
    form.append("file", files[0]);
    try {
      // No `headers`: the browser sets its own multipart boundary, which a manual Content-Type
      // would break. Same call the File tab makes.
      const orbit = await api(
        `/orbits/${encodeURIComponent(state.orbitId)}/sources/upload`,
        { method: "POST", body: form }
      );
      state.sources = orbit.sources;
      state.overview = orbit.overview || null;
      state.podcast = orbit.podcast || null;
      store.emit("sources:changed", { sources: state.sources });
    } catch (err) {
      notify(readableError(err.message), { tone: "error" });
    }
  }

  const surface = horizonEl("view-horizon");
  let dragDepth = 0;
  const setDropping = (on) => surface.classList.toggle("is-dropping", on);
  surface.addEventListener("dragenter", (event) => {
    event.preventDefault();
    dragDepth += 1;
    setDropping(true);
  });
  surface.addEventListener("dragover", (event) => {
    event.preventDefault();
    setDropping(true);
  });
  surface.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) setDropping(false);
  });
  surface.addEventListener("drop", (event) => {
    event.preventDefault();
    dragDepth = 0;
    setDropping(false);
    if (event.dataTransfer?.files?.length) captureFiles(event.dataTransfer.files);
  });

  const find = horizonEl("stream-search");
  find.addEventListener("input", () => {
    horizonEl("find-clear").hidden = !find.value;
    // Debounced, because every keystroke is a round trip and a SQL scan. 180ms is under the
    // threshold where typing feels laggy and well over the gap between two keys.
    clearTimeout(horizonState.findTimer);
    horizonState.findTimer = setTimeout(() => {
      horizonState.query = find.value.trim();
      refreshHorizon({ reset: true });
    }, 180);
  });
  find.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setHorizonQuery("");
  });
  horizonEl("find-clear").addEventListener("click", () => setHorizonQuery(""));

  horizonEl("stream-more").addEventListener("click", () => refreshHorizon());
  horizonEl("distil-btn").addEventListener("click", async () => {
    // START it, then let the strip carry it. Awaiting fifty sequential model calls behind a
    // disabled button is not progress, and it left the one action that spends money with no way to
    // stop it (invariant 47).
    const button = horizonEl("distil-btn");
    // Pressed twice in the time the first request is in flight, this fired two passes; the second
    // came back 409 and the page ignored it. The guard is the button's own disabled state, cleared
    // in the `finally` - the STRIP takes over from there and the note hides itself while a pass is
    // running, so there is nothing left to press.
    if (button.disabled) return;
    button.disabled = true;
    try {
      const reply = await api("/horizon/distil", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit: distilBatchSize() }),
      });
      // `started: false` is the server saying there was nothing to do. Ignoring it left the page
      // polling for a pass that never existed.
      if (reply && reply.started === false) {
        await refreshHorizon({ reset: true });
        return;
      }
    } catch (err) {
      // Inline, next to the action, on the same line the pass's own failures use. An `alert()` for
      // a failure the page has a place to show is a dialog the reader has to dismiss before they
      // can read the thing it is about.
      horizonState.distil = { running: false, done: 0, total: 0, failed: 1, error: err.message };
      renderDistilError();
      return;
    } finally {
      button.disabled = false;
    }
    startHorizonPolling();
    await pollIntake();
  });
  horizonEl("intake-stop").addEventListener("click", async () => {
    try {
      await api("/horizon/cancel", { method: "POST" });
    } catch {
      // Nothing to say: the strip's next poll reports whatever actually happened.
    }
    await pollIntake();
  });

  horizonEl("horizon-home").addEventListener("click", showHorizon);
  const exportBtn = document.getElementById("orbit-export");
  if (exportBtn) exportBtn.addEventListener("click", downloadOrbitMarkdown);
  horizonEl("facet-new").addEventListener("click", async () => {
    // The id is a HANDLE and the UI mints it (invariant 37): a reader is never asked to invent one
    // before they can start, which is the mistake the first version of this product made.
    await openOrbit(`nb-${crypto.randomUUID().slice(0, 8)}`, { fresh: true });
  });
}

initHorizon();

// --- Asking the Horizon ------------------------------------------------------------------------
//
// A question over everything kept, a tag or an entity, rather than inside one orbit. The server
// runs it under a reserved handle (`api.HORIZON_ASK_KEY`), so the ordinary run routes serve its
// ticker, Stop and trajectory with no second copy of any of them.
//
// It lives in the ask dock, which follows the reader: on the star map, the list and an orbit's
// knowledge graph, its scope chips are whatever is selected there. An ORBIT chip is different in
// kind: a question about one orbit is asked in that orbit's conversation, so pressing Ask with it
// opens the three columns and asks there.

const HORIZON_ASK_KEY = "horizon-ask";

const askH = {
  plan: null, // the last preview: what Ask will read
  running: false,
  generation: 0, // bumped by every new preview, so a late reply cannot overwrite a newer one
  chips: [{ id: "all", scope: { kind: "all" } }],
  chosen: "all",
  custom: null, // a tag or entity picked from the "other" list, kept as its own chip
};

function askHChipLabel(chip) {
  if (chip.orbit) return t("askH.chipOrbit", `Orbit: ${chip.orbit.title}`, { name: chip.orbit.title });
  const scope = chip.scope || { kind: "all" };
  // A tag or entity picked from the "other" list reads across every orbit, which is worth saying
  // beside an orbit-narrowed chip of the same name.
  if (chip.id === "custom" && scope.orbits) return askHScopeLabel(scope);
  if (chip.id === "custom") {
    return t("askH.chipEverywhere", `${askHScopeLabel(scope)} (everywhere)`, { name: askHScopeLabel(scope) });
  }
  // The orbit a chip is narrowed to is the one on screen, so the chip does not repeat it.
  if (scope.kind === "entity") return t("askH.chipEntity", `Entity: ${scope.value}`, { name: scope.value });
  return askHScopeLabel({ ...scope, orbit: null });
}

//: The scopes on offer, most specific last; the most specific is chosen, because the reader's
//: selection is the best evidence of what they mean to ask about.
//: `follow` is true when the READER changed the selection (picked a planet, an entity, a lens):
//: the dock then takes the most specific scope. A refresh redraws the same selection, so the
//: reader's own chip and any plan already on screen are kept; resetting them there turned the
//: free check button into a paid ask in a scope the reader had just deselected.
function setAskContext(chips, { follow = true } = {}) {
  const all = { id: "all", scope: { kind: "all" } };
  const previous = askH.chosen;
  askH.chips = [all, ...chips];
  if (askH.custom) askH.chips.push(askH.custom);
  const keep = !follow && askH.chips.some((chip) => chip.id === previous);
  askH.chosen = keep ? previous : askH.chips[askH.chips.length - 1].id;
  renderAskHChips();
  // Chips from different views can share an id while meaning different scopes (a `tag:` chip on
  // the map reads the whole Horizon, the same id on a graph reads one orbit), so a plan survives
  // only while it still describes exactly the scope on screen.
  const same = (a, b) => JSON.stringify([a.kind, a.value || null, a.orbit || null])
    === JSON.stringify([b.kind, b.value || null, b.orbit || null]);
  const chosen = askHChosen();
  const planStale = askH.plan && (chosen.orbit || !same(askH.plan.scope || {}, chosen.scope || {}));
  if (askH.chosen !== previous || planStale) dismissAskHPlan();
}

function askHChosen() {
  return askH.chips.find((chip) => chip.id === askH.chosen) || askH.chips[0];
}

function askHScope() {
  return askHChosen().scope || { kind: "all" };
}

function renderAskHChips() {
  const row = horizonEl("ask-h-chips");
  row.textContent = "";
  askH.chips.forEach((chip) => {
    const button = elt("button", "ask-h-chip", askHChipLabel(chip));
    button.type = "button";
    button.setAttribute("aria-pressed", chip.id === askH.chosen ? "true" : "false");
    button.addEventListener("click", () => {
      askH.chosen = chip.id;
      renderAskHChips();
      dismissAskHPlan();
    });
    row.appendChild(button);
  });
  const chosen = askHChosen();
  const check = horizonEl("ask-h-check");
  // An orbit chip asks straight into that orbit's conversation, where a question is one press as it
  // always has been; everything else checks first, for free. The round button is an arrow, so what
  // it will do is said in the line under the box and in its name, never left to guess.
  const does = chosen.orbit ? t("askH.askOrbit", "Ask in this orbit") : t("askH.check", "See what it reads");
  check.setAttribute("aria-label", does);
  check.title = does;
  // One word per key. What a preview is and what asking costs are said where they happen (the
  // preview itself names the spend), not repeated under every question. `/` is "commands": today it
  // only chooses what a question reads, and it is where more commands will live.
  paintAskHHint([
    ["\u23ce", chosen.orbit ? t("askH.keyAsk", "ask") : t("askH.keyPreview", "preview")],
    ["\u21e7\u23ce", t("askH.keyNewline", "new line")],
    ["/", t("askH.keyCommands", "commands")],
  ]);
}

//: The row under the box, in the composer's own keycap language: what each key does HERE. It is
//: where the dock says what Enter costs, since that differs by scope, and where the picker says
//: its keys while it is open.
function paintAskHHint(pairs) {
  const hint = horizonEl("ask-h-hint");
  hint.textContent = "";
  pairs.forEach(([key, label], i) => {
    if (i) hint.appendChild(elt("span", "ask-hint-sep", "\u00b7"));
    hint.appendChild(elt("kbd", "keycap", key));
    hint.appendChild(elt("span", "", label));
  });
}

function askHScopeLabel(scope) {
  if (!scope || scope.kind === "all") return t("askH.everything", "Everything");
  const base = scope.kind === "tag"
    ? (scope.values || [scope.value]).map((name) => `#${name}`).join(" + ")
    : scope.value || "";
  if (scope.orbits) {
    const names = scope.orbits.map((key) => orbitLabelForSlug(key) || t("suggest.anOrbit", "an orbit"));
    return `${base} \u00b7 ${names.join(" + ")}`;
  }
  const orbit = scope.orbit ? orbitLabelForSlug(scope.orbit) : "";
  return orbit ? `${base} · ${orbit}` : base;
}

//: Orbit titles by slug, for labelling a scope that was narrowed to one. Filled by the star map's
//: fetch of `/orbits`, which is the only place the client learns them in bulk.
const orbitTitles = new Map();

function orbitLabelForSlug(slug) {
  return orbitTitles.get(slug) || "";
}

// --- choosing what a question reads: the staged picker -------------------------------------------
//
// Opened by the + beside the chips or by typing "/" at the start of the question. The first level
// is the kinds (tags, entities, orbits) with how many of each; choosing one lists its names, and
// Escape goes back up one level. Typing searches every kind at once. The highlight moves without
// rebuilding the list, because rebuilding under a still pointer replaced the row between mousedown
// and mouseup, and the click never landed.

let syncAskHComposer = () => {};

const askPick = { open: false, fromSlash: false, drill: null, items: [], index: 0, data: { tags: [], entities: [] } };

async function loadAskHScopes() {
  try {
    askPick.data = await api("/horizon/concepts");
  } catch {
    return; // the narrower scopes are simply not offered
  }
  if (askPick.open) refreshAskPicker();
}

function askPickKinds() {
  const orbits = (starMap.orbits || []).map((o) => ({ name: o.title, count: o.sources || 0, orbit: o }));
  return {
    tag: { label: t("askH.tags", "Tags"), rows: askPick.data.tags || [] },
    entity: { label: t("askH.entities", "Entities"), rows: askPick.data.entities || [] },
    orbit: { label: t("askH.orbits", "Orbits"), rows: orbits },
  };
}

function askPickRow(kind, row) {
  return {
    kind, name: row.name, orbit: row.orbit || null,
    title: kind === "tag" ? `#${row.name}` : row.name,
    fact: String(row.count),
  };
}

function askPickMatches(query) {
  const kinds = askPickKinds();
  let q = query.trim().toLowerCase();
  let drill = askPick.drill;
  // "#" searches tags, the way a tag is written everywhere else in the product.
  if (!drill && q.startsWith("#")) {
    drill = "tag";
    q = q.slice(1);
  }
  const hit = (row) => !q || row.name.toLowerCase().includes(q);
  if (drill) return kinds[drill].rows.filter(hit).map((row) => askPickRow(drill, row));
  if (!q) {
    return Object.entries(kinds)
      .filter(([, k]) => k.rows.length)
      .map(([kind, k]) => ({ kind: "open", drill: kind, title: k.label, fact: String(k.rows.length) }));
  }
  const found = [];
  for (const [kind, k] of Object.entries(kinds)) {
    k.rows.filter(hit).forEach((row) => found.push({ ...askPickRow(kind, row), badge: k.label }));
  }
  return found.sort((a, b) => Number(b.fact) - Number(a.fact)).slice(0, 50);
}

function askSlashQuery() {
  const value = horizonEl("ask-h-input").value;
  return value.startsWith("/") && !value.includes("\n") ? value.slice(1) : null;
}

function refreshAskPicker() {
  askPick.items = askPickMatches(askPick.fromSlash ? askSlashQuery() || "" : "");
  askPick.index = Math.min(askPick.index, Math.max(0, askPick.items.length - 1));
  renderAskPicker();
}

function highlightAskPick(i) {
  askPick.index = i;
  horizonEl("ask-h-picker").querySelectorAll(".ask-opt").forEach((opt, n) => {
    opt.classList.toggle("is-active", n === i);
  });
}

function renderAskPicker() {
  const box = horizonEl("ask-h-picker");
  box.textContent = "";
  if (askPick.drill) {
    const head = elt("p", "ask-opt-head");
    head.appendChild(elt("span", "ask-opt-head-where", askPickKinds()[askPick.drill].label));
    head.appendChild(elt("span", "ask-opt-head-back", t("askH.pickBack", "Esc to go back")));
    box.appendChild(head);
  }
  askPick.items.forEach((row, i) => {
    const opt = elt("button", `ask-opt${i === askPick.index ? " is-active" : ""}`);
    opt.type = "button";
    opt.appendChild(elt("span", "ask-opt-title", row.title));
    if (row.badge) opt.appendChild(elt("span", "ask-opt-badge", row.badge));
    opt.appendChild(elt("span", "ask-opt-fact", row.fact));
    if (row.kind === "open") opt.appendChild(elt("span", "ask-opt-more", "›"));
    opt.addEventListener("mousedown", (event) => {
      event.preventDefault(); // keep focus in the question
      // Choosing a kind rebuilds the list, which detaches this row; the event then reached the
      // document's close-on-outside-press handler, whose `closest` on a detached row found no
      // picker and closed it. A mouse could not open a kind, while Enter could.
      event.stopPropagation();
      chooseAskPick(i);
    });
    opt.addEventListener("mouseenter", () => highlightAskPick(i));
    box.appendChild(opt);
  });
  if (!askPick.items.length) {
    box.appendChild(elt("p", "ask-opt-empty", askPick.drill || askSlashQuery()
      ? t("askH.pickNone", "Nothing by that name.")
      : t("askH.pickNothing", "No tags, entities or orbits yet. Summaries find tags and entities.")));
  }
}

function openAskPicker({ fromSlash = false } = {}) {
  if (!askPick.open) askPick.drill = null;
  askPick.open = true;
  askPick.fromSlash = fromSlash;
  askPick.index = 0;
  horizonEl("ask-h-picker").hidden = false;
  horizonEl("ask-h-add").setAttribute("aria-expanded", "true");
  // While it is open, Enter chooses a row rather than checking the question; the row says so.
  paintAskHHint([["\u2191\u2193", t("askH.keyMove", "move")], ["\u23ce", t("askH.keyChoose", "choose")],
    ["Esc", t("askH.keyBack", "back")]]);
  refreshAskPicker();
  void loadAskHScopes(); // summaries land in the background; what is on offer follows them
  syncDock();
}

function closeAskPicker() {
  askPick.open = false;
  askPick.fromSlash = false;
  askPick.drill = null;
  horizonEl("ask-h-picker").hidden = true;
  horizonEl("ask-h-add").setAttribute("aria-expanded", "false");
  renderAskHChips(); // puts the question's own hint back
}

function chooseAskPick(i) {
  const row = askPick.items[i];
  if (!row) return;
  const input = horizonEl("ask-h-input");
  if (row.kind === "open") {
    askPick.drill = row.drill;
    askPick.index = 0;
    if (askPick.fromSlash) input.value = "/";
    syncAskHComposer();
    refreshAskPicker();
    input.focus();
    return;
  }
  askH.custom = row.kind === "orbit"
    ? { id: "custom", orbit: { id: row.orbit.id, slug: row.orbit.slug, title: row.orbit.title } }
    : { id: "custom", scope: { kind: row.kind, value: row.name } };
  askH.chips = askH.chips.filter((chip) => chip.id !== "custom");
  askH.chips.push(askH.custom);
  askH.chosen = "custom";
  if (askPick.fromSlash) input.value = "";
  syncAskHComposer();
  closeAskPicker();
  renderAskHChips();
  dismissAskHPlan();
  input.focus();
}

//: The keys that belong to the picker while it is open: arrows move, Enter chooses, Escape backs
//: out one level. Registered in the capture phase so Enter chooses a row instead of checking the
//: question.
function askPickerKeys(event) {
  if (!askPick.open) return;
  const n = askPick.items.length;
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    if (n) {
      const next = (askPick.index + (event.key === "ArrowDown" ? 1 : n - 1)) % n;
      highlightAskPick(next);
      horizonEl("ask-h-picker").querySelectorAll(".ask-opt")[next]?.scrollIntoView({ block: "nearest" });
    }
  } else if (event.key === "Enter" && !event.isComposing && event.keyCode !== 229) {
    chooseAskPick(askPick.index);
  } else if (event.key === "Escape") {
    if (askPick.drill) {
      askPick.drill = null;
      askPick.index = 0;
      if (askPick.fromSlash) horizonEl("ask-h-input").value = "/"; syncAskHComposer();
      refreshAskPicker();
    } else {
      closeAskPicker();
    }
  } else {
    return;
  }
  event.preventDefault();
  event.stopImmediatePropagation();
}

function askHShowError(message) {
  const el = horizonEl("ask-h-error");
  el.textContent = message || "";
  el.hidden = !message;
  syncDock();
}

function askHPlanLine(plan) {
  if (!plan.count) {
    return plan.in_scope && (plan.too_large || []).length >= plan.in_scope
      ? t("askH.planTooLarge", "Everything in this scope is too large to read in one question.")
      : t("askH.planEmpty", "Nothing in this scope can be read yet.");
  }
  const parts = [
    plan.count === plan.in_scope
      ? t("askH.planAll", `This reads all ${plan.count} captures in this scope.`, { count: plan.count })
      : t("askH.plan", `This reads ${plan.count} of ${plan.in_scope} captures.`,
        { count: plan.count, total: plan.in_scope }),
  ];
  if (plan.strategy === "matched" && plan.count < plan.in_scope) {
    parts.push(t("askH.planMatched", "The ones your words found, best first."));
  } else if (plan.strategy === "recent" && (plan.too_large || []).length) {
    parts.push(t("askH.planRecentTooLarge", "What your words found is too large, so these are the newest."));
  } else if (plan.strategy === "recent") {
    parts.push(t("askH.planRecent", "Your words found nothing here, so these are the newest."));
  }
  if (plan.too_large && plan.too_large.length) {
    parts.push(t("askH.planSkipped", `${plan.too_large.length} too large to include.`,
      { n: plan.too_large.length }));
  }
  parts.push(t("askH.planCost", "Asking starts one paid model run."));
  // Chinese runs sentences together; a space between them reads as a stray gap.
  return parts.join(uiLang().startsWith("zh") ? "" : " ");
}

function renderAskHPlan(plan) {
  horizonEl("ask-h-plan-line").textContent = askHPlanLine(plan);
  const list = horizonEl("ask-h-plan-list");
  list.textContent = "";
  const SHOWN = 8;
  plan.items.slice(0, SHOWN).forEach((item) => list.appendChild(elt("li", "", item.title)));
  if (plan.items.length > SHOWN) {
    list.appendChild(elt("li", "ask-h-plan-more",
      t("askH.planMore", `and ${plan.items.length - SHOWN} more`, { n: plan.items.length - SHOWN })));
  }
  horizonEl("ask-h-send").disabled = !plan.count || askH.running;
  horizonEl("ask-h-plan").hidden = false;
  syncDock();
}

async function previewAskH() {
  const question = horizonEl("ask-h-input").value.trim();
  if (!question) {
    horizonEl("ask-h-input").focus();
    return;
  }
  askHShowError("");
  const chosen = askHChosen();
  if (chosen.orbit) {
    await askInOrbit(chosen.orbit, question);
    return;
  }
  const generation = ++askH.generation;
  const scope = askHScope();
  const check = horizonEl("ask-h-check");
  check.disabled = true;
  try {
    const plan = await api("/horizon/ask/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, scope }),
    });
    if (generation !== askH.generation) return;
    askH.plan = { ...plan, question, scope };
    renderAskHPlan(plan);
  } catch (err) {
    if (generation !== askH.generation) return;
    askH.plan = null;
    horizonEl("ask-h-plan").hidden = true;
    askHShowError(readableError(err.message));
  } finally {
    check.disabled = false;
  }
}

function dismissAskHPlan() {
  askH.plan = null;
  askH.generation += 1;
  horizonEl("ask-h-plan").hidden = true;
  syncDock();
}

//: Strokes through the sentences a citation backs, numbered by the capture they point at. The
//: orbit renderer numbers against its References panel, which a Horizon answer does not have, so
//: this one numbers against the answer's own source list below it.
function renderAskHAnswer(ask) {
  const article = horizonEl("ask-h-answer");
  article.textContent = "";
  article.appendChild(elt("p", "ask-h-question", ask.question));
  article.appendChild(elt("p", "ask-h-meta",
    `${askHScopeLabel(ask.scope)} · ${t("askH.readCount", `${ask.sources.length} captures`, { n: ask.sources.length })}`));

  const numberOf = new Map(ask.sources.map((source, i) => [source.source_id, i + 1]));
  const text = ask.text || "";
  const ranges = [];
  (ask.citations || []).forEach((citation) => {
    const needle = citation.answer_span;
    if (!needle) return;
    const at = text.indexOf(needle);
    if (at !== -1) ranges.push({ start: at, end: at + needle.length, citation });
  });
  ranges.sort((a, b) => a.start - b.start);
  const kept = [];
  ranges.forEach((range) => {
    if (kept.length && range.start < kept[kept.length - 1].end) return;
    kept.push(range);
  });
  const last = new Map();
  const emit = (parent, from, to) => {
    if (to <= from) return;
    let cursor = from;
    kept.forEach((range) => {
      if (range.end <= cursor || range.start >= to) return;
      const sliceFrom = Math.max(range.start, cursor);
      const sliceTo = Math.min(range.end, to);
      if (sliceFrom > cursor) parent.appendChild(document.createTextNode(text.slice(cursor, sliceFrom)));
      const stroke = elt("span", range.citation.verified ? "citation" : "citation is-unverified",
        text.slice(sliceFrom, sliceTo));
      stroke.title = range.citation.title || "";
      last.set(range, stroke);
      parent.appendChild(stroke);
      cursor = sliceTo;
    });
    if (cursor < to) parent.appendChild(document.createTextNode(text.slice(cursor, to)));
  };
  const prose = elt("div", "ask-h-prose");
  renderMarkdownInto(prose, text, emit);
  last.forEach((stroke, range) => {
    const n = numberOf.get(range.citation.source_id);
    if (n) stroke.dataset.reference = String(n);
  });
  article.appendChild(prose);

  const cited = new Set((ask.citations || []).map((c) => c.source_id));
  const sources = elt("ol", "ask-h-sources");
  ask.sources.forEach((source) => {
    const row = elt("li", cited.has(source.source_id) ? "ask-h-source is-cited" : "ask-h-source");
    row.appendChild(elt("span", "", source.title));
    if (source.origin && source.origin !== source.title) row.appendChild(elt("span", "ask-h-source-origin", source.origin));
    sources.appendChild(row);
  });
  article.appendChild(elt("p", "ask-h-sources-head", t("askH.sources", "Read")));
  article.appendChild(sources);

  if (ask.follow_ups && ask.follow_ups.length) {
    article.appendChild(elt("p", "ask-h-sources-head", t("chat.askNext", "Ask next")));
    const next = elt("div", "starter-questions");
    ask.follow_ups.forEach((question) => {
      const chip = elt("button", "starter-question", question);
      chip.type = "button";
      chip.addEventListener("click", () => {
        horizonEl("ask-h-input").value = question; syncAskHComposer();
        void previewAskH();
      });
      next.appendChild(chip);
    });
    article.appendChild(next);
  }
  const close = elt("button", "btn ask-h-close", t("askH.close", "Close"));
  close.type = "button";
  close.addEventListener("click", () => {
    article.hidden = true;
    syncDock();
  });
  article.appendChild(close);
  article.hidden = false;
  syncDock();
}

async function refreshAskHHistory() {
  let data;
  try {
    data = await api("/horizon/asks?limit=20");
  } catch {
    return;
  }
  const details = horizonEl("ask-h-history");
  const list = horizonEl("ask-h-history-list");
  list.textContent = "";
  (data.asks || []).forEach((ask) => {
    const row = elt("li", "ask-h-history-row");
    const open = elt("button", "ask-h-history-open", ask.question);
    open.type = "button";
    open.addEventListener("click", async () => {
      try {
        renderAskHAnswer(await api(`/horizon/asks/${encodeURIComponent(ask.id)}`));
        askHShowError("");
      } catch (err) {
        askHShowError(readableError(err.message));
      }
    });
    row.appendChild(open);
    row.appendChild(elt("span", "ask-h-history-when",
      `${askHScopeLabel(ask.scope)} · ${relativeTime(ask.created_at)}`));
    const remove = elt("button", "ask-h-history-remove", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", t("askH.remove", "Remove this question"));
    remove.title = t("askH.remove", "Remove this question");
    remove.addEventListener("click", async () => {
      try {
        await api(`/horizon/asks/${encodeURIComponent(ask.id)}`, { method: "DELETE" });
      } catch (err) {
        askHShowError(readableError(err.message));
        return;
      }
      void refreshAskHHistory();
    });
    row.appendChild(remove);
    list.appendChild(row);
  });
  details.hidden = !(data.asks || []).length;
}

function askHSetRunning(running) {
  askH.running = running;
  syncDock();
  horizonEl("ask-h-check").disabled = running;
  horizonEl("ask-h-send").disabled = running || !(askH.plan && askH.plan.count);
}

async function sendAskH() {
  const plan = askH.plan;
  if (!plan || !plan.count || askH.running) return;
  askHShowError("");
  const token = crypto.randomUUID();
  const runId = `${HORIZON_ASK_KEY}-${token}`;
  let cancelled = false;
  const holder = horizonEl("ask-h-run");
  const status = runStatus({
    orbitId: HORIZON_ASK_KEY,
    runIds: [runId],
    label: t("chat.thinking", "Thinking…"),
    onCancel: () => {
      cancelled = true;
      holder.hidden = true;
      holder.textContent = "";
      askHSetRunning(false);
      askHShowError(t("askH.stopped", "Stopped. Nothing was kept."));
    },
  });
  holder.textContent = "";
  holder.appendChild(status.node);
  holder.hidden = false;
  horizonEl("ask-h-plan").hidden = true;
  askHSetRunning(true);
  openTicker(HORIZON_ASK_KEY, runId, (event) => status.onEvent(event));
  try {
    const ask = await api("/horizon/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: plan.question,
        scope: plan.scope,
        node_ids: plan.items.map((item) => item.node_id),
        run_id: token,
      }),
    });
    status.finish();
    // A Stop pressed as the run finished reports success (a process already gone is stopped), yet
    // the server went on to keep the answer. Saying "Nothing was kept" over an answer that is now
    // in the history would be a status line claiming what did not happen (invariant 60).
    if (cancelled) askHShowError("");
    renderAskHAnswer(ask);
    askH.plan = null;
    void refreshAskHHistory();
  } catch (err) {
    status.finish();
    if (!cancelled) askHShowError(readableError(err.message));
  } finally {
    closeTicker(runId);
    if (!cancelled) {
      holder.hidden = true;
      holder.textContent = "";
      askHSetRunning(false);
    }
  }
}

//: **A reload must not lose a question that is still billing** (invariant 47). The run outlives
//: the page, so the Horizon asks the server what is in flight under its handle and puts a status
//: row with a working Stop back until it ends.
async function reattachAskH() {
  let runs;
  try {
    runs = (await api(`/orbits/${HORIZON_ASK_KEY}/runs`)).runs || [];
  } catch {
    return;
  }
  if (!runs.length || askH.running) return;
  const holder = horizonEl("ask-h-run");
  let ended = false;
  const status = runStatus({
    orbitId: HORIZON_ASK_KEY,
    runIds: runs,
    label: t("askH.stillRunning", "A question is still running"),
    onCancel: () => {
      ended = true;
      holder.hidden = true;
      holder.textContent = "";
      askHSetRunning(false);
    },
  });
  holder.textContent = "";
  holder.appendChild(status.node);
  holder.hidden = false;
  askHSetRunning(true);
  runs.forEach((runId) => openTicker(HORIZON_ASK_KEY, runId, (event) => status.onEvent(event)));
  const poll = setInterval(async () => {
    if (ended) {
      clearInterval(poll);
      return;
    }
    let left;
    try {
      left = (await api(`/orbits/${HORIZON_ASK_KEY}/runs`)).runs || [];
    } catch {
      return;
    }
    if (left.some((runId) => runs.includes(runId))) return;
    clearInterval(poll);
    ended = true;
    status.finish();
    holder.hidden = true;
    holder.textContent = "";
    askHSetRunning(false);
    void refreshAskHHistory();
    // The server saves the answer a moment AFTER the run leaves its in-flight list, so a second
    // look catches an answer the first one arrived too early for.
    setTimeout(() => void refreshAskHHistory(), 3000);
  }, 2500);
}


//: A question about one orbit goes into that orbit's conversation, in the three columns, where
//: its answer joins the thread and later questions can follow it up.
async function askInOrbit(orbit, question) {
  if (state.orbitId !== orbit.id) await openOrbit(orbit.id);
  if (state.orbitId !== orbit.id) return; // the orbit could not be opened; openOrbit said why
  orbitVisit.override = "cols";
  applyViewMode();
  const composer = document.getElementById("ask-input");
  // Asked of the SERVER, not only of `composerLocked()`: opening the orbit starts the recovery
  // check without waiting for it, so a run still in flight from before a reload or another tab is
  // not known here yet, and asking on top of it would buy a second worker (invariants 23, 47).
  let inFlight = [];
  try {
    inFlight = (await api(`/orbits/${encodeURIComponent(orbit.id)}/runs`)).runs || [];
  } catch {
    inFlight = ["unknown"]; // cannot tell, so do not spend
  }
  if (state.orbitId !== orbit.id) return;
  // Refused here, where the reason can be said, rather than dropped by the chat handler: the
  // question moves to the orbit's own composer so nothing typed is lost.
  if (!(state.sources || []).length || composerLocked() || inFlight.length) {
    if (composer) {
      composer.value = question;
      composer.focus();
    }
    horizonEl("ask-h-input").value = ""; syncAskHComposer();
    notify((state.sources || []).length
      ? t("askH.orbitBusy", "This orbit is still answering. Your question is in its composer for when it is done.")
      : t("askH.orbitEmpty", "This orbit has no sources yet. Your question is in its composer."),
    { tone: "info", timeout: 6000 });
    return;
  }
  horizonEl("ask-h-input").value = ""; syncAskHComposer();
  store.emit("chat:ask", { question });
}

// --- the ask dock ---------------------------------------------------------------------------------

const dock = { near: false, open: false };

//: Pinned open while it holds something the reader has to see or act on: a plan, a run, an answer,
//: an error, a half-typed question or focus. Otherwise it rests as a handle and opens when the
//: pointer comes near the bottom edge.
function dockPinned() {
  const root = horizonEl("ask-dock");
  return Boolean(
    askH.running
    || !horizonEl("ask-h-plan").hidden
    || !horizonEl("ask-h-answer").hidden
    || !horizonEl("ask-h-error").hidden
    || horizonEl("ask-h-input").value.trim()
    || root.contains(document.activeElement)
  );
}

function syncDock() {
  const dockEl = horizonEl("ask-dock");
  if (!dockEl) return;
  const view = document.body.dataset.view;
  // In an orbit the dock belongs to the graph, except while it holds a Horizon ask that is running
  // or an answer not yet read: that run's status and Stop live only here (invariant 47).
  const holding = askH.running || !horizonEl("ask-h-answer").hidden;
  const shown = view === "horizon" || (view === "orbit" && (!horizonEl("view-graph").hidden || holding));
  dockEl.hidden = !shown;
  dock.open = shown && (dock.near || dockPinned());
  dockEl.classList.toggle("is-open", dock.open);
  // The open dock sits over the foot of the map, where the legend and the summary note are.
  document.body.classList.toggle("dock-open", dock.open);
  horizonEl("ask-dock-handle").setAttribute("aria-expanded", dock.open ? "true" : "false");
}

function openDock() {
  horizonEl("ask-h-input").focus();
  syncDock();
}

// --- the capture drawer ----------------------------------------------------------------------------
//
// The ask dock's mirror at the top: open while the pointer is near the top edge or over it, while
// the field has focus or text, while it shows an error, and while a file is dragged over the page
// (a drop still lands anywhere). N opens it from anywhere that is not a text field; Escape in it
// closes it. The same on the map and the list, so capturing looks the same wherever it happens.

const captureDock = { near: false };

function syncCaptureDock() {
  const dockEl = horizonEl("capture-dock");
  if (!dockEl) return;
  const input = horizonEl("capture-input");
  const holding = dockEl.contains(document.activeElement)
    || input.value.trim().length > 0
    || !horizonEl("capture-note").hidden
    || document.getElementById("view-horizon").classList.contains("is-dropping");
  const open = captureDock.near || holding;
  dockEl.classList.toggle("is-open", open);
  horizonEl("capture-dock-handle").setAttribute("aria-expanded", String(open));
}

function openCaptureDock() {
  horizonEl("capture-input").focus();
  syncCaptureDock();
}

// A resting drawer opens only when the pointer comes to the grip bar itself, give or take a few
// pixels. A band the width of the window fired whenever the reader reached for a tag chip, the view
// switch or the legend, and a zone the size of the grip's button still caught the tag row that sits
// just under the top grip.
function nearGrip(event, grip) {
  const box = grip.getBoundingClientRect();
  if (!box.width) return false;
  return event.clientX >= box.left - 16 && event.clientX <= box.right + 16
    && event.clientY >= box.top - 10 && event.clientY <= box.bottom + 10;
}

// --- the mascot -------------------------------------------------------------------------------------
//
// Penny, the half-lit moon, is the brand in the header. A press goes home; a right click, or the
// context-menu key, lets her introduce herself the way a game character would: portrait, name plate
// and a few lines that appear as she says them. The whole line is in a live region for a screen
// reader, so the typing is decoration only, and with reduced motion each line appears at once.

function mascotLines() {
  return [
    t("mascot.line1", "Hi, I'm Penny. Half of me is lit and half is in shadow, and the soft edge between them is a penumbra. That's where the name comes from."),
    t("mascot.line2", "Whatever you throw in lands on the Horizon first. I go through it one piece at a time with this lantern, and what it lights up becomes a summary."),
    t("mascot.line3", "Things that seem related, I tie together with thread: those are the dashed lines on the star map. Once something has a home, it goes into an orbit."),
    t("mascot.line4", "Unless you change the setting, I only get to work when you press something, so I never spend your credits behind your back. Now, throw something in!"),
  ];
}

const npc = { index: 0, typing: null, opener: null };

function npcShowLine() {
  const lines = mascotLines();
  const line = lines[npc.index];
  const text = document.getElementById("npc-text");
  const next = document.getElementById("npc-next");
  document.getElementById("npc-full").textContent = line;
  document.getElementById("npc-step").textContent = `${npc.index + 1} / ${lines.length}`;
  next.textContent = npc.index === lines.length - 1 ? t("mascot.done", "Got it") : t("mascot.next", "Next");
  clearInterval(npc.typing);
  npc.typing = null;
  if (!motionAllowed()) {
    text.textContent = line;
    return;
  }
  const chars = Array.from(line);
  let shown = 0;
  text.textContent = "";
  npc.typing = setInterval(() => {
    shown += 1;
    text.textContent = chars.slice(0, shown).join("");
    if (shown >= chars.length) {
      clearInterval(npc.typing);
      npc.typing = null;
    }
  }, 28);
}

function npcAdvance() {
  if (npc.typing) {
    clearInterval(npc.typing);
    npc.typing = null;
    document.getElementById("npc-text").textContent = mascotLines()[npc.index];
    return;
  }
  if (npc.index >= mascotLines().length - 1) {
    closeNpc();
    return;
  }
  npc.index += 1;
  npcShowLine();
}

function openNpc() {
  const box = document.getElementById("npc");
  npc.index = 0;
  npc.opener = document.activeElement;
  box.hidden = false;
  document.getElementById("new-orbit").setAttribute("aria-expanded", "true");
  npcShowLine();
  document.getElementById("npc-next").focus();
}

function closeNpc() {
  const box = document.getElementById("npc");
  if (box.hidden) return;
  clearInterval(npc.typing);
  npc.typing = null;
  box.hidden = true;
  document.getElementById("new-orbit").setAttribute("aria-expanded", "false");
  npc.opener?.focus?.();
}

function initMascot() {
  const brand = document.getElementById("new-orbit");
  const box = document.getElementById("npc");
  brand.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    openNpc();
  });
  document.getElementById("npc-next").addEventListener("click", (event) => {
    event.stopPropagation();
    npcAdvance();
  });
  // A click anywhere on her speech moves it on, as it would in a game.
  box.addEventListener("click", npcAdvance);
  document.addEventListener("mousedown", (event) => {
    if (!box.hidden && !box.contains(event.target) && !brand.contains(event.target)) closeNpc();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !box.hidden) closeNpc();
  });
}

function initCaptureDock() {
  const root = horizonEl("capture-dock");
  document.addEventListener("mousemove", (event) => {
    if (document.body.dataset.view !== "horizon") return;
    const box = root.getBoundingClientRect();
    const near = nearGrip(event, root.querySelector(".capture-dock-grip"))
      || (root.classList.contains("is-open") && event.clientY <= box.bottom + 16
        && event.clientX >= box.left - 24 && event.clientX <= box.right + 24);
    if (near !== captureDock.near) {
      captureDock.near = near;
      syncCaptureDock();
    }
  });
  root.addEventListener("focusin", syncCaptureDock);
  root.addEventListener("focusout", () => queueMicrotask(syncCaptureDock));
  horizonEl("capture-input").addEventListener("input", syncCaptureDock);
  horizonEl("capture-input").addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    captureDock.near = false;
    event.target.blur();
    syncCaptureDock();
  });
  horizonEl("capture-dock-handle").addEventListener("click", () => {
    if (root.classList.contains("is-open")) {
      captureDock.near = false;
      document.activeElement?.blur?.();
      syncCaptureDock();
    } else {
      openCaptureDock();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "n" && event.key !== "N") return;
    if (event.metaKey || event.ctrlKey || event.altKey || event.isComposing) return;
    if (document.body.dataset.view !== "horizon") return;
    if (event.target.closest("input, textarea, select, [contenteditable]")) return;
    event.preventDefault();
    openCaptureDock();
  });
  // A drag over the page and an error under the field both keep it open.
  new MutationObserver(syncCaptureDock).observe(document.getElementById("view-horizon"), { attributes: true, attributeFilter: ["class"] });
  new MutationObserver(syncCaptureDock).observe(horizonEl("capture-note"), { attributes: true, attributeFilter: ["hidden"] });
  syncCaptureDock();
}

function initDock() {
  const root = horizonEl("ask-dock");
  document.addEventListener("mousemove", (event) => {
    if (root.hidden) return;
    const box = root.getBoundingClientRect();
    const near = nearGrip(event, root.querySelector(".ask-dock-grip"))
      || (dock.open && event.clientY >= box.top - 12 && event.clientX >= box.left - 24 && event.clientX <= box.right + 24);
    if (near !== dock.near) {
      dock.near = near;
      syncDock();
    }
  });
  root.addEventListener("focusin", syncDock);
  root.addEventListener("focusout", () => queueMicrotask(syncDock));
  horizonEl("ask-dock-handle").addEventListener("click", () => {
    if (dock.open) {
      dock.near = false;
      document.activeElement?.blur?.();
      syncDock();
      return;
    }
    openDock();
  });
  horizonEl("ask-h-input").addEventListener("input", syncDock);
}

// --- view modes -----------------------------------------------------------------------------------
//
// The Horizon is drawn as a star map or a list, an orbit as its knowledge graph or the three
// columns. The choice is a per-browser preference, like the theme.

const MODE_KEYS = { horizon: "penumbra-horizon-mode", orbit: "penumbra-orbit-mode" };
const MODE_DEFAULTS = { horizon: "map", orbit: "graph" };
const MODE_CHOICES = {
  horizon: [["map", () => t("mode.map", "Star map")], ["list", () => t("mode.list", "List")]],
  orbit: [["graph", () => t("mode.graph", "Knowledge graph")], ["cols", () => t("mode.cols", "Columns")]],
};

function viewMode(view) {
  let stored = null;
  try {
    stored = localStorage.getItem(MODE_KEYS[view]);
  } catch {
    /* storage blocked: the default is fine */
  }
  const allowed = MODE_CHOICES[view].map(([id]) => id);
  return allowed.includes(stored) ? stored : MODE_DEFAULTS[view];
}

function setViewMode(view, mode) {
  try {
    localStorage.setItem(MODE_KEYS[view], mode);
  } catch {
    /* the choice lasts for this page only */
  }
  applyViewMode();
}

//: How THIS visit to an orbit is drawn when it should not follow the stored preference: an orbit
//: with no sources opens in the columns where sources are added, one with a run in flight opens
//: where that run's status and Stop live, and asking into an orbit shows its conversation. None of
//: these changes the preference; pressing the toggle ends the override.
const orbitVisit = { override: null, userChose: false, orbitId: null };

function orbitHasRun() {
  return activeRuns.has(state.orbitId) || recoveredRuns.has(state.orbitId);
}

function beginOrbitVisit() {
  // Re-opening the orbit already on screen (Load the result, a rename) is the same visit: it keeps
  // how the reader was looking at it rather than jumping to the stored preference.
  if (orbitVisit.orbitId === state.orbitId) {
    if (!(state.sources || []).length || orbitHasRun()) orbitVisit.override = "cols";
    return;
  }
  orbitVisit.orbitId = state.orbitId;
  orbitVisit.userChose = false;
  orbitVisit.override = !(state.sources || []).length || orbitHasRun() ? "cols" : null;
}

function applyViewMode() {
  const view = document.body.dataset.view;
  if (view !== "horizon" && view !== "orbit") return;
  const empty = view === "orbit" && !(state.sources || []).length;
  const mode = view === "orbit" ? (empty ? "cols" : orbitVisit.override || viewMode("orbit")) : viewMode(view);
  MODE_CHOICES[view].forEach(([id, label], i) => {
    const button = horizonEl(i === 0 ? "mode-a" : "mode-b");
    button.textContent = label();
    button.dataset.mode = id;
    button.setAttribute("aria-pressed", id === mode ? "true" : "false");
    button.disabled = empty && id === "graph";
  });
  if (view === "horizon") {
    const map = mode === "map";
    horizonEl("view-horizon").classList.toggle("is-map", map);
    horizonEl("starmap").hidden = !map;
    if (map) void renderStarMap();
    else setAskContext([]);
  } else {
    const graph = mode === "graph";
    horizonEl("view-orbit").hidden = graph;
    horizonEl("view-graph").hidden = !graph;
    if (graph) void renderGraph();
  }
  syncDock();
}

function initViewModes() {
  ["mode-a", "mode-b"].forEach((id) => {
    horizonEl(id).addEventListener("click", (event) => {
      const view = document.body.dataset.view;
      if (view === "orbit") {
        orbitVisit.override = null;
        orbitVisit.userChose = true;
      }
      if (view === "horizon" || view === "orbit") setViewMode(view, event.currentTarget.dataset.mode);
    });
  });
  // A run found in flight AFTER the orbit opened (reload recovery mounts it a moment later) moves
  // the visit to the columns, where its status and Stop are, unless the reader has since chosen.
  store.on("runs:changed", () => {
    if (document.body.dataset.view !== "orbit" || orbitVisit.userChose || !orbitHasRun()) return;
    if (orbitVisit.override === "cols") return;
    orbitVisit.override = "cols";
    applyViewMode();
  });
  // The first source makes the graph a real choice; only the toggle is refreshed, the view stays.
  store.on("sources:changed", () => {
    if (document.body.dataset.view !== "orbit") return;
    horizonEl("mode-a").disabled = !(state.sources || []).length;
  });
}

// --- SVG helpers ----------------------------------------------------------------------------------

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs = {}, className = "") {
  const node = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([name, value]) => node.setAttribute(name, String(value)));
  if (className) node.setAttribute("class", className);
  return node;
}

function svgText(x, y, text, className) {
  const node = svgEl("text", { x, y }, className);
  node.textContent = text;
  return node;
}

function clearSvg(svg) {
  [...svg.childNodes].forEach((child) => {
    if (child.nodeName.toLowerCase() !== "title") child.remove();
  });
}

//: A small stable number from a string, so a layout that needs a little scatter draws the same
//: picture every time rather than jumping on each repaint.
function stableHash(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  // FNV alone barely mixes the last character, so "sx1", "sx2", "sx3" landed a near-constant step
  // apart and the star field drew as dotted lines that read like the legend's bridges. This is
  // MurmurHash3's finaliser, which spreads one changed bit across the whole word.
  h ^= h >>> 16;
  h = Math.imul(h, 0x85ebca6b);
  h ^= h >>> 13;
  h = Math.imul(h, 0xc2b2ae35);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967295;
}

function shortLabel(text, max = 18) {
  const chars = [...(text || "")];
  return chars.length > max ? `${chars.slice(0, max - 1).join("")}…` : chars.join("");
}

//: Tag lenses: pressing one lights up what carries that tag and dims the rest. One at a time.
//: Tags are lenses, and several can be on at once: a reader is often curious about more than one
//: thing. They combine as a union (any of them lights), because a lens answers "show me what is
//: about this", and adding a second interest should show more, not less. `onToggle(name)` flips one;
//: `onToggle(null)` clears them all.
function renderLenses(lensRow, tags, active, onToggle) {
  lensRow.textContent = "";
  tags.slice(0, 12).forEach((tag) => {
    const button = elt("button", "lens", `#${tag.name}`);
    button.type = "button";
    button.appendChild(elt("span", "lens-count", String(tag.count)));
    button.setAttribute("aria-pressed", active.has(tag.name) ? "true" : "false");
    button.addEventListener("click", () => onToggle(tag.name));
    lensRow.appendChild(button);
  });
  if (active.size) {
    const clear = elt("button", "lens-clear", t("lens.clear", "Clear"));
    clear.type = "button";
    clear.addEventListener("click", () => onToggle(null));
    lensRow.appendChild(clear);
  }
  lensRow.hidden = !tags.length;
}

function toggledLenses(lenses, name) {
  if (name === null) return new Set();
  const next = new Set(lenses);
  if (next.has(name)) next.delete(name);
  else next.add(name);
  return next;
}

//: The ask scope a set of lenses means: one tag, or several read as a union.
function lensScope(lenses, orbit) {
  const names = [...lenses];
  const scope = names.length === 1 ? { kind: "tag", value: names[0] } : { kind: "tag", values: names };
  if (orbit) scope.orbit = orbit;
  return scope;
}

function lensChipId(lenses) {
  return `tag:${[...lenses].join("\u001f")}`;
}

// --- the star map ---------------------------------------------------------------------------------

//: `focus` is what the card shows when it is not a planet: the Horizon's unfiled list, or one capture.
const starMap = { data: null, orbits: [], selected: null, lenses: new Set(), generation: 0, focus: null, world: null };

const MAP_CENTRE = { x: 500, y: 330 };
//: Rings grow outward as orbits need them. Orbits are placed by how recently each gained something,
//: newest innermost, and ring `i` holds 3 + 3i of them, so an outer ring (which is longer) holds
//: more. Three fixed rings with the last one unbounded crowded every orbit past the eighth onto one
//: line. At least three rings are drawn, so a young map still reads as a system.
function mapRings() {
  const rings = [];
  let left = starMap.orbits.length;
  for (let i = 0; left > 0 || rings.length < 3; i += 1) {
    const cap = 3 + 3 * i;
    rings.push({ rx: 230 + 100 * i, ry: 138 + 60 * i, cap, period: 240 + 140 * i });
    left -= cap;
  }
  return rings;
}

//: The whole map in view: zoomed out just enough for the outermost ring.
function mapHome() {
  const outer = mapRings().at(-1);
  return { x: 500, y: 320, k: Math.min(1, 480 / (outer.rx + 50), 300 / (outer.ry + 50)) };
}

async function renderStarMap() {
  const generation = ++starMap.generation;
  starMap.lastRender = Date.now();
  watchDistil();
  let topo;
  let listed;
  try {
    [topo, listed] = await Promise.all([api("/horizon/topology"), api("/orbits")]);
  } catch (err) {
    horizonEl("starmap-empty").textContent = readableError(err.message);
    horizonEl("starmap-empty").hidden = false;
    return;
  }
  if (generation !== starMap.generation) return;
  let concepts = { tags: [] };
  try {
    concepts = await api("/horizon/concepts");
  } catch {
    /* lenses are optional */
  }
  if (generation !== starMap.generation) return;
  const bySlug = new Map((topo.orbits || []).map((o) => [o.slug, o]));
  orbitTitles.clear();
  starMap.orbits = (listed.orbits || []).map((o) => {
    const planet = starMapOrbit(o, bySlug.get(o.slug));
    orbitTitles.set(o.slug, planet.title);
    return planet;
  }).sort((a, b) => b.recency - a.recency);
  starMap.data = topo;
  starMap.tags = concepts.tags || [];
  paintStarMapLenses();
  drawStarMap();
  syncStarMapContext({ follow: false });
  // New data can reorder the planets (they are placed by recency), so a camera held on one follows
  // it to wherever it now is instead of staying on empty space.
  if (mapMotion.held && starMap.selected) focusCameraOn(starMap.selected);
}

//: The lens row is repainted with every pick, so `aria-pressed` and each button's idea of what
//: is active stay true and a second press turns the lens off.
function paintStarMapLenses() {
  renderLenses(horizonEl("starmap-lenses"), starMap.tags || [], starMap.lenses, (name) => {
    starMap.lenses = toggledLenses(starMap.lenses, name);
    // Pressing a tag asks what it lights, so the card answers that: the captures behind it.
    starMap.selected = null;
    starMap.focus = starMap.lenses.size ? { kind: "lens" } : null;
    if (starMap.lenses.size && mapPanelGrip && mapPanelGrip.isCollapsed()) {
      mapPanelGrip.setCollapsed(false, { persist: false });
    }
    paintStarMapLenses();
    drawStarMap();
    syncStarMapContext();
  });
}

//: Orbital motion. Each ring turns at its own pace, inner rings faster, as a star system does;
//: the periods are long enough that a planet can still be clicked while it moves. The clock only
//: advances while the map is on screen and no planet is under the pointer, and a reader who asks for
//: reduced motion gets the same map standing still.
//: `paused` is the pointer or focus resting on something; `held` is the camera focused on a planet,
//: which must stay where the camera went until the reader goes back to the whole map.
const mapMotion = { clock: 0, last: 0, paused: false, held: false, frame: 0 };

function motionAllowed() {
  return !window.matchMedia || !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function planetLayout() {
  const placed = [];
  let index = 0;
  mapRings().forEach(({ rx, ry, cap, period }, ring) => {
    const count = Math.min(cap, starMap.orbits.length - index);
    for (let i = 0; i < count; i += 1) {
      const orbit = starMap.orbits[index];
      index += 1;
      // Spread evenly on the ring, each ring turned a little so planets do not line up radially.
      const base = (-Math.PI / 2) + (i / count) * Math.PI * 2 + ring * 0.7;
      const size = Math.max(orbit.sources, orbit.captures);
      placed.push({
        orbit, rx, ry, base,
        omega: (Math.PI * 2) / period,
        r: Math.min(30, 11 + Math.sqrt(size) * 2.6),
      });
    }
  });
  return placed;
}

function planetAt(p) {
  const angle = p.base + mapMotion.clock * p.omega;
  return { x: MAP_CENTRE.x + p.rx * Math.cos(angle), y: MAP_CENTRE.y + p.ry * Math.sin(angle), angle };
}

//: A bridge bowed away from the centre, so it never runs through the Horizon.
function bridgeGeometry(a, b) {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  let ox = mx - MAP_CENTRE.x;
  let oy = my - MAP_CENTRE.y;
  let len = Math.hypot(ox, oy);
  if (len < 1) {
    ox = -(b.y - a.y);
    oy = b.x - a.x;
    len = Math.hypot(ox, oy) || 1;
  }
  const cx = mx + (ox / len) * 160;
  const cy = my + (oy / len) * 160;
  return { d: `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`, lx: (a.x + 2 * cx + b.x) / 4, ly: (a.y + 2 * cy + b.y) / 4 - 6 };
}

function placeStarMap() {
  const scene = starMap.scene;
  if (!scene) return;
  const at = new Map();
  scene.planets.forEach(({ p, group }) => {
    const pos = planetAt(p);
    at.set(p.orbit.slug, pos);
    group.setAttribute("transform", `translate(${pos.x.toFixed(2)} ${pos.y.toFixed(2)})`);
  });
  scene.bridges.forEach(({ bridge, path, hit, label }) => {
    const a = at.get(bridge.a);
    const b = at.get(bridge.b);
    if (!a || !b) return;
    const g = bridgeGeometry(a, b);
    path.setAttribute("d", g.d);
    hit.setAttribute("d", g.d);
    label.setAttribute("x", g.lx.toFixed(2));
    label.setAttribute("y", g.ly.toFixed(2));
  });
}

function mapTick(now) {
  mapMotion.frame = 0;
  const onScreen = document.body.dataset.view === "horizon" && !horizonEl("starmap").hidden && !document.hidden;
  if (!onScreen || !motionAllowed()) {
    mapMotion.last = 0;
    return;
  }
  if (mapMotion.last && !mapMotion.paused && !mapMotion.held) mapMotion.clock += Math.min(0.1, (now - mapMotion.last) / 1000);
  mapMotion.last = now;
  placeStarMap();
  mapMotion.frame = requestAnimationFrame(mapTick);
}

function startMapMotion() {
  if (!mapMotion.frame && motionAllowed()) mapMotion.frame = requestAnimationFrame(mapTick);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) startMapMotion();
});

//: The shared paint for the map: gradients for a planet's body and shade, the Horizon's glow, and
//: the soft blur the accretion disk is drawn through, the same material as the notch's ring.
function starMapDefs() {
  const defs = svgEl("defs");
  const radial = (id, attrs, stops) => {
    const g = svgEl("radialGradient", { id, ...attrs });
    stops.forEach(([offset, cls]) => g.appendChild(svgEl("stop", { offset }, cls)));
    defs.appendChild(g);
  };
  radial("pn-planet", { cx: "0.38", cy: "0.34", r: "0.75" },
    [["0", "stop-planet-light"], ["0.55", "stop-planet-mid"], ["1", "stop-planet-dark"]]);
  radial("pn-shade", { cx: "0.32", cy: "0.3", r: "0.95" },
    [["0.5", "stop-clear"], ["1", "stop-shade"]]);
  radial("pn-halo", {}, [["0.55", "stop-halo"], ["1", "stop-clear"]]);
  radial("pn-hole-glow", {}, [["0.3", "stop-hole-glow"], ["1", "stop-clear"]]);
  const blur = svgEl("filter", { id: "pn-soft", x: "-50%", y: "-50%", width: "200%", height: "200%" });
  blur.appendChild(svgEl("feGaussianBlur", { stdDeviation: "3.2" }));
  defs.appendChild(blur);
  return defs;
}

//: Which drawn element had focus, so a redraw can hand it back. `clearSvg` removes the focused
//: planet or entity, and without this a keyboard reader was dropped to <body> by their own Enter.
function focusedKey(svg) {
  const active = document.activeElement;
  return active && svg.contains(active) && active.dataset ? active.dataset.key || null : null;
}

function restoreFocus(svg, key) {
  if (!key) return;
  const again = [...svg.querySelectorAll("[data-key]")].find((el) => el.dataset.key === key);
  if (again) again.focus();
  return Boolean(again);
}

function drawStarMap() {
  // A repaint mid-drag would remove the element holding the pointer and strand the drag; it waits
  // for the drop instead.
  if (mapDrag.id !== null) { // carrying, or putting a carried capture down
    mapDrag.redraw = true;
    return;
  }
  const svg = horizonEl("starmap-svg");
  const keepFocus = focusedKey(svg);
  clearSvg(svg);
  starMap.scene = null;
  mapMotion.paused = false; // the planet under the pointer is rebuilt; it holds again on the next move
  // The element a tooltip belongs to is about to be removed, and a removed element sends no
  // pointerleave, so the tip would stay on screen naming something that is gone.
  hideMapTip();
  const topo = starMap.data;
  if (!topo) return;
  const empty = !starMap.orbits.length && !topo.total.count;
  horizonEl("starmap-empty").textContent = t("map.empty", "Capture something and the map starts to grow.");
  horizonEl("starmap-empty").hidden = !empty;
  svg.appendChild(starMapDefs());
  // Everything drawn lives in one group the camera moves (`applyCamera`), so zooming and panning
  // are one transform and nothing below needs to know about them.
  const world = svgEl("g", {}, "map-world");
  svg.appendChild(world);
  starMap.world = world;

  // A faint field of stars, fixed per position so it does not reshuffle on every redraw.
  const field = svgEl("g", { "aria-hidden": "true" }, "map-field");
  for (let i = 0; i < 70; i += 1) {
    const star = svgEl("circle", {
      cx: (stableHash(`sx${i}`) * 1000).toFixed(1), cy: (stableHash(`sy${i}`) * 640).toFixed(1),
      r: (0.5 + stableHash(`sr${i}`) * 0.9).toFixed(2),
    }, "map-star");
    star.style.animationDelay = `${(stableHash(`sd${i}`) * 6).toFixed(2)}s`;
    field.appendChild(star);
  }
  world.appendChild(field);

  mapRings().forEach(({ rx, ry }, ring) => {
    world.appendChild(svgEl("ellipse", { cx: MAP_CENTRE.x, cy: MAP_CENTRE.y, rx, ry }, `map-ring ring-${ring}`));
  });

  const planets = planetLayout();
  const scene = { planets: [], bridges: [] };
  // Every source reaches the Horizon now, so a hollow moon is rare (a CLI addition the server has
  // not recorded yet); its legend entry shows only while one is drawn.
  horizonEl("legend-local").hidden = !starMap.orbits.some((o) => (o.sources || 0) > o.captures);

  (topo.bridges || []).forEach((bridge) => {
    if (!planets.some((p) => p.orbit.slug === bridge.a) || !planets.some((p) => p.orbit.slug === bridge.b)) return;
    // Thicker for more shared entities; a wide invisible twin makes the thin line easy to point at.
    // Under a lens a bridge stays lit only between two planets the lens lit.
    const ends = [bridge.a, bridge.b].map((key) => planets.find((p) => p.orbit.slug === key).orbit);
    const bridgeDim = ends.some((o) => dimmedByLens(o, starMap.lenses));
    const path = svgEl("path", { d: "M 0 0" }, `map-bridge${bridgeDim ? " is-dim" : ""}`);
    path.style.strokeWidth = String(1.2 + Math.min(bridge.weight || 1, 5) * 0.45);
    const hit = svgEl("path", { d: "M 0 0", tabindex: 0, role: "button" }, "map-bridge-hit");
    const extra = bridge.weight > 1 ? ` +${bridge.weight - 1}` : "";
    const label = svgText(0, 0, `${shortLabel(bridge.shared[0], 14)}${extra}`, `map-bridge-label${bridgeDim ? " is-dim" : ""}`);
    const titleA = orbitTitles.get(bridge.a) || bridge.a;
    const titleB = orbitTitles.get(bridge.b) || bridge.b;
    hit.setAttribute("aria-label", t("map.bridgeLabel", `${titleA} and ${titleB} both name ${bridge.shared.join(", ")}`,
      { a: titleA, b: titleB, names: bridge.shared.join(t("list.sep", ", ")) }));
    const light = (on) => {
      horizonEl("starmap-svg").classList.toggle("has-lit", on);
      path.classList.toggle("is-lit", on);
      label.classList.toggle("is-lit", on);
      scene.planets.forEach(({ p, group }) => {
        group.classList.toggle("is-linked", on && (p.orbit.slug === bridge.a || p.orbit.slug === bridge.b));
      });
      mapMotion.paused = on;
      if (on) {
        showMapTip(hit, `${titleA} \u2194 ${titleB}`, bridge.shared.join(t("list.sep", ", ")));
      } else {
        hideMapTip();
      }
    };
    const open = () => openMapFocus({ kind: "bridge", a: bridge.a, b: bridge.b });
    [hit, label].forEach((el) => {
      el.addEventListener("pointerenter", () => light(true));
      el.addEventListener("pointerleave", () => light(false));
      el.addEventListener("click", (event) => {
        event.stopPropagation();
        light(false);
        open();
      });
    });
    hit.addEventListener("focus", () => light(true));
    hit.addEventListener("blur", () => light(false));
    hit.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
    if (starMap.focus && starMap.focus.kind === "bridge" && starMap.focus.a === bridge.a && starMap.focus.b === bridge.b) {
      path.classList.add("is-selected");
    }
    world.appendChild(path);
    world.appendChild(hit);
    world.appendChild(label);
    scene.bridges.push({ bridge, path, hit, label });
  });

  // The Horizon: a black hole whose accretion disk is two blurred copper arcs turning around a black
  // core, the notch's own ring at a larger size; the captures filed nowhere circle it slowly.
  const hole = svgEl("g", { transform: `translate(${MAP_CENTRE.x} ${MAP_CENTRE.y})` }, "map-hole");
  // Paints are attributes, not stylesheet `url()`s: the stylesheet names no reference of any kind.
  hole.appendChild(svgEl("circle", { r: 78, fill: "url(#pn-hole-glow)" }, "map-hole-glow"));
  const disk = svgEl("g", { filter: "url(#pn-soft)" }, "map-disk");
  disk.appendChild(svgEl("circle", { r: 42 }, "map-disk-a"));
  disk.appendChild(svgEl("circle", { r: 42 }, "map-disk-b"));
  hole.appendChild(disk);
  hole.appendChild(svgEl("circle", { r: 29 }, "map-hole-rim"));
  hole.appendChild(svgEl("circle", { r: 27 }, "map-hole-core"));
  // The Horizon itself is a button: it opens the list of what is filed nowhere, each with a way to
  // file it. That list is also the keyboard's way to do what dragging a dot onto a planet does.
  const loose = topo.loose || { count: 0, undistilled: 0, busy: 0, items: [] };
  const holeHit = svgEl("circle", {
    r: 48, tabindex: 0, role: "button",
    "aria-label": t("map.holeLabel", `Horizon: ${loose.count} not in an orbit`, { n: loose.count }),
  }, "map-hole-hit");
  holeHit.dataset.key = "horizon";
  holeHit.addEventListener("click", () => openMapFocus({ kind: "horizon" }));
  holeHit.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openMapFocus({ kind: "horizon" });
    }
  });
  hole.appendChild(holeHit);
  const looseRing = svgEl("g", {}, "map-loose");
  const items = loose.items || [];
  const shown = Math.min(loose.count, items.length || loose.count, 28);
  for (let i = 0; i < shown; i += 1) {
    const angle = (i / Math.max(shown, 1)) * Math.PI * 2 + 0.4;
    const d = 62 + (i % 3) * 7;
    const item = items[i];
    const x = d * Math.cos(angle);
    const y = d * Math.sin(angle);
    looseRing.appendChild(svgEl("circle", { cx: x, cy: y, r: 2.2 }, moonClass(item) + moonLensClass(item, starMap.lenses)));
    if (item && isFocusedMoon(item)) looseRing.appendChild(moonMark(x, y));
    if (item) looseRing.appendChild(moonHit(x, y, { kind: "capture", ...item }));
  }
  hole.appendChild(looseRing);
  if (starMap.focus && starMap.focus.kind === "horizon") hole.classList.add("is-selected");
  world.appendChild(hole);
  // Close under the loose ring and drawn with a halo, so a planet passing on the inner ring never
  // runs through the words. The count reads as the Horizon's action when there is something to file.
  world.appendChild(svgText(MAP_CENTRE.x, MAP_CENTRE.y + 94, t("horizon.home", "Horizon"), "map-hole-label"));
  const sub = svgText(MAP_CENTRE.x, MAP_CENTRE.y + 110,
    t("map.loose", `${loose.count} not in an orbit`, { n: loose.count }),
    loose.count ? "map-hole-sub is-action" : "map-hole-sub");
  if (loose.count) sub.addEventListener("click", () => openMapFocus({ kind: "horizon" }));
  world.appendChild(sub);

  planets.forEach((p, index) => {
    const { orbit } = p;
    const dimmed = dimmedByLens(orbit, starMap.lenses);
    const group = svgEl("g", { tabindex: 0, role: "button", "aria-label":
      t("map.planetLabel", `${orbit.title}, ${orbit.sources} sources`, { name: orbit.title, n: orbit.sources }) },
    `map-planet${planetMark(orbit.slug)}${dimmed ? " is-dim" : ""}`);
    group.appendChild(svgEl("circle", { r: p.r + 14, fill: "url(#pn-halo)" }, "map-planet-halo"));
    // Moons: one per source, so they agree with the "N sources" under the planet. Each capture
    // filed from the Horizon is its own moon, copper once summarised and grey before, and can be
    // pointed at and opened; a source added inside the orbit is hollow, because no summary pass
    // reads it. Drawing captures alone left an orbit built in place with "1 source" and no moon.
    const captured = (orbit.moons || []).slice(0, 12);
    const local = Math.max(0, Math.min(12 - captured.length, (orbit.sources || 0) - orbit.captures));
    const moonItems = [...captured.map((item) => ({ kind: "capture", ...item })),
      ...Array.from({ length: local }, () => ({ kind: "local", orbit: orbit.slug, title: orbit.title }))];
    const moonRing = svgEl("g", {}, "map-moons");
    moonRing.style.animationDuration = `${16 + (index % 5) * 3}s`;
    moonItems.forEach((item, i) => {
      const angle = (i / moonItems.length) * Math.PI * 2;
      const d = p.r + 8 + (i % 2) * 5;
      const x = d * Math.cos(angle);
      const y = d * Math.sin(angle);
      moonRing.appendChild(svgEl("circle", { cx: x, cy: y, r: 2.2 }, moonClass(item) + moonLensClass(item, starMap.lenses)));
      if (isFocusedMoon(item)) moonRing.appendChild(moonMark(x, y));
      moonRing.appendChild(moonHit(x, y, { ...item, orbit: orbit.slug }));
    });
    group.appendChild(moonRing);
    // The planet: a lit sphere whose surface bands turn under a fixed shade, so it reads as spinning.
    const clipId = `pn-clip-${index}`;
    const clip = svgEl("clipPath", { id: clipId });
    clip.appendChild(svgEl("circle", { r: p.r }));
    group.appendChild(clip);
    group.appendChild(svgEl("circle", { r: p.r, fill: "url(#pn-planet)" }, "map-planet-body"));
    const surface = svgEl("g", { "clip-path": `url(#${clipId})` });
    const bands = svgEl("g", {}, "map-planet-bands");
    bands.style.animationDuration = `${28 + (index % 4) * 6}s`;
    bands.appendChild(svgEl("ellipse", { cx: 0, cy: -p.r * 0.35, rx: p.r * 1.5, ry: p.r * 0.16 }, "map-band"));
    bands.appendChild(svgEl("ellipse", { cx: p.r * 0.3, cy: p.r * 0.18, rx: p.r * 1.2, ry: p.r * 0.11 }, "map-band"));
    bands.appendChild(svgEl("circle", { cx: -p.r * 0.45, cy: p.r * 0.5, r: p.r * 0.18 }, "map-band"));
    surface.appendChild(bands);
    group.appendChild(surface);
    group.appendChild(svgEl("circle", { r: p.r, fill: "url(#pn-shade)" }, "map-planet-shade"));
    group.appendChild(svgEl("circle", { r: p.r }, "map-planet-rim"));
    group.appendChild(svgText(0, p.r + 30, shortLabel(orbit.title), "map-planet-label"));
    group.appendChild(svgText(0, p.r + 46, t("map.planetCount", `${orbit.sources} sources`, { n: orbit.sources }),
      "map-planet-sub"));
    // No <title>: the planet's own label names it, and the native tooltip drew the same name a
    // second time in a system box beside it.
    group.dataset.key = `orbit:${orbit.slug}`;
    const pick = () => {
      if (starMap.selected === orbit.slug && !starMap.focus) {
        void enterOrbit(orbit);
        return;
      }
      starMap.selected = orbit.slug;
      starMap.focus = null;
      drawStarMap();
      syncStarMapContext();
      focusCameraOn(orbit.slug);
    };
    group.addEventListener("click", pick);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        pick();
      }
    });
    // A planet holds still while it is pointed at or focused, so it can be read and clicked.
    const hold = () => { mapMotion.paused = true; };
    const release = () => { mapMotion.paused = false; };
    group.addEventListener("pointerenter", hold);
    group.addEventListener("pointerleave", release);
    group.addEventListener("focus", hold);
    group.addEventListener("blur", release);
    world.appendChild(group);
    scene.planets.push({ p, group });
  });
  starMap.scene = scene;
  placeStarMap();
  if (mapCamera.home && !mapCamera.anim) Object.assign(mapCamera, mapHome());
  applyCamera();
  startMapMotion();
  restoreFocus(svg, keepFocus);
  renderStarMapCard();
}

//: One planet from an orbit in `/orbits` and its entry in `/horizon/topology`. Every field the map
//: reads has to be carried here: this copied `tags` (the top few, for display) and not `all_tags`,
//: so the lens fix on the server changed nothing on screen and pressing a tag still dimmed the
//: planet that held it.
function starMapOrbit(o, topo) {
  const filed = topo || { captures: 0, undistilled: 0, last_filed_at: 0, entities: [], tags: [], all_tags: [] };
  return {
    id: o.id, slug: o.slug,
    title: o.title || o.derived_title || t("app.untitled", "Untitled orbit"),
    sources: o.source_count,
    captures: filed.captures,
    undistilled: filed.undistilled,
    entities: filed.entities,
    tags: filed.tags,
    allTags: filed.all_tags || filed.tags || [],
    moons: filed.moons || [],
    recency: Math.max(o.updated_at || 0, filed.last_filed_at || 0),
  };
}

//: Lenses dim the planets none of whose captures carry any of the tags, matched against every tag
//: the orbit holds, not only the few it shows.
function dimmedByLens(planet, lenses) {
  return lenses.size > 0 && !(planet.allTags || []).some((tag) => lenses.has(tag));
}

//: The same question one level down: which moon lit the planet. A moon carrying a lensed tag is
//: marked, every other moon fades, so the reader sees which capture the tag came from.
function moonLensClass(item, lenses) {
  if (!lenses.size) return "";
  if (item && item.kind !== "local" && (item.tags || []).some((tag) => lenses.has(tag))) return " is-lensed";
  return " is-faded";
}

async function enterOrbit(orbit) {
  await openOrbit(orbit.id);
}

function syncStarMapContext({ follow = true } = {}) {
  // A map fetch that lands after the reader has gone into an orbit must not take the dock's scope
  // from the graph they are now looking at.
  if (document.body.dataset.view !== "horizon" || viewMode("horizon") !== "map") return;
  const chips = [];
  const orbit = starMap.orbits.find((o) => o.slug === starMap.selected);
  if (orbit) chips.push({ id: `orbit:${orbit.slug}`, orbit: { id: orbit.id, slug: orbit.slug, title: orbit.title } });
  if (starMap.lenses.size) chips.push({ id: lensChipId(starMap.lenses), scope: lensScope(starMap.lenses) });
  setAskContext(chips, { follow });
}

// --- pointing at, opening and filing what the map draws -------------------------------------------
//
// Every moon and every dot around the Horizon is one capture. Pointing at one names it, clicking
// opens it in the card, and (next) dragging it onto a planet files it there. A hollow moon is a
// source added inside its orbit: it can be pointed at and opens its orbit, but it is not a capture.

//: A moon that is open in the card is marked on the moon itself, not on its planet. Its planet is
//: only the host: a faint dashed ring says where the moon lives, while the halo and the copper rim
//: stay the planet's own selection, so the two can never be mistaken for each other.
function isFocusedMoon(item) {
  return item.kind !== "local" && starMap.focus?.kind === "capture" && starMap.focus.id === item.id;
}

function planetMark(slug) {
  if (starMap.selected !== slug) return "";
  return starMap.focus?.kind === "capture" ? " is-host" : " is-selected";
}

function moonMark(x, y) {
  const mark = svgEl("g", { transform: `translate(${x} ${y})` }, "map-moon-mark");
  mark.appendChild(svgEl("circle", { r: 4 }, "map-moon-ping"));
  mark.appendChild(svgEl("circle", { r: 3.6 }, "map-moon-core"));
  return mark;
}

function moonClass(item) {
  if (!item) return "map-dot";
  if (item.kind === "local") return "map-dot is-local";
  if (item.state === "ready") return "map-dot is-done";
  if (item.state === "failed") return "map-dot is-failed";
  if (item.state === "queued" || item.state === "parsing" || item.state === "distilling") return "map-dot is-busy";
  return "map-dot";
}

function moonStateLabel(item) {
  if (item.kind === "local") return t("map.moonLocal", "Not in the Horizon yet");
  if (item.state === "ready") return t("map.legendDone", "Summarised");
  if (item.state === "failed") return t("map.moonFailed", "Could not be read");
  if (item.state === "queued" || item.state === "parsing") return t("map.moonReading", "Being read");
  if (item.state === "distilling") return t("map.moonSummarising", "Being summarised");
  return t("map.legendPending", "Not summarised yet");
}

//: A dot is 2.2 units across, far too small to point at, so each gets an invisible target around it.
function moonHit(x, y, item) {
  const hit = svgEl("circle", { cx: x, cy: y, r: 7 }, "map-hit");
  const owner = () => hit.closest(".map-planet, .map-hole");
  hit.addEventListener("pointerenter", () => {
    mapMotion.paused = true;
    const held = owner();
    if (held) held.classList.add("is-holding");
    hit.classList.add("is-pointed");
    showMapTip(hit, item.title || "", moonStateLabel(item));
  });
  hit.addEventListener("pointerleave", () => {
    const held = owner();
    // Moving from a moon onto its own planet stays inside the planet, which fires no new enter.
    const stillOnPlanet = held && held.matches(".map-planet:hover");
    if (!stillOnPlanet) mapMotion.paused = false;
    if (held && !stillOnPlanet) held.classList.remove("is-holding");
    hit.classList.remove("is-pointed");
    hideMapTip();
  });
  hit.addEventListener("click", (event) => {
    event.stopPropagation();
    hideMapTip();
    if (mapDrag.moved) return;
    if (item.kind === "local") {
      openMapFocus({ kind: "planet", orbit: item.orbit });
    } else {
      openMapFocus({ kind: "capture", id: item.id, title: item.title, state: item.state, orbit: item.orbit || null });
    }
  });
  hit.addEventListener("pointerdown", (event) => startMoonDrag(event, item, hit));
  return hit;
}

//: Dragging a capture onto a planet files it there. Planets it can go to light up while it is
//: carried, and everything holds still so the target stays put. A drag that ends anywhere else
//: files nothing. A hollow moon is not a capture and cannot be carried.
const mapDrag = { item: null, id: null, start: null, moved: false, ghost: null, over: null, redraw: false };

function worldAt(clientX, clientY) {
  const v = clientToView(horizonEl("starmap-svg"), clientX, clientY);
  return {
    x: mapCamera.x + (v.x - MAP_VIEW_CENTRE.x) / mapCamera.k,
    y: mapCamera.y + (v.y - MAP_VIEW_CENTRE.y) / mapCamera.k,
  };
}

function planetUnder(point, exclude = []) {
  const scene = starMap.scene;
  if (!scene) return null;
  let best = null;
  scene.planets.forEach((entry) => {
    if (exclude.includes(entry.p.orbit.slug)) return;
    const pos = planetAt(entry.p);
    const d = Math.hypot(point.x - pos.x, point.y - pos.y);
    if (d <= entry.p.r + 16 && (!best || d < best.d)) best = { entry, d };
  });
  return best && best.entry;
}

//: A short tween on the animation frame, resolving when done; instant under reduced motion.
function mapTween(ms, step, ease = (u) => u) {
  if (!motionAllowed()) {
    step(1);
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const start = performance.now();
    const frame = (now) => {
      const u = Math.min(1, (now - start) / ms);
      step(ease(u));
      if (u < 1) requestAnimationFrame(frame);
      else resolve();
    };
    requestAnimationFrame(frame);
  });
}

const easeIn = (u) => u * u * u;
const easeOutBack = (u) => 1 + 2.2 * Math.pow(u - 1, 3) + 1.2 * Math.pow(u - 1, 2);

//: Carrying a capture, drawn like a pin being pulled off a map: on pickup the dot lifts (it grows,
//: and a shadow drops away beneath it), it trails the pointer with a little lag and stretches along
//: the way it is moving, and it leans toward a planet it may land on. Dropped on one it falls in
//: and the planet ripples; dropped anywhere else it springs back to where it was lifted from.
function startMoonDrag(event, item, hit) {
  if (event.button !== 0 || item.kind !== "capture") return;
  event.stopPropagation();
  event.preventDefault(); // a carry, not a text selection
  mapDrag.item = item;
  mapDrag.id = event.pointerId;
  mapDrag.start = { x: event.clientX, y: event.clientY };
  mapDrag.moved = false;
  // Every orbit it is already in: none of them is somewhere to put it.
  const already = [...(item.orbits || []), item.orbit].filter(Boolean);
  const dot = hit.previousElementSibling;
  const box = hit.getBoundingClientRect();
  const home = worldAt(box.left + box.width / 2, box.top + box.height / 2);
  const carry = { pos: { ...home }, target: { ...home }, frame: 0, group: null, body: null };
  hit.setPointerCapture(event.pointerId);

  const follow = () => {
    const dx = carry.target.x - carry.pos.x;
    const dy = carry.target.y - carry.pos.y;
    carry.pos.x += dx * 0.35;
    carry.pos.y += dy * 0.35;
    const speed = Math.min(0.45, Math.hypot(dx, dy) / 40);
    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
    carry.group.setAttribute("transform", `translate(${carry.pos.x.toFixed(1)} ${carry.pos.y.toFixed(1)})`);
    carry.body.setAttribute("transform",
      `rotate(${angle.toFixed(1)}) scale(${(1 + speed).toFixed(3)} ${(1 - speed * 0.5).toFixed(3)})`);
    carry.frame = requestAnimationFrame(follow);
  };

  const move = (e) => {
    if (e.pointerId !== mapDrag.id) return;
    if (!mapDrag.moved) {
      if (Math.hypot(e.clientX - mapDrag.start.x, e.clientY - mapDrag.start.y) < 5) return;
      mapDrag.moved = true;
      mapMotion.paused = true;
      hideMapTip();
      horizonEl("starmap-svg").classList.add("is-carrying");
      if (dot) dot.classList.add("is-lifted");
      starMap.scene.planets.forEach(({ p, group }) => {
        if (!already.includes(p.orbit.slug)) group.classList.add("is-drop-target");
      });
      carry.group = svgEl("g", {}, "map-carry");
      carry.group.appendChild(svgEl("ellipse", { cx: 0, cy: 9, rx: 5, ry: 1.8 }, "map-carry-shadow"));
      const lift = svgEl("g", {}, "map-carry-lift");
      carry.body = svgEl("g", {});
      carry.body.appendChild(svgEl("circle", { r: 4 }, `map-carry-body ${moonClass(item).replace("map-dot", "")}`));
      lift.appendChild(carry.body);
      carry.group.appendChild(lift);
      starMap.world.appendChild(carry.group);
      carry.frame = requestAnimationFrame(follow);
    }
    const at = worldAt(e.clientX, e.clientY);
    const under = planetUnder(at, already);
    if (mapDrag.over && mapDrag.over !== under) mapDrag.over.group.classList.remove("is-drop-hover");
    mapDrag.over = under;
    if (under) {
      under.group.classList.add("is-drop-hover");
      // Lean toward the planet it would land on, a third of the way.
      const c = planetAt(under.p);
      carry.target = { x: at.x + (c.x - at.x) * 0.35, y: at.y + (c.y - at.y) * 0.35 };
    } else {
      carry.target = at;
    }
  };

  const settle = () => {
    horizonEl("starmap-svg").classList.remove("is-carrying");
    if (starMap.scene) {
      starMap.scene.planets.forEach(({ group }) => group.classList.remove("is-drop-target", "is-drop-hover"));
    }
    mapMotion.paused = false;
    mapDrag.id = null;
    mapDrag.over = null;
    setTimeout(() => { mapDrag.moved = false; }, 0);
    if (mapDrag.redraw) {
      mapDrag.redraw = false;
      drawStarMap();
    }
  };

  const end = async (e) => {
    if (e.pointerId !== mapDrag.id) return;
    hit.removeEventListener("pointermove", move);
    hit.removeEventListener("pointerup", end);
    hit.removeEventListener("pointercancel", end);
    hit.removeEventListener("lostpointercapture", end);
    const target = e.type === "pointerup" ? mapDrag.over : null;
    mapDrag.id = -1; // still busy animating: a repaint waits until the carry is put down
    cancelAnimationFrame(carry.frame);
    if (carry.group) {
      const from = { ...carry.pos };
      if (target) {
        const c = planetAt(target.p);
        await mapTween(260, (u) => {
          carry.group.setAttribute("transform",
            `translate(${(from.x + (c.x - from.x) * u).toFixed(1)} ${(from.y + (c.y - from.y) * u).toFixed(1)}) scale(${(1 - 0.7 * u).toFixed(3)})`);
        }, easeIn);
        carry.group.remove();
        const ripple = svgEl("circle", { cx: c.x, cy: c.y, r: target.p.r }, "map-ripple");
        starMap.world.appendChild(ripple);
        setTimeout(() => ripple.remove(), 700);
      } else {
        await mapTween(340, (u) => {
          carry.group.setAttribute("transform",
            `translate(${(from.x + (home.x - from.x) * u).toFixed(1)} ${(from.y + (home.y - from.y) * u).toFixed(1)})`);
        }, easeOutBack);
        carry.group.remove();
      }
    }
    if (dot) dot.classList.remove("is-lifted");
    settle();
    if (!target) return;
    // From a planet it is a move; from around the Horizon it is filing.
    if (item.orbit) void moveCapture(item, target.p.orbit);
    else void fileCapture(item.id, target.p.orbit.id);
  };
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerup", end);
  hit.addEventListener("pointercancel", end);
  // Losing the pointer (the window lost focus, the element went away) ends the carry, filing nothing.
  hit.addEventListener("lostpointercapture", end);
}

//: Moves a capture from the planet it was carried off to another. When saved citations in the
//: orbit it leaves point at it, the reader is told how many before anything changes: those
//: citations go unverified once its source is gone (its id is never reused).
async function moveCapture(item, to, { confirm = false } = {}) {
  const fromTitle = orbitTitles.get(item.orbit) || t("suggest.anOrbit", "an orbit");
  let moved;
  try {
    moved = await api(`/horizon/${encodeURIComponent(item.id)}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from_orbit: item.orbit, to_orbit: to.id, confirm }),
    });
  } catch (err) {
    if (err.status === 409 && !confirm) {
      const n = Number((String(err.message).match(/(\d+) saved citations/) || [])[1] || 0);
      const ok = await confirmAction(t("map.moveCited",
        `${n} saved citations in ${fromTitle} point at this. Moving it out leaves them unverified. Move it anyway?`,
        { n, from: fromTitle }));
      if (ok) await moveCapture(item, to, { confirm: true });
      return;
    }
    notify(readableError(err.message));
    return;
  }
  renderCaptureCard.cache = null;
  notify(t("map.moved", `Moved to ${to.title}.`, { name: to.title }), {
    tone: "good",
    timeout: 8000,
    action: moved.removed ? {
      label: t("map.undo", "Undo"),
      run: () => void moveCapture({ ...item, orbit: to.slug }, { id: item.orbit, slug: item.orbit, title: fromTitle },
        { confirm: true }),
    } : null,
  });
  if (!moved.removed) {
    notify(t("map.moveKept", `It was added to ${to.title} but could not be taken out of ${fromTitle}.`,
      { name: to.title, from: fromTitle }));
  }
  void refreshHorizon();
  void renderStarMap();
}

function showMapTip(target, title, sub) {
  const tip = horizonEl("starmap-tip");
  const host = horizonEl("starmap").getBoundingClientRect();
  const box = target.getBoundingClientRect();
  tip.textContent = "";
  tip.appendChild(elt("span", "map-tip-title", shortLabel(title, 60)));
  tip.appendChild(elt("span", "map-tip-sub", sub));
  tip.hidden = false;
  const x = box.left + box.width / 2 - host.left;
  const y = box.top - host.top;
  tip.style.left = `${Math.round(x)}px`;
  tip.style.top = `${Math.round(y)}px`;
}

function hideMapTip() {
  const tip = horizonEl("starmap-tip");
  if (tip) tip.hidden = true;
}

//: What the map is showing in its card, and where the camera goes for it. A planet or a capture
//: filed in one brings the camera to that planet; the Horizon brings it home.
function openMapFocus(focus) {
  if (focus.kind === "planet") {
    starMap.selected = focus.orbit;
    starMap.focus = null;
  } else {
    starMap.selected = focus.kind === "capture" ? focus.orbit : null;
    starMap.focus = focus;
  }
  if (mapPanelGrip && mapPanelGrip.isCollapsed()) mapPanelGrip.setCollapsed(false, { persist: false });
  drawStarMap();
  syncStarMapContext();
  if (starMap.selected) focusCameraOn(starMap.selected);
  else cameraHome();
}

function closeMapFocus() {
  starMap.selected = null;
  // Closing a capture opened from the lens card goes back to that card while the lenses are on.
  starMap.focus = starMap.lenses.size ? { kind: "lens" } : null;
  drawStarMap();
  syncStarMapContext();
  cameraHome();
}

// --- the camera ------------------------------------------------------------------------------------
//
// One transform on the world group: the world point at the centre of the view, and a zoom. Moving
// to a planet is a short eased glide rather than a jump, so the reader keeps their bearings; with
// reduced motion it is a jump.

const MAP_VIEW_CENTRE = { x: 500, y: 320 };
const MAP_ZOOM = { min: 0.3, max: 4, planet: 1.8 };
//: `home` is true while the camera shows the whole map and nobody has moved it; a map that grows a
//: ring then stays wholly in view without taking a camera the reader placed.
const mapCamera = { x: 500, y: 320, k: 1, anim: 0, home: true };

function applyCamera() {
  const world = starMap.world;
  if (!world) return;
  const { x, y, k } = mapCamera;
  world.setAttribute("transform",
    `translate(${MAP_VIEW_CENTRE.x} ${MAP_VIEW_CENTRE.y}) scale(${k.toFixed(4)}) translate(${(-x).toFixed(2)} ${(-y).toFixed(2)})`);
  const h = mapHome();
  const home = Math.abs(k - h.k) < 0.01 && Math.abs(x - h.x) < 1 && Math.abs(y - h.y) < 1;
  const reset = horizonEl("map-zoom-home");
  if (reset) reset.disabled = home;
}

function clampCamera(c) {
  const k = Math.min(MAP_ZOOM.max, Math.max(MAP_ZOOM.min, c.k));
  return { k, x: Math.min(1000, Math.max(0, c.x)), y: Math.min(640, Math.max(0, c.y)) };
}

function setCamera(c) {
  hideMapTip();
  cancelAnimationFrame(mapCamera.anim);
  mapCamera.anim = 0;
  Object.assign(mapCamera, clampCamera(c));
  applyCamera();
}

function animateCamera(target, ms = 620) {
  const to = clampCamera(target);
  cancelAnimationFrame(mapCamera.anim);
  if (!motionAllowed()) {
    setCamera(to);
    return;
  }
  const from = { x: mapCamera.x, y: mapCamera.y, k: mapCamera.k };
  const started = performance.now();
  const ease = (u) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);
  const step = (now) => {
    const u = Math.min(1, (now - started) / ms);
    const e = ease(u);
    mapCamera.x = from.x + (to.x - from.x) * e;
    mapCamera.y = from.y + (to.y - from.y) * e;
    // Zoom is interpolated in log space, so doubling feels the same speed at any scale.
    mapCamera.k = Math.exp(Math.log(from.k) + (Math.log(to.k) - Math.log(from.k)) * e);
    applyCamera();
    mapCamera.anim = u < 1 ? requestAnimationFrame(step) : 0;
  };
  mapCamera.anim = requestAnimationFrame(step);
}

function cameraHome() {
  mapMotion.held = false;
  mapCamera.home = true;
  animateCamera(mapHome());
}

//: The planet stops where it is while the camera is on it (`held`), centred: the details are in a
//: column of their own now, so nothing covers the middle of the map.
function focusCameraOn(slug) {
  const entry = starMap.scene && starMap.scene.planets.find(({ p }) => p.orbit.slug === slug);
  if (!entry) return;
  mapMotion.held = true;
  mapCamera.home = false;
  const pos = planetAt(entry.p);
  animateCamera({ x: pos.x, y: pos.y, k: MAP_ZOOM.planet });
}

function zoomBy(factor, around) {
  mapCamera.home = false;
  const k = Math.min(MAP_ZOOM.max, Math.max(MAP_ZOOM.min, mapCamera.k * factor));
  const v = around || MAP_VIEW_CENTRE;
  // Keep the world point under `around` where it is on screen.
  const wx = mapCamera.x + (v.x - MAP_VIEW_CENTRE.x) / mapCamera.k;
  const wy = mapCamera.y + (v.y - MAP_VIEW_CENTRE.y) / mapCamera.k;
  setCamera({ k, x: wx - (v.x - MAP_VIEW_CENTRE.x) / k, y: wy - (v.y - MAP_VIEW_CENTRE.y) / k });
}

//: A pointer position in the SVG's own units (its viewBox), whatever size it is drawn at.
function clientToView(svg, clientX, clientY) {
  const ctm = svg.getScreenCTM();
  if (!ctm) return { ...MAP_VIEW_CENTRE };
  const point = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
  return { x: point.x, y: point.y };
}

const mapPan = { id: null, start: null, moved: false };

//: In the desktop app the webview's own context menu offered Reload and Back, which belong to a
//: browser: Back landed on the shell's splash page. It is kept where it does something for the
//: reader (a text field, selected text, a link) and dropped everywhere else. A browser tab keeps it.
function initDesktopContextMenu() {
  document.addEventListener("contextmenu", (event) => {
    if (!isDesktopShell()) return;
    if (event.target.closest("input, textarea, [contenteditable], a[href]")) return;
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) return;
    event.preventDefault();
  });
}

function initStarMapCamera() {
  const svg = horizonEl("starmap-svg");
  if (!svg || svg.dataset.camera) return;
  svg.dataset.camera = "on";
  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const factor = Math.exp(-event.deltaY * (event.ctrlKey ? 0.01 : 0.0015));
    zoomBy(factor, clientToView(svg, event.clientX, event.clientY));
  }, { passive: false });
  svg.addEventListener("pointerdown", (event) => {
    if (event.button !== 0
      || event.target.closest(".map-planet, .map-hit, .map-hole-hit, .map-hole-sub, .map-bridge-hit, .map-bridge-label")) return;
    event.preventDefault(); // no text selection starting under a pan
    mapPan.id = event.pointerId;
    mapPan.start = { cx: event.clientX, cy: event.clientY, x: mapCamera.x, y: mapCamera.y };
    mapPan.moved = false;
  });
  svg.addEventListener("pointermove", (event) => {
    if (mapPan.id !== event.pointerId || !mapPan.start) return;
    const dx = event.clientX - mapPan.start.cx;
    const dy = event.clientY - mapPan.start.cy;
    if (!mapPan.moved && Math.hypot(dx, dy) < 4) return;
    if (!mapPan.moved) {
      mapPan.moved = true;
      mapCamera.home = false;
      svg.setPointerCapture(event.pointerId);
      svg.classList.add("is-panning");
    }
    const scale = (svg.getScreenCTM() || { a: 1 }).a || 1;
    setCamera({ k: mapCamera.k, x: mapPan.start.x - dx / scale / mapCamera.k, y: mapPan.start.y - dy / scale / mapCamera.k });
  });
  const endPan = (event) => {
    if (mapPan.id !== event.pointerId) return;
    const wasPan = mapPan.moved;
    mapPan.id = null;
    mapPan.start = null;
    svg.classList.remove("is-panning");
    // A click on empty space, not the end of a pan, closes the card.
    if (!wasPan && event.type === "pointerup" && (starMap.selected || starMap.focus)) closeMapFocus();
  };
  svg.addEventListener("pointerup", endPan);
  svg.addEventListener("pointercancel", endPan);
  horizonEl("starmap").addEventListener("keydown", (event) => {
    if (event.target.closest("input, select, textarea")) return;
    if (event.key === "+" || event.key === "=") zoomBy(1.25);
    else if (event.key === "-" || event.key === "_") zoomBy(0.8);
    else if (event.key === "0") cameraHome();
    else if (event.key === "Escape" && (starMap.selected || starMap.focus || mapCamera.k !== 1)) closeMapFocus();
    else return;
    event.preventDefault();
  });
  horizonEl("map-zoom-in").addEventListener("click", () => zoomBy(1.25));
  horizonEl("map-zoom-out").addEventListener("click", () => zoomBy(0.8));
  horizonEl("map-zoom-home").addEventListener("click", () => closeMapFocus());
}

// --- the card for the Horizon and for one capture ---------------------------------------------------

function mapCardClose(card) {
  const close = elt("button", "card-close", "×");
  close.type = "button";
  close.setAttribute("aria-label", t("map.closeCard", "Close"));
  close.title = t("map.closeCard", "Close");
  close.addEventListener("click", closeMapFocus);
  card.appendChild(close);
}

//: "File into…" for one capture. Only orbits it is not already in are offered.
function filePicker(nodeId, orbits = starMap.orbits) {
  const picker = document.createElement("select");
  picker.className = "card-file";
  picker.setAttribute("aria-label", t("map.fileInto", "File into…"));
  picker.appendChild(new Option(t("map.fileInto", "File into…"), ""));
  orbits.forEach((o) => picker.appendChild(new Option(o.title, o.id)));
  picker.addEventListener("change", () => {
    if (picker.value) void fileCapture(nodeId, picker.value, picker);
  });
  return picker;
}

async function fileCapture(nodeId, orbitId, control) {
  if (control) control.disabled = true;
  let filed;
  try {
    filed = await api(`/horizon/${encodeURIComponent(nodeId)}/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ orbit_id: orbitId, create: false }),
    });
  } catch (err) {
    if (control) control.disabled = false;
    notify(readableError(err.message));
    return false;
  }
  const orbit = starMap.orbits.find((o) => o.id === orbitId);
  const name = orbit ? orbit.title : t("suggest.anOrbit", "an orbit");
  // Undo only for a source THIS filing added: promotion returns the one already there when the
  // capture was filed in that orbit or the orbit holds the same text, and deleting that one would
  // remove a source that may be cited.
  const sourceId = filed && filed.appended && filed.membership && filed.membership.source_id;
  renderCaptureCard.cache = null;
  notify(t("map.filed", `Filed into ${name}.`, { name }), {
    tone: "good",
    timeout: 8000,
    // Undo takes the source out of the orbit again, which also drops the filing (and keeps it
    // from being suggested straight back).
    action: sourceId ? {
      label: t("map.undo", "Undo"),
      run: async () => {
        try {
          await api(`/orbits/${encodeURIComponent(orbitId)}/sources/${encodeURIComponent(sourceId)}`, { method: "DELETE" });
        } catch (err) {
          notify(readableError(err.message));
        }
        renderCaptureCard.cache = null;
        void refreshHorizon();
        void renderStarMap();
      },
    } : null,
  });
  // Straight to the map, not through `refreshHorizon`'s three-second throttle: a second filing or
  // an Undo inside that window left the moon where it was and the capture still listed as loose.
  void refreshHorizon();
  void renderStarMap();
  return true;
}

function renderHorizonCard(card, { standing = false } = {}) {
  const loose = (starMap.data && starMap.data.loose) || { count: 0, items: [] };
  // The standing summary has nothing to close back to.
  if (!standing) mapCardClose(card);
  card.appendChild(elt("p", "card-kicker", t("horizon.home", "Horizon")));
  card.appendChild(elt("h2", "card-title", t("map.loose", `${loose.count} not in an orbit`, { n: loose.count })));
  if (!loose.count) {
    card.appendChild(elt("p", "card-note", t("map.looseNone", "Everything you kept is in an orbit.")));
    return;
  }
  card.appendChild(elt("p", "card-note", t("map.looseHelp", "File each into an orbit here, or drag its dot onto a planet.")));
  const list = elt("ul", "card-list");
  (loose.items || []).forEach((item) => {
    const row = elt("li", "card-row");
    const name = elt("button", "card-row-title", item.title);
    name.type = "button";
    name.addEventListener("click", () => openMapFocus({ kind: "capture", ...item, orbit: null }));
    row.appendChild(name);
    row.appendChild(filePicker(item.id));
    list.appendChild(row);
  });
  card.appendChild(list);
  if (loose.count > (loose.items || []).length) {
    card.appendChild(elt("p", "card-note", t("map.looseMore", `The newest ${(loose.items || []).length} are shown; the list view has them all.`,
      { n: (loose.items || []).length })));
  }
}

//: The link between two planets: what they both name, and side by side, the captures on each side
//: that name the entity in focus. The question it offers is the reason to open it: how do these two
//: orbits each talk about this, asked over just the captures that name it on both sides.
function renderBridgeCard(card, focus) {
  mapCardClose(card);
  const titleA = orbitTitles.get(focus.a) || t("suggest.anOrbit", "an orbit");
  const titleB = orbitTitles.get(focus.b) || t("suggest.anOrbit", "an orbit");
  card.appendChild(elt("p", "card-kicker", t("map.bridgeKicker", "What two orbits share")));
  card.appendChild(elt("h2", "card-title", `${titleA} \u2194 ${titleB}`));
  const detail = elt("div", "card-detail");
  detail.appendChild(elt("p", "card-note", t("map.loading", "Loading\u2026")));
  card.appendChild(detail);
  const token = (renderBridgeCard.token = (renderBridgeCard.token || 0) + 1);
  void (async () => {
    let got;
    try {
      got = await api(`/horizon/bridge?a=${encodeURIComponent(focus.a)}&b=${encodeURIComponent(focus.b)}`);
    } catch (err) {
      if (token === renderBridgeCard.token) detail.replaceChildren(elt("p", "card-note", readableError(err.message)));
      return;
    }
    if (token !== renderBridgeCard.token || !detail.isConnected) return;
    const shared = got.shared || [];
    if (!shared.length) {
      detail.replaceChildren(elt("p", "card-note", t("map.bridgeNone", "They no longer name anything in common.")));
      return;
    }
    const chosen = shared.find((s) => s.name === focus.entity) || shared[0];
    detail.textContent = "";
    detail.appendChild(elt("h3", "card-section", t("map.bridgeShared", "Both name")));
    const chips = elt("div", "card-chips");
    shared.forEach((s) => {
      const chip = elt("button", "card-chip", s.name);
      chip.type = "button";
      chip.setAttribute("aria-pressed", String(s === chosen));
      chip.addEventListener("click", () => {
        starMap.focus = { ...focus, entity: s.name };
        renderStarMapCard();
      });
      chips.appendChild(chip);
    });
    detail.appendChild(chips);
    const sides = elt("div", "bridge-sides");
    [[titleA, focus.a, chosen.a], [titleB, focus.b, chosen.b]].forEach(([title, slugKey, items]) => {
      const side = elt("div", "bridge-side");
      side.appendChild(elt("h3", "card-section", title));
      const list = elt("ul", "card-list");
      items.forEach((item) => {
        const row = elt("li", "card-row");
        const name = elt("button", "card-row-title", item.title);
        name.type = "button";
        name.addEventListener("click", () => openMapFocus({ kind: "capture", id: item.id, title: item.title, state: "ready", orbit: slugKey }));
        row.appendChild(name);
        list.appendChild(row);
      });
      side.appendChild(list);
      sides.appendChild(side);
    });
    detail.appendChild(sides);
    const ask = elt("button", "btn btn-primary card-enter",
      t("map.bridgeAsk", `Ask how both talk about ${chosen.name}`, { name: chosen.name }));
    ask.type = "button";
    ask.addEventListener("click", () => askAcrossBridge(focus, chosen.name, titleA, titleB));
    detail.appendChild(ask);
  })();
}

//: What the lenses light, answered without opening anything: every capture carrying one of the
//: tags, with its summary, which of the tags it carries and the orbits it is in. This is the point
//: of the product: the reader sees why a planet lit, and what each capture says, at a glance.
function renderLensCard(card) {
  const close = elt("button", "card-close", "×");
  close.type = "button";
  close.setAttribute("aria-label", t("lens.clearAll", "Clear the tags"));
  close.title = t("lens.clearAll", "Clear the tags");
  close.addEventListener("click", () => {
    starMap.lenses = new Set();
    starMap.focus = null;
    paintStarMapLenses();
    drawStarMap();
    syncStarMapContext();
  });
  card.appendChild(close);
  const names = [...starMap.lenses];
  card.appendChild(elt("p", "card-kicker", names.length > 1
    ? t("lens.kickerMany", "What these tags light")
    : t("lens.kickerOne", "What this tag lights")));
  const heading = elt("div", "lens-heading");
  names.forEach((name) => {
    const chip = elt("button", "lens-chosen", `#${name}`);
    chip.type = "button";
    chip.setAttribute("aria-label", t("lens.remove", `Remove #${name}`, { name }));
    chip.appendChild(elt("span", "lens-chosen-x", "×"));
    chip.addEventListener("click", () => {
      starMap.lenses = toggledLenses(starMap.lenses, name);
      starMap.focus = starMap.lenses.size ? { kind: "lens" } : null;
      paintStarMapLenses();
      drawStarMap();
      syncStarMapContext();
    });
    heading.appendChild(chip);
  });
  card.appendChild(heading);
  const detail = elt("div", "card-detail");
  detail.appendChild(elt("p", "card-note", t("map.loading", "Loading\u2026")));
  card.appendChild(detail);
  const token = (renderLensCard.token = (renderLensCard.token || 0) + 1);
  void (async () => {
    let got;
    try {
      got = await api(`/horizon/lens?${names.map((n) => `tag=${encodeURIComponent(n)}`).join("&")}`);
    } catch (err) {
      if (token === renderLensCard.token) detail.replaceChildren(elt("p", "card-note", readableError(err.message)));
      return;
    }
    if (token !== renderLensCard.token || !detail.isConnected) return;
    detail.textContent = "";
    detail.appendChild(elt("p", "card-meta", names.length > 1
      ? t("lens.countMany", `${got.total} captures carry at least one of them`, { n: got.total })
      : t("lens.countOne", `${got.total} captures carry it`, { n: got.total })));
    const list = elt("ul", "lens-list");
    (got.captures || []).forEach((item) => {
      const row = elt("li", "lens-item");
      const title = elt("button", "lens-item-title", item.title);
      title.type = "button";
      title.addEventListener("click", () => openMapFocus({
        kind: "capture", id: item.id, title: item.title, state: item.state, orbit: item.orbits[0] || null,
      }));
      row.appendChild(title);
      row.appendChild(elt("p", "lens-item-summary", item.summary
        || t("lens.noSummary", "Not summarised yet, so only its tags are known.")));
      const meta = elt("div", "lens-item-meta");
      if (names.length > 1) item.matched.forEach((name) => meta.appendChild(elt("span", "lens-item-tag", `#${name}`)));
      item.orbits.forEach((key) => meta.appendChild(elt("span", "lens-item-orbit",
        orbitTitles.get(key) || t("suggest.anOrbit", "an orbit"))));
      if (!item.orbits.length) meta.appendChild(elt("span", "lens-item-orbit is-loose", t("lens.loose", "Not in an orbit")));
      row.appendChild(meta);
      list.appendChild(row);
    });
    detail.appendChild(list);
    if (got.total > (got.captures || []).length) {
      detail.appendChild(elt("p", "card-note", t("lens.more", `And ${got.total - got.captures.length} more.`,
        { n: got.total - got.captures.length })));
    }
    if (got.total) {
      const ask = elt("button", "btn btn-primary card-enter", names.length > 1
        ? t("lens.askMany", "Ask about everything these tags light")
        : t("lens.askOne", "Ask about everything this tag lights"));
      ask.type = "button";
      ask.addEventListener("click", () => {
        askH.custom = { id: "custom", scope: lensScope(starMap.lenses) };
        askH.chips = askH.chips.filter((chip) => chip.id !== "custom");
        askH.chips.push(askH.custom);
        askH.chosen = "custom";
        renderAskHChips();
        dismissAskHPlan();
        syncAskHComposer();
        openDock();
        horizonEl("ask-h-input").focus();
      });
      detail.appendChild(ask);
    }
  })();
}

//: Sets the dock to the entity across both orbits, writes the question, and opens it. Nothing is
//: spent: Enter still previews what it would read, free, first (invariant 47).
function askAcrossBridge(focus, name, titleA, titleB) {
  askH.custom = { id: "custom", scope: { kind: "entity", value: name, orbits: [focus.a, focus.b] } };
  askH.chips = askH.chips.filter((chip) => chip.id !== "custom");
  askH.chips.push(askH.custom);
  askH.chosen = "custom";
  renderAskHChips();
  dismissAskHPlan();
  const input = horizonEl("ask-h-input");
  input.value = t("map.bridgeQuestion", `How do ${titleA} and ${titleB} each talk about ${name}, and where do they differ?`,
    { a: titleA, b: titleB, name });
  syncAskHComposer();
  openDock();
}

//: A capture's card fills in after one fetch; the part known from the map is drawn at once.
function renderCaptureCard(card, focus) {
  mapCardClose(card);
  card.appendChild(elt("p", "card-kicker", moonStateLabel({ kind: "capture", state: focus.state })));
  card.appendChild(elt("h2", "card-title", focus.title || ""));
  const detail = elt("div", "card-detail");
  detail.appendChild(elt("p", "card-note", t("map.loading", "Loading…")));
  card.appendChild(detail);
  const token = (renderCaptureCard.token = (renderCaptureCard.token || 0) + 1);
  // The map redraws for many reasons; the capture it shows only changes when the focus does. Kept
  // by id, so a redraw repaints from memory instead of flashing "Loading" over an open picker.
  const cached = renderCaptureCard.cache && renderCaptureCard.cache.id === focus.id ? renderCaptureCard.cache.got : null;
  void (async () => {
    let got = cached;
    if (!got) {
      try {
        got = await api(`/horizon/${encodeURIComponent(focus.id)}`);
      } catch (err) {
        if (token === renderCaptureCard.token) detail.replaceChildren(elt("p", "card-note", readableError(err.message)));
        return;
      }
      renderCaptureCard.cache = { id: focus.id, got };
    }
    if (token !== renderCaptureCard.token || !detail.isConnected) return;
    const node = got.node || {};
    detail.textContent = "";
    if (node.summary) detail.appendChild(elt("p", "card-summary", node.summary));
    const names = [...(node.entities || []), ...(node.tags || []).map((tag) => `#${tag}`)];
    if (names.length) {
      const chips = elt("div", "card-chips");
      names.slice(0, 10).forEach((name) => chips.appendChild(elt("span", "card-chip", name)));
      detail.appendChild(chips);
    }
    // Memberships name an orbit by its key, which is only ever looked up: into its label for the
    // "In …" line, and out of the orbits the picker offers (invariant 37).
    const memberships = got.orbits || [];
    const offer = new Map(starMap.orbits.map((o) => [o.slug, o]));
    memberships.forEach((m) => offer.delete(m.orbit_id));
    const where = memberships.map((m) => orbitTitles.get(m.orbit_id) || t("suggest.anOrbit", "an orbit"));
    if (where.length) {
      const joined = where.join(t("list.sep", ", "));
      detail.appendChild(elt("p", "card-meta", t("map.filedIn", `In ${joined}`, { where: joined })));
    }
    const actions = elt("div", "card-actions");
    actions.appendChild(filePicker(focus.id, [...offer.values()]));
    const read = elt("button", "btn", t("map.readInList", "Read it"));
    read.type = "button";
    read.addEventListener("click", () => revealNode(focus.id));
    actions.appendChild(read);
    detail.appendChild(actions);
  })();
}

//: Opens one capture where its full text is read: the list, with that row open and in view.
function revealNode(nodeId) {
  horizonState.open.add(nodeId);
  setViewMode("horizon", "list");
  let tries = 0;
  const find = () => {
    const row = document.querySelector(`.node[data-node-id="${CSS.escape(nodeId)}"]`);
    if (!row) {
      if ((tries += 1) < 40) {
        setTimeout(find, 100);
      } else {
        horizonState.open.delete(nodeId);
        notify(t("map.notInList", "That capture is further down the list than it shows at once. Search for it by name there."),
          { tone: "info" });
      }
      return;
    }
    const open = row.querySelector(".node-open");
    if (open && !row.classList.contains("is-open")) open.click();
    row.scrollIntoView({ block: "center" });
    if (open) open.focus();
  };
  find();
}

function renderStarMapCard() {
  const mapCard = horizonEl("starmap-card");
  // A button in the card that rebuilt the card took keyboard focus with it to <body>, where the
  // map's keys no longer reach. Focus goes back into the new card instead.
  const hadFocus = mapCard.contains(document.activeElement);
  paintStarMapCard(mapCard);
  if (hadFocus && !mapCard.hidden) {
    const into = mapCard.querySelector(".card-close");
    if (into) into.focus();
  }
}

function paintStarMapCard(mapCard) {
  mapCard.textContent = "";
  if (starMap.focus && starMap.focus.kind === "horizon") {
    renderHorizonCard(mapCard);
    mapCard.hidden = false;
    return;
  }
  if (starMap.focus && starMap.focus.kind === "capture") {
    renderCaptureCard(mapCard, starMap.focus);
    mapCard.hidden = false;
    return;
  }
  if (starMap.focus && starMap.focus.kind === "lens" && starMap.lenses.size) {
    renderLensCard(mapCard);
    mapCard.hidden = false;
    return;
  }
  if (starMap.focus && starMap.focus.kind === "bridge") {
    renderBridgeCard(mapCard, starMap.focus);
    mapCard.hidden = false;
    return;
  }
  const orbit = starMap.orbits.find((o) => o.slug === starMap.selected);
  if (!orbit) {
    // Nothing chosen: the panel shows the Horizon itself, which is where filing starts.
    renderHorizonCard(mapCard, { standing: true });
    mapCard.hidden = false;
    return;
  }
  // Choosing something opens a panel the reader had put away: that is what the click asked to see.
  if (mapPanelGrip && mapPanelGrip.isCollapsed()) mapPanelGrip.setCollapsed(false, { persist: false });
  mapCardClose(mapCard);
  mapCard.appendChild(elt("p", "card-kicker", relativeTime(orbit.recency)));
  mapCard.appendChild(elt("h2", "card-title", orbit.title));
  mapCard.appendChild(elt("p", "card-meta", orbit.captures
    ? t("map.cardCounts", `${orbit.sources} sources, ${orbit.captures} filed from the Horizon`,
      { n: orbit.sources, m: orbit.captures })
    : t("map.planetCount", `${orbit.sources} sources`, { n: orbit.sources })));
  // Two sections with headings. Without them the entity names (styled as chips) and the captures
  // (a list) read as one undifferentiated column of things to click, and a reader could not tell
  // what either was.
  if (orbit.entities.length) {
    mapCard.appendChild(elt("h3", "card-section", t("map.sectionNames", "What it talks about")));
    const chips = elt("div", "card-chips");
    orbit.entities.forEach((name) => chips.appendChild(elt("span", "card-chip", name)));
    mapCard.appendChild(chips);
  } else {
    //: Entities come only from summaries of captures filed from the Horizon. A source added inside
    //: the orbit is not a capture, and "nothing has been summarised yet" over it promised something
    //: no summary pass would ever deliver.
    let why;
    if (!orbit.captures) {
      why = t("map.noCaptures", "No entities: its sources were added in the orbit, and entities come from summaries of captures filed from the Horizon.");
    } else if (orbit.undistilled) {
      why = t("map.noEntitiesWaiting", `No entities yet: ${orbit.undistilled} filed here still wait for a summary.`,
        { n: orbit.undistilled });
    } else {
      why = t("map.noEntitiesNamed", "No entities: the summaries here did not name any.");
    }
    mapCard.appendChild(elt("p", "card-note", why));
  }
  // Its captures by name, the keyboard's way to what pointing at a moon does.
  if ((orbit.moons || []).length) {
    mapCard.appendChild(elt("h3", "card-section", t("map.sectionCaptures", "Filed from the Horizon")));
    const list = elt("ul", "card-list");
    orbit.moons.forEach((item) => {
      const row = elt("li", "card-row");
      row.appendChild(elt("span", moonClass({ kind: "capture", ...item }).replace("map-dot", "legend-dot"), ""));
      const name = elt("button", "card-row-title", item.title);
      name.type = "button";
      name.addEventListener("click", () => openMapFocus({ kind: "capture", ...item, orbit: orbit.slug }));
      row.appendChild(name);
      list.appendChild(row);
    });
    mapCard.appendChild(list);
  }
  // A source added inside the orbit is a hollow moon. What that is, and why it has no summary, is
  // said here rather than left to a legend entry nobody could decode.
  const local = Math.max(0, (orbit.sources || 0) - orbit.captures);
  if (local) {
    mapCard.appendChild(elt("h3", "card-section", t("map.sectionLocal", "Not in the Horizon yet")));
    mapCard.appendChild(elt("p", "card-note", t("map.localHelp",
      `${local} not recorded in the Horizon yet, usually because they were added from the command line. They are drawn hollow until the server next starts, which records them.`,
      { n: local })));
  }
  const enter = elt("button", "btn btn-primary card-enter", t("map.enter", "Open orbit"));
  enter.type = "button";
  enter.addEventListener("click", () => void enterOrbit(orbit));
  mapCard.appendChild(enter);
  if (orbit.undistilled) {
    mapCard.appendChild(distilOrbitControl(orbit.slug, orbit.undistilled));
  }
  mapCard.hidden = false;
}

// --- summarising one orbit's captures -------------------------------------------------------------
//
// The same summary pass as the Horizon's button, narrowed to one orbit. It spends money, so it says
// how many calls before the press, shows its progress and offers Stop while it runs (47, 80).

//: The summary pass's state, kept OUTSIDE the drawn controls. The controls are rebuilt on every
//: redraw of the map or the graph, and a running pass's progress and Stop used to live inside one:
//: selecting an entity mid-pass put the spend button back with no Stop while the pass kept billing.
//: Every control paints from this, and one poll keeps it current.
//: `gen` counts presses of Summarise. A status poll already in flight when the reader presses can
//: answer `running: false` from before the pass began, and taking it cleared `slug`, so the orbit's
//: own count gave way to the generic line. A reply from an earlier `gen` is dropped and re-asked.
const distilWatch = {
  status: null, polling: false, failures: 0, stopping: false, slug: null, aligning: false, gen: 0,
};

function watchDistil() {
  if (distilWatch.polling) return;
  distilWatch.polling = true;
  void pollDistilWatch();
}

async function pollDistilWatch() {
  let reply;
  const gen = distilWatch.gen;
  try {
    reply = await api("/horizon/status");
    if (gen !== distilWatch.gen) {
      setTimeout(pollDistilWatch, 300);
      return;
    }
    distilWatch.failures = 0;
  } catch {
    // One failed poll is not the end of the pass; keep asking, and say so only if it persists.
    distilWatch.failures += 1;
    paintDistilControls();
    setTimeout(pollDistilWatch, 3000);
    return;
  }
  const wasRunning = Boolean(distilWatch.status && distilWatch.status.running);
  distilWatch.status = reply.distil || { running: false };
  distilWatch.aligning = Boolean(reply.align && reply.align.running);
  if (!distilWatch.status.running) distilWatch.stopping = false;
  paintDistilControls();
  if (distilWatch.status.running) {
    setTimeout(pollDistilWatch, 1500);
    return;
  }
  distilWatch.polling = false;
  distilWatch.slug = null;
  if (wasRunning) {
    if (distilWatch.status.error) notify(readableError(distilWatch.status.error));
    else if (reply.align && reply.align.error) {
      notify(`${t("horizon.alignFailed", "New entities were not matched")}: ${readableError(reply.align.error)}`);
    }
    refreshTopologyViews();
  }
}

function paintDistilControls() {
  document.querySelectorAll(".distil-orbit").forEach((control) => {
    if (control.paintDistil) control.paintDistil();
  });
}

function refreshTopologyViews() {
  if (document.body.dataset.view === "horizon" && viewMode("horizon") === "map") void renderStarMap();
  if (document.body.dataset.view === "orbit" && !horizonEl("view-graph").hidden) void renderGraph();
}

function distilOrbitControl(slug, count) {
  const control = elt("div", "distil-orbit");
  const n = Math.min(count, DISTIL_BATCH_CAP);
  control.paintDistil = () => {
    control.textContent = "";
    const status = distilWatch.status;
    if (status && status.running) {
      // Progress is claimed only for a pass THIS orbit started; any other pass (the Horizon's own
      // button, the automatic one, another orbit's, or one found after a reload) is named as such,
      // because a count here would say this orbit's captures are being summarised (invariant 60).
      const ours = distilWatch.slug === slug;
      control.appendChild(elt("span", "distil-orbit-cost", distilWatch.failures >= 3
        ? t("map.distilLost", "Cannot reach the server to check progress. Still trying.")
        : distilWatch.aligning
          // The stage that is actually running (invariant 60): the summaries are done and saved,
          // and the pass is now deciding which new names are the same entity.
          ? t("map.aligning", "Matching new entities to known ones")
          : ours
            ? t("map.distilling", `Summarising ${status.done || 0} of ${status.total || 0}`,
              { done: status.done || 0, total: status.total || 0 })
            : t("map.distilElsewhere", "A summary pass is running.")));
      const stop = elt("button", "btn run-stop", distilWatch.stopping
        ? t("run.stopping", "Stopping\u2026") : t("run.stop", "\u23f9 Stop"));
      stop.type = "button";
      stop.disabled = distilWatch.stopping;
      stop.addEventListener("click", async () => {
        distilWatch.stopping = true;
        paintDistilControls();
        try {
          // The summary pass only: the capture queue is not on this screen and must not be dropped.
          await api("/horizon/distil/cancel", { method: "POST" });
        } catch (err) {
          distilWatch.stopping = false;
          notify(readableError(err.message));
          paintDistilControls();
        }
      });
      control.appendChild(stop);
      return;
    }
    const go = elt("button", "btn", t("map.distil", `Summarise ${n}`, { n }));
    go.type = "button";
    const cost = elt("span", "distil-orbit-cost", t("map.distilCost", `Runs the model ${n} times.`, { n }));
    // Corrected from the server's count once it arrives: a long capture takes several calls.
    // Replaced by the server's bound once it arrives: long documents take several calls, and every
    // pass may end with one concept-alignment run, so the honest figure is a range (invariant 80).
    void distilEstimate(slug).then((est) => {
      if (!est || !cost.isConnected) return;
      cost.textContent = n === est.count
        ? t("map.distilCostRange",
          `Runs the model ${est.calls_min} to at most ${est.calls_max} times, matching new entities included.`,
          { min: est.calls_min, max: est.calls_max })
        : t("map.distilCostLong",
          `At least ${n} model calls; long documents and matching new entities take more.`, { n });
    });
    go.addEventListener("click", async () => {
      go.disabled = true;
      let reply;
      try {
        reply = await api("/horizon/distil", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ limit: n, orbit_id: slug }),
        });
      } catch (err) {
        go.disabled = false;
        cost.textContent = readableError(err.message);
        return;
      }
      if (!reply || reply.started === false) {
        refreshTopologyViews();
        return;
      }
      distilWatch.gen += 1;
      distilWatch.slug = slug;
      distilWatch.status = { running: true, done: 0, total: n };
      paintDistilControls();
      watchDistil();
    });
    control.appendChild(go);
    control.appendChild(cost);
  };
  control.paintDistil();
  return control;
}

// --- filing suggestions ---------------------------------------------------------------------------

const suggest = { items: [], open: false, lastFetch: 0, inFlight: false, again: false };

async function ensureOrbitTitles() {
  if (orbitTitles.size) return;
  try {
    const listed = await api("/orbits");
    (listed.orbits || []).forEach((o) => {
      orbitTitles.set(o.slug, o.title || o.derived_title || t("app.untitled", "Untitled orbit"));
    });
  } catch {
    /* rows fall back to a neutral label */
  }
}

async function refreshSuggestions({ force = false } = {}) {
  // One request at a time: a slow answer must not be asked for again while it is still coming. A
  // forced refresh (after Add or Not this) that arrives meanwhile runs once that one lands, since
  // the answer in flight may predate the action.
  if (suggest.inFlight) {
    if (force) suggest.again = true;
    return;
  }
  if (!force && Date.now() - suggest.lastFetch < 5000) return;
  suggest.lastFetch = Date.now();
  suggest.inFlight = true;
  let data;
  try {
    data = await api("/horizon/suggestions");
  } catch {
    return;
  } finally {
    suggest.inFlight = false;
    if (suggest.again) {
      suggest.again = false;
      void refreshSuggestions({ force: true });
    }
  }
  await ensureOrbitTitles();
  suggest.items = data.suggestions || [];
  renderSuggestions();
}

function renderSuggestions() {
  const suggestBox = horizonEl("suggest");
  const head = horizonEl("suggest-head");
  const suggestList = horizonEl("suggest-list");
  const n = suggest.items.length;
  suggestBox.hidden = !n;
  if (!n) {
    suggest.open = false;
    return;
  }
  head.textContent = t("suggest.head", `${n} could be filed into an orbit`, { n });
  head.setAttribute("aria-expanded", suggest.open ? "true" : "false");
  suggestList.hidden = !suggest.open;
  suggestList.textContent = "";
  suggest.items.forEach((item) => {
    const where = orbitLabelForSlug(item.orbit) || t("suggest.anOrbit", "an orbit");
    const row = elt("li", "suggest-row");
    row.appendChild(elt("span", "suggest-title", item.title));
    const why = [...item.shared, ...item.tags.map((tag) => `#${tag}`)].join(t("list.sep", ", "));
    row.appendChild(elt("span", "suggest-why", item.like
      ? t("suggest.like", `Into ${where}: its content is like ${item.like}`, { where, like: item.like })
      : t("suggest.why", `Into ${where}: both name ${why}`, { where, why })));
    const add = elt("button", "btn", t("suggest.add", "Add"));
    add.type = "button";
    add.addEventListener("click", async () => {
      add.disabled = true;
      try {
        await api(`/horizon/${encodeURIComponent(item.node_id)}/promote`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ orbit_id: item.orbit, create: false }),
        });
      } catch (err) {
        add.disabled = false;
        notify(readableError(err.message));
        return;
      }
      await refreshSuggestions({ force: true });
      void refreshHorizon();
    });
    const no = elt("button", "btn", t("suggest.no", "Not this"));
    no.type = "button";
    no.addEventListener("click", async () => {
      no.disabled = true;
      try {
        await api("/horizon/suggestions/dismiss", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ node_id: item.node_id, orbit: item.orbit }),
        });
      } catch (err) {
        no.disabled = false;
        notify(readableError(err.message));
        return;
      }
      await refreshSuggestions({ force: true });
    });
    const actions = elt("span", "suggest-actions");
    actions.appendChild(add);
    actions.appendChild(no);
    row.appendChild(actions);
    suggestList.appendChild(row);
  });
}

function initSuggestions() {
  horizonEl("suggest-head").addEventListener("click", () => {
    suggest.open = !suggest.open;
    renderSuggestions();
  });
}

// --- the knowledge graph --------------------------------------------------------------------------

const graphState = { data: null, slug: null, selected: null, lenses: new Set(), generation: 0, layout: null };

async function renderGraph() {
  const slug = state.orbitSlug || state.orbitId;
  if (!slug) return;
  watchDistil();
  const generation = ++graphState.generation;
  let data;
  try {
    data = await api(`/horizon/graph?orbit=${encodeURIComponent(slug)}`);
  } catch (err) {
    showGraphEmpty(readableError(err.message));
    return;
  }
  if (generation !== graphState.generation) return;
  if (graphState.slug !== slug) {
    graphState.selected = null;
    graphState.lenses = new Set();
  }
  const sameOrbit = graphState.slug === slug;
  graphState.slug = slug;
  graphState.data = data;
  const before = graphState.layout;
  graphState.layout = layoutGraph(data);
  if (sameOrbit && graphState.moved && before) {
    // Where the reader dragged things stays where they put it when the data refreshes. The
    // captures' offsets are taken from the fresh layout first, then follow the kept positions.
    followCaptures(graphState.layout);
    before.pos.forEach((point, name) => {
      if (graphState.layout.pos.has(name)) graphState.layout.pos.set(name, { ...point });
    });
    followCaptures(graphState.layout);
  } else if (!sameOrbit) {
    graphState.moved = false;
    resetGraphCamera();
  }
  graphState.follow = !sameOrbit;
  paintGraphLenses();
  drawGraph();
  graphState.follow = true;
}

function paintGraphLenses() {
  const data = graphState.data || { tags: [] };
  renderLenses(horizonEl("graph-lenses"), data.tags || [], graphState.lenses, (name) => {
    graphState.lenses = toggledLenses(graphState.lenses, name);
    graphState.selected = null;
    paintGraphLenses();
    drawGraph();
  });
}

function showGraphEmpty(text) {
  const emptyNote = horizonEl("graph-empty");
  emptyNote.textContent = text;
  emptyNote.hidden = !text;
}

//: A small force layout, run to rest before anything is drawn, so the graph appears still rather
//: than settling in front of the reader. Deterministic: the same orbit draws the same picture.
function layoutGraph(data) {
  const W = 1000;
  const H = 700;
  const names = data.entities.map((e) => e.name);
  const pos = new Map();
  names.forEach((name, i) => {
    const angle = (i / Math.max(names.length, 1)) * Math.PI * 2;
    const r = 180 + stableHash(name) * 120;
    pos.set(name, { x: W / 2 + r * Math.cos(angle), y: H / 2 + r * Math.sin(angle) });
  });
  const edges = data.edges.filter((e) => pos.has(e.a) && pos.has(e.b));
  for (let step = 0; step < 280; step += 1) {
    const cool = 1 - step / 280;
    const force = new Map(names.map((n) => [n, { x: 0, y: 0 }]));
    for (let i = 0; i < names.length; i += 1) {
      for (let j = i + 1; j < names.length; j += 1) {
        const a = pos.get(names[i]);
        const b = pos.get(names[j]);
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        const d2 = Math.max(dx * dx + dy * dy, 25);
        const push = 9000 / d2;
        const d = Math.sqrt(d2);
        dx /= d;
        dy /= d;
        force.get(names[i]).x += dx * push;
        force.get(names[i]).y += dy * push;
        force.get(names[j]).x -= dx * push;
        force.get(names[j]).y -= dy * push;
      }
    }
    edges.forEach((e) => {
      const a = pos.get(e.a);
      const b = pos.get(e.b);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const pull = (d - 110) * 0.02 * Math.min(e.weight, 4);
      force.get(e.a).x += (dx / d) * pull;
      force.get(e.a).y += (dy / d) * pull;
      force.get(e.b).x -= (dx / d) * pull;
      force.get(e.b).y -= (dy / d) * pull;
    });
    names.forEach((n) => {
      const p = pos.get(n);
      const f = force.get(n);
      f.x += (W / 2 - p.x) * 0.012;
      f.y += (H / 2 - p.y) * 0.012;
      const len = Math.sqrt(f.x * f.x + f.y * f.y);
      const cap = 24 * cool + 1;
      const scale = len > cap ? cap / len : 1;
      p.x = Math.min(W - 60, Math.max(60, p.x + f.x * scale));
      p.y = Math.min(H - 60, Math.max(50, p.y + f.y * scale));
    });
  }
  // Captures sit beside the entities they name; one naming none waits at the edge, unless local
  // relations link it to a capture that is placed, in which case it sits beside that one.
  const captures = data.captures.map((c, i) => {
    const anchors = c.entities.map((n) => pos.get(n)).filter(Boolean);
    const jitterA = stableHash(c.node_id) * Math.PI * 2;
    const jitterR = 22 + stableHash(`${c.node_id}r`) * 26;
    if (!anchors.length) {
      const angle = (i / Math.max(data.captures.length, 1)) * Math.PI * 2;
      return { ...c, x: W / 2 + 440 * Math.cos(angle), y: H / 2 + 300 * Math.sin(angle), anchors };
    }
    const cx = anchors.reduce((s, a) => s + a.x, 0) / anchors.length;
    const cy = anchors.reduce((s, a) => s + a.y, 0) / anchors.length;
    return { ...c, x: cx + jitterR * Math.cos(jitterA), y: cy + jitterR * Math.sin(jitterA), anchors };
  });
  const at = new Map(captures.map((c) => [c.node_id, c]));
  (data.similar || []).forEach((pair) => {
    const a = at.get(pair.a);
    const b = at.get(pair.b);
    if (!a || !b) return;
    const [loose, placed] = !a.anchors.length && b.anchors.length ? [a, b] : !b.anchors.length && a.anchors.length ? [b, a] : [null, null];
    if (!loose || loose.moved) return;
    const angle = stableHash(`${loose.node_id}s`) * Math.PI * 2;
    loose.x = placed.x + 34 * Math.cos(angle);
    loose.y = placed.y + 34 * Math.sin(angle);
    loose.moved = true;
  });
  // Framed to what was drawn, so a small graph fills the stage instead of sitting in its middle;
  // never tighter than a minimum, so two entities are not blown up to fill a screen.
  const points = [...pos.values(), ...captures];
  let box = { x: 0, y: 0, w: W, h: H };
  if (points.length) {
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const pad = 70;
    let x0 = Math.min(...xs) - pad;
    let x1 = Math.max(...xs) + pad;
    let y0 = Math.min(...ys) - pad;
    let y1 = Math.max(...ys) + pad + 20;
    const minW = 900;
    const minH = 640;
    if (x1 - x0 < minW) {
      const grow = (minW - (x1 - x0)) / 2;
      x0 -= grow;
      x1 += grow;
    }
    if (y1 - y0 < minH) {
      const grow = (minH - (y1 - y0)) / 2;
      y0 -= grow;
      y1 += grow;
    }
    box = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
  }
  return { pos, edges, captures, box };
}

function drawGraph() {
  const svg = horizonEl("graph-svg");
  const keepFocus = focusedKey(svg);
  clearSvg(svg);
  const data = graphState.data;
  const layout = graphState.layout;
  if (!data || !layout) return;
  svg.setAttribute("viewBox", `${layout.box.x} ${layout.box.y} ${layout.box.w} ${layout.box.h}`);
  // Everything drawn sits in one group the camera moves; `refs` keep each shape so a drag can move
  // them without rebuilding the drawing.
  const world = svgEl("g", {}, "graph-world");
  svg.appendChild(world);
  graphState.world = world;
  const refs = { entities: new Map(), edges: [], links: [], captures: [], similar: [] };
  graphState.refs = refs;
  const count = new Map(data.entities.map((e) => [e.name, e.count]));
  const lenses = graphState.lenses;
  const selected = graphState.selected;

  // What is lit: a lens lights its captures and every entity they name; an entity lights itself and
  // the captures that name it.
  const litCaptures = new Set();
  const litEntities = new Set();
  if (lenses.size) {
    layout.captures.forEach((c) => {
      if (c.tags.some((tag) => lenses.has(tag))) {
        litCaptures.add(c.node_id);
        c.entities.forEach((n) => litEntities.add(n));
      }
    });
  } else if (selected) {
    litEntities.add(selected);
    layout.captures.forEach((c) => {
      if (c.entities.includes(selected)) litCaptures.add(c.node_id);
    });
  }
  const focus = Boolean(lenses.size || selected);

  const edgeLayer = svgEl("g", {}, "graph-edges");
  layout.captures.forEach((c) => {
    c.entities.forEach((n) => {
      const p = layout.pos.get(n);
      if (!p) return;
      const lit = litCaptures.has(c.node_id) && litEntities.has(n);
      const line = svgEl("line", { x1: c.x, y1: c.y, x2: p.x, y2: p.y },
        `graph-link${lit ? " is-lit" : ""}${focus && !lit ? " is-dim" : ""}`);
      refs.links.push({ line, c, n });
      edgeLayer.appendChild(line);
    });
  });
  layout.edges.forEach((e) => {
    const a = layout.pos.get(e.a);
    const b = layout.pos.get(e.b);
    const lit = lenses.size ? litEntities.has(e.a) && litEntities.has(e.b) : e.a === selected || e.b === selected;
    const line = svgEl("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y },
      `graph-edge${lit ? " is-lit" : ""}${focus && !lit ? " is-dim" : ""}`);
    line.style.strokeWidth = String(1 + Math.min(e.weight, 5) * 1.1);
    refs.edges.push({ line, a: e.a, b: e.b });
    edgeLayer.appendChild(line);
  });
  world.appendChild(edgeLayer);

  // Local relations: a dashed line between two captures whose text is alike.
  const placed = new Map(layout.captures.map((c) => [c.node_id, c]));
  (data.similar || []).forEach((pair) => {
    const a = placed.get(pair.a);
    const b = placed.get(pair.b);
    if (!a || !b) return;
    const line = svgEl("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y }, `graph-similar${focus ? " is-dim" : ""}`);
    refs.similar.push({ line, a, b });
    edgeLayer.appendChild(line);
  });

  layout.captures.forEach((c) => {
    const lit = !focus || litCaptures.has(c.node_id);
    const waiting = c.state === "ready_undistilled";
    const mark = svgEl("rect", { x: c.x - 4, y: c.y - 4, width: 8, height: 8, rx: 2 },
      `graph-capture${waiting ? " is-waiting" : ""}${lit ? "" : " is-dim"}`);
    const title = svgEl("title");
    title.textContent = c.title;
    mark.appendChild(title);
    refs.captures.push({ rect: mark, c });
    world.appendChild(mark);
  });

  data.entities.forEach((entity) => {
    const p = layout.pos.get(entity.name);
    const r = Math.min(28, 9 + (count.get(entity.name) || 1) * 2.6);
    const lit = !focus || litEntities.has(entity.name);
    const group = svgEl("g", { tabindex: 0, role: "button", "aria-pressed": entity.name === selected ? "true" : "false",
      "aria-label": t("graph.entityLabel", `${entity.name}, in ${entity.count} captures`, { name: entity.name, n: entity.count }) },
    `graph-entity${entity.name === selected ? " is-selected" : ""}${lit ? "" : " is-dim"}`);
    const body = svgEl("circle", { cx: p.x, cy: p.y, r }, "graph-entity-body");
    const label = svgText(p.x, p.y + r + 16, shortLabel(entity.name, 16), "graph-entity-label");
    group.appendChild(body);
    group.appendChild(label);
    refs.entities.set(entity.name, { body, label, r });
    group.dataset.key = `entity:${entity.name}`;
    const pick = () => {
      // The click that ends a drag is not a pick.
      if (graphDrag.suppress) return;
      graphState.selected = graphState.selected === entity.name ? null : entity.name;
      graphState.lenses = new Set();
      paintGraphLenses();
      drawGraph();
    };
    group.addEventListener("click", pick);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        pick();
      }
    });
    world.appendChild(group);
  });
  applyGraphCamera();

  if (!data.entities.length) {
    showGraphEmpty(data.captures.length || data.undistilled.length
      ? t("graph.noEntities", "Nothing here names an entity yet. Summarising is what finds them.")
      : t("graph.nothingFiled", "Nothing in this orbit came through the Horizon, so there is nothing to draw yet. The columns have its sources."));
  } else {
    showGraphEmpty("");
  }
  restoreFocus(svg, keepFocus);
  renderGraphPending();
  renderGraphPanel(litCaptures);
  syncGraphContext();
}

// --- handling the graph: a camera, and nodes that can be pulled --------------------------------------
//
// The same gestures as the star map: scroll or pinch zooms around the pointer, dragging empty space
// pans, and + - and return sit in the corner (with + - 0 from the keyboard). A node can be dragged:
// the entities linked to it follow with a little lag and keep their shape, the captures between them
// follow their entities, and on release the neighbours settle. Return puts the camera and every
// node back where the layout placed them.

const graphCam = { x: 500, y: 350, k: 1 };
const GRAPH_ZOOM = { min: 0.4, max: 4 };
const graphDrag = { id: null, name: null, start: null, moved: false, from: null, weights: null, suppress: false };

function graphCentre() {
  const box = graphState.layout ? graphState.layout.box : { x: 0, y: 0, w: 1000, h: 700 };
  return { x: box.x + box.w / 2, y: box.y + box.h / 2 };
}

function resetGraphCamera() {
  const centre = graphCentre();
  Object.assign(graphCam, { x: centre.x, y: centre.y, k: 1 });
}

function applyGraphCamera() {
  if (!graphState.world) return;
  const centre = graphCentre();
  graphState.world.setAttribute("transform",
    `translate(${centre.x} ${centre.y}) scale(${graphCam.k}) translate(${-graphCam.x} ${-graphCam.y})`);
  const atHome = graphCam.k === 1 && graphCam.x === centre.x && graphCam.y === centre.y && !graphState.moved;
  horizonEl("graph-zoom-home").disabled = atHome;
}

function zoomGraph(factor, around) {
  const centre = graphCentre();
  const at = around || centre;
  const k = Math.min(GRAPH_ZOOM.max, Math.max(GRAPH_ZOOM.min, graphCam.k * factor));
  // The world point under the pointer stays under it.
  const wx = graphCam.x + (at.x - centre.x) / graphCam.k;
  const wy = graphCam.y + (at.y - centre.y) / graphCam.k;
  Object.assign(graphCam, { k, x: wx - (at.x - centre.x) / k, y: wy - (at.y - centre.y) / k });
  applyGraphCamera();
}

function graphWorldAt(clientX, clientY) {
  const view = clientToView(horizonEl("graph-svg"), clientX, clientY);
  const centre = graphCentre();
  return { x: graphCam.x + (view.x - centre.x) / graphCam.k, y: graphCam.y + (view.y - centre.y) / graphCam.k };
}

function graphHome() {
  if (graphState.moved && graphState.data) {
    graphState.layout = layoutGraph(graphState.data);
    graphState.moved = false;
  }
  resetGraphCamera();
  drawGraph();
}

//: A capture sits among the entities it names; after they move it moves with them, by the offset it
//: had from their centre when the layout placed it.
function followCaptures(layout) {
  layout.captures.forEach((c) => {
    const points = c.entities.map((n) => layout.pos.get(n)).filter(Boolean);
    if (!points.length) return;
    if (!c.offset) {
      const cx0 = points.reduce((sum, p) => sum + p.x, 0) / points.length;
      const cy0 = points.reduce((sum, p) => sum + p.y, 0) / points.length;
      c.offset = { x: c.x - cx0, y: c.y - cy0 };
      return;
    }
    c.x = points.reduce((sum, p) => sum + p.x, 0) / points.length + c.offset.x;
    c.y = points.reduce((sum, p) => sum + p.y, 0) / points.length + c.offset.y;
  });
}

function paintGraphGeometry() {
  const refs = graphState.refs;
  const pos = graphState.layout.pos;
  if (!refs) return;
  refs.entities.forEach(({ body, label, r }, name) => {
    const p = pos.get(name);
    body.setAttribute("cx", p.x);
    body.setAttribute("cy", p.y);
    label.setAttribute("x", p.x);
    label.setAttribute("y", p.y + r + 16);
  });
  const line = (el, a, b) => {
    el.setAttribute("x1", a.x);
    el.setAttribute("y1", a.y);
    el.setAttribute("x2", b.x);
    el.setAttribute("y2", b.y);
  };
  refs.edges.forEach(({ line: el, a, b }) => line(el, pos.get(a), pos.get(b)));
  refs.links.forEach(({ line: el, c, n }) => line(el, c, pos.get(n)));
  refs.similar.forEach(({ line: el, a, b }) => line(el, a, b));
  refs.captures.forEach(({ rect, c }) => {
    rect.setAttribute("x", c.x - 4);
    rect.setAttribute("y", c.y - 4);
  });
}

//: One step of the pull. Every node has a target: where it was when the drag began, moved by the
//: dragged node's travel times its weight (0.6 one link away, 0.3 two links away, nothing further).
//: Each step closes part of the gap, so the cluster follows with a little lag and keeps its shape.
//: Keeping only each neighbour's distance to the dragged node made them all swing to the same side
//: and pile onto one another.
function relaxNeighbours(ease) {
  const { name, from, weights } = graphDrag;
  const pos = graphState.layout.pos;
  const at = pos.get(name);
  const origin = from.get(name);
  const travel = { x: at.x - origin.x, y: at.y - origin.y };
  let moving = 0;
  weights.forEach((weight, other) => {
    const start = from.get(other);
    const p = pos.get(other);
    const tx = start.x + travel.x * weight;
    const ty = start.y + travel.y * weight;
    const step = { x: (tx - p.x) * ease, y: (ty - p.y) * ease };
    moving = Math.max(moving, Math.hypot(step.x, step.y));
    pos.set(other, { x: p.x + step.x, y: p.y + step.y });
  });
  moving = Math.max(moving, separateNodes(name));
  followCaptures(graphState.layout);
  return moving;
}

//: No node may be dropped on top of another: two closer than their radii plus room for a label are pushed
//: apart, and the one being dragged never moves for it.
function separateNodes(held) {
  const pos = graphState.layout.pos;
  const radius = (key) => (graphState.refs && graphState.refs.entities.get(key)?.r) || 12;
  const keys = [...pos.keys()];
  let pushed = 0;
  for (let i = 0; i < keys.length; i += 1) {
    for (let j = i + 1; j < keys.length; j += 1) {
      const a = pos.get(keys[i]);
      const b = pos.get(keys[j]);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d = Math.hypot(dx, dy) || 0.01;
      // 28px beyond the two radii leaves room for the label drawn under each node.
      const gap = radius(keys[i]) + radius(keys[j]) + 28 - d;
      if (gap <= 0) continue;
      const ux = dx / d;
      const uy = dy / d;
      const aHeld = keys[i] === held;
      const bHeld = keys[j] === held;
      // Against the held node the other one moves the whole gap; otherwise each moves half. Its
      // target moves with it, or the pull would drag it straight back on the next step.
      const share = aHeld || bHeld ? 1 : 0.5;
      const push = (key, point, sign) => {
        const shift = { x: sign * ux * gap * share, y: sign * uy * gap * share };
        pos.set(key, { x: point.x + shift.x, y: point.y + shift.y });
        const origin = graphDrag.from && graphDrag.from.get(key);
        if (origin && graphDrag.weights && graphDrag.weights.has(key)) {
          graphDrag.from.set(key, { x: origin.x + shift.x, y: origin.y + shift.y });
        }
      };
      if (!aHeld) push(keys[i], a, -1);
      if (!bHeld) push(keys[j], b, 1);
      pushed = Math.max(pushed, gap * share);
    }
  }
  return pushed;
}

//: How strongly each node follows a drag of `name`: by how many links away it is.
function dragWeights(name, edges) {
  const near = new Map();
  edges.forEach((e) => {
    if (e.a === name) near.set(e.b, 0.6);
    if (e.b === name) near.set(e.a, 0.6);
  });
  const second = new Map();
  edges.forEach((e) => {
    [[e.a, e.b], [e.b, e.a]].forEach(([one, two]) => {
      if (near.has(one) && two !== name && !near.has(two)) second.set(two, 0.3);
    });
  });
  return new Map([...second, ...near]);
}

function initGraphCamera() {
  const svg = horizonEl("graph-svg");
  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const factor = Math.exp(-event.deltaY * (event.ctrlKey ? 0.01 : 0.0015));
    zoomGraph(factor, clientToView(svg, event.clientX, event.clientY));
  }, { passive: false });
  svg.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || !graphState.layout) return;
    event.preventDefault();
    const node = event.target.closest(".graph-entity");
    graphDrag.id = event.pointerId;
    graphDrag.start = { cx: event.clientX, cy: event.clientY, x: graphCam.x, y: graphCam.y };
    graphDrag.moved = false;
    graphDrag.name = node ? node.dataset.key.slice("entity:".length) : null;
  });
  svg.addEventListener("pointermove", (event) => {
    if (graphDrag.id !== event.pointerId || !graphDrag.start) return;
    const dx = event.clientX - graphDrag.start.cx;
    const dy = event.clientY - graphDrag.start.cy;
    if (!graphDrag.moved && Math.hypot(dx, dy) < 4) return;
    if (!graphDrag.moved) {
      graphDrag.moved = true;
      svg.setPointerCapture(event.pointerId);
      svg.classList.add(graphDrag.name ? "is-dragging" : "is-panning");
      if (graphDrag.name) {
        graphDrag.from = new Map([...graphState.layout.pos].map(([key, p]) => [key, { ...p }]));
        graphDrag.weights = dragWeights(graphDrag.name, graphState.layout.edges);
        followCaptures(graphState.layout);
      }
    }
    if (graphDrag.name) {
      graphState.layout.pos.set(graphDrag.name, graphWorldAt(event.clientX, event.clientY));
      relaxNeighbours(0.22);
      graphState.moved = true;
      paintGraphGeometry();
      applyGraphCamera();
    } else {
      const scale = (svg.getScreenCTM() || { a: 1 }).a || 1;
      graphCam.x = graphDrag.start.x - dx / scale / graphCam.k;
      graphCam.y = graphDrag.start.y - dy / scale / graphCam.k;
      applyGraphCamera();
    }
  });
  const end = (event) => {
    if (graphDrag.id !== event.pointerId) return;
    const dragged = graphDrag.moved && graphDrag.name;
    graphDrag.id = null;
    graphDrag.start = null;
    svg.classList.remove("is-dragging", "is-panning");
    if (!graphDrag.moved) return;
    graphDrag.suppress = true;
    setTimeout(() => { graphDrag.suppress = false; }, 0);
    if (!dragged) return;
    // Released: the neighbours finish settling on their springs, briefly, unless motion is off.
    if (!motionAllowed()) {
      for (let i = 0; i < 60 && relaxNeighbours(0.5) > 0.05; i += 1);
      paintGraphGeometry();
      return;
    }
    const settle = () => {
      if (graphDrag.id !== null || !graphState.refs) return;
      const moving = relaxNeighbours(0.14);
      paintGraphGeometry();
      if (moving > 0.05) requestAnimationFrame(settle);
    };
    requestAnimationFrame(settle);
  };
  svg.addEventListener("pointerup", end);
  svg.addEventListener("pointercancel", end);
  horizonEl("view-graph").addEventListener("keydown", (event) => {
    if (event.target.closest("input, select, textarea, button")) return;
    if (event.key === "+" || event.key === "=") zoomGraph(1.25);
    else if (event.key === "-" || event.key === "_") zoomGraph(0.8);
    else if (event.key === "0") graphHome();
    else return;
    event.preventDefault();
  });
  horizonEl("graph-zoom-in").addEventListener("click", () => zoomGraph(1.25));
  horizonEl("graph-zoom-out").addEventListener("click", () => zoomGraph(0.8));
  horizonEl("graph-zoom-home").addEventListener("click", graphHome);
}

function renderGraphPending() {
  const data = graphState.data;
  const pendingBox = horizonEl("graph-pending");
  const pending = data.undistilled || [];
  pendingBox.hidden = !pending.length;
  if (!pending.length) return;
  horizonEl("graph-pending-line").textContent = t("graph.pending",
    `${pending.length} not summarised yet, so they link to nothing.`, { n: pending.length });
  const actions = pendingBox.querySelector(".graph-pending-actions");
  actions.textContent = "";
  actions.appendChild(distilOrbitControl(graphState.slug, pending.length));
}

function renderGraphPanel(litCaptures) {
  const panel = horizonEl("graph-panel");
  const keepFocus = focusedKey(panel);
  panel.textContent = "";
  const data = graphState.data;
  const layout = graphState.layout;
  let kicker;
  let heading;
  let near = [];
  let items;
  if (graphState.lenses.size) {
    kicker = graphState.lenses.size > 1 ? t("graph.tags", "Tags") : t("graph.tag", "Tag");
    heading = [...graphState.lenses].map((name) => `#${name}`).join(" + ");
    items = layout.captures.filter((c) => litCaptures.has(c.node_id));
    near = [...new Set(items.flatMap((c) => c.entities))];
  } else if (graphState.selected) {
    kicker = t("graph.entity", "Entity");
    heading = graphState.selected;
    items = layout.captures.filter((c) => c.entities.includes(graphState.selected));
    near = data.edges.filter((e) => e.a === heading || e.b === heading)
      .sort((x, y) => y.weight - x.weight)
      .map((e) => (e.a === heading ? e.b : e.a));
  } else {
    kicker = t("graph.orbit", "Orbit");
    heading = openOrbitTitle();
    items = layout.captures;
    near = data.entities.slice(0, 8).map((e) => e.name);
  }
  panel.appendChild(elt("p", "card-kicker", kicker));
  panel.appendChild(elt("h2", "card-title", heading));
  const entry = graphState.selected ? data.entities.find((e) => e.name === graphState.selected) : null;
  if (entry && entry.aliases && entry.aliases.length) {
    // Names concept alignment folded into this one, each one press from being itself again.
    panel.appendChild(elt("p", "card-kicker", t("graph.aliases", "Also written as")));
    const merged = elt("div", "card-chips");
    entry.aliases.forEach((alias) => {
      const chip = elt("span", "card-chip", alias);
      const undo = elt("button", "alias-undo", t("graph.unmerge", "Separate"));
      undo.type = "button";
      undo.setAttribute("aria-label", t("graph.unmergeLabel", `Separate ${alias}`, { name: alias }));
      undo.addEventListener("click", async () => {
        undo.disabled = true;
        try {
          await api("/horizon/aliases/remove", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ alias }),
          });
        } catch (err) {
          undo.disabled = false;
          notify(readableError(err.message));
          return;
        }
        void renderGraph();
      });
      chip.appendChild(undo);
      merged.appendChild(chip);
    });
    panel.appendChild(merged);
  }
  panel.appendChild(elt("p", "card-meta", t("graph.inCaptures", `${items.length} captures`, { n: items.length })));
  if ((data.similar || []).length && !graphState.lenses.size && !graphState.selected) {
    panel.appendChild(elt("p", "card-note", t("graph.similarNote",
      "Dashed lines join captures with similar content, compared on this computer. Hollow squares are not summarised yet.")));
  }
  const left = (data.omitted && data.omitted.entities) || 0;
  if (left && !graphState.lenses.size && !graphState.selected) {
    panel.appendChild(elt("p", "card-note", t("graph.omitted",
      `${left} less-named entities are not drawn.`, { n: left })));
  }
  if (near.length) {
    panel.appendChild(elt("p", "card-kicker", graphState.lenses.size || !graphState.selected
      ? t("graph.entitiesHere", "Entities here")
      : t("graph.together", "Often named together")));
    const chips = elt("div", "card-chips");
    near.slice(0, 10).forEach((name) => {
      const chip = elt("button", "card-chip", name);
      chip.type = "button";
      chip.dataset.key = `chip:${name}`;
      chip.addEventListener("click", () => {
        graphState.selected = name;
        graphState.lenses = new Set();
        paintGraphLenses();
        drawGraph();
      });
      chips.appendChild(chip);
    });
    panel.appendChild(chips);
  }
  const list = elt("ol", "graph-items");
  items.slice(0, 40).forEach((c) => {
    const row = elt("li", "graph-item");
    row.appendChild(elt("span", "", c.title));
    row.appendChild(elt("span", "graph-item-origin", c.origin));
    list.appendChild(row);
  });
  panel.appendChild(list);
  if (graphState.selected || graphState.lenses.size) {
    const ask = elt("button", "btn btn-primary graph-ask", t("graph.ask", "Ask about this"));
    ask.type = "button";
    ask.addEventListener("click", openDock);
    panel.appendChild(ask);
  }
  // A chip rebuilds this panel; the entity it names is where focus belongs next.
  // The graph may not draw it (`omitted`, or dimmed out by a lens), and focus then fell to <body>;
  // the rebuilt chip itself is the next best place.
  if (keepFocus && keepFocus.startsWith("chip:")
      && !restoreFocus(horizonEl("graph-svg"), `entity:${keepFocus.slice(5)}`)) {
    restoreFocus(panel, keepFocus);
  }
}

//: What the header shows for the open orbit: its title, or the label derived for it.
function openOrbitTitle() {
  return state.title || document.getElementById("orbit-title")?.textContent || "";
}

function syncGraphContext() {
  if (document.body.dataset.view !== "orbit") return;
  const slug = graphState.slug;
  const chips = [];
  if (state.orbitId) {
    chips.push({ id: `orbit:${slug}`, orbit: { id: state.orbitId, slug, title: openOrbitTitle() } });
  }
  if (graphState.selected) {
    chips.push({ id: `entity:${graphState.selected}`, scope: { kind: "entity", value: graphState.selected, orbit: slug } });
  } else if (graphState.lenses.size) {
    chips.push({ id: lensChipId(graphState.lenses), scope: lensScope(graphState.lenses, slug) });
  }
  setAskContext(chips, { follow: graphState.follow !== false });
}

function initAskH() {
  horizonEl("ask-h-form").addEventListener("submit", (event) => {
    event.preventDefault();
    void previewAskH();
  });
  const input = horizonEl("ask-h-input");
  input.addEventListener("keydown", (event) => {
    // Enter checks, Shift+Enter breaks the line; never while an IME is composing a character.
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
      event.preventDefault();
      void previewAskH();
    }
  });
  // A preview is for ONE question in ONE scope; changing either means it no longer describes Ask.
  input.addEventListener("input", dismissAskHPlan);
  // The same send state and growth as the orbit composer: the round button fills once there is text.
  const form = horizonEl("ask-h-form");
  const grow = () => {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
    form.classList.toggle("has-text", input.value.trim().length > 0 && askSlashQuery() === null);
  };
  input.addEventListener("input", grow);
  syncAskHComposer = grow;
  input.addEventListener("keydown", askPickerKeys, true);
  input.addEventListener("input", () => {
    const q = askSlashQuery();
    if (q === null) {
      if (askPick.fromSlash) closeAskPicker();
      return;
    }
    if (!askPick.open || !askPick.fromSlash) openAskPicker({ fromSlash: true });
    else refreshAskPicker();
  });
  horizonEl("ask-h-add").addEventListener("click", () => {
    if (askPick.open) closeAskPicker();
    else openAskPicker();
    input.focus();
  });
  document.addEventListener("mousedown", (event) => {
    if (!askPick.open) return;
    if (event.target.closest("#ask-h-picker, #ask-h-add, #ask-h-input")) return;
    closeAskPicker();
  });
  horizonEl("ask-h-send").addEventListener("click", () => void sendAskH());
  horizonEl("ask-h-dismiss").addEventListener("click", dismissAskHPlan);
  renderAskHChips();
  void loadAskHScopes();
  void refreshAskHHistory();
  void reattachAskH();
}

initAskH();
initDock();
initCaptureDock();
initMascot();
initGraphCamera();
initPanels();
initStarMapCamera();
initDesktopContextMenu();
initViewModes();
initSuggestions();

//: The address bar decides the first screen, so a reload lands where the reader was and a link to a
//: orbit opens that orbit. `replace: true` on the way in: the first entry is this one, not a
//: second one stacked on top of it.
(async () => {
  installShortcuts();
  installTokenGate();
  installPrintReferences();
  installColumnSwitch();
  //: Before the first request, not only after one fails: with no token at all there is nothing to
  //: try, and a rail full of dead controls is a worse answer than asking for the thing that is
  //: missing.
  if (!apiToken()) showTokenGate("");
  let wanted = "";
  try {
    wanted = new URL(window.location.href).searchParams.get("nb") || "";
  } catch {
    // no URL here; the Horizon is the right default anyway
  }
  if (wanted) {
    //: No existence PROBE any more. This used to fetch the orbit itself, throw the result away,
    //: and fetch it again through `openOrbit` — because `openOrbit` would invent a placeholder
    //: for any id it could not load, which is right for an id the reader just minted and wrong for a
    //: bookmark. `openOrbit` now distinguishes those cases itself (`fresh`), so the probe is one
    //: request doing nothing, and it was ALSO the thing that turned invariant 27's 409 — "this file
    //: is not a valid orbit, fix or remove it by hand" — into "that orbit is not here any
    //: more", telling a reader their orbit was deleted when the server had just said it was
    //: broken and how to repair it.
    if (await openOrbit(wanted, { push: false })) {
      syncAddressBar(wanted, { replace: true });
      return;
    }
  }
  showHorizon({ push: false });
  syncAddressBar("", { replace: true });
})();
