# Invariant 47: Every long run is visible and stoppable

**Every long-running action shows that it is running and offers a way to stop it, and no action starts without an explicit press.**

Chat, the overview, each guide and the podcast all mount the same `runStatus` component: a pulsing dot, the current step, elapsed time and Stop.

## Stop reaches the run the reader meant

Stop cancels by run id (`POST /notebooks/{id}/runs/{run_id}/cancel`), because `/overview` starts two runs while `_ACTIVE_RUNS` holds one slot per notebook (invariant 23); the notebook-scoped `/cancel` would reach only the one that registered last. `_RUN_PROCESSES` is keyed by run id and holds the process, so a precise cancel is a lookup. It kills the whole process group (invariant 22).

Stop also reaches a run that has not spawned yet. Every run is announced before its preparatory work (invariant 46), and `_resolve_language` is a real model call. A cancel in that window used to signal nothing, and the main run then spawned with nothing to stop it. `_CANCELLED_BEFORE_SPAWN` records the stop, `_run_isolated` refuses to spawn that id, and the cancel reaches `{base}-lang` too.

A reload is not an exemption. The worker survives the page, so `GET /notebooks/{id}/runs` lists what is in flight and the UI mounts a status with a working Stop for it.

Tier 0's two long actions are stopped globally, with no run id, because there is nothing to disambiguate: intake is one serial queue (invariant 79) and the summary pass runs one batch at a time. `/inbox/cancel` stops both on purpose, because a reader pressing Stop while both run is not asking for one of them. The automatic summary pass shares the same progress state as the manual one; before it did, the one batch that runs without a press had no progress, no Stop and no failure channel.

## A run's state belongs to that run

A page that repaints, fails or switches context must never lose, duplicate or misplace a run's state. This was the source of most late defects, so the rules are stated together:

- Each run owns its status row and its Stop. A repaint of the thread, the overview (invariant 71) or the Studio re-attaches the row instead of replacing it; the pending question and a recovered run carry theirs through every rebuild.
- A result or failure lands only in its own notebook and its own tab. Completion handlers check that the notebook has not changed before touching shared state.
- Stop cancels the new run and never removes the previous result. A stopped or failed regeneration of an answer, the overview, a guide or the podcast keeps what was there, with any failure shown above it.
- A lock is released only by the run that holds it. The composer is held while either the overview or a question runs, a recovery flag belongs to the mount that set it, and a start button is re-decided through the run guard instead of being switched back on.
- Every control becomes usable again once the reason for disabling it has ended.

An independent sweep of 60 combinations of run kind, context change and outcome found no control left stuck or unlocked too early.

## Other rules

Selecting a Studio tab never starts a run. It used to call the model on click, so browsing the four kinds cost four runs with no way to tell which click had committed them. Each tab shows what it is and offers a button.

A superseded generation says so. A silent `return` in a staleness guard looks exactly like a hang.

Panels say what they are for. "Podcast", not "Audio Overview", because users did not know what that meant, and Studio, Podcast and Notes each carry one visible sentence, with details in `data-tip` hovers. This project's own tooltip is used instead of the native `title=`, whose delay made the help feel disconnected from the hover.

One stage cannot be stopped, and it says so. A podcast's TTS synthesis runs on the host after the script subprocess has returned, so there is nothing for `killpg` to reach (invariant 29). The UI passes `stoppable: false` for that stage, and `.btn:disabled` makes a disabled Stop look disabled, because a control that looks usable and swallows the click is worse (invariant 60). With Chatterbox that stage can last fifteen minutes (invariant 43), so the status line names it.

`tests/test_web_assets.py` pins the structure, and the node harness in `tests/web_dom_harness.mjs` runs the real handlers for the behaviour.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
