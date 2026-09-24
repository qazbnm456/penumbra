# Invariant 20: One ingestion module for both entry points

**`ingest.py` and `orbit.py` (`is_url`, `ingest_one`, `ingest_new`, `load_or_create`, `ingest_sources_for`, `append_sources`, `mutate_orbit`) are shared by `cli.py` and `api.py`, and neither entry point depends on the other for its work.**

They were extracted once both entry points needed the same "give me an orbit and ingest new sources into it" step, so a fix to source handling cannot land on only one of them by accident. Do not reach into `cli.py` from `api.py`, or the reverse; code both need belongs in a shared module that does not care which entry point calls it.

There is one literal exception, and it is a string, not a dependency. `cli._cmd_serve` passes `"penumbra.api:app"` to uvicorn, which resolves it at run time; `cli.py` never imports `api.py`. `cli.py` still imports cleanly with fastapi absent, which is what this rule protects, and `serve` reports the missing extra instead of raising.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
