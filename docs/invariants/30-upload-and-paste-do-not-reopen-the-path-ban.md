# Invariant 30 — Upload and paste do not reopen the path ban

**`POST /notebooks/{id}/sources/upload` and `add_sources`'s `texts` field never reopen
invariant 26's local-path ban.** Upload is the opposite shape: the server only receives opaque
bytes the caller already had, plus a claimed filename used solely for extension-based kind
detection (`.pdf`/`.txt`/`.md`, `ingest.ingest_uploaded_file`) and display. Pasted text has no
path at all — `ingest.ingest_pasted_text` gives it a content-derived origin (a readable snippet
plus a hash, not a bare hash, because the Sources list renders `origin` verbatim as its label).

**The size cap must be checked BEFORE FastAPI parses the body.** Declaring the endpoint the
natural way (`file: UploadFile = File(...)`) makes FastAPI parse the ENTIRE multipart body
before the handler runs — a 5MB body is fully read and spooled to disk the instant the handler
starts — and Starlette's `max_part_size` never applies to file parts, only plain form fields, so
there is no framework-level backstop. `upload_source` therefore takes `request: Request`
directly (no `File(...)` parameter), checks `Content-Length` FIRST, and only calls
`request.form()` once that clears `config.max_upload_bytes()` (`RN_MAX_UPLOAD_BYTES`, 50MB). A
missing `Content-Length` (chunked encoding) is refused outright (411) — there is no safe way to
bound an unknown-length body before reading it.

**`config.max_upload_bytes()` is deliberately NOT a `NotebookConfig` field.** `from_env()` raises
`SystemExit` whenever `RN_MAIN_MODEL` is unset, correct for `ask`/`guide`/`audio` and a real bug
here: uploading a source has nothing to do with whether a model is configured. (See invariant 24
for the coverage gap this creates.)

**Multi-file batch upload shipped on `POST /inbox/upload`, and NOT on this file's own endpoint.**
The distinction matters and the first correction here blurred it: `POST /notebooks/{id}/sources/upload`
is SINGLE-FILE, matching its single-file `<input>`. It reads `form.getlist("file")` all the same and
**refuses a batch with a 422 naming the count**, because it used to read `form.get("file")` — which
returns the LAST part — so `-F file=@note.txt -F file=@broken.pdf` dropped `note.txt` without a word
and then answered 422 naming only the file that had failed. An independent review found it; a scope
is not a licence to keep one file and discard the rest in silence, which is the one thing this
invariant's own comment says a capture surface must never do.

The Inbox's capture surface is a DROP TARGET, where three files at once is the ordinary gesture
rather than the exception, which is why the batch BEHAVIOUR is there and only there.
`form.getlist("file")` takes every part, each file AND the running total are checked against the cap
(defence in depth — the `Content-Length` check above already bounds the whole multipart body, so
that second check is unreachable and a reviewer proved it by mutating it to `if False:` with the
suite still green; it stays for the day the pre-parse bound moves, not as a distinct case),
and a part that cannot be parsed is REPORTED rather than raised — the first version aborted the loop
on the first `ValueError`, keeping everything already stored and silently dropping everything after
it, which is the one thing a capture surface must never do.

**The fetch is bounded by this same cap.** `parse_web` reads `max_upload_bytes() + 1` bytes and
refuses past it. Bytes arriving from outside in one request is the same category whether they came
from a form or from a URL the reader pasted, and it needs the same independence from
`NotebookConfig` for the same reason.

**Deliberately not attempted**: Word/Slides/Docs native-format parsing.

---

One-line index: [`AGENTS.md`](../../AGENTS.md) · Incidents, measurements and superseded drafts: [`CHANGELOG.md`](../../CHANGELOG.md)
