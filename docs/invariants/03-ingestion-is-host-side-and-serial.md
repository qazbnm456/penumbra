# Invariant 3: Ingestion is host-side and serial

**Ingestion runs on the host and serially: never inside the sandbox, never in a thread pool.**

`parsers/{text,web,pdf,youtube}.py` and `parsers/_ocr.py` all run before any `RLMTask` exists. `pypdfium2`, `trafilatura`, `yt-dlp` and the OCR backends are native extensions that do not suit the Pyodide/Deno sandbox, and untrusted parsing code has no business running inside the model's trust boundary anyway. `corpus.py` hands the RLM a plain, already parsed string.

## Why the serial loop stays

`ingest.ingest_new` uses a plain `for` loop, and it looks like an easy win to parallelise: each source is a network round trip and the sources are independent. It was tried and it crashes. Four PDFs ingested concurrently died with `rc=134` (SIGABRT, and `rc=139` on another attempt), because PDFium is not thread-safe; `pypdfium2`'s own metadata says "PDFium is inherently not thread-safe". That constraint came with the dependency invariant 7 chose.

The gain was also small where the crash happens. Five HTML sources went from 7.55s to 2.85s, but four ordinary PDFs parse serially in 0.41s; the slow PDF case is OCR on scanned pages, which is one branch of PDF ingestion. A sound version would have to separate the network fetch (the waiting) from the PDF parse (the crash), and `ingest_one` fuses the two, so that is a real refactor with its own cost.

The broader lesson: the 614 passing tests at the time all used local text files, so none drove two PDFs at once. A suite that is green on the path you did not change is not evidence about the path you did.

## Concurrent HTTP requests

The HTTP API reached the same crash another way. `api.add_sources` and `api.upload_source` run ingestion through `asyncio.to_thread`, so two requests parse two PDFs on two threads at once. Measured against the real ASGI app, two concurrent uploads overlapped inside the parser for 0.405s and both returned 200. This is worse than the loop case: ingestion runs in the API process, not in a `worker.py` subprocess (invariant 21 covers `RLMTask` execution, not parsing), so the crash takes the whole server down. The per-notebook write lock does not help, because two notebooks take two different locks.

The fix is `_PDFIUM_LOCK` in `parsers/pdf.py`, placed around `parse_pdf` and not around `ingest_one`. Locking `ingest_one` would also serialise the fetch, and with a 15-second fetch timeout one slow page would block every other capture. The lock sits at the door of the library that documents itself as thread-unsafe, and it covers the OCR dispatch inside `_page_text` too. `test_two_threads_cannot_parse_two_pdfs_at_once` proves the lock, and `test_api.py::test_two_concurrent_uploads_never_parse_two_pdfs_at_once` drives the real ASGI app; both fail with the lock removed.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
