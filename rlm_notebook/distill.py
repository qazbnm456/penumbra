"""Distillation: the cheap summary that makes a captured node findable again.

The rule and its cost argument live in
`docs/invariants/80-capture-never-pays-for-a-summary.md`; the incidents live in `CHANGELOG.md`.
The short version: **capture makes no model call**, this is a SEPARATE pass the reader starts on
purpose, and a failed summary leaves the node at `ready_undistilled` rather than costing the
capture.

What a reader of THIS file needs, and the invariant does not carry:

- **Sanitisation happens in `distil_source`, not only in `DistillNode.arun`.** Both apply it, and
  that redundancy is deliberate: an earlier version cleaned only inside `arun`, so every caller that
  injected its own `run=` — which is every test, and any future caller that swaps the model —
  wrote raw values straight through to `inbox.update_node`. Deleting the cleaning from `arun` left
  the whole suite green. `_sanitize` is idempotent, so applying it twice costs nothing.
- **The "nothing to summarise" check reads the SOURCE, not the excerpt.** `Corpus.excerpt`
  unconditionally prepends `[[SRC:...]]`, so an empty document still produces a truthy string — the
  guard in `arun` was dead on the only path that reaches it, and a page trafilatura extracted
  nothing from cost a call.
- **`distil_pending` CLAIMS each node** (`inbox.claim_node`) rather than labelling it. Two
  concurrent passes each wrote `state="distilling"` unconditionally: five model calls for three
  nodes, each pass overwriting the other's summary.
- **Never call this from inside a running event loop.** It uses `asyncio.run`, and the intended
  caller is a FastAPI handler — so it raises loudly rather than letting the bare `except` turn
  `RuntimeError: asyncio.run() cannot be called from a running event loop` into a silent "the model
  was unreachable". Use `asyncio.to_thread(distil_pending, ...)`, which is what `api.py` already
  does for every other blocking call.
- **`import dspy` lives inside `arun`**, because a top-level import would make every `cli.py`
  command pay for it. Pinned by a subprocess blocker in `tests/test_distill.py`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from . import inbox
from .citations import strip_markers
from .config import clean_language, output_language
from .corpus import Corpus
from .schema import Distillation

_log = logging.getLogger(__name__)

#: How much of the node the model is shown. Same budget as `naming.SuggestTitle`, and for the same
#: reason: a summary needs the subject, not the document.
_EXCERPT_CHARS = 4000

#: Caps on what comes back, applied host-side. A model asked for "two or three sentences" that
#: returns two pages is not an error worth failing a capture over — it is a value to trim.
_MAX_TITLE_CHARS = 80
_MAX_SUMMARY_CHARS = 600
_MAX_TAGS = 8
_MAX_ENTITIES = 8

_INSTRUCTIONS = """\
Summarise one captured document so its owner can find it again months later, when they have
forgotten the words it used.

Write:
- title: a short, specific label. Name the actual subject, not the document type. Never "Article"
  or "PDF document".
- summary: two or three sentences on what this says and why someone kept it. No preamble, no "This
  document...".
- tags: up to 6 lowercase topic labels, reusable across other documents. Prefer general terms a
  person would search by over phrases unique to this text.
- entities: up to 6 proper nouns this is ABOUT — people, organisations, products, places. Not
  every name that appears.

Rules:
- Write title and summary in the requested language. If none is given, use the document's own.
  Never translate a proper noun that has no established translation.
- The text contains `[[SRC:...]]` coordinate markers. They are not content. Never copy one into
  anything you write.
- Say only what the text supports. If it is too short or too garbled to summarise, give an empty
  summary rather than inventing one.
"""


def _clean(value: object, limit: int) -> str:
    return strip_markers(str(value or "")).strip()[:limit].strip()


def _clean_list(value: object, limit: int, count: int, *, lower: bool = False) -> list[str]:
    """Deduplicated and order-preserving. A model handed a `list[str]` signature can still return a
    comma-joined string, so both shapes are accepted.

    **`lower` is applied BEFORE the dedup, not by the caller afterwards.** Lowercasing the result
    turned `["ML", "ml", "Ml"]` into `["ml", "ml", "ml"]` — and `schema.Distillation` calls tags
    "the join key a later slice needs for implicit edges", where duplicates are not cosmetic.
    """
    if isinstance(value, str):
        items = [part for part in value.split(",")]
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = [str(part) for part in value]
    else:
        if value not in (None, ""):
            # Not silently empty: "the model returned a dict" and "the model returned no tags" are
            # different problems and a reader of the logs should be able to tell them apart.
            _log.warning("distill: ignoring %s of unexpected type %s", "tags/entities", type(value))
        return []
    seen: list[str] = []
    for item in items:
        cleaned = _clean(item, limit)
        if lower:
            cleaned = cleaned.lower()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen[:count]


def _sanitize(result: Distillation) -> Distillation:
    """Cap every field and strip `[[SRC:...]]` from all of them (invariant 62).

    Applied by BOTH `DistillNode.arun` and `distil_source`, deliberately — see the module docstring.
    Idempotent, so the double application costs nothing and neither path can be the one that forgot.
    """
    return Distillation(
        title=_clean(result.title, _MAX_TITLE_CHARS),
        summary=_clean(result.summary, _MAX_SUMMARY_CHARS),
        tags=_clean_list(result.tags, 40, _MAX_TAGS, lower=True),
        entities=_clean_list(result.entities, 60, _MAX_ENTITIES),
    )


class DistillNode:
    """`worker.py`-compatible in shape (`arun(**kwargs)`), so this can be moved behind a subprocess
    later without changing its callers — the same contract `naming.SuggestTitle` satisfies.

    `arun(sources=<corpus excerpt>, language=<resolved language>) -> Distillation`.
    """

    async def arun(self, *, sources: str = "", language: str = "") -> Distillation:
        excerpt = (sources or "")[:_EXCERPT_CHARS]
        if not excerpt.strip():
            return Distillation()
        import dspy

        predictor = dspy.Predict(
            dspy.Signature(
                "sources: str, language: str -> title: str, summary: str, tags: list[str], "
                "entities: list[str]",
                _INSTRUCTIONS,
            )
        )
        result = await predictor.acall(sources=excerpt, language=language or "")
        return _sanitize(
            Distillation(
                title=str(getattr(result, "title", "") or ""),
                summary=str(getattr(result, "summary", "") or ""),
                tags=_clean_list(getattr(result, "tags", []), 40, _MAX_TAGS, lower=True),
                entities=_clean_list(getattr(result, "entities", []), 60, _MAX_ENTITIES),
            )
        )


def distil_source(
    source,
    language: str = "",
    *,
    run: Callable[..., Distillation] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> Distillation | None:
    """Distil one already-parsed `Source`. Returns `None` if the model call failed.

    `Corpus.excerpt` rather than the raw text (invariant 61), and `None` rather than a raised
    exception, because the caller's job is to record `ready_undistilled` and move on — the capture
    already succeeded and must not be lost to a summariser being unreachable.

    **`on_error` is how the reason gets OUT, and it exists because swallowing it was a real defect.**
    Returning `None` is right for CONTROL FLOW and wrong as the whole story: an independent review
    ran the pass with no model credentials and watched the progress strip count to 2 / 2 and
    disappear, because the only record of `ValueError: No LM is loaded` was a log line on the
    server. This is the one action in the product that spends the reader's money, and it was the
    only one with no failure channel at all. The callback does not change what this function
    RETURNS, so nothing downstream had to learn a new shape.
    """
    # The emptiness check reads the SOURCE, not the excerpt. `Corpus.excerpt` unconditionally
    # prepends `[[SRC:...]]`, so a document with nothing in it still produces a truthy string — the
    # guard inside `arun` was dead on this path, and a page trafilatura extracted nothing from was
    # costing a model call.
    if not "".join(block.text for block in source.blocks).strip():
        return Distillation()

    # OUTSIDE the try, and loudly. `asyncio.run` refuses to run inside an existing loop, and the
    # intended caller is a FastAPI handler — swallowing that below would turn a wiring mistake into
    # "every node bounced back to ready_undistilled", indistinguishable from an unreachable model.
    if run is None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "distil_source cannot run inside an event loop — call it through "
                "asyncio.to_thread(...), the way api.py handles every other blocking call"
            )

    excerpt = Corpus(sources=[source]).excerpt(_EXCERPT_CHARS)
    try:
        result = (
            run(sources=excerpt, language=language)
            if run is not None
            else asyncio.run(DistillNode().arun(sources=excerpt, language=language))
        )
    except Exception as exc:  # noqa: BLE001 - a missing summary must never cost a capture
        _log.exception("distill: could not summarise %s", getattr(source, "origin", "?"))
        if on_error is not None:
            on_error(exc)
        return None
    # Sanitised HERE as well as in `arun`, so an injected `run=` cannot write raw values through.
    return _sanitize(result)


def distil_pending(
    *,
    limit: int = 20,
    language: str | None = None,
    base_dir: str | Path = inbox.DEFAULT_INBOX_DIR,
    should_stop: Callable[[], bool] | None = None,
    on_node: Callable[[], None] | None = None,
    on_error: Callable[[str, Exception], None] | None = None,
    run: Callable[..., Distillation] | None = None,
) -> list[str]:
    """Summarise up to `limit` nodes sitting at `ready_undistilled`, newest first. Returns the ids
    actually distilled.

    **The language ladder, and why it is shorter here than for a notebook.** `output_language()` is
    the operator's stated preference and wins whenever it is set (invariant 39's ladder, top rung).
    Below it, the CALLER supplies one — the future HTTP handler has the request, and therefore the
    `X-RLM-Interface-Language` and `Accept-Language` signals invariant 69 ranks. This function has
    neither, which is exactly why it does not try to resolve one itself. With nothing at all, the
    prompt tells the model to follow the document; that is a KNOWN narrowing of invariant 39 for
    Tier 0, and the way out is a caller that passes the signal, not a resolver in here.

    One node failing never stops the pass: it is left at `ready_undistilled` and the next is tried.
    """
    # `clean_language` on the caller's rung too. `output_language()` is cleaned inside `config`, but
    # the caller's value is meant to come from `X-RLM-Interface-Language` / `Accept-Language` — both
    # attacker-controlled headers — and it is spliced into the prompt. `api.put_settings` already
    # records that 40 characters of "language" is enough for a persistent injected instruction,
    # which is the entire reason `clean_language` exists.
    chosen = output_language() or clean_language(language) or ""
    distilled: list[str] = []
    for node in inbox.list_nodes(state="ready_undistilled", limit=limit, base_dir=base_dir):
        if should_stop is not None and should_stop():
            break
        # CLAIM it, do not label it. Two concurrent passes each snapshotted the same rows and each
        # wrote `distilling` unconditionally — five model calls for three nodes, each overwriting
        # the other. Losing the race here means another pass owns the node; skip it.
        if not inbox.claim_node(node.id, expect="ready_undistilled", to="distilling", base_dir=base_dir):
            continue
        try:
            source = inbox.node_source(node.id, base_dir=base_dir)
        except inbox.UNREADABLE_SOURCE as exc:
            # **PRESENT BUT UNREADABLE is not the same as absent, and it used to end the batch.**
            # `node_source` handles a MISSING blocks file by returning None; a truncated or
            # wrong-shape one RAISES, and the exception escaped after `claim_node` had already
            # written `distilling`. Three things followed, all reproduced: every node after the bad
            # one was silently skipped, the node was stranded in `distilling` where nothing selects
            # it (only a restart's `reset_interrupted_states` recovers it), and because
            # `distilling` is one of the UI's busy states the Inbox then polled ~2.2 times a second
            # for the life of the tab with its progress strip hidden — invariant 79's named failure
            # ("a permanent `queued` — which looks exactly like still working"), one state over.
            if on_error is not None:
                on_error(node.id, exc)
            if on_node is not None:
                on_node()
            inbox.update_node(node.id, base_dir=base_dir, state="ready_undistilled")
            continue
        # The node id travels WITH the exception, because the caller reporting "one of these
        # failed" without saying which is the same silence one level up.
        report = (lambda exc, _id=node.id: on_error(_id, exc)) if on_error is not None else None
        if source is None:
            # **A MISSING BLOCKS FILE IS A FAILURE, not a quiet skip.** The node is claimed, ticked
            # as done and put back at `ready_undistilled` with nothing changed — so the strip read
            # `done 1 / 1, failed 0` over a node that had not been summarised and never would be.
            # Exactly the shape the model-error case was fixed for one round earlier, through the
            # one path that bypassed `distil_source` and therefore its `on_error`.
            if report is not None:
                report(FileNotFoundError(f"no stored text for {node.id}"))
            if on_node is not None:
                on_node()
            inbox.update_node(node.id, base_dir=base_dir, state="ready_undistilled")
            continue
        result = distil_source(source, chosen, run=run, on_error=report)
        # Counted after the CALL, not before it: progress that runs ahead of the spend would tell a
        # reader a node was summarised while the model was still thinking about it (invariant 60).
        if on_node is not None:
            on_node()
        if result is None:
            # Back to where it was. `ready_undistilled` is a real state, not a degraded `ready`:
            # the capture succeeded and only the summary is missing.
            inbox.update_node(node.id, base_dir=base_dir, state="ready_undistilled")
            continue
        inbox.update_node(
            node.id,
            base_dir=base_dir,
            state="ready",
            title=result.title,
            summary=result.summary,
            tags=result.tags,
            entities=result.entities,
        )
        distilled.append(node.id)
    return distilled
