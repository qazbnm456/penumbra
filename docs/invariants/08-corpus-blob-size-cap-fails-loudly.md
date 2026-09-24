# Invariant 8: The corpus size cap fails loudly

**`corpus.py` caps the size of the assembled blob and fails loudly past it.**

The design hands the whole corpus to the REPL as one variable, and the Pyodide/Deno sandbox has a real memory ceiling. The cap turns what would otherwise be a mysteriously slow or failing chat turn into a clear error.

Two gaps are known. `Corpus.blob()` concatenates every source in full before it checks the length, and the check fires when a question is asked, not at ingestion (`max_chars` defaults to `None`, and only the `ask`, `guide` and `audio` paths pass it). Closing either gap means assembling the blob on every source add, so they are one follow-up, not two.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
