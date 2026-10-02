# Invariant 83: A capture's title and tags are the reader's once they set them

**A capture's body is never editable, but its title and tags are labels for finding it, and the reader may set both (`PUT /horizon/{id}/title`, `PUT /horizon/{id}/tags`, `horizon.edit_node`). An edit records the field in the row's `edited`, and the summary pass writes through `update_node(respect_edits=True)`, which leaves every edited field alone.**

## Why the body stays fixed and the labels do not

The stored text is what every citation and every summary is checked against, so it is the source of truth and nothing in the interface changes it. The title and the tags are different in kind: the summary pass chose them for the reader, the way a browser names a bookmark after the page, and without an edit an odd tag the model picked could never be removed.

## Why the summary has to defer, even before it has run

A capture can be renamed while it still waits for its summary, and the summary pass writes a title and tags of its own. Without the rule, the pass would overwrite the reader's name a few seconds or a few days later. The check runs inside the same `BEGIN IMMEDIATE` transaction as the write, so an edit made while the model was thinking is still respected. Only the summary pass asks for this; every other writer is unaffected.

## What an edit is, and is not

- No model call (invariant 80) and no new text: the same cleaning applies to a typed tag as to the model's (`distill.clean_tags`), so `Rust` joins `rust` and the alias table, filters, lenses and the knowledge graph see one tag.
- Renaming refuses an empty name rather than deriving one, as renaming an orbit does (invariant 53).
- Growing the tags past the summary pass's own cap is refused rather than cut, so nothing typed disappears; removing is always allowed.
- Every write moves `updated_at`, which is what the full-text and vector indexes resync on. That is also why the trail dates a summary by `distilled_at` and never by `updated_at`.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
