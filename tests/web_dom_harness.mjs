/* Runs SHIPPED functions out of `penumbra/web/app.js` against a small fake DOM.
 *
 * **Why this exists, twice over.** Round seven's `readableError` test re-compiled that function's
 * regex literals and never called it, so replacing the body with `return text` left the suite
 * green. Round eight found the SAME shape one round later, in the two fixes round seven had called
 * blockers: `closeTicker` and `trajTakeFocus` could each be replaced by a no-op with all 931 tests
 * still passing, because their tests asserted that a function NAME appeared in the source.
 *
 * A source-text assertion cannot see reachability, ordering, or whether a call does anything. This
 * runs the code.
 *
 * **The shim is deliberately small, and that is a stated limit.** It models only what these
 * functions touch: a parent/child tree, `inert`, focus, `contains`, `addEventListener`, and a
 * `querySelector` that answers from a table the scenario supplies rather than parsing CSS. So a
 * bug in a SELECTOR is not visible here — that is what the source assertions in
 * `test_web_assets.py` still cover — while a bug in the BEHAVIOUR is.
 *
 * **And a shim that models a property WRONGLY is worse than one that omits it.** The first version
 * of this file gave `El` a plain own `inert` boolean. Real `inert` is INHERITED by the whole
 * subtree — `app.js` says so in its own comment — and the difference was not academic: a scenario
 * asserted that `#notices` was not inert while, in a browser, it sat inside the very `.layout` the
 * drawer had just inerted. The harness passed and the product was broken, which is the exact
 * failure this project has now hit three times (`_Response.read(size)` ignoring `size`;
 * `readableError`'s regex literals; this). `inertly()` therefore answers the question a browser
 * answers — "is this node inert, or is any ancestor?" — and scenarios must use it rather than
 * reading the flag.
 *
 * **What this shim still does NOT model, listed because a header that enumerates its limits has
 * to enumerate them all.** That cuts both ways, and this list got it wrong in BOTH directions: an
 * independent review once found three limits unstated, and the round after, two of the entries
 * written for them were still claiming gaps that had since been closed — which is worse, because a
 * reviewer trusting them skips a test that is writable. What is actually true today:
 *  - **`document.querySelector`/`querySelectorAll` are still TABLES** (`doc._one` / `doc._all`),
 *    answering `null`/`[]` for any selector a scenario did not pre-register. `inertEverythingExcept`
 *    and `syncRunGuards` both reach the tree through them, so a wrong selector in either is
 *    invisible here and covered only by the source assertions in `test_web_assets.py`. ELEMENT-level
 *    `querySelector`/`querySelectorAll`/`matches` are real (`matchesSel`) over the real subtree.
 *  - **No layout, no styles, no events beyond the listeners a scenario invokes by hand.** Anything
 *    about painted pixels, `opacity`, focus rings or hit-testing belongs in a real browser.
 *    `offsetParent` answers only the part of "is it rendered" that a tree can know.
 *  - **No timers, no network, no `requestAnimationFrame`** except what a scenario injects.
 *
 * Closed since, and named here so nobody re-states them as gaps: hiding a focused element blurs it
 * to `<body>`; `focus()` is a no-op on a hidden or disabled element; the element-level selector
 * engine is real for the subset `app.js` writes, including `[data-*]`, `[tabindex]` and `a[href]`;
 * and `document.createElement` exists, so a function that builds its own tree (`runStatus`) can be
 * executed rather than simulated.
 *
 * stdin:  {"scenario": "<name>"}
 * stdout: {"result": {...}}
 */
import { readFileSync } from "node:fs";
import { buildReadableError } from "./readable_error_parts.mjs";

const APP = new URL("../penumbra/web/app.js", import.meta.url);
const src = readFileSync(APP, "utf8");

function extract(name) {
  const head = `function ${name}(`;
  const at = src.indexOf(head);
  if (at < 0) throw new Error(`app.js no longer declares ${name}`);
  // Keep a leading `async`, or an extracted async function loses its await-ability and the
  // harness fails with a SyntaxError that looks like a bug in the product.
  const start = src.lastIndexOf("async ", at) === at - 6 ? at - 6 : at;
  return src.slice(start, src.indexOf("\n}\n", at) + 3);
}

function constant(name) {
  const found = src.match(new RegExp(`^const ${name} =[\\s\\S]*?;$`, "m"));
  if (!found) throw new Error(`app.js no longer declares ${name}`);
  return found[0];
}

//: The REAL `readableError`, assembled the way `readable_error_harness.mjs` assembles it — same
//: constants, same extraction by name. A scenario that shows the reader a message must show the
//: message the reader actually gets: with an identity stub, `openOrbitFailure("offline")`
//: reported Chrome's "Failed to fetch", which is the very string that branch exists to replace.
function realReadableError() {
  //: The SHARED builder — see `readable_error_parts.mjs`. This used to hold its own copy of the
  //: constant list, and adding three to the other harness left this one silently building a
  //: DIFFERENT function: not an error, just the wrong sentence in two scenarios.
  return buildReadableError(src);
}

// --- the shim -------------------------------------------------------------------------------
//: **A real matcher for the subset `app.js` actually writes**, replacing three separate lies: a
//: `matches()` that said yes to anything containing the word "button", a `querySelector` that read
//: a table a scenario filled in, and a `querySelectorAll` that returned `[]` unconditionally — so
//: `trapTab`'s whole body was unreachable and `if (true) return;` at the top of it left the suite
//: green. Supports comma lists, tag/`#id`/`.class`/`[attr]`/`[attr='v']`, `:not(...)`, `:disabled`
//: and `:enabled`. Deliberately NOT a CSS engine: combinators, `:last-of-type` and the rest throw
//: rather than quietly matching nothing, because silently answering "no" is how the old shim hid a
//: blocker. Anything needing those stays on the `_query` override or on `test_web_assets.py`.
function matchesSel(el, selector) {
  return selector.split(",").some((one) => matchesCompound(el, one.trim()));
}

//: The DOM's attribute-to-property mapping, for the names `app.js` actually writes. Without it
//: `[tabindex]`, `[tabindex='-1']`, `a[href]` and every `[data-*]` could NEVER match — the lookup
//: read `el.dataset["data-tip"]` and `el["tabindex"]`, neither of which exists — so those clauses
//: of `trapTab`, `trajTakeFocus` and `FOCUSABLE_TARGET` were dead in every scenario and could be
//: deleted green. Found by an independent review reading the engine that had just replaced the
//: tables; a matcher that silently answers "no" is the failure the tables were replaced for.
function attrValue(el, name) {
  if (name === "hidden" || name === "disabled") return el[name];
  if (name === "tabindex") return el.tabIndex;
  if (name.startsWith("data-")) {
    return el.dataset[name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())];
  }
  return el[name];
}

function matchesCompound(el, sel) {
  if (/[ >+~]/.test(sel)) throw new Error(`harness selector engine: no combinators (${sel})`);
  const parts = sel.match(/(\[[^\]]*\]|:not\([^)]*\)|::?[a-z-]+(\([^)]*\))?|#[\w-]+|\.[\w-]+|\*|[\w-]+)/g);
  if (!parts || parts.join("") !== sel) throw new Error(`harness selector engine: cannot parse ${sel}`);
  return parts.every((part) => {
    if (part === "*") return true;
    if (part.startsWith(":not(")) return !matchesSel(el, part.slice(5, -1));
    if (part === ":disabled") return !!el.disabled;
    if (part === ":enabled") return !el.disabled;
    if (part.startsWith(":")) throw new Error(`harness selector engine: unknown pseudo ${part}`);
    if (part.startsWith("#")) return el.id === part.slice(1);
    if (part.startsWith(".")) return String(el.className).split(/\s+/).includes(part.slice(1));
    if (part.startsWith("[")) {
      const [, name, , value] = part.slice(1, -1).match(/^([\w-]+)(=['"]?([^'"]*)['"]?)?$/) || [];
      if (!name) throw new Error(`harness selector engine: cannot parse ${part}`);
      const have = attrValue(el, name);
      if (value === undefined) return have !== undefined && have !== null && have !== false;
      return String(have) === value;
    }
    return el.tagName === part.toUpperCase();
  });
}

class El {
  constructor(id, tag = "div") {
    this.id = id;
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.children = [];
    this.parentElement = null;
    this.inert = false;
    this._hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.nodeType = 1;
    this.focused = 0;
    this.listeners = {};
    this.textContent = "";
    this.type = "";
    this.attributes = {};
    this.scrollTop = 0;
    this.scrollHeight = 0;
    this._query = {};
  }
  append(...kids) {
    for (const kid of kids) {
      kid.parentElement = this;
      this.children.push(kid);
    }
    return this;
  }
  // The DOM's own name, which the product uses.
  appendChild(kid) {
    return this.append(kid);
  }
  prepend(...kids) {
    for (const kid of kids.reverse()) {
      kid.parentElement = this;
      this.children.unshift(kid);
    }
  }
  remove() {
    const kin = this.parentElement && this.parentElement.children;
    if (kin) kin.splice(kin.indexOf(this), 1);
    this.parentElement = null;
  }
  contains(other) {
    for (let n = other; n; n = n.parentElement) if (n === this) return true;
    return false;
  }
  //: What a BROWSER computes, not what the flag on this node happens to say. `inert` is inherited,
  //: so a node is inert when it or any ancestor carries it.
  get inertly() {
    for (let n = this; n; n = n.parentElement) if (n.inert) return true;
    return false;
  }
  //: **Hiding a focused element blurs it to `<body>`** — what a browser does, and the gap that hid
  //: a real blocker: `trajTakeFocus` focused `#traj-run`, `renderTrajectory` then hid it, and every
  //: product path opened the drawer with focus on `<body>` while this shim reported success.
  get hidden() {
    return this._hidden;
  }
  set hidden(value) {
    this._hidden = value;
    if (value && doc.activeElement && this.contains(doc.activeElement)) doc.activeElement = doc.body;
  }
  //: Backed by `className`, so the selector engine and `classList` can never disagree.
  get classList() {
    const owner = this;
    const parts = () => String(owner.className).split(/\s+/).filter(Boolean);
    const write = (list) => {
      owner.className = list.join(" ");
    };
    return {
      add: (...names) => write([...new Set([...parts(), ...names])]),
      remove: (...names) => write(parts().filter((c) => !names.includes(c))),
      contains: (name) => parts().includes(name),
      toggle: (name, force) => {
        const on = force === undefined ? !parts().includes(name) : !!force;
        if (on) write([...new Set([...parts(), name])]);
        else write(parts().filter((c) => c !== name));
        return on;
      },
    };
  }
  //: A browser refuses to move focus onto something not rendered or disabled; focus stays where it
  //: was rather than landing somewhere invisible.
  get focusable() {
    if (this.disabled) return false;
    for (let n = this; n; n = n.parentElement) if (n._hidden) return false;
    return true;
  }
  //: `trapTab` filters on `offsetParent !== null` to mean "actually rendered". No layout here, so
  //: this answers the only part of that question the shim can know.
  get offsetParent() {
    return this.focusable || this.disabled ? (this.parentElement || null) : null;
  }
  focus() {
    if (!this.focusable) return;
    this.focused += 1;
    doc.activeElement = this;
  }
  addEventListener(kind, fn) {
    (this.listeners[kind] = this.listeners[kind] || []).push(fn);
  }
  //: Real attributes, so a scenario can ask what a screen reader would be told (`role`) rather
  //: than only what a mouse can do.
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
  }
  removeAttribute(name) {
    delete this.attributes[name];
  }
  //: Fires every listener a scenario registered for `kind`. No bubbling: nothing here needs it.
  dispatch(kind, event) {
    (this.listeners[kind] || []).forEach((fn) => fn(event));
  }
  matches(sel) {
    return matchesSel(this, sel);
  }
  //: Real matching over the real subtree, in document order. `_query` stays as an explicit
  //: override for the selectors the engine refuses (combinators, `:last-of-type`) — a scenario
  //: that sets one is saying so out loud rather than getting silence.
  querySelector(sel) {
    if (this._query[sel] !== undefined) return this._query[sel];
    return this.querySelectorAll(sel)[0] || null;
  }
  querySelectorAll(sel) {
    const out = [];
    const walk = (node) => {
      for (const kid of node.children) {
        if (matchesSel(kid, sel)) out.push(kid);
        walk(kid);
      }
    };
    walk(this);
    return out;
  }
}

//: **Document-level queries are STILL tables**, unlike the element-level ones above. Nothing has
//: needed a real document-wide walk, and a table makes each scenario say out loud which elements
//: its function is supposed to find. The cost is the one the header names: a wrong selector in
//: `inertEverythingExcept` or `syncRunGuards` cannot be seen from here.
const doc = {
  body: new El("body", "body"),
  activeElement: null,
  _all: {},
  _one: {},
  _byId: {},
  getElementById(id) {
    return this._byId[id] || null;
  },
  //: Real elements, so a function that BUILDS its own tree (`runStatus`) can be executed rather
  //: than simulated. Without this the shim could only call such a function's collaborators, which
  //: is how the `noteRunStarted` seam stayed unpinned by the test written to pin it.
  createElement(tag) {
    return new El("", tag);
  },
  createTextNode(data) {
    const node = new El("", "#text");
    node.nodeType = 3;
    node.textContent = data;
    return node;
  },
  //: The fallback chain `trajReturnTarget` walks. Answered from a table, like everywhere else here
  //: — the shim does not parse CSS.
  querySelector(sel) {
    return this._one[sel] || null;
  },
  querySelectorAll(sel) {
    if (sel === "#notices") return notices ? [notices] : [];
    return this._all[sel] || [];
  },
  listeners: {},
  addEventListener(kind, fn) {
    (this.listeners[kind] = this.listeners[kind] || []).push(fn);
  },
  dispatch(kind, event) {
    (this.listeners[kind] || []).forEach((fn) => fn(event));
  },
};
let notices = null;

// --- the tree every scenario uses -------------------------------------------------------------
//     body > .layout > [header, view-horizon, view-orbit]
//     body > notices, traj-backdrop, traj-drawer
//
// **This nesting IS the test's premise, so it is pinned against `index.html`** by
// `test_web_assets.py::test_the_toast_rail_is_outside_the_layout_every_overlay_inerts`. `#notices`
// sits at body level because `inert` is inherited: inside `.layout` it was swallowed whenever a
// body-level panel (the Trajectory drawer) inerted the layout, and no exemption could reach it,
// because it was never a sibling on that walk. A harness whose tree drifts from the markup is a
// harness that answers a question nobody asked.
function build() {
  doc.body.children = [];
  const layout = new El("layout");
  const header = new El("header", "header");
  const horizon = new El("view-horizon", "section");
  const orbit = new El("view-orbit", "main");
  layout.append(header, horizon, orbit);
  notices = new El("notices");
  const backdrop = new El("traj-backdrop");
  const drawer = new El("traj-drawer");
  const closeBtn = new El("traj-close", "button");
  const picker = new El("traj-run", "select");
  drawer.append(picker, closeBtn);
  doc.body.append(layout, notices, backdrop, drawer);
  return { layout, header, horizon, orbit, notices, backdrop, drawer, closeBtn, picker };
}

const SCENARIOS = {
  //: B2 + H1: the backdrop and the toast rail are the overlay's OWN machinery.
  //: `mode` is `"detach"` (the trigger is replaced while the drawer is open) or `"body"` (the
  //: trigger was ALREADY `<body>` when the drawer opened, which is what an `await` between the
  //: press and the open produces).
  drawerFocus(mode) {
    const detach = mode === "detach" || mode === true;
    const openedFromBody = mode === "body";
    const tree = build();
    const trigger = new El("settings-open", "button");
    const replacement = new El("fresh-ticker-toggle", "button");
    const composer = new El("ask-input", "button");
    tree.header.append(trigger, replacement, composer);
    doc._one = {};
    // The last rung of `trajReturnTarget`'s chain: with no live equivalent, focus goes to the
    // composer rather than nowhere.
    doc._byId = { "ask-input": composer };
    trigger.focus();

    const scope = { document: doc, trajEl: { drawer: tree.drawer, backdrop: tree.backdrop } };
    const run = new Function(
      "document", "trajEl",
      `${constant("ALWAYS_LIVE")}\n${extract("inertEverythingExcept")}\n${extract("trapTab")}\n` +
        `let trajReturnFocus = null; let trajInerted = []; let trajOpenedFrom = ${
          openedFromBody ? "document.body" : "null"
        };\n` +
        `${constant("FOCUSABLE_TARGET")}\n${extract("trajTakeFocus")}\n` +
        `${extract("trajReturnTarget")}\n${extract("trajReleaseFocus")}\n` +
        "return { take: trajTakeFocus, release: trajReleaseFocus, held: () => trajInerted };"
    )(scope.document, scope.trajEl);

    run.take();
    // **The trigger a chat re-render has replaced.** `.ticker-toggle` lives inside a turn, and any
    // re-render between opening and closing detaches the node the drawer recorded — `.focus()` on
    // it is then a silent no-op and the reader is left on `<body>`, which is the same state as
    // opening on `<body>`. `detach` says whether to simulate that.
    if (detach) {
      trigger.remove();
      doc._one[".turn:last-of-type .ticker-affordance .ticker-toggle"] = replacement;
    }
    const whileOpen = {
      inerted: doc.body.children
        .concat(tree.layout.children)
        .filter((e) => e.inertly)
        .map((e) => e.id),
      focusInsideDrawer: tree.drawer.contains(doc.activeElement),
      backdropInert: tree.backdrop.inertly,
      noticesInert: tree.notices.inertly,
      trapInstalled: (tree.drawer.listeners.keydown || []).length,
    };
    run.release();
    return {
      whileOpen,
      afterClose: {
        stillInert: doc.body.children
          .concat(tree.layout.children)
          .filter((e) => e.inertly)
          .map((e) => e.id),
        focusBack: doc.activeElement && doc.activeElement.id,
        focusIsAttached: !!(doc.activeElement && doc.body.contains(doc.activeElement)),
        held: run.held().length,
      },
    };
  },

  //: **Round ten's drawer fix, which shipped with no test — both halves of it reverted green.**
  //: `trajShowDrawer` focuses the drawer's first focusable; `renderTrajectory` then sets
  //: `trajEl.run.hidden = runIds.length < 2`. Every persisted "Steps" pill opens with ONE run id,
  //: so the picker was hidden a moment after being focused, and hiding a focused element blurs it
  //: to `<body>`: two Tab presses to reach anything, under an `aria-modal` that hides the page
  //: behind from a screen reader the whole time.
  //:
  //: `mode` is the ORDER of the two effects. "render-first" is what ships; "focus-first" is the
  //: bug, reproduced through the same real `trajTakeFocus`. The hide itself stands in for
  //: `renderTrajectory`, which is far too large to run here — the order is what is under test.
  drawerFocusOrder(mode) {
    const tree = build();
    const back = new El("traj-prev", "button");
    const search = new El("traj-search", "input");
    // **This order is `index.html`'s**: `#traj-run`, then the transport, then `#traj-close`, and
    // `#traj-search` a long way below. It is the premise of the test — put the search box first and
    // the `:not(:disabled)` clause can be deleted with everything still green, because the disabled
    // transport button would never have been the first match anyway.
    tree.drawer.append(back, search);
    back.disabled = true; // a trace with no turns: the transport is off
    doc._one = {};
    doc._byId = {};
    doc.activeElement = doc.body;

    const run = new Function(
      "document", "trajEl",
      `${constant("ALWAYS_LIVE")}\n${extract("inertEverythingExcept")}\n${extract("trapTab")}\n` +
        "let trajReturnFocus = null; let trajInerted = []; let trajOpenedFrom = null;\n" +
        `${constant("FOCUSABLE_TARGET")}\n${extract("trajTakeFocus")}\n` +
        "return { take: trajTakeFocus };"
    )(doc, { drawer: tree.drawer, backdrop: tree.backdrop });

    const hidePickerForASingleRunTrace = () => {
      tree.picker.hidden = true;
    };
    if (mode === "focus-first") {
      run.take();
      hidePickerForASingleRunTrace();
    } else {
      hidePickerForASingleRunTrace();
      run.take();
    }
    const landed = doc.activeElement;
    return {
      focusedId: landed && landed.id,
      onBody: landed === doc.body,
      insideDrawer: tree.drawer.contains(landed),
      // The disabled transport button must never be the answer either - the `:not(:disabled)` half.
      onDisabled: !!(landed && landed.disabled),
      onHidden: !!(landed && landed.hidden),
    };
  },

  //: `trapTab` — whose body an independent review found UNREACHABLE here, because the old shim's
  //: `querySelectorAll` returned `[]` for every selector. `if (true) return;` at the top of it left
  //: 961 tests passing. It now runs against the real subtree.
  tabTrap() {
    const tree = build();
    const first = new El("traj-search", "input");
    const middle = new El("traj-hidden-one", "button");
    const last = new El("traj-copy", "button");
    tree.drawer.append(first, middle, last);
    middle.hidden = true; // not rendered: `offsetParent === null`
    tree.picker.disabled = true; // excluded by `:not([disabled])`
    // The three attribute clauses, which could never match until `attrValue` existed and so were
    // deletable green: `a[href]` matches only an anchor WITH one, `[tabindex]` matches a custom
    // stop, and `[tabindex='-1']` is excluded by name.
    const link = new El("traj-link", "a");
    link.href = "https://example.com/spec";
    const bareAnchor = new El("traj-anchor", "a"); // an anchor with no href is not a tab stop
    const custom = new El("traj-custom", "div");
    custom.tabIndex = 0;
    const programmatic = new El("traj-programmatic", "div");
    programmatic.tabIndex = -1; // reachable by script, never by Tab
    tree.drawer.append(link, bareAnchor, custom, programmatic);
    const run = new Function("document", `${extract("trapTab")}\nreturn trapTab;`)(doc);
    // What `trapTab` itself will compute, so the presses below land on the real ends of the ring
    // rather than on whichever element this scenario happened to append first.
    const candidates = [...tree.drawer.querySelectorAll(
      "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), " +
      "textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
    )].filter((el) => el.offsetParent !== null);

    const press = (target, shiftKey) => {
      doc.activeElement = target;
      let prevented = false;
      run(tree.drawer, { key: "Tab", shiftKey, preventDefault: () => (prevented = true) });
      return { landed: doc.activeElement && doc.activeElement.id, prevented };
    };
    const ends = { first: candidates[0], last: candidates[candidates.length - 1] };
    return {
      candidates: candidates.map((el) => el.id),
      forwardFromLast: press(ends.last, false),
      backFromFirst: press(ends.first, true),
      interiorIsLeftAlone: press(candidates[1], false),
      // Not a Tab at all: the handler must not touch anything.
      otherKey: (() => {
        doc.activeElement = ends.last;
        let prevented = false;
        run(tree.drawer, { key: "a", preventDefault: () => (prevented = true) });
        return { landed: doc.activeElement.id, prevented };
      })(),
      excluded: {
        hidden: middle.id,
        disabled: tree.picker.id,
        anchorWithoutHref: bareAnchor.id,
        negativeTabindex: programmatic.id,
      },
    };
  },

  //: **One dropped request used to fabricate the reader's orbit.** `openOrbit`'s `catch` was
  //: bare, so every failure meant "does not exist yet": an orbit with real sources and turns
  //: rendered empty, silently, and did not heal. `mode` is the failure to serve.
  openOrbitFailure(mode) {
    build();
    const notices = [];
    const switched = [];
    const state = {};
    const errors = {
      "404-fresh": { status: 404, message: "404: no such orbit" },
      "404-known": { status: 404, message: "404: no such orbit" },
      corrupt: {
        status: 409,
        message: "409: orbits/x.json exists but is not a valid orbit file (ValidationError)",
      },
      offline: { message: "Failed to fetch" }, // `fetch` rejecting: no status at all
      server: { status: 500, message: "500: Internal Server Error" },
    };
    const fail = errors[mode];
    const api = async () => {
      const err = new Error(fail.message);
      if (fail.status !== undefined) err.status = fail.status;
      throw err;
    };

    const run = new Function(
      "api", "notify", "t", "readableError", "state", "store", "refreshOrbitList",
      "showOrbitView", "reattachInFlightRuns",
      `let orbitGeneration = 0;\n${extract("openOrbit")}\nreturn openOrbit;`
    )(
      api,
      (message) => notices.push(message),
      (key, fallback) => fallback,
      realReadableError(),
      state,
      { emit: (name, payload) => switched.push([name, payload]) },
      () => {},
      () => switched.push(["view", null]),
      async () => {}
    );

    return run("nb-real", { push: false, fresh: mode === "404-fresh" }).then((opened) => ({
      opened: opened === true,
      // The fabrication: did it install an orbit into `state` at all?
      invented: Object.prototype.hasOwnProperty.call(state, "sources"),
      switchedView: switched.some(([name]) => name === "view"),
      notices,
    }));
  },

  // The real inline renderer over one paragraph, flattened to `tag:text` pairs.
  markdownInline() {
    build();
    const render = new Function(
      "document",
      ["MD_FENCE", "MD_HEADING", "MD_QUOTE", "MD_BULLET", "MD_ORDERED", "MD_RULE",
        "MD_TABLE_DIVIDER", "MD_INLINE"].map(constant).join("\n") + "\n" +
        ["mdIsSpace", "mdIsWord"].map(constant).join("\n") + "\n" +
        ["mdLines", "mdLinkAt", "mdMarkerOpens", "mdMarkerCloses", "mdFindClose", "renderInline",
         "mdTableRowCells", "renderMarkdownInto"].map(extract).join("\n") +
        "\nreturn renderMarkdownInto;"
    )(doc);
    const text = "~~Chunk size~~ matters less than overlap, and ~ alone or a~~b stays plain.";
    const root = new El("", "div");
    render(root, text, (parent, from, to) => {
      const leaf = new El("", "#text");
      leaf.textContent = text.slice(from, to);
      parent.appendChild(leaf);
    });
    const out = [];
    const walk = (node) => node.children.forEach((kid) => {
      if (kid.tagName === "#TEXT") out.push(`${node.tagName}:${kid.textContent}`);
      else walk(kid);
    });
    walk(root);
    return { parts: out };
  },

  //: **The product's signature interaction, executed.** `DESIGN.md` §2 calls the stroke "the
  //: literal visual expression of the product's core value", and it was bound to `click` and
  //: `mouseenter` alone: no `tabindex`, no `role`, no key handler. A recorded Tab walk of a whole
  //: orbit — 37 stops — reached not one citation. SC 2.1.1 and SC 4.1.2, both Level A.
  //:
  //: Runs the REAL `renderAnswerWithCitations` and the REAL markdown renderer beneath it, which is
  //: what `document.createElement`/`createTextNode` bought: the stroke under test is the one the
  //: reader gets, including the case that only happens through markdown (a stroke crossing `**`
  //: emits more than one span).
  citationStroke(mode) {
    build();
    const lit = [];
    const opened = [];
    const citations = [
      { source_id: "s1", locator: "page:2", quote: "q1", answer_span: "grounded **claim** here" },
    ];
    const answer = "A sentence with a grounded **claim** here, and a tail.";

    const run = new Function(
      "document", "t", "collectReferences", "referenceKey", "citationHoverLabel", "sourceLabel",
      "sourceDisplayName", "linkReference", "focusReference", "renderReferenceLink",
      "referenceNumberFor",
      ["MD_FENCE", "MD_HEADING", "MD_QUOTE", "MD_BULLET", "MD_ORDERED", "MD_RULE",
        "MD_TABLE_DIVIDER", "MD_INLINE"].map(constant).join("\n") + "\n" +
        ["mdIsSpace", "mdIsWord"].map(constant).join("\n") + "\n" +
        ["mdLines", "mdLinkAt", "mdMarkerOpens", "mdMarkerCloses", "mdFindClose", "renderInline",
         "mdTableRowCells", "renderMarkdownInto"].map(extract).join("\n") +
        `\n${extract("renderAnswerWithCitations")}\nreturn renderAnswerWithCitations;`
    )(
      doc,
      (key, fallback) => fallback,
      () => citations,
      (c) => `${c.source_id}\u001f${c.locator}`,
      (c) => `Source one · ${c.locator}`,
      () => "Source one",
      () => "Source one",
      (key, on) => lit.push([key, on]),
      (c) => opened.push(c.source_id),
      () => new El("", "a"),
      () => 1
    );

    // `runId` is what makes a stroke clickable at all: a turn saved before run ids existed renders
    // plain, non-interactive citations on purpose (invariant 29's graceful degradation).
    const root = run(answer, citations, mode === "no-run" ? null : "nb-1-abc");
    const strokes = root.querySelectorAll(".citation");
    //: The OPERABLE one — the last fragment, which is where the number goes. A split stroke is one
    //: citation, so it is one tab stop, and this is the span a keyboard reader actually lands on.
    const first = strokes[strokes.length - 1];
    if (!first) return { strokes: 0 };

    const before = lit.length;
    first.dispatch("focus", {});
    const litOnFocus = lit.length > before && lit[lit.length - 1][1] === true;
    first.dispatch("blur", {});
    const clearedOnBlur = lit[lit.length - 1][1] === false;

    let prevented = false;
    first.dispatch("keydown", { key: "Enter", preventDefault: () => (prevented = true) });
    const afterEnter = opened.length;
    first.dispatch("keydown", { key: " ", preventDefault: () => {} });
    first.dispatch("keydown", { key: "x", preventDefault: () => {} });

    return {
      strokes: strokes.length,
      tagName: first.tagName,
      tabIndex: first.tabIndex === undefined ? null : first.tabIndex,
      role: first.getAttribute("role"),
      hasKeydown: (first.listeners.keydown || []).length,
      litOnFocus,
      clearedOnBlur,
      openedByEnter: afterEnter,
      openedTotal: opened.length,
      preventedDefault: prevented,
      // ONE tab stop per citation, on the fragment that carries the number. The others stay
      // clickable and hoverable but leave the accessibility tree alone.
      operable: [...strokes].filter((s) => s.tabIndex === 0).length,
      numbered: [...strokes].filter((s) => s.dataset.reference !== undefined).length,
      hiddenFragments: [...strokes].filter((s) => s.getAttribute("aria-hidden") === "true").length,
      lastIsTheOperableOne:
        strokes.length > 1 &&
        strokes[strokes.length - 1].tabIndex === 0 &&
        strokes[strokes.length - 1].getAttribute("role") === "button",
    };
  },

  //: **Keyboard shortcuts, which the product had none of.** Every global `keydown` in `app.js`
  //: handled exactly one key (`Escape`), and on the screen built for capture the field was the
  //: sixteenth tab stop. `mode` picks the situation: which view, and whether the find field is
  //: rendered at all — an empty Horizon hides it, which is what makes "decline and let the browser
  //: keep its own ⌘F" the interesting case rather than a detail.
  shortcuts(mode) {
    const tree = build();
    doc.listeners = {};
    const capture = new El("capture-input", "textarea");
    const ask = new El("ask-input", "textarea");
    const find = new El("stream-search", "input");
    const settings = new El("settings-open", "button");
    tree.horizon.append(capture, find);
    tree.orbit.append(ask);
    tree.header.append(settings);
    doc._byId = {
      "capture-input": capture,
      "ask-input": ask,
      "stream-search": find,
      "settings-open": settings,
    };
    // An empty Horizon hides the find field, and `.focus()` on something not rendered is a no-op.
    if (mode === "no-find") find.hidden = true;
    doc.body.dataset = doc.body.dataset || {};
    doc.body.dataset.view = mode === "orbit" ? "orbit" : "horizon";
    let opened = 0;
    settings.click = () => (opened += 1);

    const run = new Function(
      "document", "showHorizon",
      `${constant("SHORTCUTS")}\n` +
        ["viewIsHorizon", "syncSkipLink", "focusIfUsable", "clickIfPresent", "focusFind",
         "installShortcuts"].map(extract).join("\n") +
        "\nreturn installShortcuts;"
    )(doc, () => {
      doc.body.dataset.view = "horizon";
    });
    run();

    const press = (key, mods = { metaKey: true }) => {
      let prevented = false;
      doc.dispatch("keydown", { key, ...mods, preventDefault: () => (prevented = true) });
      return { focus: doc.activeElement && doc.activeElement.id, prevented };
    };

    doc.activeElement = doc.body;
    return {
      cmdK: press("k"),
      cmdF: press("f"),
      cmdComma: (() => {
        const r = press(",");
        return { ...r, opened };
      })(),
      // A bare letter must never be swallowed: this product is mostly a text field.
      plainK: press("k", {}),
      // Ctrl is the same binding on Windows/Linux.
      ctrlK: (() => {
        doc.activeElement = doc.body;
        return press("k", { ctrlKey: true });
      })(),
      // An unbound combination is left entirely alone.
      cmdP: press("p"),
    };
  },

  //: **The audio transport**, which was `<audio controls>` — the browser's stock black pill inside
  //: a hand-drawn ink-on-paper panel, on the most expensive artifact in the product, and the worst
  //: thing to leave cross-platform because a Tauri build is three different players.
  transport() {
    build();
    const fired = {};
    const player = {
      paused: true,
      ended: false,
      duration: NaN,
      currentTime: 0,
      played: 0,
      paused_calls: 0,
      listeners: {},
      addEventListener(kind, fn) {
        (this.listeners[kind] = this.listeners[kind] || []).push(fn);
      },
      emit(kind) {
        fired[kind] = (fired[kind] || 0) + 1;
        (this.listeners[kind] || []).forEach((fn) => fn());
      },
      play() {
        this.played += 1;
        this.paused = false;
        this.emit("play");
        return { catch: () => {} };
      },
      pause() {
        this.paused_calls += 1;
        this.paused = true;
        this.emit("pause");
      },
    };

    const run = new Function(
      "document", "t",
      ["elt", "formatTimecode", "buildTransport"].map(extract).join("\n") +
        "\nreturn buildTransport;"
    )(doc, (key, fallback) => fallback);

    const bar = run(player);
    const play = bar.querySelectorAll(".transport-play")[0];
    const scrub = bar.querySelectorAll(".transport-scrub")[0];
    const clock = bar.querySelectorAll(".transport-time")[0];
    const snap = () => ({
      label: play.getAttribute("aria-label"),
      glyph: play.textContent,
      clock: clock.textContent,
      scrubMax: scrub.max,
      scrubOff: scrub.disabled,
      valuetext: scrub.getAttribute("aria-valuetext"),
    });

    // Before metadata: no duration is known, so the scrub cannot lie about where it is.
    const cold = snap();

    player.duration = 154;
    player.emit("loadedmetadata");
    const ready = snap();

    play.dispatch("click", {});
    const playing = snap();

    player.currentTime = 65;
    player.emit("timeupdate");
    const advanced = { ...snap(), scrubValue: scrub.value };

    // A drag or an arrow key seeks LIVE, which is what makes the transcript follow the handle.
    scrub.value = "100";
    scrub.dispatch("input", {});
    const afterDrag = { seekedTo: player.currentTime, clock: clock.textContent };

    play.dispatch("click", {});
    const paused = snap();

    return {
      cold,
      ready,
      playing,
      advanced,
      afterDrag,
      paused,
      plays: player.played,
      pauses: player.paused_calls,
      // The element itself must never grow chrome again.
      role: play.tagName,
      scrubIsRange: scrub.type,
    };
  },

  //: **The locked-out state rendered the whole application as live.** No `?token=` — an ordinary
  //: bookmark loses the query string — gave a facet rail, "+ New orbit", Settings and a FOCUSED
  //: capture field, all of them dead, with the only remedy being a sentence telling the reader to
  //: hand-edit a URL. There was no field anywhere in the product to paste a token into.
  tokenGate() {
    const tree = build();
    const gate = new El("token-gate");
    const field = new El("token-gate-input", "input");
    const error = new El("token-gate-error", "p");
    error.hidden = true;
    gate.append(field, error);
    gate.hidden = true;
    doc.body.append(gate);
    doc._byId = { "token-gate": gate, "token-gate-input": field, "token-gate-error": error };
    doc.activeElement = doc.body;

    const run = new Function(
      "document", "t",
      `${constant("ALWAYS_LIVE")}\n${extract("inertEverythingExcept")}\n` +
        "let tokenGateOpen = false;\nconst isDesktopShell = () => false;\n" +
        `${extract("showTokenGate")}\n` +
        "return { show: showTokenGate, twice: () => tokenGateOpen };"
    )(doc, (key, fallback) => fallback);

    run.show("That token was not accepted.");
    return {
      shown: !gate.hidden,
      focused: doc.activeElement && doc.activeElement.id,
      errorShown: !error.hidden,
      errorText: error.textContent,
      // Everything behind it is UNREACHABLE, not merely unhelpful — the drawer's own treatment.
      layoutInert: tree.layout.inertly,
      headerInert: tree.header.inertly,
      captureInert: tree.horizon.inertly,
      gateInert: gate.inertly,
      // ...and the toast rail stays live, because a notice about the failure has to land somewhere.
      noticesInert: tree.notices.inertly,
    };
  },

  //: `sourceDisplayName` — the one function the source row's `aria-label`, the source viewer's
  //: heading and the citation labels all read.
  sourceName() {
    const run = new Function(
      "t",
      constant("PASTED_SNIPPET_CAP") + "\n" +
        ["pastedExcerpt", "sourceDisplayName"].map(extract).join("\n") +
        "\nreturn sourceDisplayName;"
    )((key, fallback) => fallback);
    const withPreview = (title) => ({
      origin: "https://example.com/a", preview: { title },
    });
    return {
      withTitle: run(withPreview("Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks")),
      noPreview: run({ origin: "https://example.com/a" }),
      blankTitle: run(withPreview("   ")),
      pasted: run({ origin: "pasted:a pasted note about voyager #abc123" }),
    };
  },

  //: The Trajectory axis, which labelled itself with the run's wall clock while the strip beside it
  //: partitioned tool time.
  trajAxis() {
    const axisEnd = new El("traj-axis-end", "span");
    const trajData = {
      total_s: 99.1,
      timeline: [{ duration_s: 0.18 }, { duration_s: 0.0 }, { duration_s: 0.002 }, { duration_s: 0.003 }],
    };
    //: The REAL `trajAxisLabel`, extracted by name. The first version of this scenario rebuilt the
    //: expression by hand, so reverting the product to the wall clock left it green.
    const run = new Function(
      ["formatTimecode", "formatTrajDuration", "trajAxisLabel"].map(extract).join("\n") +
        "\nreturn { label: trajAxisLabel, fmt: formatTrajDuration };"
    )();
    axisEnd.textContent = run.label(trajData);
    return {
      axis: axisEnd.textContent,
      subSecond: run.fmt(0.185),
      seconds: run.fmt(2.9),
      minutes: run.fmt(99.1),
    };
  },

  //: `collectReferences` decides the NUMBERING the interface owns (invariant 48.5), and it ordered
  //: by the array the model emitted rather than by where the reader meets each mark.
  referenceOrder() {
    const prose = "Alpha comes first. Beta comes second. Gamma comes third.";
    const cite = (id, span) => ({ source_id: id, locator: "whole", quote: id, answer_span: span });
    const state = {
      //: Deliberately OUT of order, which is what a model citing a source it wrote about earlier
      //: produces — measured on a real orbit as marks running 1, 3, 4, 6, 5.
      overview: { text: prose, citations: [cite("s3", "Gamma"), cite("s1", "Alpha"), cite("s2", "Beta")] },
      turns: [{ answer: prose, citations: [cite("s9", "Beta"), cite("s8", "Alpha")] }],
    };
    const run = new Function(
      "state",
constant("REFERENCE_KEY_SEP") + "\n" + ["referenceKey", "collectReferences"].map(extract).join("\n") + "\nreturn collectReferences;"
    )(state);
    const ordered = run().map((r) => r.source_id);

    //: A citation with no span cannot be located, so it keeps its array position.
    const noSpans = new Function(
      "state",
constant("REFERENCE_KEY_SEP") + "\n" + ["referenceKey", "collectReferences"].map(extract).join("\n") + "\nreturn collectReferences;"
    )({
      overview: { text: prose, citations: [
        { source_id: "b", locator: "whole" }, { source_id: "a", locator: "whole" }] },
      turns: [],
    })().map((r) => r.source_id);

    //: **The MIXED case, which is the designed common one** — `instructions.py` tells the model to
    //: leave `answer_span` out when it cannot point precisely, and `locate_answer_spans` nulls any
    //: span it cannot find verbatim. The first comparator written here was inconsistent, so one
    //: span-less citation dragged its neighbours back into emission order.
    const mixed = (citations) =>
      new Function(
        "state",
        constant("REFERENCE_KEY_SEP") + "\n" +
          ["referenceKey", "collectReferences"].map(extract).join("\n") +
          "\nreturn collectReferences;"
      )({ overview: { text: prose, citations }, turns: [] })().map((r) => r.source_id);

    //: **The other five surfaces that render the same numbered stroke.** The pass above was
    //: applied to the overview and the chat turns only, so a Timeline read `[3] … [1] … [2]` while
    //: the overview above it read `[1] [2] [3]` — and the export renumbers from this same list, so
    //: the wrong numbers left the product as a file. Each carries its own prose: an utterance's
    //: `text`, a summary/insight's `text`, an FAQ item's `answer`, a timeline event's
    //: `description`.
    const otherSurfaces = new Function(
      "state",
constant("REFERENCE_KEY_SEP") + "\n" + ["referenceKey", "collectReferences"].map(extract).join("\n") + "\nreturn collectReferences;"
    )({
      turns: [],
      podcast: { utterances: [{ text: prose, citations: [cite("p3", "Gamma"), cite("p1", "Alpha")] }] },
      guides: {
        summary: { result: { text: prose, citations: [cite("g3", "Gamma"), cite("g1", "Alpha")] } },
        faq: { result: { items: [{ answer: prose, citations: [cite("f3", "Gamma"), cite("f1", "Alpha")] }] } },
        timeline: {
          result: {
            events: [{ description: prose, citations: [cite("t3", "Gamma"), cite("t1", "Alpha")] }],
          },
        },
      },
    })().map((r) => r.source_id);

    return {
      ordered,
      otherSurfaces,
      noSpans,
      // Gamma, (none), Alpha -> the reader meets Alpha first, and the span-less one does not move.
      oneMissingInTheMiddle: mixed([cite("s3", "Gamma"), { source_id: "sX", locator: "whole" }, cite("s1", "Alpha")]),
      // ...and one missing THIRD of four leaves it exactly at index 2.
      oneMissingThirdOfFour: mixed([
        cite("s3", "Gamma"), cite("s2", "Beta"), { source_id: "sX", locator: "whole" }, cite("s1", "Alpha"),
      ]),
    };
  },

  //: **The artifact leaving the product**, which until now it could not do in any form: no copy on
  //: an answer, the overview or a Guide kind, no orbit export, and `@media print` matched zero
  //: rules. Runs the real `orbitMarkdown` / `artifactMarkdown` / `guideMarkdown`.
  //: **Printing hid the reference list and kept the numbers.** Runs the real
  //: `installPrintReferences` against a window that records listeners, then fires them.
  printReferences() {
    const listeners = {};
    const win = { addEventListener: (type, fn) => { (listeners[type] ||= []).push(fn); } };
    const fire = (type) => (listeners[type] || []).forEach((fn) => fn());
    const history = new El("chat-history", "div");
    doc._byId["chat-history"] = history;
    const cite = (id, span, extra = {}) =>
      ({ source_id: id, locator: "page:1", quote: `q-${id}`, answer_span: span, ...extra });
    const state = {
      title: "Voyager notes",
      sources: [{ id: "s1", origin: "a.txt" }, { id: "s2", origin: "b.txt" }],
      overview: { text: "Alpha then Beta.", citations: [cite("s2", "Beta"), cite("s1", "Alpha", { verified: false })] },
      turns: [],
    };
    new Function(
      "state", "t", "document", "window",
      constant("REFERENCE_KEY_SEP") + "\n" +
        ["referenceKey", "collectReferences", "pastedExcerpt", "sourceDisplayName", "sourceLabel", "elt",
         "printReferenceList", "installPrintReferences"].map(extract).join("\n") +
        constant("PASTED_SNIPPET_CAP") + "\n" +
        "installPrintReferences();"
    )(state, (key, fallback) => fallback, doc, win);

    const text = (node) => node.textContent + node.children.map(text).join("");
    doc.body.dataset.view = "horizon";
    fire("beforeprint");
    const onTheHorizon = history.children.length;
    fire("afterprint");

    doc.body.dataset.view = "orbit";
    fire("beforeprint");
    const title = history.children.find((c) => c.className === "print-title");
    const titleFirst = history.children[0] === title;
    const section = history.children.find((c) => c.className === "print-references");
    const items = section ? section.children.find((c) => c.tagName === "OL") : null;
    const printed = items ? items.children.map(text) : [];
    fire("beforeprint"); // a second print dialog must not stack a second list
    const afterTwoPrints = history.children.length;
    fire("afterprint");
    return {
      onTheHorizon, printed, afterTwoPrints, afterPrint: history.children.length,
      title: title ? title.textContent : null, titleFirst,
    };
  },

  //: **Removing a source left chat and podcast citations to it looking verified until a reload.**
  //: Runs the REAL `.src-remove` handler out of `renderSourceItem` (collaborators stubbed), then the
  //: REAL `renumberStrokes` over strokes rendered BEFORE the removal, the way the page holds them.
  async removeSourceReverifies() {
    const key = (id, loc) => `${id}\u001f${loc}`;
    const before = { source_id: "s1", locator: "page:1", quote: "alpha", verified: true };
    const after = { ...before, verified: false };
    const state = {
      orbitId: "nb",
      sources: [{ id: "s1", origin: "a.txt" }, { id: "s2", origin: "b.txt" }],
      overview: null,
      turns: [{ question: "q", answer: "alpha", citations: [before] }],
      podcast: { utterances: [{ speaker: "host_a", text: "alpha", citations: [before] }] },
      guides: {},
    };
    const server = {
      sources: [{ id: "s2", origin: "b.txt" }],
      overview: null,
      turns: [{ question: "q", answer: "alpha", citations: [after] }],
      podcast: { utterances: [{ speaker: "host_a", text: "alpha", citations: [after] }] },
    };
    const emitted = [];
    let refreshed = 0;
    //: Strokes as they were painted before the removal: one in a turn, one in the podcast, which
    //: `renumberStrokes` must re-stamp in place (rebuilding the podcast would stop playback).
    const turnStroke = new El("", "span");
    const podcastStroke = new El("", "span");
    for (const span of [turnStroke, podcastStroke]) {
      span.className = "citation";
      span.dataset.refKey = key("s1", "page:1");
    }
    //: ...and one stroke split in two by `*emphasis*`: only its LAST fragment may carry the number.
    const fragHead = new El("", "span");
    const fragEnd = new El("", "span");
    for (const span of [fragHead, fragEnd]) {
      span.className = "citation";
      span.dataset.refKey = key("s2", "whole");
    }
    fragEnd.dataset.strokeEnd = "";
    state.turns[0].citations.push({ source_id: "s2", locator: "whole", quote: "beta", verified: true });
    server.turns[0].citations.push({ source_id: "s2", locator: "whole", quote: "beta", verified: true });
    doc._all[".citation[data-ref-key]"] = [turnStroke, podcastStroke, fragHead, fragEnd];

    const helpers = ["referenceKey", "collectReferences", "pastedExcerpt", "sourceDisplayName", "sourceLabel",
      "citationHoverLabel", "renumberStrokes", "kindLabel", "readableFlag", "renderSourceItem"].map(extract).join("\n");
    const run = new Function(
      "state", "t", "document", "window", "api", "store", "confirmAction", "notify", "renderChatOverview",
      "showSourceViewer", "prettyOrigin", "refreshReferenceView",
      constant("REFERENCE_KEY_SEP") + "\n" + constant("FLAG_KEYS") + "\n" + helpers +
        constant("PASTED_SNIPPET_CAP") + "\n" +
        "return { renderSourceItem, renumberStrokes };"
    );
    let fns;
    fns = run(
      state, (k, fallback) => fallback, doc, { getSelection: () => null },
      async () => server,
      { emit: (name) => emitted.push(name) },
      async () => true, () => {}, () => {}, () => {}, (o) => o,
      () => { refreshed += 1; fns.renumberStrokes(); },
    );
    const li = fns.renderSourceItem(state.sources[0]);
    const remove = li.children.find((c) => c.className === "src-remove");
    await remove.listeners.click[0]({ stopPropagation() {} });
    return {
      turnVerified: state.turns[0].citations[0].verified,
      emitted,
      refreshed,
      turnStroke: { cls: turnStroke.className, title: turnStroke.title },
      podcastStroke: { cls: podcastStroke.className, title: podcastStroke.title },
      fragments: [fragHead.dataset.reference ?? null, fragEnd.dataset.reference ?? null],
    };
  },

  exportMarkdown() {
    const state = {
      title: "Voyager notes",
      sources: [
        { id: "s1", origin: "https://example.com/a", preview: { title: "Crossing the heliopause" } },
        { id: "s2", origin: "notes.txt" },
        //: A PASTED source whose opening words span a blank line — the capture path the product
        //: leads with, and the one that broke every list item it appeared in.
        { id: "s3", origin: "pasted:Alpha is first.\n\nBeta is second. #64f31058" },
      ],
      overview: {
        text: "The boundary was crossed in 2012.",
        citations: [{ source_id: "s1", locator: "page:2", quote: "electron density", verified: true }],
      },
      turns: [
        {
          question: "When did it cross?",
          answer: "In August 2012.",
          citations: [
            { source_id: "s1", locator: "page:2", quote: "electron density", verified: true },
            { source_id: "s2", locator: "whole", quote: "a later note", verified: false },
            { source_id: "s3", locator: "whole", quote: "Alpha is first.\n\nBeta", verified: true },
          ],
        },
      ],
      notes: [{ id: "n1", text: "check the power budget" }],
    };
    const run = new Function(
      "state", "t",
      constant("REFERENCE_KEY_SEP") + "\n" +
        ["referenceKey", "collectReferences", "pastedExcerpt", "sourceDisplayName", "sourceLabel",
         "markdownInline", "referenceListMarkdown", "artifactMarkdown", "guideMarkdown", "orbitMarkdown"]
          .map(extract).join("\n") +
        constant("PASTED_SNIPPET_CAP") + "\n" + constant("GUIDE_KIND_LABELS") + "\n" +
        "return { orbit: orbitMarkdown, guide: guideMarkdown, artifact: artifactMarkdown };"
    )(state, (key, fallback) => fallback);

    const orbit = run.orbit();
    return {
      orbit,
      // An FAQ flattens its question/answer pairs; a timeline flattens its events. All three shapes
      // end in `artifactMarkdown`, so all three carry their references out.
      faq: run.guide("faq", {
        items: [{ question: "Q?", answer: "A.", citations: [
          { source_id: "s1", locator: "page:2", quote: "electron density" }] }],
      }),
      //: **`description`, the field `schema.TimelineEvent` declares** — this fixture said `what`,
      //: which matched the code under test and nothing the server has ever sent, so the assertion
      //: passed while Copy on a Timeline dropped every event's text. A fixture written against the
      //: implementation instead of the wire tests that the implementation agrees with itself.
      timeline: run.guide("timeline", {
        events: [{ when: "2012", description: "crossed the heliopause", citations: [] }],
      }),
    };
  },

  //: The same rule from the other side: a MODAL must still inert the page behind it.
  modalStillInertsThePage() {
    const tree = build();
    const overlay = new El("settings-overlay");
    tree.layout.append(overlay);
    const run = new Function(
      "document",
      `${constant("ALWAYS_LIVE")}\n${extract("inertEverythingExcept")}\nreturn inertEverythingExcept;`
    )(doc);
    const touched = run(overlay);
    return {
      touched: touched.map((e) => e.id),
      headerInert: tree.header.inertly,
      horizonInert: tree.horizon.inertly,
      noticesInert: tree.notices.inertly,
      backdropInert: tree.backdrop.inertly,
    };
  },

  //: **`syncRunGuards`, which round eight shipped with no test of any kind** — an independent
  //: review put `if (true) return;` in its body and all 945 tests stayed green, on the one fix the
  //: CHANGELOG prices in money. Fourth instance of this project's recurring failure, in the newest
  //: code, in the class the harness beside it was built for.
  runGuards() {
    const tree = build();
    const podcast = new El("podcast-generate", "button");
    const regen = new El("guide-regenerate", "button");
    // **The two STATIC controls carry an author `data-tip` that `applyStaticI18n` has already
    // translated**, and that function runs only at boot and on a language change. Without this the
    // restore half of `syncRunGuards` is unobservable — an independent review reverted it wholesale
    // and all 953 tests stayed green, because these fakes had no `i18nTipSource` to restore from.
    podcast.dataset.tip = "Writes a script from your sources, then speaks it.";
    podcast.dataset.i18nTip = "podcast.generateTip";
    podcast.dataset.i18nTipSource = "Writes a script from your sources, then speaks it.";
    regen.dataset.tip = "Run it again on the current sources.";
    regen.dataset.i18nTip = "studio.regenTip";
    regen.dataset.i18nTipSource = "Run it again on the current sources.";
    const starter = new El("", "button");
    starter.className = "chat-starter-btn";
    // The composer and the last turn's ↻, which are guarded ONLY while a run this tab did not
    // start is in flight — the reload case, where "the pending turn is its own guard" is false.
    const ask = new El("ask-submit", "button");
    const turnRegen = new El("", "button");
    turnRegen.className = "turn-regenerate-btn";
    // Something else already disabled this one, for its own reason (an empty field, a submit in
    // flight). The guard must leave it exactly as it found it.
    const foreign = new El("add-note", "button");
    foreign.disabled = true;
    tree.orbit.append(podcast, regen, starter, ask, turnRegen, foreign);

    const narrow = [podcast, regen, starter, foreign];
    const wide = [...narrow, ask, turnRegen];
    doc._all["#podcast-generate, #guide-regenerate, .chat-starter button"] = narrow;
    doc._all[
      "#podcast-generate, #guide-regenerate, .chat-starter button, #ask-submit, .turn-regenerate button"
    ] = wide;
    const activeRuns = new Map();
    const recovered = new Set();
    const state = { orbitId: "nb-1" };
    const run = new Function(
      "document", "activeRuns", "state", "t", "recoveredRuns",
      `${constant("RUN_GUARDED")}\n${constant("RUN_GUARDED_ON_RECOVERY")}\n` +
        `${extract("syncRunGuards")}\nreturn syncRunGuards;`
    )(doc, activeRuns, state, (key, fallback) => fallback, recovered);

    const snap = () => wide.map((e) => ({ id: e.id || e.className, off: e.disabled, tip: e.dataset.tip || null }));
    run();
    const idle = snap();
    // A run THIS TAB started: the artifact controls lock, the composer does not.
    activeRuns.set("nb-1", 1);
    run();
    const busy = snap();
    // The same run after a RELOAD: `reattachInFlightRuns` marks it recovered.
    recovered.add("nb-1");
    run();
    const afterReload = snap();
    recovered.delete("nb-1");
    activeRuns.delete("nb-1");
    run();
    const released = snap();
    activeRuns.set("nb-2", 1);
    run();
    return { idle, busy, afterReload, released, otherOrbit: snap() };
  },

  //: **`reattachInFlightRuns` ITSELF**, because the guard scenario above injects the recovery flag
  //: rather than proving anything sets it — and because a stale teardown, a failed outcome and the
  //: flag's lifecycle are all decisions made inside this one function. Every collaborator is a
  //: one-line stub, which is the point: the function's own wiring is what is under test.
  //:
  //: `mode` picks what the recovered run does: "fail" makes its stream report `failed`, "finish"
  //: makes it end quietly, "stale" opens a SECOND mount for the same run and then lets the FIRST
  //: mount's teardown fire.
  async recovery(mode) {
    build();
    const history = new El("chat-history");
    doc.body.append(history);
    const byId = { "chat-history": history };
    doc.getElementById = (id) => byId[id] || null;

    const opened = [];
    class FakeEventSource {
      constructor() {
        this.closed = false;
        opened.push(this);
      }
      close() {
        this.closed = true;
      }
    }

    const recoveredRuns = new Map(); // app.js keys each flag by the mount that owns it
    const activeRuns = new Map();
    const guardCalls = [];
    const finished = [];
    let runsAnswer = ["run-1"];

    const prelude =
      `${constant("tickerSources")}\n${extract("closeTicker")}\n${extract("openTicker")}\n`;
    const make = new Function(
      "document", "recoveredRuns", "activeRuns", "EventSource", "withToken", "TERMINAL_KINDS",
      "api", "runStatus", "elt", "t", "syncRunGuards", "failureBlock", "openOrbit",
      "setInterval", "clearInterval", "orbitGeneration", "store",
      `${prelude}${extract("reattachInFlightRuns")}\n` +
        "return { reattachInFlightRuns, openTicker, closeTicker };"
    );

    const timers = [];
    const emitted = [];
    let onCancel = null;
    const status = {
      node: new El("run-status"),
      onEvent: () => {},
      finish: () => finished.push(1),
    };
    const run = make(
      doc,
      recoveredRuns,
      activeRuns,
      FakeEventSource,
      (u) => u,
      new Set(["done", "failed", "not_found"]),
      async () => ({ runs: runsAnswer }),
      (opts) => {
        // `runStatus` is where Stop is wired; the scenario needs the handler to press it.
        onCancel = opts && opts.onCancel;
        return status;
      },
      (tag, cls, text) => {
        const el = new El("", tag);
        el.className = cls || "";
        el.textContent = text || "";
        return el;
      },
      (key, fallback) => fallback,
      () => guardCalls.push(recoveredRuns.has("nb-1")),
      (head, detail) => {
        const el = new El("failure-block");
        el.textContent = `${head}|${detail}`;
        return el;
      },
      () => {},
      (fn, ms) => timers.push(fn) && timers.length,
      () => {},
      0,
      //: `stopWatching` re-decides the composer once the recovery flag is gone (a ↻ Regenerate
      //: built while the lock held would otherwise stay disabled until a reload).
      { emit: (name, payload) => emitted.push([name, payload]) }
    );

    await run.reattachInFlightRuns("nb-1", 0);
    const afterMount = {
      flagged: recoveredRuns.has("nb-1"),
      guardSawFlag: guardCalls.includes(true),
      streams: opened.length,
    };

    //: **PRESSING STOP on the recovered row.** It used to tear the row down by hand, which made the
    //: shared teardown's `if (!watching) return;` swallow the only `recoveredRuns.delete` there is
    //: — so the orbit stayed marked as recovering for the life of the tab and every later in-tab
    //: run took the composer away.
    if (mode === "stop") {
      if (!onCancel) return { afterMount, error: "runStatus was mounted without an onCancel" };
      onCancel();
      return {
        afterMount,
        flagCleared: !recoveredRuns.has("nb-1"),
        composerResynced: emitted.some(([name, payload]) => name === "chat:pending" && payload.pending === false),
        finished: finished.length,
        ownStreamClosed: opened.every((src) => src.closed),
        rendered: history.children.map((e) => `${e.className}:${e.textContent}`),
      };
    }

    if (mode === "stale") {
      // A SECOND mount for the same run, exactly what an orbit switch produces...
      await run.reattachInFlightRuns("nb-1", 0);
      const live = opened[opened.length - 1];
      // ...and now the FIRST mount's poll fires with the run gone.
      runsAnswer = [];
      await timers[0]();
      return { afterMount, liveStillOpen: !live.closed, streams: opened.length };
    }

    // **The POLL WINS and no terminal event ever arrives** — the exact race this recovery exists
    // for, a run that ended between the `/runs` answer and the stream opening. Nothing else closes
    // the stream in that case, so it is the only mode where the mount's own teardown is load-
    // bearing.
    if (mode === "silent") {
      runsAnswer = [];
      await timers[0]();
      return {
        afterMount,
        flagCleared: !recoveredRuns.has("nb-1"),
        finished: finished.length,
        ownStreamClosed: opened.every((src) => src.closed),
        rendered: history.children.map((e) => `${e.className}:${e.textContent}`),
      };
    }

    // The run ends. `failed` carries the server's own reason; `done` is a quiet finish.
    const source = opened[0];
    source.onmessage({
      data: JSON.stringify(
        mode === "fail"
          ? { kind: "failed", primary: "failed", detail: "the provider rejected the key" }
          : { kind: "done", primary: "done", detail: "" }
      ),
    });
    runsAnswer = [];
    await timers[0]();

    return {
      afterMount,
      flagCleared: !recoveredRuns.has("nb-1"),
      finished: finished.length,
      // The mount's OWN stream has to be closed when it ends, or the socket leak this whole
      // mechanism exists to stop is simply back.
      ownStreamClosed: opened.every((src) => src.closed),
      rendered: history.children.map((e) => `${e.className}:${e.textContent}`),
    };
  },

  //: **THE SEAM BETWEEN THE TWO HALVES**, which neither scenario above could see: `syncRunGuards`
  //: is driven with `activeRuns` INJECTED, and `reattachInFlightRuns` with `runStatus` STUBBED — so
  //: `noteRunStarted`, the only line in the file that ever populates `activeRuns`, was testable by
  //: nobody. Delete it and `busy` is permanently false, every guard releases, and "one press buys a
  //: second billed worker" is back invisibly. This runs the real `noteRunStarted`/`noteRunFinished`
  //: against the real `syncRunGuards`.
  runBookkeeping() {
    const tree = build();
    const podcast = new El("podcast-generate", "button");
    tree.orbit.append(podcast);
    const guarded = [podcast];
    doc._all["#podcast-generate, #guide-regenerate, .chat-starter button"] = guarded;
    doc._all[
      "#podcast-generate, #guide-regenerate, .chat-starter button, #ask-submit, .turn-regenerate button"
    ] = guarded;

    const state = { orbitId: "nb-1" };
    const emitted = [];
    const run = new Function(
      "document", "state", "t", "store", "recoveredRuns",
      `${constant("activeRuns")}\n${constant("RUN_GUARDED")}\n` +
        `${constant("RUN_GUARDED_ON_RECOVERY")}\n${extract("syncRunGuards")}\n` +
        `${extract("noteRunStarted")}\n${extract("noteRunFinished")}\n` +
        "return { noteRunStarted, noteRunFinished, busy: () => activeRuns.has('nb-1') };"
    )(doc, state, (k, f) => f, { emit: (name) => emitted.push(name) }, new Set());

    const snap = () => ({ busy: run.busy(), off: podcast.disabled });
    const idle = snap();
    run.noteRunStarted("nb-1");
    const started = snap();
    // TWO runs on one orbit: the count, not a boolean — one ending must not release the other.
    run.noteRunStarted("nb-1");
    run.noteRunFinished("nb-1");
    const stillOne = snap();
    run.noteRunFinished("nb-1");
    return { idle, started, stillOne, ended: snap(), emitted };
  },

  //: **The SEAM, which the scenario above does not reach.** `runGuards` calls `noteRunStarted`
  //: directly; production never does — the only call is the first statement of `runStatus`
  //: (`app.js:469`). An independent review deleted that line and all 979 tests stayed green, while
  //: the test named for this property said in its own docstring that the deletion was now caught.
  //: Pinning a function is not pinning the call to it. This runs the REAL `runStatus`, which is why
  //: the shim needed `document.createElement` and a `classList`.
  runStatusTakesTheGuard() {
    const tree = build();
    const podcast = new El("podcast-generate", "button");
    tree.orbit.append(podcast);
    // The same registration `runGuards` uses: `syncRunGuards` reaches these through
    // `document.querySelectorAll`, which is still a TABLE here (see the header's limits).
    doc._all["#podcast-generate, #guide-regenerate, .chat-starter button"] = [podcast];
    doc._all[
      "#podcast-generate, #guide-regenerate, .chat-starter button, #ask-submit, .turn-regenerate button"
    ] = [podcast];
    const state = { orbitId: "nb-1" };
    const stopped = [];

    const run = new Function(
      "document", "state", "t", "store", "recoveredRuns", "setInterval", "clearInterval",
      "openTrajectory", "onStop",
      `${constant("activeRuns")}\n${constant("RUN_GUARDED")}\n` +
        `${constant("RUN_GUARDED_ON_RECOVERY")}\n${extract("syncRunGuards")}\n` +
        `${extract("noteRunStarted")}\n${extract("noteRunFinished")}\n` +
        `${extract("i18nText")}\n${extract("runStatus")}\n` +
        "return { runStatus, busy: () => activeRuns.has('nb-1') };"
    )(
      doc,
      state,
      (k, f) => f,
      { emit: () => {} },
      new Set(),
      () => 0,
      () => {},
      () => {},
      (id) => stopped.push(id)
    );

    const before = { busy: run.busy(), off: podcast.disabled };
    const status = run.runStatus({
      orbitId: "nb-1",
      runIds: ["nb-1-abc"],
      label: "Reading…",
      onCancel: () => {},
    });
    const during = { busy: run.busy(), off: podcast.disabled };
    status.finish();
    return { before, during, after: { busy: run.busy(), off: podcast.disabled } };
  },

  //: B1 + H2: closing actually closes, and a second open for one run id does not orphan the first.
  tickerLifecycle() {
    const opened = [];
    class FakeEventSource {
      constructor(url) {
        this.url = url;
        this.closed = false;
        opened.push(this);
      }
      close() {
        this.closed = true;
      }
    }
    const run = new Function(
      "EventSource", "withToken", "TERMINAL_KINDS",
      `${constant("tickerSources")}\n${extract("closeTicker")}\n${extract("openTicker")}\n` +
        "return { openTicker, closeTicker, size: () => tickerSources.size };"
    )(FakeEventSource, (u) => u, new Set(["done", "failed", "not_found"]));

    run.openTicker("nb", "run-1", () => {});
    const afterFirst = { opened: opened.length, size: run.size() };
    run.openTicker("nb", "run-1", () => {}); // the same run, a second time
    const afterSecond = {
      opened: opened.length,
      size: run.size(),
      firstClosed: opened[0].closed,
      secondClosed: opened[1].closed,
    };
    // **A STALE TEARDOWN MUST NOT CLOSE A LIVE STREAM.** `closeTicker(runId, expected)` closes only
    // when the map still holds the stream the caller opened — the previous mount's poll was closing
    // the NEW mount's stream 584ms after it opened, permanently killing the live trace.
    const live = opened[1];
    run.closeTicker("run-1", opened[0]); // the stale mount's handle
    const afterStaleClose = { liveStillOpen: !live.closed, size: run.size() };

    run.closeTicker("run-1");
    const afterClose = { allClosed: opened.every((s) => s.closed), size: run.size() };
    run.closeTicker("run-1"); // idempotent
    run.closeTicker("never-opened");
    return { afterFirst, afterSecond, afterStaleClose, afterClose, survivedExtraCloses: true };
  },

  //: The knowledge graph's layout, run on a small orbit twice: it must be deterministic (the same
  //: orbit draws the same picture), keep every entity on the stage, frame what it drew no tighter
  //: than the minimum, and put a capture beside the entities it names.
  graphLayout() {
    const run = new Function(
      `${extract("stableHash")}\n${extract("layoutGraph")}\nreturn { layoutGraph };`
    )();
    const data = {
      entities: [
        { name: "REM", count: 3 }, { name: "memory", count: 2 }, { name: "Walker", count: 1 },
        { name: "caffeine", count: 1 },
      ],
      edges: [{ a: "REM", b: "memory", weight: 2 }, { a: "REM", b: "Walker", weight: 1 }],
      captures: [
        { node_id: "nd-1", title: "a", origin: "x", state: "ready", entities: ["REM", "memory"], tags: [] },
        { node_id: "nd-2", title: "b", origin: "y", state: "ready", entities: [], tags: [] },
      ],
      tags: [], undistilled: [],
    };
    const one = run.layoutGraph(data);
    const two = run.layoutGraph(data);
    const pts = [...one.pos.values()];
    const rem = one.pos.get("REM");
    const memory = one.pos.get("memory");
    const c = one.captures[0];
    const mid = { x: (rem.x + memory.x) / 2, y: (rem.y + memory.y) / 2 };
    return {
      same: JSON.stringify([...one.pos.entries()]) === JSON.stringify([...two.pos.entries()]),
      inside: pts.every((p) => p.x >= 60 && p.x <= 940 && p.y >= 50 && p.y <= 640),
      box: one.box,
      captureNearAnchors: Math.hypot(c.x - mid.x, c.y - mid.y) <= 60,
      linkedCloser: Math.hypot(rem.x - memory.x, rem.y - memory.y)
        < Math.hypot(one.pos.get("caffeine").x - rem.x, one.pos.get("caffeine").y - rem.y),
    };
  },

  //: A tag lens, from the server's topology to the planet: a tag outside an orbit's top few still
  //: lights it. The server sent `all_tags` and the page dropped it while building the planet.
  starMapLens() {
    const t = (_k, fallback) => fallback;
    const run = new Function(
      "t", `${extract("starMapOrbit")}\n${extract("dimmedByLens")}\n${extract("moonLensClass")}\n` +
        "return { starMapOrbit, dimmedByLens, moonLensClass };"
    )(t);
    const top = ["a", "b", "c", "d", "e", "f"];
    const planet = run.starMapOrbit(
      { id: "cfp", slug: "cfp", title: "cfp", source_count: 2, updated_at: 1 },
      { captures: 2, undistilled: 0, last_filed_at: 2, entities: [], tags: top,
        all_tags: [...top, "supply chain security"], moons: [] },
    );
    const bare = run.starMapOrbit({ id: "new", slug: "new", title: "", source_count: 0 }, undefined);
    const lenses = (...names) => new Set(names);
    return {
      heldTagLit: !run.dimmedByLens(planet, lenses("supply chain security")),
      otherTagDim: run.dimmedByLens(planet, lenses("cooking")),
      noLensLit: !run.dimmedByLens(planet, lenses()),
      emptyOrbitDim: run.dimmedByLens(bare, lenses("a")),
      unionLit: !run.dimmedByLens(planet, lenses("cooking", "supply chain security")),
      moonLit: run.moonLensClass({ kind: "capture", tags: ["ai threats"] }, lenses("ai threats", "x")),
      moonFaded: run.moonLensClass({ kind: "capture", tags: ["rust"] }, lenses("ai threats")),
      localFaded: run.moonLensClass({ kind: "local" }, lenses("ai threats")),
      moonPlain: run.moonLensClass({ kind: "capture", tags: ["rust"] }, lenses()),
      displayStillCapped: planet.tags.length === 6,
    };
  },

  //: The view-mode preference: a stored value outside the allowed pair falls back to the default,
  //: and blocked storage is not an error.
  viewModes() {
    const store = {};
    const localStorage = {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
    };
    const t = (_k, fallback) => fallback;
    const run = new Function(
      "localStorage", "t",
      `${constant("MODE_KEYS")}\n${constant("MODE_DEFAULTS")}\n${constant("MODE_CHOICES")}\n` +
        `${extract("viewMode")}\nreturn { viewMode };`
    )(localStorage, t);
    const fresh = [run.viewMode("horizon"), run.viewMode("orbit")];
    store["penumbra-orbit-mode"] = "cols";
    store["penumbra-horizon-mode"] = "nonsense";
    const stored = [run.viewMode("horizon"), run.viewMode("orbit")];
    const blocked = new Function(
      "localStorage", "t",
      `${constant("MODE_KEYS")}\n${constant("MODE_DEFAULTS")}\n${constant("MODE_CHOICES")}\n` +
        `${extract("viewMode")}\nreturn viewMode("orbit");`
    )({ getItem: () => { throw new Error("blocked"); } }, t);
    return { fresh, stored, blocked };
  },

  //: What a scope chip says. On a graph the orbit is the one on screen, so an entity chip does not
  //: repeat it; in the history, where there is no screen to lean on, the orbit is named.
  scopeLabels() {
    const t = (_k, fallback) => fallback;
    const run = new Function(
      "t",
      "const orbitTitles = new Map([['sleep', 'Sleep']]);\n" +
        `${extract("orbitLabelForSlug")}\n${extract("askHScopeLabel")}\n${extract("askHChipLabel")}\n` +
        "return { askHScopeLabel, askHChipLabel };"
    )(t);
    return {
      all: run.askHScopeLabel({ kind: "all" }),
      tagHistory: run.askHScopeLabel({ kind: "tag", value: "sleep", orbit: "sleep" }),
      entityChip: run.askHChipLabel({ id: "e", scope: { kind: "entity", value: "REM", orbit: "sleep" } }),
      tagChip: run.askHChipLabel({ id: "t", scope: { kind: "tag", value: "sleep", orbit: "sleep" } }),
      orbitChip: run.askHChipLabel({ id: "o", orbit: { id: "nb-1", slug: "sleep", title: "Sleep" } }),
    };
  },

  //: A running summary pass keeps its Stop through a redraw. The map and the graph rebuild their
  //: summarise control on every redraw; before its state moved out of the DOM, a redraw mid-pass
  //: put the spend button back with no Stop while the pass kept billing.
  distilControlSurvivesRedraw() {
    class Node {
      constructor(tag) { this.tag = tag; this.kids = []; this.className = ""; this.type = ""; this.disabled = false; this._text = ""; }
      set textContent(v) { this._text = v; this.kids = []; }
      get textContent() { return this._text + this.kids.map((k) => k.textContent).join(""); }
      appendChild(k) { this.kids.push(k); return k; }
      addEventListener() {}
    }
    const elt = (tag, cls, text) => { const n = new Node(tag); n.className = cls || ""; if (text) n._text = text; return n; };
    const t = (_k, fallback) => fallback;
    const run = new Function(
      "elt", "t", "api", "notify", "readableError", "document",
      "const DISTIL_BATCH_CAP = 50;\n" +
        "const distilWatch = { status: null, polling: false, failures: 0, stopping: false };\n" +
        "function paintDistilControls() {} function watchDistil() {} function refreshTopologyViews() {}\n" +
        "async function distilEstimate() { return null; }\n" +
        `${extract("distilOrbitControl")}\nreturn { distilOrbitControl, distilWatch };`
    )(elt, t, async () => ({}), () => {}, (m) => m, { querySelectorAll: () => [] });
    const idle = run.distilOrbitControl("sleep", 3);
    const idleHasStop = idle.kids.some((k) => (k.className || "").includes("run-stop"));
    run.distilWatch.status = { running: true, done: 1, total: 3 };
    run.distilWatch.slug = "sleep"; // this orbit started it
    const redrawn = run.distilOrbitControl("sleep", 3); // what a redraw builds mid-pass
    return {
      idleHasStop,
      idleOffersSpend: idle.textContent.includes("Summarise 3"),
      redrawnHasStop: redrawn.kids.some((k) => (k.className || "").includes("run-stop")),
      redrawnShowsProgress: redrawn.textContent.includes("Summarising 1 of 3"),
      redrawnOffersSpend: redrawn.textContent.includes("Summarise 3"),
    };
  },

  //: An orbit entered with a run in flight opens where that run's status and Stop are.
  orbitVisitWithRun() {
    const run = new Function(
      "state", "activeRuns", "recoveredRuns",
      "const orbitVisit = { override: null, userChose: false };\n" +
        `${extract("orbitHasRun")}\n${extract("beginOrbitVisit")}\n` +
        "return { begin: () => { beginOrbitVisit(); return orbitVisit.override; } };"
    );
    const busy = run({ orbitId: "nb-1", sources: [1] }, new Map([["nb-1", 1]]), new Map()).begin();
    const recovered = run({ orbitId: "nb-1", sources: [1] }, new Map(), new Map([["nb-1", {}]])).begin();
    const quiet = run({ orbitId: "nb-1", sources: [1] }, new Map([["nb-2", 1]]), new Map()).begin();
    const empty = run({ orbitId: "nb-1", sources: [] }, new Map(), new Map()).begin();
    return { busy, recovered, quiet, empty };
  },

  //: A refresh keeps the reader's chosen scope and the plan on screen; a new selection by the
  //: reader moves to its most specific scope. Before, every map refresh (window focus, a capture)
  //: snapped the dock back and hid the plan, turning the free check into a paid ask.
  askContextOnRefresh() {
    const dismissed = [];
    const run = new Function(
      "dismissAskHPlan", "renderAskHChips",
      "const askH = { chips: [{ id: 'all', scope: { kind: 'all' } }], chosen: 'all', custom: null };\n" +
        `${extract("askHChosen")}\n${extract("setAskContext")}\nreturn { setAskContext, askH };`
    )(() => dismissed.push(1), () => {});
    const orbitChip = { id: "orbit:sleep", orbit: { id: "nb-1", slug: "sleep", title: "Sleep" } };
    run.setAskContext([orbitChip]); // the reader picked a planet
    const afterPick = run.askH.chosen;
    run.askH.chosen = "all"; // the reader pressed the Everything chip, then checked a plan
    const before = dismissed.length;
    run.setAskContext([orbitChip], { follow: false }); // a background refresh
    const afterRefresh = { chosen: run.askH.chosen, dismissed: dismissed.length - before };
    const tagChip = { id: "tag:x", scope: { kind: "tag", value: "x" } };
    run.setAskContext([orbitChip, tagChip]); // the reader turned on a lens
    return { afterPick, afterRefresh, afterLens: run.askH.chosen };
  },

  //: The summarise control claims progress only for a pass its own orbit started.
  distilControlClaimsOnlyItsOwnPass() {
    class Node {
      constructor(tag) { this.tag = tag; this.kids = []; this.className = ""; this.type = ""; this.disabled = false; this._text = ""; }
      set textContent(v) { this._text = v; this.kids = []; }
      get textContent() { return this._text + this.kids.map((k) => k.textContent).join(""); }
      appendChild(k) { this.kids.push(k); return k; }
      addEventListener() {}
    }
    const elt = (tag, cls, text) => { const n = new Node(tag); n.className = cls || ""; if (text) n._text = text; return n; };
    const t = (_k, fallback) => fallback;
    const run = new Function(
      "elt", "t", "api", "notify", "readableError",
      "const DISTIL_BATCH_CAP = 50;\n" +
        "const distilWatch = { status: { running: true, done: 2, total: 5 }, polling: true, failures: 0, stopping: false, slug: 'coffee' };\n" +
        "function paintDistilControls() {} function watchDistil() {} function refreshTopologyViews() {}\n" +
        "async function distilEstimate() { return null; }\n" +
        `${extract("distilOrbitControl")}\nreturn { distilOrbitControl };`
    )(elt, t, async () => ({}), () => {}, (m) => m);
    return {
      mine: run.distilOrbitControl("coffee", 5).textContent,
      other: run.distilOrbitControl("sleep", 3).textContent,
    };
  },
};

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { scenario, mode } = JSON.parse(input);
const runner = SCENARIOS[scenario];
if (!runner) throw new Error(`no scenario ${scenario}`);
process.stdout.write(JSON.stringify({ result: await runner(mode) }));
