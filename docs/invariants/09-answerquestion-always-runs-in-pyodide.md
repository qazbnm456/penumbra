# Invariant 9: AnswerQuestion always runs in Pyodide

**`AnswerQuestion` always runs in the `pyodide` sandbox, and `NotebookConfig.from_env` refuses any other `RN_INTERPRETER` value instead of silently overriding it.**

An operator who set `RN_INTERPRETER=local` believes something about the run that would stop being true if the value were quietly corrected. Refusing makes the misconfiguration visible.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
