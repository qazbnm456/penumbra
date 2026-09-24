# Penumbra web UI: visual and UX spec

This is the web frontend's design contract, and `index.html`, `style.css` and `app.js` follow it. It owns look and feel only. The architecture and the reasoning behind each rule live in `AGENTS.md` and `docs/invariants/`.

**Where this file and the code disagree, the code is right and this file has drifted.** Prose about code rots, and reviews have found this file stale more than once: an accent value, a replaced control, a removed `alert()`. Where a claim names a selector or a token, `tests/test_web_assets.py` can pin it, and a test fails if this file names a class the code no longer has without saying so. Where a claim describes intent, nothing can check it, so fix this file rather than reasoning from it.

**This is a workspace, not a trace console.** The sibling projects each ship a single-verdict console: one input, one result card, a live feed and a replay drawer. This product holds many orbits, many sources, a saved conversation and artifacts meant to be read, and the difference is deliberate.

## 1. Direction

Warm editorial calm: ink on paper in the light theme (Paper, the default) and a reading lamp at night in the dark one (Study). It is focused, legible and unhurried; not playful, not corporate, not a terminal, and never the cool blue-slate of a security console.

**There are two surfaces, and the Horizon is the one you land on.** `index.html` switches between `#view-horizon`, the default (an orbit rail, a capture field and a dated stream of nodes, §10), and `#view-orbit`, the three-pane workspace you reach by opening an orbit. The address bar follows the view, so an orbit can be bookmarked and Back returns to the Horizon.

The direction did not change when the Horizon arrived. Ink on paper, Literata for reading, Public Sans for the interface and one copper accent were already what the Horizon needed. What it lacked was structure, and a typeface this file described but the page never loaded (§4).

Both surfaces are in utility mode, with no marketing hero. The Horizon reads: orient (the rail), capture (the field), status (a strip, only while something runs), read (the stream). The orbit reads: sources (left), converse (centre), produce (the Studio, right).

## 2. The signature: a citation as a highlighter stroke

A citation is a span (`.citation`) whose resting mark is a small superscript number, appended by `.citation::after { content: attr(data-reference) }`. The 2px `--highlight-border` underline appears on `:hover` and `:focus-visible`. This is the literal visual expression of the product's core value: grounded, verifiable text. The number belongs to the interface, never to the model (invariant 48.5).

The resting mark is the number because an always-on mark made grounding unreadable. A permanent wash turned an answer with nine citations into nine highlighted bands. A permanent underline was no better: a real 1,996-character overview had 16 strokes covering 95.9% of its text, a solid slab that answered "which part is grounded?" with "all of it". So the stroke now shows the extent of one claim when you point at it or tab to it. The underline, not the wash, carries the highlight, because the wash alone measured a self-contrast near 1.0 over Study's `--surface-3`.

An unverified citation (one `citations.py` could not resolve against the current corpus) keeps a dashed `--bad` underline at rest, because a warning that appears only on hover is not a warning. It is flagged and never dropped, the same discipline `injection_scan.py`'s flags follow.

The stroke is operable: `tabindex="0"`, `role="button"`, Enter and Space, and a `:focus-visible` ring. Activating it opens the matching card in the References view (invariant 58). This shows where the model read, never that the surrounding prose is faithful to it (invariant 5).

## 3. Palette

Two first-class OKLCH palettes, `[data-theme="light"]` (Paper) and `[data-theme="dark"]` (Study), are toggled from the header, stored in `localStorage` and seeded from `prefers-color-scheme` on the first visit. **The live tokens are the `:root` blocks in `style.css`.** The values below are the intent.

```
/* Paper (light, default) */
--bg: warm off-white        --surface-1..3: step down in warmth    --border / --border-strong
--text: deep ink navy, oklch(22% … 260)                           --text-dim
--text-faint: oklch(46% 0.018 260)
--accent: copper, oklch(54% 0.16 55)
--highlight-wash: warm cream, oklch(88% 0.09 75)
--highlight-border: oklch(62% 0.16 55), lighter than the accent
--studio-accent: muted sage, oklch(55% 0.05 165)
--ok / --warn / --bad
```

```
/* Study (dark): a reading lamp at night, not a security terminal */
--bg: warm near-black       --surface-1..3: step up in warmth
--text: warm cream          --text-dim
--text-faint: oklch(70% 0.012 75)
--accent and --highlight-border: brightened copper, oklch(75% 0.15 55)
--highlight-wash: oklch(50% 0.08 70 / 0.65)
--studio-accent: oklch(68% 0.06 165)
--ok / --warn / --bad in the same hue families as Paper
```

Every text token clears WCAG AA (4.5:1) on every surface step it is used on. Paper's accent is darker than its highlight border for that reason: at 62% the copper failed AA as text, so the accent moved to 54% and the stroke kept the lighter value.

**Accent discipline.** `--accent` goes only on interactive elements and the citation stroke, and `--studio-accent` only inside the Studio, which separates conversing from producing. A filled accent marks the one primary action in a visible region, so a tab never fills: a tab reports a position, it does not promise an action. Surfaces step 1, 2, 3, and two panels of the same tone never touch.

## 4. Typography

The faces were chosen deliberately. Fraunces, Inter and JetBrains Mono everywhere were each considered and rejected.

**The faces are self-hosted and actually loaded** (`web/fonts/*.woff2`, 176 KB). For a long time `style.css` named them and nothing delivered them, so any machine without them installed drew the whole interface in its system sans, which in an ink-on-paper direction means losing the identity. They are served locally rather than from a CDN for the reason invariant 51 refuses `og:image`: a remote font makes the reader's browser call a third party on every load, and this app binds loopback and ships in a container verified with no network at all. There is one variable file per family and style, and each covers the Latin `unicode-range` only, so a run of Han characters never waits on a download it cannot use. CJK faces come from the operating system and are paired explicitly in `--sans` and `--serif`, Traditional first, because a Simplified face draws the wrong forms for the zh-Hant interface.

- **Literata** is for content read at length: the Horizon's node titles, summaries and full text, and the capture field itself. Its optical-size axis is driven by `font-optical-sizing: auto`, so one file gives a display cut at heading sizes and a reading cut at body sizes. Google commissioned it for long-form reading on screen, which is what this product asks of a reader. Guide and podcast content still use the chat's Public Sans treatment, for consistency with the thread they sit beside.
- **Public Sans** is all interface chrome: navigation, labels, buttons, form fields and the chat turns. It is the US Web Design System face, built around clarity and trust, and it is the `body` default.
- **A system monospace stack**, `--mono` (`ui-monospace, SFMono-Regular, "SF Mono", Menlo, …`), not JetBrains Mono. Every target OS ships a good monospace, and here it carries technical texture rather than identity. Every rule reads `var(--mono)`; an earlier set of rules that put JetBrains Mono first rendered it only for readers who happened to have it installed. It appears where the product echoes a developer console: the ticker pill (`.trace-face`), the Trajectory drawer's code and payload panes, and the technical half of each failure block (`.node-error-why`, `.turn-failed-why`, `.distil-error-why`).

## 5. The orbit

### 5.1 Header

A 56px bar over `--surface`, blurred. From left to right:

- **The wordmark** (`#new-orbit`) is a real `<button>` that goes home to the Horizon. Starting an orbit lives at the foot of the rail instead (`#facet-new`).
- **The orbit title** (`#orbit-title`) is the orbit's human name (invariant 37), hidden when no orbit is open. The id is a handle nobody has to invent or read.
- **The orbit switcher** is `#orbit-current`, a button showing the current name that opens `#orbit-menu`: orbits listed by title, with source and turn counts and when each was last touched.
- **The Horizon crumb** (`#horizon-home`) leads back to the default surface whenever the rail is not visible. At desktop width it is the only way back, so it is never the element that shrinks.
- **`.header-actions`**, on the right, holds settings (`#settings-open`, invariant 41) and the theme toggle. One wrapper pushes both to the right.

### 5.2 Sources (left, about 280px)

The add-source form has URL, paste and file tabs, all wired to the API. A URL posts `{sources: [...]}` to `POST /orbits/{id}/sources`, http(s) only (invariant 26). A YouTube link goes through the same field and a hint under it says YouTube links work and read captions only (invariant 33). Pasted text posts `{texts: [...]}` to the same endpoint. A file posts `multipart/form-data` to `POST .../sources/upload` (`.pdf`, `.txt`, `.md`, one per request), never a local path string, which keeps invariant 26's ban intact (invariant 30).

Below the form, each `.source-item` shows the kind, a title and the origin, broken across lines rather than truncated into an unreadable middle. A pasted text's origin is a readable snippet plus a content hash, an upload's is its filename, and a YouTube source's is the video URL. Any `injection_scan.py` flag shows as an amber warning line, never hidden and never blocking (invariant 6). The row's head is a real button (`.src-open`) named by the source, so a keyboard can open a source and not only delete one. It opens the source viewer (§5.6) with the full text.

### 5.3 Chat (centre)

Turns run oldest first and the thread scrolls to the bottom when one is added. A question is a right-aligned bubble; an answer sits left in a bordered well with its citations inline (§2). Each answer carries Copy, Save as note, follow-up questions from the same run (invariant 56) and, on the latest answer, Regenerate. The references link, the steps pill and Regenerate share one footer row (`.turn-footer`), and the overview uses the same row. Follow-ups and Regenerate belong only to the newest completed turn. A stopped turn (`.is-stopped`) does not count as newest, so a Stop never hides the previous answer's actions.

The overview (`#chat-overview`) is the thread's first entry, inside `#chat-history`, and scrolls away as the conversation grows (invariant 57). It has three states: never generated, which offers a primary Generate overview button and "or just ask a question below"; generated and current, which shows the summary with its citations, the steps pill, Copy, Save as note and up to three "Start with" questions; and generated but stale, which keeps everything readable, marks it stale and offers Regenerate (invariant 38). A stale overview is still true about the sources it was computed from and cost a real run, so it is marked rather than removed, and Save as note stays because a stale overview is exactly the one worth keeping. It is hidden when the orbit has no sources; an empty orbit shows Paste a link (primary), Paste text and Upload a file instead (`#chat-start`), because Add source stays disabled until its field has something in it. It exists because adding a source used to leave the screen waiting for the reader to discover the next move; the artifact appearing in the conversation, as something to ask about, is what makes the product feel guided. It is still an explicit button and never generated automatically.

A pending turn shows the live ticker (§5.5) in its status row, with elapsed time and a Stop. A failure renders as its own failed turn, a bordered, tinted block with a heading and the reason in the mono face, never an answer bubble with an error prefix, and it offers no Save as note, because a note can be promoted into a citable source and an exception must not become one. Above the thread, Export downloads the orbit as Markdown and Clear conversation removes the turns; Clear is disabled while the composer is locked.

### 5.4 Studio (right, about 340px)

One tab strip (`.studio-view-tab`) switches four views: Studio, Podcast, References and Notes. The Studio view has its own inner strip of Guide kinds (Summary, FAQ, Timeline, Insight, matching `guide/{kind}`). Both strips use an underline, never a filled pill, and are told apart by size and weight. The outer strip is sticky, so opening a card low in References never scrolls the way to the other views out of sight. The column can be resized with a drag handle and collapsed to an icon strip, and the choice is remembered.

A Guide tab runs only on its first activation or an explicit Regenerate, never on orbit open or a bare tab switch, because each run is a real RLM loop. Results are cached in the page per orbit. A result computed while the sources changed is kept and marked stale with a prompt to regenerate, rather than silently shown as current. Summary and Insight render through `renderAnswerWithCitations`, the same path as a chat answer; FAQ and Timeline render one `.guide-item` per pair or event. An empty FAQ or timeline says so explicitly.

The Podcast view generates the Audio Overview. `POST .../audio` runs script generation and then synthesis in series, by far the slowest action in the product (16 minutes for a 3.4-minute episode on the local provider, invariant 43), and its pending copy says so. The episode is persisted and played from `GET .../audio/file`, so it replays after a reload without synthesising again, and the download link's extension follows the served file, since a provider may write WAV (invariants 42 and 43).

**The transport is ours and the `<audio>` element is headless.** The browser's stock player was the last unthemed surface in the product, and it differs across the three webviews a Tauri build would use (WKWebView, WebView2, WebKitGTK). `.transport` is a round `.transport-play` button, a `.transport-scrub` range whose `aria-valuetext` carries the time, and a tabular `.transport-time`. A real button and a real range come with keyboard operation and accessible names for free. `preload="metadata"` gives the duration without pulling the episode.

**The transcript behaves like subtitles.** Each `.podcast-utterance` carries a `.podcast-timecode` (`m:ss`, or `h:mm:ss` past an hour); clicking a line seeks to it and plays, and the line being spoken carries `.is-speaking` in `--studio-accent`, deliberately not the citation colour, so "where the voice is" and "what came from a source" never look alike. Highlight and scroll follow the player's own `timeupdate`, so scrubbing and pausing stay in sync with no timer of ours. The timing comes from `Podcast.offsets`, reported by the TTS provider at synthesis (invariant 44). Anything other than one strictly increasing offset per utterance falls back to a plain transcript with no timecodes, seeking or highlight. A length check alone is not enough: a provider that reports no boundaries returns one zero per line, and a simulation of that case stamped every line `0:00`, highlighted one line for the whole episode and sent every click to zero. Misaligned subtitles are worse than none.

References (invariant 58) holds one compact `.ref-card` row per cited source that opens to show the passage, with the cited words marked as a `.source-quote` and scrolled into view. Pointing at either end of a citation lights up the other. Notes are covered in §5.7.

### 5.5 Live runs, the ticker and the Trajectory drawer

Every ask, Guide run and podcast picks its own run id in the client (`crypto.randomUUID()`, prefixed with the orbit id), because a server-made id would not reach the page until the request was over. The page opens a live SSE stream against that id beside the request, and while the run is pending, translated trace events update the status row in place. The ticker is secondary: if its connection drops the row stops updating, and the request still delivers the answer.

When the run settles, a `⌁ steps` pill (`.ticker-toggle`) opens the Trajectory drawer for that run (invariant 70): each planner turn in the model's own words, the code each turn ran, the tool calls, real per-turn timing, the token budget (invariant 75) and what the validator rejected. The planner's prose belongs there and not in the answer. On a run that left no trace, the pill retires in place rather than raising a dialog. A turn saved without a `run_id` has plain, non-clickable citations and no pill.

Every run follows the same state rules (invariants 47, 60 and 71). A run owns its status row and its Stop. A result lands only in its own orbit and tab. Stop or a failure keeps the previous result. A lock is released only by its owner, and the composer stays locked while either the overview or a question runs. A run found still going after a reload keeps a working Stop, and every control comes back once its run ends. Motion marks a running state and nothing else.

### 5.6 Source viewer

A modal (`.modal-overlay` and `.modal`, with an explicit `z-index`) that fetches `GET /orbits/{id}/sources/{source_id}` and renders every block as a labelled `.source-block`. It is headed by the page's own title (the response carries `preview`), opens from a Sources row and shows the whole text with no highlight: `showSourceViewer` can centre a quote, but the References card already shows the cited words where the reader is, so no caller passes one. It closes with `✕`, a backdrop click or Escape, and on an orbit switch. Each open aborts the previous open's fetch (`AbortController`), so a slow first response can never overwrite a faster second one. It does not paginate, cache across opens or step between citations; each open is a fresh fetch, on purpose. A failed fetch shows an inline error and the modal stays open.

### 5.7 Notes

A note, written by hand or saved from an answer, can later be promoted into a real, citable source. Notes are a Studio view with the same head, form, list and empty state as the others. A `.note-item` shows its text with Promote to source (`POST .../notes/{id}/promote`) and delete (`DELETE .../notes/{id}`), and both re-render from the response, which is the new state. A promoted note disappears from Notes and appears in Sources; if identical text is already a source, only the note disappears. Deleting asks for no confirmation. A failed action shows an inline notice (`notify()`, `#notices`) and re-enables the button. The page uses no `alert()`: it cannot be styled, it blocks the renderer, and in a Tauri shell it becomes an OS modal.

Save as note appears on a chat answer and on the overview, and nowhere else. It is added by the callers that opt in through a shared factory, never inside `renderAnswerWithCitations`, which Guide tabs and the podcast transcript also use. The line is the surface: what is in the chat thread is the reader's to curate, and a Studio artifact is not (invariant 32). A note has no citations and is never re-verified, so nothing in the UI may suggest a note is grounded before it is promoted.

### 5.8 States

| state | what shows |
|---|---|
| no sources | Sources: an empty note under the form. Chat: the add-a-source note, then Paste a link, Paste text and Upload a file. The overview is hidden. |
| sources, no turns | The overview's Generate button and an invitation to ask. |
| a question or overview running | A status row with the live ticker, elapsed time and Stop; the composer is locked. |
| a question stopped | The turn is marked stopped; the previous answer keeps its actions. |
| ask fails | A failed turn with a heading and the reason, and no Save as note. |
| a Guide tab running | Its own status row and Stop in the tab body; other tabs stay usable. |
| a Guide result made while sources changed | The result, marked stale, with a prompt to regenerate. |
| empty FAQ or timeline | An explicit message that the sources did not produce enough, never a blank body. |
| a Guide or podcast run fails | An inline failure block; the previous result, if any, comes back. |
| podcast running | Pending copy that says it takes a while, plus Stop; Generate is disabled. |
| podcast script empty | A message that the sources did not produce enough to discuss, and no player. |
| a citation activated | The Studio switches to References and the matching card opens at the quote. |
| a source row opened | The source viewer, first "Loading…", then the full text. |
| a note action fails | An inline notice; the button re-enables. |

## 6. Depth and motion

Minimal. Hairline borders separate surface steps, interactive elements use `var(--radius)` (6px), and there is no glassmorphism and no marketing gradient beyond the header's light `backdrop-filter` blur. Motion marks a running state (`run-pulse`, `source-sheen`, `spin`, invariant 47) and one entrance, the Horizon's swallow (§10). Everything respects `prefers-reduced-motion`. Interactive affordances such as `.ticker-toggle` and `.citation-clickable` use the same hover and focus language as buttons and tabs.

## 7. Layout by width

This is a desktop application, so the layouts below 1024px serve a narrow window or high zoom, not a phone.

- **Above 1024px**: three columns, `280px minmax(0, 1fr) 340px`, with the Studio resizable.
- **641px to 1024px**: Sources and Chat side by side, with the Studio as a full-width row beneath; the resize handle is hidden because the split it drags no longer exists.
- **860px and below**: the Horizon's orbit rail gives way to the header crumb.
- **640px and below**: the orbit shows one area at a time through a Sources, Chat and Studio tab row (`#col-switch`), and the wordmark drops out of the header.
- **Down to 320px** (WCAG 1.4.10 reflow, a 1280px display at 400% zoom): no horizontal scroll in either view.

Print drops the application chrome, always uses the light palette, starts with the orbit's title and appends the reference list the printed numbers point to.

## 8. Do and don't

**Do**: key citation styling on `verified`, which means only that the coordinate exists (invariant 5); flag an unverified citation and an injection-scan hit and never hide either; show every state explicitly (pending, stopped, failed, empty, stale) rather than a blank gap; keep `--accent` and `--studio-accent` apart; keep a running action visible and stoppable.

**Don't**: use Inter or Fraunces, a centred marketing hero or a purple-to-blue gradient; put ✨ on a button; fill a tab with the accent; imply a citation's surrounding prose is faithful to its source; auto-run a Guide kind on orbit open or a bare tab switch; use a `data:` URI for the podcast; let a dropped ticker change a request's result; skip the source viewer's `AbortController`; add pagination, cross-open caching or citation stepping to the source viewer; move Save as note into `renderAnswerWithCitations`; imply a note is grounded before it is promoted.

## 9. Acceptance, in a browser

1. The first screen is the Horizon: an orbit rail, a capture field set in the reading face, a find field and a dated stream.
2. Opening a new orbit shows empty Sources and Chat. Adding a URL source fills the list and clears the input.
3. Asking shows the question at once, then a status row with live ticker copy, elapsed time and Stop, then the answer with numbered citations. References holds one row per cited source that opens. A failed question renders as a failure, never as an answer, and offers no Save as note.
4. An unverified citation shows a dashed red underline at rest; a verified one rests as a number and shows its stroke on hover or focus. Tab reaches every citation, and Enter or Space opens its reference.
5. The theme toggle switches Paper and Study and survives a reload, and neither palette has near-invisible text on any surface.
6. There is no horizontal overflow at 320px in either view. Below 860px the rail gives way to the crumb, and below 640px the orbit shows one area at a time through tabs.
7. A Guide tab's first activation runs it, then shows content with citations. Switching away and back shows the same content without a second run, until Regenerate. A result produced while the sources changed is marked stale.
8. Generate podcast shows pending copy that warns it takes a while, then a working transport (play, scrub, clock) and a transcript whose citations behave like the chat's. After a reload the episode still plays, and regenerating replaces it rather than replaying the old one.
9. After a run settles, the `⌁ steps` pill opens the Trajectory drawer; on a run with no trace it retires in place.
10. Activating a citation in chat, a Guide tab or the transcript lights up its References row, and pointing at either end lights up the other.
11. A turn saved before run ids existed shows plain citations and no pill.
12. Pasting text adds a source whose origin is a readable snippet; uploading a `.pdf`, `.txt` or `.md` shows the filename as the origin; an unsupported file type shows an inline notice, never a browser dialog.
13. Opening a Sources row opens the viewer with the full text, and Escape, the backdrop or `✕` closes it.
14. Adding a note clears the field and lists it; Save as note on an answer adds a note with its text and never appears on a Guide tab or the transcript; promoting moves the note into Sources; deleting asks for no confirmation.

## 10. The Horizon (`#view-horizon`)

**The constraint that produced the design.** Invariant 51 forbids rendering `og:image`, because a remote image makes the reader's browser fetch a URL the captured page's author chose, and every saved link becomes a beacon. So the thumbnail masonry that comparable products lean on is unavailable here. That is the brief, not a limitation:

> **If recall cannot be visual, it has to be typographic.**

Everything follows from it. The title and the distilled summary are set in the reading face at a real measure, because they are what you scan. There is no card, no thumbnail slot and no shadow; a hairline between rows is the only separation, so the page reads as one column of prose. A row is a `.node`, its prose is `.node-title` and `.node-summary`, and its metadata (`.node-meta`) carries only what helps you find it again.

**Where this sits among comparable products.** Things 3 treats an inbox as a staging area you empty, with a count that is a debt. mymind treats it as a canvas you never organise, with search as the only navigation. This Horizon takes mymind's posture (no unread count, no inbox zero) and keeps Things' filing verb available but never demanded, because the pain it answers is not wanting to owe anything to what you keep.

- **`.capture`** is one field, not tabs: what you paste decides what it is. The orbit's source form keeps its tabs because adding a source to this orbit is a deliberate act and capturing is not. A file dropped anywhere on the surface is a capture.
- **`.dateline`** groups the stream the way people remember ("it was that afternoon") and anchors a page that would otherwise have no focal point. It is the only time marker on the surface, which is why it shows the year once a date leaves the current one. A size appears on a row only above 2,000 characters, where it says something about the document rather than the sentence you can already see.
- **`.facets`** is the orbit rail. Without it the two-tier model lived only in a header menu and the product's central idea was invisible. It sits on `--surface-2`, because `--surface-1` is only 2.5% lightness from `--bg` in Paper, under the 4% an app shell needs between sidebar and main surface.
- **`.intake-strip`** appears only while something runs, and shows exactly what `GET /horizon/status` returns (invariants 47 and 60). Its Stop says what it can do: the item being parsed finishes, because a native PDFium parse cannot be interrupted.
- **`#distil-btn`** names the number it will spend before spending it. The count beside it is the backlog and the button is one batch from it, which are different numbers (invariant 80). It is an id; the `.distil-btn` class this file used to name matched nothing anywhere.

**The signature micro-interaction is the swallow.** A captured row settles into place from just above its own position (`.node.is-new`, `@keyframes node-swallow`: `translateY(-0.5rem)`, `scaleY(0.96)` and opacity over 260ms on `cubic-bezier(0.16, 1, 0.3, 1)`, transform and opacity only). It is the only entrance animation on the surface. The only other motion is the state dot, which pulses while a node is being worked on and is otherwise still, so noticing it means something. A row expands with `grid-template-rows: 0fr → 1fr` on `.node-body`, with no modal and no route change, so it stays exactly where the eye left it.

**No `innerHTML`, no `<img>`, and every `url()` is a `data:` URI** (invariant 55). This surface renders the most attacker-influenced text in the product (a captured page's title, a model-written summary, the full text of anything at all), and `tests/test_web_assets.py` asserts all three against the source.

### Acceptance, the Horizon

- Pasting a link adds a row immediately, before anything is fetched. The row settles into place, its dot pulses while it is read and goes still when done. Dropping a file anywhere on the surface does the same.
- Pressing Enter while composing with an IME commits the candidate and never posts a half-formed node. The same holds for the find field and renaming an orbit.
- A failed capture shows why it failed and offers Try again and Forget, the same size, Try again first. It does not offer File into…, because a node with no text cannot be filed, and says so instead.
- The find field narrows the stream by title, summary, tags, entities and origin; clicking a tag does the same; Escape clears it. An empty result says nothing matched, never that the Horizon is empty.
- The summary action names the batch it will run before it spends anything. While it runs, automatic or pressed, the strip shows progress and a Stop. Stop ends at a node boundary: the item being parsed finishes, and everything still waiting becomes `failed` with "stopped before it was read" rather than sitting at `queued`, which would look exactly like still working.
- A row left open through a parse stays open, and the page stays where it was. A repaint may not take the reader's place away.
- An empty Horizon explains what a paste becomes, what an orbit is, and that summaries are a separate, deliberate spend. A search that found nothing does not.

## 11. The island (`island.html`)

**At rest the app is the notch, and the notch says nothing.** The desktop app runs in the background, and its only presence is a black shape in the MacBook notch, the same black and the same size, so at rest it cannot be told from the hardware. Where there is no notch it is a thin target at the top centre of the screen, or at the left edge on Windows and Linux.

**Icons only.** The island carries one thing, a ring (`.horizon`: `.accretion` spinning around a black `.core`), and every state is told by what the ring does. A screen reader hears each state through a live region instead. An app name or a sentence in the notch was tried and removed: the shape is small, it is seen hundreds of times a day, and words there read as noise.

| state | what the ring does |
|---|---|
| resting | nothing; the shape is the notch |
| hover (the pointer rests on it) | the shape grows a capsule-shaped lower half and the ring turns slowly |
| armed (something is dragged toward it) | the shape opens into a deep bowl, the ring grows and spins faster, and rings of light (`.pull`) collapse into the core |
| taking in (after a drop) | the dropped item falls in as a glowing mote; the pull keeps going while the server works |
| landed | the core swallows once and the ring flares |
| refused (a file type the server cannot read) | the ring turns red and shakes |

**The shape grows out of the hardware.** Its size is set per state and transitioned, anchored at the top centre, so it grows out of the notch and shrinks back into it; the window around it is enlarged first and made small last, so nothing is clipped. Concave shoulders (`.hole::before`, `::after`) join it to the top of the screen the way the notch meets the bezel, the lower corners are deep (a capsule when hovering, a 46px bowl when open), and a soft shadow appears only once it is open. Content stays below `--inset`, the notch's height, because the display has no pixels there.

**Motion is transform and opacity only.** A blurred spinning ring and blurred falling motes stuttered in the transparent window, because a filter re-rasterises every frame. The ring's soft edge is a static mask and every moving layer has `will-change`, so each frame is a composited transform.
