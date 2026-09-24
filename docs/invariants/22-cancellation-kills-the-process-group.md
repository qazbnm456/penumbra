# Invariant 22: Cancellation kills the process group

**Cancellation calls `killpg` on the whole process group (the worker is spawned with `start_new_session=True`), not just the worker's own PID.**

A stuck Deno grandchild must not survive as an orphan once its parent worker is killed. `test_runner.py::test_cancel_kills_the_whole_process_group_not_just_the_leader` spawns a real grandchild and confirms it dies, so breaking this rule turns a test red. Do not simplify it to `process.kill()`, which signals only the worker's PID.

The same rule covers shutdown: `penumbra serve` bounds its graceful shutdown and turns a terminal hangup into SIGTERM, so quitting the server with a run in flight cancels the request and kills the run's whole process group instead of leaving it billing.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
