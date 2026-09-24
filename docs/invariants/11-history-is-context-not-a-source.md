# Invariant 11: History is context, not a source

**`history` (earlier turns) is context only, never a source of facts or citations.**

`AnswerQuestion.instructions` says so, and `citations.py` never trusts a citation because a similar one appeared earlier: every citation is verified again against the current `sources` blob. A past answer that was wrong, or a source that has since been removed, must not be inherited by a new answer.

As with invariant 4, the evidence is behavioural, not a proof: in a live turn the model used history to resolve a reference while still deriving its citation from `sources`.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
