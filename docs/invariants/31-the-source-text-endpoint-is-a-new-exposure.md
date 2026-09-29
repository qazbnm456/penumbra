# Invariant 31: Endpoints that return a whole document are deliberate

**An endpoint that returns a whole document is a deliberate decision, stated openly. There are four: `GET /orbits/{id}/sources/{source_id}`, the trace pair (invariant 29), `GET /horizon/{node_id}/source` and `GET /data/export`.**

Before the first of them, no caller could read more of a source than a citation's short `quote`. Invariant 25's posture covers them in spirit, since the model already sees the whole corpus, but the surface is new and deserves its own line. The source endpoint reuses `corpus.Corpus.get(source_id)`, the same lookup `citations.py` performs on every request, instead of a second hand-written scan.

Clicking a row in the Sources list opens the source viewer (`showSourceViewer(source.id, null, null)`). Its fetch carries a staleness guard, the module-level `AbortController` `sourceViewerAbort`, so a slow response cannot refill a panel the reader has already moved on from. Keep that guard on any future source-detail fetch.

Citations reach the source through invariant 58's References panel: a citation calls `focusReference`, which opens the matching card and marks the cited words in its passage.

`GET /data/export` is the widest of the four: every capture's full text and every orbit file in one zip. It adds reach, not privilege, since every token holder can already read each piece through the other three; it exists so a reader can take everything they made to another tool or keep a copy, and it is built in a temporary file that is deleted once sent.

`Corpus.add()`'s duplicate-id guard is dead code, because nothing in the real ingestion path calls it. This is known and deliberately left alone.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
