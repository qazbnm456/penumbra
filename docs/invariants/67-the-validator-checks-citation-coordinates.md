# Invariant 67: The validator checks citation coordinates

**The pre-SUBMIT validator checks each citation's coordinate against the corpus the run was given, and every grounded task shares one base class (`GroundedTask`) instead of its own copy of `__init__`.**

The check is structural: anything in the output carrying both `source_id` and `locator` is a coordinate. That is how `DistillLongDocument`'s entity mentions are checked without a line of their own, and the host checks them once more after the run (`distill.from_long`).

The failure was specific: every web source is one block with locator `whole`, and a model wrote the section heading it was citing into `locator`, which made every citation in an overview unverifiable.

`citations.verify_citations` remains the guarantee (invariant 5); this is the early warning, computed from the same text, while the model can still fix it. `instructions.coordinates_in` extracts every `source_id|locator` pair that occurs as a marker, and `_cited_coordinates` walks the output structurally (anything carrying both fields) instead of importing `Citation`, so a future citation-shaped model is covered automatically.

A rejection shows a real coordinate, not just which ones are wrong. The failure is a model composing a locator from the passage's own words, and a message that only says "wrong" invites it to compose a different sentence.

It fails open when the corpus yields no markers at all, on purpose. An empty set means "we do not know what is valid here", and rejecting every citation of a legitimate run would be far worse than letting server-side verification catch an invented one. The trigger is stated and tested.

`instructions.GroundedTask` is the base class all six tasks share. The check needs a per-run value, which a class-level tool list composed at import time cannot hold: `arun` captures the corpus before the model can cite anything, and the validator is built per instance from `output_model`. This removed six identical `__init__` methods and six class-level tool lists, six chances for one task to get a weaker validator.

As a result, `Task.tools` is empty at class level. Tests that checked invariant 1 against that class attribute, together with `rlm_harness.testing.assert_repl_safe`, would pass against nothing, so they construct an instance instead, which makes them stronger.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
