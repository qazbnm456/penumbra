# Invariant 4: Citation markers are opaque coordinates

**The corpus blob uses `[[SRC:<id>|<locator>]]` markers, and every citation-grounded task's instructions teach the model to treat them as opaque and echo them verbatim in a `Citation`.**

That covers all six tasks: `AnswerQuestion` (`task.py`), the four Orbit Guide tasks (`guide.py`) and `GeneratePodcastScript` (`audio.py`). `CITATION_RULES` in `instructions.py` is the one copy of the rule (invariant 13). Without an explicit rule the model has no reason to keep an ad hoc marker intact through `.find()` and slicing, and `citations.py` would have nothing to verify against.

The offline tests drive a scripted LM with fixed turns, so they prove the tool wiring and the SUBMIT chain, not real model compliance. Live runs have shown a real model following the rule. That is evidence, not proof, and must not be restated as a guarantee.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
