# Invariant 1: No network tool in the chat REPL

**No fetch or network tool is ever registered on the chat task's `RLMTask(tools=…)`.**

The fetcher in `parsers/web.py` runs once, on the host, during ingestion. It is never handed to the model while it answers a question.

A source's content is untrusted (invariant 6). If a fetch tool were reachable from the REPL, an instruction hidden in a source could steer the model into sending the orbit's contents to an attacker's URL. `rlm_harness`'s SSRF guard (`is_safe_url`) blocks internal, loopback and metadata targets only; it cannot tell a legitimate-looking external domain from a hostile one.

If "fetch one more page" is ever wanted, it must be a separate action the user explicitly confirms, not a tool the model decides to call.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
