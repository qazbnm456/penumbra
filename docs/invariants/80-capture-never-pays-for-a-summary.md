# Invariant 80: Capture never pays for a summary by default

**Capture makes no model call unless the operator turns that on: distillation (`distill.py`) is a separate pass, off by default and bounded by a batch size capped at 500, and a failed summary leaves the node at `ready_undistilled` instead of costing the capture.**

## Why this is a product rule

This project is bring-your-own-key: the reader supplies the model credentials, so every call is their money. The interface's whole message is "just throw everything in". Together, distilling at intake would mean importing 200 bookmarks silently spends 200 calls the reader never asked for, from a surface designed to stop them thinking about whether to keep something. The decision is stated here rather than cited, because the working note that settled it is not tracked.

So intake leaves a parsed node at `ready_undistilled` and stops. `distil_pending` is a separate entry point with a `limit` the caller names, never "everything", and `GET /horizon` reports the `undistilled` count, so the cost is known before anything runs. That is invariant 47's "no action starts without an explicit press" applied to money. A reader can capture all week and summarise nothing.

## What a summary pass may spend, and what follows it

A short capture (up to `distill.SHORT_LIMIT`, 12,000 characters) is one call that reads the whole text. A long one is `DistillLongDocument`, an RLM run in a worker subprocess that reads the whole document from a section map, which costs several calls. The summarise buttons say so before the press: `GET /horizon/distil/estimate` counts the long captures waiting and the label gives a range rather than a single number.

Concept alignment (`AlignConcepts`) is the other model call the pass can make, and it follows the same rule: it runs only at the end of a pass the reader pressed, never on its own and never after the automatic pass, once per pass, over at most 60 names no alignment has seen before (`concepts.entity_seen`). A stopped pass does not go on to align, and the pass's Stop ends a long-document or alignment worker at once rather than after it finishes. The estimate is a bound rather than a guess: the top of its range counts every long document and the one alignment run at the full budget an RLM run is capped by (its steps, its sub-model calls, the one extraction when the steps run out, times the whole-run retries allowed), and the per-orbit summarise button shows it as a number; the Horizon's own button says in words that long captures and alignment take more. A failed alignment is reported beside the pass and leaves its names unseen, so the next pass tries again; the same names failing twice are set aside, so a persistent failure is not paid for at the end of every pass. A Stop is not reported as a failure.

By default the automatic pass leaves long captures for a press. It runs on the intake worker's thread, and an RLM run holding that thread for minutes would keep a capture dropped meanwhile at `queued`. With long ones deferred, each capture in a batch is one call. `auto_distil_long` (`PN_AUTO_DISTIL_LONG` or the settings page) lets it take them too, for a model fast or local enough that neither the wait nor the extra calls matter. It does not align either, for the same reason; the names it writes are aligned at the end of the next pass the reader presses.

## The toggle and its bound

`auto_distil` (`config.auto_distil_enabled`) is a settings-page option, and `test_the_settings_page_renders_every_setting_the_server_stores` fails if the server stores a setting the page does not draw, because a key without a row is erased by the next Save. It is allowed there although invariant 41 keeps safety bounds off that page, because `POST /horizon/distil` already lets any token holder cause model calls. The toggle changes when spending happens, not whether a token holder can cause it, so it adds no new exposure. Each pass, automatic or pressed, takes at most the batch size (`config.distil_batch_size`: `PN_DISTIL_BATCH` or the settings page, 20 by default, never more than 500, the most `POST /horizon/distil` accepts), so a flipped toggle spends at most one batch per idle.

The automatic path lives in `api.py`, not `intake.py`. The queue exposes an idle hook and imports nothing model-related, so the default is structural: capture cannot be made to spend money by editing the queue. The automatic pass shares the manual pass's progress state, so it is visible, stoppable and cannot overlap a manual pass (invariant 47).

## ready_undistilled is a real state

`schema.NodeState` carries it as a first-class value, for invariant 79's reason. A node whose summary failed is still a usable node: it has its origin, blocks and flags, and it can be filed into an orbit and cited. Only a convenience is missing. A failed or cancelled distillation puts the node back to `ready_undistilled` and the pass moves on; it never becomes `failed`, which means the capture itself did not work, and nothing is removed.

That survives the process dying. `horizon._OWNED_STATES` maps each in-progress state to its fallback, and `horizon.reset_interrupted_states` applies it at startup: a `parsing` node has no blocks yet and returns to `queued`, while a `distilling` node has its blocks and returns to `ready_undistilled`. One map, because two resetters is how the second one goes missing; `distilling` was once reset nowhere, stranding nodes in a state nothing selects after a crash.

A pass claims a node rather than labelling it. `horizon.claim_node` is a compare-and-set, because two callers can both run `update_node(state="distilling")`; before it existed, two concurrent passes over three nodes made five model calls and overwrote each other's summaries.

## Two inherited rules

The summariser reads `Corpus.excerpt`, never `blob()[:n]` (invariant 61). `distil_source` takes one `Source`, so the multi-source prefix problem is not reachable today; what the two readings differ on here is marker placement (one per source against one per block), which a three-page PDF shows and the test asserts. The multi-source case becomes real when a node can hold a folder.

`[[SRC:...]]` markers are stripped from the result (invariant 62). The excerpt carries markers, and a summary is displayed prose; a real run once ended most of its paragraphs with a literal marker on screen.

## The language ladder is shorter here

A summary is model-written prose, so invariant 39 applies, but `distil_pending` runs on a background thread with no request, so the interface-language signal (invariant 69) and `Accept-Language` are out of reach. The ladder is `output_language()` (the operator's stated preference), then a language the caller passes, then nothing, in which case the prompt tells the model to follow the document. That last step is a known narrowing of invariant 39 for Tier 0; the way out is a caller that passes the signal, not a resolver inside a function with no request.

## Not an RLMTask, not a subprocess

The full REPL loop suits exploring a large corpus with verifiable citations and is absurd for three sentences (the same argument as `naming.py`). Invariant 21 covers `RLMTask` execution, not every model call. Spawning a subprocess per node would cost more than the call it isolates, and the pass already survives any single node failing. `DistillNode` keeps `worker.py`'s `arun(**kwargs)` shape, so moving it behind a subprocess later needs no caller changes.

`import dspy` lives inside `arun`, because a top-level import would make every `cli.py` command pay for dspy; a subprocess import blocker pins it.

It must never be called from inside an event loop, because `asyncio.run` refuses, so that check raises outside the `except`. Swallowed, a wiring mistake looked exactly like an unreachable model. `asyncio.to_thread(distil_pending, ...)` is the supported shape.

## Details that must hold

- Values are sanitised in `distil_source` as well as in `DistillNode.arun`, because callers that inject their own `run=` (every test, and any caller that swaps the model) otherwise wrote raw values to `horizon.update_node`. Sanitising is idempotent, so neither path can be the one that forgot.
- The "nothing to summarise" check reads the source text, not the excerpt, because `Corpus.excerpt` always prepends a marker and an empty source produced a non-empty string that was paid for.
- Tags are lowercased before deduplication, so `["ML", "ml", "Ml"]` is one tag. Tags are the join key for later features, so duplicates are not cosmetic.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
