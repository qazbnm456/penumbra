# Invariant 3 — Ingestion is host-side and serial

**Ingestion is host-side only AND SERIAL — never inside the sandbox, never in a thread pool.** `parsers/{text,web,pdf,youtube}.py`
and `parsers/_ocr.py` all run before any `RLMTask` exists. `pypdfium2`, `trafilatura`, `yt-dlp`
and the OCR backends are native/C-extension dependencies unsuited to the pyodide/deno sandbox —
and untrusted parsing logic has no reason to run inside the same trust boundary as the model's
own code anyway. `corpus.py` only ever hands the RLM a plain string, already parsed.

**`ingest.ingest_new`'s plain `for` loop is load-bearing, and it looks exactly like an easy win.**
Each source is a network round trip, so a serial loop spends the sum of every wait when the
longest would do, and the sources are independent by construction (the caller handed us a list) —
the case for a `ThreadPoolExecutor` writes itself. It was written, measured, and it CRASHES:
four PDFs ingested concurrently died with `rc=134` (SIGABRT; an earlier attempt `rc=139`,
SIGSEGV), because `pypdfium2`'s own metadata says so in as many words —
*"PDFium is inherently not thread-safe"* (`pypdfium2-5.12.1.dist-info/METADATA:1066`). That
constraint arrived with the dependency invariant 7 chose and nobody had written it down here.

**The measured upside was near zero on the path that crashes**: five HTML sources went 7.55s to
2.85s, but four ordinary PDFs parse serially in 0.41s — `api.py`'s "can take minutes" describes
OCR on SCANNED pages, one branch of PDF ingestion, not the text-extraction path. So the workload
the saving was supposed to scale on is the one where the saving is nearly zero and the risk is a
hard crash.

**A green suite proved nothing, and that is the transferable part**: `tests/test_ingest.py`'s
multi-value cases all take local TEXT files through `parse_text`, so nothing in 614 passing tests
drove two PDFs at once. **A suite that is green on the path you did not change is not evidence
about the path you did.**

A sound version is NOT ten lines: the waiting is the network FETCH and the crashing is the PDF
PARSE, but `ingest_one` fuses them, so separating them is a real refactor of the ingestion
dispatch — a different proposal with a different cost, and not one a 2.94% measurement buys.

## The HTTP API reached this by a path the argument above never considered

Everything above is about `ingest_new`'s internal loop. Nothing in it considers two concurrent
HTTP REQUESTS — and `api.add_sources` and `api.upload_source` both call ingestion through
`asyncio.to_thread`, which hands the work to the default `ThreadPoolExecutor`. So two requests
parse two PDFs at the same time, which is the forbidden shape arriving through the front door.

**Measured, because this invariant's own standard is measurement:** two
`POST /notebooks/{id}/sources/upload` fired with `asyncio.gather` against the real ASGI app
overlapped inside the parser by **0.405s on two distinct threads**, and both returned 200.

It is worse here than in the loop this invariant was written about. Ingestion runs in the API
PROCESS, not in a `worker.py` subprocess — invariant 21 is about `RLMTask` EXECUTION, and parsing
is not a task — so the SIGABRT takes the whole server down rather than one request. The comment
beside that call site says ingestion sits outside the per-notebook write lock because "there's no
reason for ANY ingestion to sit under the lock"; that is correct about the WRITE lock and does not
address this, since two different notebooks take two different locks anyway.

**The fix is `parsers/pdf.py`'s `_PDFIUM_LOCK`, and where it sits is the decision.** Around
`parse_pdf`, not around `ingest_one`: a lock on `ingest_one` would serialise the FETCH too, and
`web._default_fetcher` has a 15-second timeout, so one slow page would block every other capture
for up to fifteen seconds. That is not the fetch/parse refactor declined above — it is a mutex on a
library that documents itself as thread-unsafe, placed at that library's door. It covers the OCR
dispatch too, which is inside `_page_text`.

**Two tests, and the second one is the point.** `test_two_threads_cannot_parse_two_pdfs_at_once`
proves the lock; `test_api.py::test_two_concurrent_uploads_never_parse_two_pdfs_at_once` drives the
real ASGI app, because of this invariant's own closing line — *a suite that is green on the path
you did not change is not evidence about the path you did.* Both were confirmed to FAIL with the
lock removed.

---

One-line index: [`AGENTS.md`](../../AGENTS.md) · Incidents, measurements and superseded drafts: [`CHANGELOG.md`](../../CHANGELOG.md)
