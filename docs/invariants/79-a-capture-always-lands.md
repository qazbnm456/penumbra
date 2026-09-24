# Invariant 79 — A capture always lands, and intake is one worker

**Submitting something to the Inbox creates a `queued` node BEFORE anything is fetched, a parse
failure becomes a `failed` node that keeps its message, and intake runs ONE item at a time.** Three
rules, one invariant, because they all protect the same promise: throwing something in always works.

## Why the node exists before the parse does

`node_id_for` needs only the origin for a URL, so the row can be written the instant a capture is
submitted (`inbox.add_pending_node`) and the reader sees it land immediately. The alternative — a
node that appears when parsing finishes — means a spinner with nothing behind it, and a fetch can
take seconds or, on a scanned PDF going through OCR, minutes.

**A URL, and only a URL, and that is the whole rule for what a node's identity is.** The queue is
the reason: a queued capture must be identifiable before there is any content to identify it with,
and `capture_into_inbox` refuses anything that is not `is_url` before it reaches the queue, so the
set that needs an origin-only id is exactly the set that gets one. It is also right on its own
terms — a URL names a place, so a page re-captured after an edit is the same capture rather than a
second one.

**Every other origin folds the TEXT into the id, because a filename is not an identity.** Two
different files both called `notes.txt` hashed to one node: `add_node` is idempotent, so the second
found the row already there and returned it untouched, and the batch answered
`{"nodes": [A, A], "refused": []}` — the same node reported twice as two successful captures, with
the second file's bytes gone. That is this invariant broken in the one way it cannot be seen:
nothing failed, nothing was refused, so there was nothing to retry. It also silently falsified the
comment in `promote_node` that justifies its blocks-equality branch ("two DISTINCT nodes sharing an
origin necessarily differ in text"), which was simply untrue while a filename decided identity
alone.

**And landing has to survive PROMOTION, or it was not landing.** Fixing the id made two different
`notes.txt` two nodes; promoting the second into a notebook that already held the first was then a
hard refusal — "cannot be added without shadowing it" — with no way out, because nothing in this
product can rename a node or a source. The capture landed and the thing you keep it for did not.
Refusing was right about shadowing and wrong about the outcome: the answer is to disambiguate the
display origin (`notes (2).txt`), which is neither silent nor shadowing, since both sources exist,
both are citable, and the name on screen says which is which. Only the display origin moves — ids
still come from `next_source_id` and are never reused (invariant 50).

Pasted text was never affected — `ingest.ingest_pasted_text` builds `f"pasted:{snippet} #{hash}"`,
which already carries a content hash — but it now takes the same path, so there is one rule rather
than an exemption. The cost is paid once: the id VALUE changed for paste and upload, so something
captured before the fix and re-captured after it makes a second node instead of deduping.

The cost is that `Node.kind` has to be decided before anything is read. `ingest.kind_for` decides
from the origin alone, using **the same dispatch `ingest_one` uses**: a second dispatch is how a
`.pdf` URL ends up filed as `web`, and invariant 20 already draws that conclusion for this module.
For a while this paragraph was aspirational — the two functions held parallel copies of the same
four-branch chain, which is the second dispatch it warns about wearing the words that deny it.
`ingest_one` now reads `kind_for`'s answer, and a test fails if they can take different branches.

**It is a GUESS that can be wrong, by design — and this paragraph has been wrong in both
directions.** An early draft said "a URL can serve a PDF", implying a correction that did not
happen; the correction was then written out entirely ("`parse_web` hardcodes `kind="web"` and has no
content-type branch"), and that became false the moment sniffing shipped. `parse_web` reads the
content type and the magic bytes now, so a URL serving a PDF is filed `web` at capture — nothing has
been fetched, and the reader is watching for their row to land — and comes back `pdf` from the parse.
`store_blocks` overwriting `kind` is what makes the guess safe to be provisional, rather than defence against
a future `parse_web` that sniffs, and `test_kind_for_agrees_with_ingest_ones_own_dispatch` — a
tripwire in invariant 28's shape, driving the REAL `ingest_one` with recording parsers — is what
keeps the two from drifting rather than an assertion that they have not.

## Why a failure is a state and not an exception that escapes

`ingest_one` reaches trafilatura, pypdfium2, yt-dlp and two OCR backends. Any of them can raise
anything. The worker catches broadly on purpose and records
`state="failed"` with the message, because two things must both be true:

- **The capture is never lost.** It is a node the reader can see and retry; "try that again" is a
  re-submit, not a second verb, and a successful retry clears the old message.
- **The worker outlives the item.** One bad link must not end intake for everything behind it in
  the queue. A worker that dies silently turns every later capture into a permanent `queued`, which
  is the worst failure this feature can have — it looks like it is still working.

The message is KEPT rather than flattened to a boolean: a dead link and an unparseable PDF are
different problems, and a reader who cannot tell them apart cannot act on either.

## One worker, which is invariant 3 and not a performance choice

Invariant 3 measured it: four PDFs parsed concurrently died with `rc=134` (SIGABRT). Dropping a
folder or a bookmarks export is precisely the shape that would drive many at once, so the queue is
one thread with no pool. `parsers/pdf.py`'s `_PDFIUM_LOCK` is the backstop for every other caller —
see invariant 3 for the API path that needed it.

`parsers/pdf.py`'s lock is pinned by a SOURCE assertion as well as by two behavioural tests, because
both of those patch `_parse_pdf_locked` and neither would notice a new `pdfium.PdfDocument(...)`
added outside it — same class of hazard as invariants 36 and 54, with an intermittent SIGABRT as the
symptom rather than a failing assertion.

`test_items_are_parsed_one_at_a_time` asserts the windows do not overlap, and was confirmed to fail
when a second worker thread is started. That is the regression to expect: "the sources are
independent, just parallelise it" writes itself, and invariant 3 records that it was written,
measured, and crashed.

## Four ways the first draft broke its own promise, all measured

An independent review found these in code that had no caller yet. They are recorded because each
one is a shape that comes back, not because they ever shipped.

- **A node left at `parsing`.** `get_node`, the `parsing` write and `store_blocks` all sat OUTSIDE
  `_process`'s `try`, so a failure in any of the three left `state='parsing', error=None` — this
  invariant's own "worst available failure", recoverable only by a restart. Everything is inside
  the `try` now, and `_run` records a failure even for a `BaseException` `_process` did not expect,
  which is what makes "never left at `parsing`" a property of the WORKER rather than of one
  function's exception list.
- **An orphan blocks file, adopted with stale content.** A node removed WHILE its parse ran still
  got its blocks written. `add_node` adopts an orphan blocks file (that branch exists for a crash
  between the two writes), so the next capture of the same origin silently received the old text —
  measured: a re-capture with 10 characters of fresh text reported `chars=4`. Fixed in
  `inbox.store_blocks`, which deletes the file it just wrote when the row is gone: the sink is
  where this belongs, because it is the only place that knows whether the row survived.
- **A second worker, i.e. invariant 3's forbidden shape from inside the thing built to prevent
  it.** `stop()` cleared `_thread`, released `_guard`, and only then enqueued the sentinel; a
  `submit()` in that window started worker #2 (measured consequence: −0.155s between consecutive
  parse windows, real overlap). The drain and the sentinel now happen under ONE hold of `_guard`
  with `_stopping` set first, and `stop()` is terminal. 300 racing submit/stop pairs now produce
  exactly one worker thread.
- **A relative `base_dir` re-resolved on the worker thread.** `Path("inbox")` resolves against the
  process's CURRENT working directory at every syscall, and the worker outlives any single call.
  Hold a worker inside `parse`, `chdir`, release, and one node ends up SPLIT ACROSS TWO
  DIRECTORIES — the row under the old cwd, the blocks under the new one. Resolving once in
  `__init__` is also the only reading that makes invariant 34's "where you START this decides where
  your data lives" true for a thread.

Two smaller ones: `resume_interrupted` re-enqueued nodes already waiting (four parse calls for two
origins, i.e. two network fetches each), and `status()` read `qsize()`, which counts the sentinel
and reads zero between the worker's `get()` and its first state write — it reported
`{"running": False, "current": "nd-…", "pending": 1}`, denying and naming in one dict. Both now read
`_outstanding`, which is the field that is actually correct.

## Stopping tells the truth about what it can stop

`cancel_pending` drops everything still waiting and returns how many. **The item being parsed runs
to completion**, because a native PDFium parse cannot be interrupted without taking the process with
it — which is the same fact the lock exists for. So the guarantee is "nothing further starts", not
"this stops now", and `status()` names the node that is still going. Invariant 60's rule applies
here as much as to any status line: it may not claim something the system is not doing.

**Cancelled items land as `failed`, carrying "stopped before it was read", and this paragraph used
to argue the opposite.** It said they stay at `queued`, which "remains TRUE of them — nothing was
parsed, so nothing is lost", and that `resume_interrupted` picks them up later. The second half is
true only across a RESTART, which is not a thing a reader does. In the meantime a reviewer watched
three of them sit there permanently: drawn identically to a node still being read, the page polling
at 2.2 requests a second because `queued` counts as busy, no Try again offered (that is
`failed`-only), and opening one answering `404: node '...' has no stored text yet`. That is this
invariant's own headline sentence — a permanent `queued` "looks exactly like still working" — coming
true inside the file that states it. The state they land in now is terminal, visible, and retryable
through the reset `submit` already has.

`resume_interrupted` is what recovers from a crash: it resets
`parsing` rows (a state whose owning process is gone is a lie) but deliberately does NOT resume
`failed` ones. Retrying a parse that failed on its own terms, on every restart, is how a poisoned
item becomes a loop.

## Single-process, like everything else here

One queue and one worker thread per process. Two `uvicorn` workers would each get their own, and
the SQLite index underneath them is safe across processes while the queue is not — the same
documented limitation invariant 23 records for `_ACTIVE_RUNS`, stated rather than defended.

---

One-line index: [`AGENTS.md`](../../AGENTS.md) · Incidents, measurements and superseded drafts: [`CHANGELOG.md`](../../CHANGELOG.md)
