# Invariant 62: Markers are stripped at the display boundary

**A `[[SRC:...]]` marker is a coordinate for the interface and must never reach the reader. It is stripped at the display boundary, not before storage.**

Invariant 4 tells the model to echo a marker into a `Citation`; it says nothing about writing one into the sentence as well, which a real run did. Stripping on the way out means nothing stored is rewritten and every notebook already on disk is fixed with no migration; stripping on the way in would make old and new notebooks disagree about their own history.

`api._prose` is the one place this happens, and the same stripped value goes to `_citation_responses`. Giving the raw text to one and the stripped text to the other fails silently either way: every `answer_span` stops matching and every citation mark disappears, invariant 49's failure one layer down. `locate_answer_spans` strips the span too, because a span copied from the model's prose can carry a marker with it.

Removing a marker leaves a hole, and the hole is closed where it is, never globally. A marker between a word and its punctuation leaves `claim . Next`, which looks wrong and is audible in synthesis. A global "no space before punctuation" rule would be wrong twice: it would change text that never had a marker (French spacing, for one), and because `strip_markers` returns marker-free text unchanged, the prose and the `answer_span` would be normalised differently and the span would stop matching. `_close_gap` is a replacement function on the marker match itself, so it can only touch the whitespace around the marker.

The prompt asks the model not to write markers into prose as well. The display strip is a safety net, not a reason to stop asking, and it makes non-compliance cost nothing.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
