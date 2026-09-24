# Invariant 78 — The Inbox is an index, not a corpus

**Nothing at Tier 0 (`inbox.py`) ever assembles a corpus blob, and every write to the index is a
SQL DELTA** — with exactly one stated exception, `promote_node`'s `INSERT OR REPLACE` into
`memberships`, whose four columns are all freshly supplied and which has no prior row to preserve.
Those are two rules because they answer two different questions — how the Inbox
coexists with invariant 8, and how it survives concurrent writers — but they are one invariant
because breaking either one turns the Inbox back into a notebook.

## Why there are two tiers at all

`config._DEFAULT_MAX_CORPUS_CHARS` is **8,000,000**, and its own comment says it is a memory-safety
cap on the pyodide/deno sandbox, *not* a tuning knob. The RLM mechanic behind it is that the entire
corpus becomes ONE variable in the sandboxed REPL, which the model explores with `.find()` and
slicing (`corpus.py`'s opening docstring: "not a new indexing layer"), under `max_iterations=25`
and `max_llm_calls=30`.

One source measured in this project was **69,859 characters** — invariant 61's incident, where a
four-source notebook was titled by transliterating source one because everything after it fell
outside a 4,000-character window. At that size a notebook tops out near a hundred sources.

A capture inbox is aimed at thousands. **The two only coexist because they are different things:**

```
Tier 0  inbox.py     thousands of nodes, a SQLite index, no blob, ever
                        ↓ promotion (a copy)
Tier 1  notebook.py  ~10-50 sources, one JSON file, the corpus blob, invariant 8
```

So the rule to defend is narrow and absolute: **the moment something at Tier 0 calls `Corpus.blob()`
over the inbox, invariant 8 is back in play against a collection designed to outgrow it.** Anything
Tier 0 needs to read from the text — distillation, search, an embedding — reads one node's blocks,
or `Corpus.excerpt` over a bounded selection. Never the whole inbox, never a blob.

## A node is a parsed Source that is not bound to a notebook yet

That framing is what makes the tier cheap rather than a second ingestion stack, and it rests on two
facts that were already true:

- `ingest.ingest_one` produces a fully-parsed, citable `Source` host-side, before any task exists
  (invariant 3).
- `Source.marker()` COMPUTES `[[SRC:<id>|<locator>]]` from the id at blob time rather than storing
  it in the block text (invariant 4).

So blocks can be stored with no id assigned, and **promotion is re-id + append, not re-fetch.** No
new parsing, no new marker scheme, and citations behave exactly as they already do. The id comes
from `notebook.append_sources`, which renumbers from the max id in use (invariant 50) inside
`mutate_notebook`'s lock against a re-read of the file (invariant 34).

**Promotion does not consume the node**, and that is the "different facets of yourself" premise
rather than an implementation convenience: the node is what persists, and a notebook is a view over
a selection of them. It follows that removing a node must NOT reach a source already promoted from
it — the source was copied, and a notebook silently losing a cited source because someone tidied
their inbox would break invariant 12's promise.

**Promotion matches on the node's own prior MEMBERSHIP, never on the origin — and matching on the
origin lost data.** `append_sources` dedupes by origin, and the first draft read "appended nothing"
as "this same node is already here". It means *some* source here shares this origin. Reproduced:
two distinct nodes sharing one origin both recorded a membership pointing at the FIRST node's
source, the second node's text never reached the notebook, and `promote_node` returned success —
corrupted index state, not a missed append. The origin collision is now a loud `ValueError` naming
the source that already holds it, and re-promoting the same node stays idempotent because the
membership row, not the origin, is what identifies it.

**A node's id is the hash of its origin**, so dedupe is free: capturing the same URL twice is one
row, which is the property invariant 12 already requires of `--source`. That covers pasted text
without a special case, because `ingest.ingest_pasted_text` already builds a content-derived origin
(`f"pasted:{snippet} #{hash}"`) — not the bare string `"pasted"`, which an earlier draft of
`schema.Node` said and which would collide every paste into one node.

**A MINTED id is filename-safe; a RECEIVED one is not, and this paragraph used to say otherwise.**
It read: *"the id is hex, so it is filename-safe by construction and invariant 10's traversal
problem cannot arise — there is no `slug()` step here to get wrong."* True of ids this module makes,
false of ids it is handed, which is exactly the distinction invariant 10 exists to draw. Written as
an invariant, it would have told whoever writes `DELETE /inbox/{node_id}` that no guard was needed.

It was not hypothetical. `node_blocks_path` interpolated the id straight into a path, and
`remove_node`'s `unlink` sat outside the `if changed` guard, so — both reproduced —
`remove_node("../../notebooks/mynb")` **deleted a live notebook file and returned `False`**, and an
absolute id discarded the directory outright, because `Path("inbox/nodes") / "/etc/x"` IS `/etc/x`.
`node_blocks_path` now validates against the exact minting pattern AND asserts containment: the
pattern is the guard, the containment check is format-independent depth so a later change to the id
format cannot quietly reopen it. Pinned by `test_a_node_id_never_becomes_an_arbitrary_path`.

## The delta rule, and why the signature enforces it

Invariant 34 records TWO faults and is explicit that a lock alone would not have helped: a caller
read a snapshot, ran something SLOW, and wrote the whole object back over everything written
meanwhile; and separately, two critical sections interleaved.

Both carry over to a global write surface, and **distillation is exactly that slow step** — a model
call between reading a node and writing its summary. So:

- `update_node(node_id, **fields)` emits `UPDATE nodes SET <only those fields> WHERE id = ?`.
- **There is deliberately no `save_node(node)`.** A whole-object write is the fault itself, and in
  SQL it is *easier* to write than in Python, because `SELECT *` into an object and back feels
  tidy. The absence of the function is the guard.
- An unknown field raises rather than being ignored, which also keeps `id` and `created_at` out of
  reach — the two things that must never change.
- **The VALUE is validated too, not just the column name.** Checking only the name let
  `update_node(id, state="bogus")` commit, after which `Node.model_validate` failed on every
  read-back — so one bad write made the whole LISTING unreadable, not just its own row. Each delta
  is now checked against that field's own type before anything is written, which is the same "flag,
  never silently drop" discipline `notebook.list_notebook_summaries` already applies on the way
  out (invariants 5/6).

**The interleaving half is answered by a LOCK plus `ON CONFLICT`, not by a transaction — and an
earlier draft of this paragraph claimed otherwise.** It said transactions answered it "across
processes, which is strictly stronger than what notebooks have". There are no multi-statement
transactions in `inbox.py` at all: `_connect` sets `isolation_level=None`, so every statement is
its own. The one place atomicity was actually needed is where it broke. Measured: eight threads
capturing one origin from a barrier produced **seven `IntegrityError: UNIQUE constraint failed`** —
and `IntegrityError` is not an `OperationalError`, so `busy_timeout` never sees it and nothing
retries — while the surviving row reported 80 characters against 40 on disk, because every losing
thread still wrote the blocks file.

What answers it now: `_CAPTURE_LOCK` around the read-then-insert (exact within a process, which is
the only case invariant 23 leaves open anyway), `INSERT ... ON CONFLICT(id) DO NOTHING` so a
cross-process loser gets no error, and adopting an existing blocks file rather than overwriting it
so the row's `chars` always agrees with the disk. Compared with `notebook.mutate_notebook`, which
really does hold a cross-process `flock` across its read-modify-write, the Inbox is **weaker** here,
not stronger — say so rather than inheriting a claim from a sibling paragraph.

## The trap that cost a debugging session, measured

**`PRAGMA journal_mode=WAL` is the one statement here that `busy_timeout` does not protect.**
Changing the journal mode needs an exclusive lock, and SQLite does **not** invoke the busy handler
for that change — it returns `SQLITE_BUSY` immediately while any other connection is active.

The first draft ran it on every connection, and the reasoning was almost right: WAL is a property
of the FILE, so re-setting it is a no-op. It is a no-op *once the mode is already WAL*. While a
brand-new database is being created, concurrent writers race on the change itself.

`test_concurrent_writers_all_land` failed about **one run in six**; a probe looping over fresh
directories reproduced it on attempt 5 and put the traceback on that exact pragma. After moving the
pragma into `_initialize` (once per process, with an in-process lock and a retry for the
cross-process case), the same probe ran 60/60 clean.

It is pinned by a SOURCE assertion — `test_connect_never_sets_the_journal_mode` — and it has to be,
because the behavioural symptom is a one-in-six flake that would pass five times out of six after
the regression came back. Same reasoning as invariants 36 and 54.

**The initialization cache must notice a database that vanished.** It is keyed by resolved path, so
without also checking that the file still exists, `rm -rf inbox/` against a running server leaves
the key cached, `sqlite3.connect` makes an empty file, and every later call raises `no such table:
nodes` for the life of the process. The DDL is all `IF NOT EXISTS`, so recovering costs one `stat`
per connection.

**The delta rule's test had to be rewritten, and the rewrite is the point.** A test that made two
sequential `update_node` calls and checked both fields survived passes against a whole-row
implementation too, because each call re-reads inside itself — it was a hollow green, found by an
independent review. The real guard reads the SQL that was emitted and asserts it names the caller's
columns and nothing else, with no `SELECT` before it.

Two smaller per-connection facts that are easy to assume are sticky and are not: `busy_timeout` and
`foreign_keys` are both per-CONNECTION. Without the second, the `ON DELETE CASCADE` on
`memberships` is decoration.

## What is NOT here, so nobody assumes it

No parsers beyond what `ingest_one` already handles, no embeddings, no implicit edges, no graph
(the working note that settled it is untracked, so: the graph is decorative and the edges that matter —
citations — already exist), and no cross-notebook search surface. The index carries `tags` and
`entities` so a later slice can join on them without a migration.

**WAL needs a real local filesystem** and degrades or fails on a network share. The same is already
true of the notebook JSON files; it just fails more quietly there.

---

One-line index: [`AGENTS.md`](../../AGENTS.md) · Incidents, measurements and superseded drafts: [`CHANGELOG.md`](../../CHANGELOG.md)
