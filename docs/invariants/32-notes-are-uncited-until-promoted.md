# Invariant 32: Notes are uncited until promoted

**Notes (`schema.Note`, `Orbit.notes`) are free, uncited text, grounded and citable only once promoted into a real `Source`.**

A note may start as a copy of a grounded answer, but the note carries no `citations` and is never re-verified, so invariant 5's guarantee does not extend to it. `orbit.promote_note` is the only path from a note to `orbit.sources`, and it reuses `ingest.ingest_pasted_text` unchanged, so a promoted note gets the same content-derived origin, dedup by origin and injection scan as any paste. Promotion removes the note whether or not a source was appended (a dedup hit appends nothing), because the user's action is complete either way; the endpoint returns the full `OrbitResponse`, and a client tells the outcomes apart by comparing, not by status code.

A note id comes from the highest id among live notes, never `len(notes) + 1` (`orbit._next_note_id`). With length-based ids, deleting a note in the middle let two live notes share one id, and since deleting and promoting act by id, one action silently affected both. `delete_note` and `promote_note` also remove exactly the first matching note, as defence in depth.

`POST /orbits/{id}/notes` creates the orbit if needed (`create=True`, like `add_sources`), so a new orbit can start with a note. `DELETE .../notes/{note_id}` requires an existing orbit (`create=False`), and the web UI asks for confirmation before deleting, as it does for every other delete.

Saving as a note is offered by call sites that opt in, never by the shared `renderAnswerWithCitations`, which six places call. The `saveAsNoteButton` factory is used by a chat answer (`renderTurn`) and by the overview (`renderChatOverview`). The line follows the surface, not the author: what appears in the chat thread is the reader's to curate, while a Studio guide and a podcast transcript are not part of that thread.

---

**Keeping an answer as a moon is the same two steps in one press.** An answer's keep button adds its text as a note and promotes it at once, so it becomes a source of the orbit, and through `_record_in_horizon` a capture filed there and a moon on the map. Nothing about the rule changes: the note is still uncited and the source is still text the reader chose to keep, re-verified like any other; the press only spares the reader the second click when they already mean both.

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
