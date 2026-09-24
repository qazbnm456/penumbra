# Invariant 49: answer_span is the model pointing at its own prose

**`Citation.answer_span` is the model pointing at its own prose, and it exists because locating the highlight by `quote` stopped working.**

The highlight used to find its place with `answer.indexOf(citation.quote)`, which works only while the answer and the source share a language. Invariant 39 made the prose follow the reader while the quote stays in the source's words, so the two stopped sharing any substring. That is the cost of invariant 39, paid here rather than by weakening the verbatim-quote rule.

`citations.locate_answer_spans` applies invariant 5's existence check to the model's own text. A span that does not occur verbatim in the prose is dropped, and the citation survives. Losing a highlight costs the reader one affordance, while highlighting the wrong sentence would tell them a claim is supported when it is not. Matching is exact apart from leading and trailing whitespace, with no case folding, punctuation normalisation or fuzzy matching, because each would buy a few more highlights at the price of sometimes underlining prose the citation does not support. It checks where, never whether.

`_citation_responses` takes the prose to check against as a required argument, and every call site passes the text that artifact actually renders: a chat answer, an FAQ item's `answer`, a timeline event's `description`, a podcast utterance's `text` or the overview's `text`. An empty default that skipped validation is no longer possible. Passing the wrong text is still silent (the page renders with no marks), which a dedicated test pins.

The span also orders the numbering. The interface numbers citations in the order the reader meets them in the prose, using `answer_span`, on every surface that renders marks; a citation without a span keeps its position.

`CITATION_RULES` teaches `answer_span` as the mirror of `quote`: `quote` is in the source's language and `answer_span` in the model's. Whether the model emits a usable span is a compliance claim, with the same caveat as invariants 4 and 11.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
