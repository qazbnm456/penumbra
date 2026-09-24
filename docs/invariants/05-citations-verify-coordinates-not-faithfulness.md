# Invariant 5: Citations verify coordinates, not faithfulness

**`citations.py` verifies that a coordinate exists, never that the content is faithful.**

It confirms that a claimed `source_id` exists and that its `locator` resolves to real text in the corpus. It does not confirm that the prose around the citation represents that text faithfully. No docstring, log message or UI string may imply the stronger guarantee; that gap is the "grounded but not verified" failure found in NotebookLM itself.

A citation that fails verification is marked unverified. It is never silently dropped and never silently trusted, and the label travels with it into Copy, Export and print.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
