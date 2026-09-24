# Invariant 64: Long scripts are built across turns

**A `long` script is built across REPL turns, which is what the sandbox is for.**

Written as one code block, a long script was cut off mid-structure by the per-call generation cap and the run failed. Built up in a list across turns, printing only its length and never its contents, the same corpus under the same cap produced 80 utterances with 44 citations. Nothing about the budget changed.

Raising `max_tokens` would have been the wrong answer here. Invariant 59's raise was right because the planner's reasoning did not fit in one reply; this was an output that should never have been one reply. If a finished object will not comfortably fit in one reply, it must not be written in one reply. The rule lives in the prompt as `instructions.ACCUMULATE_LARGE_OUTPUTS` for all six tasks (invariant 65), and the `corpus-navigation` skill explains it.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
