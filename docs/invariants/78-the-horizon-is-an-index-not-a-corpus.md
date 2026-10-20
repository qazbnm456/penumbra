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

The rule is narrow and absolute: if anything at Tier 0 calls `Corpus.blob()` over the Horizon, invariant 8 applies to a collection designed to outgrow it. Anything Tier 0 reads from the text reads one node's blocks or a bounded selection, never the whole Horizon. Distillation reads one node. The full-text index is the kit's, kept by its memory store item by item as each is written. A Horizon ask is the one place a blob is assembled at Tier 0, and it is assembled from a selection that `search.select_for_ask` has already bounded by `PN_HORIZON_ASK_CHARS` and `PN_HORIZON_ASK_ITEMS`, which can never exceed the orbit cap, and then measured against that cap again before the run. That is the same bound an orbit lives under, applied to a selection instead of to a collection, so the ask is a temporary orbit and not an exception to this rule. "Ask the whole Horizon" therefore means "ask what the question's words select from the whole Horizon", and the preview says how many captures that is before anything is spent.

## A node is a parsed Source not yet bound to an orbit

`ingest.ingest_one` already produces a fully parsed, citable `Source` on the host before any task exists (invariant 3), and `Source.marker()` computes `[[SRC:<id>|<locator>]]` from the id when the blob is built instead of storing it in the text (invariant 4). Blocks can therefore be stored with no id, and filing a node is re-numbering plus appending, not fetching again. The id comes from `orbit.append_sources`, from the persisted high-water mark (invariant 50), inside `mutate_orbit`'s lock (invariant 34).

Filing does not consume the node. The node is what persists, and an orbit is a view over a selection of nodes, which is the "facets of yourself" premise. Removing a node therefore never removes a source already filed from it, because the source was copied and an orbit silently losing a cited source would break invariant 12.

Filing matches on the node's own membership, never on the origin. `append_sources` dedupes by origin, and treating "appended nothing" as "this node is already here" let two different nodes with the same origin both record a membership pointing at the first node's source, while the second node's text never reached the orbit. An origin collision is now a loud `ValueError` naming the source that holds it, and filing the same node again stays idempotent, because the membership row identifies it.

A node id for a URL is a hash of the origin alone, so capturing the same URL twice is one row, as invariant 12 requires, and a queued capture can get its id before anything is fetched (invariant 79). Every other origin folds the text into the hash, because a filename is not an identity: two different files named `notes.txt` used to become one node and the second file's content was silently discarded. The input is NFC-normalised first.

## Where the text lives

A capture's labels (its title, summary, tags and entities) are rows in the kit's memory store as well, `inferred` from the summary pass and `said` from the reader (invariant 83), and are read beside the capture's row through a connection that attaches the store read-only (`horizon._connect_labels` and its `labelled` view), so every reader sees the same current labels and the Horizon's own table holds none. A label is written to the kit first and read back after, since an attached read sees the store as it was when its transaction began.

A capture's text is kept twice, for two readers. Its blocks file (`horizon/nodes/<temporary id>.json`, named in the row's `blocks_file`) holds the blocks with their locators, which filing copies into an orbit. Its item in the kit's memory store (`memory_store.py`, `horizon/memory.db`) holds the joined text with its provenance: `said` for a paste, the reader's own words, and `observed` for everything taken from a source. The row records the item (`memory_rowid`) once it exists, and becoming one is invariant 79's business.

The store lives beside `index.db` rather than inside it, because the kit and the Horizon each count their schema in `PRAGMA user_version`, and one file holds one count. It is opened with this product's settings, not the kit's defaults: no cap on an item, since a capture has never had one (only an orbit has, invariant 8); a search index over the first 1,000,000 characters of each text; and origins indexed, since an address is often the one word a reader remembers.

Removing a capture decides and deletes the row in one transaction, unlinks the blocks file, then purges its item and any item a crash left carrying its temporary id (`find_meta`, by `meta.node_id`). Purging after the commit means a removal that decided not to remove (`only_if_unfiled`, filed in the meantime, or waiting to be) never costs a kept capture its text. A capture of the same content can be made again at any moment under the same temporary id, so an item belongs to one row, not to the id: it carries the row's capture time, a capture adopts only an item stamped with its own, and a removal's purge spares the items of the capture live now. The blocks file is unlinked under `_CAPTURE_LOCK` only while no row names it in `blocks_file`, since a removal names the old item id while a new capture of the same content has a new row with the same file. The kit's purge removes the text from its search index too; a purge a busy store blocks is retried off the request's thread, once, and then only its checkpoint, so the words leave the file rather than waiting in the WAL. A clear stops every retry still pending, since the new store reuses the old ids. A membership still pending goes with its orbit or its source, as a written one does. Becoming an item records it in a transaction serialised with the removal's: either the removal sees the item and purges it, or the recording finds no row and purges the item itself, with the blocks; `add_node` then raises `CaptureRemoved` (a `ValueError`) rather than returning nothing. Clearing everything erases the store with the index, and refuses while a capture is being stored; no capture starts storing while it clears.

## A capture's id

A capture's id is a temporary `nd-<hash>` until its text is a kit memory item, and the item's own id (`m<n>`) from then on. The temporary id is a content hash, so a capture can have a row, and be deduped, before anything is read; the item id is what the kit's labels, topics and vectors are keyed by, so the Horizon uses it once there is one. The switch happens once, in the transaction that records the item (`_record_item`): the row's `id` becomes `m<n>`, the old id is kept in `former_id`, and every table holding a foreign key to `nodes(id)` follows, found from the file's foreign keys rather than listed, since some are created by other modules without `ON UPDATE CASCADE`.

The temporary id keeps working. Every public function here, and every route, resolves either id (`resolve_id`, `get_node` matching `id` or `former_id`); a route resolves once and passes the current id on, so another module never receives a temporary id it cannot join. Dedupe at capture and every claim use the temporary id, which a capture keeps. A page re-keys what it holds when a response names a capture with its `former_id`. The browser extension keeps a capture's temporary id rather than its item id: the temporary id is a hash of what was captured and names no other capture, while item ids start again from `m1` after a clear. Removing a capture deletes its row, `former_id` with it, so a later capture of the same content starts as a new capture.

Within one store an item id is never reused (the kit numbers its items with `AUTOINCREMENT`). A clear starts a new store numbered from `m1`, so a page still holding ids from before could name a different capture: the Horizon has an epoch (`horizon.epoch`) that every clear replaces, a page sends it with every request that names a capture, and one that does not match is refused with 412 before the handler runs; the page then reloads. A request that names no capture (a new capture, a question in an orbit) is never refused for it. A Horizon question names the captures its preview chose, so the preview carries the epoch too and a page learns of a clear before the question is sent; whatever the reader was typing into a capture or a question is kept across the reload. A poll that reports a new epoch reloads the page too.

An id the module mints is hex and filename-safe; an id it is handed is not. The blocks file is named by the temporary id at capture and never moves; `node_blocks_path` validates that shape against the exact minting pattern and asserts that the resulting path stays inside the nodes directory, and every reader after capture goes through the row's `blocks_file` instead (`blocks_file_path`). Before that, `remove_node("../../orbits/myorbit")` deleted a live orbit file, and an absolute id escaped the directory entirely, because `Path("horizon/nodes") / "/etc/x"` is `/etc/x`. `test_a_node_id_never_becomes_an_arbitrary_path` pins it. The stored `blocks_file` is validated the same way before it becomes a path.

## The delta rule

Invariant 34 records two faults: a caller reading a snapshot, doing something slow and writing the whole object back over everything written meanwhile, and two critical sections interleaving. Both apply to a global write surface, and distillation is exactly that slow step, a model call between reading a node and writing its summary.

- `update_node(node_id, **fields)` emits `UPDATE nodes SET <only those fields> WHERE id = ?`.
- There is no `save_node(node)`. A whole-object write is the fault itself, and in SQL it is even easier to write than in Python. The missing function is the guard.
- An unknown field raises, which also keeps `id` and `created_at` out of reach.
- Values are validated as well as column names. Checking only the name let `update_node(id, state="bogus")` commit, after which every read of the listing failed validation, so one bad write made the whole Horizon unreadable.

The test reads the SQL that was emitted and asserts it names only the caller's columns, with no `SELECT` before it; a test of two sequential updates would also pass against a whole-row implementation.

Interleaving at capture is handled by a lock plus `ON CONFLICT`. `_connect` sets `isolation_level=None`, so each statement is its own transaction unless a function opens one with `BEGIN IMMEDIATE`, as removal (the record and the delete) and becoming an item (the item, the state and the pending memberships) do. Eight threads capturing one origin at once used to produce seven `IntegrityError` failures, which `busy_timeout` never retries, and a row whose character count disagreed with the file on disk. `_CAPTURE_LOCK` now guards the read-then-insert within a process, `INSERT ... ON CONFLICT(id) DO NOTHING` lets a loser in another process pass without an error, and an existing blocks file is adopted rather than overwritten. This is weaker than `mutate_orbit`, which holds a cross-process lock across its read-modify-write.

## SQLite traps

`PRAGMA journal_mode=WAL` is the one statement `busy_timeout` does not protect: changing the journal mode needs an exclusive lock, and SQLite returns `SQLITE_BUSY` immediately instead of waiting. Setting it on every connection is a no-op once the mode is WAL, but while a new database is being created, concurrent writers race on the change itself; a concurrency test failed about one run in six. The pragma now runs once per process in `_initialize`, with a lock and a retry, and the same probe ran 60 of 60 clean. `test_connect_never_sets_the_journal_mode` is a source assertion, because the behavioural symptom is a one-in-six flake.

The initialisation cache checks that the database file still exists. Without that, deleting `horizon/` under a running server leaves the path cached, `sqlite3.connect` creates an empty file, and every later call fails with `no such table: nodes`. The DDL is idempotent, so recovery costs one `stat` per connection.

`busy_timeout` and `foreign_keys` are both per connection. Without the second, the `ON DELETE CASCADE` on `memberships` does nothing.

## The search index

The full-text index is the kit's memory store's (`items_fts` and `labels_fts` in `memory.db`): each capture's text up to `memory_store.INDEX_CHARS`, its origin, and its current labels, so a title the reader set or a summary that just landed is found at once, with no sync. Penumbra's own FTS index in `index.db` was dropped when search moved there (invariant 84). `search.select_for_ask` asks the kit only for the order (`search_ids` with no limit) and decides the scope itself from the Horizon's rows (the readable states, a tag, an entity with its aliases, an orbit through `memberships`), so the scope is applied inside the ranking, never to a cut of its top hits: with a global `LIMIT`, five hundred better matches outside a tag once left nothing inside it. An empty question matches nothing, although the kit would list every item for one.

Chinese, Japanese and Korean text is indexed as overlapping character pairs (the kit adds single characters), never through a dictionary. FTS5's `unicode61` tokenizer makes a whole run of Han characters one token, and its `trigram` tokenizer cannot match a two-character word, which is most of Chinese vocabulary. A dictionary segmenter was measured and refused: jieba's default dictionary split 關係 on Traditional text, its Traditional dictionary and a Simplified-conversion round trip both split 海馬迴 into 海馬 / 迴在, and a search for 海馬迴 then found nothing. Pairs need no dictionary, carry no Traditional or Simplified bias and never lose a term to a wrong cut; they are the standard CJK analyzer in Lucene for the same reasons. `tests/test_search.py` keeps both measured words as tests against the kit's index.

The searchable states are derived from `schema.NodeState` minus `queued`, `parsing`, `stored_unindexed` and `failed`, so a search returns only captures that are memory items. A hand-written list once said `distilled`, a state that does not exist (a summarised node is `ready`), and every summarised capture would have dropped out of search.

## The star map and the knowledge graph

`topology.py` draws both from rows already in the index: `nodes.entities`, `nodes.tags` and `memberships`. It never reads a node's text and never calls a model, so drawing the Horizon costs one query however large it grows. Two entities are linked when one capture names both; two orbits are bridged when captures filed into each name the same entity. An unsummarised capture names nothing, so it is counted apart and offered for summarising rather than guessed into the picture. Orbits are keyed by `slug`, the token memberships are written with, which `/orbits` also reports, because an orbit's id and its filename can differ (invariant 10). Each drawing's output is capped (the 60 most-named entities, 300 captures, at least each orbit's three strongest bridges, `BRIDGES_PER_ORBIT`) and reports how much it left out; the graph's side panel says so when entities were dropped.

## A summary sees labels, not the Horizon

A summary is shown the tags and entities in use (the kit's `known_listing`: the 80 and 60 most used, each entity once per capture and read through the aliases), so a capture reuses a label that means the same thing. It is a bounded list of names, never other captures' text: feeding summaries or unsummarised sources as context would grow every call with the Horizon, which this invariant exists to prevent, and would let one document's content leak into another's summary.

## Not here

There are no parsers beyond what `ingest_one` handles, no embeddings and no edges inferred from text. Traditional and Simplified spellings of the same word do not match each other in the index. The find box on the Horizon still matches the distilled fields by substring; the full-text index serves Horizon asks. WAL needs a real local filesystem and degrades or fails on a network share, as the orbit files already do, more quietly.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
