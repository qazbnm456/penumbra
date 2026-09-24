# Invariant 54: Two web hazards only a source assertion catches

**Two more web UI hazards can only be caught by a source-tree assertion, extending invariant 36's reasoning to properties nothing else in this project can see.**

## A tooltip host must not clip its own tooltip

A `data-tip` tooltip is an `::after` on its host, so any clipping `overflow` on the host erases it, with no error and no layout shift. `test_no_tooltip_host_clips_its_own_tooltip` collects tooltip-bearing classes from the markup, from `dataset.tip` in `app.js` and from stylesheet rules that already name `[data-tip]`. A horizontal clip at the left edge is fixable without removing the tooltip: `[data-tip]::after` anchors `right: 0`, so a wide tooltip on a control at the left edge of a scroller runs off it, and the fix is to anchor into the space the control actually has (`left: 0; right: auto`).

A clipping ancestor does the same thing and is not covered, because finding one needs a real DOM. `.col` has `overflow-y: auto` (one non-visible axis forces the other to `auto`), so both tab rows anchor their tooltips to the row rather than to a tab. The collapsed Studio rail anchors to the button and opens leftward, which is safe only because `.col-studio.is-collapsed` sets `overflow: visible`. `.notebook-menu` is the other such ancestor (`overflow-y: auto`), so the picker's running-dot tooltip needed the same treatment. This file is the only record of these ancestor cases, because the test cannot see them.

## A drag threshold pair must not be inverted

A two-state toggle driven by one continuous value is stable only while the open threshold is at or above the close threshold. Setting `STUDIO_EXPAND_AT` below `STUDIO_COLLAPSE_AT` to make reopening easier creates a band where every `pointermove` flips the state. Expanding at exactly `STUDIO_MIN_WIDTH` keeps the order and opens with no jump, because at the crossing the pointer and the panel are at the same position; the dead band that leaves is covered by stretching the rail under the pointer, never by breaking the order.

Applying a width and remembering one are separate. Saving on every `pointermove` made dragging the panel closed overwrite the user's width with the minimum, so a drag is saved only when it ends, and only if it ended open. The collapsed state applies only above 1024px, where the Studio is a side column; a collapse remembered from a wide window is kept but not applied in a narrow one.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
