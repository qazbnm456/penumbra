# Invariant 23: One active-run slot per notebook

**`api._ACTIVE_RUNS` is a single-process, in-memory map with one slot per notebook id.**

Both halves are documented limitations, not silent bugs:

- There is no multi-worker `uvicorn` story. Each worker process has its own map, so `POST .../cancel` reaches only the worker that holds the request.
- Two concurrent requests on the same notebook share one slot, so `/cancel` reaches only the most recent one; the first still finishes on its own. The overwrite never corrupts state, because each request's `finally` clears only its own entry (an `is run` identity check).

A per-run-id registry removes the second limitation, and `POST /runs/{run_id}/cancel` (invariant 47) already provides it where it matters. Whether a notebook is busy for deletion is a separate question, answered by the counted `_BUSY` map, which covers every run and the host-side work after it.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
