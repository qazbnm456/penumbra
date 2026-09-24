# Invariant 56: Follow-ups come from the same run

**`Answer.follow_ups` comes from the same run that produced the answer, never from a second model call, and is not verified against anything.**

When the model submits, it already holds the corpus and its own answer, so asking for two or three next questions in the same SUBMIT costs nothing, while a separate `dspy.Predict` would be a real call per answer. The questions are not citation-grounded, because a question is a prompt, not a claim, and invariant 5 has nothing to check. The instruction still requires each to be answerable from the sources; that is a compliance claim the offline scripted LM cannot demonstrate. The field is optional and defaults to empty, so older turns still load.

The overview's row says "Start with" and an answer's says "Ask next", sharing one renderer (`starterQuestionRow`). The overview's appears before any conversation exists, where "ask next" would ask the reader to continue something they have not started, and it gives way to the latest answer's row once the first answer arrives. Clicking a suggestion asks it directly, without touching a draft in the composer, and only while no run holds the composer.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
