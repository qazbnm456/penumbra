# Invariant 47 — Every long run is visible and stoppable

**Every long-running action shows that it is running and offers a way to STOP it, and no action
starts without an explicit press.** All four surfaces — chat, the chat overview, each Guide kind,
the podcast — mount the same `runStatus` component (pulsing dot, live action, ticking elapsed,
Stop).

**Stop cancels by RUN ID** (`POST /notebooks/{id}/runs/{run_id}/cancel`), because `/overview`
fires TWO runs and invariant 23's `_ACTIVE_RUNS` holds one slot per NOTEBOOK — the notebook-scoped
`/cancel` reaches only whichever registered last, so the user asks to stop and the other run keeps
burning a model call to completion. `_RUN_PROCESSES` is already run-id-keyed and already holds the
process, so cancelling precisely is a lookup, not a new registry. It `killpg`s the whole group
(invariant 22) and reports an announced-but-unspawned id honestly rather than as a 404 reading
"already finished".

**Tier 0's two long actions are stopped GLOBALLY, and that is not the run-id rule being relaxed.**
`POST /inbox/cancel` takes no run id because there is nothing to disambiguate: intake is one serial
queue (invariant 79 — exactly one item is ever in flight) and the summary pass is one at a time.
**That second half was briefly false and is worth recording**: the AUTOMATIC pass reported through
none of `_DISTIL`, so the 409 guard could not see it, a second pass could start on top of it, and
— far worse — the one batch that runs without a press was the one with no progress, no Stop and no
failure channel. Thirteen model calls were measured behind `{running: false, done: 0, total: 0}`.
Both passes share the state now, which is what makes "one at a time" and "stoppable" true of each.

**And a Stop must reach a run that has not SPAWNED yet.** Every run is announced before its
pre-work (invariant 46), and `_resolve_language` is a real model round trip that always happens on
a notebook whose language is unresolved. Cancelling in that window used to report "not spawned yet"
and signal nothing: the pre-work kept going under a derived id the caller never saw, and the main
run spawned afterwards, unindicated and unstoppable. `_CANCELLED_BEFORE_SPAWN` records the stop,
`_run_isolated` refuses to spawn an id in it, and the cancel reaches `{base}-lang` too.

**A reload is not an exemption either.** The worker survives the page, so the page has to be able to
find it again: `GET /notebooks/{id}/runs` lists what is in flight and the UI re-mounts a status with
a working Stop on it. The run-id rule above exists because `/overview` fires TWO
runs against ONE notebook-scoped slot; neither Tier 0 action can be in that situation by
construction. What the rule really says is "Stop must reach the thing the reader meant", and here
the thing they meant is the only one there is. `/inbox/cancel` stops BOTH, deliberately: a reader
pressing Stop while parsing and summarising are both running is not asking for one of them.

**Selecting a Studio tab does not start a run.** It used to fire a real RLM call on click, so
browsing the four kinds to see what they were cost four model runs with no way to tell which click
had committed them. Each tab shows what it is and offers a button.

**A superseded generation SAYS SO.** A silent `return` in a staleness guard is indistinguishable
from a hang, and it is the exact path that produces "pressed generate, it said Finished, then
nothing ever appeared".

**Panels say what they are for.** "Podcast", not "Audio Overview" (users did not know what it
was), and Studio/Podcast/Notes each carry ONE visible sentence, with per-control detail in
`data-tip` hovers — this project's own tooltip, not the native `title=`, whose ~1s delay made the
help feel disconnected from the hover effect accompanying it. Notes says what a note is *for*,
since neither the section nor the button explained that promotion is what makes it citable.

`tests/test_web_assets.py` pins all of it as source-tree assertions, since there is no JS test
runner.


**ONE action is genuinely un-stoppable, and it SAYS so rather than pretending.** A podcast's TTS
synthesis runs in-process after the script subprocess has returned, so `_run_isolated`'s `finally`
has already cleared the entry `killpg` would have reached (invariant 29). `app.js` passes
`stoppable: false` for that half, and `.btn:disabled` is styled precisely so a disabled Stop LOOKS
disabled — invariant 60's rule, because a control that looks operable and swallows the click is
worse than one that is visibly not available. With chatterbox that window is up to fifteen minutes
(invariant 43), which is why the phase is named in the status line instead.

---

One-line index: [`AGENTS.md`](../../AGENTS.md) · Incidents, measurements and superseded drafts: [`CHANGELOG.md`](../../CHANGELOG.md)
