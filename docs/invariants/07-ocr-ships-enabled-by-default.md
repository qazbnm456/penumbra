# Invariant 7: OCR ships enabled by default

**OCR ships enabled by default, not merely pluggable and off.**

`parsers/pdf.py` extracts each page's text with `pypdfium2`. A page with no text layer (below `_MIN_TEXT_CHARS`, which is 1) is rendered to an image and sent to the hybrid OCR in `parsers/_ocr.py`: RapidOCR first, Tesseract as the fallback, both Apache-2.0 and CPU-only. The backends are core dependencies, so a plain `uv sync` installs them. `pytesseract` is only a wrapper: the `tesseract` binary is a system dependency no Python manifest can express, and `_ocr.py` swallows `TesseractNotFoundError`, so on a machine without it the fallback is silently absent. A `vision_llm` OCR mode is a deferred follow-up.

`NotebookConfig.ocr_provider` (`RN_OCR_PROVIDER`) has no consumers. `parse_pdf` takes no config and always calls `ocr_image`; the setting is validated on read and then ignored. It is kept as the seam the `vision_llm` mode will use, so do not assume anything dispatches on it today.

## Licensing and packaging

`pypdfium2` replaced `pymupdf` and `pymupdf4llm` because their only licences were AGPL v3 or Artifex Commercial, and `pymupdf-layout` added a Polyform Noncommercial licence on top. This project is MIT and ships an HTTP API meant to run as a network service (invariant 25), which is exactly what AGPL's network clause binds. `Pillow` is a direct dependency, because `pypdfium2` declares none and `.to_pil()` had only worked through a transitive one. `tests/_pdf_fixtures.py` builds test PDFs with `reportlab`, a dev-only dependency.

The OCR distribution is `rapidocr`, not `rapidocr-onnxruntime`. It is the same upstream project, but the old name was frozen at 1.4.4 with `Requires-Python <3.13`, which made `pip install` refuse this project on Python 3.13 and 3.14. Three consequences follow:

- `onnxruntime` is declared by this project, because `rapidocr` 3.x supports six engines and pulls none of them; without it the OCR path imports fine and fails at first use.
- The shipped models are PP-OCRv6 (`det_small` and `rec_small`) plus a v2.0 classifier, inside the wheel rather than downloaded on first use, which keeps the container working with no network.
- The adapter is `zip(out.boxes, out.txts, strict=True)`. The new API returns two parallel sequences, and a plain `zip` would silently truncate to the shorter one and return a partial page as if it were whole.

The move also improved accuracy. On a rendered two-column page, 7 of 12 regions differ and the new model is right in all of them; the old recogniser dropped word spacing (`thebenchmark`), which is worse than a wrong character for citations verified by exact quote matching (invariant 5).

## What this does not cover

The OCR trigger detects a missing text layer, not a garbled one. Invariant 74 narrows that gap by comparing a suspicious page against OCR, but a layer too garbled to yield eight Latin tokens is never challenged.

## Chinese text needs no second model

The default backend is Chinese-native. On rendered text (measured on the earlier `ch_PP-OCRv4` model), Simplified scored 1.000 per paragraph and Traditional 0.879 to 0.973. PaddleOCR's `chinese_cht` recognition model was wired in and measured head to head, and it was a wash (mean 0.929 against 0.922), so it is not worth 11MB, a second OCR pass and a third-party conversion. Do not add it back without a measurement that beats this one.

Any such measurement has one trap: `PIL.ImageFont.truetype(path, size)` loads face 0 of a `.ttc` collection, and face 0 of macOS `Songti.ttc` is Songti SC, which renders nothing for Traditional-only glyphs. A first pass through that scored Traditional at 0.589 because it was measuring the font. Render the fixture and look at it before believing any OCR number.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
