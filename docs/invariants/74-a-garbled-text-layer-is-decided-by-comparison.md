# Invariant 74: A garbled text layer is decided by comparison

**A garbled text layer is detected by comparing it with OCR, never by a threshold alone (`pdf._page_text`, `_ocr.wordlike_ratio`).**

Measurement ruled out a threshold on its own. Across six documents the worst scores of good pages (0.79 to 0.99) overlapped the scores of mis-decoded pages (0.63 to 0.80) on every metric tried: alphanumeric ratio, long-token ratio, dictionary hit rate and the shape score that shipped. No threshold separates them, so no threshold may decide. A false positive is not free either, because a good text layer beats any OCR of the same page.

The score only decides whether to spend an OCR pass; the comparison decides what to keep. Below `_SUSPECT_TEXT_BELOW` (0.85) the page is OCR'd as a second opinion, and the text layer stands unless OCR beats it by `_OCR_REPLACES_TEXT_BY` (0.10). A generous threshold therefore costs time, never quality. The margin matters: a bare comparison flipped a healthy page (0.97) to OCR (0.98) on a rounding-level difference, while genuinely mis-decoded pages lost by 0.20 and 0.27.

`wordlike_ratio` uses no dictionary. `/usr/share/dict/words` is missing on stock Debian, so CI cannot rely on it, and a bundled list would describe one language and condemn pages in every other. Two shape rules do the work, both taken from how mis-decoded layers read: a token with no vowel (`CNC`, `TTT`), and a token whose case flips mid-word (`BEANseGE`), with all-caps exempt because headings are real. Real garble often contains vowels, so this works in aggregate, never per token.

`None` is a real answer. Below `_MIN_SCORED_TOKENS` (8) there is nothing to judge. An unscoreable second opinion never replaces the first, which is an accepted loss on pure diagram pages. An unscoreable first opinion is never challenged, so a layer garbled down to a handful of tokens spends no OCR and stands; that is the larger remaining gap, and it is deliberate, because guessing from five tokens is how good pages get thrown away.

The protection for Chinese and other non-Latin text is a share of the page (`_MIN_LATIN_SHARE`, 0.7), not the absence of Latin text. Scoring whatever Latin happened to be present let a garbled Chinese body with a clean English reference list score 1.000 from the readable minority. `wordlike_ratio` now checks whether the rule applies before applying it, and declines below that share. `_WORD_TOKEN` and `_LATIN_CHAR` share one character-class constant, so they never disagree about what counts as Latin.

`_WORD_TOKEN` covers accented Latin letters, not just ASCII. With `[A-Za-z]`, accents split words into fragments, so correct German scored 0.824 and correct Vietnamese 0.375, while stripping the accents, which is what weak OCR does, raised both to 1.000; the metric rewarded degradation. It is not a general Unicode letter class, because CJK characters are letters too and matching them would remove the `None` that protects them.

Neither score measures volume, so `_OCR_MIN_TOKEN_SHARE` (0.25) is a separate gate. Without it, a page of prose with one garbled figure could be replaced wholesale by an OCR pass that recovered only the caption. The pages a real scan needed replaced scored 0.39 and 0.45, a diagram page that must keep its layer 0.03, and a constructed caption-only case 0.10. The margin cannot be tightened, because a garbled layer fragments into more tokens than a clean OCR of the same page.

The trigger was real: an Internet Archive scan of a 1960 monograph whose chart pages were scanned upside down or mirrored, so its embedded text decoded to strings like `UN ELTN NII PIN COCO`. The layer has characters, so the missing-layer check (invariant 7) never ran OCR. Re-OCRing those pages was expected to gain nothing, because they are charts, and it recovered `FALSE ALARM INTERVAL` and `PULSE REPETITION RATE`, because OCR reads the page as rendered.

The cost is reported, not capped: `parse_pdf` logs one line per document when any page paid for a second opinion. On the 260-page scan that motivated this, 61 pages were suspected, 4 were unscoreable and 187 were untouched, so about a quarter of the document paid a full OCR pass on top of its text layer. On the API path that work runs on a daemon thread. From outside, slow ingestion looks like a hang, which is why the line exists. It is not capped, because a page with no text layer already pays the same pass with no cap, and a cap would silently leave garbled text on whatever pages fell past it. A CLI user sees only the wait, because `uvicorn` configures logging for the server and the CLI does not; plumbing the counts back was judged disproportionate.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
