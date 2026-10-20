# Invariant 83: A capture's title and tags are the reader's once they set them

**A capture's body is never editable, but its title and tags are labels for finding it, and the reader may set both (`PUT /horizon/{id}/title`, `PUT /horizon/{id}/tags`, `horizon.edit_node`). An edit is a `said` label in the kit's memory store, and a `said` label outranks every `inferred` one the summary pass writes, before or after it.**

## Why the body stays fixed and the labels do not

The stored text is what every citation and every summary is checked against, so it is the source of truth and nothing in the interface changes it. The title and the tags are different in kind: the summary pass chose them for the reader, the way a browser names a bookmark after the page, and without an edit an odd tag the model picked could never be removed.

## Why precedence, not a guarded write

A capture can be renamed while it still waits for its summary, and the summary pass writes a title and tags of its own. The two never share a place to overwrite: each is its own row, and the kit's `current_labels` view shows a capture's latest `said` row for a kind whenever it has one, and its latest `inferred` row otherwise. So a summary landing a few seconds after a rename, or a pass run again a month later, leaves the reader's name showing, with no check to get right at write time. `edited` is read from the same rows (the kinds whose current label is `said`), which is how the card says "You named this" and the trail dates a summary by its own row (`distilled_at`), never by the last edit.

## What an edit is, and is not

- No model call (invariant 80) and no new text: a typed tag is cleaned the way the store keeps tags (`distill.clean_tags`: NFKC, casefolded), so `Rust` joins `rust` and the alias table, filters, lenses and the knowledge graph see one tag.
- Renaming refuses an empty name rather than deriving one, as renaming an orbit does (invariant 53).
- Growing the tags past eight is refused rather than cut, so nothing typed disappears; removing is always allowed.
- A capture still being read (queued, parsing, failed before its text was stored, or waiting to be stored) has no labels yet: its labels belong to its memory item, which it has once its text is stored (invariant 79). Renaming or retagging it answers 409, and the card offers neither until it has landed.
- Every edit moves the row's `updated_at`, which is what the full-text and vector indexes resync on.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
