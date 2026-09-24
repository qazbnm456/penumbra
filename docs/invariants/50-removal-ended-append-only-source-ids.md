# Invariant 50: Removal ended append-only source ids

**A source can be removed, so ids are no longer append-only: survivors are never renumbered and no id is ever allocated twice.**

`len(sources) + 1` was correct only while sources were append-only. Once removal existed it produced two live sources under one id, and `Corpus.get` resolved whichever it reached first, so a stored citation read the wrong text; that is what invariant 12 forbids, and the same bug `_next_note_id` fixed for notes (invariant 32).

`max(live ids) + 1` fixes only the middle of the range. Removing the highest source frees its id: `s1, s2, s3` minus `s3` would give `s3` to the next source. The citation saved against the old `s3` then reads `verified: true`, because verification checks that a coordinate exists, not that it still means the same thing (invariant 5), while opening a document that never contained the quote. That is worse than a duplicate id, because nothing looks ambiguous.

So the allocator is a high-water mark that only rises (`schema.Notebook.source_seq`), and ids may have holes; nothing reads them as a count. It is stored rather than re-derived, because the hazard reaches outside the notebook file: `api.py` drops the Inbox's `NodeMembership` rows for a removed source on the promise that its id never comes back, and `notebook.py` cannot read that store. For a notebook saved before the field existed, the first allocation recovers a mark from the source ids the file still references. That cannot see membership rows, but it covers the damaging case without a migration. A tripwire walks the schema for `source_id` and `source_ids` fields and fails if the recovery scan misses one.

Allocating and recording the mark are one operation: `next_source_id` bumps the mark itself. Leaving that to callers is how `promote_note` kept the bug after `append_sources` had been fixed. There are two append sites, and `promote_note` matters most, because promotion is the only thing that makes a note citable.

`remove_source` deletes the first match by index and raises on a miss. `mutate_notebook` writes the file unless the delta raises, so returning `False` meant a 404 still rewrote the file and bumped the modification time the picker sorts by (invariant 53).

Nothing is renumbered on removal, which is what makes removal safe to offer. A citation pointing at the removed source comes back unverified with a reason (invariants 5 and 11), on every surface at once, and stored artifacts are marked stale by invariant 38's set comparison.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
