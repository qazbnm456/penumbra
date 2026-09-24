# Invariant 68: The timeout scales with the tier

**A wall-clock backstop scales with the work requested (`schema.PODCAST_TIMEOUT_FACTOR`).**

A long episode failed at the 300-second default after writing three trace events, while an ordinary chat answer on the same notebook took 77 seconds over four or five planner turns. A tier asking for 60 to 90 utterances built across turns (invariant 64) could never fit, so invariant 63 had shipped a tier that could not finish under its own default.

The backstop exists to catch a runaway, not to cap work the reader explicitly asked for. Scaling per request keeps a runaway chat turn bounded at the value it always had, and an operator's `RN_RUN_TIMEOUT_SECONDS` still moves every tier, because the factor multiplies it. The table sits next to the tier definitions, and a tripwire asserts that every tier has a factor and that the factors never decrease.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
