# Invariant 21: The API runs every task in a subprocess

**Every API request that runs an `RLMTask` does so in an isolated subprocess (`runner.py` and `worker.py`), never in the server process.**

This is a separate execution model from `cli.py`, which runs synchronously in-process, and the two coexist. `worker.py` is the only place an `RLMTask` runs (`.arun()` is called there and nowhere else), so a crash deep in a model run takes down a worker subprocess and never the API server.

The guarantee is about execution, not imports. `api.py` does import `dspy` and `rlm_harness` indirectly, because it imports the task classes for `_dotted()` and they import `rlm_harness` at module scope, so do not claim otherwise.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
