"""The summary pass: a capture's title, summary, tags and entities, written by the kit's labelling
pass (`rlm_harness.memory_tasks.distill_pending`) into the kit's memory store.

The rule and its cost argument live in
`docs/invariants/80-capture-never-pays-for-a-summary.md`. The short version: **capture makes no model
call**, this is a SEPARATE pass the reader starts on purpose (or turns on), a failed summary leaves the
capture at `ready_undistilled` rather than costing the capture, and after `horizon.DISTILL_MAX_FAILURES`
failures a capture leaves the automatic queue until a press names it.

What this module adds to the kit's pass, and why each is the host's:

- **Which captures.** `horizon.waiting_ids` is the queue, passed as the pass's `item_ids`: the kit's
  own selection would also pick items with no live capture (a row still under its temporary id, one a
  crash left, one being purged).
- **The capture's state.** `distilling` while its call runs, then `ready` or back to
  `ready_undistilled` (the list and the map draw it), with a failure's reason on the row.
- **What counts as the capture's failure.** A Stop, an unreachable model or a misconfigured server is
  not: the run wrapper raises `StepNotCounted`, which the kit reports without counting toward the cap.
- **A capture with no text** is labelled empty without a call: its kit item holds its origin instead,
  which must not be summarised.
- **Where each step runs.** A short capture is the kit's one `SummariseShort` call, in this process; a
  long one is the kit's `DistillLongItem`, an RLM run, which the caller runs in a worker subprocess
  (`run_long`, invariant 21).

**Never call this from inside a running event loop.** It uses `asyncio.run`; the API calls it from a
thread of its own.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from pathlib import Path

from rlm_harness.memory import SHORT_LIMIT, fold_name

from . import horizon, memory_store
from .config import clean_language, output_language

_log = logging.getLogger(__name__)

__all__ = ["MAX_TAGS", "MAX_TAG_CHARS", "SHORT_LIMIT", "clean_tags", "distil_pending", "summarise_short"]

#: The most tags a capture carries, and the longest a tag may be: the kit's own bounds.
MAX_TAGS = 8
MAX_TAG_CHARS = 40

#: The fields each step reads; nothing else in a payload reaches a step (not `step`, `item_id` or
#: `run_id`).
_STEP_FIELDS = {
    "summarise_short": ("text", "language", "known"),
    "distill_long": ("text", "section_map", "language", "known"),
}


def clean_tags(value: object, count: int = MAX_TAGS) -> list[str]:
    """Tags as the store keeps them (`fold_name`: NFKC, casefolded, spaces collapsed), each at most
    `MAX_TAG_CHARS`, empty and repeated ones dropped, at most `count`. A reader's typed tags go through
    this before `horizon.edit_node`, so `Rust` joins `rust` and a growth past `MAX_TAGS` can be refused
    rather than cut by the store."""
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        tag = fold_name(str(item))[:MAX_TAG_CHARS].strip()
        if tag and tag not in out:
            out.append(tag)
    return out[:count]


def summarise_short(fields: dict):
    """One short capture's labels: the kit's `SummariseShort`, one `dspy.Predict` call in this
    process. The default `run_short`, looked up when each capture is summarised."""
    from rlm_harness.memory_tasks import arun_step

    return arun_step({"step": "summarise_short", **fields})


def distil_pending(
    *,
    limit: int = 20,
    language: str | None = None,
    base_dir: str | Path = horizon.DEFAULT_HORIZON_DIR,
    should_stop: Callable[[], bool] | None = None,
    on_node: Callable[[], None] | None = None,
    on_error: Callable[[str, str], None] | None = None,
    not_counted: Callable[[str], bool] | None = None,
    node_ids: list[str] | None = None,
    orbit_id: str | None = None,
    run_short: Callable[[dict], object] | None = None,
    run_long: Callable[[dict], dict] | None = None,
    defer_long: bool = False,
) -> list[str]:
    """Summarise up to `limit` waiting captures (`horizon.waiting_ids`), newest first, and return the
    ids summarised. `node_ids` names captures (a press on them; the failure cap does not apply) and
    `orbit_id` narrows to one orbit. Without `run_long`, long captures are left waiting, as
    `defer_long` asks.

    `on_node` is called once per capture attempted, after its call; `on_error(node_id, reason)` for a
    capture that failed, with the reason as reported; `not_counted(reason)` says a failure is not the
    capture's (an unreachable model), and so is a failure while `should_stop()` holds.
    `run_short(fields)` and `run_long(fields)` run one step given its own fields and return its
    labels; `run_short` defaults to `summarise_short`, and `run_long` is called on a thread.

    **The language ladder.** `output_language()` is the operator's stated preference and wins whenever
    it is set (invariant 39's top rung); below it, the caller's (the request's interface language, or
    the one the reader last used). With nothing, the kit tells the model to write in the text's own.
    """
    from rlm_harness.memory_tasks import StepNotCounted
    from rlm_harness.memory_tasks import distill_pending as kit_distill_pending

    chosen = output_language() or clean_language(language) or ""
    deferring = defer_long or run_long is None
    ids = horizon.waiting_ids(base_dir=base_dir, node_ids=node_ids, orbit_id=orbit_id,
                              defer_long=deferring, limit=max(1, min(int(limit), 500)))
    if not ids:
        return []
    store = memory_store.store(base_dir)
    distilled: list[str] = []
    #: Captures this pass did not try (removed, or no longer waiting): neither progress nor failure.
    passed_over: set[str] = set()

    def stopping() -> bool:
        return bool(should_stop is not None and should_stop())

    async def run(payload: dict) -> dict:
        item_id = payload["item_id"]
        # Claimed, not labelled: a compare-and-set, so a second pass running at the same time
        # (the API runs one, but this function does not rely on it) never pays for it twice.
        if not horizon.claim_node(item_id, expect="ready_undistilled", to="distilling", base_dir=base_dir):
            passed_over.add(item_id)
            raise StepNotCounted(f"CaptureGone: {item_id} is no longer waiting")
        item = store.get(item_id)
        if item is not None and item.meta.get("empty_text"):
            # Its item's text is its origin, kept so the item is findable; nothing to summarise.
            return {"title": "", "summary": "", "tags": [], "entities": []}
        step = payload["step"]
        fields = {name: payload.get(name, "") for name in _STEP_FIELDS[step]}
        try:
            if step == "distill_long":
                if run_long is None:
                    raise RuntimeError("no long-document runner")
                return await asyncio.to_thread(run_long, fields)
            result = (run_short or summarise_short)(fields)
            return await result if inspect.isawaitable(result) else result
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            if stopping() or (not_counted is not None and not_counted(reason)):
                raise StepNotCounted(reason) from exc
            raise

    def progress(event: dict) -> None:
        item_id = event["item_id"]
        if item_id in passed_over or horizon.get_node(item_id, base_dir=base_dir) is None:
            return   # removed meanwhile, or no longer waiting: nothing to report about it
        if event["ok"]:
            horizon.update_node(item_id, base_dir=base_dir, state="ready", error=None)
            distilled.append(item_id)
        else:
            horizon.update_node(item_id, base_dir=base_dir, state="ready_undistilled")
            if on_error is not None:
                on_error(item_id, event["error"])
        if on_node is not None:
            on_node()

    asyncio.run(kit_distill_pending(
        store, limit=len(ids), language=chosen, item_ids=ids, defer_long=False, run=run,
        should_stop=stopping, on_progress=progress, max_failures=horizon.DISTILL_MAX_FAILURES,
    ))
    return distilled
