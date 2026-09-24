# Invariant 50 — Removal ended append-only source ids

**A source can be REMOVED now, which ended append-only id numbering — and the survivors are never
renumbered.** `notebook.next_source_id` derives from the MAX id in use; `len(sources) + 1` was
correct only while sources were append-only, and the moment removal existed it produced TWO live
sources under one id, with `Corpus.get` resolving whichever it reaches first, so a stored citation
reads the wrong text — exactly what invariant 12 forbids, and the identical bug `_next_note_id`
was written for (invariant 32) one field over.

**`max(live ids) + 1` fixed only the MIDDLE of the range, and the top of it stayed broken for
longer.** Removing a source that is not the highest leaves the max unchanged, so the old rule
happens to be right there — which is the case both tests written for this property exercised.
Remove the HIGHEST source and its id is free again: `s1,s2,s3` minus `s3` hands `s3` to the next
source added. The citation saved against the old `s3` then comes back `verified: true`, because
`citations.py` checks that a coordinate EXISTS and never that it still means what it meant
(invariant 5), while opening a document that never contained the quote. That is strictly worse than
the duplicate-id bug above: there is no ambiguity for `Corpus.get` to resolve wrongly, just a ✓
beside the wrong text.

So the allocator is a HIGH-WATER MARK that only ever rises (`schema.Notebook.source_seq`), and ids
are allowed to have holes — nothing reads them as a count or an index. It has to be PERSISTED
rather than re-derived, because the reuse hazard reaches outside this file: `api.py` drops the
Inbox's `NodeMembership` rows for a removed source on the stated promise that its id "will never
come back", and those rows live in a store `notebook.py` cannot read. For a notebook saved before
the field existed, the first allocation recovers a mark from the source ids the FILE still
references — weaker (it cannot see those membership rows) but enough to cover the case that does
the damage, and it needs no migration step. A tripwire walks the schema for `source_id`/`source_ids`
fields and fails if the recovery scan does not read one; it found a fifth field on its first run.

**The allocation and the bookkeeping are ONE operation, deliberately.** `next_source_id` bumps the
mark itself rather than leaving that to its callers — a query function with a side effect, chosen
because the alternative is the exact split that left `promote_note` reproducing this bug after
`append_sources` had already been fixed.

**There are TWO append sites.** `promote_note` appends to `notebook.sources` DIRECTLY rather than
through `append_sources`, and it is the worse of the two, because promotion is the ONLY thing that
makes a note citable — a colliding promoted note is unreachable by any citation.

**`remove_source` deletes the first match by index rather than filtering every id-equal entry, and
RAISES on a miss.** `mutate_notebook` writes the file unless the delta raises, so returning `False`
meant a 404-ing DELETE still did a full save and bumped the mtime invariant 53 made the picker's
sort key.

**Nothing is renumbered on removal, and that is what makes removal safe to offer.** A citation
pointing at the removed source comes back UNVERIFIED with a reason (invariants 5 and 11) rather
than silently resolving to a different source's text, and persisted artifacts are marked STALE by
invariant 38's set-equality comparison.

---

One-line index: [`AGENTS.md`](../../AGENTS.md) · Incidents, measurements and superseded drafts: [`CHANGELOG.md`](../../CHANGELOG.md)
