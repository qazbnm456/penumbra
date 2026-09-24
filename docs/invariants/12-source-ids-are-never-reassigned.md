# Invariant 12: Source ids are never reassigned

**Extending a notebook with `--source` dedupes by origin and never reassigns an existing source's id.**

`notebook.existing_origins` and `ingest.ingest_new`'s `skip_origins` (reached through `notebook.ingest_sources_for`) make passing the same path or URL again a no-op. A source already cited in a saved `ChatTurn.answer` can therefore never have its id repointed at different text. The guarantee is what matters here; id assignment itself belongs to `append_sources`, which numbers new sources against the freshly loaded notebook inside the lock (invariants 34 and 50).

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
