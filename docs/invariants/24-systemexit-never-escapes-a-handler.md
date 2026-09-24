# Invariant 24: SystemExit never escapes a handler

**Every `SystemExit` a request handler can reach is turned into an HTTP 500 instead of escaping.**

`cli.py` lets the same `SystemExit` propagate and exit, which is right for a one-shot command. In a long-running server, an unhandled `SystemExit` inside a handler is a crash, not an error response. `api._config()` wraps `PenumbraConfig.from_env`, so never call `from_env()` directly from a handler.

The rule is the invariant, not the current list of places it applies, so re-derive that list instead of trusting it. `config.max_upload_bytes()` raises its own `SystemExit` (through `_env_int`), runs first in `upload_source`, and fell outside `_config()`'s coverage because it is deliberately not a `PenumbraConfig` field (invariant 30). Any standalone config reader a handler calls needs the same treatment.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
