# Invariant 62: Markers are stripped at the display boundary

**A `[[SRC:...]]` marker is a coordinate for the interface and must never reach the reader. It is stripped at the display boundary, not before storage.**

Invariant 4 tells the model to echo a marker into a `Citation`; it says nothing about writing one into the sentence as well, which a real run did. Stripping on the way out means nothing stored is rewritten and every orbit already on disk is fixed with no migration; stripping on the way in would make old and new orbits disagree about their own history.

`api._prose` is the one place this happens, and the same stripped value goes to `_citation_responses`. Giving the raw text to one and the stripped text to the other fails silently either way: every `answer_span` stops matching and every citation mark disappears, invariant 49's failure one layer down. `locate_answer_spans` strips the span too, because a span copied from the model's prose can carry a marker with it.

Removing a marker leaves a hole, and the hole is closed where it is, never globally. A marker between a word and its punctuation leaves `claim . Next`, which looks wrong and is audible in synthesis. A global "no space before punctuation" rule would be wrong twice: it would change text that never had a marker (French spacing, for one), and because `strip_markers` returns marker-free text unchanged, the prose and the `answer_span` would be normalised differently and the span would stop matching. `_close_gap` is a replacement function on the marker match itself, so it can only touch the whitespace around the marker.

The prompt asks the model not to write markers into prose as well. The display strip is a safety net, not a reason to stop asking, and it makes non-compliance cost nothing.

---

**Model prose is tidied at the same boundary, by fixed rules.** `prose.polish` removes the habits a prompt does not hold back: announcing openings ("本文件為", "This document describes"), empty signposts ("總的來說", "In summary,"), dashes where a comma belongs, and ASCII punctuation between Chinese characters. It never rewrites a sentence and costs no model call. It runs in `api._prose` and on a capture's title and summary on the way out, for the same reason markers are stripped there: stored text stays what the model wrote, so every orbit already on disk reads tidied with no migration and a rule can be withdrawn without touching data. A citation's `answer_span` gets the same polish before it is located, so a highlight still lands on its words; a span that no longer matches loses its highlight and is never matched onto other words.

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
