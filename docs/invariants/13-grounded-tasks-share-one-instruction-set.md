# Invariant 13: Grounded tasks share one instruction set

**Every citation-grounded `RLMTask` takes its citation-marker and validate-before-submit instructions from `instructions.py`, never from a hand-copied paragraph.**

All six tasks compose the same three shared pieces (`CITATION_RULES`, `validate_before_submit_rule(...)`, and `VERBATIM_COORDINATES` through `chat_language_rule` or `artifact_language_rule`) onto their own opening. A wording fix to a shared piece must never land on one task's local copy, so there must be no local copy.

The task-specific opening is deliberately not unified. `AnswerQuestion`'s "ground only in sources" sentence is about a missing answer, while `guide.py:_grounded_instructions` is about an unsupported claim, and forcing one sentence would blur one of them. `cli._prepare` applies the same one-copy rule to the orbit setup that `ask` and `guide` both need.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
