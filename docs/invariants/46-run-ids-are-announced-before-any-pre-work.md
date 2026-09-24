# Invariant 46: Run ids are announced before any preparatory work

**Every run-taking handler announces its run id (`api._announced`) before any preparatory work, not just before the spawn.**

This window is larger than the one invariant 29 closed and comes before it. Every one of these handlers calls `_resolve_language` first (invariant 39), which is a real model call in its own subprocess. On a new orbit the output language is unresolved, so that call always happens and always outlasts `_TRACE_FILE_WAIT_GRACE` (5s). Without the announcement, the client opens its ticker, waits five seconds for a trace file that cannot exist yet, and reports the run missing while the request succeeds.

`_announced` reuses `_RUN_PROCESSES` rather than adding a registry, because `stream_run` already reads it as "is anything still going to write this file". It uses `setdefault`, so an id `_run_isolated` has already claimed is never downgraded, and on release it removes only ids still at the `None` placeholder, because a spawned run belongs to `_run_isolated`'s own `finally`. A handler that fails before spawning does release, so a failed request never leaves a stream waiting forever. `_tail_trace_events` resets its grace counter while the id is announced.

It applies to all five run-taking handlers, including `/title`, which no client streams today. `/title` accepts `run_id` like the others, and a rule with one silent exception tends to come back as a bug report.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
