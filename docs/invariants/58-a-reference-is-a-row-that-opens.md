# Invariant 58: A reference is a row that opens

**A reference is a compact row that opens, and pointing at either end of a citation lights up the other.**

Rendering every quote as an always-visible `blockquote` let one source cited eight times fill the column. A row now shows the number, the title, a provenance chip, the use count and two clamped lines of the passage, with everything else behind a click.

Opening a citation opens its card and marks the cited words in the source passage as a `<mark class="source-quote">`, highlighted at rest. After the passage loads, the passage scrolls to the words and the Studio column scrolls them into the window, with `scroll-margin-block` so they never sit flush against the edge. A card low in the list, which is usually the newest answer's, therefore still shows its words. The source viewer, opened from a Sources row, shows the whole text with no highlight: `showSourceViewer` can centre a quote, but no caller passes one, because the card already shows the words where the reader is.

`linkReference` is the reciprocal highlight; without it a numbered mark and a numbered row are two lists the reader has to match by eye. `.is-linked` and `.is-focused` set disjoint properties (hover owns `background`, focus owns `border-color` and an inset bar), so hovering one reference never wipes the focus ring on another.

`referenceKey`'s separator is `\u001f`, because U+0000 is a trap. Every lookup is a `[data-ref-key="…"]` selector, and `CSS.escape` maps U+0000 to U+FFFD by specification, as does the CSS tokenizer, so a key joined with NUL could never match anything. The Python suite cannot reach this.

The run log is a timeline: one rail with a node per step, the current step pulsing and shown in full, earlier steps clamped and expandable. Node colour comes from the step's kind, and "current" is the animation plus a ring, disjoint properties because the two rules have equal specificity. Each row shows how long its step took as visible text, because "where is it stuck" is a question about durations, and a tooltip inside the `.run-log` scroller would be clipped (invariant 54). The first row measures from the run's start, since that gap is the wait for the model's first response. `finish()` clears `is-current`, or the last step would keep pulsing after the run has finished.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
