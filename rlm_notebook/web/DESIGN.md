# rlm-notebook web UI: visual & UX spec

The web frontend's design contract. Implementation (`index.html`/`style.css`/`app.js`) follows this
file.

> **This file is prose about code, and prose about code rots.** Two independent reviews have now
> found it stale in ways nothing could catch by itself: an accent value, a control that had been
> replaced, a section count, an `alert()` that no longer exists. Where a claim here names a SELECTOR
> or a TOKEN, `tests/test_web_assets.py` can pin it and increasingly does; where it describes
> intent, it cannot. Treat a disagreement between this file and `rlm_notebook/web/` as drift in
> THIS file — fix it here rather than reasoning from it. Architecture and the full decision record (why this exists, what was audited, what's deferred)
live in `AGENTS.md` and `docs/invariants/` — this file owns *look and feel* only, the
same split `ctx-distillery/studio/DESIGN.md` established for the sibling family.

**This is NOT a replay-only trace console, unlike every sibling's `studio/`.**
`ctx-distillery`/`cve-reverser`/`diff-sentry`/`toolscout` each ship a single-verdict security/review
console: one input, one derived-state card, a live action feed, a Trajectory replay drawer. This is a
persistent, multi-notebook, multi-turn knowledge workspace instead — many notebooks, many ingested
sources, a saved chat history, human-readable output artifacts meant to be read. The divergence from
the family pattern is a recorded decision (see the blueprint's §0), not an oversight.

## 1. Theme

Warm editorial calm: ink-on-paper in Paper (light, default), a reading-lamp-at-night warmth in Study
(dark) — never the siblings' cool blue-slate security-console dark. Energy: focused, legible,
unhurried. Not playful, not corporate, not a terminal.

**Two surfaces, and the Inbox is the one you land on.** The product pivoted to a Tier 0 capture
Inbox with notebooks as curated facets below it (AGENTS.md invariants 78-80), so `index.html` holds
a top-level view switch:

- `#view-inbox` — the default. A facet rail, a capture field, a dated stream of nodes. §10.
- `#view-notebook` — the previous three-pane workspace, unchanged, reached by picking a facet.

**The aesthetic direction did NOT change in that rebuild, and that is a finding rather than an
omission.** The direction chosen in Phase 1 (ink-on-paper, Literata for reading, Public Sans for
chrome, copper accent) is the same direction the Inbox needed. Repainting it would have been
motion without a reason; what was actually missing was structural, plus one thing this file had
been describing without shipping it — see §4.

Utility mode (no marketing hero). Inbox: orient (facet rail) → capture (the field) → status (the
running strip, only while running) → read (the stream). Notebook: sources (rail) → converse (chat)
→ produce (Studio panel).

## 2. The signature: citation as highlighter stroke

A citation renders as a span (`.citation`) carrying a small superscript reference number appended by
`.citation::after { content: attr(data-reference) }`, with the 2px `--highlight-border` underline
arriving on `:hover` and `:focus-visible`. **Every clause of this paragraph has been rewritten at
least once, always in the same direction.** It first said the wash was always on and that there was
emphatically no number; the wash moved to `:hover` (an answer with nine citations was nine
highlighted bands) and the number arrived with the References panel, which needs a way to point at a
row. Then the underline inherited the problem the wash had been moved for: an independent review
measured a real overview at 1,996 characters with 16 strokes covering 1,914 of them — **95.9%** — a
solid slab that is harder to read than plain text and answers "which part of this is grounded?" with
"all of it". So the resting mark is now the NUMBER, and the stroke shows the extent of ONE claim
when you point at it or tab to it. An unverified stroke is the exception and keeps its dashed rule
at rest, because a warning that appears only on hover is not a warning.

The stroke is also OPERABLE: `tabindex="0"`, `role="button"`, Enter and Space, and a
`:focus-visible` ring. It was bound to `click` and `mouseenter` alone until an independent review
walked 37 tab stops through a notebook and reached no citation at all — SC 2.1.1 and SC 4.1.2, both
Level A, on the interaction this section calls the core of the product. The
number is the INTERFACE's, never the model's — invariant 48.5 is what keeps the model from writing a
competing one into its own prose. This is the literal visual expression of the product's core value: grounded, verifiable
text. The underline exists specifically because the wash's own luminance separation from an arbitrary
surface step is not reliably perceptible alone — verified computationally during the pre-implementation
design audit (Study mode's wash over `--surface-3` measured self-contrast ≈1.0, i.e. invisible, before
the fix) — so perceptibility never depends on the wash alone.

An unverified citation (`citations.py` could not resolve its coordinates against the current corpus)
gets a dashed `--bad`-colored underline instead of the solid accent one — flagged, never silently
dropped, the same discipline `injection_scan.py`'s flags already use elsewhere in this project.

## 3. Palette

Two full, first-class OKLCH palettes, `[data-theme="light"]` (Paper, default) and
`[data-theme="dark"]` (Study), toggled from the header, persisted in `localStorage`, seeded from
`prefers-color-scheme` on first visit — same mechanism the sibling studios already use. **Live tokens
are `style.css`'s `:root` blocks — source of truth**; the values below are design intent.

```
/* Paper (light, default) */
--bg:#f9f7f4(≈)  --surface-1..3 step down in warmth  --border / --border-strong
--text:(deep ink navy, oklch 22% 260)  --text-dim  --text-faint:(oklch 46% 260 — corrected, see below)
--accent:(copper, oklch 54% .16 55 in Paper - see below)  --highlight-wash:(warm cream wash)  --highlight-border:(oklch 62% .16 55 - NO LONGER = accent, which darkened to 54% for WCAG AA)
--studio-accent:(muted sage, oklch 55% .05 165)
--ok / --warn / --bad
```

```
/* Study (dark) — a reading lamp at night, not a security terminal */
--bg:(warm near-black, oklch 20% .015 55)  --surface-1..3 step up in warmth
--text:(warm cream, oklch 93% .015 75)  --text-dim  --text-faint:(oklch 70% 75 — corrected, see below)
--accent:(brightened copper, oklch 75% .15 55)  --highlight-wash:(oklch 50% .08 70 / .65 — corrected)
--studio-accent / --ok / --warn / --bad, same hue family as Paper for brand continuity
```

**Both `--text-faint` values and Study's `--highlight-wash` were corrected during the
pre-implementation audit** — the originals measured 3.08:1 (Paper) and 2.97:1 (Study) against
`--surface-3` (WCAG AA's floor is 4.5:1 for normal text), and the original wash was self-contrast ≈1.0
against an elevated panel. The computed values behind the fix are in `CHANGELOG.md`.

**Accent discipline** (same "do not cross-use" rule the siblings enforce): `--accent` only on
interactive elements and the citation highlighter; `--studio-accent` only inside the Studio panel,
separating "converse" mood from "produce" mood visually; surfaces step 1→2→3, never two same-tone
panels touching.

## 4. Typography

Font-selection procedure run explicitly (not a reflex pick — Fraunces/Inter/JetBrains-Mono-everywhere
were all considered and rejected first):

**THE TYPEFACES ARE NOW ACTUALLY LOADED, AND UNTIL THE INBOX REBUILD THEY WERE NOT.** `index.html`
pulled in one stylesheet and nothing else: Literata, Public Sans and JetBrains Mono were named in
`style.css` and never delivered, so every machine without them installed rendered the whole
interface in its system sans. In an ink-on-paper direction the typeface IS the identity, which made
this the largest gap between this file and the product.

They are **self-hosted** (`web/fonts/*.woff2`, 176 KB), not fetched from a CDN, for the reason
invariant 51 refuses `og:image`: a remote font makes the READER's browser call a third party on
every page load, and this app binds loopback and ships in a container verified with no network at
all. One VARIABLE file per family and style — Google serves the same woff2 for every weight, so
shipping 400/500/600 separately would have been the identical file three times. Latin
`unicode-range` only, so a Han run never waits on a download it cannot use; the CJK faces come from
the OS and are paired explicitly in `--sans` / `--serif`, Traditional first, because this
interface's own language is zh-Hant and an SC face draws Simplified forms for it. No monospace is
self-hosted: every target OS ships a good one and the mono face here carries technical texture, not
identity.

- **Literata** — content meant to be read at length, and **now used for it**: the Inbox's node
  titles, summaries and full text, and the capture field itself (§10). Its OPTICAL SIZE axis
  (7..72) is driven by `font-optical-sizing: auto`, so one file gives a display cut at heading sizes
  and a reading cut at body sizes. That axis is why the face is worth its bytes here. Reserved via
  the `.reading-face` class; NOT yet applied to Guide/
  podcast content either, since Phase 2 reused `renderAnswerWithCitations`'s existing Public Sans
  treatment for consistency with Chat rather than introducing a font switch mid-panel — worth
  reconsidering once a dedicated long-form reading surface exists. Commissioned by Google originally
  for on-screen long-form reading (Google Play Books); the one typeface actually designed for what
  this product asks a reader to do, once something actually uses it.
- **Public Sans** — all UI chrome: nav, labels, buttons, form fields, the chat turns themselves. US
  Web Design System typeface, built around clarity/accessibility/trust — thematically aligned with a
  citation-verifiable-truth product. The body default (`body { font-family: "Public Sans", ... }`).
- **A monospace stack, and NOT JetBrains Mono — which took two goes to get right.** `--mono` is
  `ui-monospace, SFMono-Regular, "SF Mono", Menlo, …` (`style.css:20`). The font was named here for
  three phases and never shipped, which is the same defect recorded above for Literata and Public
  Sans; the correction written for it was ALSO wrong, because it only checked the token. Ten live
  rules bypassed `--mono` and put `"JetBrains Mono"` first in their own family lists, so the face
  rendered for any reader who happened to have it installed and for nobody else — an inconsistency
  invisible to a developer whose machine has it. Every one of those rules reads `var(--mono)` now:
  one stack, one answer, and a `grep` that means something.
  It is used where the product echoes a developer-console reading: the reasoning ticker pill
  (`.trace-face`), the Trajectory drawer's code and payload panes, and now the technical half of
  each failure block (`.node-error-why`, `.turn-failed-why`, `.distil-error-why`).

## 5. Components

### 5.1 Header

56px, `--surface` with a blur. Left to right:

- **Wordmark** (`#new-notebook`) — a real `<button>`, not a label: it goes HOME, to the Inbox. It
  used to start an empty notebook, which did nothing at all on the Inbox itself — a dead control in
  the first tab stop. Starting a notebook lives at the foot of the facet rail.
  Needs its own chrome reset, since the global `button` rule only resets font and colour.
- **Notebook title** (`#notebook-title`) — the notebook's human name (invariant 37). Hidden when no
  notebook is open. The id is a handle the user never has to invent or read.
- **Notebook switcher** — `#notebook-current` (the current name, as a button) opening
  `#notebook-menu`, a list of notebooks BY TITLE with a source/turn count and a last-touched time.
  The id input and its `datalist` are gone: they put the handle and some machine metadata in front
  of the name, which is invariant 37 read backwards.
- **Inbox crumb** (`#inbox-home`) — the route back to the default surface, shown whenever the rail
  is not (always in the notebook view; at narrow widths in the Inbox). It is the ONLY route back at
  desktop width, so it may never be the element that shrinks.
- **`.header-actions`** (right) — the settings ⚙ (`#settings-open`, invariant 41) and the theme
  toggle. ONE wrapper owns the push-right; giving both buttons `margin-left: auto` misplaced them.

### 5.2 Sources (left rail, ~280px)
A kind-agnostic "Add source" form: URL / paste-text / file tabs (blueprint §7 — built extensible so
a future video/audio ingestion slice doesn't need a UI rework). All three are wired to the API: URL
posts to `POST /notebooks/{id}/sources` (`{sources: [...]}`, http(s) only — AGENTS.md invariant 26
stays exactly as strict; a YouTube link is ingested transparently by the SAME field, dispatched
server-side by `ingest.ingest_one` — no separate UI affordance needed, just a `<p class="hint">`
under the URL input naming that YouTube links work and are captions-only, per invariant 33),
paste-text posts to the SAME endpoint with `{texts: [...]}` (a post-launch addendum — see
`docs/invariants/30-upload-and-paste-do-not-reopen-the-path-ban.md`), and file upload POSTs
`multipart/form-data` to `POST /notebooks/{id}/sources/upload` (`.pdf`/`.txt`/`.md`, one file per
request) — never a local-path string, which is what keeps it from reopening invariant 26's
local-path ban. Below: the source list, one `.source-item` per source — kind, origin
(word-broken, never truncated into an unreadable middle; a pasted text's origin is a readable
snippet plus a content hash, an uploaded file's origin is its filename, a YouTube source's origin
is the video URL itself), and any `flags` from `injection_scan.py` shown as an amber warning line,
never hidden and never blocking (AGENTS.md invariant 6). Clicking a `.source-item` opens the
source-viewer modal (§5.7) for that source, no highlight target — a YouTube source's blocks render
there with their `"ts:<mm:ss>"` locators, the same as any other source's blocks.

### 5.3 Chat (center, fills remaining width)
Turn history, oldest first, scrolled to bottom on append. A question renders as a right-aligned
accent-filled bubble; an answer renders left-aligned in a bordered well, with citations rendered inline
per §2 plus a compact citation list below (source id + locator, a checkmark or an "unverified" flag).
SUPERSEDED by invariant 58's References panel: a citation stroke calls `focusReference`, which
expands that entry's `.ref-card`, and the source viewer opens from the SOURCES row instead. The
per-row `⌁ trace` icon is gone; `⌁` now marks the persisted steps pill only.
A pending turn (the model is still running — this is a real, potentially tens-of-seconds-long RLM
loop, invariant 21) shows LIVE, updating copy from the Phase 3 reasoning ticker (§5.5) in place of a
static "Thinking…" — the ticker is a secondary, opt-in layer; losing it (a dropped SSE connection)
never blocks the request, which remains the sole source of the final answer. An error surfaces
in place as a failed turn carrying the reason, never a silent disappearance of the question the
user just asked.

### 5.4 Studio (right rail, ~340px)
FOUR VIEWS behind one tab strip (`.studio-view-tab`): Studio, Podcast, References and Notes. The
Studio view holds its own inner strip of Guide kinds (`Summary | FAQ | Timeline | Insight`, matching
`guide/{kind}`). The two strips are the same idiom — an underline, never a filled pill — and are
separated by SIZE and weight, because at near-identical sizes neither read as the outer one. This
section used to describe three stacked sections and an "Audio Overview"; the string does not exist
under `web/` and the layout is tabs. A tab's content is fetched ONLY on first activation or an
explicit `↻ Regenerate` click — never automatically, including on notebook open — since a guide
run is a real RLM loop and re-running it for free would burn a model call for nothing; results are
cached client-side per notebook, invalidated on both a notebook switch AND a source being added (a
cached Guide result is stale the instant the corpus it was computed from changes). `summary`/
`insight` reuse `renderAnswerWithCitations` verbatim (same citation-highlighter treatment as Chat);
`faq` renders one `.guide-item` block per Q/A pair; `timeline` renders one `.guide-item` per
`{when, description}` event. Below: a `Generate podcast` button — `POST .../audio` runs a real RLM
script-generation loop THEN a TTS call in series (a NETWORK call for edge-tts, fully local for
chatterbox — invariant 43, measured at 16 MINUTES for a 3.4-minute episode), so this is by far
the single slowest
action in the product, with its own pending copy saying so — producing a HEADLESS `<audio>`
element (playing from `GET .../audio/file`, so a persisted episode replays without re-synthesis and a
multi-MB episode doesn't sit fully
base64-encoded in a DOM attribute for its whole lifetime) plus a transcript below it, one
`.podcast-utterance` per line with the same citation-highlighter treatment. Notes: see §5.8.

**The transport is ours; the element is headless.** `<audio controls>` put the browser's stock
black pill — play, slider, volume, a `⋮` overflow menu — inside this panel, and it was the last
un-themed surface in the product, on its most expensive artifact. It is also the worst one to leave
cross-platform: a Tauri build is WKWebView on macOS, WebView2 on Windows and WebKitGTK on Linux,
three genuinely different players. `.transport` is a circular `.transport-play`, a
`.transport-scrub` (a real `<input type="range">`, with `aria-valuetext` carrying the TIME because a
range otherwise announces "437") and a tabular `.transport-time`. A real button and a real range
rather than hand-rolled widgets: both are keyboard-operable and nameable for free, and
re-implementing a slider's drag/arrow/Home/End behaviour buys nothing. `preload="metadata"`, so the
duration is known before the first press without pulling the episode.

**The transcript is SUBTITLES, not a wall of text** (Post-launch addendum 6, after a user listened
to a real episode and asked for it): each line carries a `.podcast-timecode` in `m:ss` (`h:mm:ss` once an episode passes an hour),
clicking a
line seeks the `<audio>` element to it and plays, and the line currently being spoken carries
`.is-speaking` — `--studio-accent`, deliberately NOT the citation highlighter, so "where the voice
is" and "what came from a source" never read as the same signal. Highlight and scroll are driven
off the player's own `timeupdate`, so scrubbing, pausing and seeking all stay in sync for free with
no timer of our own.

The timing comes from `Podcast.offsets`, a list of per-utterance start seconds PARALLEL to
`utterances`, measured by the TTS provider at synthesis (every provider here already synthesizes
utterance by utterance, so it knows them — parsing MP3 frames to recover a number we were already
handed would be a second, worse implementation). **Anything but one strictly-increasing
offset per utterance degrades to the plain transcript** — no timecodes, no seek, no highlight.
Missing and wrong-length are the easy cases (an episode persisted before this field existed has
none); the one a LENGTH check cannot catch is one zero per line, which is exactly what a provider
reporting no boundary events returns. An independent audit simulated the length-only version:
every line stamped `0:00`, the second row highlighted for the whole episode, every click seeking to
zero. Mis-aligned subtitles are worse than none at all.

### 5.5 Reasoning-trace ticker + citation-turn detail (Phase 3; the detail half is SUPERSEDED)

Every `ask`/Guide-tab/podcast-generate call picks its OWN run id client-side (`crypto.randomUUID()`,
prefixed with the notebook id — the client, never the server, since a server-generated id would
never reach the page until the request was already over) and opens a live SSE ticker against it
alongside the actual request. While pending, the ticker's translated `{kind, summary}` events
replace the static "Thinking…"/"Generating…" copy with live-updating copy in the SAME slot — this
is not a new UI element, just a livelier version of an existing one. Once the request settles, the
ticker log collapses into a small `⌁ steps`
pill (`.ticker-toggle`). **Superseded**: that pill no longer expands a plain-text log in place
(`.ticker-detail` and its CSS are gone). It opens the Trajectory drawer for the run, which carries
the same trace with the code each turn ran, the tool calls and real per-turn timing. Recorded here
rather than rewritten, because this file is the Phase 3 design record and the change came later.

**Superseded, the same way and for the same reason as the paragraph above.** Every citation span
with a known run id becomes clickable (`.citation-clickable`, which is still live) and it used to
call `GET .../citation-turn` and fill a single shared `.citation-detail` slot per answer with the
raw trace-event payload, monospaced. That slot is GONE — `.citation-detail` and
`.citation-detail-payload` appear nowhere in `app.js`, `style.css` or `index.html`, and nothing
under `web/` fetches `citation-turn` any more. A click now opens the References panel (invariant
58), where the passage is a row that expands. The endpoint survives with no client; `api.py` says
so itself.

What has NOT changed is the limit that paragraph existed to state: this shows WHERE the model read
the source, never a faithfulness proof (AGENTS.md invariant 5, restated in the UI rather than left
for it to imply something stronger). A turn with no `run_id` (saved
before this field existed) simply has no clickable citations — a graceful, silent degradation, not
a broken link.

### 5.6 States
| state | what shows |
|---|---|
| no notebook opened | Sources: empty-note. Chat: empty-note. Studio: "pick a tab" prompt, no podcast section content. |
| notebook opened, no sources | Sources: empty-note under the add-source form. Chat: empty-note. |
| notebook opened, sources but no turns | Sources: list. Chat: empty-note ("ask a question…"). |
| a question in flight | Chat: the question bubble + a "Thinking…" pending answer; ask form disabled. |
| ask fails | Chat: the question bubble + a FAILED turn — its own bordered, tinted block with a heading and the reason in the mono face, never the ordinary answer bubble with an `(error)` prefix. The failure carries no save-as-note control: a note promotes into a citable `Source` (invariant 32), and an exception must not become one. |
| a Guide tab generating | Studio: "Generating…" in muted italic where the content will render. |
| a Guide tab's sources produced nothing (empty FAQ/timeline) | Studio: an explicit "(no … — the sources didn't produce enough to …)" message, never a blank body. |
| a Guide fetch fails | Studio: an inline error line in the tab body. |
| podcast generating | Studio: "Generating script and synthesizing audio — this can take a while…" in muted italic; the Generate button is disabled. |
| podcast script has no utterances | Studio: "(no podcast script — the sources didn't produce enough to discuss)", no player. |
| podcast generation fails (script OR synthesis) | Studio: an inline error line; the Generate button re-enables. |
| a run in flight, ticker connected | The pending slot's copy updates live from translated trace events instead of staying static. |
| a run's ticker drops (SSE error/close) | The pending slot simply stops updating — the request itself is unaffected and still resolves normally. |
| a completed turn/tab/episode with a known run id | A `⌁ steps` pill appears; clicking opens the Trajectory drawer (invariant 70) — it no longer expands an inline log, and it carries no count. On a run that produced no trace it RETIRES in place rather than raising a dialog. |
| a citation activated — clicked, or Enter/Space with it focused (run id known) | The Studio switches to References and the matching card opens at that quote. The "shared detail slot below the answer" this row used to describe is gone from the tree entirely (§5.5), along with `.citation-detail`, which matches nothing under `web/`. |
| a citation clicked (no run id — a pre-Phase-3 saved turn) | Nothing — the citation simply isn't clickable, no broken affordance shown. |
| a citation row or source item clicked | The source-viewer modal opens with "Loading…", then the source's full text. It does NOT highlight a block: both call sites pass `(source.id, null, null)`, so `showSourceViewer`'s highlight branch is unreachable and its `locator`/`quote` parameters are dead. The closed loop is delivered by the reference card instead, which fetches the source and highlights the quote in place. |
| the source viewer's fetch fails | The modal body shows an inline error message; the modal itself stays open (closable normally). |
| the source viewer is closed and reopened for a different source before the first fetch resolves | The first fetch is aborted; only the second open's response ever renders. |
| notebook opened, no notes | Notes section: empty-note under the add-note form. |
| a note added (manually, or via "+ Save as note") | Notes section: the new `.note-item` appears in the list; the add-note textarea clears on success. |
| a note promoted to a source | It disappears from Notes and a new item appears in Sources — both re-rendered from the same response; if the text was already an identical source, only the note disappears (no duplicate source). |
| a note deleted | It disappears from the Notes list; no confirmation prompt (matches every other non-destructive-feeling list-item removal in this UI). |
| a note action (promote/delete) fails | An inline notice (`notify()`, `#notices`) names the error and the button re-enables. `alert()` is gone from this application — it cannot be styled, it blocks the renderer, and in the planned Tauri shell it becomes an OS modal over the window. |

### 5.7 Source viewer modal (Post-launch addendum 2)

NotebookLM's most basic closed loop: click a citation, see the highlighted original passage — not
just the reasoning trace. The first stacking-context component in this codebase's `web/`
(`.modal-overlay`/`.modal`, an explicit `z-index` rather than relying on paint order), opened from
a citation-list row (§5.3, with a highlight target) or a `.source-item` (§5.2, no highlight
target). Fetches `GET /notebooks/{id}/sources/{source_id}` and renders every block as a labelled
`.source-block` section. **The highlight this paragraph described is not wired up**: both call sites
pass no locator and no quote, so the branch that would highlight and scroll is unreachable — found
by an independent review, and recorded here rather than quietly deleted because the closed loop it
describes IS delivered, by the reference card (§5.5), which fetches the source and highlights the
quote where the reader already is. Closes via
a `✕` button, a backdrop click, or `Esc` — the same family convention the sibling projects' own
`studio/`s already use for their trace-replay drawers. Each open aborts any still-in-flight fetch
from a PREVIOUS open (`AbortController`, module-level `sourceViewerAbort`) so a slower first
response can never overwrite a faster second one's render. Also closes on `notebook:switched`, like
every other stateful surface in this product. Does not paginate, cache across opens, or support
next/prev-citation navigation — each open is a fresh fetch, deliberately (§8's Don't list has the
same scope cut written out).

### 5.8 Notes section (Post-launch addendum 4)

NotebookLM's research-loop closing feature: a manual note, or a Chat answer saved as one, can
later be promoted into a real, independently-citable source. Lives at the bottom of the Studio
panel (§5.4) — its own VIEW behind the Studio tab strip, with the same `.panel-head` + form + list +
empty-state shape the other views use, not a new top-level column. A
`.note-item` shows the note's text plus two actions: `→ Promote to source`
(`POST .../notes/{id}/promote`) and `✕` delete (`DELETE .../notes/{id}`) — both re-render Sources
and/or Notes from the mutating endpoint's own returned `NotebookResponse`, the same "the response
IS the new state" pattern the Sources panel's add-source form already uses.

Every Chat answer (`renderTurn`, §5.3) carries a `+ Save as note` button — added by `renderTurn`
that OPTS IN, via the shared `saveAsNoteButton` factory — never inside
`renderAnswerWithCitations` itself, which six call sites use. TWO sites opt in: a Chat answer
and the chat overview (§5.9). The line is the SURFACE, not who authored the text: things
rendered in the chat thread are the user's to curate; a Studio tab's artifact and the podcast
transcript are not (AGENTS.md invariant 32).

A note carries no citations of its own and is never re-verified against `sources` (AGENTS.md
invariant 5's coordinate-only guarantee doesn't extend to freeform notes) until it's promoted —
nothing in this section's UI should imply a note is "grounded" before that point.

### 5.9 Chat overview — the "generate the research artifact" action (Post-launch addendum 5)

`#chat-overview`, the thread's FIRST ENTRY, inside `#chat-history` (invariant 57). It was a block
ABOVE it originally, because `ask` rebuilt the history wholesale from `state.turns` and would have
wiped anything in there; `rebuildHistory` re-appends the overview node now, so it simply scrolls
away as the conversation grows instead of permanently owning up to half the column.

Three states, one container (the third was added by invariant 38 and this list went stale at two):

- **Never generated, sources present** — a primary `Generate overview` button plus the hint
  "…or just ask a question below."
- **Generated, current** — `Overview` head, the Summary rendered through
  `renderAnswerWithCitations` (so its citations behave exactly like a Chat answer's), the trace
  affordance, `+ Save as note`, then `Start with` and up to three clickable starter questions taken
  from the FAQ task.
- **Generated, sources changed since** — the same, still readable, marked stale, plus
  `↻ Regenerate`. Confiscating an overview because the user added a source is worse than showing it
  with a marker: it is still true about the sources it was computed from, and it cost a real RLM
  run. `+ Save as note` stays here especially — a stale overview is precisely the one worth keeping
  before regenerating.

Hidden entirely when the notebook has no sources. It carried `max-height: 45%` and its own
scroller while it was a SIBLING of `.chat-history` — as an unbounded flex item it would have
refused to shrink and pushed the ask box off screen. Inside the scroller that reason evaporates,
and `style.css` says so: "NO `max-height` and no scroller of its own any more".

**Why it exists.** Adding a source used to leave the screen doing nothing — Chat said "ask a
question once you've added a source", Studio said "pick a tab to generate it", and both waited on
the user to discover the next move. The guided feel of a notebook product comes from the artifact
appearing IN the conversation and being something to ask follow-ups about; a Summary buried in a
right-hand tab is disconnected from the thread, so even finding it leads nowhere.

**Still an explicit button, never auto-generated.** §5.4's rule (a guide run is a real RLM loop, so
never spend one nobody asked for) is unchanged — what changed is that the action is obvious rather
than hidden behind a tab.

**Persisted** (invariant 38 — a deliberately narrow cut of the never-cache-guide-artifacts rule,
the overview only) and marked STALE rather than deleted whenever the corpus changes
(the same rule the Studio cache follows: stale the moment the sources it was computed from change,
not just when the notebook does).

## 6. Depth / motion

Minimal: 1px hairline borders between surface steps, `var(--radius)` (6px) on interactive elements,
no glassmorphism, no marketing gradients. The header uses a subtle `backdrop-filter: blur` over a
translucent background, matching the sibling studios' sticky-header treatment. Phase 3's ticker is
originally NOT an animated signature — plain live-updating TEXT in an existing pending slot. That
held until a run had to show it was alive across minutes: `run-pulse`, `source-sheen` and `spin`
exist now (invariant 47), and the constraint that survived is that motion marks a RUNNING state and
nothing else. The one new interaction affordance (`.ticker-toggle`,
`.citation-clickable`) uses only the existing hover/focus language already established for buttons
and tabs, not a new visual language of its own.

## 7. Responsive

Three columns (`280px minmax(0,1fr) 340px`) above 1024px. Two columns (Sources | Chat) with Studio
dropped to a full-width row under Chat between 640px and 1024px. Single-column stack (Sources, Chat,
Studio) below 640px. Matches the family's existing breakpoint convention.

## 8. Do / Don't

**Do**: key citation styling on `verified` (from `citations.py`, coordinate-existence only — see
AGENTS.md invariant 5), never imply stronger faithfulness than that; flag an unverified citation and
an injection-scan hit, never hide either; show every state explicitly (pending, error, empty) rather
than a blank gap; keep `--accent`/`--studio-accent` non-cross-used.

**Don't**: no Inter, no Fraunces, no centered marketing hero, no purple/blue gradient; no ✨ on a
button (it is the 2023 AI tell, and this product had two); no tab that fills with the accent — a tab
reports a position, it does not promise an action, and the fill is reserved for the one primary per
visible region; don't imply a
citation's surrounding prose is faithful to the source, only that its coordinates resolve, and don't
let the citation-turn detail panel imply a stronger claim either — it shows WHERE the model read
something, never that the surrounding prose is faithful to it; don't auto-fetch a Guide kind on
notebook open or on a bare tab switch
— only first activation or an explicit regenerate; don't use a `data:` URI for the podcast player —
a real URL on this server instead (`GET .../audio/file`). The episode is PERSISTED (invariant 42),
so there is no object URL to revoke and no revocation order to get right — the rule that replaced
this one is that the download link's extension follows the served FILE, since a provider may emit
WAV (invariant 43). (Historically: assign the new URL before revoking the
old one, never the reverse); don't let a dropped ticker connection block or alter the actual
request's own result — the ticker is strictly secondary; don't let the source-viewer modal's fetch
skip its `AbortController` guard — a stale response overwriting a fresher one's render is exactly
the class of bug the Phase 3 trace-detail retrofit (§5.5) had to fix after shipping once already;
don't add pagination, cross-open caching, or next/prev-citation navigation to the source viewer —
each open is a deliberately fresh, simple fetch; don't move the "+ Save as note" button into the
shared `renderAnswerWithCitations` — it must appear on Chat answers only, never on a Guide kind or
the podcast transcript, which also call that same function; don't imply a note is grounded or
citable before it's promoted into a real source.

## 9. Acceptance (in a browser)

1. **First screen is the INBOX**, not a notebook: a facet rail, a capture field set in the reading
   face, a find field under it, a dated stream. This item used to say "three visible columns",
   which stopped being the first screen when the Inbox became the default surface.
2. Opening a fresh notebook id shows empty Sources/Chat; adding a URL source populates the Sources
   list and clears the input.
3. Asking a question shows the question bubble immediately, a "Thinking…" pending answer, then the
   real answer with inline underlined citations, each numbered, and the References view carrying one
   compact ROW per source that opens (invariant 58). The "citation list below the answer" this item
   used to describe is gone — one source cited eight times filled the column with blockquotes.
   A question that FAILS renders as its own state, never as an answer (and offers no save-as-note:
   a note promotes into a citable `Source`, and an exception must not become one).
4. An unverified citation shows a dashed red underline AT REST; a verified one rests as a
   superscript number and shows its accent stroke on hover or focus (§2). Tab reaches every
   citation in a turn that has a run id, and Enter or Space opens its reference.
5. The theme toggle flips Paper ↔ Study and survives a reload; neither palette shows invisible or
   near-invisible text against any surface step it's used on.
6. No horizontal overflow at 375px in EITHER view. Below 860px the facet rail gives way to the
   header crumb; below 640px the notebook's three columns stack Sources → Chat → Studio.
7. Clicking a Studio Guide tab for the first time shows "Generating…" then real content with
   inline citations; clicking a DIFFERENT tab and back shows the FIRST tab's content instantly (no
   second model call) until `↻ Regenerate` is clicked or a source is added.
8. Clicking `Generate podcast` on a notebook with substantive sources shows the "this can take a
   while" pending copy, then a working transport (play, scrub, clock) plus a transcript below it, each
   line highlighted the same way a Chat citation is. Regenerating replaces the player without ever
   leaving two object URLs alive at once (check via a memory profiler or simply confirming the old
   player still works after a page RELOAD, which is the point of persisting it, and that
   regenerating replaces the audio rather than replaying the previous episode).
9. Asking a question shows LIVE, updating ticker copy in the pending slot (not static "Thinking…")
   while the run is in flight; once it settles, a `⌁ steps` pill appears next to the answer, and
   clicking it opens the Trajectory drawer (invariant 70). It no longer expands an inline log — the
   planner's prose does not belong inside the answer — and on a run that produced no trace the pill
   retires in place rather than raising a dialog.
10. Clicking a highlighted citation (in Chat, a Guide tab, or the podcast transcript) lights up its
    row in the References view, and pointing at either end lights up the other (invariant 58). The
    shared `.citation-detail` slot this item used to describe is gone from the tree entirely — see
    §5.5.
11. Reloading the page and reopening a notebook whose history predates Phase 3 (no `run_id` on
    those turns) shows those old turns with plain, non-clickable citations and no `⌁` pill — a
    graceful degradation, not a broken affordance.
12. Switching to the "Paste text" tab and submitting real text adds a source whose origin is a
    readable snippet, not a bare hash; switching to "File" and selecting a real `.pdf`/`.txt`/`.md`
    file uploads and ingests it, with the Sources list showing the original filename as the origin.
    Selecting an unsupported file type shows an inline notice naming the problem — the same error
    surface every other failure in this UI now uses, not a silent failure and not a browser dialog.
13. Clicking a citation-list row (not just the inline highlighted span) opens the source-viewer
    modal with that source's full text. It does NOT highlight a block — no call site passes one
    (§5.7); the highlighted-quote loop is the reference card's, in place;
    the per-row `⌁ trace` icon is gone (§ above says so; this item had not followed). Clicking a
    `.source-item` in the Sources panel opens the same modal with no highlight. `Esc`, the backdrop, or the `✕` button all close it.
14. Typing a note into the Notes section's textarea and submitting adds it to the list and clears
    the textarea; clicking `+ Save as note` on a Chat answer adds a note with that answer's text,
    and the SAME button never appears on a Guide tab's or the podcast transcript's answers.
    Clicking `→ Promote to source` on a note removes it from Notes and adds a matching item to
    Sources; clicking `✕` on a note removes it with no confirmation prompt.

## 10. The Inbox (`#view-inbox`)

**The constraint that produced the design.** Invariant 51 forbids rendering `og:image`, because a
remote image makes the reader's browser fetch a URL the captured page's author chose, turning every
saved link into a beacon. So the pattern every comparable product leans on — mymind's masonry of
thumbnails — is structurally unavailable here. That is the brief, not a limitation to work around:

> **If recall cannot be visual it has to be typographic.**

Everything follows. The title and the distilled summary are set in the reading face at a real
measure, because they are what you scan. There is no card, no thumbnail slot and no shadow: a
hairline between rows is the only separation, so the page reads as one column of prose. The row is
a `.node`, the prose is `.node-title` + `.node-summary`, and the metadata (`.node-meta`) carries
only what helps you find it again.

**Comparable products, and where this departs.** Things 3 treats an inbox as a staging area you
empty, with a count that is a debt; mymind treats it as a canvas you never organise, with no
folders and search as the only navigation. This is mymind's posture (no unread count, no
inbox-zero) with Things' promotion verb available but never demanded, because the user's stated
pain was not wanting to owe anything to the things they keep.

- **`.capture`** — one field, not tabs. What you paste decides what it is; the notebook's own source
  panel keeps its tabs because "add a source to THIS notebook" is a deliberate act and this is not.
  A file dropped anywhere on the surface is a capture.
- **`.dateline`** — editorial furniture with a job. It anchors a page that otherwise had no focal
  point, groups the stream the way a person actually looks ("it was that afternoon"), and is the
  only time marker in the product — which is why it carries the YEAR once the date leaves the
  current one, or a stream older than twelve months stops being monotonic. It replaced a per-row
  character count as the recall cue; a SIZE still appears above 2,000 characters, where it is a fact
  about the document rather than about the sentence you can already see.
- **`.facets`** — the rail. Without it the two-tier model existed only in a header dropdown and the
  product's central idea was invisible. Stepped to `--surface-2`, which is measured rather than
  eyeballed: `--surface-1` is 2.5% of lightness from `--bg` in Paper, under the 4% an app shell
  needs between a sidebar and a main surface.
- **`.intake-strip`** — present only while something is running, and it renders exactly what
  `GET /inbox/status` returns (invariants 47 and 60). Its Stop says what it can do: the item being
  parsed finishes, because a native PDFium parse cannot be interrupted.
- **`#distil-btn`** — an ID, not a class. `.distil-btn` appeared here and in a focus rule, and matched nothing in either place. It names the NUMBER it will cost before it costs it: the count beside it is the backlog, the button is one batch out of it, and they are different numbers (invariant 80).

**The signature micro-interaction is the swallow**: a captured row settles into place from just
above it (`.node.is-new`, `@keyframes node-swallow` — `translateY(-0.5rem)` + `scaleY(0.96)` +
opacity, 260ms on `cubic-bezier(0.16,1,0.3,1)`, transform and opacity only). This paragraph used to
say the row "grows out of the capture field", and a reviewer checked the keyframes and the geometry:
it animates at the ROW's own position, three hundred pixels below the field. The motion is good and
the sentence was describing a different one. Naming it accurately matters more than keeping the
metaphor, because the metaphor is what a later reader would try to build. It is the only entrance animation on the surface. The only other
motion is the state dot, which pulses while a node is being worked on and is otherwise still, so
noticing it means something. Expansion is `grid-template-rows: 0fr → 1fr` on `.node-body`: no modal
and no route change, so the row stays exactly where the eye left it.

**Never `innerHTML`** (invariant 55), never an `<img>`, and every `url()` on this surface is a
`data:` URI. This is the surface that renders the most attacker-influenced text in the product — a
captured page's title, a model-written summary, the full text of anything at all — and
`tests/test_web_assets.py` asserts all three against the source.

### Acceptance, the Inbox specifically

- Pasting a link adds a row IMMEDIATELY, before anything is fetched, and the row grows out of the
  capture field rather than appearing. Its dot pulses while the node is read and settles when it is
  done. Dropping a file anywhere on the surface does the same.
- Typing with an IME and pressing Enter COMMITS the candidate; it never posts a half-formed node.
  The same holds for the find field and the notebook rename.
- A failed capture shows the reason it failed, and still offers `Try again` and `Forget`. It is not
  a dead row. It does NOT offer `File into…`: a node with no blocks cannot be promoted, and the
  picker's only possible outcome was a 400 contradicting what the reader could see. In its place the
  row says "Nothing to file yet — it has no text."
- The find field narrows the stream against titles, summaries, tags, entities and origins; clicking
  a tag does the same; Escape clears it. An empty result says nothing MATCHED, never that the Inbox
  is empty.
- The summary action names the BATCH it will run before it spends anything (which is a different
  number from the backlog beside it), and while it runs the strip shows progress and a Stop. The
  same is true of the AUTOMATIC pass, which shares the state — the one batch nobody pressed a button
  for is the one that most needs to be visible. Stop ends it at a node boundary and says what it
  reached: an item already being parsed runs to completion (a native PDFium parse cannot be
  interrupted without taking the process with it), and everything still waiting lands as `failed`
  with "stopped before it was read" rather than sitting at `queued` forever, which looks exactly
  like still working.
- Opening a row, then waiting through a parse, leaves the row OPEN and the page where it was. A
  repaint may not take the reader's place away from them.
- An empty Inbox explains what a paste becomes, what a facet is, and that summaries are a separate
  deliberate spend. A search that found nothing does not.
