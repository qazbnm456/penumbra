# Invariant 79: A capture always lands, and intake is one worker

**A capture always lands: submitting creates a `queued` node before anything is fetched, a parse failure becomes a `failed` node that keeps its message, and intake (`intake.py`) runs one item at a time.**

The three rules protect one promise: throwing something in always works.

## The node exists before the parse

A URL's node id needs only the origin, so the row is written the moment a capture is submitted (`horizon.add_pending_node`) and the reader sees it land at once. A node that appeared only after parsing would mean a spinner with nothing behind it, and a fetch can take seconds, or minutes for a scanned PDF going through OCR.

Only URLs get an origin-only id. A queued capture must be identifiable before there is any content, and `capture_into_horizon` accepts only URLs into the queue, so the set that needs an origin-only id is exactly the set that gets one. It is also right on its own terms: a URL names a place, so a page captured again after an edit is the same capture. Every other origin folds the text into the id, because a filename is not an identity; two different files named `notes.txt` used to become one node, and the batch reported both as captured while the second file's content was gone. Pasted text already carried its own content hash and follows the same rule.

Landing has to survive filing too. Two files named `notes.txt` are now two nodes, and filing the second into an orbit that holds the first disambiguates its display origin (`notes (2).txt`) instead of refusing, since nothing in the product can rename a source. Both sources exist and are citable, and only the display origin changes; ids still come from `next_source_id` and are never reused (invariant 50).

`Node.kind` is decided before anything is read, by `ingest.kind_for`, the same dispatch `ingest_one` uses. `ingest_one` reads `kind_for`'s answer, and `test_kind_for_agrees_with_ingest_ones_own_dispatch` drives the real `ingest_one` with recording parsers and fails if the two ever take different branches; a second dispatch is how a `.pdf` URL ends up filed as `web`. For a URL the kind is a guess by design: `parse_web` reads the content type and magic bytes, so a URL serving a PDF is filed as `web` at capture and comes back as `pdf` from the parse, and `store_blocks` overwrites the kind with the parsed one.

## A failure is a state, not an escaping exception

`ingest_one` reaches trafilatura, pypdfium2, yt-dlp and two OCR backends, and any of them can raise anything. The worker catches broadly on purpose and records `state="failed"` with the message, because two things must hold:

- The capture is never lost. It stays visible and can be retried; a retry is simply a re-submit, and a successful one clears the old message.
- The worker outlives the item. One bad link must not stop intake for everything behind it. A worker that died silently would leave every later capture permanently `queued`, which looks exactly like still working.

The message is kept rather than reduced to a boolean, because a dead link and an unparseable PDF are different problems, and a reader who cannot tell them apart cannot act on either.

The worker enforces this as a property of itself, not of one function's exception list: everything from reading the node to storing its blocks is inside the `try`, and `_run` records a failure even for an unexpected `BaseException`, so a node is never left at `parsing`. A node removed while its parse runs has its freshly written blocks file deleted by `horizon.store_blocks`, the only place that knows whether the row survived, so a later capture of the same origin cannot adopt stale text.

## One worker, because of invariant 3

Four PDFs parsed concurrently crashed with `rc=134` (invariant 3), and dropping a folder or a bookmarks export is exactly the shape that would drive many at once. The queue is one thread with no pool, and `_PDFIUM_LOCK` in `parsers/pdf.py` is the backstop for every other caller. The lock is pinned by a source assertion as well as two behavioural tests, because both tests patch `_parse_pdf_locked` and would not notice a new `pdfium.PdfDocument(...)` added outside it. `test_items_are_parsed_one_at_a_time` asserts that parse windows never overlap and fails when a second worker thread is started.

Three details keep that single worker single and in one place. The drain and the stop sentinel happen under one hold of `_guard` with `_stopping` set first, and `stop()` is terminal, so a `submit()` during shutdown cannot start a second worker; 300 racing submit and stop pairs produce exactly one worker thread. `base_dir` is resolved once in `__init__`, because a relative path resolves against the current working directory at every call and a `chdir` while a parse ran split one node across two directories. Progress reads `_outstanding`, not the queue size, which counts the sentinel and reads zero between the worker taking an item and marking it.

## Stopping says what it can stop

`cancel_pending` drops everything still waiting and returns how many. The item being parsed runs to completion, because a native PDFium parse cannot be interrupted without taking the process with it. The guarantee is "nothing further starts", not "this stops now", and `status()` names the node that is still going (invariant 60).

Cancelled items become `failed` with the message "stopped before it was read". Leaving them `queued` would draw them exactly like nodes still being read, keep the page polling as if busy, offer no Try again and answer "no stored text yet" when opened. `failed` is terminal, visible and retryable through the reset `submit` already has.

`resume_interrupted` recovers from a crash: it resets `parsing` rows, whose owning process is gone, and re-queues only nodes not already waiting. It deliberately does not retry `failed` nodes, because retrying a parse that failed on its own terms at every restart is how a poisoned item becomes a loop.

## Single process

There is one queue and one worker thread per process. Two `uvicorn` workers would each get their own; the SQLite index is safe across processes while the queue is not. This is the same documented limitation as invariant 23.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
