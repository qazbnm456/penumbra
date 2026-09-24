# Invariant 33: YouTube ingestion is captions only

**YouTube ingestion (`parsers/youtube.py`) fetches captions only, never the video or audio stream.**

This is a deliberate scope decision: no `ffmpeg`, no Whisper, no transcription API key. A video with neither official nor automatic captions is a loud ingestion error (`CaptionError`), never a silent empty or partial source.

YouTube's terms prohibit automated access outside its own interfaces, and `yt-dlp` (a core dependency, for the same "working default" reason as invariants 7 and 15) works in the same grey area as every such tool. Fetching only captions is narrower than downloading media but not risk-free. Whoever deploys this accepts that risk, and `README.md` says so.

`CaptionError` subclasses `ValueError`. `cli._prepare` and `api.add_sources` both catch ingestion failures as `except (FetchError, ValueError, OSError)`, so a bare `RuntimeError` would surface a captionless video as a raw 500. `test_api.py::test_add_sources_reports_422_not_500_on_a_captionless_youtube_video` pins this. A future ingestion error needs a base class inside that tuple, or both call sites need updating.

## Parsing captions

`_parse_vtt` turns every non-blank line into its own `(start, text)` entry, one per line rather than one per cue, and leaves all deduplication to `_dedupe_consecutive`. Classifying cues was tried twice and failed on real automatic captions both times: a rolling cue that adds exactly one word carries no `<...>` tag, so tag-based classification misreads it. Per-line entries avoid classification altogether. A transition cue's settled line always repeats a line the previous cue already emitted, so adjacent dedup collapses it, while both lines of a real two-line cue are new and survive; `_chunk` joins them back up.

Ending a cue and extracting text use two different notions of blank. Real automatic-caption VTT uses a single-space line inside a cue's payload, so the cue ends only on an exactly empty line (`lines[i] != ""`), while text extraction treats whitespace-only content as blank. The fixtures in `tests/test_parsers_youtube.py` are real captured dumps for this reason.

Locators are `"ts:<mm:ss>"`, widening to `"ts:<h:mm:ss>"` past one hour, over fixed 120-second windows (`_CHUNK_SECONDS`), alongside `"whole"` for text and web and `"page:<n>"` for PDF. Neither `citations.py` nor `CITATION_RULES` parses a locator, so a new prefix breaks nothing.

`_fetch_caption_track` reuses the hardened `_opener` from `parsers/web.py` instead of an unguarded fetch. The caption URL comes from YouTube's own `timedtext` API rather than from untrusted content, so invariant 2's threat does not really apply, but reusing the opener costs nothing and removes the residual risk. `youtube.py` also imports `web.allow_nets` (invariant 76); that second shared point is deliberate.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
