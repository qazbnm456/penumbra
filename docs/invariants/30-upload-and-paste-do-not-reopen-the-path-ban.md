# Invariant 30: Upload and paste do not reopen the path ban

**No upload surface reopens invariant 26's local-path ban: not `POST /notebooks/{id}/sources/upload`, not `add_sources`'s `texts`, not `/inbox/upload`, not the fetch inside `parse_web`.**

Upload is the opposite shape to a path. The server receives only bytes the caller already had, plus a claimed filename used for extension-based kind detection (`.pdf`, `.txt`, `.md` in `ingest.ingest_uploaded_file`) and for display. Pasted text has no path at all: `ingest.ingest_pasted_text` gives it a content-derived origin, a readable snippet plus a hash, because the Sources list shows the origin as its label. When a PDF upload cannot be read, the error names the uploaded file, never the server's temp path.

## The size cap is checked before the body is parsed

Declared the natural way (`file: UploadFile = File(...)`), FastAPI reads and spools the entire multipart body before the handler runs, and Starlette's `max_part_size` does not apply to file parts, so there is no framework-level limit. `upload_source` therefore takes `request: Request`, checks `Content-Length` first, and calls `request.form()` only once the length clears `config.max_upload_bytes()` (`RN_MAX_UPLOAD_BYTES`, 50MB by default). A missing `Content-Length` (chunked encoding) is refused with 411, because an unknown-length body cannot be bounded before reading it.

`config.max_upload_bytes()` is deliberately not a `NotebookConfig` field. `from_env()` raises `SystemExit` whenever `RN_MAIN_MODEL` is unset, which is right for `ask`, `guide` and `audio` but wrong here: uploading a source has nothing to do with whether a model is configured. Invariant 24 covers the error-handling consequence.

`parse_web` is bounded by the same cap: it reads `max_upload_bytes() + 1` bytes and refuses past it. Bytes arriving from outside in one request are the same risk whether they came from a form or from a URL, and they need the same independence from `NotebookConfig`.

## Single file here, batches in the Inbox

The notebook upload endpoint takes one file, matching its single-file input. It reads every `file` part anyway and refuses a batch with a 422 that names the count, because reading only one part used to drop the other files without a word.

Batch upload lives on `POST /inbox/upload`, where the Inbox's drop target makes several files at once the ordinary gesture. Each file and the running total are checked against the cap, and a part that cannot be parsed is reported instead of aborting the batch, so one bad file never drops the files after it. The per-file check is defence in depth: the `Content-Length` check already bounds the whole body, and the inner check stays for the day that outer bound moves.

Word, Slides and Docs native formats are deliberately not parsed.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
