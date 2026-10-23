# Invariant 84: The Horizon's schema changes only by numbered steps

**`horizon._SCHEMA` is the database's first shape and `horizon._MIGRATIONS` its history: one statement per step, applied in order inside `BEGIN IMMEDIATE` and counted in SQLite's `PRAGMA user_version`. A step is appended, never edited or reordered once it has shipped.**

## Why the first shape stays the first shape

A new database runs every step from version 0 and an older one runs only the steps it lacks, so both end identical and no step has to work out which kind of database it is facing. If `_SCHEMA` were updated to the latest shape instead, a new database would already have a column that step 1 then tries to add, and every step would need a guard.

## Why one transaction per step, with the version read inside it

Two processes can open an old database at the same moment (the server and a CLI run, or two servers). The version is read after `BEGIN IMMEDIATE` takes the write lock, so the second process waits and then sees the version the first one wrote. A step that fails rolls back with the version unbumped and runs again on the next start. A database newer than the code is left as it is.

## What it makes possible

Without a version, `CREATE TABLE IF NOT EXISTS` cannot add a column to a database that already exists. The persisted `readable` flag that `_READABLE`'s comment asks for is one step, and so is every later column. This is the usual way an embedded SQLite database evolves. A stand-in step appended after the shipped ones tests the mechanism.

## The baseline was reset once, before release

When a capture's text moved into the kit's memory store (invariant 78), `_SCHEMA` became a new baseline that already holds everything the five earlier steps added, and `_MIGRATIONS` started empty again. That is allowed exactly once, while nothing has been released, because no reader holds a database the old steps would bring forward. The file is marked as this layout with `PRAGMA application_id` (`horizon._APPLICATION_ID`). A database with a `nodes` table and any other mark is from before the reset: it is moved, with its `nodes/` directory, into `pre-memory-<time>/` beside it, and an empty Horizon starts. Nothing is deleted or converted. After release, the rule above holds without exception.

The first steps after the reset add `nodes.former_id` with a unique index, for a capture's temporary id once it is a kit item (invariant 78), and the `horizon_meta` table that holds the Horizon's epoch. The next six drop the label columns (`title`, `summary`, `tags`, `entities`, `edited`, `distilled_at`), once a capture's labels moved to the kit's memory store, so a read left behind fails rather than finding stale values. Nothing is copied across: no build with labels in those columns was released, so there were none to carry. The baseline's `node_ids` table, reserved for the same job before `former_id` replaced it, stays an empty table nothing reads: a step dropping it would be undone at the next start by `_SCHEMA`'s `CREATE TABLE IF NOT EXISTS`, and the baseline is not edited.

Tables owned by other modules in the same file (`asks.py`) still create themselves with `IF NOT EXISTS`, and they do so after `_migrate` has run. A step in `_MIGRATIONS` can therefore change only the tables in `_SCHEMA`: on a new database, a step that alters one of the others finds no such table and fails every time. Changing one of those tables needs that module's own guarded step, or its table moved into `_SCHEMA` first.

There is one exception: a `DROP TABLE IF EXISTS` of a table no module creates any more, landed in the same commit that removes the code that created it. On a new database it does nothing; on an older one it frees the table; and with the creating code gone, nothing puts the table back at the next start, which is the trap a drop with its creator still in place would fall into. Steps 10 to 13 are this: `search_rows` and `search_fts` (Penumbra's own full-text index, replaced by the kit's) and `entity_aliases` and `entity_seen` (its alias tables, replaced by the kit's). Steps 14 to 18 are the same for local relations: `vector_rows`, and the four plain tables `sqlite-vec` kept its embeddings in (`node_vectors_info`, `_chunks`, `_rowids`, `_vector_chunks00`), dropped because an embedding can be partly turned back into its text and nothing would ever delete them otherwise. Their virtual table, `node_vectors`, cannot be dropped without the extension, which is no longer installed ("no such module: vec0"): a database from before keeps it as an entry nothing opens. Measured with the extension absent, storing and re-keying a capture, clearing, `ALTER TABLE`, `VACUUM`, the backup API and `integrity_check` all work with it in place. No released build wrote one. Step 19 adds `orbit_topics`, which orbit is which kit topic (`topics.py`), and steps 20 and 21 drop `filing_dismissed` and `organize_left`, since dismissals and organising's leftovers are now the kit's; dismissals recorded before are not carried. Each step names `main.` explicitly, because the kit's store, attached as `mem` on a labels connection, has tables called `entity_aliases` and `entity_seen` too, and an unqualified name would reach them wherever `main` has none. A test fails on any other mention of these names in the package.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
