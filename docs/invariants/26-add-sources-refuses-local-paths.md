# Invariant 26: add_sources refuses local paths

**`add_sources` accepts only http(s) URLs, never a local file path, unlike `cli.py`'s `--source`.**

`ingest.ingest_one` treats any non-URL string as a path on the machine running the process and reads it with no allowlist. That is reasonable for a CLI whose operator trusts their own machine. Behind an HTTP endpoint with no per-user authorization (invariants 25 and 77), it is an arbitrary-file-read hole. The attack was reproduced end to end: `POST {"sources": ["/etc/passwd"]}` read the file and returned it through a citation that passed verification.

Accepting files over the API needs its own explicit upload design (invariant 30), never a quiet widening of this check.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
