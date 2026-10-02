# Invariant 84: The Horizon's schema changes only by numbered steps

**`horizon._SCHEMA` is the database's first shape and `horizon._MIGRATIONS` its history: one statement per step, applied in order inside `BEGIN IMMEDIATE` and counted in SQLite's `PRAGMA user_version`. A step is appended, never edited or reordered once it has shipped.**

## Why the first shape stays the first shape

A new database runs every step from version 0 and an older one runs only the steps it lacks, so both end identical and no step has to work out which kind of database it is facing. If `_SCHEMA` were updated to the latest shape instead, a new database would already have a column that step 1 then tries to add, and every step would need a guard.

## Why one transaction per step, with the version read inside it

Two processes can open an old database at the same moment (the server and a CLI run, or two servers). The version is read after `BEGIN IMMEDIATE` takes the write lock, so the second process waits and then sees the version the first one wrote. A step that fails rolls back with the version unbumped and runs again on the next start. A database newer than the code is left as it is.

## What it makes possible

Without a version, `CREATE TABLE IF NOT EXISTS` cannot add a column to a database that already exists. The first two steps add `edited` and `distilled_at` for the reader's own labels (invariant 83), steps 3 and 4 create `map_planets` and `map_settings` for the star map (invariant 85), and the persisted `readable` flag that `_READABLE`'s comment asks for is one more step. This is the usual way an embedded SQLite database evolves.

Tables owned by other modules in the same file (`search.py`, `vectors.py`, `asks.py`, `concepts.py`) still create themselves with `IF NOT EXISTS`, and they do so after `_migrate` has run. A step in `_MIGRATIONS` can therefore change only the tables in `_SCHEMA`: on a new database, a step that alters one of the others finds no such table and fails every time. Changing one of those tables needs that module's own guarded step, or its table moved into `_SCHEMA` first.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
