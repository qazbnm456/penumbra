# Invariant 73: OCR reading order for two-column scans

**RapidOCR's region coordinates decide reading order (`_ocr.reading_order`); joining regions in detection order interleaves the columns of a two-column scan.**

RapidOCR reports a bounding quad per region and no layout, and it emits regions roughly line by line across the full page, so joining them in that order produced prose that jumps between columns mid-sentence. Against the same pages' own text layer, a two-column paper improved from 0.425 to 0.756 and a single-column one stayed level (0.802 to 0.792). Those figures were measured on the earlier detector; the tests assert structure and direction rather than a figure so an engine change does not invalidate them, and they still pass on the current one. The text-layer path was never affected, because `pypdfium2` reads a LaTeX two-column paper in column order already; only scanned pages without a text layer reach this code (invariant 7).

## Three rules, each falling back to the detector's own order

- A page is left exactly as detected unless it looks two-column. If more than `_MAX_SPANNING_FRACTION` (0.15) of regions cross the content's horizontal centre, nothing is touched: a two-column page crosses the centre only where something spans the measure, such as a heading, a caption or a centred page number, while a single-column page crosses it on nearly every line. Too low a value only declines to improve a page and too high reorders one that was already right, so it is set on the safe side. It was calibrated on rendered PDFs and confirmed on a real two-column scan, and controlled skew does not reach it.
- A centre-crossing region is a band boundary, never a veto. An early draft distrusted any band containing a crosser, and one centred page number cost a real page its column order. Crossers now cut the page into bands, and each band is column-split on its own.
- Within a band nothing is re-sorted; the two columns are only separated out of the detector's order. Sorting by vertical position measured worse on both layouts, because RapidOCR already emits a column's lines in order and re-sorting only disturbs near-ties such as a superscript or a skewed line. This is the counter-intuitive half, and the one most likely to be "fixed".

`_order_band` partitions rather than filtering twice, because a zero-width region exactly on the centre would otherwise land in both columns. Tesseract is not given this treatment, because it segments pages itself, columns included.

The claim is reproducible in CI in two ways. `tests/fixtures/ocr_two_column_page.json` holds 105 boxes measured from a rendered two-column page, with the text removed, and the test asserts the structure (the whole left column, then the whole right, then the centred footer) with gutter bounds taken from the measurement. Two further tests run the real OCR stack over a two-column page built from this project's own prose, and assert structure and direction, never a score. Neither replaces the synthetic cases, because the recorded page is a single band.

The known cost was inspected directly: a wide table on a single-column page can be split down the middle, and two figure pages scored slightly lower (-0.08 and -0.06). A flattened table and a scatter of figure labels are word soup under either order, so that cost is accepted against a +0.331 gain on two-column prose.

## More than two columns

More than two columns is out of scope and is declined. An odd count declines itself, because the middle column crosses the centre on nearly every line. An even count did not: a four-column page has its centre in the middle gutter, nothing spans it, and the split interleaved rows within each half. `_column_count` projects the page onto the x-axis and counts the runs separated by real gutters; above two, the page is returned in detection order. The count is taken over the whole page, never per band, because a sparse band reads its own spacing as extra gutters.

`_MIN_GUTTER_SHARE` (0.02) has about twice the margin needed: the real fixture's gutter is 0.038 of the content width. Raising it merges runs and lowers the count, which leaves two-column pages working but stops declining four-column pages.

A layout-detection model (`PicoDet-S_layout_3cls`) was evaluated and rejected: its classes are table, image and stamp, with no text class, so it cannot do the one thing that was broken.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
