"""PDF ingestion: per-page text via `pypdfium2`, with hybrid OCR (`_ocr.py`) for scanned pages.

AGENTS.md invariant 7: a page whose text layer extracts to (near-)nothing is rendered to an image
and dispatched to a locally-installed OCR backend (RapidOCR primary, Tesseract fallback — core
`dependencies` in pyproject.toml, always installed by a plain `uv sync`, not an opt-in extra).
`pypdfium2` (BSD-3-Clause/Apache-2.0, wraps Google's PDFium) replaces this project's former
`pymupdf`/`pymupdf4llm` dependency, which was dual-licensed AGPL-3.0-or-Artifex-commercial — see
the pymupdf-replacement design record for the full account of why that had to go.
"""

from __future__ import annotations

import logging
import threading
from typing import NamedTuple

import pypdfium2 as pdfium

from ..schema import Source, SourceBlock
from ._ocr import ocr_image, scoreable_tokens, wordlike_ratio

#: A page's own text layer below this many stripped characters has nothing to compare and goes
#: straight to OCR. Literally 1, i.e. no text layer at all: this is the MISSING-layer test only.
#: pymupdf4llm's former ML classifier also caught a GARBLED-but-present layer; `_page_text` handles
#: that case separately now (invariant 74), and the two conditions stay distinct because one has no
#: alternative to weigh and the other has two readings to choose between.
_MIN_TEXT_CHARS = 1

#: Scale factor for rendering a textless page to an image before OCR — 2x roughly matches
#: pymupdf4llm's own former default of ~144-200 DPI at typical page sizes, verified to produce
#: OCR-legible output against a real rendered page during this feature's design.
_OCR_RENDER_SCALE = 2.0

#: A page whose text layer scores below this on `_ocr.wordlike_ratio` is SUSPECTED of having decoded
#: badly, and is OCR'd as well so the two can be compared (invariant 74). Not a verdict: it only
#: decides whether to spend the OCR. Measured — good documents' worst pages scored 0.79-0.99 while a
#: real scan's mis-decoded pages scored 0.63-0.80, so the two populations overlap and no threshold
#: can separate them. That is exactly why the decision is made by COMPARING afterwards.
_SUSPECT_TEXT_BELOW = 0.85

#: ...and the OCR result has to beat the text layer by this much to replace it. A bare `>` flipped a
#: perfectly good page on a rounding-level difference in testing. Measured margins on genuinely
#: mis-decoded pages were +0.20 and +0.27; the one page where the layer was fine lost by 0.06.
_OCR_REPLACES_TEXT_BY = 0.10

#: ...and it has to have READ a comparable amount of the page. Both scores are RATIOS with no
#: volume term, so without this a page of prose carrying one garbled figure block could be replaced
#: wholesale by an OCR pass that recovered only the caption — scoring 1.0 on nine words against 0.68
#: on ninety-two. Measured token shares: the two pages a real scan genuinely needed replaced scored
#: 0.39 and 0.45, a diagram page that must keep its layer scored 0.03, and the constructed
#: prose-for-a-caption loss scored 0.10. **The separation is narrow and cannot be tightened**: a
#: garbled layer fragments into MORE tokens than a clean OCR of the same page, so a high share is
#: exactly what a true replacement does NOT look like.
_OCR_MIN_TOKEN_SHARE = 0.25


#: Second-opinion OCR is the one thing here that can make ingestion take minutes longer than the
#: caller expects, and it is invisible from the outside — the text simply arrives late. Measured on
#: a 260-page scan: 61 pages suspected, so roughly a quarter of the document paid a full OCR pass on
#: top of reading its own text layer. `uvicorn` configures the root logger, so this surfaces in the
#: server's normal output with no setup, the same way the trace sweep's line does (invariant 34).
_log = logging.getLogger(__name__)


class _PageText(NamedTuple):
    """One page's text plus what it cost to decide on it — `parse_pdf` reports the totals so a slow
    ingestion has a stated reason rather than looking like a hang."""

    text: str
    second_opinion: bool
    """An OCR pass was spent weighing this page's text layer against a fresh reading."""
    replaced: bool
    """...and the fresh reading won."""


def _page_text(page) -> _PageText:
    """One page's text: its own layer when that is usable, OCR when it is not (invariants 7, 74).

    Two different conditions reach OCR here. A page with NO text layer has nothing to compare and
    OCR is simply the only source. A page WITH a text layer that reads like mis-decoded glyphs is
    OCR'd as a SECOND opinion, and the better of the two is kept — the text layer stays unless OCR
    clearly beats it, because a good text layer is better than any OCR of the same page and a
    suspicion is not evidence."""
    text = page.get_textpage().get_text_range().strip()
    if len(text) < _MIN_TEXT_CHARS:
        # No text layer: OCR is the only source, not a second opinion, and its cost is unavoidable.
        return _PageText(ocr_image(page.render(scale=_OCR_RENDER_SCALE).to_pil()).strip(), False, False)

    layer_score = wordlike_ratio(text)
    if layer_score is None or layer_score >= _SUSPECT_TEXT_BELOW:
        return _PageText(text, False, False)
    ocr_text = ocr_image(page.render(scale=_OCR_RENDER_SCALE).to_pil()).strip()
    ocr_score = wordlike_ratio(ocr_text)
    if ocr_score is None or ocr_score < layer_score + _OCR_REPLACES_TEXT_BY:
        return _PageText(text, True, False)
    if scoreable_tokens(ocr_text) < scoreable_tokens(text) * _OCR_MIN_TOKEN_SHARE:
        return _PageText(text, True, False)
    return _PageText(ocr_text, True, True)


#: Serialises every PDF parse in this PROCESS. AGENTS.md invariant 3 says ingestion is serial and
#: measured the cost of ignoring it — four PDFs parsed concurrently died with `rc=134` (SIGABRT),
#: because `pypdfium2`'s own metadata says "PDFium is inherently not thread-safe".
#:
#: **That invariant's argument is written about `ingest_new`'s internal loop, and the API reaches
#: this function by a path it does not consider.** `api.add_sources` and `api.upload_source` both
#: call ingestion through `asyncio.to_thread`, which hands the work to the default
#: `ThreadPoolExecutor` — so two concurrent requests parse two PDFs at the same time. MEASURED:
#: two `POST .../sources/upload` fired with `asyncio.gather` against the real ASGI app overlapped
#: inside the parser by 0.405s on two distinct threads, and both returned 200. It is worse here
#: than in the loop the invariant was written about, because ingestion runs in the API PROCESS and
#: not in a `worker.py` subprocess (invariant 21 is about RLMTask EXECUTION, and parsing is not a
#: task), so the SIGABRT takes the server down rather than one request.
#:
#: **Here rather than around `ingest_one`, deliberately.** Invariant 3 already says the honest
#: thing about the wider change: "the waiting is the network FETCH and the crashing is the PDF
#: PARSE, but `ingest_one` fuses them, so separating them is a real refactor." A lock around
#: `ingest_one` would serialise the fetch too, and `web._default_fetcher` has a 15-second timeout —
#: one slow page would block every other capture for up to fifteen seconds. This is not that
#: refactor; it is a mutex on a library that documents itself as thread-unsafe, at that library's
#: door. It covers the OCR dispatch too, which is inside `_page_text`.
#:
#: **The cost it DOES pay, named because invariant 3's own standard is to name the trade.** OCR runs
#: under this lock, and `_ocr._try_rapidocr` constructs a fresh `RapidOCR()` per page. A long scanned
#: PDF therefore holds a process-wide mutex for minutes while every other upload's `to_thread`
#: worker waits behind it. That is accepted: the alternative measured in invariant 3 is SIGABRT, and
#: a slow upload is a better outcome than a dead server. It is also why `intake.py`'s queue exists —
#: captures that go through it are serial by design and never contend for this at all.
_PDFIUM_LOCK = threading.Lock()


def parse_pdf(path: str, source_id: str) -> Source:
    """Ingest a PDF. Each page becomes one citable `SourceBlock` at locator `"page:<n>"`
    (1-indexed). A page with no extractable text (OCR included) is skipped, not emitted as an
    empty block; the whole source is refused only if EVERY page comes back empty.

    Serialised process-wide by `_PDFIUM_LOCK` — see its comment for the measurement and for why the
    lock is here and not around `ingest_one`."""
    with _PDFIUM_LOCK:
        return _parse_pdf_locked(path, source_id)


def _parse_pdf_locked(path: str, source_id: str) -> Source:
    pdf = pdfium.PdfDocument(path)
    try:
        blocks: list[SourceBlock] = []
        second_opinions = replaced = 0
        for page_number, page in enumerate(pdf, start=1):
            page_text = _page_text(page)
            second_opinions += page_text.second_opinion
            replaced += page_text.replaced
            if page_text.text:
                blocks.append(SourceBlock(locator=f"page:{page_number}", text=page_text.text))
        if second_opinions:
            # Only when it actually happened — an ordinary PDF must not log a line saying nothing.
            _log.info(
                "%s: %d of %d page(s) had a suspect text layer and were OCR'd for comparison, "
                "%d replaced (invariant 74)",
                path,
                second_opinions,
                len(pdf),
                replaced,
            )
    finally:
        pdf.close()
    if not blocks:
        raise ValueError(f"no extractable text in {path!r}, even with OCR")
    return Source(id=source_id, kind="pdf", origin=path, blocks=blocks)
