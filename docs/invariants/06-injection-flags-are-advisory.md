# Invariant 6: Injection flags are advisory

**`injection_scan.py`'s flags are deterministic and additive, and they gate nothing.**

A flagged source still reaches the model and its answers still return. The flag is metadata attached to the source at ingestion (`ingest.with_injection_flags`). An answer never carries one, because `AskResponse` has no flags field, but the source shows it everywhere: `cli.py` prints it, `api.py` returns `flags` on each source in `OrbitResponse` and on `SourceDetailResponse`, and the web UI shows an amber `⚠` chip in the Sources list and a row in the source viewer.

It is a transparency mechanism, so do not wire it to refuse a run. Its patterns trade recall for precision on purpose; a paper that discusses prompt injection can trip it. That false-positive rate is acceptable for a flag nobody has to act on, so do not tighten the patterns into false negatives to get a cleaner result.

Because the flags gate nothing, their whole value is whether a person can act on them. Each flag is therefore a sentence addressed to a person, never a raw regex: `_INSTRUCTION_PATTERNS` pairs every pattern with its description, and the role-label pattern is anchored to its own line (`^\s*(system|assistant|user)\s*:\s*`, MULTILINE) instead of matching mid-sentence prose.

The scan runs once, at ingestion, and its result is stored in `Source.flags`. Nothing re-scans, so a change to the patterns applies only to sources ingested afterwards. There is deliberately no migration: re-scanning on every read is expensive, and rewriting on load would silently edit stored orbits.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
