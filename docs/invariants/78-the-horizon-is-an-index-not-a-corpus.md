# Invariant 78: The Horizon is an index, not a corpus

**The Horizon (`horizon.py`) is an index, not a corpus: nothing at Tier 0 ever assembles a blob, and every write to it is a SQL delta (`update_node`; there is deliberately no `save_node`).**

The one stated exception to the delta rule is `promote_node`'s `INSERT OR REPLACE` into `memberships`, whose four columns are all freshly supplied and which has no earlier row to preserve. The two rules answer different questions (how the Horizon coexists with invariant 8, and how it survives concurrent writers), but breaking either one turns the Horizon back into an orbit.

## Why there are two tiers

`config._DEFAULT_MAX_CORPUS_CHARS` is 8,000,000, a memory-safety cap on the sandbox, not a tuning knob. The whole corpus becomes one variable in the REPL, explored by searching and slicing under `max_iterations=25` and `max_llm_calls=30`. One source measured in this project was 69,859 characters; at that size an orbit tops out near a hundred sources, while a capture horizon is meant for thousands.

```
Tier 0  horizon.py     thousands of nodes, a SQLite index, never a blob
                        ↓ filing (a copy)
Tier 1  orbit.py  about 10 to 50 sources, one JSON file, the corpus blob, invariant 8
```

The rule is narrow and absolute: if anything at Tier 0 calls `Corpus.blob()` over the Horizon, invariant 8 applies to a collection designed to outgrow it. Anything Tier 0 reads from the text reads one node's blocks or a bounded selection, never the whole Horizon. Distillation reads one node. The search index reads one node at a time to build its row. A Horizon ask is the one place a blob is assembled at Tier 0, and it is assembled from a selection that `search.select_for_ask` has already bounded by `PN_HORIZON_ASK_CHARS` and `PN_HORIZON_ASK_ITEMS`, which can never exceed the orbit cap, and then measured against that cap again before the run. That is the same bound an orbit lives under, applied to a selection instead of to a collection, so the ask is a temporary orbit and not an exception to this rule. "Ask the whole Horizon" therefore means "ask what the question's words select from the whole Horizon", and the preview says how many captures that is before anything is spent.

## A node is a parsed Source not yet bound to an orbit

`ingest.ingest_one` already produces a fully parsed, citable `Source` on the host before any task exists (invariant 3), and `Source.marker()` computes `[[SRC:<id>|<locator>]]` from the id when the blob is built instead of storing it in the text (invariant 4). Blocks can therefore be stored with no id, and filing a node is re-numbering plus appending, not fetching again. The id comes from `orbit.append_sources`, from the persisted high-water mark (invariant 50), inside `mutate_orbit`'s lock (invariant 34).

Filing does not consume the node. The node is what persists, and an orbit is a view over a selection of nodes, which is the "facets of yourself" premise. Removing a node therefore never removes a source already filed from it, because the source was copied and an orbit silently losing a cited source would break invariant 12.

Filing matches on the node's own membership, never on the origin. `append_sources` dedupes by origin, and treating "appended nothing" as "this node is already here" let two different nodes with the same origin both record a membership pointing at the first node's source, while the second node's text never reached the orbit. An origin collision is now a loud `ValueError` naming the source that holds it, and filing the same node again stays idempotent, because the membership row identifies it.

A node id for a URL is a hash of the origin alone, so capturing the same URL twice is one row, as invariant 12 requires, and a queued capture can get its id before anything is fetched (invariant 79). Every other origin folds the text into the hash, because a filename is not an identity: two different files named `notes.txt` used to become one node and the second file's content was silently discarded. The input is NFC-normalised first.

An id the module mints is hex and filename-safe; an id it is handed is not. `node_blocks_path` validates the id against the exact minting pattern and asserts that the resulting path stays inside the nodes directory. Before that, `remove_node("../../orbits/mynb")` deleted a live orbit file, and an absolute id escaped the directory entirely, because `Path("horizon/nodes") / "/etc/x"` is `/etc/x`. `test_a_node_id_never_becomes_an_arbitrary_path` pins it.

## The delta rule

Invariant 34 records two faults: a caller reading a snapshot, doing something slow and writing the whole object back over everything written meanwhile, and two critical sections interleaving. Both apply to a global write surface, and distillation is exactly that slow step, a model call between reading a node and writing its summary.

- `update_node(node_id, **fields)` emits `UPDATE nodes SET <only those fields> WHERE id = ?`.
- There is no `save_node(node)`. A whole-object write is the fault itself, and in SQL it is even easier to write than in Python. The missing function is the guard.
- An unknown field raises, which also keeps `id` and `created_at` out of reach.
- Values are validated as well as column names. Checking only the name let `update_node(id, state="bogus")` commit, after which every read of the listing failed validation, so one bad write made the whole Horizon unreadable.

The test reads the SQL that was emitted and asserts it names only the caller's columns, with no `SELECT` before it; a test of two sequential updates would also pass against a whole-row implementation.

Interleaving is handled by a lock plus `ON CONFLICT`, not by a transaction; `horizon.py` has no multi-statement transactions, because `_connect` sets `isolation_level=None`. Eight threads capturing one origin at once used to produce seven `IntegrityError` failures, which `busy_timeout` never retries, and a row whose character count disagreed with the file on disk. `_CAPTURE_LOCK` now guards the read-then-insert within a process, `INSERT ... ON CONFLICT(id) DO NOTHING` lets a loser in another process pass without an error, and an existing blocks file is adopted rather than overwritten. This is weaker than `mutate_orbit`, which holds a cross-process lock across its read-modify-write.

## SQLite traps

`PRAGMA journal_mode=WAL` is the one statement `busy_timeout` does not protect: changing the journal mode needs an exclusive lock, and SQLite returns `SQLITE_BUSY` immediately instead of waiting. Setting it on every connection is a no-op once the mode is WAL, but while a new database is being created, concurrent writers race on the change itself; a concurrency test failed about one run in six. The pragma now runs once per process in `_initialize`, with a lock and a retry, and the same probe ran 60 of 60 clean. `test_connect_never_sets_the_journal_mode` is a source assertion, because the behavioural symptom is a one-in-six flake.

The initialisation cache checks that the database file still exists. Without that, deleting `horizon/` under a running server leaves the path cached, `sqlite3.connect` creates an empty file, and every later call fails with `no such table: nodes`. The DDL is idempotent, so recovery costs one `stat` per connection.

`busy_timeout` and `foreign_keys` are both per connection. Without the second, the `ON DELETE CASCADE` on `memberships` does nothing.

## The search index

`search.py` keeps a full-text index in the same `index.db`, as an FTS5 table beside `nodes`. It is derived: every row can be rebuilt from a node row and its blocks file, `sync` rebuilds whatever is missing or older than its node, and a `search_rows` mapping with `ON DELETE CASCADE` plus a trigger removes a node's index row when the node goes. The mapping uses `AUTOINCREMENT`, because a reused rowid would hand a new node the words of a deleted one if its index row were ever left behind.

Chinese, Japanese and Korean text is indexed as overlapping character pairs, computed in Python because Python's `sqlite3` cannot register an FTS5 tokenizer. FTS5's `unicode61` tokenizer makes a whole run of Han characters one token, and its `trigram` tokenizer cannot match a two-character word, which is most of Chinese vocabulary. A dictionary segmenter was measured and refused: jieba's default dictionary split 關係 on Traditional text, its Traditional dictionary and a Simplified-conversion round trip both split 海馬迴 into 海馬 / 迴在, and a search for 海馬迴 then found nothing. Pairs need no dictionary, carry no Traditional or Simplified bias and never lose a term to a wrong cut; they are the standard CJK analyzer in Lucene for the same reasons. The table is contentless (`content=''`, `contentless_delete=1`, SQLite 3.43 or newer), because storing the paired text would double every node's size.

The searchable states are derived from `schema.NodeState` minus `queued`, `parsing` and `failed`. A hand-written list once said `distilled`, a state that does not exist (a summarised node is `ready`), and every summarised capture would have dropped out of search.

## The star map and the knowledge graph

`topology.py` draws both from rows already in the index: `nodes.entities`, `nodes.tags` and `memberships`. It never reads a node's text and never calls a model, so drawing the Horizon costs one query however large it grows. Two entities are linked when one capture names both; two orbits are bridged when captures filed into each name the same entity. An unsummarised capture names nothing, so it is counted apart and offered for summarising rather than guessed into the picture. Orbits are keyed by `slug`, the token memberships are written with, which `/orbits` also reports, because an orbit's id and its filename can differ (invariant 10). Each drawing's output is capped (the 60 most-named entities, 300 captures, the 12 strongest bridges) and reports how much it left out; the graph's side panel says so when entities were dropped.

## Not here

There are no parsers beyond what `ingest_one` handles, no embeddings and no edges inferred from text. Traditional and Simplified spellings of the same word do not match each other in the index. The find box on the Horizon still matches the distilled fields by substring; the full-text index serves Horizon asks. WAL needs a real local filesystem and degrades or fails on a network share, as the orbit files already do, more quietly.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
