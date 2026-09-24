# Invariant 44: The transcript is subtitles timed by the provider

**The podcast transcript behaves like subtitles, and its timing comes from the provider rather than from measuring the audio.**

`TTSProvider.synthesize` returns each utterance's start offset in seconds. The unit is the contract between every provider, `Podcast.offsets` and the seek handler in `app.js`, so it is stated rather than inferred. Every provider synthesises utterance by utterance and already knows these numbers; parsing MP3 frame headers to recover them would be a second, worse implementation.

`Podcast.offsets` is a list parallel to `utterances`, never a field on `Utterance`, because `Utterance` is the model's output and the model has no idea how long its words take to say.

The consumer checks that offsets increase, not only that the length matches. A provider that reports no boundaries yields `[0.0, 0.0, ...]`, exactly as long as `utterances`, which would stamp every line `0:00`, highlight one row for the whole episode and send every click to zero. `app.js` requires finite, non-negative, strictly increasing offsets and a matching length; anything else, including an episode stored before offsets existed, gets a plain transcript. Misaligned subtitles are worse than none.

edge-tts is matched on any `*Boundary` event, not `WordBoundary`, because the installed version defaults to sentence boundaries and emits only those. The boundary sum approximates each utterance's duration (measured error between -0.049s and +0.066s, with no consistent sign), which is fine for highlighting and does not drift in one direction.

A provider that holds raw samples gets its offsets from a pure function, `tts.sequence_offsets`, which charges the gap between utterances to the line before it, so each offset is where its own line's audio starts. Keeping this bookkeeping out of `synthesize` lets CI check it without the extra, a model download or any audio. Both offset tests use three different durations, because with equal ones a running-total bug and a correct implementation produce the same list.

## The transcript in the page

`.btn` sets `color: inherit`, `text-decoration: none` and `display: inline-block` because it is also used on an `<a>`, which the global reset does not cover. The `display` would enrol the class in invariant 36's tripwire the moment a `.btn` is toggled with `hidden`, so `.btn` carries its own `[hidden] { display: none }` in advance.

A timed transcript scrolls in its own box (`.podcast-transcript.is-timed`), and the follower sets `scrollTop` directly rather than calling `scrollIntoView`, which scrolls every scrollable ancestor and would drag a listener who scrolled away back to the podcast every few seconds. Positions come from `getBoundingClientRect`, not `offsetTop`, so the arithmetic survives the box no longer being positioned.

Clicking a line seeks to it, unless the click was meant for something inside it: `.citation`, `.reference-link` (the "N references" control) or `.podcast-timecode`. A click that ends a drag-selection also does not seek. The `play()` promise is caught, so a cleared file is a silent no-op rather than an unhandled rejection. A `.is-seekable:hover` rule must not touch any property `.is-speaking` sets; hover declares `border-color`, and `.is-speaking` uses `background` and `box-shadow`, so the two never compete.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
