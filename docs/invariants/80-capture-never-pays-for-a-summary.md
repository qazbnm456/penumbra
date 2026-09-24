# Invariant 80 — Capture never pays for a summary, by default

**Capturing something into the Inbox makes NO model call unless the operator has explicitly turned
that on.** Distillation (`distill.py`) is a separate pass, the number of pending summaries is
knowable before any spend, and a failed summary never costs the capture.

> **The headline used to read "makes NO model call", full stop**, and an opt-in auto path made that
> false. It is rewritten rather than quietly stretched, because a rule that no longer matches the
> code is worse than no rule — three earlier slices in this same body of work each shipped a doc
> asserting something the code contradicted, and each was caught by review rather than by anyone
> reading it. The ARGUMENT below is unchanged; only the quantifier moved.

## The toggle, and why it is allowed on the settings page

`auto_distil` (`config.auto_distil_enabled`) is a settings-page setting — carried by
`config._SETTING_PATTERNS`, `settings_state` and `SettingsRequest`, and the settings page draws it
(`test_the_settings_page_renders_every_setting_the_server_stores` fails if the server ever stores a
setting the page does not render — a key with no row is a key the next Save erases, which is exactly
what happened to this one). That placement looks like it collides with invariant 41: *"Moving a safety BOUND onto a page every token holder can write is the
same mistake as moving a key there, just quieter."* A spend lever is exactly the category
`RN_MAX_UPLOAD_BYTES` is excluded for.

**It is not the same thing, and the distinction is the reason it is allowed.** `POST /inbox/distil`
is itself a spend endpoint: any token holder can already cause model calls, and that is what the
endpoint is FOR. The toggle changes WHEN the spend happens, not whether a token holder can cause
it, so it adds no exposure class — which makes it a behaviour preference, which invariant 41 admits.

What stays OFF the page is the bound. `RN_AUTO_DISTIL_MAX_PER_BATCH` is environment-only, the same
placement invariant 41 gives trace retention and the upload cap, so the worst a flipped toggle can
do is spend up to a number the operator set.

**And the auto path lives in `api.py`, not in `intake.py`.** The queue exposes an idle hook and
knows nothing about what it does; `intake.py` imports nothing model-related at all. That is what
keeps the default STRUCTURAL rather than merely intended — you cannot make capture spend money by
editing the queue.

## Why this is a product rule and not a scheduling detail

BYOK is a decision this project has already made: **the reader supplies their own model
credentials, so every call is their money.** (The working note that settled it is not tracked —
`.gitignore` excludes `docs/` apart from this directory — so the decision is stated here rather
than cited.) And the whole message of the interface is *just throw everything in*. Put those together and
distilling at intake means **importing 200 bookmarks silently spends 200 calls** the reader never
asked for, from a surface designed to make them stop thinking about whether to keep something.

So `intake.py` leaves a parsed node at `ready_undistilled` and stops there. `distil_pending` is a
separate entry point, with a `limit` the CALLER names rather than a default of "everything", and
`GET /inbox` reports `undistilled` so the count is knowable before it runs — which is invariant 47's
*"no action starts without an explicit press"* applied to money instead of to time. A reader can
capture all week and summarise nothing.

## `ready_undistilled` is a real state, not a degraded `ready`

`schema.NodeState` carries it as a first-class value, and the reason is the same promise invariant
79 is named after. A node whose summary failed is **still a usable node** — it has its origin, its
blocks, its flags, and it can be promoted into a notebook and cited like anything else. The only
thing missing is a convenience.

So a failed or cancelled distillation puts the node back to `ready_undistilled` and the pass moves
on. It never becomes `failed`, which means "the capture itself did not work", and it never removes
anything. **Losing a capture because a summariser was unreachable would break the only promise this
feature makes.**

**And that has to survive the process dying, which an earlier draft of this paragraph claimed
without the code behind it.** `distilling` was written in one place and reset nowhere: a crash, a
container restart, or a failing write-back between the claim and the summary stranded a node in a
state NOTHING selects — `distil_pending` queries `ready_undistilled` — with the model call already
paid for and the summary lost. `intake.py` already carried the argument for the sibling case ("the
process that owned them is gone, so the state is a lie") and this did not inherit it.

Both states now live in ONE map, `inbox._OWNED_STATES`, recovered by
`inbox.reset_interrupted_states` at startup. The fallbacks differ and that is the point: a `parsing`
node has no blocks file yet, so it goes back to `queued`; a `distilling` node has one, so only the
summary is missing and it goes to `ready_undistilled`. One map because they are the same fact — two
resetters is how the second one ends up missing again.

**A pass CLAIMS a node, it does not label one.** `inbox.claim_node` is a compare-and-set, because
`update_node(state="distilling")` is something two callers can both do. Measured before it existed:
two concurrent passes over three nodes made **five model calls**, each reporting it had distilled
ids the other also distilled and overwrote. The reader pays for that twice.

## Two inherited rules meet here, from opposite directions

- **Read `Corpus.excerpt`, never `blob()[:n]`** (invariant 61). **Defensive, and worth being exact
  about what it does and does not guard today**: `distil_source` takes ONE `Source`, so invariant
  61's own incident — a prefix that is source ONE with everything after it invisible — is not
  reachable through this signature, and an earlier draft implied it was. What the two readings DO
  differ on here is marker count: `excerpt` emits one per SOURCE, `blob` one per BLOCK, so a
  three-page PDF distinguishes them and a one-page document never can. That is what the test
  asserts; the multi-source shape becomes live the day a node can hold a folder.
- **Strip `[[SRC:...]]` from what comes back** (invariant 62). The excerpt deliberately CARRIES
  those markers; a summary is displayed prose. Read the marked-up text, hand the reader text with no
  coordinates in it. A real run once ended four of five paragraphs with a literal `[[SRC:s1|whole]]`
  on screen, reported as a failed render — which is a fair reading.

## The language ladder is SHORTER here, and that is stated rather than hidden

Invariant 39: model-authored prose follows the READER's language. A summary is model-authored prose,
so it is in scope — but `distil_pending` runs on a background thread with **no request**, so
invariant 69's interface-language signal and `Accept-Language` are both out of reach at the moment
the model is called.

The ladder is therefore: `output_language()` (the operator's STATED preference, invariant 39's top
rung) → the language the CALLER passes, because a future HTTP handler has the request and can
supply the signal → nothing, in which case the prompt tells the model to follow the document.

**That last rung is a known narrowing of invariant 39 for Tier 0.** It is written down here so it
is a decision rather than a discovery, and the way out is a caller that passes the signal — not a
resolver inside a function that has no request to resolve from.

## Not an `RLMTask`, and not in a subprocess

`naming.py` already argues the first half: the full rlm-harness REPL loop in a sandbox is right for
exploring a multi-MB corpus with verifiable citations and absurd for three sentences. Invariant 21
is untouched — its guarantee is about `RLMTask` EXECUTION, not about every model call.

The second half is new: `naming.SuggestTitle` reaches the API's subprocess only because `api.py`
routes it through `worker.py`, and nothing requires that of a Predict. Spawning a subprocess per
captured node would cost more than the call it isolates, and the pass already survives any single
node failing. `DistillNode` keeps `worker.py`'s `arun(**kwargs)` shape anyway, so moving it behind a
subprocess later needs no caller changes.

**`import dspy` lives inside `arun`, and that placement is load-bearing** — a top-level import would
make every `cli.py` command pay for dspy. Pinned by a subprocess blocker, not by this sentence.

**And it must never be called from inside an event loop.** `asyncio.run` refuses to, and the
intended caller is a FastAPI handler — so the check is OUTSIDE the `except`, and raises. Swallowed,
it turned a wiring mistake into every node bouncing back to `ready_undistilled` with a log line
indistinguishable from an unreachable model. `asyncio.to_thread(distil_pending, ...)` is the
supported shape, which is what `api.py` already does for every other blocking call.

## Three places the first draft let something through

- **Sanitisation lived only in `DistillNode.arun`**, so every caller that injected its own `run=` —
  which is every test, and any future caller that swaps the model — wrote raw values straight to
  `inbox.update_node`. Deleting the cleaning left the entire suite green. `_sanitize` is now applied
  in `distil_source` as well; it is idempotent, so neither path can be the one that forgot.
- **The "nothing to summarise" guard read the EXCERPT**, and `Corpus.excerpt` unconditionally
  prepends `[[SRC:...]]` — so a source with no blocks, one empty block or one whitespace block all
  produced a truthy string and were paid for. It reads the source text now, before the corpus.
- **Tags were lowercased AFTER the deduplication**, so `["ML", "ml", "Ml"]` became three tags.
  `schema.Distillation` calls tags "the join key a later slice needs for implicit edges", where
  duplicates are not cosmetic.

---

One-line index: [`AGENTS.md`](../../AGENTS.md) · Incidents, measurements and superseded drafts: [`CHANGELOG.md`](../../CHANGELOG.md)
