# Changelog

All notable changes to `rlm-notebook` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`rlm-notebook` is an RLM-driven research notebook, built on
[`rlm-harness`](https://github.com/qazbnm456/rlm-harness): paste in sources of any kind, ask grounded
questions with verifiable citations, and get a distilled research artifact out.

## [Unreleased]

- **Round thirty-one (design confirmation): `VERDICT: COMPLETE`.** There is now an independent
  COMPLETE on both halves of the author's end condition: functional completeness and
  interactivity (round twenty-eight) and design (this round).
  - The citation-to-passage loop was confirmed on the hardest case: the newest answer's lowest card,
    with the quote at the end of a 4.1k-character block. It held in 32 of 32 runs, across 1440×900,
    1440×800, 1280×800 and 1280×720, light and dark, en and zh-Hant, and both a mouse click and
    Enter.
  - Early cards do not move the column.
  - A design sweep of 8 configurations × 15 states found no BLOCKER or HIGH. Its only repeating
    audit failure is the decorative `·`, already POLISH.
  - The judge's summary of the design: the verification loop "is now excellent". The palette and
    type are "coherent and distinctive in both themes". Every run shows its state in place with
    Stop, the Inbox gives calm typographic recall, and print produces a true artifact.
  - **Open, MEDIUM:**
    - The source viewer is headed by the host ("arxiv.org") rather than the source's title, because
      `SourceDetailResponse` carries no `preview`. The comment at `sourceDisplayName` claiming this
      was fixed is stale.
    - Opening a low card scrolls the Studio's tab strip out of view at 1280×720 and 1280×800.
    - The "Interface language" help line uses an unstyled class (`setting-help`).
  - **Open, POLISH:**
    - Three `margin: -var(...)` declarations are invalid CSS and are dropped (style.css ~2397, ~4350,
      ~6458).
    - The printed "(未驗證)" is italic, which shears Han text.
    - The raw verifier reason shows in English under zh-Hant.
    - Strikethrough is unsupported.

- **Round thirty (design confirmation): the quote marking and the three small fixes held. The
  marked words still missed the window, and that is now fixed.**
  - The quote is legible on its wash: 11.99:1 in light, 6.88:1 in dark.
  - The capture focus is now a single ring, at least 3:1 in both themes.
  - zh-Hant still renders in Songti TC.
  - `color-scheme` reaches the settings selects.
  - **HIGH, fixed: for a References card low in the list (the newest answer's, which is the common
    case), the marked words landed below the window at 1280×800 and 1440×800.** `focusReference`
    scrolled the card while it was a collapsed head, and loading the passage then grew it. After the
    load, the marked words are now scrolled into the window, with `scroll-margin-block` so they do
    not stop flush against the edge. Verified at 1280×800, 1280×720 and 1440×800, light and dark,
    on the last card: the words sit fully inside the window.
  - Also: `.empty-note` joins the rule that keeps Han text upright. It was being sheared by an
    italic in four empty states.
  - **Recorded as MEDIUM:**
    - A new answer can land partly below the fold.
    - Opening a notebook shows the top of the thread rather than the latest turn.

- **Round twenty-nine: a dedicated UI/UX DESIGN review against the author's original brief.** The
  judge studied what macapp.supply actually lists (Craft, Obsidian, Hejour, Letterboxx, Muse,
  Glance) and this category's leaders (NotebookLM, Perplexity, Readwise Reader, Heptabase). It then
  judged every surface at 1440 and 1280, light and dark, en and zh-Hant, and audited cross-platform
  risk for the Tauri targets.
  - Its verdict on the design itself: a coherent, distinctive identity that holds across both
    themes and both languages. The Inbox's typographic recall, the numbered citation, in-place run
    states with Stop, the honest stale markers, the podcast transport and the print stylesheet are
    "at or above the bar" set by NotebookLM and Perplexity. It found one HIGH.
  - **HIGH, fixed: opening a citation never visibly marked the cited words in the source passage.**
    The quote reused `.citation`, which rests unmarked since citations became numbers, so the
    product's verification loop ended on an unhighlighted wall of text. Nothing scrolled the words
    into view inside the 24rem passage either. The words are now a `<mark class="source-quote">`,
    washed and stroked at rest. The reference card scrolls its own passage to them, and the source
    viewer centres the quote rather than its block. Verified with a quote 4,800px deep, light and
    dark.
  - **Cheap cross-platform fixes, done:**
    - `PMingLiU`/`MingLiU` added to `--serif`: Windows ships no other CJK serif, so zh-Hant fell back
      to a sans in WebView2.
    - `color-scheme` is declared per theme, so native `<select>` popups follow the palette.
    - The Inbox capture field's double focus ring is gone.
  - **Recorded for the Tauri shell work, not the web UI:**
    - The WebKit floor is Safari 16.2 because of `color-mix()`, and 18 for unprefixed
      `backdrop-filter`, which degrades gracefully. `minimumSystemVersion` must match.
    - Export, "Download mp3" and print rely on browser affordances the shell must provide.
  - **Recorded as MEDIUM:**
    - An answer's footer actions sit on three lines rather than one action row.
    - The Studio panel is a stack of bordered boxes.
    - An empty notebook has no primary action.
    - A failed Inbox row mixes three button sizes.
    - The injection flag shows a raw slug.

- **Round twenty-eight (confirmation): `VERDICT: COMPLETE`, with no BLOCKER and no HIGH on any
  core journey at desktop scope.** This meets the stop condition the author set.
  - Both round-twenty-seven fixes held.
  - The stuck-control sweep was clean in both directions: every run-related control came back
    usable after the run ended, and none unlocked while its lock should still hold. It covered 60
    combinations: 4 run kinds × 5 contexts × success, failure and Stop, plus a 9-case zh-Hant subset.
    A negative control confirmed the detector can fail.
  - Journeys, contrast (canvas-resolved, with a 21.00 sanity check) and a 40-stop focus walk were all
    sound at 1440 and 1280, light and dark, en and zh-Hant.
  - **Open, recorded as MEDIUM and not blocking:**
    - Podcast Generate comes back live while a question started during the podcast still runs,
      after the podcast is stopped or fails. Pressing it is a deliberate second run, and both runs
      keep their Stop.
    - After a recovered run ends or fails, its "Load the result" line becomes the last child and
      hides the last turn's ↻ Regenerate.
    - The overview's "Start with" chips stay beside the first answer's "Ask next".
    - Clear stays hidden after a fresh notebook's first answer, and is enabled during a recovered run.
    - A chip overwrites a draft.
    - A run row keeps its label in the old language after a language switch.
    - A guide that succeeds after a mid-run source change is cached as current.
    - Keyboard focus falls to `<body>` after Stop.
    - A failed question can land just below the fold.
    - The podcast panel does not relabel on a language switch.
    - "Load the result" after a guide outlives a notebook switch finds nothing, because guides are
      memory-only.
  - **Open, POLISH:**
    - The Inbox `·` separators measure 2.24:1 and 2.62:1 (decorative).
    - The "Ask next" chips print.
    - The server-derived "Untitled notebook" stays English under zh-Hant.

- **Round twenty-seven (confirmation): round twenty-six's fixes held, and every lock-or-flag pairing
  the judge tried passed. Two HIGHs remained, both regressions of mine; both are fixed.**
  - **The suggested-question chips ("Start with", "Ask next") did nothing when the composer was
    empty, which is their normal state.** Their guard read `#ask-submit.disabled`, and an earlier
    round made Send disabled whenever the field is empty. They now ask the lock itself
    (`composerLocked()`, plus the sources check). Verified with a real mouse click on an empty
    composer: the chip's question runs.
  - **↻ Regenerate stuck disabled after Stop on a recovered run.** This happened after a re-mount or
    a rebuild during recovery. A button built while the lock held is disabled by construction, and
    `syncRunGuards` releases only what it marked itself. `stopWatching` now emits
    `chat:pending false` once the flag is gone. The handler derives the hold from its owners, so
    nothing another run holds is released. The harness pins the resync, and removing it fails the
    test. Verified: after F5, a re-open and Stop, ↻ Regenerate and Send are usable again.
  - Recorded as MEDIUM:
    - Clear conversation stays hidden after a fresh notebook's first answer.
    - A chip overwrites a draft in the composer.

- **Round twenty-six (confirmation): round twenty-five's fixes held for every single action. The
  judge's pairwise matrix found two more HIGHs, both fixed.**
  - **↻ Regenerate on the last turn stayed live during an overview run and got past the composer
    lock.** It emitted `chat:regenerate`, which never asked `composerLocked()`. Then the overview's
    end released the composer while that question still ran, a second question could start, and the
    first answer's rebuild dropped the second one's Stop. The root cause was that one boolean
    (`chat:pending`) had TWO owners, the overview and a question, and either one's `false` released
    both. Now:
    - The composer is held while either owner is live
      (`pending || overviewRunning || pendingTurn.pending`).
    - The notebook switch emits only after releasing both owners.
    - ↻ Regenerate is disabled whenever the composer is locked, and its handler asks the same lock.
  - **Re-opening a notebook with a recovered run cleared its recovery flag.** `recoveredRuns` was a
    Set keyed by notebook id, so the OLD mount's teardown deleted the NEW mount's flag. The composer
    unlocked, a second paid question could start, and a rebuild dropped the row with the first run's
    only Stop. The flag is now per mount (a Map from notebook id to mount), and only its owner may
    clear it.
  - Verified in the browser:
    - During an overview, ↻ Regenerate is disabled and a click starts nothing.
    - The composer unlocks after the overview ends, and again after a question ends.
    - After F5 plus re-opening the same notebook, the lock holds, Enter starts no second worker, and
      the Stop survives a rebuild.
  - The judge also found a harness trap worth keeping: `goto(<same URL>)` is not an F5. Chrome
    keeps the old document's sockets, and with two runs in flight that hits the 6-per-host cap.
    Use `Page.reload`.
  - Recorded as MEDIUM:
    - Clear conversation stays enabled during a recovered run.
    - The podcast panel does not relabel on a language switch.

- **Round twenty-five (confirmation): round twenty-four's three fixes held.** The judge ran the class
  as a matrix: 31 surface × context combinations, each with success, failure and Stop, and all of
  them passed. Combining two conditions found two more HIGHs, both fixed.
  - **The composer lock could be bypassed.** `autoGrow` recomputed Send from text and sources alone,
    and it runs on every `sources:changed`, which a language switch or a source change emits. The
    submit handler, which Enter goes through, checked nothing. So a draft plus a repaint re-enabled
    Send mid-run, and typing plus Enter submitted past the recovery guard. Either way a second paid
    question started, and one of the two ended with no Stop anywhere. The fix is one predicate,
    `composerLocked()`: a chat or overview run holds the composer, or a recovered run is in flight.
    The send button and the submit handler both ask it.
  - **A recovered run lost its only Stop to any thread rebuild.** Its row lives in `#chat-history`,
    and `rebuildHistory` restored the turns and the pending question but not that row. Removing a
    source, Clear conversation and an answer landing all wiped it. It now travels the same way the
    pending turn's row does (`recoveredRow`).
  - Verified in the browser:
    - Draft, then Regenerate, then a language switch: Send stays off, and a click starts nothing.
    - A recovered run plus Enter starts no second worker.
    - A recovered run's Stop survives a source removal and still kills the worker.
  - Recorded as MEDIUM: a failed question can land just below the fold, because the status row
    attached after the scroll leaves the thread 62px from the bottom, beyond `PINNED_SLACK`.

- **Round twenty-four (confirmation): round twenty-three's chat fix held. The same cross-notebook
  test on the other three run surfaces found the same defect in all three; all fixed.** Each run
  released SHARED state when it ended before checking which notebook it belonged to.
  - **Overview.** Both exits cleared `overviewRunning` and sent `chat:pending false` first. An
    overview ending in A unlocked B's composer mid-question, so a second paid question could start,
    and released B's own overview so a repaint wiped its Stop. `releaseIfMine()` now releases only
    while `live()`, and `onCancel` is gated the same way.
  - **Guides.** `settle()` deleted the running entry by KIND. A Summary ending in A removed B's
    running Summary, taking its dot and then its Stop. It now removes the entry only if it is this
    run's own node.
  - **Podcast.** The `finally` re-enabled Generate unconditionally. In B that allowed a second paid
    run, whose status row the first run's render then overwrote. It now re-enables only in the
    notebook that pressed it.
  - Verified in the browser. With A's run ended and B's own run still going, B keeps:
    - its locked composer and its question's Stop;
    - its overview's Stop through a language switch;
    - its Summary dot and Stop through a tab round trip;
    - a disabled Generate and a Stop for the podcast.
  - Two source-count tests now count the `releaseIfMine()` exits as well.

- **Round twenty-three (confirmation): the round-twenty-two fix held across every in-notebook
  re-render tried. One more HIGH, across a notebook switch, found and fixed.**
  - **A running chat question followed the reader into another notebook.** The chat's switch
    handler never cleared `pendingTurn`, and `askQuestion`'s catch had no generation guard (the guide
    and podcast catches did). The effects:
    - A failure landed in notebook B's thread, and its ↻ Regenerate ran A's question on B's sources
      as a real, paid run.
    - Any re-render in B drew A's question as pending, with a Stop.
    - A's `finally` unlocked B's composer while B's own question was still running.
  - Now:
    - The switch clears `pendingTurn`.
    - The success, catch and `finally` paths act only on this run's turn, in the notebook that
      asked.
    - Returning to A finds the run through `reattachInFlightRuns`.
  - Verified in the browser on both the success and failure paths:
    - B's thread stays empty through A's end and through a re-render in B.
    - With B's own question running, A's end leaves B pending with its Stop and its composer locked.
  - Recorded as MEDIUM: a run row keeps its "Starting…" label in the old language after a language
    switch.

- **Round twenty-two (confirmation): all three round-twenty-one fixes held. One more HIGH was found
  and fixed, plus two regressions or omissions of mine.**
  - **Removing a source while a chat question ran deleted that run's only Stop, and the run kept
    billing.** The chat half of the round-twenty-one guide defect, and one I introduced: round
    seventeen made source removal emit `chat:rerender`, and the rebuild drew the pending turn as a
    bare "Thinking…". The run's status row now travels with the pending turn (`statusNode`), and
    `renderTurn` re-attaches it. Verified: the Stop survives a removal and still kills the worker.
  - **The guide-tab busy dot, which round twenty-one claimed was verified, was invisible.** The tabs'
    tooltip owns `::after`, so the dot inherited `opacity: 0; position: absolute` and showed as an
    orange blob on hover. It is now a real `.tab-busy` element, measured 6×6 at opacity 1.
  - **Deleting a note had no confirmation and no accessible name.** Every other delete confirms. It
    now confirms, and is named "Delete this note".
  - Recorded as MEDIUM:
    - "Load the result" after a guide run outlives a notebook switch finds nothing, because guides
      are memory-only.
    - Keyboard focus falls to `<body>` after Stop.
    - A guide that succeeds after a mid-run source change is cached as current.

- **Round twenty-one (confirmation): the round-twenty fix held for all four guides. Three more HIGHs
  were found and fixed.**
  - **A failed overview regeneration removed the overview on screen.** Stop already restored it; the
    failure path did not. The failure now appears above the kept overview, and its ↻ Regenerate is
    the retry.
  - **A running guide lost its only Stop to any re-render**, whether a tab switch, a language switch
    or a source change, and the run kept billing. When it finished, its result was drawn into
    whichever tab was open: Summary content under the FAQ label, with FAQ's Copy and Regenerate.
    Four tabs share one `#guide-body`.
    - Each run now owns its status row in a `running` map, and `showKind` re-attaches it.
    - A result or a failure lands in its own kind; failures are kept in a `failures` map.
    - A tab with a run in flight carries a dot and `aria-busy`.
  - **Changing the interface language deleted every generated guide.** The language listener
    re-emitted `sources:changed`, which invalidates the cache. It now passes `relabel: true`, and
    the Studio re-renders without invalidating.
  - **Caught before shipping, by the browser check and not by the suite:** the first version called
    `tabs.find` on a NodeList. That throws before the request is sent, so every guide generation
    would have stalled, and all 1040 tests stayed green.
    `test_no_nodelist_is_called_with_an_array_only_method` now pins the whole class, scoped per
    function because `tabs` is an Array elsewhere. It fails on exactly that line when the line is
    reverted.
  - Verified in the browser:
    - the overview is kept on failure;
    - a Summary run keeps its Stop across tab switches and lands only in Summary;
    - a Timeline failure does not appear under FAQ;
    - a language switch keeps the guide, re-labelled.
  - Recorded as MEDIUM, not fixed:
    - A guide whose run succeeds after the sources changed mid-run is cached as current.
    - Keyboard focus falls to `<body>` after Stop.
    - After Regenerate then Stop on the last chat turn, the "(stopped)" row takes that turn's
      ↻ Regenerate.

- **Round twenty (confirmation): the podcast fix held on every failure path; the same defect was
  found once more, on the guides, and fixed.** Stopping a guide regeneration, or having one fail,
  deleted the guide the reader already had. Regenerate dropped the cache entry before the run
  started, and guides live only in page memory (invariant 38), so a reload could not bring the guide
  back.
  - The entry being replaced now travels with the run (`fetchKind(kind, { previous })`).
  - Stop restores it.
  - A failure shows its message above it, with ↻ Regenerate still offered as the retry.
  - `cacheEpoch` stops a restore from resurrecting a guide made from a corpus that has since changed.
  - Verified in the browser for both paths, including after a tab round trip.
  - Also: an empty podcast script now clears `state.podcast` too, because the server had already
    deleted that episode.

  This entry originally said the class was complete across the overview, chat, podcast and guides.
  It was not: round twenty-one found the overview's FAILURE path still removed the overview (below).

- **Round nineteen (confirmation): (a) through (f) re-checked. Five held; one found a bug in my own
  round-eighteen fix.**
  - `renderSavedEpisode` restored an episode loaded from disk correctly. For an episode generated in
    the same session, a Stop or a failed regeneration re-rendered it as "This episode's audio is
    gone" and removed Play and Download, while the mp3 was intact on disk.
  - The cause was that the success path rebuilt `state.podcast` without `audio_suffix`. It is now
    kept.
  - The restored player's URL is now versioned by the episode's run id, like the fresh path:
    otherwise the plain URL could replay the previous episode's cached bytes.
  - Verified in the browser: generate, then Regenerate, then Stop leaves the player, Download and
    the transcript on screen.
  - Also: the Notes help text now names the ☆ star rather than the retired "+ Save as note".

- **Round eighteen (desktop scope): three design HIGHs, all fixed and re-measured in a real
  browser.**
  - **Copy covered the first line of a Summary or Insight guide.** Round seventeen's corner
    reservation covered chat answers only. `.guide-prose` now gets the same right float, sized down
    to Copy's bottom edge: a float of 1.5rem let Insight's second line run under Copy's last 4px.
    There is now no prose under Copy on any of the four kinds, light or dark.
  - **Timeline dates measured 3.72:1 in Paper.** A new `--studio-accent-text` token (the
    `--accent-text` split, for the Studio hue) brings them to 5.93:1.
  - **The address link inside an open reference measured 4.20:1.** It now uses `--accent-text` and
    measures 4.72:1.
  - **Print (was MEDIUM, cheap).** The page now opens with the notebook's title, because the header
    it lived in is hidden in print. The overview's regenerate button, the "N references" buttons and
    the chat panel label no longer print.
  - **Function judge: `VERDICT: COMPLETE`**, with no BLOCKER and no HIGH on any core journey. Two of
    its MEDIUMs were cheap and misleading on a core journey, so they are fixed and checked in the
    browser:
    - Stopping or failing a podcast regeneration blanked the existing episode until a reload.
      `renderSavedEpisode` now puts it back.
    - With no sources, Enter still submitted. The question was lost, and the reply quoted the
      server's internal id. The submit handler now applies the send button's gate.
    - Also fixed: "1 steps".
  - **Recorded as MEDIUM or POLISH, not chased:**
    - At 400% zoom the header, tab row and composer leave a short reading window.
    - The "File into…" picker's border is faint.
    - A queued node is shown by colour alone.
    - Two focus rings are clipped.
    - Assorted polish in the judge's report.

- **Round seventeen: six HIGHs from two judges, all fixed. The review loop now stops on a
  severity bar.** The user noticed the rounds were drifting toward rare races and ceremony and
  changed the stop condition. The work is done when judges find no BLOCKER or HIGH on the core
  journeys (capture → notebook → ask/cite → Studio → export) at desktop and phone widths. Rare races
  and polish are recorded here and no longer chased round by round.

  Function judge:
  - **Removing a source left chat and podcast citations to it shown, copied and exported as
    verified until a reload.** The handler never took `turns` from the response. `renumberStrokes`
    now re-stamps the verdict along with the number.
  - **Deleting a notebook mid-overview left a paid run with no Stop.** `/overview` runs two tasks
    against one `_ACTIVE_RUNS` slot. `_run_isolated` now holds the counted `_BUSY` guard itself.
    Reproduced in both registration orders.
  - **Medium: one Ctrl-C still waited out TTS synthesis (40.1s measured).** `asyncio.run` joins the
    default executor, however the request was cancelled. Long host-side calls (synthesis, fetch, PDF,
    OCR) now run on a daemon thread through `_abandonable`, and the same probe exits in 3.6s. Notebook
    writes stay on `to_thread`, because a write should finish.
  - **Medium: exports from pasted text broke their own lists.** List items are now one line
    (`markdownInline`), and the raw `pasted:… #hash` origin no longer appears.
  - **Polish:** guide Copy headings read `## summary`; a failed guide had no retry, and a late failure
    could land in the wrong notebook. Both fixed.

  Design judge (measured in a real browser before and after):
  - Three of its four HIGHs were earlier fixes lost to CSS cascade order. **Skip link** painted under
    the header (z-index tie). **Copy** fell into the flow because `[data-tip] { position: relative }`
    outranked it; it now sits beside the star, and a right float reserves the corner, so neither
    control covers prose. **Save-as-note on touch** was opacity 0 because a later rule beat the
    `any-hover: none` escape. The escape now comes last in the file, and
    `test_the_touch_escape_comes_after_every_rule_it_overrides` pins the order.
  - **Dark-theme print** was 1.23:1. Both dark palettes are now `screen`-only, and it measures 17.3:1.
  - **Medium:** `renumberStrokes` stamped a number on every fragment of a split stroke ("¹a
    ¹parametric¹"). It now stamps only the fragment the renderer marks `data-stroke-end`.

  **Recorded, not fixed this round.**
  - Function judge:
    - A Stop is shown during synthesis that can do nothing.
    - The Notes empty state still names "+ Save as note".
    - A refused Inbox upload shows a temp path instead of the file name.
    - Back after deleting leaves `?nb=` in the address bar.
  - Design judge:
    - Export floats mid-header and hovers in the destructive colour.
    - The reference address link is 4.20:1.
    - Print omits the title and still shows the regenerate and "N references" buttons.
    - At 320px the sticky Save in settings has no backing band.
    - A queued node is shown by colour alone.
    - A failed node's actions mix three sizes.
    - The trajectory transport clips its focus rings.
    - Focus order inside a card jumps back up to the star.
    - Seven polish items.

  **Narrow windows: one panel at a time.** Below 640px a notebook now shows one panel at a time,
  switched by a sticky Sources · Chat · Studio tab row. Scope note: this is a DESKTOP application
  (the planned Tauri shell; `serve` binds loopback, so a phone cannot reach it). I first framed and
  prioritised this as a "phone layout" without checking that scope, and the user caught it. Narrow
  widths matter only as a narrow desktop window or 400% zoom (WCAG 1.4.10 reflow). The user decided
  to keep the tab row on that footing, and touch-only issues are at most MEDIUM.
  Measured at 375 and 320:
  - The conversation starts at y=149 instead of about 700px down, and the composer stays pinned to
    the bottom edge.
  - A notebook with no sources opens on Sources.
  - A citation click switches to Studio › References.
  - Arrow keys move between the tabs (WAI-ARIA tabs), and each panel keeps its own scroll position.
  - Desktop is unchanged.

  Three things the narrow view exposed:
  - A Studio collapse remembered from a wide window took over the narrow grid. Collapse is a side-column
    state, so it now applies only above 1024px; the preference is kept and re-applied when the
    window is wide again.
  - `1fr` let a long reference title widen the column to 512px. It is now `minmax(0, 1fr)`, and
    the overflow had been hidden because `.cols` is itself a scroller.
  - The grid rows stretched and made the tab row about 200px tall on short panels.

  Also from the list above: Export and Clear now sit together on the right of the chat header, and
  only Clear hovers red. The stale overview heading no longer runs under Copy.

- **Round sixteen. Round fifteen's shutdown fix could not run, and the export it added carried
  wrong numbers and dropped a whole guide's text.**

  **The server could not be quit while a run was in flight (B1).** `Server.shutdown()` ends in
  `await server.wait_closed()`, which since Python 3.12 waits for every open connection, and
  `force_exit` does not break out of it. The judge reproduced it against the shipped `serve`:
  SIGTERM, then four SIGINTs, and the process stayed up. The only exit left was SIGKILL, which
  reparented the worker and its grandchild to init, still billing. That also made round fifteen's
  `_lifespan` cancel loop dead code, because uvicorn skips `lifespan.shutdown()` on a forced exit and
  `_ACTIVE_RUNS` is empty by construction when it does run. The test written for that loop put
  `FakeRun`s in the map by hand and could see neither fact. `cli._cmd_serve` now passes
  `timeout_graceful_shutdown=3`, so one Ctrl-C cancels the open request, and `_run_isolated`'s
  `except BaseException` kills the process group. SIGHUP gets a handler that re-raises it as
  SIGTERM. **The first draft raised `KeyboardInterrupt` from that handler instead. It passed its unit
  test, but run live it crashed the event loop with a traceback and no lifespan teardown.** Verified
  live after the change, with a stand-in worker that leads its own process group and has a sleeping
  grandchild in it: one SIGHUP, then "Shutting down … Finished server process", and both processes
  gone. The replacement test runs the real `_cmd_serve` and fires the handler it installed. It no
  longer asserts that `"SIGHUP"` appears in the source, which a comment would satisfy.

  **Copy on a Timeline dropped every event's text (H2).** `guideMarkdown` read `event.what`, a field
  the server has never sent (`schema.TimelineEvent` declares `description`), so a copied timeline
  was a list of bare dates. The harness fixture had been written to match that line rather than the
  wire, so its assertion passed on an input the product cannot produce. Fixed, along with the
  fixture. A new tripwire (`test_the_client_only_reads_guide_fields_the_schema_declares`) reads the
  pydantic models and fails on any `event.`/`item.`/`utterance.` field they do not declare. It is
  scoped to the functions that consume each payload, because `event` is also every DOM handler's
  argument. Mutation-checked: restoring `event.what` fails both it and the export test.

  **Reference numbers still ran out of reading order on five of seven surfaces (H3).** Round
  fourteen's `inReadingOrder` was applied to the overview and the chat turns only. The podcast and
  all four guide kinds render the same numbered stroke and were numbered in the order the model
  emitted them. Measured: identical citations numbered `s1, s2, s3` in the overview and
  `s3, s1, s2` in a Summary guide, and the Markdown export carried that list out. Each surface now
  sorts against its own prose (an utterance's `text`, a guide's `text`, an FAQ item's `answer`, a
  timeline event's `description`).

  **Deleting a notebook during TTS synthesis orphaned its episode (H4).** The delete endpoint's 409
  reads `_ACTIVE_RUNS`, which empties when the subprocess returns, and synthesis runs entirely after
  that. So a DELETE mid-synthesis answered `{"deleted": true}`, and the handler then wrote the mp3
  back. The next notebook to take that id was served the previous one's audio. There are two fixes.
  `_BUSY` (slug-keyed, counted) holds a notebook for the whole `audio` request, and the delete guard
  reads it. Separately, if the podcast record write fails, the mp3 written just before it is
  cleared. That closes the one interleaving the guard cannot: DELETE checks and then deletes across
  an `await`. Each half has its own test, driven from inside `synthesize`, and each fails when its
  half is reverted.

  **`tests/readable_error_parts.mjs` was untracked (H5)**, and 45 tests import it, so a commit of
  the index as it stood would have shipped a suite that fails on checkout. It is added now, and
  `.coverage` is ignored.

  **Printing kept the citation numbers and hid the list they point at (M6).** `@media print` hides
  `.col-studio`, where `#panel-references` lives, and the stylesheet's comment claimed the opposite.
  Un-hiding the panel would not fix it, because the panel is only built while its tab is showing.
  `installPrintReferences` builds a list at `beforeprint` from `collectReferences()`, the same order
  every mark was stamped from, and removes it at `afterprint`. It prints nothing on the Inbox and
  never stacks a second list. The "(unverified)" label in both this list and the Markdown export is
  localized now (`copy.unverified`), where the export had hardcoded English.

  **Docs (P7).** `README.md` now describes Copy, Export and printing. `AGENTS.md`'s scope note names
  the export surface and adds `_BUSY` to the in-memory maps that have no multi-worker story.

  **Not acted on: P8.** Exported prose carries no inline marks, so outside the app a list that
  starts at "3." has nothing in the text to attach to. The judge called this deliberate, and so did
  round fifteen. It stays recorded here.

- **Round fifteen. The product could not hand over the thing it exists to produce, and quitting it
  left paid runs running.**

  **Quitting the server orphaned every in-flight run.** The worker is spawned
  `start_new_session=True` so `killpg` can take its Deno grandchild with it (invariant 22) — and
  that same flag puts it in a DIFFERENT session, so the terminal's Ctrl-C and a terminal close's
  SIGHUP never reach it either. Reproduced against the shipped `serve`: the first Ctrl-C made the
  server wait for the whole run; the second left the worker and its `deno` child reparented to init
  and still billing, until their own wall-clock backstop — up to 1500s on the API path and **9000s
  on the subscription path**. No `/cancel`, no UI, no signal, and a restarted server knows nothing
  about it. Invariant 47 failing at the one moment the reader has decided to stop everything.
  Shutdown cancels every active run now, and `_run_isolated` cancels on the way out of a cancelled
  await — the same one-line gap in both places, since the `finally` that forgets the run is exactly
  what makes it unreachable.

  **The product had no way out for any artifact.** `README.md` and `AGENTS.md` describe the purpose
  as "get a distilled research artifact out the other end"; measured across 8,269 lines of
  `app.js`, `navigator.clipboard` appeared ONCE — copying a markdown link's URL — there was no copy
  on an answer, the overview or a Guide kind, no export of any kind, and `@media print` matched
  ZERO rules, so Cmd+P printed the three-column application shell. The only export in the product
  was the podcast's audio file. And the one remaining route, select-and-copy, was broken by the
  citation click handler firing on the mouseup that ends a drag — a guard the podcast transcript's
  line handler has carried, with exactly that argument, since it shipped. There is now a Copy on
  every artifact surface, an Export that writes the whole notebook as Markdown, and a print
  stylesheet; what leaves carries the SAME numbered reference list the panel shows, with an
  unverified citation marked as such, so an artifact cannot launder a claim that failed
  verification.

  **A persisted Audio Overview whose file is missing rendered a fully armed, dead transport.**
  `audio/file` 404s, `play()`'s promise rejects, and the rejection is swallowed on purpose — so
  pressing Play produced nothing at all: no toast, no state change, no message, on the most
  expensive artifact the product makes (invariant 64) and the one it persists deliberately (42).
  Reachable by any backup restore or a desktop sync that moves the JSON without the blob. The
  server already says so (`audio_suffix: null`), so the state is stated and the transcript kept.

  **The reading-order fix from round fourteen was not a consistent ordering.** The comparator read
  `a.seen < 0 || b.seen < 0 ? a.at - b.at : …`, so ONE span-less citation dragged its neighbours
  back into emission order: `[s3(Gamma), sX, s1(Alpha)]` came out `s3, sX, s1` and the reader met
  `[3] … [1]` — the same defect, reintroduced in the case the product's own prompt asks for
  (`instructions.py` tells the model to omit `answer_span` when it cannot point precisely, and
  `locate_answer_spans` nulls any span it cannot find verbatim, so a MIXED array is the designed
  common case). Only the locatable citations are permuted now, among the positions they already
  hold, which is consistent by construction and makes true the claim that a span-less one does not
  move. The shipped test covered only the two PURE cases, which is why one defect was invisible.

  **Two write sites could still resurrect a deleted notebook**, and promote needed no race at all: a
  stale picker option was enough, because the options come from the notebook list fetched when the
  Inbox rendered. `create` is now what the CALLER meant — the UI mints an id for "a new notebook"
  and says so — and the note path keeps lazy creation while refusing to undo a delete. Also: a file
  NAMED `https://example.com/paper.md` took `node_id_for`'s origin-only branch, so two such uploads
  collapsed to one node with the second discarded under `refused: []`, and the id collided with a
  real capture of that URL. The capture PATH decides identity now, not a `startswith` on a string
  the caller chose.

- **Round fourteen's mediums, taken rather than deferred.**

  **The one irreversible action was distinguished from Cancel by border hue alone**: identical
  background, identical text colour, 1.49:1 between the two borders. WCAG 1.4.1 and 1.4.11, and
  against every platform HIG for a destructive confirmation — the whole point is that the dangerous
  button should not be the one you press by muscle memory. It differs in three ways now (fill, text
  colour, border), with a `--bad-text` token joining `--warn-text`/`--accent-text` so the label
  measures 6.70:1 in Paper and 5.99:1 in Study instead of 3.93.

  **Reflow failed at 320 CSS px** — 400% zoom on a 1280px display, which is what SC 1.4.10 actually
  asks for. `scrollWidth 331` against `clientWidth 320` in the English interface, and the first two
  attempts at it measured as having changed nothing: no element's own rect passed 320, because the
  11px came from a TOOLTIP's generated content. `overflow-x: clip` on the header (not `hidden`,
  which would create a scroll container and break the sticky composer) removes the phantom scroll
  while leaving the Y axis visible, so the tip still drops below the bar and the notebook menu still
  escapes it.

  **Three surfaces still spoke English to a Chinese reader**: `Host A`/`Host B` once per line down a
  transcript of up to 90, `Thinking…` in the same pending bubble whose live ticker said 思考中…, and
  the twelve `TRAJ_META_LABELS` chips that are the whole "Initial state" panel of the Trajectory
  drawer — rendered raw in the same function that REJECTS the server's `timing_note` because
  "interface copy belongs to the interface" (invariant 48).

  **`/DESIGN.md` — a 47 KB internal spec — answered unauthenticated.** `auth.PUBLIC_PATHS` is derived
  from the contents of `web/`, justified as "the static assets, which carry nothing private"; that is
  an argument about assets and a design record is not one, and the derive-from-the-directory rule
  made anything dropped in there public by default. The allowlist filters on asset suffixes now, so
  deny-by-default holds for the next thing added.

  **Stop did not reach the batch that had not started yet.** `cancel_pending` bumps
  `_cancel_generation` for exactly this reason — and `_auto_distil_after_intake` read that counter at
  ENTRY, i.e. after the bump, then wrote `cancel: False` over the flag the reader had just set. A
  paid batch began milliseconds later with `should_stop()` already false. The automatic pass refuses
  to start while the flag is set and no longer clears it; a NEW capture is the deliberate act that
  turns it back on.

  **Reference numbers ran 1, 3, 4, 6, 5 down one answer.** The interface owns the numbering
  (invariant 48.5 exists so there is exactly one scheme) and assigned it in the order the MODEL
  emitted citations. `answer_span` is the model pointing at its own prose (invariant 49), which is
  precisely the coordinate for sorting by where the reader meets each mark; a citation with no span
  keeps its array position, because nothing locates it.

  Also: the source viewer was the widest reading surface in the product with no measure and the
  chrome face (97.5 cpl in Public Sans; now 65 in Literata, sharing `--chat-measure`, which moved to
  `:root` because a measure scoped to the chat column could not reach it); the Inbox's full text was
  a mono `<pre>` for every kind, so a captured page containing a 520-character URL became a
  horizontal scroller that **WKWebView does not make keyboard-reachable** — prose gets the reading
  face and wraps, and the mono block stays for the scanned pages whose alignment is the point;
  dropping a file on an open notebook refused and pointed elsewhere while the Sources panel 300px
  away did exactly what the drop implied; `#panel-studio` was a tab stop while containing focusable
  children; and `count_nodes`' comment claimed "one cheap query at thousands of rows" when
  `json_valid()` on four unindexed columns makes every count a full scan — 11.89ms against 0.15ms at
  30,000 rows. The filter is kept (the alternative is a spend action announcing a total it can never
  reach) and the comment now carries the measurement and names the schema migration that is the
  prerequisite for fixing it properly.

- **Round fourteen, the design judge: the collapsed Studio rail was four blank squares, and I
  deleted the markup that filled them.**

  Round thirteen's ARIA pass rewrote the four Studio tab buttons to add `id`/`aria-controls`/
  `aria-selected` and dropped their `<span class="tab-icon">✦︎</span>` in the same edit. The CSS
  that turns the collapsed rail into an ICON strip survived in three places, so collapsing it —
  Enter on the focused splitter, a double-click on the grip, or any drag under 170px, all persisted
  to `localStorage` — removed Guide, Podcast, References and Notes behind four unlabelled 32px
  squares with no visible way back. Accessibility made it worse rather than rescuing it: with
  `.tab-label` at `display: none` the accessible name fell back to the tooltip, so a screen reader
  announced "A two-host audio overview" and never the word "Podcast". The glyphs are back, the label
  is `.sr-only`-hidden rather than removed from the tree, and a tripwire now fails on any class a
  rule styles and the product never creates — which found 16 more, all dead CSS from three
  superseded designs (the citation-detail slot, the pre-`ref-card` reference list, the inline trace
  console), now deleted. `DESIGN.md` §10 already recorded this exact shape once for `.distil-btn`
  and nothing failed on it either time.

  **Round thirteen fixed the outer tab strip and left the two inside it.** `#guide-tabs` and
  `#source-kind-tabs` carried which one is current in an underline ALONE — no role, no
  `aria-selected`, no roving `tabindex`, no arrow keys, four and three separate tab stops — and the
  podcast Length group, which decides what the next press COSTS (invariant 63), had no
  `aria-pressed`. `DESIGN.md` §5.4 calls the guide strip and the view strip "the same idiom"; only
  one of them kept the promise. SC 4.1.2, fixed one level up and left open one level down inside the
  same panel.

  **A source's title was readable nowhere and announced nowhere.** `sourceDisplayName` returned the
  HOST, so the row's `aria-label` said "Open arxiv.org" and overrode its own content, the source
  viewer headed itself with the host, and `.src-title` is line-clamped to two lines with no tooltip
  — three surfaces, one cause. The Inbox's whole thesis is that if recall cannot be visual it has to
  be typographic; a title truncated everywhere and absent from the accessibility tree is neither.

  **The Trajectory strip drew a 180ms call as 67% of an axis labelled 1:39.** `renderTrajTimeline`
  normalises segment widths by the sum of tool `duration_s` while the axis printed the run's wall
  clock, so on a 99.1s run the 40.6s the model spent thinking between calls was drawn as nothing and
  a 2.9s sub-LM call got the same 108px floor as a 2ms validator. A true label over an untrue
  layout, which is what invariant 60 forbids. The axis names what the strip partitions — tool time,
  formatted so sub-second totals do not all floor to `0:00` — and the wall clock stays on the header
  stat, where it is true. Laying out against `total_s` instead is the other fix and is wrong here:
  `TRAJ_SEG_MIN_PX` exists because these calls are milliseconds, so every segment would become a
  sliver with no room for a label.

  **And the first test written for that axis was theatre.** The scenario rebuilt the expression by
  hand instead of extracting it, so reverting the product to the wall clock left it green. The logic
  is a named `trajAxisLabel` now and the scenario runs that one; the same mutation fails.

- **A designed outcome reported as a network fault.** `UNREACHABLE` matched the bare words "timed
  out" anywhere and was tested above every provider branch, so a run that hit
  `RN_RUN_TIMEOUT_SECONDS` — the thing invariant 68 exists for, since a `long` podcast asking for
  60-90 accumulated utterances could not fit under the 300s default — told the reader "Could not
  reach that address." for a run in which no address was involved, immediately after they had paid
  for a 5x-budget episode. `runner.py` names the knob in the message precisely so they can act on
  it; the branch kept the knob in the raw text and threw the diagnosis away. A dead local model
  server (the commonest first-run failure for BYOK) read the same, and a proxy answering a model
  request with a sign-in page put 645 characters of raw `<!doctype html>` in a toast. Four failures,
  four sentences, with the source-URL one now reached only when it is not about a run or a provider.

  **And the two harnesses that build `readableError` each carried their own copy of its parts.**
  Adding three constants to one left the other silently assembling a DIFFERENT function — not an
  error, just the wrong sentence in two scenarios, which is how the fix above was caught only by an
  unrelated test. `tests/readable_error_parts.mjs` is the one list now: renaming a constant in
  `app.js` fails loudly in both, where before it failed in one and lied in the other.

- **Round fourteen: two blockers, both on paths round thirteen was working in, both mine.**

  **Five paid endpoints ran a full model loop against an EMPTY corpus.** Round thirteen closed "the
  one place a press spends money for nothing" on `ask` — and `guide` (four kinds) and `audio` never
  had the check, so the Studio guides and the Audio Overview each spawned a run whose corpus blob
  was the empty string. The podcast is the most expensive action in the product
  (`PODCAST_TIMEOUT_FACTOR["long"] = 5.0` over 60-90 accumulated utterances, invariant 64), and its
  Generate button was LIVE on a source-less notebook: the four guide tabs are gated by `showKind`,
  but `#podcast-generate` is static markup whose only guard was "is a notebook open", and the
  selected Studio tab is remembered — so pressing "+ New notebook" lands a reader who last used
  Audio on an enabled button. Fixing the INSTANCE rather than the CLASS is what left five more, so
  there is one `_require_sources` now and a tripwire that fails on a sixth handler reaching
  `_run_isolated` without it — including a checked exemption for `_resolve_language`, which spawns
  a run of its own and is reachable only from the five.

  **`DELETE /notebooks/{id}` answered `{"deleted": true}` and the notebook came back.** Its own
  docstring names that outcome as what its 409 prevents, but the 409 reads `_ACTIVE_RUNS`, which is
  populated only AFTER `runner.start_run` returns — so it covers spawned runs and not ingestion,
  which this file elsewhere says "can take minutes". A source landing after the delete re-created
  the file through `create=True`, holding only that source: every earlier source, note, turn,
  overview and podcast gone, and the Inbox membership rows already dropped. Reachable by dropping a
  scanned PDF, thinking better of it, and pressing the ✕ the picker puts on every row. `create` is
  now "it was not there when we started" rather than a constant, at all three sites — a concurrent
  delete makes the write FAIL, which is the right way round, and `ask` gives up a paid answer rather
  than resurrect a notebook the reader deleted. Second half of the same guard: `_ACTIVE_RUNS` is
  keyed by the raw id and the file by `slug(id)`, so `"Reading List"` and `"Reading-List"` were two
  keys and one file — the alias spelling walked straight past the 409.

- **Round thirteen, third pass: the mediums worth taking now.** One tab stop per citation, not
  one per fragment — a stroke crossing an inline `**` is emitted as several spans, and making every
  one operable turned a single reference into three identical-sounding buttons, two of them
  announcing no number at all, since only the last fragment carries `data-reference`. Keyboard-only,
  and it arrived WITH the keyboard fix. The composer's disabled send glyph was still dimmed by
  `opacity` at 2.77:1, the one control the "fill goes quiet, label stays readable" pass missed. The
  References link printed "1 references." three times on one screen, in English only. The theme
  toggle's label named the action and never the state, so no screen reader could tell Paper from
  Study — and the splitter's `aria-valuenow` was the literal `50` written in the markup, so an AT
  user pressing the arrow keys it handles so carefully was told nothing had moved. `SourcesRequest`
  was the one request model without `extra="forbid"`: the singular typo `{"source": [...]}` answered
  200, created the notebook and added nothing.

- **Round thirteen, second pass: the four HIGHs left open after the blockers.**

  **The product had a colour system and no size system.** 24 distinct `rem` font sizes and 29
  spacing values, with zero `--text-*`/`--space-*` tokens — ten of the font sizes between 0.68 and
  0.85rem, steps of 0.16-0.32px that nobody can perceive and that guaranteed no two labels in
  different components ever agreed (inside ONE Inbox failure banner: `.distil-error` at 0.78 with
  `.distil-error-count` at 0.76). The strongest evidence it was drift rather than a decision: the
  Inbox rebuild reached for a scale and, finding none, defined `--ib-gap` scoped to itself. Both
  scales take their steps from the MODES of what was already there rather than an invented ratio, so
  retrofitting cost at most 0.80px on any type declaration and moved only 7 of 269 spacing
  declarations by more than that — 146 and 205 declarations converted, `--ib-gap` re-pointed at the
  global scale as a semantic alias, and a test that fails on any new literal. Fourteen spacing steps
  is more than a scale wants; thinning it is now a safe change to make one component at a time,
  which it was not before.

  **The locked-out screen rendered the whole application as live.** No `?token=` — which an ordinary
  bookmark produces, and a mis-handshaked Tauri sidecar too — gave a facet rail, "+ New notebook",
  Settings and a FOCUSED capture field, all dead, with the remedy being a line of body text telling
  the reader to hand-edit a URL. There was no field anywhere in the product to paste a token into,
  although the app already persists one. There is a gate now: it replaces the surface, inerts
  everything behind it (the drawer's own treatment), takes focus, and writes to the key the app
  already reads.

  **A settled turn was never re-scrolled**, so after a failed question 83px sat below the fold
  containing both of that turn's actions — `Steps` and `↻ Regenerate`. The one affordance that
  recovers from the error was the one you could not see. Re-pinned only if the reader was already at
  the bottom, because yanking someone back while they read an earlier turn is the same bug the other
  way round.

  **Focus was dropped to `<body>` in two keyboard paths**: closing the notebook switcher with Escape
  (the next Tab restarted at the skip link), and the `Steps` pill retiring, which set `disabled` on
  the element the reader was standing on. `aria-disabled` keeps it focusable and inert, and the
  retirement sentence is now a `role="status"` so it is announced rather than merely drawn.

  Also: `.ask-hint` has been tuned for contrast three times and failed a fourth measurement at 3.54,
  because `opacity` multiplies whatever is underneath and the surface under it changed again when
  the composer gained a sticky background. "Recedes until engaged" is a colour decision, so it is
  made in colour now — dim at rest, full strength on focus — and the decorative middot beside it is
  `aria-hidden` rather than dimmed below the floor.

- **Round thirteen. Seven blockers across two judges, and one of them was a claim made in this
  file.** Both verdicts were NOT YET; every blocker is fixed, reproduced first and mutation-checked.

  **The CHANGELOG said a regression "fails instead of hanging CI". It hung.** Round twelve's
  `_DISTIL_GUARD` split shipped with two tests: one drives the deadlock through a real request, the
  other through a proxy that refuses re-entry. The proxy one fails in 2s; the one ABOVE it in the
  file never returns, and pytest runs a file top-down — so the regression hung the whole suite past
  600s with no `pytest-timeout` and no `timeout-minutes`, which reads as "cancelled" rather than
  "this test failed". The second test's own docstring is the argument against the first
  ("a worse CI failure than the bug"). Both use the proxy now: the same regression fails in 2.15s.

  **The UI reported a live notebook as deleted.** `promote_node` keys memberships on
  `slug(notebook_id)` — right, because the slug identifies the FILE — while `GET /notebooks`
  returned the id inside the file and no slug, so the two ends could never meet. Every node filed
  into a notebook whose id differs from its slug rendered "In a deleted notebook" while that
  notebook sat live in the same row's own picker. Unreachable from the web UI alone (invariant 37
  mints `nb-<uuid8>`, whose slug is itself) and reachable from the first
  `--notebook "reading list"`, or any CJK name, which is what invariant 10's hash fallback exists
  for. `NotebookSummary` carries `slug` now; `NotebookResponse` always did.

  **A notebook could not be deleted from anywhere** — no endpoint, no CLI verb, no control — so once
  one existed it was permanent, and emptying it left "Untitled notebook · 0" in the facet rail
  forever. The product ships Forget for a node and ✕ for a source, and `app.js` even carried the
  string "a deleted notebook" for a state nothing could produce. `DELETE /notebooks/{id}` now
  removes the file, its audio (invariant 42's one-file-per-notebook is what made retention a
  non-question) and its membership rows, refuses with 409 while a run is in flight — deleting under
  a worker would let `mutate_notebook` re-create the notebook it just deleted — and leaves the nodes
  alone, because promotion COPIES (invariant 78).

  **`playground/smoke.mjs` was failing and nobody had run it.** Round twelve added
  `POST /inbox/distil/dismiss` to `api.py` and `app.js` and not to the shim, which is the exact
  drift the playground's route-coverage check exists to catch — and CI runs neither `build.py` nor
  `smoke.mjs`, so the guard was only as good as somebody remembering. The same correspondence is
  now a pytest, and it caught the next one immediately: it failed on `DELETE /notebooks/{id}` the
  moment that endpoint was added, before the shim learned it.

  **Below 640px the composer was at the end of the document.** The one-scroller decision for phones
  is right and it left the primary verb 9,934px down a 10,776px page on a 25-turn notebook — twelve
  viewport-heights, growing with every turn, and below the fold even on an EMPTY notebook because
  the Sources rail is 701px. Sticky inside `.col-chat`, with an opaque background and a top hairline
  because content now passes under it. Verified: sticky at 375 and 640, static at 700, no overflow.

  **The skip link — the first tab stop on every screen — pointed at a hidden element.**
  `#capture-input` lives inside `#view-inbox`, which is `hidden` whenever a notebook is open, so in
  a notebook it moved focus nowhere, left a dead fragment in the address bar and named a destination
  that is not on that screen. SC 2.4.1 unsatisfied and SC 2.4.4 on the label. Both halves follow the
  view now, and the press focuses the field itself rather than trusting the fragment.

  **`role="tablist"` and `role="listbox"` were declared and never fulfilled.** `aria-selected` did
  not appear ONCE in the product: all four Studio tabs reported "not selected", and the notebook
  menu was a listbox whose options were `<button>`s with an interactive sibling, which is not a
  listbox in any assistive technology. The tabs are a real tablist now (`aria-selected`,
  `aria-controls`, `role="tabpanel"`, roving `tabindex`, arrow/Home/End keys); the menu drops the
  roles it could not keep and marks the current notebook with `aria-current`. While wiring that:
  `#facet-inbox` had `is-current` hardcoded in the markup and nothing ever removed it, so the rail
  claimed the Inbox was current from inside a notebook.

  **Three AA failures in the default theme, and one of them was round twelve's own doing.** Promoting
  the citation superscript to the RESTING mark moved the whole burden of the signature interaction
  onto the smallest type in the product: 8.93px at 4.20:1. The injection-scan flag — invariant 6's
  entire transparency mechanism — measured 2.35:1, and the Trajectory strip's state glyphs 1.98:1
  for the one that means "the validator rejected this". A signal colour and a text colour are not
  the same colour: `--warn-text`/`--accent-text` join `--field-border` as tokens that exist because
  a signal was reused as type. The superscript is 0.72em now and measures 6.45:1 in a browser,
  sanity-checked at 21.00.

  **And the one place a press spent money for nothing.** `PUT /title` and `POST /overview` both
  refuse a source-less notebook; `ask` did not, so the composer accepted a question 20px from a
  panel reading "Add a source first" and ran a full model loop against an empty corpus. A 422 and a
  composer that says why.

  Also: the page had **no `<!DOCTYPE html>`**, so the whole product rendered in quirks mode — nothing
  visibly broken (no `<img>`, no `<table>`, `box-sizing` already reset) but every vertical position
  on the reading surface 8px off the CSS as authored, in a product that measures characters-per-line
  to two decimals. `/inbox/upload`'s 411 guard — invariant 30 on the DEFAULT drop target — could be
  deleted with all 999 tests green, because `TestClient` always sends a `Content-Length`. And the
  manual summary pass re-derived the inbox directory from the process cwd while the auto pass passed
  the queue's resolved one, which is the asymmetry `IntakeQueue.__init__`'s comment was written to
  close, on the other half of the same feature.

- **Round twelve. The function judge found a single authenticated GET that ends the server, and the
  design judge found that one dropped request fabricates the reader's notebook.** Both verdicts were
  NOT YET; every blocker is fixed, reproduced first and mutation-checked after.

  **`POST /inbox/distil` self-deadlocked the event loop whenever there was nothing to summarise.**
  `_DISTIL_GUARD` is a plain `threading.Lock`, and the `total == 0` early return called
  `_distil_status()`, which takes the same lock. The handler is `async`, so the deadlock was on the
  ASGI event loop: the server answered nothing further, static page included, and survived SIGINT
  and SIGTERM — only SIGKILL ended it. Every existing test posts with pending nodes, so the branch
  was executed by nothing, while the shipped UI reaches it by design (`app.js` has a `started:
  false` branch whose comment records it firing in the wild): a stale count, a second tab,
  auto-distil finishing first, or a node deleted between the poll and the press. Split into
  `_distil_snapshot()` (no lock, caller holds it) and `_distil_status()` (takes it). Deliberately
  NOT an `RLock`, which would silence the next nested acquisition instead of preventing it — and a
  test now fails if anyone swaps it, alongside one that drives the branch through a proxy which
  refuses re-entry rather than waiting, so a regression fails instead of hanging CI.

  **`openNotebook`'s bare `catch` treated every failure as "does not exist yet".** Blocking one
  request to a notebook with four sources and two turns rendered it as: "Untitled notebook", no
  sources, "Ask a question once you've added a source.", an empty notices rail, and the `?nb=`
  dropped from the address bar. Four false statements about the reader's own data, no error, no
  retry, and it did not heal when the request started working — while "Add source" from that screen
  writes into a notebook the reader believes is empty. It also discarded what the server had gone
  to the trouble of saying: invariant 27 makes a corrupted notebook file a 409 carrying the sentence
  that says how to fix it, and the boot path turned that into "that notebook is not here any more".
  `api()` now carries the status on the error, the placeholder is gated on a `fresh` flag that only
  the two id-minting call sites pass, and the boot path's redundant existence probe is gone.

  **The signature interaction was mouse-only.** `DESIGN.md` §2 calls the citation stroke "the
  literal visual expression of the product's core value"; it had a `click` listener and nothing
  else — no `tabindex`, no `role`, no key handler — and a recorded walk of 37 tab stops through a
  notebook reached no citation at all. SC 2.1.1 and SC 4.1.2, both Level A. Now `tabindex="0"`,
  `role="button"`, Enter and Space, a `:focus-visible` ring, and the reciprocal highlight on focus
  as well as hover. Verified in a real browser: 13 Tab presses reach a citation, which draws a 2px
  accent ring. The test runs the real `renderAnswerWithCitations` over the real markdown renderer,
  so it covers the split-fragment case too.

  **The reading surface had no measure on the machine most of its readers use.** Measured with each
  block's own font advance: the chat answer ran 82 characters per line at 1440, 133 at 1920 and
  **203 at 2560**, and the overview 99 / 163 / **247**, while `.inbox-inner` held 544px at every one
  of those widths. The product capped its measure on the scanning surface and not on the reading
  one. `--chat-measure: 38rem` on the block (not the column, so the gutters grow instead of the
  line): now 52 and 61 cpl, constant from 1440 to 2560. The overview was also the one prose surface
  the reading face never reached — Public Sans 14.4/21.6 directly above Literata 14.4/24.48, through
  the same render function — and is now `.chat-overview-body`.

  **The citation underline had become the thing the wash was moved for.** An independent review
  measured a real overview at 1,996 characters with 16 strokes covering 1,914 of them: 95.9%, a
  solid slab harder to read than plain text, answering "which part of this is grounded?" with "all
  of it". The resting mark is now the superscript number; the stroke arrives on hover and focus,
  one claim at a time. An UNVERIFIED stroke keeps its dashed rule at rest, because a warning that
  only appears when you point at it is not a warning.

  Also fixed: a rejected `fetch` reached the reader as Chrome's "Failed to fetch", untranslated even
  in a zh-Hant interface, never saying that the page had lost its own loopback server — all three
  browser spellings now answer with what to check. A failed summary pass was IMMORTAL: process
  state that only the start of the next pass cleared, so one failure installed a banner on the
  default screen for every later visitor, in a brand-new browser profile, with no dismiss — there is
  a server-side dismiss now, refused with 409 while a pass owns the fields. `_` was a live `LIKE`
  wildcard in the Inbox search, so `my_notes` also matched `myXnotes.txt` (`%` stays a wildcard: that
  one is a recorded decision, and nobody types it by accident). A client disconnect during a spawn
  skipped `except Exception` — `CancelledError` is a `BaseException` — leaving `_RUN_PROCESSES[id] =
  None` and its trace file reserved for the life of the process, so that (notebook, token) pair
  409'd forever. The podcast transcript's timecode measured 2.55:1 in Paper and 3.57:1 in Study
  (failing AA in both, and 1.4.11 in Paper, since it is also the seek control) because
  `--studio-accent` was inherited and then multiplied by `opacity: 0.75`. The Studio's outer tab and
  its own first child tab were both called "Summary", 120px apart, one containing the other.

  **The product had no keyboard shortcuts at all**, which an independent review called its clearest
  "web page, not app" tell and the one that matters most for the planned Tauri shell: a window with
  none is a browser tab with the chrome removed. Every global `keydown` in `app.js` handled exactly
  one key, `Escape`. There is now ⌘/Ctrl-K (the primary field of the screen you are on — capture on
  the Inbox, the composer in a notebook), ⌘F (find, going home first if you are in a notebook), ⌘,
  (Settings), a skip link as the first tab stop, and the capture field focused on the screen built
  for capture — it was the SIXTEENTH stop, behind three header controls and one per notebook, a
  list that grows. Each binding reports whether it acted and only then swallows the browser's own:
  the find field is hidden on an empty Inbox, and taking ⌘F away to do nothing would be worse than
  not binding it.

  **A disabled control lost its label, not just its fill.** `opacity` dims the whole button, so
  "Add source" measured 1.52:1 and the capture send glyph 1.23:1 — invisible — while the copper
  block behind them stayed the loudest thing on the rail, on the first-run screen, at the moment a
  reader is deciding whether Enter does anything. Now the fill goes quiet and the label stays
  readable: 6.68:1 in Paper and 6.58:1 in Study, measured with the sanity check at 21.00. The worst
  case was `.ticker-toggle.is-absent`, which delivers a SENTENCE — "This run left no trace." —
  through a `disabled` button and so inherited a control's WCAG exemption for free at 3.36:1.

  **Two files with the same name both landed and one of them could never be filed.** Round eleven's
  `node_id_for` fix made them two nodes, which is right; promoting the second into a notebook that
  already held the first was a hard refusal with no way out, because nothing here renames a node or
  a source. Invariant 79 lands the capture and invariant 78's promotion was a dead end one step
  later. The display origin is disambiguated now (`notes (2).txt`) — neither silent nor shadowing,
  since both sources exist, both are citable, and the name says which is which. Two tests that
  pinned the refusal now pin the property the refusal was protecting: each source keeps its own text
  and its own membership.

  **The audio player was the browser's, on the artifact this product is proudest of.**
  `<audio controls>` rendered Chrome's stock black pill — play, slider, volume, a `⋮` overflow menu
  — inside a hand-drawn ink-on-paper panel, and it was the last un-themed surface in the product:
  the native file picker was replaced for showing OS chrome in the wrong locale, and the scrollbars
  and `<select>`s were themed for the same reason. It is also the worst one to leave
  cross-platform, because a Tauri build is WKWebView on macOS, WebView2 on Windows and WebKitGTK on
  Linux — three genuinely different players. The element is headless now and drives a transport
  built from this product's own parts: a circular play button, a copper-thumbed scrub and a tabular
  clock. A real `<button>` and a real `<input type="range">`, because both are keyboard-operable and
  nameable for free and re-implementing a slider's drag/arrow/Home/End behaviour buys nothing —
  with `aria-valuetext` carrying the TIME, since a range otherwise announces "437". `preload` moved
  from `none` to `metadata` so the duration is known before the first press without pulling the
  episode. Verified in a real browser: play, pause, live scrubbing, and the transcript's
  `.is-speaking` following the handle.

  **The harness lied about itself in both directions, one round after being fixed for the first.**
  Round eleven closed three stated gaps and left the header claiming they were open — which is
  worse, because a reviewer trusting it skips a test that is writable. Meanwhile the one real
  remaining limit (document-level queries are still tables) was stated nowhere, and `El` had no
  `tabIndex`, `href` or `data-*` mapping, so `[tabindex]`, `a[href]` and every `[data-*]` clause of
  `trapTab`, `trajTakeFocus` and `FOCUSABLE_TARGET` matched nothing and were deletable green. Worse,
  `test_starting_a_run_is_what_makes_the_guard_fire` said in its own docstring that deleting
  `runStatus`'s first statement was now caught; deleting it left all 979 tests passing, because the
  scenario calls `noteRunStarted` directly and the shim had no `document.createElement`. Pinning a
  function is not pinning the call to it. The shim now has `createElement`, `createTextNode`,
  `classList`, attributes and event dispatch, so `runStatus`, the markdown renderer and
  `renderAnswerWithCitations` are executed rather than simulated.

  **One of the round's findings was wrong, checked rather than assumed.** `promote_node`'s in-lock
  `prior_membership()` read was called a no-op subsumed by the blocks comparison below it; removing
  it fails `test_re_promoting_a_node_whose_text_changed_is_still_idempotent` every run, because a
  node's text can move and the copied source then no longer matches. The comment says so and names
  the test. Doc drift closed with the round: the README sent readers to "the URL `rlm-notebook
  serve` prints", which does not exist (it prints a token; uvicorn prints the address, deliberately,
  because an address announced before the bind is one an occupied port then fails to serve) — and
  the lockout message pointed at the same non-existent thing. `kind_for` and `ingest_one` held
  parallel copies of the same four-branch dispatch while both docstrings claimed one was factored
  out of the other.

- **Round eleven, the function judge: a citation could say `verified: true` about text it had never
  read.** Three blockers, all reproduced before being fixed, all mutation-checked after.

  **Removing the HIGHEST source freed its id.** `next_source_id` was `max(live ids) + 1`, which is
  right only while the removed source is not the top of the range — and both tests written for
  invariant 12 removed a MIDDLE source, so both stayed green. Delete `s3` from `s1,s2,s3`, add
  anything, and the new source is `s3`: the citation saved against the old one comes back
  `verified: true`, because `citations.py` checks that a coordinate EXISTS and never that it still
  means what it meant (invariant 5), while opening a document that never contained the quote. The
  allocator is now a persisted high-water mark (`schema.Notebook.source_seq`) that only rises, and
  it has to be persisted rather than re-derived because `api.py` drops the Inbox's membership rows
  for a removed source on the stated promise that its id "will never come back" — rows in a store
  `notebook.py` cannot read. Notebooks already on disk recover a mark from the source ids the file
  still references; a tripwire walks the schema for `source_id`/`source_ids` fields and fails if the
  recovery scan misses one, which it did on its first run (a podcast utterance carries citations).

  **One authenticated `GET /inbox` could end the server process.** `max_corpus_chars()` was the last
  statement of the handler and the only unguarded `_env_int` reader left on a request path.
  `SystemExit` is a `BaseException`, so Starlette's error middleware never sees it: a raw
  `text/plain` 500, and then the process exits — on the default screen, from a typo in an env var
  startup did not reject. Converted to a 500 (invariant 24) AND pre-read in `_lifespan`, the same
  pairing the retention knobs and `auto_distil_max_per_batch` already have.

  **Two uploaded files with the same name were one node, reported as two.** `node_id_for` hashed the
  origin whenever it was non-empty, and an upload's origin is its filename; `add_node` is idempotent,
  so the second file found the row already there and its bytes were discarded while the batch
  answered `{"nodes": [A, A], "refused": []}`. Invariant 79 broken in the one way it cannot be seen,
  since nothing failed. A filename is not an identity, so every origin now folds in the text —
  except a URL, which must stay origin-only because a queued capture mints its id before the fetch,
  and `capture_into_inbox` refuses anything that is not `is_url` before the queue. This also
  silently falsified `promote_node`'s justification for its blocks-equality branch ("two DISTINCT
  nodes sharing an origin necessarily differ in text"), which was untrue while a filename decided
  identity alone.

  **A lock-order inversion with nothing to time out.** `_enqueue` took `_idle` then `_guard`, while
  `stop` and `cancel_pending` hold `_guard` across `_drain`, which reaches `_idle` through
  `_finish_one`. Latent rather than routine, which is what makes it worth pinning: it would surface
  as an unreproducible hang. Racing for it would prove nothing, so the test asserts the PROPERTY —
  both locks are wrapped in a proxy that records what each thread holds when it takes another, and
  any pair seen in both orders fails, anywhere in the class.

  **Round ten's drawer fix had no test, and the harness could not have caught a repeat.** Both
  reverts left the suite green. The shim's own header listed the gap honestly ("hiding a focused
  element blurs it to `<body>`; this does not") and two more: `querySelectorAll` returned `[]` for
  every selector, so `trapTab`'s body was unreachable and `if (true) return;` at the top of it left
  961 tests passing. The harness now matches the selector subset `app.js` writes, refuses to focus a
  hidden or disabled element, and blurs on hide — so the wrong order can be reproduced through the
  shipped `trajTakeFocus` and lands on `<body>`, and `trapTab` is executed by a test for the first
  time. The scenario's control order is `index.html`'s, deliberately: put the search box first and
  the `:not(:disabled)` clause deletes green.

  **A page that blocks bots was reported as a bad API key.** `FROM_PROVIDER` matched the literal
  `litellm` anywhere, and every URL in the test guarding this was `example.com` — so capturing
  `https://docs.litellm.ai/...` and getting a 403 sent the reader to change a credential that was
  fine. A URL says what a message is ABOUT, never where it came FROM, so provenance is now decided
  with URLs stripped. Same shape as the `\b499\b` gate directly above it.

  **`kind_for` and `ingest_one` were the second dispatch that both their docstrings warned about.**
  Each held its own copy of the same four-branch chain while claiming one had been "factored out" of
  the other — true about the intent, false about the code, and one edit from a `.pdf` URL filed as
  `web`. `ingest_one` reads `kind_for`'s answer now, and a test fails if they can diverge.

  **One of the round's findings was wrong, and the check is worth recording.** `promote_node`'s
  in-lock `prior_membership()` read was called a no-op subsumed by the blocks comparison below it.
  Removing it fails `test_re_promoting_a_node_whose_text_changed_is_still_idempotent` on every run:
  a node's text CAN move, and when it has, the source copied at promotion no longer matches the
  node's current blocks, so the equality test refuses the promotion as a conflict with itself. The
  membership row is the only thing that still knows they are the same capture. The comment now says
  so and names the test.

  Doc drift closed with it: the README called the server's token "one-time" (it is per-process and
  every request needs it), `.env.example` attributed `RN_AUTO_DISTIL`/`RN_AUTO_DISTIL_MAX_PER_BATCH`
  to `auth.py`/`api.py` when both are read by `config.py`'s own functions and omitted
  `RN_MAX_CORPUS_CHARS` from the read-both-ways list, invariant 79's file described the shared
  dispatch as fact rather than as the thing that had drifted, and `openTrajectory` still carried a
  paragraph recommending the `alert` that the comment immediately below it says was removed.

- **A tenth round, and the first thing both judges confirmed is that NOTHING was billed.** Every
  model path died at `Missing credentials` before any network I/O. The previous round's briefs had
  neutered `OPENAI_API_KEY`, which is not the variable that authenticates — `RN_API_KEY` is, and the
  repo's `.env` defines it — so ~186 runs were billed across earlier rounds. Both briefs now empty
  `RN_API_KEY`, `RN_BASE_URL` and `RN_SUB_MODEL`, forbid sourcing `.env` outright (the README and the
  product's own error text both recommend that incantation), and tell the reviewer to stop and say
  so if a model action ever succeeds. Verified by resolving `NotebookConfig.from_env()` under that
  environment before dispatching: `api_key` empty, `base_url` empty, `sub_model` falling back to
  main.

  **The Trajectory drawer opened with focus on `<body>` on every path a person can actually take.**
  `trajTakeFocus` focused the drawer's first focusable, `#traj-run` — and `renderTrajectory` then ran
  `trajEl.run.hidden = runIds.length < 2`, hiding the element that had just been focused, which
  blurs it. Every persisted "Steps" pill opens with ONE run id, so the picker was always hidden and
  focus always landed outside an `aria-modal="true"` dialog: two Tab presses to reach anything, with
  the page behind hidden from a screen reader the whole time. It stayed invisible because the drawer
  opens correctly from `trajShowDrawer()` alone, which is the path every probe used. Render first,
  focus second, and never target a `[hidden]` control. **And closing it returned focus nowhere**: the
  recorded trigger is a `.ticker-toggle` inside a chat turn, which any re-render replaces, and
  `.focus()` on a detached node is a silent no-op.

  **The commonest BYOK first-run failure printed raw provider text on the Inbox front page.** Two
  independent causes: `Missing credentials` was not a shape `BAD_KEY` knew, and `LEADING_NOISE` is
  `^`-anchored so a class-name prefix SHIELDED the `[openai/gpt-4o-mini]` tag from the only rule
  that strips it. The strips alternate until nothing more comes off now, `CLASS_NAME` learned
  litellm's dash separator (`OpenAIException - `), and `FROM_PROVIDER` learned that `RLMTaskError`
  has no word boundary before `LM`. The sentence also names **`RN_API_KEY`** — the variable the
  product actually reads — where the provider's own wording named three credentials this product has
  no concept of.

  **Two instrument errors, both mine, both caught before they shipped a wrong fix.** The contrast
  helper read the colour TOKEN and ignored `opacity`, so it reported 5.63 where the painted pixel was
  3.70 — on the composer hint, whose whole design is an opacity. That is the second time a number
  here came from a helper measuring something other than what a reader sees, and the rule now reads
  every ancestor's opacity into the foreground alpha. And the `web_dom_harness` header claimed to
  enumerate its limits while omitting three real ones, including the exact gap that hid the drawer
  blocker: it does not model "hiding a focused element blurs it".

  Also from the function half: **pressing Stop on a recovered run leaked the recovery flag** — a
  second teardown path bypassed the only `recoveredRuns.delete` there is, so every later in-tab run
  took the composer away for the life of the tab; `promote_node` read its membership snapshot
  OUTSIDE the lock, so ten concurrent promotions of one node produced eight false 400s blaming a
  source their own siblings had just created (invariant 34's named fault, at Tier 0); and
  `playground/build.py` never copied the newly-added `favicon.svg` or `web/fonts/*.woff2` and never
  rewrote CSS `url()`, so the published page 404'd five assets and fell back to system faces — on a
  page whose entire premise is that it IS the shipped UI.

  **Four fixes shipped in earlier rounds had no test at all**, each proven by reverting it with the
  whole suite still green: `syncRunGuards` (the one priced in money), the tooltip restore,
  `_MAX_CANCELLED_IDS`' placeholder eviction, and `IntakeQueue.submit`'s own stopped guard. Worse,
  `noteRunStarted` — the single line that populates `activeRuns`, on which the entire run guard
  depends — was testable by nobody, because one half is driven with `activeRuns` injected and the
  other with `runStatus` stubbed. All five are pinned now, and the harness gained the scenarios to
  do it: pressing Stop, a detached trigger, the seam between the two halves.

  Docs: `.env.example` said "six are NOT read by `from_env`", named five, and counted one that IS —
  it names the properties now, because the count is what went stale; invariant 41's headline said
  three settings where the paragraph below it already explained the fourth; `README.md`, the
  `Dockerfile` and `cli.py` all called `audio/` a working-directory path when it is
  `notebooks/audio/`, and the Dockerfile's mount note — the one place that tells an operator what to
  persist — omitted `inbox/`; and one incident was written up twice with two different numbers, in
  the very paragraphs arguing that counts rot.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **961 passed**;
  `smoke.mjs` at the same 13 "0 recorded runs" failures, plus three new assertions that every asset
  the built page references exists and none is absolute. Every fix mutation-checked; every contrast
  number re-measured through opacity with the helper sanity-checked at exactly 21.00 first.

- **A ninth round. Its sharpest finding is that the harness built to stop this project asserting on
  names instead of behaviour was itself asserting on a model the browser contradicts.**

  `tests/web_dom_harness.mjs` gave its fake element a plain own `inert` boolean. Real `inert` is
  INHERITED by the whole subtree — `app.js` says so in its own comment — and the difference was not
  academic. `#notices` lived inside `.layout`; the Trajectory drawer is a body-level sibling, so it
  inerts `.layout` and takes the toast rail with it by inheritance. `ALWAYS_LIVE = "#notices"` could
  never fire for the drawer, because `#notices` was never a sibling on the drawer's walk path. The
  harness said the rail was live, a real browser said it was inert, and the test passed over a
  half-applied fix: the previous round's toast fix worked for the three `.modal-overlay` dialogs and
  did nothing for the one surface invariant 70 calls "where a run's reasoning lives".

  That is the third time this project has shipped a stub that ignores what the real object does
  (`_Response.read(size)` ignoring `size`; `readableError`'s regex literals; this). The shim models
  inheritance now and answers `inertly`, the scenarios read it, `#notices` moved to body level where
  the exemption can actually reach it (`position: fixed`, so nothing moved on screen), and a source
  assertion pins that placement — because a harness whose tree drifts from the markup answers a
  question nobody asked. The first version had BOTH mistakes and they cancelled out into a green
  test over a broken product.

  **And `syncRunGuards` — the previous round's one fix priced in money — shipped with no test at
  all.** `if (true) return;` in its body left all 945 green. Fourth instance of the same failure, in
  the newest code, in exactly the class the harness beside it exists for; it simply had not been
  pointed at it. Four mutations now go red, including "the guard touches a control something else
  disabled" and "the guard ignores which notebook the run is on".

  **An unreadable index row was invisible, immortal, and still billed for.** The previous round made
  `list_nodes` skip it so `GET /inbox` would stop 500ing — and `count_nodes` is a separate
  `COUNT(*)` over the same WHERE, so `total` went on including it: measured `total 3, rows 2`,
  `Load more` offered on a page already holding everything, and a real summary pass reporting
  `done 3 / total 4`, a number on the spend action that can never be reached. Every per-node
  endpoint answered `400 "invalid node id"` about an id that is perfectly valid — the same mis-blame
  fixed one endpoint over — **including `DELETE`, the only verb that could have cleared it.** The
  count now shares the listing's readability filter (`json_valid`, SQLite's own, so it stays one
  cheap query), the message names the ROW and points at the fix, and `DELETE` no longer resolves the
  row it is about to remove.

  Also: the run guard DELETED a static tooltip instead of restoring it, so a control lost its help
  text for the rest of the session after a run it had nothing to do with; `traces._effective_max_tokens`'
  two-seat `min()` was unpinned, which is the artifact the previous round added it for;
  `IntakeQueue.submit`'s stopped check releases its lock before the enqueue, so a `stop()` in that
  window still produced a permanent `queued` node and a leaked counter — the guard is inside
  `_enqueue` now, under the lock that owns the counter; a cancelled-before-spawn id could leak its
  `_RUN_PROCESSES` placeholder for the life of the process if a handler raised before the spawn,
  making `cancel_run` answer "stopped before it started" for that id forever. And `AGENTS.md`'s node
  requirement stated a COUNT that rotted inside the same slice that added the second file, so it
  states the property instead.

  **The design half of the same round found three more, all on the reload-recovery path the
  previous round had just worked on.**

  - **After a reload the composer was unguarded, and one press bought a second billed worker.** The
    run guard deliberately exempts `#ask-submit`, arguing "the pending turn is its own guard" — true
    in-tab, and exactly what a NEW tab does not have. Measured with writes stubbed: a real
    `POST /ask` with a fresh run id, from both the composer and the last turn's `↻ Regenerate`. And
    since `_run_isolated` overwrites the one slot `_ACTIVE_RUNS` keeps per notebook (invariant 23),
    Stop then reaches only the second run and the first cannot be stopped at all. The exemption now
    holds only while the run is one this tab started.
  - **The live trace died permanently on the second Inbox↔notebook round trip during a run.** Each
    `reattachInFlightRuns` mount starts a 2.5s poll that outlives it, so the PREVIOUS mount's
    teardown looked the run id up, found the NEW mount's stream, and closed it — born at t+13324ms,
    killed 584ms later, no `EventSource` created again, while the clock and Stop kept promising
    otherwise. The exact inverse of the collision `openTicker` was taught to avoid one round
    earlier, through the same lookup. A teardown may now only close the stream it opened.
  - **A recovered run that FAILED said "That run has finished" and offered "Load the result"**,
    which loaded nothing and said nothing, on the one path with no other channel, after a call that
    was billed. The ticker's terminal event is where the page can learn this; the same failure
    WITHOUT a reload had always rendered correctly, so the machinery existed and the recovered path
    simply could not tell the two apart. The neutral wording is "ended" now, because "finished" is a
    claim.

  Plus `.ref-card-unverified` — the one label that says a citation could not be resolved — at
  **4.17 / 4.14**, the third element in this family to be moved off a colour that was doing the
  word's job.

  **And the tests for all three are the point of the round.** The first attempt reproduced the
  failure this project has now hit four times: the guard scenario INJECTED the recovery flag, so
  `recoveredRuns.add` and `.delete` could both be deleted with every test still green, and seven of
  nine mutations survived. `tests/web_dom_harness.mjs` runs `reattachInFlightRuns` itself now, with
  one-line stubs for its collaborators and four modes — a run that fails, one that ends cleanly, one
  where the poll wins and no terminal event ever arrives (the race the recovery exists for, and the
  only mode where the mount's own teardown is load-bearing), and a notebook switch mid-run. All nine
  mutations go red. One mutant that survived turned out to be genuinely equivalent, and the
  redundant branch that made it so was deleted rather than left looking load-bearing.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **953 passed**;
  `smoke.mjs` at the same 13 "0 recorded runs" failures. Every fix mutation-checked; the contrast
  number measured with the helper sanity-checked at exactly 21.00 first.

- **An eighth round, and its first finding is that round seven did not learn round seven's lesson.**
  Round seven deleted a `readableError` test for asserting on a function's regex literals instead of
  calling it — and then wrote two more of the same shape, for the two fixes it had itself called
  blockers. An independent review replaced `closeTicker`'s whole body with a no-op, and
  `trajTakeFocus`'s with `if (true) return;`, and **all 931 tests stayed green** both times. A
  source-text assertion cannot see reachability, ordering, or whether a call does anything.

  `tests/web_dom_harness.mjs` + `tests/test_web_behaviour.py` run these functions against a small
  fake DOM, and seven mutations against them all go red — including the two that were invisible. The
  harness states its own limit: it answers `querySelector` from a table rather than parsing CSS, so
  a broken SELECTOR is still only covered by the source assertions, which is why those keep the half
  they can genuinely see (a NEW `aria-modal` element in the markup must be named before the test
  passes) and lose the half they could not.

  **Two regressions the last round introduced, one root cause.** `inertEverythingExcept` inerts
  every sibling — and two siblings are the overlay's OWN machinery, not the page behind it.
  `.traj-backdrop` carries `pointer-events: auto` and a close listener, so **click-outside-to-close
  on the Trajectory drawer silently stopped working** while the CSS and the listener both still
  promised it (Escape and ✕ still worked, which is why nothing noticed). `#notices` is where every
  toast lands, so a toast raised FROM a dialog had a dead ✕ — the click passed through to the dialog
  behind it — and was never announced, because `inert` removes the subtree from the accessibility
  tree too; `notify` defaults to `life = 0` for a bad tone, so it never went away either.

  **And `openTicker` re-entered its own leak per run.** A second ticker for one run id overwrote the
  map entry and ORPHANED the first stream: its own `onerror` looks itself up, finds the newer entry
  or nothing, and returns — so nothing could ever close it and it reconnected every few seconds for
  the life of the tab. Reachable by asking in notebook A, navigating away, and coming back while it
  still runs. Same cliff the map was added to stop.

  **A corrupt blocks file broke three things at once.** `node_source` returns `None` for a MISSING
  file and RAISES for a truncated or wrong-shape one, after `claim_node` has already written
  `distilling`. So the summary pass aborted mid-batch (every later node silently skipped), the node
  was stranded in `distilling` — which nothing selects, `/inbox/cancel` cannot reach, and only a
  restart recovers — and because `distilling` is one of the UI's busy states the Inbox then polled
  about twice a second for the life of the tab with its progress strip hidden: invariant 79's named
  failure, one state over. `GET /inbox/{id}/source` let it escape as a bodyless 500, and
  `POST /inbox/{id}/promote` caught `ValidationError` broadly and blamed the NOTEBOOK — telling the
  operator to remove by hand a `notebooks/<id>.json` that parses perfectly well. `promote_node`
  raises `inbox.UnreadableNodeText` from the one call that knows which file it was reading.

  **The `max_tokens` clamp was applied to one of its two seats.** `RLMConfig` carries ONE
  `max_tokens` and `rlm_harness.configure` builds both LMs from the same kwargs, so a split-role
  install — which `README.md` advertises and invariant 35 supports — handed the sub LM a value its
  own provider refuses outright. The lower of the two ceilings is the only number both seats accept.
  Invisible by default, because `RN_SUB_MODEL` inherits `RN_MAIN_MODEL`: the same reason the main
  seat's version survived seven rounds.

  Also: a membership was keyed on the RAW notebook id while the file is keyed on its slug, so
  `"Foo Bar"` and `"Foo-Bar"` were one notebook on disk and two rows in the index — and after a
  removal through one spelling, the next promotion handed the same source id to a different
  document; a failed note save wiped the text the reader had typed, because `addNote` swallowed its
  error and left the caller on the success path that clears the field; `settingsDraft` could outlive
  a failed reload and be re-applied on the next open; `readableError` still printed the status code
  and the URL for any fetch status outside the five it named (402, 406, 451 and a bare 400 are
  ordinary paywall and bot-block answers) and read a website's 499 as "You stopped this one.";
  `tickerLogs` was a `Map` accumulating every event of every run, read by nobody, described by a
  comment naming a consumer that had stopped existing; the Trajectory drawer's Initial-state panel —
  the one artifact whose job is "how much rope did it have" — reported the UNCLAMPED budget;
  `IntakeQueue.submit` had no `stopped` guard, so a capture racing shutdown returned a permanent
  `queued`; and ONE unparseable row turned `GET /inbox`, the application's front page, into a
  bodyless 500 so that nothing rendered at all.

  Docs: `AGENTS.md`'s Verify section now records that **`node` must be on PATH and the suite FAILS
  without it** (hide it and the result is 9 failed, 0 skipped — deliberately, for the same reason
  the `importorskip` trap above it gives), the multi-worker list gained the four in-memory maps it
  had missed, and invariant 30's file stopped naming a mechanism the code had replaced. A route
  count rotted inside the comment arguing that counts rot.

  **The design half of the same round, and its first item costs money.** After a reload
  `reattachInFlightRuns` puts the run indicator and its Stop back — and every run-STARTING control
  came back live, because each one's guard lives in the tab's memory and the tab is new. One press
  of Generate podcast then bought a SECOND worker: measured as two run ids, two `rlm_notebook.worker`
  processes and two status rows counting in parallel, with nothing said. That is verbatim the
  failure `reattachInFlightRuns`' own comment says it exists to prevent. The guard is driven off
  `activeRuns` now — the map `runStatus` already keeps for the header dot — so a recovered run
  counts exactly like one this tab started, and it never touches a control something else disabled
  for its own reason.

  - **All four Studio tab labels ellipsised in English at every desktop width**: "Summary & anal…",
    "Podc…", "Referen…", "Not…", with no `title` to recover them (the tip existed only on the
    collapsed rail). `#col-studio` is a fixed 340px at 1280 through 1920, and zh-Hant fit — so it
    was the DEFAULT language that lost. Shortened rather than tooltipped, because the panel below a
    tab says what it holds: once "Summary & analysis" became "Summary" the other three fit as they
    always should have. Verified uncut at 1280/1440/1920 in both languages, with tips added anyway
    for the translations this will meet later.
  - **Two AA failures in Paper, the default theme**: `#podcast-generate` at **4.20:1** and
    `.source-block-locator` at **4.10:1** — the second inside the source viewer, one of invariant
    31's three deliberate whole-document exposures, on the coordinate a reader checks a citation
    against. `.btn-danger` four rules below already stated the answer for its own identical
    measurement ("the LABEL is `--text`; the colour lives in the border and the hover wash"), and
    `.btn-offer` had not been given it. Now 13.60 and 7.36.
  - **The capture send button stayed a saturated enabled primary over an empty field after any file
    capture, for the rest of the session**, doing nothing when pressed — twelve lines below the
    comment recording that exact defect being fixed on the TEXT path. No control assigns this
    button's state by hand any more; a test forbids it.
  - The drawer's Initial-state chip and its budget note printed **two different generation caps in
    one viewport** (32768 vs 16384), because `traces.run_meta` read the `NotebookConfig` value that
    the previous round's clamp had made fictional — on the one artifact whose whole job is invariant
    75's third reading.

  Also: five Trajectory playback controls were the only `data-tip`s in `index.html` with no
  `data-i18n-tip`, so a Chinese interface announced "⏮ Previous step" two elements from one saying
  關閉; the notebook picker's tooltip rendered at `left: -46px` at 375, off-screen, on the only
  control that reaches a notebook on a phone; an expanded row's `<pre>` is a focusable scroll
  container matching none of the focus-ring floor's selectors and wore Chrome's stock cobalt outline
  in an ink-and-copper palette — and set whitespace-significant text in a proportional serif, so a
  two-column capture lost its alignment; Settings' Save, the only global money-spending write in the
  product, reported **nothing at all** on success while its failure path notified; `readableError`'s
  output is prose now but was still set in `--mono`, a leftover from when it was a raw dump; and a
  fullwidth `＋` survived in the English UI at the second of its two sites.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **945 passed**;
  `smoke.mjs` at the same 13 "0 recorded runs" failures. Every fix mutation-checked; every contrast
  number measured with the helper sanity-checked at exactly 21.00 first; and click-outside-to-close,
  the in-dialog toast, the reload guard, the tab widths, the send button and the save toast all
  re-confirmed in a real browser.

- **A seventh round, and three of the four function blockers were in code the sixth round had just
  written.** The lesson is the test, not the bugs: `readableError` was rewritten last round and
  pinned by a test that re-compiled its regex LITERALS with Python's `re` and never called it.
  Replacing the whole function body with `return String(text || "")` left all 917 tests green —
  while the shipped function returned the EMPTY STRING for two of the commonest provider failures,
  so a real error rendered as a blank `.distil-error-why` and a toast whose only content was its own
  ✕. Pinning a function's inputs is not testing the function.

  `tests/test_readable_error.py` RUNS it now, through node, against strings captured from a live
  server, and CI installs node so it can never silently skip. Eight mutations were tried against it
  and all eight go red. The old test is deleted, and the deletion is commented as the point.

  **What that function was actually doing.**

  - `TRAILING_BLOB` was unanchored and matched `[`, so it began at the `[vendor/model]` tag in
    position 0 and ate everything. It is braces-only now, keeps the character before them, and the
    tail ends `return cleaned || raw` — a guess about what is noise that eats the whole sentence is
    strictly worse than the raw text it replaced.
  - `BAD_KEY` carried `\b40[13]\b` and `OVER_QUOTA` `\b429\b`, matched against the whole message —
    so a website answering 403 to a capture was reported as *"the model provider rejected the API
    key. Check it in your environment"*. A paywalled or bot-blocked page is the commonest capture
    failure there is. The provider branches are gated on a PROVENANCE test now, and a fetch failure
    is translated into what its status means rather than having its number printed.
  - `NO_SUCH_MODEL` carried `Received Model Group=`, which is litellm's router boilerplate and
    appears in every router error — so the `max_tokens` failure below rendered as *"your provider
    has no model called gpt-4o-mini"*, sending the reader to pick another OpenAI model that fails
    identically, while the Inbox strip on the same page blamed something else.
  - `\b500\b` matched `'code': 500` inside a provider's JSON payload.

  **And the fourth: the shipped `RN_MAX_TOKENS=32768` made every model call fail for the model this
  repo's own `.env.example` names.** Most models people run have a lower completion ceiling —
  `gpt-4o` and `gpt-4o-mini` 16384, `gpt-4-turbo` and `claude-3-opus` 4096, `gemini-2.0-flash`
  8192 — and OpenAI refuses an oversized `max_tokens` BEFORE it checks the key, so the request never
  left the machine and a valid key changed nothing. Proven by an A/B on a live server where
  `RN_MAX_TOKENS=8000` reached the provider and the default did not. `config._max_tokens_for` clamps
  to the model's own ceiling and LOGS both numbers once per process rather than correcting silently
  (invariant 9's rule); an unknown model keeps the operator's value, because the metadata is a
  convenience and refusing to run over a missing table row would break every self-hosted setup. It
  survived seven rounds because it is invisible to anyone whose own model has a ≥32k ceiling.

  **`openTicker` had no close handle, and `reattachInFlightRuns` leaked one SSE socket per notebook
  open.** Measured: at six opens the page could no longer make ANY request to its own server —
  `fetch` stalled past eight seconds against Chrome's per-origin HTTP/1.1 cap while `curl` answered
  the same server in two milliseconds. The row lifecycle round six added was correct; only the
  streams leaked, because the one caller that awaits nothing had no way to end what it opened.

  **The design half found two more places an argued rule had been applied to one of its sites.**

  - **The Trajectory drawer claimed `aria-modal="true"` and kept none of it** — no focus taken,
    nothing marked `inert`, and six consecutive Tabs reached the wordmark, the notebook picker,
    Settings, the URL field and the destructive ✕ that removes a source. `aria-modal` makes that
    worse than an honest non-modal: it hides the page behind from a screen reader's virtual cursor
    while leaving every control on it reachable. Round two built the machinery for the Settings
    dialog and `inertEverythingExcept` already knew about this drawer; it just never ran for the one
    surface invariant 70 calls "where a run's reasoning lives". Measured after: zero focusable
    controls outside the drawer, focus returned to the trigger, nothing left inert.
  - **Changing the interface language inside Settings silently discarded every unsaved change in
    the same dialog** — including `auto_distil`, the setting that decides whether captures spend
    money. Set the output language to Japanese, turn auto-summary on, correct the interface
    language, press Save, and you saved auto-summary OFF. The dialog was being rebuilt by clicking
    its own open button, which re-ran `openModal` on an already-open dialog and dropped focus on the
    floor. It RELOADS now, carrying a draft of what the reader had typed.

  Also: twelve static controls carried a hardcoded English `aria-label`, which overrides both the
  element's text and its translated `title`, so a Chinese interface announced "Go to the Inbox",
  "Settings", "Toggle theme", "Capture", "Ask" — `data-i18n-label` routes them, and the key
  tripwire that should have caught the five new keys did not know the attribute existed either;
  three money-spending surfaces still printed the literal `（錯誤）` prefix round two banned, and
  five surfaces now share one `failureBlock` with the Inbox row's measured treatment; four elements
  inside the Trajectory drawer failed AA (the budget note's tag at **2.13:1**, which is the thing
  that drawer exists to say); `document.title` did not follow a live language switch; Add source and
  Add note were silent no-ops on an empty field while the two fields beside them disable themselves;
  `distil_pending` counted a node with a missing blocks file as done with no failure; a doubled
  ellipsis, a fullwidth `＋` in the English UI, a missing `aria-live` on Find, and a resize handle
  with `role="separator"` and no value attributes.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **931 passed**;
  `smoke.mjs` at the same 13 "0 recorded runs" failures. Every fix mutation-checked; every contrast
  number re-measured from painted pixels with the helper sanity-checked at exactly 21 on
  black-on-white first.

- **A sixth round, and both judges independently found the same defect** — a source in a notebook
  could be DELETED by keyboard and not OPENED by one. Two rows in this product had already been
  given a real control for exactly that reason (`button.node-open` in the Inbox, after round three
  found it; `button.ref-card-head` in the references), and the source row was still a bare `<li>`
  with a click handler whose only focusable child was the destructive ✕. It reaches
  `GET /notebooks/{id}/sources/{source_id}`, one of three deliberate whole-document exposures
  (invariant 31), so "you can see it with a mouse" was the entire feature. The head is a real
  button now, named by the source rather than by the word "Open", with the description left outside
  it so the prose stays selectable — and the three rows are pinned together, because learning this
  once per row is what produced the third one.

  **The design half's other two blockers.**

  - **The facet rail's tie-breaker printed `1970/1/22` on every notebook.** `new Date(b.updated_at)`
    on epoch SECONDS, where both siblings multiply by 1000. So the rung that exists BECAUSE the
    three above it tied was itself byte-identical across notebooks, 56 years wrong, and long enough
    that the rail's 13rem clamp ellipsised it away. Fixing the arithmetic was not enough: a date
    cannot separate notebooks promoted in the same minute, and three of them still rendered
    identically. The ladder had run out of rungs, so it gains a terminal one that cannot tie — an
    ordinal, which is what a file manager does, and not the notebook id (invariant 37, and round
    five caught that handle leaking onto the public playground).
  - **`.turn-failed-head` measured 4.27 / 4.37 against AA's 4.5** on the tinted block it sits on.
    `.node-error-head` is the same element on the other surface; its rule already carried *those
    exact two numbers* as the reason it had been moved off `--bad`. Found, argued, written down,
    applied to one of the two places it applies — this project's recurring shape, so the two are now
    paired by a test. Measured after: 13.91 / 12.55, which are the twin's own numbers.
  - **Every failure surface printed raw `litellm`** for the commonest BYOK failure there is: a
    bracketed model tag, a dotted exception class, an HTTP status, a Python dict repr and a literal
    two-character `\n`, in the chat bubble, the summary strip, the podcast panel, the overview and
    the capture note. `readableError`'s two strips were `^`-anchored and every real message nests
    the class behind something — `[openai/gpt-4o-mini] litellm.AuthenticationError:` leads with a
    bracket, `422: could not ingest: PdfiumError:` carries it in the middle — while the capture note
    cleaned a string its own callers had already wrapped, which killed both anchors by construction.
    It now recognises the three provider failures (bad key, quota, no such model) and the two parser
    ones, keeps the MODEL STRING because that is the actionable half, and strips noise wherever it
    sits. The live ticker was the surface still leaking after the first pass, and is included.

  **The function half's other blocker: a recovered run never ended.** `reattachInFlightRuns` was the
  one `runStatus` mount of five that called neither `openTicker` nor `finish()`, so after a reload
  the row counted upward for as long as the tab stayed open while the worker had exited and
  `GET .../runs` had gone empty — and its Stop, still on screen because `is-done` only stills the
  pulsing dot, answered 404 and reported "it may still be going". `finish()` is the only route to
  `noteRunFinished`, so the header's run dot leaked for the session. One test asserted the row
  MOUNTS; nothing asserted it ever ends, which is this project's composition gap again. It now
  watches two signals (the ticker for words, `/runs` for the authoritative ending, because a run
  that finishes between the answer and the stream opening emits no terminal event) and REPLACES the
  row rather than stilling it, because a finished run has a result this tab has not got.

  Also: the auto-summary pass reported `done` greater than `total` (it announced
  `min(limit, pending)` and then ran with the raw cap, so anything reaching `ready_undistilled` in
  the window was summarised too — `2 / 1`, on the action that spends money); the notebook upload
  endpoint kept only the LAST file of a multipart batch and said nothing, so `note.txt` +
  `broken.pdf` answered 422 naming only the failure while the file that worked was neither stored
  nor mentioned; a membership outlived the source it pointed at, so a node went on claiming to be
  filed in a notebook whose copy of it had been removed; and `parse_web`'s bounded read had a test
  that could not see the bound — the canned response ignored `read(n)`, so `resp.read(cap + 1)` →
  `resp.read()` left the whole suite green. `IntakeQueue.has_pending_work` and `cancel_generation`
  had no test at all, and both are how a Stop and a capture reach a batch running on the queue's own
  thread.

  Measured and fixed from the design judge's non-blocking list: five fields wore Chrome's UA
  placeholder grey (`#ask-input` 3.62 / 3.17 at 17px) because nothing had ever set one; the two
  "type here" fields had two focus languages, which the previous round had already settled for
  their typeface; every input, textarea and `.node-danger` drew its boundary at 1.37 / 1.65 against
  1.4.11's 3:1, on a token picked for a hairline between rows and reused for a component edge (a
  measured `--field-border` now lands at 3.30 / 3.39, and `.node-danger` at 3.55 / 3.72); switching
  the interface language left the whole Inbox in the old one until a reload, because the listener
  that repaints the notebook column had never covered Tier 0; the Studio's vertical resize handle
  stayed focusable and half off the left edge across the entire 641–1024 band, one breakpoint below
  where the split it drags stops existing; Find was offered over a first-run Inbox with nothing to
  find; an uploaded file's row printed its filename twice; the capture picker offered `.csv`, `.rst`
  and `.markdown`, all three of which the server refuses; and **the document had no headings at
  all** — not one `<h1>`–`<h6>`, so the outline a screen-reader user navigates by began at a node
  row's `<h3>`.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **917 passed**;
  every fix above mutation-checked against its own test, and every measurement re-taken from painted
  pixels. One instrument was wrong and is worth recording: a contrast helper that pre-fills its
  canvas with black makes every read-back opaque, so the background walk stops at the first
  (transparent) element and reports 1.21 where the real figure is 13.91.

- **Two independent reviews, run in parallel — one on design, one on function — and the second one
  found that the summary pass had never worked.**

  **`POST /inbox/distil` was dead in every shipped configuration, and 869 green tests said nothing.**
  `config.setup()` is the only caller of `rlm_harness.configure`, and therefore the only thing that
  gives `dspy` a model. It is invoked in `cli.py` and in `worker.py` — and `worker.py` is the
  isolated subprocess every `RLMTask` runs in (invariant 21), which is why `ask`, the guides, the
  podcast and `_resolve_language` all work. `distill.py` is deliberately NOT an `RLMTask`: it is a
  plain `dspy.Predict` (invariant 80) on a thread inside the server, where nothing had ever called
  `setup`. Every node came back `ValueError: No LM is loaded`. The reviewer proved it by pointing
  `RN_BASE_URL` at a stub and watching zero HTTP requests arrive.

  **The suite could not see it because every distillation test monkeypatches `distill.distil_source`
  — exactly the function whose real body could not work.** Patching the unit under test at the seam
  where the bug lives makes a green suite worth nothing. `tests/test_distil_live.py` patches nothing:
  it stands up an OpenAI-compatible server on loopback and asserts on BYTES. It runs in a FRESH
  INTERPRETER, which is not fussiness — `rlm_harness.configure` keeps the first LM a process builds
  (configure against port A then port B and the LM still talks to A; the second LM comes back with
  no `base_url` at all), and `dspy` caches completions on disk, so the first in-suite version passed
  once and then hit the stub zero times while still reporting `done: 2, failed: 0`. Either cache
  turns the assertion into one that passes over a re-broken build.

  **And the failure had nowhere to go.** `_run_distil_pass` ticked `done` once per ATTEMPTED node
  and discarded `distil_pending`'s return, so the status could only ever describe success: the strip
  counted to 2 / 2 and vanished while both nodes sat unchanged. `_DISTIL` carries `failed` and
  `error` now, `distil_source` takes an `on_error`, and the reason reaches the reader verbatim —
  "RN_MAIN_MODEL is not set" is the actionable sentence, and this is a single-operator BYOK tool.

  **A second gap fell out of testing the first: auto-summary never fired for a paste or a drop.**
  The hook runs when the intake QUEUE goes idle, and pasted text and uploads never enter the queue
  (both are bytes in hand). A queue that was never busy never goes idle. `IntakeQueue.nudge` asks
  for the idle check on the queue's own thread — where the model calls belong, never a request
  thread.

  **The design review's verdict was that the Inbox was close to the bar and the surface BEHIND it
  had not been brought along.** Acted on:

  - **A notebook was a one-way door.** `.crumb { display: none }` above 860px, justified by "the
    rail is the navigation whenever it is on screen" — and the rail lives inside `#view-inbox`,
    which is hidden the moment a notebook opens. At the width the product is used at there was no
    route back to the default surface at all. The crumb now keys off WHICH VIEW IS UP.
  - **And there was no URL state**, so Back left the application rather than the notebook and a
    notebook could not be bookmarked or reloaded into. `?nb=` plus `popstate`.
  - **One notebook, three names, one of them the raw id.** The rail said "Christopher Alexander",
    the File-into `<select>` said `reading`, and the line beside it said "已在 reading" — invariant
    37's violation, one function away from the tripwire written for it, in the one control where the
    reader must CHOOSE. The tripwire is global now: it walks every expression that becomes visible
    text, and `notebook_id` may only be a lookup key, a URL segment or a request-body field.
  - **Labels also collided** — three rail entries all reading "Christopher Alexander". `facetLabels`
    lengthens only the groups that tie, and the id is not a rung even when the rungs run out.
  - **Eight nested `<button>`s on first paint**, plus an `<h3>` inside one. The head is a container
    with a stretched overlay button now: valid markup, one keyboard control per row, tags as
    siblings. The failed-capture chip stopped wearing `.node-tag`, which made it look like a filter.
  - **Four saturated copper fills at once, and two tab idioms ninety pixels apart.** Tabs use the
    underline the Studio already used; a tab reports a position and does not promise an action. Both
    ✨ emoji went — the 2023 AI tell, on a surface whose Inbox has no emoji anywhere. An empty thread
    centres its invitation instead of pinning a bordered card above 550px of nothing.
  - **The settings dialog had `aria-modal` and no focus management**, which is the half a keyboard
    reader feels: eight Tabs still walked the page behind the scrim. The first fix was measurably
    wrong — `.layout.inert = true` made the DIALOG inert too, since the overlays live inside it —
    so siblings are marked, walking up, and focus returns to the trigger on close.
  - **The steps pill apologised.** It was rendered on every finished artifact, so a run that failed
    before producing a trace still offered it, and pressing it raised a native `alert()` carrying a
    raw run UUID. An affordance whose only outcome is an apology is not one: it retires in place.
  - **`auto_distil` was an API capability with no control, and Save DESTROYED it.** `PUT /settings`
    is a full replacement and the page built its payload from the rendered inputs, so a key with no
    row was a key the next save erased. A cross-language tripwire now fails if the server stores a
    setting the page does not draw.
  - **"Summarise them" next to "324 not summarised yet" summarised fifty.** The button names the
    batch; `DISTIL_BATCH_CAP` is one number read by both the label and the request.
  - Every header control wore Chrome's stock blue focus ring, because the rule named eight classes
    and `.distil-btn` (an id) matched none of them. One zero-specificity rule covers everything
    focusable. Four `<select>`s were left native while one was drawn; one element rule covers them,
    with the chevron as a per-theme token because a data URI cannot use `currentColor`.
  - `word-break: break-all` shredded prose into "A Patter / n Language"; `overflow-wrap: anywhere`.
  - A pasted excerpt ended on a dangling preposition, which made a short note and a truncated one
    indistinguishable. The send button was never `disabled` and sat there as a copper block doing
    nothing on an empty field.

  **Three more the function review found, each a real capability gap:**

  - **A multi-file drop silently lost every file after an unsupported one.** The first `ValueError`
    aborted the loop, keeping what was already stored and dropping the rest, under a 422 naming
    neither. Every file is attempted and the refusals are named, by filename, inline.
  - **A PDF URL could not be captured at all** — `trafilatura` ran unconditionally, so an arXiv link
    came back "no extractable text content". Local PDF upload worked the whole time, which made it a
    routing bug. `parse_web` sniffs content type (and magic bytes, for a PDF served as
    `octet-stream`), and plain text is kept verbatim. `ingest.kind_for`'s own comment had predicted
    this exact change. The fetch is also BOUNDED now, at the upload cap.
  - **Search was one substring, so "design Rams" matched nothing** although "Rams" opens that node's
    summary — the two words live in different columns. Terms AND, split on whitespace only, which
    leaves a Chinese query as exactly one substring.

  **Documentation drift, which this project treats as a defect:** `AGENTS.md`'s Scope note said
  twice that the Inbox has no UI, through the whole stage that built it; invariant 41 was
  contradicted by `auto_distil` with the reconciliation living only in invariant 80's file;
  invariant 47's run-id rule did not cover `/inbox/cancel`; invariant 30 still called multi-file
  upload "deliberately not attempted" after it shipped; `README.md` never mentioned the Inbox; and
  two comments arguing AGAINST registers that rot carried counts that had rotted by ten. Those two
  now carry the argument and no number. `tests/test_docs.py` puts tripwires under the Scope note's
  checkable halves, in BOTH directions.

  **A second independent design review then found eight more, and its first item was mine.**

  - **The Inbox was deleting the last word of every pasted note.** `pastedExcerpt` cut at the last
    space whenever that space fell past index 24 — which is most English sentences — without ever
    checking whether the value had been truncated at all. "Swallow test note about editorial
    recall." arrives complete at 41 characters and rendered as "Swallow test note about editorial".
    The origin is `text[:60]`, so the client CAN tell: a value under the cap is shown whole, and a
    value at it is cut and **ellipsised**. The no-glyph rule is `facetLabel`'s and belongs there — a
    name in a 13rem slot — not on prose in a 63-character column, where the hand-written list of
    dangling function words was producing "...is a river, not".
  - **Every primary button failed WCAG AA in Paper.** Near-white on `--accent` at L=0.62 measures
    3.56:1 against the 4.5:1 AA needs at 14.4px/600, and `#distil-btn` — copper text, the control
    that spends money — measured the same. L=0.54 gives 4.95:1 both ways. The worst pair anywhere
    is now 4.97 in light and 5.44 in dark. (My own first attempt to measure this was wrong: Chrome
    returns `oklch()` in computed style and the script read those numbers as RGB, reporting 1.04.
    The second pass resolves colours through a canvas.)
  - **A failed answer was styled as a successful one** — same bubble, same reading face, a literal
    "(error)" prefix doing all the work — while the Inbox used a red dot and a tinted block for the
    same event. Two surfaces disagreeing about what failure looks like.
  - **The summary pass reported a number it could not support.** `_DISTIL["failed"] = max(1, ...)`
    when the PASS failed, so pressing "Summarise 2" with no credentials said "1 could not be
    summarised" when nothing had been attempted. `failed` counts NODES; a pass that could not start
    is zero with an error, and the page says so in different words.
  - **`alert()` and `confirm()` are gone**, all sixteen. They cannot be styled, they block the
    renderer (which is how one was found — a hung page mid-review), and in the planned Tauri shell
    they become OS modals over the window. Notices are inline and non-blocking; the confirm is a
    real dialog on the same `inert`/focus machinery, focused on **Cancel**, with Escape answering no.
  - **Focus escaped the Settings dialog for one Tab press**, landing on the document with nothing
    visible before wrapping. `inert` keeps focus off the page but does not close the cycle; the
    dialog wraps Tab at its own edges now.
  - **The rail floated.** `.view-inbox` was capped at 74rem and centred, so the shell sidebar
    started 108px from the window edge at 1400 and 308px at 1800. The shell is full-bleed; the
    MEASURE is what gets capped, which is where a measure belongs.
  - **The notebook still read as a different product**, narrowed rather than closed: the reader's
    own question wore the primary-action fill, a source was a bordered card where a node is a
    hairline row, one button was in Literata and four in Public Sans, and two underline tab strips
    90px apart measured 12.16 and 12.48px. One idiom, one typeface, two real levels — and the
    Studio's Generate is demoted, because two primary actions with near-synonymous labels 500px
    apart are one too many.

  Plus: a tooltip that presented the server's 60-character cut as the full name (a tooltip that is
  also truncated answers the question wrongly instead of not at all), a `document.title` that never
  named the place, `#ask-submit` never disabled, Save below the fold at 375, the exception CLASS
  name stripped at the display boundary the way invariant 62 strips markers, and `.node-actions`
  wrapping raggedly because a flex spacer only spaces while everything fits on one line.

  **My own tripwires caught me twice more here**: a 2px accent border on the question bubble is
  exactly the admin-UI stripe `test_no_accent_bar_wider_than_a_hairline` bans, and the tooltip
  change broke an assertion that had pinned the behaviour being corrected — rewritten to the
  stronger rule, then mutation-checked.

  **A parallel function review found five more, and its blocking one is the sharpest thing either
  reviewer found about this codebase's own habits.**

  - **Stop reported success and stopped nothing.** Every run is announced before its pre-work
    (invariant 46), and `_resolve_language` is a real model round trip that always happens on a
    notebook whose language is unresolved — every new one. Press Stop in that window and
    `cancel_run` found the `None` placeholder, honestly reported "not spawned yet", and signalled
    NOTHING: the page declared the run over, the pre-work carried on under a derived id the Stop
    never named, and twenty-four seconds later the main worker spawned and burned a full model call
    with no indicator and no control anywhere. Honest reporting of a no-op is still a no-op.
    `_CANCELLED_BEFORE_SPAWN` records the stop, `_run_isolated` refuses to spawn an id in it, and
    the cancel reaches `{base}-lang` too. The client stopped calling `finish()` unconditionally:
    a Stop that could not reach its run now says so instead of claiming one.
  - **The AUTOMATIC summary pass was invisible, unstoppable and silent.** It called
    `distil_pending` directly, touching none of `_DISTIL`, so thirteen measured model calls ran
    behind `{running: false, done: 0, total: 0}` with the strip hidden. The one batch that runs
    WITHOUT a press was the one with no progress, no Stop and no failure channel — invariant 47
    inverted — and the 409 guard could not see it either, so a second pass could start on top of it.
  - **A page reload lost a run that kept spending.** The worker is a subprocess and survives the
    page; the run id lived only in the tab that started it. After F5 there was no indicator, no
    Stop, and no way to find either — asking again simply started a SECOND run on the same notebook.
    `GET /notebooks/{id}/runs` lists what is in flight and the page re-mounts a status on it.
  - **Stopping intake stranded every waiting node at `queued` forever.** "Nothing was parsed, so
    `resume_interrupted` can pick them up later" was true only across a RESTART. Meanwhile they were
    drawn identically to a node being read, the page polled at 2.2 requests a second because
    `queued` counts as busy, no Try again was offered (that is `failed`-only), and opening one
    answered `404: node '...' has no stored text yet`. Invariant 79's own sentence is that a
    permanent `queued` "looks exactly like still working". A dropped item lands `failed` with
    "stopped before it was read" — terminal, visible, and retryable through the reset `submit`
    already has.
  - **The failed-chat-turn state was unreachable**, and this one is a process lesson rather than a
    design one. The branch, its two CSS rules and its translation key all shipped; the single line
    that SET the flag did not, because the reviewer restored `app.js` from a backup during its own
    mutation testing and my edit was inside the window. Dead code is silent by construction. Worse
    while it lasted: the failure rendered as an ordinary answer with "save as note" attached, and a
    note promotes into a citable `Source` (invariant 32) — the exception text could have become a
    SOURCE.

  **And the review mutated eight seams to see which the suite would catch.** Six were caught. The
  two that were not are now the point:

  - Deleting the IME guard from the capture field's Enter handler left the whole suite green.
    `grep -rn "isComposing" tests/` returned nothing, on a product whose own interface language is
    zh-Hant. The rule is written as a rule: every `keydown` handler that acts on Enter carries the
    guard, with handlers that treat SPACE as activation excluded — a text field can never activate
    on Space, so an element that does is a button being operated by keyboard and cannot be composing.
  - Neutering `intake.submit`'s failed-to-queued reset left 52 tests green. That one line IS the
    retry path behind the UI's "Try again", which deliberately has no endpoint of its own.

  **Documentation drift, again, and one entry contradicted itself inside its own block**: invariant
  80 still said the web UI had no `auto_distil` control in the same `[Unreleased]` that records it
  shipping; invariant 79 said `parse_web` "hardcodes `kind="web"`" after sniffing landed; invariant
  30's correction blurred which endpoint got batch upload (it is `/inbox/upload`, not the notebook
  one); invariant 41 called `auto_distil` the API's first global mutation when Tier 0 added five;
  invariant 47's "one at a time" was false of the auto path; `README.md` described search as reading
  titles/summaries/tags when it also reads entities and origin; and `DESIGN.md` — which claims to be
  pinned to the code — was stale in about twenty-five places. It now carries a standing note saying
  that prose about code rots and that a disagreement means THIS file is wrong.

  **A third round, and the two headline findings are both about how this work was verified rather
  than about the code.**

  - **The Stop fix from the previous round was dead on arrival, and two tests said it worked.**
    `_announced`'s `finally` discarded the cancel flag when the `with` block exited — and every
    handler is `with _announced(id): await pre_work()` followed by `_run_isolated(..., id)`, so the
    flag was erased one line before the only code that reads it. A reviewer pressed Stop at t=2s,
    the UI said stopped, and a full chat turn was persisted and billed 27 seconds later. One test
    hand-built `_RUN_PROCESSES` and asserted the id lands in the set; another pre-seeded the set and
    called `_run_isolated` directly. **Each half green, the seam untested** — and mutating the check
    to `if False` DID fail two tests, so the line was "covered". That is the illusion. The new test
    composes the two, which is the only shape production has, and fails on the shipped code.
  - **Most of the previous round's web edits were reverted by my own backup file**, which is the
    footgun I had warned two reviewers about that same hour. `cp /tmp/app7.bak` during a mutation
    check restored a snapshot taken before them. The CSS half had landed and the JS half had not, so
    `.node-open` became an empty button with no `position` — **13.59 × 0 px: no Inbox row could be
    opened with a mouse at all**, on the default screen. Every lost edit is re-applied and verified
    by name; mutation checks now restore with `git checkout --`, never from `/tmp`.

  **What the round found in the product:**

  - A pasted CHINESE thought was cut at sixty characters with no ellipsis. The mark had been made to
    depend on an English word-boundary trim, and `lastIndexOf(" ")` returns -1 for a script with no
    interword spaces — so the interface's DEFAULT language was the one that lost the signal.
  - The stretched overlay that fixed the nested-button problem made **the prose unselectable**: a
    195px drag returned an empty selection and toggled the row. A reading surface whose one
    distilled sentence cannot be copied is not a reading surface. Third shape: the left gutter's
    state dot IS the button, and the head's click yields to a selection.
  - An undistilled web capture was identified by HOSTNAME, though `preview.title` was in the payload
    and the notebook's source list already used it. Distillation is opt-in, so undistilled is the
    river's default state: ten articles from one site were ten identical rows.
  - Datelines dropped the year, so a stream older than twelve months stopped being monotonic.
  - An auto-summary pass triggered by an UPLOAD was invisible for all twenty calls — the paste half
    was fixed last round and the drop half was not, and the test's own docstring named both while
    asserting one. Visibility now comes from asking the server, not from guessing at the page.
  - Adding a source did not mark the on-screen overview stale (the remove path did); the file-into
    picker was offered on nodes with no text, whose only possible outcome was a 400 contradicting
    what the reader could see; a file could only enter the Inbox by MOUSE DRAG, which excludes
    keyboard, touch and every phone, on the screen whose promise is "throw anything in"; the
    wordmark emptied the notebook you were looking at and left its id in the address bar; and a
    failed promotion left an empty notebook behind in the facet rail.
  - **The pivot broke `playground/`**, whose README claims it "cannot rot into a mock-up of a UI we
    no longer ship". The shim intercepted `/notebooks*` and `/settings*` only, and the byte-copied
    `app.js` now boots into the Inbox — so the public demo's first screen was
    "（錯誤）404: File not found" under a tour pointing at a button that was not there. CI runs
    neither `build.py` nor `smoke.mjs`. The shim serves a read-only Inbox built from the same real
    notebooks, and writes answer honestly rather than 404ing.

  **A fourth round, measured from painted pixels, and its two blocking items are both mine.**

  - **The file button I added in round three had NO CSS RULE AT ALL.** `grep -c capture-pick
    style.css` → 0, so it wore the UA's `buttonface`: rgb(239,239,239) with rgb(163,157,150) text is
    **2.34:1** in Study, on a page whose background is rgb(28,20,16) — the single native-chrome
    element in the product, on the default screen and on the public playground page. The `select`
    one row away carries a comment recording this exact lesson. It is an inline accent LINK now,
    4.97:1 light and 7.8:1 dark.
  - **On a phone you could not reach a notebook from the Inbox.** `.facets` is hidden below 860px
    and I had hidden `.notebook-picker` in the Inbox view; together that left no control that opens
    a notebook, creates a facet, or reveals that notebooks exist — half the two-tier model,
    unreachable. It was a one-way door, too: inside a notebook the picker IS shown at 375, so you
    could switch until you pressed the Inbox crumb once. One navigation surface at a time, never
    none.

  **`test_every_class_the_inbox_creates_has_a_rule` did not catch the first of those, and now
  does.** It scanned only classes `app.js` creates with `elt()`; a class written in `index.html` was
  invisible to it. Widening it to the markup immediately found two more (`.facet-list`,
  `.stream-more`) that styled nothing and never had.

  The rest, each with a measurement behind it: the source viewer's heading was the raw 60-character
  cut with the un-cut sentence visible four lines below it (one marker helper, two call sites, one
  wired up); `pastedExcerpt`'s `<` should have been `<=`, because `text[:60].strip()` can land on 59
  and the seeded data ships one; `.node-error-head` was checked against the PAGE (4.94/5.15) and
  sits on the tinted block (4.27/4.37, under AA); the hidden file input was a phantom tab stop; a
  row's focus ring was a 14px circle round the dot while the row it opens showed nothing; a file
  dropped on the header or in a notebook **navigated the browser away**, taking any unsent capture
  text with it; the summary error collapsed into a 112px twelve-line ribbon at 375; a row had no
  hover state at all, so the signature gesture rested entirely on a cursor shape; "1 sources · 0
  turns"; and the playground overflowed at 375.

  **One rule is a synthesis of two reviewers disagreeing.** Round three banned a tooltip built from
  `derived_title`, because a hovered label produced a tooltip that was itself cut. Round four
  measured the cost: rail labels ellipsise at 154px against a 238px natural width with no way to
  read them, in the one place a notebook's label IS its identity. Neither "show a fragment as if
  complete" nor "show nothing" is right — show it, and MARK it, which is what `pastedExcerpt`
  already does. The tripwire now requires the mark instead of banning the value.

  **And `git checkout -- <path>` bit me the same way `/tmp` did.** It restores the INDEX, so running
  it to undo a mutation wiped five unstaged CSS blocks. Stage first, then mutate.

  **And the function half of the same round found three seams this changeset shipped that a
  one-line mutation breaks with the whole suite green.** All three are now driven end to end:

  - **`?q=` had no HTTP-level test at all** — the product's stated promise. `query=q` → `query=None`
    left 894 passing while every search in the UI returned the unfiltered listing.
    `inbox._search_clause` has six unit tests and `?state=`/`?offset=` are driven over HTTP, which
    is exactly what made the parameter look covered.
  - **Stop did not have to reach the summary pass.** `_DISTIL["cancel"] = True` → `False`: green,
    while every remaining model call in a batch ran on after the reader pressed Stop. The one test
    that looked like it covered this asserted `distil.running is False` with nothing running —
    vacuously true, and true of a no-op endpoint.
  - **"One pass at a time" lived in a comment.** Deleting the 409 guard: green.
  - And the `failed`/`error` channel added earlier in this same block had never once been observed
    NON-ZERO. Its test had to patch `DistillNode.arun` rather than `distil_source`, because patching
    `distil_source` bypasses the mechanism under test — the same trap, one level down.

  **Plus a Stop that still left a model run burning.** `ensureTitle()` fired at the START of ask,
  overview, guide and podcast, on the reasoning that the reader had committed to a call anyway.
  They had committed to THAT call: stopping a question 1.8s in correctly prevented it and left the
  title's language pre-work and its main worker to spawn six seconds later, two round trips with no
  indicator and no Stop, under a different run id no Stop names. It fires on SUCCESS now, which
  keeps the original reasoning and makes Stop mean what it says.

  **Two raw internal strings reaching the reader**, both in the same family the CHANGELOG had
  already recorded twice: opening the same notebook in two tabs — which `reattachInFlightRuns`
  invites — and stopping from one showed the other `499: run 'reading-4d2662ef-…' was stopped before
  it started`, or `502: worker … produced no output (exit -9)`. Neither is an error; the reader
  asked for it. And opening a row while it was still being PARSED showed "Could not read this" over
  a 404 naming an internal node id — both the cause and the claim wrong, fixed for `failed` only.

  **And a correction in this same changeset was itself wrong.** It said `--mono` is a plain system
  stack and JetBrains Mono "was never in the repo". The token was right and ten live rules bypassed
  it, putting `"JetBrains Mono"` first in their own family lists — so the face rendered for any
  reader who happened to have it installed and for nobody else, which is invisible on a developer's
  machine. Every rule reads `var(--mono)` now, and
  `test_no_rule_names_a_typeface_this_repo_does_not_ship` makes the rule mechanical: a quoted family
  in `style.css` either has a file under `web/fonts/` or is a system stack.

  **A fifth round. The blocking item loses data and is reproducible with curl.**

  - **A malformed `.pdf` 500'd both upload endpoints.** `pypdfium2.PdfiumError` subclasses
    `RuntimeError`, and both caught `(ValueError, OSError)` — so the exception escaped, the request
    became `500: Internal Server Error`, and every file ALREADY STORED in that batch was never
    reported, because the response that would have named them never happened. `note.txt` +
    `broken.pdf` together: 500, and the reader told nothing about the file that worked. That is the
    exact failure the batch loop was written to fix, arriving through a different exception type,
    and it contradicts invariant 79. `intake.py`'s worker already catches `Exception` with the
    reason written down ("a parser may raise anything; the node records it") — the queue path had
    it, both upload paths did not.

  Measured, not argued: **there was no `::selection` rule anywhere**, so selecting a summary — the
  gesture this product exists for — painted Chrome's default, 1.82:1 in Study and a cobalt blue in
  Paper. **Four contrast failures** measured against the surface each element actually sits on
  rather than against the page: the ask hint (2.31/2.66, legible only ON focus, which is after you
  need it), the send glyph (2.12/2.59, the sole send affordance, under the 3:1 floor for a UI
  component), the remove ✕ (3.80/3.63, destructive) and the confirm's Delete button (4.17/4.14).
  **The notebook picker overflowed the viewport at 375** and put each row's Rename control entirely
  off-screen — on the width where the rail is hidden and that menu is the only route to a notebook.

  **Three rules this codebase had already written down and applied in exactly one place:**
  "reveal on hover is a hiding place" was applied to the rename pencil and not to `.src-remove`
  (destructive) or `.save-as-note` (the only route into Notes), so on a phone a source could not be
  removed at all; the Inbox's hidden-input-plus-real-button was not carried to the Sources pane,
  which still rendered the browser's own control with an OS-locale button reading 選擇檔案 inside an
  English interface; and the public playground printed the internal notebook HANDLE as a tag on
  every row (`nb-en-security`), on the first screen a stranger sees, two functions above
  `anonymise_models`, which scrubs the same fixture for exactly this reason.

  **The two halves still read as different products, and the gap was measurable**: 0.02% of Inbox
  pixels are saturated accent against 1.29% of the notebook's, with three copper CTAs at equal
  weight — "Add source" (free, instant) beside "Generate podcast" (the most expensive action in the
  product), while the CHEAP "Generate summary" was the quiet one. Cost and prominence ran opposite.
  The podcast offer is `.btn-offer` now, and the tripwire that had required `btn-primary` there was
  rewritten to pin the DISTINCTION it cares about rather than the class. The two "type here" fields
  — one per tier — were Literata 17px and Public Sans 14.4px; what a person WRITES is content on
  both surfaces, so both take the reading face.

  **And `readableError` grew from three shapes to seven.** A dead link put four lines of
  Python/OpenSSL in the reading column (`<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] …
  (_ssl.c:1028)>`); a failed question put an HTTP status code and a **shell command**
  (`set -a; . ./.env; set +a`) in the most-read surface in the product. The rule is not "make it
  friendly" — this is a BYOK tool and a specific cause beats a soothing one — it is that nothing
  reaches the reader which they cannot act on: a status code, an exception class, an OpenSSL source
  line, a run UUID, a signal number, a shell incantation. `RN_MAIN_MODEL` stays, because that half
  IS the action.

  Plus: one object had three names in adjacent controls ("New facet" → "＋ New notebook" → "Untitled
  notebook"), and two measure words for one noun; Settings listed 32 vendor SKUs where the select
  one row above correctly reads "Arabic"; the send button stayed enabled over an empty field for the
  whole session after the first capture; a Stopped capture was drawn identically to a broken one;
  and `⌁` rendered as an illegible 7px squiggle.

  **The function half of the same round left three items, and two of them were the playground.**

  - **An undistilled web or PDF capture never showed its URL, anywhere.** Distillation is manual by
    default (invariant 80), so this was the DEFAULT state of a captured page: three links from one
    host rendered as three identical rows reading `localtest.me`, with `.node-meta` empty and no
    `title=`. The condition guarding the origin line was `&& node.title`, which is only true AFTER
    distillation; an earlier fix reached HTML pages through `preview.title` and left PDFs, text URLs
    and any page without `og:title` exactly as they were. The origin is the one thing every capture
    has, so the headline falls back to the HOST and the meta line carries the PATH — the part that
    tells two captures apart — with the whole URL on the element's `title`. Verified against a real
    server: three `rfc-editor.org` captures come back `ready_undistilled` as `/rfc/rfc1149.txt`,
    `/rfc/rfc2324.txt`, `/rfc/rfc8890.txt`, and an arXiv PDF as `arxiv.org` + `/pdf/1706.03762v7`.
  - **The playground's guided tour never left the Inbox — fifteen steps, every one of them a control
    in the three-column notebook.** `openInitial` opened a notebook before the reader had seen
    anything, so the entire Tier 0 half of the product — the screen it now BOOTS to, and the reason
    the redesign happened — had no step at all. The script opens on the Inbox now and the notebook is
    reached the way a reader reaches it, by pressing a facet, which is step 4 of 19. Three of the
    four new steps describe controls this page cannot let anyone use (capture, distillation and
    promotion all write, and there is no server), so those ask for the one thing a recorded page can
    honestly offer and say plainly which part needs the real app; Find and opening a row are NOT in
    that set, because both are reads answered from the recorded index and both do exactly what they
    do in the product.
  - **The playground header overflowed at 375 and three controls were unreachable** — ★ GitHub, ⚙ and
    ◐ at x = 341…480 against a 375 viewport, two of them the APP's own, inside a scroller with
    `scrollbar-width: none` and therefore no affordance saying they were out there. The earlier fix
    was that scroller, argued on "hiding a button whose label is its only meaning is worse than a
    scroll a thumb can do" — true of the word, and the glyph beside it was already the icon, so
    splitting the two keeps the control and drops only the word. Measured at every width from 375 to
    1440: nothing clipped, nothing unreachable.
  - **And on a phone the page carried no "this is simulated" marker at all**, which is the one thing
    `playground/README.md` calls non-negotiable. `.pg-sim` is hidden below 900px to buy the row its
    width and the app hides `.wordmark` below 640, which took the PLAYGROUND tag with it; between
    them the entire phone layout was unlabelled, on the surface most likely to be opened from a link.
    A strip under the header costs the row nothing.

  **Two findings about the instruments rather than the product, both of which had produced a wrong
  answer.** `tests/test_distil_live.py` runs its scenario as `sys.executable -c`, and `rlm_notebook`
  resolves there through the EDITABLE INSTALL, not the subprocess's cwd — so a mutation applied to a
  copied tree is invisible and the test passes, which looks exactly like a test that does not catch
  the mutation. Reported as an untested seam; it is not, and mutating the real tree with the change
  staged catches it. And the tour's "open a row" step completed itself the instant it armed, because
  **driver.js writes `aria-expanded="true"` onto whatever it spotlights** as part of its own stage
  bookkeeping, so a `done` predicate reading that attribute was satisfied by the act of asking the
  question. It reads the app's own `is-open` class now. The smoke suite gained the anchors for the
  four new targets, a recursive `textContent` (a split label read as empty and fell through to the
  className, which would have passed for a button whose copy had gone missing), and a fake DOM whose
  header has a parent — a detached one made the strip's insertion a no-op the check could not see.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **905 passed**;
  `playground/build.py` + `smoke.mjs` run and the page loads with real Inbox rows at a clean 375
  (the remaining smoke failures are all "0 recorded runs" — this checkout's `traces/` is pruned, not
  a defect in the page).

- **The Inbox gets a face, and the typefaces this project has described since Phase 1 are loaded for
  the first time.**

  **The largest gap was not the missing surface, it was that the identity was never delivered.**
  `index.html` pulled in one stylesheet and nothing else: Literata, Public Sans and JetBrains Mono
  were named throughout `style.css` and `DESIGN.md` and **no font file existed anywhere in the
  repo**, so every machine without them installed rendered the whole product in its system sans. In
  an ink-on-paper direction the typeface IS the identity.

  Self-hosted, not from a CDN, for the reason invariant 51 refuses `og:image`: a remote font makes
  the READER's browser call a third party on every page load, and this app binds loopback and ships
  in a container verified with no network at all. One VARIABLE file per family and style — Google
  serves the same woff2 for every weight, so the naive download was the identical 26 KB three times
  (176 KB shipped instead of 316 KB). Latin `unicode-range` only, so a Han run never waits on a
  download it cannot use, with the CJK faces paired explicitly and Traditional first, because this
  interface's own language is zh-Hant and an SC face draws Simplified forms for it.

  **The aesthetic direction did not change, and that is the finding.** The direction locked in
  Phase 1 is the same one the Inbox needed; repainting it would have been motion without a reason.
  What was missing was structural, plus the delivery above. `DESIGN.md` says so rather than
  implying a redesign happened.

  **The design brief came from an invariant.** Invariant 51 makes mymind's masonry-of-thumbnails
  structurally unavailable, so recall here cannot be visual: it has to be TYPOGRAPHIC. Titles and
  summaries are set in the reading face at a real measure, there are no cards, and a hairline
  between rows is the only separation. Literata's optical-size axis does real work — one file, a
  display cut at heading sizes and a reading cut at body sizes.

  **Six defects the screenshots found, each fixed and re-shot:**

  - The home control inherited `.header-btn`, a 32px square built for one glyph, and folded a
    two-character label into three stacked lines. It was the first thing on screen.
  - Pasted nodes used `ingest_pasted_text`'s 60-character origin as a TITLE, so rows read
    "Less, but bette" and "the reason I cannot". A pasted node has no title now; its fragment is
    prose and goes in the prose slot, trimmed at a word boundary with no ellipsis.
  - The facet rail showed `derived_title`, a whole sentence in a 13rem slot, ellipsised to
    "Christopher Alexander, A …". A rail label has to be short by construction. Getting there took
    three drafts, and the two wrong ones are the interesting part. Falling back to a person-chosen
    id (`reading`, `work`) reads beautifully and is the one thing invariant 37 forbids: the id is a
    HANDLE. `test_the_notebook_id_never_appears_in_the_picker` caught it, and the tripwire was then
    deepened to follow `facetLabel` itself, because a tripwire a helper can hide behind is not one.
    Slicing the first three WORDS passed every test and was worse on screen: "A note to" and
    "Christopher Alexander, A" fit, so they carried no ellipsis, so they read as complete names that
    happened to be gibberish. An unsignalled cut is worse than a signalled one. The shipped rule
    cuts at a boundary the sentence already had — the first clause — and only when the value does
    not fit, measured in COLUMNS rather than `.length` so that 24 Han characters are not mistaken
    for 24 Latin ones. "Less, but better" therefore survives whole, "Christopher Alexander, A
    Pattern Language" becomes "Christopher Alexander", and a long clause with no boundary in it
    falls back to the CSS ellipsis — honest, on a label that is openly a fragment — with the full
    value on the row's native `title`.
  - The rail's count `float: right` after a full-width name wrapped to a second line.
  - The header read "還沒有筆記本" (there are no notebooks yet) beside a rail listing two. It meant
    "no notebook open"; two different sentences, only one ever true.
  - The rail sat on `--surface-1`, 2.5% of lightness from `--bg` in Paper against the 4% an app
    shell needs. **My own read of the screenshots had this backwards** — I thought dark was the weak
    one — which is why it is a measurement and not an opinion.

  **And one bug I nearly invented.** A 375px screenshot showed the capture field clipped, so I began
  fixing a mobile overflow; a measurement probe reported `SW=500 IW=500`. Headless Chrome on macOS
  has a 500px minimum window and had been rendering at 500 and cropping the PNG to 390. There was no
  overflow. Rendering in an iframe at a true 375px confirmed the surface is clean. The header
  media query written during that detour is kept: it is right for genuinely narrow windows, it just
  was not what the screenshot showed.

  **Verification without a browser, where it is stronger than looking:** all 18 text/surface pairs
  computed for WCAG AA in both themes (tightest 5.48:1); the fonts served with the right MIME and
  `wOF2` magic bytes; and a new source assertion that every class the Inbox creates has a rule,
  which found three gaps on its first run — `.sr-only` did not exist so a visually-hidden label was
  VISIBLE, `.intake-dot` did not exist so the running indicator rendered as an empty span, and
  `.node-col` had no `min-width: 0` so every `text-overflow: ellipsis` inside a grid child silently
  did nothing. None of those throw.

  Also: a favicon, which the product never had (`GET /favicon.ico` was a 401 on every load), drawn
  as the state dot on paper and theme-aware. And invariant 77 gains one sentence: `PUBLIC_PATHS` is
  computed AT IMPORT, so a file added to `web/` while a server runs is not public until it restarts.

  **An independent design review then returned NOT YET with fourteen items, and the split it drew is
  the useful part: "the look is done and it is good; what is missing is everything that happens
  after the first glance."**

  - **The capture field submitted mid-IME-composition.** Enter is how you COMMIT a candidate in 注音
    or 拼音, so typing a thought in this interface's own language and pressing Enter posted a
    half-formed node. The identical guard, with the identical comment, had been sitting 1,700 lines
    away on the chat box since Phase 1. An audit of every `Enter` handler found the same hole in the
    notebook rename and the trace search; the other two act on a span and a separator, where there
    is no composition to interrupt.
  - **There was no search.** Distillation produces a title, a summary, tags and entities precisely
    so a node can be found by DESCRIPTION months later, and nothing could read any of it back: the
    product's stated promise was unimplemented. `GET /inbox` takes `q` now, matching over those four
    plus the origin, in the index and never in the block files (invariant 78). Tags are buttons.
  - **A repaint destroyed what the reader was doing.** The 900ms poll called
    `refreshInbox({reset: true})`, which emptied the stream and rebuilt every row: open rows snapped
    shut about once a second, selections died, and "Older" was undone. It patches only the rows
    whose serialisation changed now, and `inboxState.open` — which was written and never read — is
    read.
  - **A failed capture was a dead row.** The catch path returned before the actions, so there was no
    Forget, no File into and no retry; and it showed a raw `404 … has no stored text yet`, naming an
    internal id and the wrong cause, while the node's own stored error said what actually happened.
  - **Invariant 47 did not cover the one action that costs money.** `POST /inbox/distil` ran up to
    fifty sequential model calls inside the request with a disabled button as the only feedback. It
    starts a pass now; `GET /inbox/status` carries `done / total` and Stop reaches it.
  - **Focus was Chrome's cobalt ring**, on the most-used control on the surface, in a blue that
    exists nowhere in the palette and tight enough to cut the descenders of a node title.
  - **Faux-italic Han on the first text every reader sees.** No CJK face has an italic, so
    `font-style: italic` makes the browser SHEAR the glyphs, and the capture placeholder and the
    empty state are the whole first-run screen. There was not one `:lang()` rule in 4,800 lines.
    Fixed once, for the script rather than per component, and the three pre-existing sites are
    included because invariant 39 makes model prose follow the reader's language.
  - **Nine `border-left` accents of 2 to 3px**, including one on the first element you see entering
    a notebook — while the Inbox's own stylesheet carried a comment citing that exact ban. Two were
    carrying an accent and became background swatches; the rest are blockquote-shaped and keep the
    hairline the ban allows. Pinned by a tripwire.
  - Smaller: `約 20 千字` (Chinese counts in 萬); the notebook header and source list still showing
    `pasted:… #8fe0a5cd`; Forget styled as a label rather than a control; the reading face never
    reaching the chat answer or the guide body, which DESIGN.md §4 had listed as an open gap since
    Phase 2; the shell sprawling at 1680px; and no first-run explanation at all.

  **And one thing I tried and had to reverse.** The summary action was made sticky at the foot so it
  would not sit a scroll away from its rows. A sticky bar over a reading column permanently covers a
  line of prose, and softening its edge only made the cut look deliberate. It is one quiet line
  above the stream now.

  **And one piece of drift the docs carried for a whole stage.** `AGENTS.md`'s Scope note was
  written when the Inbox was library-plus-HTTP and said, twice, that **there is no UI for any of
  it** — once in the paragraph and once in the "Still unbuilt" list. It stayed false for the whole
  stage that built the UI, and nothing in the suite can catch a prose claim about what exists. Found
  by re-reading the file rather than by a test, which is the honest account. Both sentences now say
  the Inbox is the DEFAULT screen; `cli.py` still cannot reach it, which was the true half.

  Then the obvious follow-up: **"the Scope note has no tripwire under it" was a claim, not a fact**,
  and it turned out to be wrong for the parts of the note that name a symbol. `tests/test_docs.py`
  pins them BOTH WAYS, which is the part worth copying. A test that only fires when a claim becomes
  too MODEST would have caught this drift and nothing else; the mirror case - `cli.py` growing an
  `inbox` subcommand while the note still says the command line cannot reach it - is the same defect
  running the other direction, and it is now the same failing test. A third checks that every
  `([why](docs/invariants/...))` link resolves and that no argument file is orphaned, which the
  rename of 25 in this changeset would have needed. What is deliberately NOT asserted is the prose:
  "Word/Slides/Docs native-format parsing ... undone" is a claim about the ABSENCE of code and has
  no symbol to look for, so the file's own rule is to assert a claim only where a concrete symbol,
  route or filename decides it.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **869 passed**;
  screenshots at 1280px, 1400px and a true 375px, in Paper and Study, plus the expanded row.

- **The Inbox reaches HTTP: `/inbox/*` (10 endpoints), the opt-in auto-summary setting, and startup
  recovery.** Four slices of library work become usable; the UI is the next one.

  **Invariant 26 is the reason this endpoint is shaped the way it is, and the check is written here
  rather than inherited.** `intake.submit` accepts a local path perfectly happily, because
  `ingest_one` does — correct for `cli.py`, whose operator already trusts their own machine, and an
  arbitrary-file-read vector the moment the same function sits behind HTTP. That attack was
  reproduced end to end once (`POST {"sources": ["/etc/passwd"]}` read the file and echoed it back
  through a citation that PASSED verification), and **a second capture endpoint is exactly where it
  comes back**. `POST /inbox` takes http(s) and pasted text; files arrive at `/inbox/upload` as
  opaque bytes under invariant 30's pre-parse `Content-Length` cap.

  **`auto_distil` is a settings-page setting and its BOUND is not, which is invariant 41's rule and
  took a moment to get right.** (No control on the page yet at THIS point in the history; it lands
  later in this same `[Unreleased]` block, after an independent review found that a key with no row
  is a key the next Save erases.) A spend lever is exactly what
  that invariant keeps off a page every
  token holder can write. This is not one: `POST /inbox/distil` is already a spend endpoint any
  token holder can call, so the toggle changes WHEN summaries happen, not whether someone can cause
  them — a behaviour preference, which invariant 41 admits. `RN_AUTO_DISTIL_MAX_PER_BATCH` stays
  environment-only, beside trace retention and the upload cap.

  **Invariant 80's headline was rewritten, not stretched.** It read "Capture makes NO model call",
  and an opt-in auto path makes that false. Three earlier slices in this same body of work each
  shipped a doc asserting something the code contradicted, every one caught by review rather than by
  a reader — so the quantifier moved and the argument stayed.

  **The auto path lives in `api.py`, never in `intake.py`.** The queue gained an idle hook and knows
  nothing about what it does; `intake.py` still imports nothing model-related. That is what keeps
  invariant 80's default structural — capture cannot be made to spend money by editing the queue.

  **A bug found while wiring the lifespan, and it was the failure mode invariant 79 is named
  after.** `stop()` is terminal by design and the ASGI shutdown calls it — but `intake.shared()` is
  a PROCESS singleton, so a second server lifecycle in the same process (every
  `with TestClient(app)`, and any embedder starting the app twice) got a queue whose worker refuses
  to start. A URL captured after that sat at `queued` forever while the request returned 200.
  Measured, then fixed by having `shared()` rebuild a stopped queue, then measured again.

  **Two smaller things the tests forced out.** `_node_or_404` had to validate the id SHAPE
  explicitly: `get_node` is a SQL lookup, so a malformed id simply misses and is indistinguishable
  from a missing one — `DELETE /inbox/../../x` and `DELETE /inbox/<absent>` would have given the same
  answer for very different reasons (invariant 27's distinction, one tier down). And
  `inbox.is_node_id` is public now, so the HTTP layer can make that call without reaching for a
  private regex.

  Startup runs `resume_interrupted` — the only place that can, since a state naming a live owner is
  a lie only once the process that owned it is gone — and shutdown stops the queue with a SHORT
  timeout and reads the boolean, because blocking an ASGI shutdown for two minutes on an
  uninterruptible OCR pass is worse than abandoning a parse the next startup recovers.

  **An independent review drove a real server with ~60 curl probes and found two hard problems, five
  medium ones, and two surviving mutants.**

  - **A promotion losing a race with a deletion returned a raw 500 AND left the notebook holding a
    source nothing recorded.** `memberships.node_id` has a foreign key, so a node removed
    mid-promotion made the INSERT fail — by which time `mutate_notebook` had already written the
    source. Measured at **two of twelve** concurrent pairs. The two writes cannot be one transaction
    (one is a JSON file under a `flock`, the other is SQLite), so the repair is a COMPENSATING
    write: undo the append, and only the append — a promotion that merely FOUND an existing source
    must not remove someone else's.
  - **`auto_distil` was half-wired, and five files said otherwise.** It reached
    `config._SETTING_PATTERNS` and `settings_state` but not `SettingsRequest`, whose
    `extra="forbid"` then refused it with a 422 — so `GET /settings` reported a setting `PUT`
    rejected, and because the body is a FULL replacement, hand-editing `.settings` was wiped by the
    next legitimate save. A setting one half of the pair knows about is worse than one neither does.
  - **Three raw 500s from unbounded integers**, each from one ordinary request:
    `?offset=10**20` and `{"limit": 10**20}` reached `sqlite3` as `OverflowError`, and a malformed
    multipart body escaped `request.form()` as plain text — that last one **pre-existing on
    `/notebooks/{id}/sources/upload`**, which the Inbox's uploader had copied, so both are fixed.
  - **`?limit=-1` returned all 303 rows.** `min(limit, 200)` has no floor and SQLite reads a
    negative `LIMIT` as "no limit" — from the handler whose own docstring says it must stay cheap at
    thousands. Both bounds are in the signature now, and an out-of-range value is REFUSED rather
    than silently clamped (invariant 9's reasoning: a caller that asked for 500 believes something
    about what it got).
  - **A malformed `RN_AUTO_DISTIL_MAX_PER_BATCH` silently killed the intake worker**, while two
    files claimed it refused startup. `_env_int` raises `SystemExit` — a `BaseException` — which
    escaped the idle hook's `except Exception`, unwound the worker and ended the thread;
    `threading` swallows `SystemExit` without a traceback, so captures simply stopped being parsed
    with no signal at all. Both halves fixed: the bound is read at startup where the docs said it
    was, and the hook catches `BaseException`, because "anything it raises is logged and swallowed"
    has to be true for every exception or it is worth less than no promise.
  - **The auto-summary batch blocked the next capture and could not be stopped.** It runs on the
    queue's own worker thread, so a capture arriving mid-batch sat at `queued` for the whole batch —
    measured at 2.6s with one stand-in call and a minute or more at the default of 20 real ones.
    `should_stop`, which **had no caller anywhere in the repo**, now gets two reasons to fire: a new
    capture is waiting, or somebody pressed Stop.
  - **A multi-file upload silently kept only the last file.** `form.get` returns the last value for
    a repeated key, under a response shape (`{"nodes": [...]}`) that specifically reads as "several
    are fine". Dropping a file the reader chose is the one thing a capture surface must not do
    quietly.

  **Two surviving mutants, and the more important one was a promise this CHANGELOG had already
  made.** Removing the `shared()` rebuild left the whole suite green — the very fix the entry above
  describes as "measured, then fixed, then measured again" was pinned by nothing, because
  `test_api_inbox.py`'s fixture resets the singleton BETWEEN tests and the scenario is two
  lifecycles in ONE. Removing the 200-row listing cap also survived, which is why the negative-limit
  hole went unnoticed. Both are pinned now, and all six mutations the review ran are caught.

  **And one race was in a test I wrote**: it read the node's state and the call counter as two
  separate actions, with the next idle hook running in between — the same behaviour reported 6 and
  8 on different runs. The counter is recorded from inside the parse now.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **857 passed** (28
  new), three consecutive full runs, nothing reaching the network or a model.

- **Distillation (`distill.py`, invariant 80) — the summary that makes a capture findable again,
  and the cost rule that keeps it from being charged for silently.**

  **Why it matters most.** `docs/design/inbox-pivot.md` §8 ranks this FIRST of the three things that
  address the problem the whole pivot exists for, above surfacing and above any graph: *recall by
  DESCRIPTION instead of by the exact words you have forgotten.* The forgotten-keyword problem is
  the failure the user actually described — a hundred tabs they cannot close because the thing that
  would let them find it again is gone with the tab.

  **Capture makes NO model call, and that is a product rule.** BYOK is locked, so the reader's own
  key pays; the interface's whole message is "just throw everything in". Together those mean
  distilling at intake would spend **200 calls on a 200-bookmark import** the reader never asked
  for. So `intake.py` stops at `ready_undistilled` and `distil_pending` is a separate entry point
  with a `limit`, a `should_stop`, and a count that is knowable before it runs — invariant 47's "no
  action starts without an explicit press", applied to money instead of to time.

  **`ready_undistilled` is a real state, not a degraded `ready`.** A node whose summary failed still
  has its origin, its blocks, its flags, and can be promoted and cited like anything else. A failed
  or cancelled pass puts it back there and moves on; it never becomes `failed`, and one node failing
  never stops the others. Losing a capture because a summariser was unreachable would break the only
  promise this feature makes.

  **Two inherited rules meet here from opposite directions.** It reads `Corpus.excerpt`, never
  `blob()[:n]` (invariant 61 — a node built from a folder is several sources, which is exactly where
  a prefix is source ONE), and it strips `[[SRC:...]]` from what comes back (invariant 62 — the
  excerpt deliberately carries them and a summary is displayed prose).

  **The language ladder is SHORTER here, stated rather than discovered.** `distil_pending` runs with
  no request, so invariant 69's interface-language signal is out of reach. The ladder is
  `output_language()` → what the CALLER passes (a future HTTP handler has the request) → nothing, in
  which case the model follows the document. That last rung is **a known narrowing of invariant 39
  for Tier 0**, and the way out is a caller that passes the signal, not a resolver in a function
  with no request to resolve from.

  **Not an `RLMTask` and not in a subprocess.** `naming.py` already argues the first half; the second
  is new — `SuggestTitle` reaches the API's subprocess only because `api.py` routes it through
  `worker.py`, and spawning one per captured node would cost more than the call it isolates.
  `DistillNode` keeps `worker.py`'s `arun(**kwargs)` shape so that can change without touching
  callers. **`import dspy` lives inside `arun`**, because a top-level import would make every
  `cli.py` command pay for it — pinned by a subprocess blocker rather than by a comment.

  **An independent review ran a mutation ledger and two of the five mutants survived — both of them
  on claims invariant 80 makes about itself.**

  - **Deleting the sanitisation left 16/16 green.** The marker test hand-assembled the result by
    calling `_clean*` directly and never touched the shipped path. Worse than the test: the cleaning
    lived only inside `DistillNode.arun`, so every caller that injects its own `run=` — every test,
    and any future caller that swaps the model — wrote raw values straight into `inbox.update_node`.
    Measured: `distil_source` returned `title='T [[SRC:s1|whole]]'`. `_sanitize` is now applied in
    `distil_source` too (idempotent, so neither path can be the one that forgot), and the test runs
    through `distil_pending` and reads the result back out of the index.
  - **Swapping `Corpus.excerpt` for `blob()[:n]` left 16/16 green**, because the test asserted only
    that the text starts with `[[SRC:` and fits the cap — both true of either. The property that
    actually separates them here is marker COUNT: `excerpt` emits one per SOURCE, `blob` one per
    BLOCK. The test now uses a three-page PDF. Invariant 80 also said too much: `distil_source`
    takes ONE `Source`, so invariant 61's own incident is not reachable through this signature, and
    the rule is defensive rather than live — now stated that way.

  **A false claim, and it was the one about recovery.** Invariant 80 said a cancelled distillation
  returns the node to `ready_undistilled`. True for `should_stop`; **false for process death.**
  `distilling` was written in one place and reset nowhere, so a crash or a failing write-back
  stranded a node in a state nothing selects — with the call already paid for. Both owned states now
  live in one map (`inbox._OWNED_STATES`) recovered by `inbox.reset_interrupted_states`, with
  different fallbacks for a real reason: a `parsing` node has no blocks file, a `distilling` one
  does.

  **Three more, each measured.** Two concurrent passes over three nodes made **five model calls**,
  each overwriting the other's summary, because `state="distilling"` was a label — `inbox.claim_node`
  is a compare-and-set now. The "empty document costs nothing" guard read the EXCERPT, and
  `Corpus.excerpt` unconditionally prepends `[[SRC:...]]`, so a page trafilatura extracted nothing
  from still cost a call. And tags were lowercased AFTER deduplication, turning `["ML","ml","Ml"]`
  into three entries in what `schema.Distillation` calls "the join key a later slice needs".

  **Two smaller ones:** the caller's language rung never passed `clean_language`, while the docs
  point that rung at `X-RLM-Interface-Language` and `Accept-Language` — attacker-controlled headers
  spliced into the prompt; and `asyncio.run` inside a running event loop was swallowed by the bare
  `except`, so a FastAPI handler calling this would see every node bounce back with a log line
  indistinguishable from an unreachable model. It raises now, outside the `try`.

  All five mutations from the review's ledger are now caught, re-run to confirm.

  **Still no caller:** no API endpoints, no UI. `AGENTS.md`'s unbuilt list says so.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **829 passed** (31 new),
  none behind an `importorskip` and none needing credentials — every test injects the model call, so
  the module's own logic (the excerpt, the stripping, the ladder, the state machine) is what is
  exercised.

- **The Inbox's capture queue (`intake.py`, invariant 79) — and the process-wide PDF lock it closes
  a bug with that exists TODAY (invariant 3).**

  **The bug first, because it is not new code.** Invariant 3's argument is written about
  `ingest_new`'s internal loop and never considers two concurrent HTTP REQUESTS — but
  `api.add_sources` and `api.upload_source` both reach ingestion through `asyncio.to_thread`, which
  hands the work to the default `ThreadPoolExecutor`. **Measured, to this invariant's own standard:**
  two `POST .../sources/upload` fired with `asyncio.gather` against the real ASGI app overlapped
  inside the parser by **0.405s on two distinct threads**, and both returned 200. PDFium is not
  thread-safe — invariant 3's own `rc=134` — and ingestion runs in the API PROCESS rather than a
  `worker.py` subprocess (invariant 21 is about `RLMTask` EXECUTION, and parsing is not a task), so
  the SIGABRT takes the whole server down rather than one request.

  **The lock sits around `parse_pdf`, not around `ingest_one`, and that is the decision.** Invariant
  3 already says the honest thing about the wider change: *"the waiting is the network FETCH and the
  crashing is the PDF PARSE, but `ingest_one` fuses them, so separating them is a real refactor."* A
  lock on `ingest_one` would serialise the fetch too, and `web._default_fetcher` has a 15-second
  timeout — one slow page would block every capture for up to fifteen seconds. This is not that
  refactor; it is a mutex on a library that documents itself as thread-unsafe, at that library's
  door. Two tests, and the second is the point: one proves the lock, one drives the real ASGI app,
  because of invariant 3's closing line — *a suite that is green on the path you did not change is
  not evidence about the path you did.* Both confirmed to FAIL with the lock removed.

  **The queue: one worker, and a capture that always lands.** Submitting creates a `queued` node
  BEFORE anything is fetched, so the reader sees it immediately rather than watching a spinner with
  nothing behind it. The cost is that `kind` must be decided from the origin alone —
  `ingest.kind_for`, factored OUT of `ingest_one` rather than written beside it, because a second
  dispatch is how a `.pdf` URL ends up filed as `web`. It is EXACT for every input `ingest_one`
  handles (`parse_web` hardcodes `kind="web"` and does not sniff content type), so `store_blocks`
  overwriting `kind` is defence rather than a correction that happens today — a first draft of the
  invariant said otherwise, and a tripwire now drives the real `ingest_one` to keep them agreeing.

  **A parse failure is a state, not an escaping exception.** `ingest_one` reaches trafilatura,
  pypdfium2, yt-dlp and two OCR backends; any of them can raise anything. The worker catches broadly
  and records `failed` WITH the message, because both halves matter: the capture is never lost, and
  one bad link must not end intake for everything behind it. A worker that dies silently turns every
  later capture into a permanent `queued`, which is the worst available failure — it looks exactly
  like still working.

  **Stopping says only what it can do.** `cancel_pending` drops what is waiting; the item being
  parsed RUNS TO COMPLETION, because a native PDFium parse cannot be interrupted without taking the
  process with it. Cancelled items stay `queued`, which remains true of them, and
  `resume_interrupted` picks them up — resetting `parsing` rows (a state whose owning process is
  gone is a lie) but deliberately NOT `failed` ones, since retrying a failure on every restart is
  how a poisoned item becomes a loop. Invariant 60's rule about status lines applies here too.

  `test_items_are_parsed_one_at_a_time` was confirmed to fail when a second worker thread is
  started — the "the sources are independent, just parallelise it" regression that invariant 3
  records as having been written, measured, and crashed.

  **An independent review then found six concurrency defects in the queue, every one measured with
  a runnable probe.** None had shipped — `intake.py` has no caller — but each is a shape that comes
  back, and four of them broke the promise invariant 79 is named after.

  - **A node left at `parsing`.** `get_node`, the `parsing` write and `store_blocks` all sat OUTSIDE
    `_process`'s `try`. With a raising `store_blocks`: `state='parsing', error=None` — this
    invariant's own "worst available failure", the one that looks exactly like still working, and
    recoverable only by a restart.
  - **An orphan blocks file adopted with stale content.** A node removed WHILE parsing still got its
    blocks written, and `add_node` adopts an orphan. Measured: a re-capture with 10 characters of
    fresh text reported `chars=4`. Fixed in `inbox.store_blocks` rather than in the worker — the
    sink is the only place that knows whether the row survived.
  - **A second worker, i.e. invariant 3's forbidden shape from inside the thing built to prevent
    it.** `stop()` cleared `_thread`, released the lock, and only then enqueued the sentinel; a
    `submit()` in that window started worker #2 — measured at **−0.155s between consecutive parse
    windows**. The drain and the sentinel now happen under one hold of `_guard`; 300 racing
    submit/stop pairs produce exactly one worker thread.
  - **A relative `base_dir` re-resolved on the worker thread**, so a `chdir` split one node across
    two directories: the row under the old cwd, the blocks under the new one. Resolving once in
    `__init__` is the only reading that makes invariant 34 true for a thread.
  - `resume_interrupted` re-enqueued nodes already waiting — **four parse calls for two origins**,
    i.e. two network fetches each. And `status()` read `qsize()`, which counts the stop sentinel and
    reads zero between the worker's `get()` and its first state write, so it reported
    `{"running": False, "current": "nd-…", "pending": 1}` — denying and naming in one dict
    (invariant 60).

  **Three surviving mutants, and a claim that was too strong.** The review mutation-tested what I
  had not: replacing the removed-node guard with a `raise` left the suite green (the blanket handler
  swallowed it — a `caplog` assertion closes it); deleting the `state="parsing"` write left it green
  (nothing observed the state `resume_interrupted` exists to recover); and deleting `error=None`
  from `store_blocks` left it green (the covering test was satisfied by `submit`'s own clear). It
  also caught **five places, including invariant 79 itself, claiming `kind_for` is a guess because
  "a URL can serve a PDF"** — `parse_web` hardcodes `kind="web"` and has no content-type branch, so
  the two dispatches agree on every input and the overwrite is defence, not correction. All five now
  say so, and `test_kind_for_agrees_with_ingest_ones_own_dispatch` drives the REAL `ingest_one` with
  recording parsers — invariant 28's tripwire shape — rather than asserting the agreement in prose.

  **The lock's own cost is now named too**, because invariant 3's standard is to name the trade: OCR
  runs under it and `_try_rapidocr` builds a fresh `RapidOCR()` per page, so a long scanned PDF holds
  a process-wide mutex for minutes. Accepted — the alternative is SIGABRT — and it is also why
  captures through the queue, which are serial by design, never contend for it.

  **Still no caller:** no distillation, no API endpoints, no UI. `AGENTS.md`'s unbuilt list says so.

  **An intermittent warning, chased to its actual cause and left alone.** A full run reported
  `802 passed, 1 warning` about one time in five. It survived 18 consecutive clean runs (8 with
  thread-exception and unraisable warnings escalated to errors, 10 with `-rw`), and there is no
  order-randomising plugin, so it was not ordering. `-W error` named it: `zhconv/zhconv.py:36`
  loads its 1MB character table with a bare `open()` it never closes, and garbage collection
  decides which test the resulting unraisable `ResourceWarning` lands on — which is the whole of the
  intermittency. **Pre-existing and upstream**, reproducible alone with
  `pytest tests/test_instructions.py::test_the_wrong_script_table_never_flags_a_correct_traditional_character -W error`,
  a test that predates all of this work. Recorded against the dependency in `pyproject.toml` rather
  than silenced: a filter that hides the whole `ResourceWarning` class to quiet one third-party leak
  costs more than the leak does.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **804 passed** (29
  new), none behind an `importorskip`. Every fix re-checked against the probe that found the
  defect, and every new tripwire mutation-checked — including the two the review flagged as
  uncovered (`cancel_pending`'s sentinel branch and `submit`'s return type), each confirmed to fail
  against the behaviour it replaced.

- **Tier 0: the Inbox (`inbox.py`, invariant 78) — a global capture index that coexists with the
  corpus cap by never building a corpus.** Storage layer only; nothing calls it yet.

  **Why a second tier rather than a bigger notebook.** `config._DEFAULT_MAX_CORPUS_CHARS` is
  8,000,000 and its own comment says it is a memory-safety cap on the pyodide/deno sandbox, not a
  tuning knob — the whole corpus becomes ONE variable in the sandboxed REPL. One source measured in
  this project was **69,859 characters** (invariant 61's incident), so a notebook tops out near a
  hundred sources. A capture inbox is aimed at thousands. The two coexist because **nothing at Tier
  0 ever assembles a blob**: invariant 8 governs Tier 1 and is simply not in play here.

  **A node is a parsed `Source` that is not bound to a notebook yet.** That framing came out of
  reading the code rather than designing something new, and it is what made the tier cheap:
  `ingest.ingest_one` already produces a fully-parsed citable `Source` host-side (invariant 3), and
  `Source.marker()` COMPUTES `[[SRC:<id>|<locator>]]` from the id at blob time rather than storing
  it in the block text (invariant 4). So blocks can be stored with no id assigned, and **promotion
  is re-id + append, not re-fetch** — no new parsing, no new marker scheme, citations unchanged.
  The id comes from `append_sources`' max-in-use rule (invariant 50) inside `mutate_notebook`
  (invariant 34). Promotion does NOT consume the node, and removing a node does NOT reach a source
  already promoted from it — the source was copied, and a notebook silently losing a cited source
  because someone tidied their inbox would break invariant 12's promise.

  **Invariant 34's delta rule, carried to a global write surface, and enforced by the signature.**
  `update_node(node_id, **fields)` emits `UPDATE nodes SET <only those> WHERE id = ?`, and **there
  is deliberately no `save_node(node)`** — a whole-object write is the fault invariant 34 records,
  and distillation is exactly its slow step (a model call between reading a node and writing its
  summary). An unknown field raises rather than being ignored, which also puts `id` and
  `created_at` out of reach. Transactions answer the interleaving half and do it ACROSS PROCESSES,
  which is stronger than notebooks have: invariant 23 records that the API's in-memory maps have no
  multi-process story, and `notebook._THREAD_LOCKS` is single-process too.

  **A real bug, found by a new test, in the line that looked most harmless.** The first draft ran
  `PRAGMA journal_mode=WAL` on every connection, reasoned about as a no-op because WAL is a property
  of the FILE. It is a no-op only once the mode is ALREADY WAL: **changing it needs an exclusive
  lock, and SQLite does not invoke the busy handler for that change**, so the 15-second
  `busy_timeout` protects every statement in the module except that one.
  `test_concurrent_writers_all_land` failed about **one run in six**; a probe looping over fresh
  directories reproduced it on attempt 5 and put the traceback on that exact pragma. Moved into
  `_initialize` (once per process, in-process lock plus a retry for two processes creating the same
  new database) — the same probe then ran **60/60 clean**. Pinned by a SOURCE assertion,
  `test_connect_never_sets_the_journal_mode`, because the symptom is a flake that would pass five
  runs in six after a regression: invariants 36 and 54's reasoning, applied to a pragma.

  **A docstring claim caught by its own test.** `tests/test_inbox.py` asserts its no-`importorskip`
  claim with a meta-path blocker **in a subprocess** — an in-process blocker cannot see an import
  another test already cached in `sys.modules`, so it would pass by doing nothing on almost every
  full run. The subprocess immediately disproved the draft docstring: `inbox.py` DOES reach
  `rlm_harness`, through `notebook.py` -> `ingest.py` -> `parsers/web.py`'s SSRF guard. The claim
  that matters is about the EXTRAS (`api`, `chatterbox`), and it holds; both docstrings now say the
  true thing instead.

  **An independent review then found three data-loss paths, all reproduced with runnable probes
  rather than reasoned about — and two of them were things invariant 78 itself asserted were safe.**

  - **A node id became an arbitrary path.** `node_blocks_path` interpolated a caller-supplied id
    straight in, and `remove_node`'s `unlink` sat outside the `if changed` guard. So
    `remove_node("../../notebooks/mynb")` **deleted a live notebook file and returned `False`**, and
    an absolute id discarded the directory entirely, because `Path("inbox/nodes") / "/etc/x"` IS
    `/etc/x`. Worse than the bug: invariant 78 SAID this could not happen — *"the id is hex, so it
    is filename-safe by construction and invariant 10's traversal problem cannot arise"* — which is
    true of ids the module MINTS and false of ids it RECEIVES, the exact distinction invariant 10
    exists to draw, and which would have told whoever writes `DELETE /inbox/{node_id}` that no guard
    was needed. Now validated against the minting pattern AND contained by a resolved-path check.
  - **Capture was not idempotent under concurrency.** SELECT-then-INSERT is a check-then-act and
    `isolation_level=None` means nothing spans the two. Eight threads on one origin, released from a
    barrier: **seven `IntegrityError`**, against a docstring promising "rather than raising" — and
    `IntegrityError` is not an `OperationalError`, so `busy_timeout` never sees it and nothing
    retries. The surviving row said 80 characters against 40 on disk, because every losing thread
    still wrote the blocks file. Fixed with a capture lock, `ON CONFLICT(id) DO NOTHING`, and
    adopting an existing blocks file instead of overwriting it. **This was invariant 78's second
    false claim**: it said transactions answered the interleaving "across processes, which is
    strictly stronger than what notebooks have". There are no multi-statement transactions in the
    module at all, and against `mutate_notebook`'s real cross-process `flock` the Inbox is WEAKER
    here. The invariant now says so.
  - **Two nodes sharing an origin silently shadowed each other.** `append_sources` dedupes by
    ORIGIN; promotion read "appended nothing" as "this same node is already here". It means *some*
    source shares the origin. Both nodes recorded a membership pointing at the FIRST node's source,
    the second's text never reached the notebook, and `promote_node` returned success. Identity now
    comes from the node's own membership row, and an origin collision is a loud error.

  **Two smaller ones, and a hollow test.** A bad VALUE (`state="bogus"`, `tags=None`) committed and
  then broke every later `list_nodes()` — the whole page, not just its row — so deltas are now
  validated per field before the write. The initialization cache went stale if `inbox/` was deleted
  under a running process, permanently. And `test_update_node_writes_only_the_fields_it_was_given`
  **passed against a deliberately whole-row implementation**: two sequential `update_node` calls
  cannot see the difference, because each re-reads inside itself. It now reads the SQL that was
  actually emitted and asserts it names the caller's columns and nothing else.

  Thirteen regression tests came with the fixes, each named after the failure it reproduces.
  `inbox.py`'s module docstring was also cut from 61 lines to 42: it had grown a full copy of the
  argument that belongs in `docs/invariants/78` and the incidents that belong here, which is the
  drift AGENTS.md's three-way split exists to prevent, one level below the index it protects.

  **Deliberately not built here:** no intake queue, no distillation, no API endpoints, no UI, no
  new parsers, no embeddings and no graph (`docs/design/inbox-pivot.md` §8 argues the graph is
  decorative and the edges that matter — citations — already exist). `AGENTS.md`'s unbuilt list
  says so rather than leaving it to be discovered. `/inbox/` is gitignored: it holds a user's whole
  capture history.

  **Verified:** `uvx ruff@0.16.0 check .` clean; `uv run python -m pytest -q` → **775 passed** (38
  new, none behind an `importorskip`); `test_concurrent_writers_all_land` 15/15 against a recorded
  ~1-in-6 baseline.

- **Every API request now needs a token (invariant 77), because "reachable only from this machine"
  was never the same property as "reachable only by this app".**

  **What changed and why now.** Invariant 25 said this API has no authentication, and that `serve`
  binding `127.0.0.1` is therefore the entire access-control story. That was true, and it was
  adequate for as long as the only thing that ever talked to this server was a page the same server
  had just handed the user. The Inbox pivot (`docs/design/inbox-pivot.md`) adds a desktop shell and
  a browser extension, and the moment a SECOND client exists the assumption breaks — every browser
  the user runs is also on this machine. Any page in any tab can POST to `127.0.0.1` and ignore the
  response, which is enough for all three live `DELETE`s and for the global `PUT /settings`. DNS
  rebinding goes further and reaches READS, where `GET /notebooks/{id}/sources/{id}` returns a
  source's FULL TEXT (invariant 31) and a trace can hold full ingested source text (invariant 29).

  **Two defences, answering two different attacks.** The token is the real one: a cross-origin page
  cannot read the URL the token arrived in. The `Host` check answers rebinding specifically, and the
  rule is *a literal IP address, or `localhost`* — which needs to know nothing about what the server
  actually bound, because rebinding is a thing you do to a NAME. `192.168.1.5:8000` is unaffected;
  `RN_ALLOWED_HOSTS` is the carve-out for a name that is genuinely the operator's, the same shape and
  the same reasoning as invariant 76's `RN_FETCH_ALLOW_CIDRS`.

  **Deny by default, which is why it is a middleware and not 25 dependencies.** `auth.PUBLIC_PATHS`
  is the static mount's own files, computed from the DIRECTORY rather than listed, so a route added
  later is protected because nobody did anything and an asset added later keeps working. Twenty-five
  routes existed when this was written; `dependencies=[Depends(...)]` on each is twenty-five chances
  to forget, with a failure that is silent and invisible in the response. This is invariant 24's
  "the RULE is the invariant, NOT the current list of places it applies", and
  `test_every_registered_api_route_is_protected` walks the actual route table so it is enforced
  rather than stated.

  **The query-string form is forced, not lazy.** `EventSource` cannot set request headers at all,
  and neither can `<audio src>` or a download `href` — the live trace stream and the persisted
  episode are reached by exactly those. A header-only token would make both unreachable, and the
  ticker's failure mode is SILENT (the answer still arrives; the ticker just never ticks). The cost
  is accepted with its eyes open — `app.js` strips the token from the address bar the instant it
  reads it, and `serve`'s non-loopback warning now names the query-string exposure explicitly.

  **Invariant 25's file was RENAMED, not just edited.** It was
  `25-the-api-has-no-authentication.md`, and that name had become false. Its authorization half is
  untouched and is the half that still matters: the token authenticates THE APPLICATION, not a
  person, so every holder remains fully privileged over every notebook and over global settings.

  **Deliberately not built:** accounts, sessions, per-user authorization, and any way to turn the
  token off. A `--no-token` flag re-creates the exact hole this closes and would be reached the
  first time anything looked inconvenient; an operator fronting this with their own auth sets
  `RN_API_TOKEN` to something their proxy injects, which is the same escape hatch without a switch
  labelled "off". `RN_API_TOKEN="   "` falls back to the minted token rather than reading as
  "authentication off" — pinned by a test.

  **Five defects the repo's own tripwires caught while this was being built**, which is most of the
  argument for having them:

  - **`test_no_translated_string_carries_an_english_dash`** caught a `——` in the new `zh-Hant`
    error string on the first full run. The dash is already full-width; the English habit is not.
  - **`TestClient`'s default `base_url` is `http://testserver`, a DNS NAME**, which the new Host
    check refuses — so nine clients went red at once. The fix was to point the tests at a literal
    address, NOT to allow `testserver` in the guard: putting a test hostname inside a security
    control is how the control quietly stops being one.
  - **`serve`'s non-loopback warning said "NO AUTHENTICATION", and that became false.** Its test
    asserted the WORDING, so it failed loudly — and the fix was to assert the CLAIM instead (the
    token is the only protection, there is no authorization behind it, it travels in cleartext).
    Asserting phrasing is what would have let the warning quietly become a lie.
  - **`playground/smoke.mjs` caught `rlmnb-api-token`** against its rule that every key the
    workspace persists is either cleared on load or deliberately exempt. It is cleared: the
    playground has no backend at all, so a token there can only sit in a public demo page's
    storage. It is workspace state, not a reader preference.
  - **`URL` is not a global in a Node `vm` context** (it is a WHATWG addition, not an ECMAScript
    intrinsic), and `captureApiToken` runs at TOP LEVEL — where anything it throws takes every
    `init*()` below it down and renders a blank page. The whole body is now guarded. Failing soft
    costs the reader one re-opened URL; failing hard costs them the application.

  **An independent review found the real gap, and it was not in the code.** The implementation had
  no reachable path without a token — the review probed framework routes (`/docs`, `/openapi.json`,
  `/redoc`), `HEAD`/`OPTIONS`, `root_path`, and path confusion through raw ASGI scopes (`//app.js`,
  `/./app.js`, `/app.js/`, `/%61pp.js`, `/APP.JS`), and every divergence between `request.url.path`
  and the static mount fails CLOSED. What it found instead was **36 places across 31 files still
  asserting in the present tense that this API has no authentication**, five of them user-facing or
  self-contradictory: `AGENTS.md`'s "Still unbuilt" list taught the opposite of `AGENTS.md`'s own
  invariants 25 and 77 three hundred lines later; `--host`'s argparse help printed the old claim to
  anyone running `serve --help`; and `_cmd_serve`'s docstring said "Until this grows auth" forty
  lines above where it grew auth.

  **The sweep distinguishes three cases, and only one of them changed.** Historical narration ("this
  WAS an unauthenticated 500, found by an independent review") is still true and was left alone, as
  was every dated `CHANGELOG` entry. Still-true AUTHORIZATION claims were kept. What was rewritten
  is the present-tense assertions — including in `docs/invariants/` itself, where the ARGUMENT for
  41, 42, 52 and 53 genuinely changed: each rested on "anyone who can reach this server", which is
  now false. An independent enumeration caught a spelling the review's own list had partly missed,
  the hyphenated `no-auth`, in seven more places.

  **One corollary is now written down rather than merely true:** `PUBLIC_PATHS` is the WHOLE `web/`
  directory, so `GET /DESIGN.md` answers 200 ungated. `StaticFiles` already served it, but this
  change codifies "anything in `web/` is public" as a security rule, which makes dropping a file
  there a decision about publishing.

  **Verified:** `uv run python -m pytest -q` → 737 passed (29 new: 21 in `tests/test_auth.py`, which
  deliberately carries NO `importorskip` so it runs on a bare `uv sync`, and 8 in `test_api.py`
  driving the middleware). `uvx ruff@0.16.0 check .` clean. A REAL server was exercised end to end
  with curl, not only `TestClient`: no token → 401, bearer → 200, `?token=` → 200, static asset with
  no token → 200, `Host: evil.example` with a VALID token → 403, `audio/file?v=1&token=` → past auth.
  `playground/smoke.mjs` → 13 failures, identical to the pre-change baseline measured by stashing
  (all of them "0 recorded runs", which is `traces/` being gitignored on this machine).

- **The OCR backend moves from `rapidocr-onnxruntime` to `rapidocr`, which unblocks Python 3.13
  and 3.14 and reads better while it is there.**

  **The packaging problem it solves.** `rapidocr-onnxruntime` was frozen at 1.4.4 in January 2025
  and declares `Requires-Python >=3.6,<3.13`, so `pip install` refused this whole project on 3.13
  and 3.14 while uv resolved past the bound — the manifest said `>=3.11` and pip disagreed, and the
  error named rapidocr rather than rlm-notebook. `rapidocr` is the same upstream project
  (RapidAI/RapidOCR, Apache-2.0, a commit the day this was written), declares `>=3.8,<4`, and was
  verified installing, importing and RUNNING on both 3.13 and 3.14 before anything was changed
  here — invariant 43's "nothing is adopted until it has been installed and run".

  **The alternative was capping at `<3.13`, and it was evaluated and rejected.** Python 3.14 is
  current and 3.13 is one behind, so the cap gives up two generations, not one; 3.11 reaches
  security-EOL in October 2027. It kills the `chatterbox` extra outright (marked `>= 3.13`), breaks
  the development environment (every venv here is 3.13), and expires anyway. It buys a shrinking
  window; the migration buys the package upstream actually maintains.

  **It is also measurably more accurate, which was not the reason but is the bigger one.** On one
  rendered two-column page, 7 of 12 regions differ and the new model is right in every case: the
  old recogniser drops word spacing (`thebenchmark`, `sublayerswhichareapplied`). For a project
  whose citations are verified by exact `quote` matching (invariant 5), losing word boundaries is
  worse than a wrong character. On a three-line Traditional Chinese fixture, 3/3 exact against 2/3,
  rendered through the `.ttc` face index invariant 7 records as the trap that makes such a
  measurement worthless, with the ink checked before believing the number.

  **A defect the migration created and a test caught.** The old return was one list of
  `(box, text, score)` rows; the new one is two PARALLEL sequences, `boxes` and `txts`. A plain
  `zip` truncates to the shorter and returns a partial page as though it were the whole one, which
  a length mismatch made representable for the first time. `strict=True` raises instead, which
  lands in the existing `except` and falls through to Tesseract. Invariant 44's `Podcast.offsets`
  lesson on a second parallel pair.

  **Every fake in `tests/test_parsers_ocr.py` had been passing against a contract the library no
  longer had**, because a monkeypatched name cannot notice that the thing it replaced changed
  shape. They are `_Out` stand-ins now, and a new test pins that stand-in against the REAL
  `RapidOCROutput` dataclass so the next such change fails in the suite.

  Also: `onnxruntime` becomes an explicit dependency (`rapidocr` 3.x supports six engines and pulls
  none), the shipped models are PP-OCRv6 and live IN the wheel rather than downloading at first use
  (checked in its `RECORD`, which is what keeps the container working with no network), the
  container base moves back to 3.13, and `_quiet_rapidocr` raises the library's own log HANDLER to
  WARNING — the LOGGER cannot be quieted, because several rapidocr modules reconstruct it at
  import time during `RapidOCR()` and reset the level, which measured as still nine lines per page
  and over five hundred on a 260-page scan.

  **The container was then built and driven**, which is where the models-in-the-wheel claim stopped
  being a reading of a `RECORD` file: `docker run --network none` OCR'd a rendered line correctly,
  so the image needs no npm or model egress to do the one thing it exists for. Python 3.13.15,
  deno 2.1.4, tesseract 5.5.0, rapidocr 3.9.2, onnxruntime 1.29.0; `/notebooks`, `/`, `/settings`
  and `/settings/choices` all 200 with no model configured; one stderr line where there were nine,
  and it is onnxruntime's own `Unknown CPU vendor` note under Docker Desktop on aarch64, not ours.
  The same run incidentally confirmed two earlier fixes end to end: `PYTHONUNBUFFERED=1` makes the
  data-directory line reach `docker logs` at all, and the loopback warning fires on the image's own
  `--host 0.0.0.0`.

- **`rlm-notebook serve`, a container, an install story for an application, and the three
  independent reviews that found what all of it was missing.**

  **The shape was wrong before the code was.** This was being described as "a service that goes
  online", and it must not be: invariant 25 means any caller who reaches it can read every
  notebook's full source text and reasoning traces, delete sources, and change global settings. It
  is a LOCAL application with a web UI, in the shape of jupyter or aider. So PyPI is the right
  channel and `pip install` was the wrong VERB — nobody imports `rlm_notebook`, and installing it
  into a shared environment drags numpy, an ONNX runtime and a PDF engine along. `README.md` leads
  with `uv tool install` / `pipx` now, and the `git clone` + `uv sync` that used to be the whole
  section moved under "To develop it".

  **`serve` binds 127.0.0.1 by default**, and that default is in code rather than in a README
  paragraph because, with no authentication, which interface it binds IS the access control. A
  non-loopback `--host` is allowed (a trusted network is a use the README sanctions) and warns.
  `_is_loopback` treats `""` as EXPOSED: `bind("")` is `INADDR_ANY`, and a first draft listed it
  beside `"localhost"` as obviously local, which would have silenced the warning on precisely the
  binding that most needs it. Found by printing the classifier's own table rather than reading it.

  **The Dockerfile exists for one reason**: `deno` and `tesseract` are system binaries no Python
  manifest can express, so no `pip install` is ever complete on its own. Built and run rather than
  claimed: deno 2.1.4 and tesseract 5.5.0 in the image, a container answering `/notebooks`, `/` and
  `/settings` with no model configured.

  **Three independent reviews, and every finding below was reproduced before being acted on.**

  The commit's own security claim had NO TEST. Three mutations survived all 51: flipping the
  default host to `0.0.0.0`, deleting the entire warning block, and sending the warning to stdout.
  The only test exercised the pure `_is_loopback` predicate, so nothing asserted it was wired to
  anything — the thesis was exactly the part with nothing behind it. Replaced with tests that drive
  `_cmd_serve` against a stubbed uvicorn.

  **Invariant 35's core sentence had become false.** It said `rlm_harness.configure` does not route
  on the `claude-agent-sdk/` prefix, so `config.setup`'s injection is what makes the sentinel work.
  `rlm-harness==1.10.0` routes on the identical prefix itself. Behaviour never changed — an
  explicit `main_lm=` still wins — which is exactly why nobody noticed the justification had
  expired. The injection WINS rather than enables, and deleting it would now "work", which is the
  trap: it would hand every subscription run to a construction this project has never measured.

  **The playground's Studio → Insight threw on every notebook, always**, and faq and timeline told
  readers their own sources "didn't produce enough" — a fabricated claim on the one page whose
  premise is that nothing there is fabricated. The guide fallback returned a field `app.js` reads
  nowhere. **Its trace step ringed the wrong button** on four of six notebooks including the default
  English one, because `regenerateTurnButton` carries the identical `ticker-toggle` class and only
  the trace pill is wrapped in `.ticker-affordance`. **And every mutating shim route wrote to a
  copy**: a deleted source came back, a rename reverted, a cleared conversation reappeared. Notes
  were the single exception, because `view` spreads them by reference, and that exception is what
  hid the class from the assertions already in the suite.

  **One review suggestion was measured and REJECTED.** Capping `requires-python` to `<3.13` to make
  pip's rapidocr refusal legible breaks the development environment outright: every venv here is
  3.13, uv resolves past rapidocr's bound, and the `chatterbox` extra (marked `>= 3.13`) becomes
  unsatisfiable. `uv run` stopped working entirely. The limit is stated in `README.md` instead.

  Also: `--port 99999` raised `OverflowError`, which is not an `OSError`, so uvicorn's own startup
  guard never caught it. The serving line announced a URL one line BEFORE the bind and was
  block-buffered away entirely in the container. The image shipped MIT metadata with no LICENSE and
  discarded deno's 15MB pyodide cache outside the mounted volume. `↓ Download` 404'd because the
  media-element hook never sees an anchor. Stop did not stop. Doc drift closed across invariants
  20, 25, 29, 41 and 47, `.env.example`, `DESIGN.md` and `api.py`'s docstring, which FastAPI serves
  at `/docs` and which was still teaching readers the raw uvicorn command that routes around the
  loopback default.

- **A second private sibling scrubbed, the other one's fingerprint scrubbed, and every doc-drift
  item the three-reviewer round left open is now closed.**

  **Names.** A second sibling project turned out to be private too, and is gone from all six tracked
  sites (`naming.py`, `schema.py`, `tests/conftest.py`, three CHANGELOG entries) — including a design
  note's FILENAME, which identified it as surely as the name did. Three other sibling projects named
  in this repo are not private and stay.

  **Fingerprint.** Removing a name is not removing an attribution: phrases describing the shape of
  the other sibling's deployment — its document type, the nature of its corpora, and the size of its
  output — identified it to anyone who knew it existed. Rewritten to carry the same evidence — bodies
  versus TITLES, technical rather than literary corpora, 89,160 Han characters of deployed output —
  without the shape.

  **The dead "web-UI blueprint" pointers, 16 of them, now point at tracked files.** That document is
  deliberately gitignored working notes, so `api.py`, `schema.py`, `parsers/youtube.py` and
  `web/DESIGN.md` were sending readers to "Phase 3 addendum P3.1" and "audit round 1" — findable by
  one person. Each now names the `docs/invariants/` file that actually holds the reasoning. The two
  in `CHANGELOG.md` stay: they are history and say "gitignored" themselves.

  **Four places described a UI that had been replaced.** Invariants 31, 36 and 44 and `DESIGN.md`
  still specified the per-answer citation LIST — clickable `.citation-row`, a per-row `⌁ trace`
  icon, `showCitationTurn`/`_shownKey` — none of which exists in `app.js`; invariant 58's References
  panel replaced all of it, and `style.css` keeps only dead rules. Invariant 44's stated exclusion
  list was the sharpest case: it named two dead classes and MISSED `.reference-link`, the live one,
  which is why clicking "2 references" used to jump the podcast player. **A stale exclusion list
  costs nothing until the thing it forgot to name ships.** Marked SUPERSEDED rather than deleted,
  because older CHANGELOG entries still describe the earlier shape.

  Also: `AGENTS.md`'s Verify section claimed `tests/test_runner.py` needs the `api` extra to be
  collected. It has no `importorskip`, `rlm_notebook.runner` imports with `fastapi`/`starlette`/
  `httpx`/`uvicorn` blocked (verified with a meta-path blocker, as that section itself demands), and
  CI names only `test_api.py` — so its 9 tests, invariant 22's `killpg` grandchild tripwire among
  them, run on a bare `uv sync`. `api.py` documented a citation "view reasoning" link that no client
  calls. `README` described a citation → source-viewer modal reachable from no shipped affordance,
  and understated the unauthenticated surface by omitting three live `DELETE`s and the global
  `PUT /settings`. `DESIGN.md` contradicted invariant 57 on `#chat-overview` and claimed "no spinner,
  no pulse, no sweep" against three shipped keyframes.

- **A third reviewer checked the docs against the code and found two claims that were simply
  false, one of them a rule forbidding exactly the sentence another file was making.**

  - **`naming.py` asserted that "`api.py` continues to import neither `dspy` nor `rlm_harness`".**
    Invariant 21 names that sentence and says **"it is FALSE and was verified false"** — the
    guarantee is about EXECUTION, not imports. Confirmed empirically: `import rlm_notebook.api` puts
    both in `sys.modules`. One file in the package was asserting what an invariant explicitly forbids
    asserting.
  - **Invariant 6 and `README.md` said the injection flag was CLI-only and invisible to the API and
    the web UI.** The premise was right (`AskResponse` carries no flags) and the conclusion wrong:
    `api.py` emits `flags` on every source in `NotebookResponse` and on `SourceDetailResponse`, and
    `app.js` renders an amber `⚠` chip in the Sources list — **from a block whose own comment cites
    invariant 6 while contradicting it**. An ANSWER shows no flag; the SOURCE shows one everywhere.

  Also corrected: `AGENTS.md`'s header still described the pre-split TWO-place arrangement and never
  mentioned `docs/invariants/`, so an agent following it would have put the argument straight back
  into the index the split exists to keep small. Invariant 33's "`web.py` is UNCHANGED" was falsified
  by the carve-out one commit earlier. `api.py`'s `Endpoints:` list — which is also its OpenAPI
  description — named 17 of 25 routes, omitting all three `DELETE`s. `max_tokens` was described as
  "the PLANNER's" cap in two places, which invariant 59 explicitly corrects. `README.md` did not
  mention `RN_FETCH_ALLOW_CIDRS`, the one new knob whose absence breaks every ingestion behind a
  fake-IP proxy.

  **Two of the three reviewers disagreed about invariant 75, and the disagreement was an artefact of
  timing**: the second found its body undedented and carrying a stray section-closing line, the third
  read the file after that was fixed and reported the finding as fabricated. Both were looking at
  real states. Worth recording because a later reader comparing the two reports would otherwise trust
  the wrong one — `git show d660f5f:docs/invariants/75-*.md` settles it.

- **An independent review of the four preceding commits found that the SSRF carve-out's
  documentation and its test both asserted a guarantee the code did not provide.** `.env.example` and
  invariant 76 said "loopback and cloud-metadata targets stay refused regardless of what you list
  here; that check is syntactic and this does not reach it". True only for a URL whose host is a
  LITERAL blocked IP. `is_safe_url` returns True for `http://evil.example.com/` however that name
  resolves, so the DNS-rebinding check is the only layer that ever sees the resolved address — and
  `allow_nets` short-circuits every property it tests. Under `RN_FETCH_ALLOW_CIDRS=0.0.0.0/0` a
  public-looking hostname resolving to `127.0.0.1` or `169.254.169.254` was fetchable end to end,
  through a redirect, on an API with no authentication (invariant 25).

  **The test that "pinned" it was vacuous, and that is the sharper lesson.** It used literal-IP URLs,
  which `is_safe_url` rejects before `resolved_host_is_safe` is consulted — so it passed with the
  `resolved_host_is_safe` call DELETED from `_check_safe`, and all 669 tests stayed green under a
  mutant that opened every IPv6 internal target. **A guard test that never reaches the guard is worse
  than no test, because it gets cited as proof.** The replacement resolves a public-looking hostname
  to each internal address in turn, and both mutants were re-run to confirm it now fails on them.

  **Fixed by making the dangerous configuration unrepresentable rather than by softening the
  wording.** `config._NEVER_ALLOWED` refuses any entry overlapping loopback, RFC1918, link-local,
  unspecified or multicast, so `0.0.0.0/0`, `::/0` and `10.9.0.0/16` are rejected at read time and
  the documented guarantee is true again by construction. It is an explicit list rather than
  `ipaddress`'s `is_private`/`is_reserved`, because `198.18.0.0/16` reports `is_private` True and a
  property-based rule would refuse the one value the variable exists to accept. This also closes a
  hole the "does it parse" validator missed: `198.18.0.0/16` with a dropped character is
  `198.18.0.0/1`, which normalises to `128.0.0.0/1` — cloud metadata and `192.168/16` included — and
  parsed cleanly. Accepted and stated: a split-DNS VPN mapping into RFC1918 cannot be carved out.

  The `SystemExit`-to-500 arm added in the previous commit was unpinned; it has a test now.

- **The same review found four defects in the invariant split itself.**

  - **Invariant 75's body was never dedented** — it is the last invariant, so the extractor swept in
    the line that closed the whole section, and that line sits at indent 0, making the "minimum
    indent" dedent a no-op. Three of its four paragraphs were rendering as indented CODE BLOCKS. The
    stray closing line ("...behind every invariant above") went with it, where it was false.
  - **`textwrap.fill` broke four hyphenated words across lines** (`rlm-notebook`,
    `script-generation`, `source-handling`, `Accept-Language`), and markdown renders a paragraph
    newline as a space, so the index read `rlm- notebook`. **Re-wrapping cannot fix this**: collapsing
    `rlm-\n    notebook` turns the newline into a space, making them two separate words that wrap to
    the same place. They had to be re-joined explicitly first.
  - **The scrub's capitalisation pass fired on LINE start, not sentence start**, leaving
    `The sibling` / `A sibling project shipped` across a wrap in invariant 39.
  - **Two pointers promised "the full account" at what is now a three-line index entry**
    (`pyproject.toml`, an older CHANGELOG entry); both now point into `docs/invariants/`. README said
    `AGENTS.md` was the authoritative record without mentioning where the arguments went.

  A new check asserts every index lead matches its detail file's opening statement VERBATIM — that is
  what surfaced three of the four word-splits. The reference count in the rename entry was 139, not
  144; corrected.

- **The private sibling project is no longer named anywhere in tracked files.** 28 references
  across `CHANGELOG.md`, `docs/invariants/`, `instructions.py`, `config.py`, `trajectory.py` and four
  test files now say "a sibling project". Nothing else changes: every measurement it supplied — the
  3,683-call token distribution, the 287-of-972 first-in-turn figure, the Big5 let-through
  enumeration, the phrase-aware suggestion defect — is still recorded with its numbers, because the
  evidence is what makes those decisions reviewable and only the attribution had to go. The repo is
  private, so this closes an exposure that would open the day it is not.

- **Web and YouTube ingestion was refusing EVERY URL behind a fake-IP proxy, and the failing test
  saying so was dismissed three times as a sandbox artifact.** `_check_safe` called
  `resolved_host_is_safe(host, port)` with no `allow_nets`, so on a machine running Clash / Mihomo /
  Surge — where every public hostname resolves into the fake-IP range `198.18.0.0/16` — the guard
  refused everything. Verified end to end on the developer's machine: `parse_web("https://example.com/")`
  raised `refused: … resolves to a disallowed address` before the fix and returned the page after it.

  **The misreading is the transferable part.** `test_default_fetcher_uses_the_guarded_opener_never_plain_urlopen`
  had been failing locally and passing in CI, and three commit messages in a row recorded it as
  "pre-existing and unrelated". Two separate faults were hiding behind that phrase: the test does live
  DNS, which violates the suite's stated "fully offline" property, AND the product genuinely refused
  every URL on that machine. **A test that fails on one developer's machine and passes in CI is
  evidence about the product until someone proves otherwise** — "pre-existing" describes when it
  started, not whether it matters. The first fix drafted here stubbed the guard in the test, which
  would have made the suite green and left ingestion broken.

  Now: `RN_FETCH_ALLOW_CIDRS` (a standalone reader, invariant 30's reasoning), resolved once in
  `web.allow_nets` and imported by `parsers/youtube.py` rather than re-read, so the two host-side
  fetchers cannot disagree. The carve-out reaches only the DNS-rebinding half — `is_safe_url` is
  syntactic and still refuses loopback and metadata targets at `0.0.0.0/0`, which a test pins. The
  refusal message names the variable, since the failure is otherwise indistinguishable from a genuine
  SSRF refusal.

  **An unparseable entry raises instead of being skipped, inverting upstream's own policy on purpose.**
  `rlm_harness.tools.parse_cidrs` warns and drops one so a typo "can't sink a run"; here, dropping the
  only entry restores full strictness and reproduces the exact symptom the variable was set to fix.
  That `SystemExit` turned out to be invariant 24's documented trap, live: `add_sources` caught
  `(FetchError, ValueError, OSError)` and nothing else, so a malformed variable would have escaped a
  request handler as an unhandled 500.

  Suite is **669 passed, 0 failed** — green for the first time in this sequence of changes.

- **The 76 invariants are an INDEX in `AGENTS.md` plus one file each under `docs/invariants/`.**
  (77 files: 1-76 plus the half-numbered 48.5.)
  `AGENTS.md` goes from **53,300 to 8,800 tokens** — every request had been carrying the full
  argument for OCR two-column reading order while someone edited CSS. Each index entry keeps the
  rule verbatim and one sentence of the sharpest reason; the argument, the cost and the traps move
  to `docs/invariants/<n>-<slug>.md`, reachable by a `([why](…))` link. Every one of the files
  was verified to contain its invariant's original text verbatim before the section was replaced.

  **Agent-agnostic on purpose, and that ruled out the mechanism that would have been easier.**
  Claude Code's `.claude/rules/` with `paths:` frontmatter auto-loads a rule when a matching file is
  read — no model choice involved — but nothing except Claude Code reads it, so splitting that way
  would have hidden 41% of the rulebook from the very agents the `AGENTS.md` rename exists to serve.
  A markdown link works everywhere. The cost is real and stated: a linked file is read only if the
  agent chooses to, which is why every index entry carries a reason and the preamble says to read
  the file before overturning anything.

  **The index is declared non-growing, with the failure mode measured rather than imagined.** A
  sibling repo made this same split: its indexed section has held at ~5,100 tokens for 56 decisions,
  while an un-indexed section beside it grew to ~55,600. So the split is not self-sustaining — the
  rule is that an index entry which has acquired a second paragraph has taken on something belonging
  to `docs/invariants/` or `CHANGELOG.md`, and moves there.

  `docs/` is otherwise gitignored here as a scratch area, so `docs/invariants/` is a tracked
  exception. The shape matters and was verified in a scratch repo rather than assumed: `/docs/*`
  excludes the CONTENTS and lets `!/docs/invariants/` fire, where `/docs/` would exclude the
  directory itself and stop git ever descending into it, making the negation silently dead.

- **The agent guide is `AGENTS.md` now, with `CLAUDE.md` as a one-line `@AGENTS.md` bridge.**
  `AGENTS.md` is the cross-agent standard; Claude Code reads `CLAUDE.md` and not `AGENTS.md` (its own
  documentation says so in as many words), so a project with only one of the two hands the other side
  nothing. 139 references across 45 files were rewritten with it — test docstrings, `pyproject.toml`
  comments, `.env.example`, `.gitignore`, `README.md`, `web/DESIGN.md` and the module docstrings that
  cite invariants by number.

  **The bridge is an `@` import and deliberately NOT a symlink**, which is what the usual advice
  suggests. Committed as a symlink, git stores mode 120000, and a checkout with `core.symlinks=false`
  — Windows without developer mode — writes a 9-byte TEXT file whose whole content is the target's
  name. An agent reading that gets one word and no instructions, **worse than an absent file because
  it looks present**. Measured rather than assumed: a sibling repo is committed exactly that way and
  its `AGENTS.md` blob is 9 bytes reading `CLAUDE.md`.

  And not the other way round either — only Claude Code expands `@`, so an `AGENTS.md` pointing at a
  `CLAUDE.md` would hand every other agent that same one line.

  **What this does NOT buy is a smaller instruction budget.** An `@` import loads at session start
  like the file itself, so the ~53,000 tokens are still on every request. Progressive disclosure is a
  separate change, and `/docs/` is gitignored here, so it cannot be the home for split-out rulebooks
  without changing that first.

- **AGENTS.md's own rule — "the incident that produced it lives in `CHANGELOG.md`" — had stopped
  being applied to two invariants.** The following entries recover what was moved: which draft was
  wrong, what the raw numbers were, which reading was corrected by which later one. The invariants
  keep the rule and the reasoning a later reader needs in order not to simplify it away; the
  arithmetic that established it lives here.

  **The scan that prompted this over-counted, and the honest figure is much smaller.** Grepping the
  invariants for evidence markers (`measured`, `an earlier draft`, `was corrected`, Poisson figures)
  flagged ~14,000 tokens, about a quarter of the section. Read paragraph by paragraph, nearly all of
  it turned out to be load-bearing justification rather than history — the numbers in invariant 74
  ARE the argument that no threshold can decide, and moving them would weaken the file. Only #66 and
  #39 had genuinely outgrown the rule. Actual reduction: **56,100 -> 53,300 tokens** (~5% of the
  section), and a check for material duplicated verbatim between the two files found 211 tokens in
  total. **A keyword scan of prose is a way to find candidates, not a way to count them.**

- **Invariant 39's script drift — the measurement, corrected three times, moved out of AGENTS.md.**
  Each correction was published as settled before the next one killed it, which is the part worth
  keeping.

  1. **A ~90-character hand table reported ZERO Simplified characters.** Its own author documents it
     as a script identifier, not a converter.
  2. **A full `zhconv` mapping reported five**, of which the published list was wrong on four. A
     `zhconv` diff counts characters that are correct Traditional in their own right (`干` in
     干預/干擾, `台` in 一台, `群`, `里` in 里程碑), and it counts Japanese entirely — 386 Han-only
     diff positions in `nb-d22c2a9a`'s sources alone, which are Japanese and whose shinjitai map to
     Traditional. Excluding both classes, two real notebooks carry `尔 兹 峡 么 对 点 问 题` — eight
     characters, 19 sites, ALL in podcast fields, with titles, overviews, answers and follow-ups
     clean. `没 帮 们` appear zero times.
  3. **A third exclusion, and correcting it produced a second wrong answer — only the CHARACTER-level
     split is true.** `霍尔木兹海峡` (12 of the 19) was first excluded whole as "a Simplified place
     name copied from a Simplified source"; the correction said no source spells it in any script and
     counted all 12 as drift. Measured per character: `nb-d22c2a9a`'s sources hold **5,456 Han
     characters of Japanese**, containing `海峡` **67 times** and `ホルムズ海峡` 24, and `霍`, `尔`,
     `兹` **zero** times; `nb-6f2d49d3`'s hold no CJK at all. So `霍尔木兹` is the model's own
     rendering and IS drift, while `峡` is a character its sources spell that way sixty-seven times.
     The live A/B says so without being asked: the two characters ABSENT from the corpus converted
     (`尔`->`爾`, `兹`->`茲`) and the one present 67 times did not. **Both earlier readings argued
     about the whole NAME, and the name is not the unit.**

  **The A/B for the prompt rule alone (arms 1 and 2 of the three-arm experiment recorded above) was
  NOT significant.** Same four sources, same `qwen36_35b_a3b`/`gpt-5.6-luna` pair, same Traditional
  Chinese, same `long` tier, 258s, only the prompt differing, through the CLI path, which persists
  nothing (invariant 42) so the stored episode the baseline came from was never overwritten.
  Wrong-script characters went `13 / 5699` to `7 / 4013`, one per 438 to one per 573; the null
  expectation for the shorter episode is 9.2 and seven were observed, Poisson `P(X<=7) = 0.31`. **One
  run cannot establish that a rule works.** What it DID establish is that the rule REACHES the model:
  the place name went from `霍尔木兹海峡` (three of six characters wrong, three occurrences) to
  `霍爾木茲海峡` (one of six, six occurrences). The new episode also ran 27% shorter per utterance,
  71.2 to 52.1 characters — one sample, not attributed.

  **"The model cannot write that character" was the obvious excuse and it is FALSE**, settled for
  about 600 tokens against the same configured LM: asked directly it returns `霍爾木茲海峽`, all six
  characters correct, and `峽` alone on request.

  **A first reading of that run called the half-converted name a REGRESSION caused by the rule**, on
  the premise reading 3 records as false — that the sources spelled the name and the model had
  stopped copying them. Under the corrected premise the same measurement reads the other way: two of
  three wrong characters were FIXED. The prompt sentence added to forbid a partial conversion was
  reverted with it, having been written against a collision that never occurred.

  **The incident recorded as motivating the proper-noun precedence did not happen.** The clause was
  added because a Traditional podcast carried `霍尔木兹海峡` and that was read as the model keeping a
  Simplified source's own spelling — choosing the name over the script, correctly, without being
  told. The corpus check kills it: those sources say `the Strait of Hormuz` in English and contain no
  Chinese at all, so nothing was being kept and there was no collision. The precedence is still worth
  stating, but on the general argument, **not on an observation here** — and the one time it looked
  observed, the evidence was a story nobody checked against the blob.

  **Why a validator was declined for a long time, and what moved.** Every condition justifying one —
  short, navigational, repeated, demonstrably drifting — was read as absent, and the one field that
  would qualify (the title) does not drift; this project's failure is the inverse of the sibling's,
  whose failure was in page TITLES. Two of those conditions then moved: the drift is real and three
  times larger than published, and the correct output is demonstrably knowable by the model.

- **Invariant 73's calibration figures and its two corrected paragraphs, moved out of AGENTS.md.**

  **`_MAX_SPANNING_FRACTION` transfers from rendered PDFs to real scans.** A real two-column scan
  (Physical Review Letters, 1958) measured 0.01-0.05 per page — the same band as the clean digital
  renders the threshold was set on — and every one of its 16 pages was reordered. Controlled skew of
  0.25-2.0 degrees held it at 0.00-0.08, so the drift a scanner introduces does not reach 0.15. The
  three-column case that declines itself is Scientific American Supplement, 1890.

  **Sorting a band by vertical position measured worse on both layouts**: two-column 0.756 -> 0.743,
  single-column 0.774 -> 0.751.

  **`_MIN_GUTTER_SHARE` was asserted backwards in three places at once.** An earlier draft claimed
  raising it would stop a two-column page being reordered; it does not — output is byte-identical at
  0.02, 0.05 and 0.30, because a count of 1 falls through to the split exactly as 2 does. What
  raising it actually breaks is the DECLINE for four-column pages.

  **The whole-page column count's supporting number is about plausible bands, not observed ones**, and
  the hedge went missing twice. Measured over contiguous windows of the fixture's own geometry,
  7.8-11.1% of 3-to-8-region slices count more than two, peaking at seven-region windows. The commit
  message carried the hedge; the docstring and AGENTS.md dropped it. A first correction then reported
  the sweep's ENDPOINTS (7.8 and 10.2) as its range.

- **Invariant 66's script check — the measurements, moved out of AGENTS.md.**

  **Live A/B, three episodes off one notebook, same models, same tier, same language:**

  | arm | chars | characters the check would flag |
  |---|---|---|
  | rule inert | 5699 | 13 |
  | rule shipping, no check | 4013 | 7 |
  | rule + check | 4617 | **0** |

  Against the middle run — whose ONLY difference is the check — the null expectation is 8.1 and zero
  were observed, Poisson `P(X=0) = 0.0003`; against the first, 10.5 expected, `P = 0.00003`. **Six of
  the seven middle-arm flags are `峡`**, and the check's own rejection message tells the model it may
  keep exactly that: a character verbatim from a source, or Japanese being quoted, and `海峡` is in
  those sources 67 times. Broken out, the middle arm is `峡`×6 plus `么`×1, so on the remainder alone
  the expectation is 1.15 and `P(X=0) = 0.32`. **The one significant number in this area rests on a
  character the rule does not clearly require changing.** And the CLI writes no trace, so whether the
  validator FIRED is unobservable — the draft may simply have been clean. One episode per arm.

  Survivors: `厘清` (should be `釐清`) — `厘` is valid Big5 for `公厘` and not one of the eight
  measured additions. `制` in `問責制` is `zhconv` being wrong rather than the gate: `制度` is correct
  Traditional, and flagging it would have been the false positive the gate prevents.

  **Replayed against real measured output before it shipped**: 17 offenders on the episode that
  motivated it, 7 on the one after, 2 on the notebook whose only drift is `么` — every one a genuine
  drift, zero false positives across 119 utterances produced against a corpus containing Japanese.

  **`_SCRIPT_REPORT_LIMIT` at ONE was measured too few in both directions.** A live run rejected nine
  characters WITH their fixes (`权`->`權`, `时`->`時`, `识`->`識`), the model submitted anyway, and all
  nine shipped — the single look bought nothing. The other direction is worse: a compliant model that
  fixed and re-validated was told `success` on its second call whether or not it had fixed anything.

- **Invariant 66's Big5 let-through — how the enumeration was arrived at, and the wrong answer it
  replaced.** An earlier note called the 131 let-through characters "almost exactly the genuinely
  ambiguous set" after reading the first forty. The tail is `优 听 党 网 极 确 触 异 价 种 复 划 挂 洁`,
  plus four curly quotation marks (`zh-hant` maps them to corner brackets — not characters at all).
  So before the enumeration, `基于`, `机器`, `后端`, `优化` and `价值` produced NO flag at all and
  `网络`, `标准`, `确认`, `范围`, `复杂` flagged one character of two — this project's own subject
  matter. All 131 were then read once: 52 SHARED, 79 flagged despite the codec.

  **Two independent readings, agreeing on 72 and disagreeing on 16, and each caught real errors in the
  other**: `伙食` and `凶宅` would have been corrupted by this project's reading; `昵稱`, `腌菜`,
  `昆虫`, `蚝油` and `蝎子` were missed by it. The residual disagreement is exactly the five the
  sibling's own reviewer predicted would move.

  Scale, for the gate's shape: over `zhconv`'s own 3909 single-character rewrites, Big5-encodability
  flags 3857 and lets through 52.

- **Invariant 66's suggestion path — the two errors it was built around.** A character-level table
  names the WRONG character whenever the word is the less common one (`历` is `歷` in `历史` but `曆`
  in `日历`; `发` is `發` in `发现` but `髮` in `头发`; `汇` is `匯` in `汇率` but `彙` in `词汇`).
  That shipped, and was found by a sibling project hitting it in its converter.

  The `zh-hant` → `zh-tw` post-map is taken from the SOURCE character rather than from `zh-hant`'s
  answer because the two disagree on NINE characters — `账`->`帳` plus the Taiwan element names
  `鈽 鍅 鉲 鎝 鉳 鑀 鋂 錼` — and via-source is right on all nine, since `zh-tw` maps `账` straight to
  `帳` and has no `賬`->`帳` entry. 22 of the flagged characters take the regional post-map.

- **The whole validate chain passed end to end for the first time, and it needed BOTH of the last
  two fixes.** One run, `long`, same notebook:

  ```
  validate  ok=False   shape error (a list where an object was expected)
  validate  ok=False   5 character(s) across 5 fields in the wrong script
  validate  ok=True    Validation successful.
  final turn:  script = {'utterances': script_utterances}; SUBMIT(script)
  ```

  **At the old `_SCRIPT_REPORT_LIMIT` of one, the second rejection would have returned success and
  five characters would have shipped.** Without the later-turn ordering rule the model would not
  have read either verdict — the run before this one printed a verdict beside its SUBMIT and
  shipped the character it had just been told about. Neither fix alone would have produced this.

  Result: 62 utterances (off the 60 floor for the first time), **zero** drift, and exactly one
  close, at the last utterance. Prompt-compliance claims still carry invariant 4's hedge — one run
  is evidence, not proof.

- **"Only submit after it reports success" was read as an ordering within ONE CELL.** A run wrote:

  ```python
  print(validate_podcastscript(json_str))
  SUBMIT(final_output)
  ```

  which validates nothing — the verdict is printed where the model cannot act on it, because the
  submit beside it has already run. That run was told exactly which character was in the wrong
  script (`utterances[23].text: 么 -> 麼`) and shipped it.

  **`_SCRIPT_REPORT_LIMIT` cannot rescue this**, which is worth stating because raising it from one
  to three was yesterday's fix for a neighbouring symptom: the limit governs how many times the
  validator will REJECT, and this model asked ONCE. An earlier run that DID recover branched on the
  result (`if 'success' in validation_result.lower(): SUBMIT(...)`), so the difference is entirely
  whether the model acts on the answer.

  `validate_before_submit_rule` now says the SUBMIT belongs on a LATER REPL turn, names the
  anti-pattern with the task's own tool name substituted in, and offers a guarded single cell as
  the alternative. Shared by all six tasks (invariant 13).

- **The count-against-target rule works, visibly, and hugs the floor.** The run after it compared
  its count to the target on EVERY turn — "I have 5 turns so far. Target is 60-90", "I have 30
  turns so far and need to reach 60-90", "I have accumulated exactly 60 turns" — where before it
  printed a count and compared it to nothing. It stopped at exactly 60, the band's floor, so the
  rule reads as a minimum to clear rather than a range to land in. Inside target, and recorded
  rather than tuned: one run is not a reason to move a number that eight runs put at the floor
  already.

- **A `long` episode came back at 43 turns against a 60-90 target, and the reason is a rule the
  accumulate-across-turns pattern needed and did not have.** That run hit an `IndexError` at step
  9, escalated to the sub-LM for 1m45s, spent two turns re-parsing the corpus, and submitted at 43
  — without ever comparing 43 against 60.

  **Building across turns keeps the count in a VARIABLE and not in front of the model.** A 70-turn
  run and the 43-turn run both printed their count in the step before validating, and neither
  compared it to anything; six of seven landing inside the band was luck, not a check. The prompt
  now says to count against the target before validating and, when short, to go back to the SOURCES
  rather than forward to the close — deliberately a different sentence from the filler rule beside
  it, which is about a corpus with nothing left in it.

  **Invariant 63's calibration note went from one sample to eight**, and the target turns out to be
  met at its FLOOR:

  | corpus | utterances |
  |---|---|
  | 18,466 chars | 70, 70, 65, 65, 61, 60, **43** |
  | 131,057 chars | 80 |

  So length tracks the CORPUS at least as much as the tier, and six of seven small-corpus runs sat
  in the bottom sixth of a 60-90 band. The recorded figure had been a single 80 on the large corpus.

- **The live ticker carried the whole validator verdict, which is written for the MODEL.** A
  rejection names the offenders, then explains what to do about them and which exception applies —
  so the status line read `2 character(s) … 么 -> 麼` followed by "Rewrite each in Traditional and
  validate again. A character that is verbatim from a source …" and then an ellipsis. Reported from
  a live run, one turn after the branch started emitting anything at all.

  It sends the FIRST SENTENCE now, which for a rejection is exactly the offender list. Cutting at
  `". "` is safe on these strings specifically: the list carries `.` inside `utterances[5].text`
  and `citations[0].answer_span`, neither followed by a space. The full text is unchanged in the
  trace and in the drawer's detail pane.

- **The live ticker said "Tool" and threw the payload away.** `_translate_trace_event`'s
  `tool_call` branch emitted a fixed word with the tool name demoted to `detail`, and its `meta`
  read a `status` key `record_tool_call` never writes — so it was always `None`. That is the exact
  shape invariant 52 records this function being rewritten to stop doing; it survived because this
  project emitted no `tool_call` events at all until the validator started recording, so nobody
  read the branch.

  Reported from a live run: the status line read "4 tools, 18 steps" while the validator was
  rejecting a draft, and nothing on screen said so. Now the tool names itself in `primary`, the
  verdict or the named argument is `detail`, and a rejection sets `meta`.

  **The kind stays `tool` even for a rejection.** `failed` is TERMINAL — `app.js`'s
  `TERMINAL_KINDS` closes the live log on it — so one rejected tool call would have ended the
  ticker while the run carried on. Pinned; the mutation that makes it `failed` fails two tests.

- **The three-look bound paid off on its first run.** The validator rejected two characters, the
  model fixed them, and the second call returned a real `Validation successful.` — which at the old
  limit of one it would have returned regardless. The stored episode has **zero** drift, the first
  end-to-end clean result this check has produced.

- **The script check's one-rejection bound was measured too few, in both directions, and is now
  three.** A live run rejected NINE characters with their fixes — `权`->`權` five times, `时`->`時`,
  `间`->`間`, `识`->`識`, `恶`->`惡` — the model submitted anyway, and all nine shipped in the
  stored episode. The single look bought nothing on the one run where the check finally fired.

  **The other direction is the worse half and was not noticed when the bound was chosen**: a
  COMPLIANT model that fixes its prose and re-validates was told `success` on its second call
  whether or not it had fixed anything, because the bound had already been spent. The design was
  lying to the model that deserved a real answer.

  Three gives fix, verify, and one more fix. The worst case is three planner turns against
  `max_iterations=25`, so the original reason for a bound — a check the model cannot satisfy must
  never spend the whole budget — still holds.

  The same run is the first time every piece of this session's work ran together and could be seen
  doing it: `read_skill` called FOUR times (zero across the previous eight runs), real token usage
  reported (so the cache bypass took effect), five tool calls recorded, turn marks numbered from
  one, the strip filled, and the jump-to-turn button on a failed segment.

- **A regression this batch introduced: the Simplified direction lost its gate entirely.**
  Refactoring `_wrong_script_chars` from a small forced set to an exempt set dropped the `continue`
  after `src.encode(codec)`, making the codec DEAD CODE — every path fell through to the
  assignment. For Traditional that is the documented intent, since `_BIG5_SHARED["hant"]` replaced
  the codec. For Simplified `_BIG5_SHARED["hans"]` is EMPTY, so nothing gated it at all:

  | | before | after the regression | now |
  |---|---|---|---|
  | hant | 3,782 | 3,857 | 3,857 |
  | **hans** | **652** | **4,704** | **652** |

  Measured consequence: a Simplified run over this project's own Japanese-bearing corpus flagged
  `鎖 響 際 係 門 軍 優 換 東 報 書 動 運 業` plus curly quotes — so its single once-per-run report
  would have been spent on quoted Japanese and could never reach real drift. Retained Simplified
  forms went too: `瞭` in 一目瞭然, `徵` in 宫商角徵羽, `麼` in 幺麼小丑, all of which zhconv's own
  zh-hans table emits as correct Simplified.

  **No test saw it**, because the one covering that direction listed `简体字概览模块对点问题` —
  characters that are already Simplified and therefore never SOURCES in the table, so it passed
  against a build with no gate. It now uses characters that are sources, and a second test pins the
  two counts, which is the cheapest witness that both branches still run.

- **Acting on an independent review of the batch. Four more of its findings:**

  - **"Never source text" was false.** The coordinate branch interpolates the offending `locator`
    VERBATIM, and its own documented failure mode is a model writing the SECTION HEADING it was
    citing into that field. The test that claimed to cover it was vacuous — its secret string
    appeared only in the payload that VALIDATES, whose verdict is one fixed sentence. Corrected
    rather than tightened: the model needs its real coordinate back to fix the citation, and a
    trace already holds full source text in front of an API with no auth (invariants 25 and 29).
    A new test records that it DOES reach the trace, so the claim and the behaviour cannot drift
    apart again.
  - **Six mutations survived the Big5 tests**, all of them MOVING a character between the two
    halves — which the union pin cannot see, since it only catches one in neither. The membership
    is pinned as the exact set now.
  - **The chat cache bypass was unpinned.** `fresh=body.regenerate or body.fresh` is the entire
    chat arm and mutating it away left the suite green. Pinned, along with `/title`'s exemption.
  - **Stale numbers, each re-derived before correcting**: `.env.example` still documented and
    offered `RN_MAX_TOKENS=16384`, so an operator uncommenting it would silently halve the cap;
    invariant 66 carried the pre-enumeration arithmetic and listed `规 监 随` as let-through when
    none of the three is Big5-encodable; invariant 70 said the replay's steps were "0.09s apart"
    when 0.09s is the total SPAN (spacings are 0.010-0.023s); a code comment said the two `zh-tw`
    keyings disagree on four characters when it is nine, which `AGENTS.md` had already been
    corrected on; and a test comment said 0.04/96% where the arithmetic gives 0.055/6%.

  **Invariants 59 and 75 now argue opposite ways about the same cap**, and that is recorded rather
  than resolved: 75's proximity reading was transposed to 16384, and 59 has since raised it to
  32768 — the very cap the maintainer's own corpus found no gradient in. This project's own data at
  32768 is two capped calls in 54, at ratios 1.0 and 0.275, with the band between intact.

- **The replay transport now shows its progress through the stop it is dwelling on.** It waits for
  the time a turn really took divided by the speed, and with no bar that is indistinguishable from
  a frozen panel — the same "watched it and read it as a crash" complaint the run ticker's
  long-wait tier exists to answer, in a panel that has no other sign of life. Reported against
  a sibling project, which has one.

  It names the stop as well as drawing the bar (a bar alone says how long is left, not what for),
  and the transition is restarted per stop — cleared, snapped to zero, forced reflow, run — because
  without the reflow the browser coalesces both writes into one style recalculation and the bar
  jumps to 100% with no animation at all.

  **Invariant 36's tripwire caught the change, and the catch was a false positive it documents.**
  The new local was called `row`, and that route matches `<var>.hidden =` across the WHOLE file
  while three other functions build `const row = document.createElement(...)` — so it failed the
  build naming `notebook-row`, `starter-questions` and `tstep`. The test's own comment says the fix
  for that collision is to rename the local rather than loosen the tripwire, so the local is `bar`.
  Failing loudly in the safe direction is what it is for.

- **The trajectory drawer's two notes share one row.** Stacked, they were two full-width rows of
  one short sentence each, pushing the timeline strip down for no information (reported).

  They remain two ELEMENTS. Merging the text would have cost the thing the note colours exist for:
  the budget note turns red on a truncation and the timing note never does, and telling those apart
  without reading the sentence is invariant 75's whole point.

  The row carries both guards its own `display: flex` creates — a `[hidden]` pairing (invariant
  36's rule, pre-emptive the way `.btn`'s is) and a `:has()` rule that removes it when both notes
  are hidden, since otherwise its margins hold 11px of blank exactly where the space was reclaimed.

  **One of the three mutations survived the first version of the test and that is the finding.**
  Moving the budget note back OUT of the container left it inside the 400-character slice the
  assertion was reading, so "both notes are inside the row" passed against markup where one was
  not. It reads INDENTATION now — the container's children, by depth — and the mutation fails.

- **Two defects a user found in the trajectory strip, both reported from screenshots.**

  **The strip numbered turns from zero while every other surface counted from one.** The nav rail
  said "Turn 3", the detail head said "Turn 3", and the mark above them said `T2` for the same
  call. Display-only fix (`T${entry.turn_index + 1}`); the trace data stays 0-indexed. Pinned as
  the EXPRESSION rather than the token, because `entry.turn_index` reads the same either way and
  the whole defect was a missing `+ 1`.

  **The strip left most of its width empty.** `flex-grow` distributes free space in proportion to
  the grow values and STOPS AT THEIR SUM — a run whose calls were 0ms/0ms/25ms/1ms floored to 0.01
  each summed to **0.06**, so CSS filled 6% of the free space and left 94% blank:

  ```
  before: grow [0.010, 0.010, 0.025, 0.010]  sum 0.06  ->  6% filled
  after : grow [0.182, 0.182, 0.455, 0.182]  sum 1.00  -> 100% filled
  ```

  Normalising by the total makes the sum exactly 1 and leaves every ratio between segments
  untouched, which is the half that had to survive. The existing test asserted the grow factor was
  "the duration" and now asserts it is the duration NORMALISED, with the arithmetic in the comment.

  Three mutations killed: numbering from zero again, dropping the normalisation, and making every
  segment equal.

- **A turn's FIRST tool call no longer shows a gap-derived duration.** The gap reaches back to the
  previous timeline event, which for a turn's first call is on the far side of the model generating
  that whole code cell — so the number displayed was mostly model time wearing a tool's name.
  A sibling project measured **287 of 972 calls first-in-turn**, a third of every duration its drawer
  showed. A call that measured ITSELF is unaffected (`duration_measured`); this only discards a
  fallback that was never the tool's.

  An existing test pinned the old value (`[3.0, 2.0]`), and its own comment said `duration_s` is
  "the gap since the PREVIOUS live event" — it was pinning the implementation, not defending it.
  Now `[None, 2.0]` with the reason attached.

- **A tool segment offers a way back to the turn that called it.** On every ATTRIBUTED segment
  rather than only a failed one, and absent where nothing is attributed. The detail head already
  named the turn, and naming one a reader then has to find in the nav by eye is exactly the
  two-lists-to-correlate problem the strip's turn marks remove.

  From a four-screenshot comparison with a sibling project's drawer. Of the five gaps it showed, three
  turned out to be already present here (turn marks, the flex-grow floor, the basis floor) and one
  is better here (`2ms` rather than a `<10ms` display floor). The two real ones were this and the
  first-in-turn rule.

  **Not adopted: a run-wide picker and a `成功` header badge.** The picker needs a server-wide run
  index this project does not have — a trace is reachable only from the artifact that produced it
  (invariant 29's persisted run ids). The badge would come from `run_end.ok`, which says a SUBMIT
  parsed and nothing about whether the artifact is any good: citations are verified host-side and
  afterwards, so a run whose every citation was refused still reads `ok`. That is a status line
  claiming something the page is not doing (invariant 60). The sibling reached the same conclusion
  about its own and is renaming it to say what it measures.

- **Regenerate now actually regenerates (`RunOptions.fresh`).** `dspy.LM` defaults to
  `cache=True`, so pressing Regenerate on an unchanged notebook returned a run with 0 model calls
  in 3.4 seconds that replayed the previous one byte-identically — same seven turns, same
  first-turn reasoning, the same two validator failures. A button labelled Regenerate that returns
  what you already had is a UI that lies, and the drawer's honest "no usage, no per-turn timing"
  then reads as a broken panel.

  **A FIRST generate keeps the cache**, where a hit is a free correct answer, so the flag is the
  EXISTENCE of the artifact — `Boolean(state.overview)`, `Boolean(state.podcast)`, and
  `AskRequest.regenerate` for chat — never a constant. A test rejects a hardcoded `fresh: true` or
  `fresh: false` at either call site.

  It rides ALONGSIDE `kwargs` down to the worker, never inside them: `kwargs` are the task's
  `arun()` arguments and anything added there reaches the model as a signature field. The worker
  switches it globally with `dspy.configure_cache(enable_disk_cache=False,
  enable_memory_cache=False)` BEFORE `setup` — correct because a worker handles exactly one run, so
  process-global is run-scoped, and because rebuilding the LMs would mean a second construction of
  `runtime.configure`'s `lm_kwargs` that drifts from upstream's.

  Four mutations killed: never bypassing, smuggling `fresh` into the task kwargs, and hardcoding
  either constant on the client.

- **A tool that measures itself is no longer charged the strip's gap.** `_tool_entry` sized every
  timeline segment by the distance from the previous timeline event — right for a call that reports
  nothing, wrong for one that does, because it charges the tool with everything since, including
  the planner turn that decided to call it. The first run after the validator started recording drew
  a **3.3-second** segment for a call it had measured at **1.9ms**. The gap stays as the fallback,
  and a non-numeric report does not become a duration.

- **Recorded, not fixed: `dspy.LM` defaults to `cache=True`, so Regenerate can cost nothing and
  return the identical episode.** A user pressed Regenerate on an unchanged notebook and got a run
  with **0 LLM calls in 3.4 seconds** against the previous **7 calls in 263.6 seconds** — same
  seven turns, byte-identical first-turn reasoning, the same two validator failures replayed.

  The drawer's two notes on that run are both TRUE and both easy to misread as a broken panel: no
  per-turn timing (the steps are 0.09s apart because nothing was generated) and a cap with no usage
  (there were no calls). Invariant 70 now says so, since the alternative is rediscovering it from a
  screenshot every time.

  Whether Regenerate SHOULD bypass the cache is a product question and is not answered here.
  Invariant 42 gives the button three states and none of them is "this returned what you already
  had".

- **The Trajectory drawer said "this run called no tools" on every run, and it was wrong every
  time.** `rlm_harness.record_tool_call` is OPT-IN — a tool wrapper calls it or the event does not
  exist — and `make_grounded_validator`'s `validate` never did. So this project wrote no
  `tool_call` events at all, the drawer's tool timeline was structurally empty, and its empty state
  contradicted the turn's own code pane three lines away, which read
  `validate_podcastscript(json.dumps(script_list))`.

  Found by a user reading a real trace: "明明就有 `validate_podcastscript` 但仍沒有工具呼叫".
  Upstream's `read_skill` records; ours simply never did, so the drawer could not tell "no tool was
  called" from "tools do not report".

  **It also closes a limitation this project had written down rather than fixed**: the live A/B of
  the script check could not say whether the validator had FIRED, and that caveat is attached to
  every number in that measurement. It is observable now.

  The JSON is the whole artifact, so its LENGTH is recorded and its TEXT is not (invariant 52's
  rule for the ticker, applied to the drawer); a test asserts the artifact string is absent from
  the trace file. `ok` splits a rejection from a pass, and `duration_s` is measured with a
  monotonic clock around the call. The empty state now says WHICH empty it is — the model never
  called the validator its own instructions ask for, which is a real signal rather than a bug.

  Three mutations killed: removing the recording, recording the artifact text instead of its size,
  and reporting `ok` unconditionally.

- **The 32768 raise behaved exactly as the sibling's distribution predicted, on the first run after
  it.** A `GeneratePodcastScript` call hit the new cap — but it was call 1 of 7, which produced 318
  characters of reasoning and 128 of code before dying with `Invalid Python syntax`. That is a
  turn-0 runaway, the class that data says no cap saves; the run recovered on its next turn and
  finished 65 utterances. **Not evidence for raising again.**

  The close rule held on the same run: one close, at the end.

- **`max_tokens` 16384 -> 32768, sized against a distribution rather than against the truncation
  that prompted it.** A live `GeneratePodcastScript` call hit 16384 exactly on call 5 of 10 and
  came back `[Error] Invalid Python syntax` — cut mid-code — costing an iteration.

  It is invariant 59's case and not invariant 64's, which is what makes a raise the right answer
  rather than a restructure: the model was ALREADY batching 5-20 utterances per step, and the
  truncated call left 407 characters of reasoning and 995 of code in the trace. The tokens went
  into chain-of-thought that dspy discards.

  **One truncation is not a size.** A sibling project supplied the distribution this project cannot
  produce for itself — 3,683 calls on the same `qwen36_35b_a3b` under a 32768 cap:

  | | |
  |---|---|
  | median / p90 / p99 | 1,621 / 6,993 / 15,030 |
  | at cap | 26 calls, 0.71% |
  | 40-50% of cap (13-16k) | 26 calls — exactly what the old cap was cutting |
  | 50-60% | 1 call |
  | **60-90%** | **ZERO** |

  That empty band is the finding: legitimate long turns end below ~16k and everything reaching the
  cap is a runaway no cap would save (three of their six fatal parses were the model writing
  `{The user wants to write…` until it ran out). The doubling buys the tail; a second one buys
  nothing. **Do not raise it again without a distribution.**

  Their measured cost: a run with a cap hit is ~2.5x tokens and ~2.5x wall clock, which at 0.71% is
  noise. What does NOT transfer: their cap hits are single turns, while `max_iterations` here is 25
  and the budgets multiply — `run_timeout_seconds` is the only bound on a looping runaway.

  Also checked, because the sibling suggested it before concluding the model declines the skill:
  `read_skill` IS wired and IS advertised — a real instance carries
  `[validate_podcastscript, read_skill]` and the prompt holds a closed `<available_skills>` catalog
  naming it. So the zero calls are a genuine decline, consistent with that project's 15% overall
  and 2-of-16 on its craft skill.

- **A real episode ended, then restarted: the close rule and the accumulate-across-turns rule had
  never been checked together.** Invariant 45 asks for an opening, a body and a CLOSE; invariant 64
  asks for a long script to be built across REPL turns. Neither said WHERE the close goes.

  Measured on a 70-utterance run (`nb-443d7daa`): step 7 appended twenty utterances including a
  close, reaching 50; step 8 then read a source section it had not covered (`ACT THREE CONTENT`);
  step 9 appended twenty more, ending in a second close. On screen that is `6:49 感謝大家收聽` ->
  `6:57 我們回到 AI 挑戰賽的最後一關`.

  The prompt now says the close is written once and last, names the batching as the mechanism, and
  says what to do if more material turns up afterwards. Prompt-only, same hedge as invariants 4
  and 11.

  **Two observations from the same traces, neither acted on yet:**

  - **The Trajectory drawer shows NO tool calls for any of these tasks, and that is correct.** The
    only tools are the validator and `read_skill`; the validator is called from inside REPL Python
    (`print(validate_podcastscript(...))` in the submitting step) so it produces no `sub_call`
    event and no timeline segment. It DID run, in all six traced runs. Worth knowing before reading
    an empty timeline as a compliance failure.
  - **`read_skill` was called ZERO times across all eight runs of that notebook.** Invariant 65
    defaults skills ON "because a planner that has to be told to consult its own knowledge base
    will not" — measured, it does not consult it either way. The catalog is still paid for on every
    planner turn.

- **The Big5 let-through is enumerated now — all 131 read character by character, 52 SHARED and 79
  flagged.** It closed the recall hole this project's own subject matter fell into: before it
  `基于`, `机器`, `后端`, `优化` and `价值` produced NO flag at all, and `网络`, `标准`, `确认`,
  `范围` and `复杂` flagged one character of two.

  **SHARED means a live Traditional use the PHRASE TABLE does not protect.** Where it does —
  `皇后`, `茶几`, `划船`, `拮据`, `佣金`, `老么`, `尸位素餐`, `夸父`, `并州`, `云云`, `于右任`,
  `洪适` — the character is flagged and `_actionable` drops the self-suggestion, so the exemption
  is spent only where it is needed.

  **Where this diverges from a sibling project and why**: a PROPER NOUN keeps a character SHARED even
  where the Simplified drift is commoner (`范` 范仲淹, `余`, `涌` 東涌, `涂`, `朴`, `杰`, `岳`,
  `郁`). Invariant 69 forbids translating a name, and an obedient model told `范 -> 範` writes
  `範仲淹`. That project ranks them the other way because its corpora are technical rather than literary. Both answers
  are defensible; the reason is recorded rather than averaged.

  **Two independent readings, and each caught real errors in the other.** 72 agreed, 16 disagreed.
  Mine would have corrupted `伙食` and `凶宅`; mine missed `昵稱`, `腌菜`, `昆虫`, `蚝油` and
  `蝎子`, all of which convert to the standard Taiwan forms. What survived is five characters —
  `余 范 涌 吁 咨` — which is EXACTLY the set the sibling's own reviewer predicted would move under
  a different reading. Neither list is adopted from the other; the diff is the artifact.

  Pinned by `test_the_big5_letthrough_is_fully_classified`: the two halves must cover the codec's
  let-through exactly, so a zhconv upgrade fails the build instead of landing an unread character
  in the unflagged half. Verified: zero false positives across 43 correct Traditional words, and
  the three measured episodes are unchanged at 13 / 7 / 0.

- **Retracted: "a looser gate is affordable here because this check only reports".** It was used to
  justify diverging from a sibling project's direction-when-unsure, and it is wrong. A reporting
  check whose advice is wrong is advice a model may FOLLOW — told `干 -> 幹`, an obedient model
  writes `幹預` and the corruption lands in the artifact anyway, by a longer route than the
  sibling's persisted title but landing all the same. The once-per-run bound limits how OFTEN that
  can happen, not whether. The direction when unsure is to prefer the miss, on both sides, and the
  two projects' tolerances are not legitimately different in this respect.

- **`_actionable` does not substitute for a shared/simplified classification, measured.** It drops
  an offender whose phrase-aware suggestion equals the character it already has, which looked like
  it might make the Big5 recall hole closable without hand-classifying anything. Over 27 ordinary
  Traditional words it rescues **four** — `皇后`, `几案`, `拮据`, `恒生`, the ones zhconv's phrase
  table happens to know — and leaves 23:

  ```
  干預→幹  台灣→臺  一群→羣  里程碑→裏  余先生→餘  丑時→醜  高峰→峯  准許→準
  占卜→佔  北斗→鬥  托盤→託  栗子→慄  上游→遊  痴心→癡  秘密→祕  岳父→嶽
  神采→採  征服→徵  朴素→樸  涂鴉→塗  伙伴→夥  咸豐→鹹  公厘→釐
  ```

  So whatever closes the hole has to carry those 23 itself, and the sibling's 52-character SHARED
  list is doing real work rather than belt-and-braces. Still not adopted: the borderline entries
  (`秘` 秘密/祕密, `峰` 高峰/高峯, `采` 神采/採用, `准` 准許/準許, `游` 上游/遊戲, `征` 征服/徵收)
  are not "shared versus simplified" at all — they are two Traditional characters a Simplified
  merge collapsed, where the right answer depends on the WORD and no per-character set can express
  it in either direction. That is the open question with the sibling.

- **An independent review of the previous ten commits found two defects the model could not have
  worked around, and re-derived every headline number. Two were wrong; one of them was a
  "correction" this batch had already made once.**

  **`峡` is in the corpus 67 times, so the corpus correction was itself over-broad.** `nb-d22c2a9a`'s
  sources hold 5,456 Han characters of JAPANESE, containing `海峡` 67 times and `ホルムズ海峡` 24,
  while `霍`, `尔` and `兹` appear ZERO times. The first reading excluded the whole name as copied;
  the second counted the whole name as drift; **only the per-character split is true**, and the
  live A/B had already said so — the two characters absent from the corpus converted, the one
  present 67 times did not.

  That reaches the one significant number this line of work produced. Six of the middle arm's seven
  flags are `峡`, which the check's own rejection message tells the model it may keep. On the
  remainder alone the expectation is 1.15 and `P(X=0) = 0.32`. `AGENTS.md` now carries the
  breakout beside the `0.0003`.

  **The check rejected correct Traditional with an instruction it could not follow.**
  `_suggest` returns the phrase-aware conversion at the position, and where zhconv's phrase table
  leaves a character alone — because it is already right in that word — the "fix" was the character
  itself: `拮据` was rejected with `据 -> 据`, `恒生` with `恒 -> 恒`. **Sixteen** gate characters
  have such a context (`么 农 冲 别 叶 广 恒 据 汤 温 灯 联 胆 荐 适 鹰`), so the one documented
  `拮据` was not the extent of it, and the once-per-run bound capped the cost without making the
  message coherent — the exact failure invariant 66 forbids. `_actionable` drops any offender whose
  fix equals the character it already has: the phrase-aware pass agreeing with the input IS the
  evidence the character is right.

  **`--trace` reported a model failure as a bad path.** `TimeoutError`, `BrokenPipeError` and
  `ConnectionResetError` are all `OSError` subclasses, so a `try:` around the whole traced block
  caught a dying sandbox and told the operator to fix a path that was fine — while the trace sat on
  disk, complete, with `run_end ok=false` in it. Only `__enter__` is wrapped now; the run's own
  exception propagates and the trace is still written.

  **Counts corrected**, each re-derived rather than taken from the review: the gate flags 3782 of
  3909 and lets through 127 (was 3774/135, stale by exactly the eight `_MEASURED_OTHER_SCRIPT`
  added); source- and destination-keyed `zh-tw` disagree on NINE characters, not four, and
  via-source is right on all nine (`账`->`帳` plus eight Taiwan element names); the OCR sparse-band
  sweep is 7.8-11.1% peaking at seven-region windows, not "7.8-10.2%" — that first correction
  reported the sweep's ENDPOINTS as its range; "40,521 characters" was unreproducible and is now
  stated with its scope (39,770 with verbatim quotes, 27,047 without); `么` was documented in three
  places as deliberately unflagged after `420c979` started flagging it; the rejection said
  "N field(s)" while counting `(path, character, fix)` triples.

  **`script_family` was silently inert for two ordinary spellings.** `Chinese (Traditional)`,
  `Chinese (Simplified)` and `簡體中文` all returned `None`, turning the whole check off — and
  `RN_OUTPUT_LANGUAGE` and the settings file accept any string, since `clean_language` bounds
  length rather than the character set.

- **The Big5 gate's recall loss is larger than recorded, and the hole is now stated rather than
  characterised away.** A sibling project enumerated all 135 let-through characters and reported that
  the "almost exactly the genuinely ambiguous set" claim — made here after reading the first forty —
  holds for about eight of them. Verified: `基于`, `机器`, `后端`, `优化` and `价值` produce NO
  flag, and `网络`, `标准`, `确认`, `范围` and `复杂` flag one of their two characters. That is this
  project's own subject matter.

  **It did not invalidate the existing measurements**: across the three measured episodes the only
  characters falling in the miss surface were `干`x3 (correct Traditional), `么`x1 (since bought
  back) and `厘`x1 (the recorded accepted miss). None of the software vocabulary appeared.

  The sibling closed its own hole by reading all 135 once into a shared/simplified split with a
  test pinning the union so a zhconv upgrade cannot add an unread character silently. Not adopted
  here yet — it is 135 characters of human classification and belongs to a decision, not to a
  cleanup pass.

- **The check's SUGGESTION was a character lookup and a character lookup cannot answer it.** `历`
  is `歷` in `历史` and `曆` in `日历`; `发` is `發` in `发现` and `髮` in `头发`; `汇` is `匯` in
  `汇率` and `彙` in `词汇`. The table carried whichever form is commoner, so the validator named
  the wrong character whenever the word was the less common one — shipped that way, and reported
  by a sibling project after hitting it in its own converter. Confirmed against this project's table
  before adopting anything.

  The whole string is converted now (`zh-hant` is phrase-aware and script-only) and each offender
  takes the character at its own index, falling back to the table if the conversion changes length.

  **The two suggestion rules compose in ONE direction.** The regional `zh-tw` preference applies
  only where the phrase-aware pass made no choice of its own — where it agrees with the plain
  single-character answer. Applying it unconditionally would lose `日历`'s `曆` back to `歷`, which
  is the same defect reintroduced from the other side; `因为` still gets `為` over `zh-hant`'s
  `爲`, and `账户` still gets `帳`.

  Detection is unchanged — the same 13 / 7 / 0 flags across the three measured episodes — because
  this only ever affected what the rejection ADVISES. Two mutations killed: reverting to the
  character lookup, and letting context override the regional preference.

- **The CLI can write a trace now (`--trace PATH`), and the reason it never could is recorded
  rather than left as an accident.** Everything about `traces/` belonged to the server: it is a
  bare relative directory resolved against the process's working directory, and `prune_traces`
  runs from `api.py`'s lifespan and after every API run. A CLI has neither, so tracing by default
  would scatter a `traces/` directory into whatever directory the command was invoked from and
  leave files nobody collects — holding the one artifact here that can contain FULL ingested
  source text.

  **Opt-in with an explicit path answers both halves**: the caller names the file, so nothing is
  scattered and retention is theirs; off by default, so nothing accumulates silently. The flag sits
  on the SHARED `_add_source_and_notebook_args`, so `ask`, `guide` and `audio` all get it and none
  can be forgotten — invariant 46's "a rule with one silent exception gets rediscovered as a bug
  report". The recorder is entered before the model call, so an unwritable path costs nothing
  (invariant 19).

  **A missing directory is CREATED, not refused.** `TraceRecorder.__enter__` calls
  `os.makedirs(..., exist_ok=True)`, so `--trace new/dir/run.jsonl` works; only a genuinely
  unwritable path (a parent that is a regular file) fails. The first version of the test asserted
  the opposite and was wrong about the library it was testing.

  **The gap was measurable, not hypothetical.** The live measurement of the pre-SUBMIT script
  check could not say whether the validator had FIRED, and that caveat is attached to every number
  in it — because the cheap path for such a measurement is the CLI and the CLI produced no
  evidence at all.

  `worker.py`'s meta builder moved to `traces.run_meta`, shared by both entry points rather than
  copied (invariant 20); two of `test_api.py`'s assertions moved with it, and the one that sliced
  `worker.main`'s SOURCE for a `meta = {` literal now checks the BUILT dict — a source slice would
  have kept passing against whichever copy it happened to point at.

- **Two fixes from a sibling project, both measured before adopting, and one of them was a live defect
  on this side.** That project confirmed its own prompt script rule was inert in all four
  production prompts exactly as read here, and that its stability came from host-side title
  conversion rather than the prompt.

  **The suggestion was not the Taiwan standard.** `zhconv`'s `zh-hant` target answers "a
  Traditional form", not "the form Taiwan writes": `为` -> `爲` where Taiwan writes `為`, and the
  same for `众`/`眾`, `启`/`啟`, `账`/`帳`, `伪`/`偽` — **22 of the 3774 characters this check
  flags**, several of them common. The validator was telling a model to write characters no
  Taiwanese reader uses. Each suggestion is now post-mapped through `zh-tw`, **from the SOURCE
  character rather than from `zh-hant`'s answer** (`账` reaches `賬`, which `zh-tw` leaves alone,
  while `账` maps straight to `帳`; the two agree on 29 of the 33 characters where anything
  differs and via-source is right on all four of the rest), and **single-character only**, because
  `zh-tw` carries a vocabulary layer that rewrites `鼠标` to `滑鼠` and would misalign a positional
  zip.

  **Eight characters are now flagged despite the Big5 gate** (`_MEASURED_OTHER_SCRIPT`). `体 适 荐
  离 据` are five of the sibling's 29 real Simplified sites across 89,160 Han
  characters of deployed output — `适` being the exact title, `執行環境與作業系統适配`, that started its conversion
  work and that the bare gate would have left unfixed. `构 与 么` are this project's own gaps.

  This is where the two projects' tolerances legitimately differ and the difference is recorded
  rather than split: `据` in `拮据` is correct Traditional, so the list CAN produce a false
  positive. That costs the sibling a silently corrupted TITLE (its converter persists); it costs
  this check ONE rejection the model may override. A looser gate is affordable here and is not
  there. Measured on this side: all eight occur ZERO times in 40,521 characters of real Traditional
  output, apart from `么`'s three genuine drifts.

  The widened gate also re-scores the live measurement — the middle run had 7 flaggable characters
  rather than 6, so `P(X=0)` for the checked run moves to 0.0003.

  **What the sibling reproduced of this project's finding**, for the record: its bare
  zhconv-table detector flagged 34 characters over 99 sites, of which **70 were the false-positive
  class** — `群`(35), `游`(10), `表`(7), `干`(6), `峰`(4), `占`(2) in `群組`, `上游`, `表格`,
  `干預`, `高峰`, `占用`. It has adopted the Big5 gate and deleted its `_KEEP_AS_WRITTEN`.

- **The script check measured live: zero flaggable characters, `P(X=0) = 0.001` against the run it
  is the only difference from.** A third episode off `nb-d22c2a9a`, same models, same `long` tier,
  same Traditional Chinese, 346s.

  | | utterances | chars | characters the check would flag |
  |---|---|---|---|
  | rule inert (`scripttest2`) | 80 | 5699 | 13 |
  | rule shipping, no check | 77 | 4013 | 6 |
  | **rule + check** | 66 | 4617 | **0** |

  Against the middle run — whose only difference is the check itself — the null expectation is 6.9
  and zero were observed: Poisson `P(X=0) = 0.001`. Against the inert baseline, 10.5 expected,
  `P = 0.00003`. That is the first significant number this line of work has produced; the two
  earlier drift comparisons were `P = 0.23` and `P = 0.31` and were recorded as not significant.

  **What it does NOT establish, stated because the whole area has a history of over-reading:**

  - The CLI writes no trace, so whether the validator FIRED is unobservable. The draft may have
    been clean on the first attempt. This measures the configuration, not the tool being exercised.
  - One episode per arm. The Poisson test treats the rate as a property of the configuration.
  - Two changes are conflated against the baseline (rule + check); only the middle comparison
    isolates the check.

  **The accepted 3% recall loss appeared, once**: `厘清` survived and should be `釐清`, because
  `厘` is valid Big5 (`公厘`) and therefore outside the gate by design. The only other `zhconv`
  hit, `制` in `問責制`, is `zhconv` being wrong rather than the gate being loose — `制度` is
  correct Traditional, and flagging it would have been exactly the false positive the gate exists
  to prevent.

- **Confirmed with a sibling project how it keeps its output Traditional, by reading and RUNNING its
  code rather than taking an answer.** Its stability comes from solving this in a different place:
  HOST-SIDE and POST-HOC, split BY FIELD — a majority comparison on page bodies (advisory,
  tolerant), per-character strictness on page TITLES only, and a converter that rewrites a title
  and persists it. A prompt rule that turns out to be inert therefore costs that project nothing,
  where this project had only the prompt. Its field split is better reasoning than a global
  strictness dial and is recorded in invariant 66.

  **Its membership test does not transfer, and its own shipped functions demonstrate why.** Run
  against correct Traditional prose, `strict_script_offenders` reports `干` in `干預`, `里` in
  `里程碑` and `群` in `一群`, and `to_script` would persist `幹預`, `裏程碑` and `一羣` into a
  title; `台` is safe only because `_KEEP_AS_WRITTEN` hand-lists it, while the docstring claims no
  such list is needed. Reported to that project with the reproduction and the Big5 alternative —
  their user's call, not ours.

- **A pre-SUBMIT script check now catches Simplified characters in Traditional output, and it is
  the only check here that is allowed to be wrong.** Invariant 39 had declined a validator; two of
  its conditions moved — the drift is real and three times larger than published (19 sites), and
  the correct output is demonstrably knowable BY THE MODEL, which is what separates a
  reject-and-look-again check from a converter.

  **The membership test is Big5-encodability, and that is the finding that made it possible.**
  `zhconv`'s own `SIMPONLY` set was tried first and is unusable: it contains `干`, `台`, `群` and
  `里`, which are ordinary Traditional characters this project's real notebooks use correctly. Big5
  answers "does this glyph exist in the Traditional inventory at all" — `干` is in it, `对` is not.
  `zhconv` is still the dependency, for the SUGGESTION (`对 -> 對`) and to bound the set to known
  Simplified forms.

  **Three properties, each a deliberate loss:**

  | property | choice | cost |
  |---|---|---|
  | precision | absolute — no correct Traditional character may be flagged | `么` passes, because it is valid Big5 |
  | blocking | fires AT MOST ONCE per run | a determined model can submit drifted prose |
  | scope | `quote` exempt | a Simplified character inside a quotation is never caught |

  **The one-shot bound is the design, not an optimisation.** Every other check in
  `make_grounded_validator` rejects something WRONG; a Simplified character is COSMETIC, and the
  detector cannot distinguish one from a Japanese glyph being quoted inline — `学`, `会`, `国` and
  `峡` are shinjitai and this project's own corpora carry Japanese. A blocking check the model
  cannot satisfy spends the step budget looping and loses a paid-for episode over one glyph, which
  is the trade invariant 66 already refuses for `tts.spoken_script`.

  **Replayed against real measured output**: 17 offenders on the episode that motivated this, 6 on
  the one after it, every one a genuine drift; 0 on the notebook whose only drift was `么`. Zero
  false positives across 119 utterances produced against a corpus containing Japanese.

  Six mutations run against the new tests, all killed: removing the check, dropping the `quote`
  exemption, removing the one-shot bound, using the raw `zhconv` table without the Big5 gate,
  dropping the `arun` capture, and unwiring it from `GroundedTask`. `validate_before_submit_rule`
  now says four things rather than three, because a prompt describing three checks while four run
  is the drift invariant 13 exists to prevent.

- **"The model cannot write `峽`" was falsified for about 600 tokens.** The live episode left one
  character of `霍爾木茲海峡` unconverted, and the obvious reading was a vocabulary limit no prompt
  could reach. Asked directly, the same configured LM returns `霍爾木茲海峽` — all six characters
  — and `峽` alone on request.

  So the residual Simplified drift is a COMPLIANCE problem rather than a knowledge one: the model
  holds the right answer and does not apply it across 4000 characters of dialogue. `AGENTS.md`'s
  sentence excusing it as a capability limit is removed.

  **This reopens the validator question with one of its conditions now met.** Invariant 39 declined
  a validator because "every condition justifying one is absent, and the one field that would
  qualify does not drift". Two of those have moved: the drift is real and larger than published
  (19 sites, all in podcast fields), and the correct output is demonstrably knowable BY THE MODEL,
  which is what makes a reject-and-retry check different from a converter. A `zhconv` CONVERTER
  remains wrong for the reason already recorded — it rewrites `干`, `台`, `群`, `里`, which are
  correct Traditional — so any such check would have to report offenders and let the model judge
  context, not rewrite prose. Not built; recorded as a live option rather than a closed one.

  Method note for the next person: the first attempt at this check hand-rolled a `dspy.LM(...)`
  from `RN_MAIN_MODEL` and died on a missing provider prefix, because `config.setup` is the ONE
  place either entry point configures a model (invariant 35). Use it.

- **The Hormuz proper-noun story was false, and it had been used to justify two changes and to
  discount twelve drift hits.** `霍尔木兹海峡` in a Traditional podcast was recorded as the model
  faithfully keeping a Simplified source's own spelling. **Neither notebook's corpus contains a
  single Chinese character.** `nb-d22c2a9a`'s sources say `the Strait of Hormuz` in English, 22
  times, with Japanese prose around it; `nb-6f2d49d3`'s hold no CJK at all. The model rendered the
  name into Chinese from its own priors, and Simplified is what those priors produce.

  Three things fall out, in the order they were wrong:

  | claim | as recorded | corrected |
  |---|---|---|
  | drift across both notebooks | `么 对 点 问 题`, 5 chars, 5 sites | `尔 兹 峡 么 对 点 问 题`, **8 chars, 19 sites** |
  | the live A/B | 4 / 5699 -> 1 / 4013, `P<=1`=0.23 | **13 / 5699 -> 7 / 4013**, `P(X<=7)`=0.31 |
  | the half-converted name | a REGRESSION the rule caused | an **improvement**: 3 of 6 wrong characters -> 1 of 6 |

  **The exclusion was never checked against the corpus, only against a plausible story** — that a
  name appearing in a foreign script must have been copied from somewhere. It was applied while
  correcting a different bad exclusion in the same measurement, which is what made it feel
  rigorous. Still not significant either way: one run, `P = 0.31`.

  **`51d2dac` is reverted in full.** It added a sentence forbidding a PARTIAL proper-noun
  conversion, with `霍尔木兹海峡` as "a name the sources spell" — a factually false statement about
  this project's own data, shipping in all six prompts. The failure it described is not a
  carve-out failure at all: the model rendered the name itself and left one character unconverted,
  which is ordinary drift, and the script rule already says `throughout`. The clause may still be
  right in general and there is no evidence for it, so it does not ship.

  **The proper-noun precedence clause stays**, but on the sibling's measured Simplified-source
  case and the general argument, NOT on an observation here — `AGENTS.md` now says so.

- **The script rule was measured live, and the run bought a REGRESSION rather than a
  confirmation.** A/B on one notebook (`nb-d22c2a9a`): same four sources, same
  `qwen36_35b_a3b`/`gpt-5.6-luna` pair, same Traditional Chinese, same `long` tier, 258s — only
  the prompt differed. Run through the CLI `audio` path, which persists nothing (invariant 42), so
  the stored episode the baseline came from was never overwritten and the comparison is against
  the real recorded artifact rather than a re-derivation.

  | | baseline (`scripttest2`, rule inert) | new (`SCRIPT_PINNED` shipping) |
  |---|---|---|
  | utterances / chars | 80 / 5699 | 77 / 4013 |
  | Simplified drift sites | 4 (1 per 1424 chars) | 1 (1 per 4013) |
  | the place name, ×n | `霍尔木兹海峡` ×3 | **`霍爾木茲海峡` ×6** |

  **The drift half is NOT significant and must not be reported as a win.** The null expectation
  for a 4013-character episode at the baseline rate is 2.82 hits; one was observed, Poisson
  `P(X<=1) = 0.23`. The previous run's "no measurable effect at this sample size" was wrong for a
  different reason — the prompt had not changed at all — and replacing one wrong conclusion with
  an over-read of the next one would be the same mistake wearing better numbers.

  **What the run DID establish is that the rule reaches the model, and it established it through a
  new defect.** With the rule inert the model copied `霍尔木兹海峡` verbatim from its Simplified
  source. With the rule shipping it produced `霍爾木茲海峡` — `尔`→`爾` and `兹`→`茲` converted,
  `峡`→`峽` not — six times, consistently. That string is neither the Simplified the sources use
  nor the correct Traditional `霍爾木茲海峽`, so a reader can search for it in NEITHER script,
  which is exactly the harm the proper-noun carve-out exists to prevent. Behaviour changed on
  precisely the collision the rule addresses, which is direct evidence rather than inference —
  and the change was for the worse on that name.

  **The failure mode had not been considered**: "keep the name" and "convert the name" were taken
  to be the only outcomes, and a PARTIAL conversion is worse than either. Caveats kept: one name,
  one run, one model, and `峡`/`峽` may simply be a character this model does not write.

  Also measured, one sample, not attributed: the new episode ran 27% shorter per utterance (71.2
  to 52.1 characters) at a near-identical turn count.

  **Method note.** The drift scan classifies only the four characters verified in context
  (`干 台 群 里`) as already-Traditional and prints everything else for a human to judge — a
  blanket exclusion list would forgive the context-dependent pairs (`面/麵`, `系/係`, `松/鬆`)
  and fail in the direction of UNDER-counting, which is the same error as the ~90-character hand
  table, run backwards.

- **The script rule never reached a prompt: it shipped inert, and three documents described it as
  working.** `instructions._script_rule` matched on the language NAME, but invariant 39 carries the
  language as a SIGNATURE FIELD — so all three call sites (`task.py:37`, `guide.py:37`,
  `audio.py:110`) compose their rule at import time with the literal placeholder
  `"the language named by the `output_language` variable"`, which matches nothing. It returned `""`
  for all six tasks, in production, from the day it shipped. Measured on the shipped classes: every
  one scored `script-rule-text=False`. Found by an independent review of the batch that added it.

  **Replaced by `instructions.SCRIPT_PINNED`, worded conditionally and shipped unconditionally** —
  the same shape the sentence beside it (`Write your prose in {language}`) had always had. All six
  now carry exactly one copy. The proper-noun carve-out moved with it and is stated ONCE covering
  both directions; the superseded table carved it out of the Traditional rule only and left the
  Simplified rule with the mirror-image exposure.

  **The test could not have caught it, and that is the transferable part.**
  `tests/test_instructions.py` called `artifact_language_rule("Traditional Chinese")` — a call shape
  that occurs nowhere in the product. A mutation making `_script_rule` `return ""` was duly KILLED
  by it while the feature was entirely dead. That is a test passing for a reason unrelated to its
  name at FEATURE level rather than assertion level, which is a level the project had not written
  down. Every assertion in that file now goes through a shipped task class.

  **Consequence for the live run this batch spent**: it cost 459s and could not have tested what it
  was spent on — the "after" prompt differed from the "before" only by `NATURAL_REGISTER`, which is
  an unconditional constant and did ship correctly. Whether the script rule prevents Simplified
  drift remains UNMEASURED.

- **The Simplified-character measurement was wrong on four of its five characters.** `AGENTS.md`
  recorded "five genuine ones — `么 没 干 帮 们`". Re-run over the same two notebooks (675 string
  fields), excluding the three classes the batch had itself identified:

  | excluded | hits | why |
  |---|---|---|
  | Japanese context | 391 | one notebook holds Japanese sources; shinjitai maps to Traditional |
  | punctuation | 78 | zhconv rewrites `“ ” ’` |
  | correct Traditional already | 14 | `干` (干預/干擾), `台` (一台), `群`, `里` (里程碑) |
  | proper nouns | 12 | `霍尔木兹海峡`, copied verbatim from a Simplified source |

  What survives is **`么 对 点 问 题` — five characters, five sites, all in podcast utterances**.
  `没 帮 们` appear ZERO times in either notebook. The "all in podcast utterances, titles and
  answers clean" half of the claim stands and is now verified against field paths rather than
  asserted. No validator is still the right call, for the reason already recorded.

- **Three fixes from the previous batch had no regression test, and the sparse-band measurement was
  overstated in two places.** All from the same review.

  - `tests/test_web_assets.py` now pins the budget note's cap-without-usage branch (by ORDER, so a
    run with both fields cannot take the weaker one), the `dropped` notice's preservation of
    `is-cut` (by the DIRECTION of the conditional), and — as a general rule rather than a token
    name — that **no `var()` fallback in the stylesheet hardcodes a colour**. That last one is
    stated as a property of the fallback because `var(--danger, #d9534f)` is how a typo'd token
    ships looking healthy: the fallback renders, so nothing is visibly broken, and the value
    silently ignores all three theme blocks. `--danger` is assigned nowhere in the tree; `--bad` is
    defined in all three.
  - `tests/test_instructions.py` pins `AnswerQuestion`'s answer-first and "say what the sources did
    NOT settle" rules, which had no enforcement anywhere — mutations deleting each survived the
    full suite.
  - **The real-detector fixture cannot demonstrate the per-band defect and never could**: it
    carries ONE spanning region, so that page is a single band of 104 and both schemes agree on it
    exactly. `_ocr.py`'s docstring and `AGENTS.md` both reported it as a three-region band the
    fixture holds. The 6-15% figure is sound and was reproduced (7.8% / 8.8% / 9.9% / 10.2% for
    contiguous windows of 3/4/5/8 regions) — it is a claim about PLAUSIBLE bands, and the hedge the
    commit message carried was dropped in both prose copies.

- **Two test guards measured something other than what they said.**
  `tests/test_parsers_pdf.py`'s single-column guard asserted `len(raw) > 20` under the message "the
  fixture must produce several regions" — `raw` is a normalised WORD list, and that page has FOUR
  regions, so the guard read literally was false while passing. It now asserts the GEOMETRY that
  actually decides (the page must be declined BY the spanning guard, not by the two-region
  short-circuit above it), computed with plain arithmetic so the fixture stays validated
  independently of the code under test. And `test_web_assets.py`'s regenerate test imported
  `rlm_notebook.api`, so without the `api` extra it FAILED rather than being absent — sharper than
  the trap the Verify section records, and it misreported a missing dependency as a broken feature.
  It reads `api.py` as text now, like every other assertion in that file.

- **OCR reading order: a two-column scan no longer comes back with its columns interleaved
  (invariant 73).** `parsers/_ocr.py` joined RapidOCR's regions with
  `" ".join(text for _, text, _ in result)`, throwing away the bounding quad reported alongside
  every one of them. RapidOCR emits regions roughly line-by-line ACROSS the full page, so a
  two-column page produced prose that jumps between columns mid-sentence — the model then read
  scrambled text, and a citation's `quote` could be a scrambled span that still passed coordinate
  verification (invariant 5 checks where, never what).

  **Measured against the same pages' own text layer** (`difflib.SequenceMatcher` over normalised
  word sequences), two real papers, every page over 120 words:

  | | before | after |
  |---|---|---|
  | ResNet, two-column, 12 pages | 0.425 | **0.756** |
  | "Attention Is All You Need", single-column, 15 pages | 0.802 | 0.792 |

  **The text-layer path was never affected, which is why this was not found earlier.**
  `pypdfium2` reads a two-column LaTeX paper in correct column order already — the content stream
  is written a column at a time — so only scanned/textless pages (invariant 7's OCR dispatch) were
  ever wrong. That was verified on the same PDF before any code changed, not assumed.

  **Two drafts were wrong before this one, and both failures are the reason the rules are shaped
  the way they are.** The first treated any band containing a centre-crossing region as untrustworthy
  and fell back to plain order: on a real page the ONLY crossing region was the page number centred
  in the footer, and that one tiny box cost the whole page its column order — the initial fix
  measured no better than no fix at all. It "worked" in the prototype only because an earlier version
  had used the image midpoint rather than the content midpoint, which happened to land on the other
  side of that page number. The second draft sorted each band by vertical position, which measured
  WORSE on BOTH layouts (two-column 0.756 -> 0.743, single-column 0.774 -> 0.751) — RapidOCR already
  emits a column's lines in reading order, so the re-sort only disturbed near-ties. Isolating the
  re-sort from the column split, as four separate variants over one cached OCR run, is what showed
  this; guard parameters were swept first and moved nothing, which is what prompted looking
  elsewhere.

  **Accepted cost, inspected rather than inferred**: a wide table on a single-column page can be
  split down the middle (the Transformer paper's Table 3 does), and two attention-visualisation
  pages measured -0.08/-0.06. Both were read directly before being accepted — a flattened table and
  a scatter of figure labels are word soup under either ordering. `_MAX_SPANNING_FRACTION = 0.15`
  is set from a two-document sample and deliberately errs low, since too low only declines to
  improve a page while too high reorders one that was already correct.

- **`rlm-harness` 1.0.0 -> 1.10.0, and `worker.py` stopped reaching into a private module.** Ten
  minor versions with no code change beyond one import: the only edit the upgrade itself forced was
  swapping `from rlm_harness._retry import _short_error` for the public `from rlm_harness import
  short_error`, verified to be the SAME object with the same signature before the swap. Note the
  fix went one step further than proposed — dropping the underscore off the NAME still left the
  import reaching through `_retry`, a `_`-prefixed MODULE; `short_error` is in the kit's `__all__`,
  so the top-level path is the one with a compatibility promise behind it.

  `dspy` moves 3.2.1 -> 3.3.1 with it (the kit's floor since 1.5.0), which renamed `max_iterations`
  to `max_iters` upstream. The kit absorbs that internally: `RLMConfig` still accepts
  `max_iterations` and invariant 59's budgets (25 / 16384 / 40000 / 1) still arrive intact —
  checked, not assumed. Resolution touches three packages in total.

  **The upgrade makes something measurable that was structurally unmeasurable here.** This project
  passes a plain `dspy.LM` and never wrapped it in `intercept_sub_lm`, and before kit 1.7.0 only
  that wrapper emitted `sub_call`. So every `sub_call` count in any trace this project has written
  is a property of its own WIRING, not of the model — while three features read those events:
  the ticker's event translation, the citation-turn lookup (invariant 29, which searches a
  `sub_call`'s whole payload precisely because its keys differ from a `main_step`'s) and the
  Trajectory timeline (invariant 70). The kit records it at the task seam now. Stated as a
  structural claim from the code path, NOT as a measurement: `traces/` is empty here, so nothing
  was counted to confirm it.

  **Any later comparison across this boundary must split on `run_start.rlm_harness`** and treat an
  absent field as UNMEASURED rather than zero. Traces written before kit 1.6.0 carry no such field
  and none of `sub_call`, `tool_call.duration_s`, `run_end.error_chain` or `run_end.budgets`/`usage`
  — so averaging a rate across the upgrade reads a component added afterwards as 100% and everything
  older as 0%, which is corpus composition rather than a property of this code.

- **Took two rules from the sibling's `prose-craft` skill, and left most of it, because the rest is
  answering a problem this project does not have.** Measured first on the two real notebooks here,
  20 model-authored fields:

  | `prose-craft` rule | violations measured here |
  |---|---|
  | space between Chinese and Latin | 1 (one podcast utterance) |
  | full-width Chinese punctuation | 0 |
  | avoid stacking three or more `的` | 8, of which 6 are podcast |

  So the two typography rules are answering a failure this project's model is not making, and adding
  them would be writing a rule against something never observed. The `的` stacking is real and it
  CONCENTRATES in the podcast, which fits: it is the only artifact meant to be heard, where a
  listener has no punctuation to lean on. That one went into `podcast-craft` with its measurement,
  not into a prompt — skipping it makes an episode duller to listen to, not wrong (invariant 65).

  **What did go in the PROMPT is an honesty rule**, and it is the half of `prose-craft`'s
  answer section that is not taste. `AnswerQuestion` already said to admit when the sources cannot
  answer a question AT ALL; the commoner case is a question mostly answered with one part left open,
  where an answer that reads confident throughout while quietly skipping the unsupported half is
  worse than a short one that names the gap — the reader cannot see it, and every citation on the
  rest still verifies (invariant 5). Answer-first and stop-when-done went in beside it: a closing
  summary paragraph is a second, worse copy of `follow_ups` (invariant 56).

  **Not taken, and why**: the nine AI-taste patterns (summary sentence, false contrast, bold as
  pseudo-heading) are taste judgements — nothing here can measure whether this project has them or
  whether a rule improved them, and a prompt rule whose effect cannot be observed is one more thing
  to maintain on faith. The em-dash prohibition is the sibling's house style. The `read_file` /
  `grep_repo` grounding advice has no analogue in a corpus this project hands over whole.

- **CI had been red on every push since the rlm-harness upgrade, and nobody looked.** Ten
  consecutive failures. Local `pytest` was green throughout, which is exactly why it went unnoticed:
  the suite passes on 3.13 and fails on 3.11 and 3.12, and only the full run fails — the OCR test
  file alone passes.

  **Root cause, isolated to one line of a dependency.** dspy 3.3.1 installs a lazy-import proxy for
  numpy (`dspy/utils/lazy_import.py`). Against numpy 1.x that proxy re-executes numpy's `__init__`
  while it is already partially imported, the moment another extension module touches the module
  object — so `import dspy; import cv2` dies with `ImportError: cannot import name 'array' from
  partially initialized module 'numpy.core'`, and cv2 reports only "OpenCV bindings requires numpy",
  which names the wrong thing. That takes the whole OCR path with it, since rapidocr imports cv2.

  **Why 3.11 and 3.12 had numpy 1.x at all**: `chatterbox-tts` pins `numpy<2.0.0` below 3.13 and
  permits numpy 2 at and above it, and uv's lock is UNIVERSAL — so the optional extra set the numpy
  version for every install of this project on those interpreters, chatterbox requested or not. CI
  syncs `--extra api` and never touches chatterbox, and still got numpy 1.26.4.

  **So this was never only a CI problem.** Any 3.11 or 3.12 user ingesting a scanned PDF would have
  hit it, because the API process imports dspy and ingestion reaches cv2 through rapidocr.

  The fix states the constraint where it lives: `numpy>=2` is a core dependency now, with the reason
  attached, and every entry in the `chatterbox` extra carries `python_full_version >= '3.13'`. Below
  that the extra resolves to nothing and `ChatterboxProvider`'s existing import guard reports a
  `TTSError` — a loud failure in the feature the user asked for, rather than a silent one in the
  ingestion they did not. Verified on all three interpreters: 621 passed on 3.11, 3.12 and 3.13,
  where 3.11 and 3.12 had been 17 failed / 604 passed.

  **The process lesson is the one worth keeping**: "I ran the suite" meant one interpreter. The
  matrix existed precisely because that is not the same claim, and ten pushes went out on it.

- **Spent a live podcast run to test the script rule. It has no measurable effect at this sample
  size, and the run bought three other things instead.** 459 seconds, one `long` episode on the same
  notebook, same tier as the baseline it replaced.

  | | before the rule | after |
  |---|---|---|
  | Han characters | 3,069 | 4,643 |
  | Simplified in the model's OWN prose | 3 | 4 |
  | rate | 9.78 / 10k | 8.62 / 10k |

  **Three against four is not evidence of anything.** One run, one notebook: the honest reading is
  "no measurable effect", not "it works" and not "it doesn't".

  **The first reading of this run was wrong, and by a lot** — 13.03 against 34.46 per 10k, a
  doubling, reported before the offenders were read. Two errors, both in the MEASUREMENT:

  - **`干` is not a Simplified character here.** The hits were `不干預` and `干擾`, both correct
    Traditional; zhconv rewrites them to `幹`, which is wrong. Three of the sixteen were the tool
    misreading, counted as the model's failure.
  - **Nine of the sixteen were one proper noun, three times.** `霍尔木兹海峡` came verbatim from a
    Simplified source, which is `PROPER_NOUNS` working rather than the script rule failing.

  **That second one is a rule conflict this project created and had not written down.**
  `PROPER_NOUNS` says never translate a name; the script rule says write Traditional throughout; a
  Simplified-spelled name in the sources puts them in direct opposition. The model picked the name,
  which is correct — converting it costs the reader the exact string they would search for
  (invariant 69) — but nothing had told it which wins. The precedence is now stated inside the
  script rule itself, so a reader of that paragraph meets the exception there rather than having to
  hold a later paragraph in mind.

  **The measurement tooling needs both exclusions to be worth anything**, and that is the durable
  part: a zhconv diff counts characters that are correct Traditional in their own right, and it
  counts proper nouns the rules deliberately preserve. Either alone turns a null result into an
  alarming one.

- **Re-measured the Simplified-character claim with a full conversion table, and the earlier zero
  was an artifact of the tool.** The check that produced it used a sibling's ~90-character hand
  table — deliberately small, and documented by its author as a script IDENTIFIER rather than a
  converter. Re-run through `zhconv`'s full mapping over the same fields:

  | | hand table (~90 chars) | zhconv full mapping |
  |---|---|---|
  | nb-6f2d49d3, 50 fields | 0 | 6 |
  | nb-d22c2a9a, 78 fields | 0 | 5 |

  **Most of that difference is not Simplified text.** `zh-hant` rewrites several characters that are
  correct Traditional in their own right — `台`→`臺`, `群`→`羣` — and `zh-tw` adds Taiwan locale
  vocabulary on top (`里`→`裡`). Excluding that class leaves **five genuine Simplified characters**:
  `么 没 干 帮 们`.

  **Where they are is what decides the design, and it inverts the sibling's case.** All five sit in
  PODCAST UTTERANCES. Titles, overviews, answers and follow-ups are clean — zero across both
  notebooks. The sibling's strict per-character check exists for a page TITLE: short, in the
  navigation, on every page, where one drifted character is a visible fraction of the field. Our
  equivalent short nav field (`naming.SuggestTitle`) is exactly the one with no offenders, and the
  field that has them is the one meant to be HEARD — `没` and `沒` are the same sound, and the
  transcript shows one character in a 32-character line.

  **So: still no validator, but now for a reason that survives its own measurement.** Every
  condition that justifies one (short field, visually prominent, repeated, demonstrably drifting) is
  absent here, and the one field that would qualify does not drift.

  **Untested, and stated rather than implied**: all five characters predate the script rule added in
  the entry above. Whether that rule prevents them is unmeasured — it needs a live podcast run, which
  costs money, and no run has been spent on it.

- **A language name buys neither its script nor its idiom; both now have a rule (invariant 39).**
  Two findings, one observed here and one borrowed from a sibling project after reading how
  it had solved the same class of problem.

  **Observed: `源文`.** A Traditional Chinese answer's follow-up questions wrote `源文` for "the
  source text", where a reader expects `原文`. That is a word-for-word rendering of the English, and
  no script rule can reach it — 源 and 原 are both perfectly ordinary Traditional characters, so it
  is a REGISTER failure rather than a script one. `NATURAL_REGISTER` asks for the term a reader of
  that language would use rather than a compound assembled from the English words for it, and it
  composes into a single-script language's rule too, because the failure is about wording.

  **Borrowed: the script rule.** The sibling pins the script in the script itself (`概览` must be
  `概覽`) after a real run returned a document set whose body text was Traditional while every TITLE
  came back Simplified, so the nav and the page disagreed on screen. This project had NO script rule
  at all — just "write your prose in {language}", the exact under-specification that failure came
  from.

  **The "not reproduced here" that first accompanied this was itself a bad measurement, and the
  correction is the entry below.** It reported zero Simplified-only characters across every
  model-authored field — measured with the sibling's ~90-character hand table, whose own comment
  says it answers "which script is this text in", not "convert this text". A reader that cannot
  report a non-zero value reports absence either way.

  **What was deliberately NOT taken.** The sibling also carries a two-threshold VALIDATOR: a
  majority comparison for a page body (a repository may legitimately contain Simplified strings) and
  a strict per-character check for a short field like a title, justified by a measured case
  (`插件與鉤子系统`, where the majority check correctly reported clean because that is not the
  question a title asks). It is a good design and this project has the matching short field in
  `naming.SuggestTitle` — but adding a validator for a failure never observed here would be building
  machinery ahead of evidence. The prompt rule is cheap and the seam is recorded.

- **Rejected: concurrent source ingestion. It crashes, and the crash is documented in a direct
  dependency's own metadata (invariant 3).** A peer session implemented it in this working tree
  unprompted — `ingest_new` planning serially and fetching through a `ThreadPoolExecutor` — with a
  measured 7.55s to 2.85s on five HTML sources. The objection raised here was that the PDF path,
  the one claimed to scale the saving, had not been measured. Measured: four PDFs serial 0.41s
  `rc=0`; concurrent `rc=134`, SIGABRT (a first attempt gave `rc=139`, SIGSEGV). Cause, verified
  locally at `pypdfium2-5.12.1.dist-info/METADATA:1066`: *"PDFium is inherently not thread-safe."*

  **The upside was near zero exactly where the risk was.** Four ordinary PDFs parse in 0.41s;
  `api.py`'s "can take minutes" describes OCR on SCANNED pages, one branch of PDF ingestion, and it
  had been read as characterising the whole. The 2.94% saving was measured on HTML, where it is real
  and small.

  **The green suite proved nothing**, and that generalises past this patch: `tests/test_ingest.py`'s
  multi-value cases all take local text files through `parse_text`, so nothing in 614 passing tests
  drove two PDFs at once. A suite that is green on the path you did not change is not evidence about
  the path you did.

  Also recorded, from the same exchange: `traces/` is empty here because `cli.py` never reaches
  `runner.start_run` — the only caller is `api.py:1193` — so the CLI cannot produce a trace at all,
  and any future trace-reading measurement has to go through the API path. That sharpens an earlier
  entry which said only that this checkout had no corpus.

  A sound version is not ten lines: the waiting is the network fetch and the crashing is the PDF
  parse, and `ingest_one` fuses them, so separating them is a refactor of the ingestion dispatch.

- **A fourth review round over the eight unreviewed commits: one shipped regression, one false
  claim in three places, one more hollow test, three UI defects.** All verified locally before being
  acted on.

  **The regression is the serious one, and it was mine.** `_column_count` was called per BAND, and a
  column count is a property of the PAGE. A sparse band — a few short fragments between two spanning
  elements — reads its own intra-column whitespace as a gutter: on this project's own real-detector
  fixture a three-region band counted 3 columns and was DECLINED, returning the interleaved
  detection order the module exists to remove. Estimated at 6-15% of that page's plausible bands.
  The count now runs once over the page's non-spanning regions, beside the existing page-level
  guard, so a band cannot be seen at all.

  **The test written for it was hollow, which makes four in this session.** It asserted on the real
  fixture, whose page is a SINGLE band — so per-band and per-page counting cannot differ there and
  it passed against the bug. The replacement builds a page where the two readings disagree: the
  sparse band's fragments sit inside the left column's own x-range, so the page projects to two runs
  while the band alone projects to three. Verified by restoring the old code, which now fails it.

  **A consequence stated in three places was simply false.** `_MIN_GUTTER_SHARE`'s comment, invariant
  73 and a changelog entry all said raising the threshold past 0.038 would make the real page "read
  as one column and stop being reordered at all". It would not: the only test is `> 2`, so a count of
  1 falls through to the split exactly as 2 does, and the output is byte-identical at 0.02, 0.05 and
  0.30. The hazard runs the other way — a higher value merges runs, lowers the count, and stops the
  four-column DECLINE from firing.

  **The single-column end-to-end test never reached the guard it named.** `make_text_pdf` draws one
  unwrapped line per page, so OCR returned a single region and `reading_order` short-circuited at
  `len(items) < 2`; mutating the page-level threshold left it green. `make_single_column_pdf` draws
  five lines, and the test now asserts it produced enough regions for anything to be exercised.

  **Three defects in the budget note.** "No generation cap was reported" was shown when a cap WAS
  reported but the provider returned no usage — two states collapsed into the message for one, in
  both languages; there is a fifth state now. The `dropped` warning overwrote `className`, destroying
  the truncation colour on a run that both hit the cap and had its step budgets rejected — the one
  thing those colours exist to keep separable. And `.traj-note.is-cut` used `var(--danger)`, which is
  not a token in this stylesheet; the project's token is `--bad`, defined for all three themes.

  Also corrected: dspy's `_check_truncation` was credited with a mechanism it does not use (it
  branches on `finish_reason == "length"`, never on token counts — the rule is the kit's
  recommendation, not dspy's), and `worker.py` still carried a comment calling its import private on
  the very line `b841605` changed to the public one.

- **Made invariant 73's headline claim reproducible in CI.** Every accuracy figure recorded for the
  reading-order work was measured on real papers that cannot go in the repo, so CI could reproduce
  none of them — the numbers were evidence a reader had to take on trust. Two tests now run the REAL
  OCR stack over a two-column page built from prose this project owns
  (`_pdf_fixtures.make_two_column_pdf`, drawn at coordinates so the gutter belongs to the fixture
  rather than to a layout engine).

  **They assert STRUCTURE and DIRECTION, not a figure.** "Every left-column line precedes every
  right-column line" does not depend on how well the OCR read the characters; an exact ratio would
  move with an OCR version and would have to be re-measured rather than trusted. The similarity check
  only pins that the gain is real and clear (measured +0.222 on this page, asserted > +0.10).

  Confirmed the effect reproduces on synthetic content BEFORE building the test: 0.459 detector order
  against 0.681 reordered. The gap between 0.681 and a perfect 1.000 is OCR dropping spaces
  (`eachlayerhas`), which hits both readings equally — the ordering itself is exactly right, which is
  why the structural assertion is the load-bearing one. Verified by neutering `reading_order` to
  return detection order, which fails the two-column test.

  **What is still NOT reproducible, stated rather than left implied**: the corpus-level measurements —
  the 0.425 -> 0.756 across twelve real pages, the scanned-corpus validation, the CJK figures, the
  good/garbled score overlap behind invariant 74. Those are properties of documents, not behaviours,
  and pinning them would mean shipping the documents. They stay recorded as single-run measurements
  with their provenance.

- **A four-column page is declined instead of being cut in half (invariant 73).** Recorded as a
  limitation when a review found it; now fixed. Three columns already declined themselves — the
  middle column crosses the centre, so the page-level guard fires — but an even count has its centre
  in the middle gutter with nothing spanning it, so the split ran and produced
  `c1r1 c2r1 c1r2 c2r2 … c3r1 c4r1 …`: the page halved, and the rows inside each half interleaved.
  That is the defect the whole module exists to prevent, at half scale, and it was reproduced before
  being fixed rather than taken from the note.

  `_column_count` projects a band onto the x-axis and counts the runs a real gutter separates; above
  two, the count declines. **The threshold's hazard runs UPWARD, and the first version of this entry
  said the opposite**: the real two-column page has a 38px gutter across 996px of content, 0.038
  against a 0.02 threshold — but raising the value MERGES runs and LOWERS the count, and since the
  only test is `> 2`, a count of 1 falls through to the split exactly as 2 does. Output is
  byte-identical at 0.02, 0.05 and 0.30. What a higher value breaks is the DECLINE: a four-column
  page merges to two or fewer and is halved again.

  One probe was wrong before it was right: counting columns over ALL the page's regions returned 1,
  because the page number sits IN the gutter. `_order_band` never sees it — `reading_order` peels
  every centre-crosser off as a band boundary first — so the count on the band it actually receives
  is 2. The fix was to the probe, not the code.

  Four of five mutations die (dropping the decline, declining at >1, moving the gutter share to
  0.05, taking `reach = end` instead of the running max). The fifth is `>` versus `>=` at exactly
  the threshold, accepted unpinned for the same reason as the other exact-equality boundaries here.

- **`line-length = 110` is enforced now, not a convention.** Ruff's default rule set carries no
  `E501`, so the number in `pyproject.toml` was a formatter setting that `check` ignored — about 20
  over-long lines had accumulated, and a name scrub once left a 157-character line that only an
  independent review caught. All 19 remaining offenders rewrapped (eight prose, eleven restructured
  code) and the rule selected.

  **Selected with `extend-select`, never `select`.** The first attempt named `select` and re-listed
  what the defaults were believed to be, which is a guess: it pulled in `E402` and reddened 20 lines
  in the test suite — the deliberate `pytest.importorskip` that has to run BEFORE the imports it
  guards, which the Verify section documents. `extend-select` adds to the real defaults instead of
  replacing them with a reconstruction.

  Verified in both directions rather than by the tree going green: a probe file with a 120-character
  line is now reported, and the tree is clean.

- **Built the `run_end.budgets`/`usage` surfacing the entry below specified (invariant 75).**
  `trajectory.budget_summary` is a pure function over trace events — no server, no model, no run,
  the seam invariant 44 established — and the Trajectory drawer gained a budget note beside its
  timing note.

  **Three states, and the third is why this needed a rule.** A run that stayed under its cap shows
  the busiest turn against the cap and the percentage; a run that hit it shows the truncation with
  both numbers and what it costs (a truncated code cell is usually repaired by the planner's next
  turn, a truncated final answer ends the run); and a trace from before rlm-harness 1.10.0 shows
  **NOT RECORDED**, in its own colour, with the string itself denying the wrong reading. The three
  are distinguishable by colour before the sentence is read, which was the point.

  **The proximity reading shipped as a number**, per the correction recorded below — the "no
  gradient" measurement came from a corpus at twice its model's needed cap and does not transpose to
  16384. It is labelled as a shape to expect rather than a local figure.

  **Two of this project's own tripwires caught the work**, which is the system behaving as designed:
  invariant 48's translation-key check refused the new `t()` keys until the zh-Hant table had them,
  and the Chinese-punctuation check rejected an em dash carried over from the English copy. A third
  was added — a source-tree assertion that the not-recorded branch comes first and uses its own
  string, since there is no JS test runner (invariant 36).

  Verified by mutation rather than by passing: six mutations of `budget_summary` (returning `{}`
  instead of `None` for an unmeasured trace, `>=` to `>` at the cap, dropping the no-cap guard,
  taking the first attempt instead of the peak, always computing the ratio) each fail at least one
  test, and disabling the null branch fails the new tripwire.

- **Design constraint recorded for the `run_end.budgets`/`usage` follow-up, BEFORE building it.**
  The kit upgrade made those fields available; `trajectory.py` reads `run_end` and surfaces neither,
  which is a real gap for a drawer whose whole purpose is "why did it produce that"
  (`accepted-not-done`). Guidance arrived from the kit maintainer as a measurement, was recorded,
  and was then overturned by its own author — both halves are kept below, because which half
  survived is the useful part:

  **First guidance, since CORRECTED — recorded because the correction is the lesson.** The initial
  advice was "do not build a proximity indicator, there is no gradient": on the measured corpus the
  used/cap ratio had a HOLE, 363 runs below 0.6, zero between 0.6 and 1.0, 21 at exactly 1.0.

  **That hole is an artifact of the CAP, not a property of the model, and it does not survive
  transposition to this project's cap.** The measured corpus ran at 32768; this project's
  `max_tokens` is 16384 (invariant 59). Converting each bin back to absolute tokens and re-dividing
  by 16384 moves the two bins spanning 9,830-16,384 tokens — 64 runs — straight into the band that
  was empty, and the two runs sitting in 16,384-19,661 would TRUNCATE outright rather than fit
  comfortably. Median max-turn 0.209 -> 0.418, p90 0.378 -> 0.756; both are the mechanical doubling.
  **So at 16384 there IS a gradient, and a proximity reading may be exactly the right thing to
  build.** The hole said the cap was roughly twice what that model needed, never that the model has
  no middle.

  Arithmetic checked here rather than accepted: the bins transpose exactly as claimed and 49 + 15 =
  64. A denominator that did not reconcile — 64/379 against earlier figures summing to 384 — turned
  out to be **two populations reported without saying so**, and the split is worth keeping because
  it changes which number to quote: 385 runs reached `run_end`, of which 379 SUCCEEDED and 6 FAILED.
  The binned distribution is the successes only (363 / 0 / 16 at the cap); the failures add
  1 / 0 / 5; across all 385 it is 364 / 0 / 21, which closes. So **64/379 = 16.9% of successful runs
  and 64/385 = 16.6% of everything reaching `run_end`** — both defensible, neither interchangeable.
  It cross-checks independently against the same source's "21 hit the cap, 16 finished anyway":
  16 successes plus 5 failures at the cap is exactly 21.

  **What keeps this an indication rather than a measurement**: transposing assumes a run's token
  count is unchanged by the cap it ran under. `max_tokens` is a hard stop rather than a hint, so
  that is plausible, but a model given less room may genuinely write shorter and nothing here
  settles it. Confirm against this project's own runs before treating 17% as a local figure.

  **What survived the correction unchanged is the MECHANISM**, and it is the half worth relying on:
  of the runs that hit the cap, most finished anyway — a truncated CODE cell is a `SyntaxError` that
  dspy's own in-loop feedback repairs, while a truncated FINAL answer kills the run. That is a
  property of dspy's loop and carries to any cap and any model. So the surfacing to build is
  per-run and retrospective — "a turn in this run was truncated at N tokens against a cap of M" —
  with a proximity reading now a live option rather than a ruled-out one.

  **The pattern is the lesson, and it repeated twice in two exchanges**: a fact true in one
  configuration, stated without the configuration. The same source's import advice dropped an
  underscore from a NAME and left the import reaching through a private MODULE; this one reported a
  hole and left out that a hole at 2x the needed cap says nothing about 1x. Splitting an incoming
  claim by how far it travels — mechanism versus measured shape — caught both before either was
  known to be wrong, which is why the provenance line is recorded next to every borrowed number
  here rather than dropped once it looks settled.

  **And one working rule, earned by getting it wrong in this very entry: after correcting a claim,
  re-read what INTRODUCES it, not only the claim.** The correction above replaced the guidance and
  left the entry still opening with "it rules out the obvious design" — the one thing the correction
  had just removed, sitting in the first line a reader meets. Same shape as fixing the underscore in
  `_short_error` and leaving the import reaching through `_retry`. The challenged sentence is easy to
  find because somebody quoted it back; the sentence that set it up is not, because nobody did.

- **A third review round, this time over the restorations themselves; six defects fixed.** Restored
  prose is the dangerous kind, because it reads as authoritative while nobody has re-checked it
  against the code. Of 26 claims put back by the two restoration commits, four were wrong.

  **The worst pointed a maintainer at the wrong file.** The restored coverage floor — mutation
  testing once got `setAttribute("href")`, a template-literal `` createElement(`a`) `` and a
  `window.location` assignment past the test — was attributed to
  `test_the_markdown_renderer_builds_nodes_rather_than_markup`. That test checks
  `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write` and would fail on none of the three.
  The floor belongs to `test_the_markdown_renderer_never_creates_a_navigable_link`, which is a
  different test with a different sink list. Someone widening an XSS guard would have widened a file
  that does not have one. The two are now named separately with an explicit "do not merge these in
  your head".

  **One overstated a guarantee.** The lazy-titling tripwire's `ensureTitle();` count is a FLOOR
  (`>= 4`), so it catches a call site being DELETED, not a fifth model-running action forgetting to
  add one. The restored sentence claimed the latter. The useful half is the slice assertion, and the
  text now says which half does what.

  **Two were mechanical and both from the restore itself**: a "rests on four rules" lead-in left
  standing over five bullets after one was appended, and an insertion that landed mid-sentence and
  orphaned a `The`.

  **The substantive code gap: the log's headline number was untested for the case it exists to
  explain.** Gating it on `replaced` instead of `second_opinions` survived every test — and that
  mutant silences the line for exactly the majority case in the 260-page measurement, where most
  suspected pages are NOT replaced. The logging test also made all four quantities equal (two pages,
  two suspected, two replaced), so swapping any two in the format string passed. Now: four pages,
  two suspected, one replaced, one blank — four different numbers, with a second test covering
  "suspected but nothing replaced". Getting the blank page to matter took two attempts: the
  monkeypatched OCR stub was handing text to a page that has none, so `len(blocks)` silently equalled
  `len(pdf)` again and the mutant lived through the first fix.

  Also: both empty-log assertions are scoped to this module's logger rather than to all of
  `caplog.text`, and the real-geometry fixture's self-disclaimer now names all three things it cannot
  see (its single centre-crosser is the last detection, so the spanning branch is invisible in it
  too) alongside the one thing only it can — `_order_band`'s within-column sort key, which no
  hand-built fixture reproduces.

- **Closed the mixed-script scoring hole, and made one measurement reproducible in CI.** Both were
  named as open when the OCR work was reviewed; neither had been acted on.

  **A garbled Chinese body carrying a clean English reference list scored 1.000 and was never
  challenged.** `wordlike_ratio` reads Latin tokens only, so on a mixed page its verdict came
  entirely from whatever minority happened to be readable — measured at a 0.49 Latin share of the
  page's alphabetic characters. The CJK protection was "there are no Latin tokens", which is a
  property of pure CJK pages and not of the mixed ones that actually occur. It is now a SHARE
  (`_MIN_LATIN_SHARE`, 0.7): the function asks whether the rule applies before asking what it says.
  Erring high costs a missed improvement, erring low lets a Latin-shaped rule pass sentence on a
  page written in something else, so the uncertainty is spent upward. `_WORD_TOKEN` and
  `_LATIN_CHAR` are built from one character-class constant so they cannot drift apart about what
  counts as Latin — one decides what is scored, the other whether scoring applies.

  **Every OCR number in these entries came from documents not in the repo, so CI could reproduce
  none of them.** One test now drives real detector geometry: 105 boxes measured off a rendered
  two-column page, stored as `tests/fixtures/ocr_two_column_page.json` with the TEXT EXCLUDED, so
  the fixture carries a real page's layout without carrying its prose. It asserts the structure —
  the whole left column, then the whole right, then the centred footer — rather than freezing an
  output list, which is the difference between saying what correct means and locking in today's
  answer; and its gutter bounds are read off the measurement rather than computed by the code under
  test. Stated rather than oversold: that page is a single band, so the band-assignment key and the
  vertical-centre choice are invisible in it and stay pinned by the synthetic fixtures. `tests/` is
  not in `pyproject.toml`'s `packages`, so none of this ships in the wheel.

- **Finished the condensation audit: invariants 1-37 read semantically, ten losses restored.** This
  range had only ever been checked mechanically — that every heading survived and every bold rule
  still appeared — which is a weaker check than the one that found real losses in 38-72, and it was
  the last unread part of the rewrite. Every restored item was verified live in the code first.

  **1-37 came through markedly better than 38-72**: no inverted security statement, no weakened
  contract, and every residual-risk hedge intact. What it lost is almost entirely the layer linking
  a rule to its enforcement, plus two client-side rules that had no other home.

  **The two that had nowhere else to live** are both in invariant 29's dropped `↓ Download`
  paragraph: the filename is SLUGGED from the model-authored notebook title, because `download` is an
  attribute the browser turns into a path component; and its extension follows the SERVED file,
  because a provider may emit WAV and naming it `.mp3` would mislabel half of them. The second is the
  sharper loss — `app.js` records that an audit once found it listed among invariant 43's "handled"
  consequences when it was not, so invariant 43 is explicitly not its home either.

  **One behaviour lost its "what" while keeping its "why".** Invariant 34 kept "the lifespan reads
  the retention settings itself — otherwise a typo'd value means silently never prune" but dropped
  "a malformed one refuses startup instead". Someone could satisfy every word of the surviving
  sentence by warning-and-defaulting, and turn a typo'd `RN_TRACE_RETENTION_DAYS` back into silently
  keeping files that hold ingested source text.

  **Also restored**: five enforcement links to live tests (the lazy-titling tripwire, which also
  asserts a CALL COUNT so a fifth model-running action must touch it; the process-group test that
  spawns a real grandchild, one of the few executable claims here rather than a source-tree
  assertion; the guide-registry tripwire; the captionless-YouTube 422 test; and the specificity test
  invariant 36 refers to only as "a separate test"); the temp file whose `finally` must wrap
  `synthesize()` itself, not just the read-back; the persisted `Overview.run_id`/`Podcast.run_id`
  contract that invariant 70's re-openable "⌁ N steps" pill rests on; invariant 6's "don't
  over-tighten it into false negatives chasing a clean read"; invariant 18's point, which the
  condensation left hanging (a third host needs BOTH maps updated and only one fails loudly); and
  invariant 37's `textContent`-never-`innerHTML` clause for the one model output with no schema
  validation behind it.

  **Checked and correctly dropped**, recorded so the line is visible: the pymupdf/AGPL discovery
  story, the `/etc/passwd` reproduction, the lost-update reproduction, the VTT design history and
  every "an independent audit found…" attribution are incident narrative and belong here. Invariant
  24's enumeration of `SystemExit` sources was declared wrong by the old text itself. Invariant 36's
  `.studio-view { display: flex }` example is stale — that rule no longer exists in `style.css`.

- **`parse_pdf` now reports what the second-opinion OCR cost, because that cost was measured only
  after it shipped.** Asking what invariant 74 actually does to the 260-page scan that motivated it
  gave: 61 pages suspected and OCR'd for comparison, 4 unscoreable, 187 untouched. So roughly a
  quarter of that document pays a full OCR pass on top of reading its own text layer — and on the
  API path that runs in the request's thread pool (invariant 34's accepted limitation), where a slow
  ingestion is indistinguishable from a hang. One log line per document, only when a page paid,
  naming how many paid and how many the payment changed. Same idiom as the trace sweep's line.

  **Deliberately not capped.** A page with NO text layer already costs the identical OCR pass under
  invariant 7, uncapped and uncontroversial, so bounding the speculative case more tightly than the
  unavoidable one it sits beside would be backwards — and a cap would silently leave garbled text on
  whichever pages fell past it. The honest answer to "why is this slow" is a sentence, not a limit.

  It also settles a question left open when invariant 74 shipped: the short garbled strings quoted as
  its trigger all score `None` on their own, so it was not obvious the feature fires on the document
  they came from. It does — those strings are excerpts, and the full pages clear the token floor.

- **Restored what the rulebook condensation dropped: enforcement links, one security statement, and
  four contract details.** The condensation moved incident narrative to this file, which was its
  stated intent and is right. What it also removed, unintentionally, was the layer of the rulebook
  that connects a rule to the thing enforcing it — and for rules whose ONLY enforcement is a
  source-tree assertion (invariant 36: this project has no JavaScript test runner), the rulebook is
  the only place a later reader would learn the rule exists at all. Every item below was verified
  live in the code before being restored; nothing was put back on the strength of the old text.

  **One rule had disappeared entirely.** `test_no_event_is_subscribed_twice_inside_one_init_function`
  (`tests/test_web_assets.py:209`) still runs, and the prohibition it enforces — one subscription per
  event per init, because four inits in `app.js` spell the same event names and a duplicate handler
  reads as a race that isn't one — appeared nowhere in AGENTS.md. Deleting that test would have
  contradicted nothing.

  **One statement had been inverted, which matters most.** Invariant 52 said the ticker's `detail`
  "can quote ingested source text — the same category invariant 29 already records". What survived was
  only "the step's `output` is deliberately NOT streamed", which reads as though no source text
  reaches the SSE stream at all — on an API with no authentication (invariant 25). The stronger claim
  is now stated first, with the narrower one explicitly marked as not a promise.

  **Also restored**: the markdown renderer's XSS tripwire together with its coverage floor (mutation
  testing once got `setAttribute("href")`, a template-literal `` createElement(`a`) `` and a
  `window.location` assignment past its first version — a future widening must still catch all three);
  `assert_repl_safe` as half of what the invariant-1 tests check; `TTSProvider.synthesize`'s offsets
  being **in seconds**, which is the contract between every provider, `Podcast.offsets` and `app.js`'s
  seek handler; the `rlmnb-podcast-length` storage key; the `corpus-navigation` skill by name;
  `.notebook-menu` as a clipping ancestor, which invariant 54's own text says the test cannot see;
  `RN_BASE_URL` being "not just a URL, and a later reader must not relax it on that basis"; clearing
  the conversation being "the one thing NOT to do" as a freeze signal; and the residual-risk hedge on
  invariants 39, 49, 56 and 62, whose absence had made those four read as stronger claims than the
  ones that kept it.

  **Checked and deliberately NOT restored**: six other test names the old file mentioned are still
  live, but in each case the RULE survived the condensation and only the test's name went — and
  `test_the_podcast_transcript_is_not_capped_by_a_fixed_height` carries its whole rationale in its own
  docstring. Naming every test in the rulebook is not the convention; naming the ones that are a
  rule's only enforcement is.

- **An independent review of the OCR work found three real defects and a hollow test; all fixed.**
  Every finding below was reproduced locally before being acted on.

  **A correct text layer could be replaced by a WORSE OCR of itself, for accented Latin scripts.**
  `_WORD_TOKEN` was `[A-Za-z]{2,}`, so a diacritic split every accented word into ASCII fragments
  and the vowelless residue counted as garble: correct German scored 0.824 and correct Vietnamese
  0.375, both under the 0.85 suspicion gate. Worse, stripping the accents — exactly what a weak OCR
  does — raised both to 1.000, clearing the replacement margin. The metric REWARDED the degradation.
  This was the same "a bundled dictionary would describe one language while condemning pages in
  another" that the dictionary-free design exists to avoid, reintroduced through the regex, with
  only CJK actually protected. The token class now spans Latin-1 Supplement, Latin Extended-A/B and
  Latin Extended Additional, and the vowel test folds accents through NFD first. Deliberately not a
  general Unicode-letter class: CJK characters are letters too, and matching them would end the
  `None` that keeps a Chinese page away from rules about vowels.

  **The replace decision was volume-blind.** Both sides are RATIOS with no length term, so a
  484-character layer scoring 0.682 (four clean sentences plus a garbled figure block) was replaced
  by a 59-character OCR result scoring 1.000 — a page of prose traded for a caption.
  `_OCR_MIN_TOKEN_SHARE` (0.25) now requires the second opinion to have read a comparable amount of
  the page. Calibrated on real pages: the two that genuinely needed replacing scored 0.39 and 0.45,
  a diagram page that must keep its layer 0.03, the constructed loss 0.10.

  **`ocr_image`'s documented "never raises" had become false.** `reading_order` reads coordinates
  out of the detector's result and sat OUTSIDE `_try_rapidocr`'s try/except, so a `None` box, a flat
  xyxy box, a two-element row or a non-numeric coordinate all escaped — verified, all four. The
  earlier code touched only the text field, so this change widened the unguarded surface from row
  arity to every coordinate value, against a dependency pinned `>=1.3` with no upper bound.

  **The test named for invariant 74's headline rule did not test it.** Its OCR fixture contained
  `ELTN`, the same token the assertion looked for in the layer, so the assertion held whichever text
  came back: deleting the entire comparison from `_page_text` left the suite green, as did setting
  the margin to zero. Fixed, and the margin is now pinned from both sides.

  **Mutation testing drove the rest.** Of the surviving mutations the review reported, the two that
  mattered are now killed: the band sort key and the top-edge-versus-centre choice. Both needed a
  fixture with a centre-crossing region to be observable at all — inside one band the regions are
  re-sorted into detection order anyway, which is why every earlier fixture left them alive.
  Three survivors are ACCEPTED and stated rather than chased: centre versus bottom edge, and two
  boundary flips (`>` to `>=` on the spanning guard, `<=` to `<` in the partition) that differ only
  on exact equality. Writing tests for those would be contriving inputs to defend an arbitrary
  choice.

  **Overstated claims corrected rather than defended.** Invariant 7 said the garbled-layer gap was
  "closed"; it is narrowed — a layer too garbled to yield eight Latin tokens still scores `None` and
  is never challenged, which covers most of the short strings quoted as the trigger. The docstring
  listed `ELTN` as an example of "no vowel at all" while the code scores it wordlike. `pdf.py`'s
  comment still said this project's use case is a missing layer "not a garbled one" twelve lines
  above the code that handles a garbled one. The "safe side" framing on `_MAX_SPANNING_FRACTION`,
  the "unsupported layouts decline themselves" claim (true for odd column counts; a four-column page
  passes the guard and is split down the middle) and "language-agnostic" (the split hardcodes
  left-then-right, so a two-column RTL scan would be swapped) are recorded as limits.

  **Not fixed, and worth naming**: the condensation in `15813c4` dropped the enforcement records
  linking several live tripwire tests to the rules they pin, weakened invariant 52's statement that
  the reasoning stream can quote ingested source text, and dropped a few contract details
  (`synthesize`'s offsets being in seconds, the `rlmnb-podcast-length` key, the `corpus-navigation`
  skill by name). That is a separate restoration pass over a commit this work did not author.

- **Measured the CJK OCR coverage, and rejected a Traditional Chinese recognition model as a
  wash.** No code changed; this is the evidence, and the reason not to do it again.

  The default backend already handles both scripts. RapidOCR ships `ch_PP-OCRv4`, which is
  Chinese-native: Simplified measured 1.000 on a paragraph and 20/21 per isolated character,
  Traditional 0.879-0.973 per paragraph and 16-17/21 isolated (two fonts, Songti TC and Heiti TC).
  Invariant 73's reordering is language-agnostic and helps Chinese exactly as much as English —
  a two-column Simplified layout went 0.646 -> 1.000 — while a single-column CJK page crosses the
  centre on every line and is left untouched.

  PaddleOCR's `chinese_cht_PP-OCRv3` recognition model was then fetched with the official
  `chinese_cht_dict.txt` (8421 characters, covering every character that had failed) and wired in
  through RapidOCR's `rec_model_path`/`rec_keys_path` seam — which exists precisely because the
  bundled models carry their dictionary in ONNX metadata while an external file is also accepted.
  Head to head over six cases it was a wash: mean 0.929 against 0.922, winning two, losing three,
  tying one. Not worth an 11MB model, a doubled OCR pass on every CJK page, and the provenance of
  a third-party conversion (RapidOCR publishes no `chinese_cht` ONNX of its own; only japan, korean
  and english).

  **The trap, recorded because it inverted the conclusion twice.** `PIL.ImageFont.truetype(path,
  size)` loads face index 0 of a `.ttc` COLLECTION, and index 0 of macOS `Songti.ttc` is Songti
  **SC** — which silently renders nothing at all for Traditional-only glyphs. The first pass
  scored Traditional at 0.589 with 0/21 isolated characters, which read as the backend having no
  Traditional support, and produced two further false findings on top: that swapping in the
  `chinese_cht` model changed nothing (it was the *detector* finding no ink, not the recogniser
  lacking the character), and that invariant 73's reordering compounded the damage (the blank gaps
  fragmented each line into pieces the geometry then mistook for two columns). Rendering the
  fixture to a PNG and looking at it showed blank space where the characters should be. Every one
  of those findings evaporated with a font that has the glyphs.

- **A garbled-but-present text layer is now caught, by comparing against OCR rather than by
  trusting a threshold (invariant 74).** Invariant 7 had recorded "a bad-character-ratio heuristic"
  as the follow-up for this gap. The heuristic does not work on its own, and measuring is what
  showed it: across six documents the good pages' worst scores overlap the mis-decoded pages' on
  every metric tried — alphanumeric ratio, long-token ratio, dictionary hit rate, and the shape
  score that shipped (good 0.79-0.99 against garbled 0.63-0.80). A false positive is not free
  either, since a good text layer beats any OCR of the same page.

  So the score only decides whether to SPEND an OCR pass and the comparison decides what to keep:
  below 0.85 the page is OCR'd as a second opinion, and the layer stands unless OCR beats it by
  0.10. A generous gate then costs time and never quality. The margin earned its place immediately —
  a bare `>` flipped a healthy page (0.97) to OCR (0.98) on a rounding-level difference, while the
  genuinely mis-decoded pages won by +0.20 and +0.27.

  **The trigger was a real document**, found while validating the reading-order work: an Internet
  Archive scan of a 1960 IRE monograph whose chart pages were fed to the scanner upside-down or
  mirrored, so its embedded OCR decoded to `UN ELTN NII PIN COCO` and `Zh *9td 3ONVY G3zMw30!` —
  that second string is "FIG.72 / ACTUAL RANGE" reversed. `_MIN_TEXT_CHARS` sees characters, skips
  OCR, and that is what reached the corpus.

  **An assumption had to die first.** The initial read was that re-OCRing those pages gains nothing
  because the source is a chart, and that was stated before it was checked. It is false: on the same
  pages OCR recovered `FALSE ALARM INTERVAL`, `PULSE REPETITION RATE` and `THE INCOMPLETE TORONTO
  FUNCTION`, because it reads the page as rendered rather than as the scanner mis-fed it. Had that
  gone unchecked the conclusion would have been "not worth building".

  **`wordlike_ratio` is dictionary-free on purpose**: `/usr/share/dict/words` is absent on stock
  Debian so CI cannot depend on it, and a bundled list would describe one language while condemning
  pages in every other. Two shape rules replace it — no vowel anywhere in the token, and case
  flipping mid-token, with all-caps exempt. Real garble often does contain vowels (`ELTN` scores as
  wordlike), so it works in aggregate and never per token.

  **Accepted loss, stated rather than discovered later**: a pure diagram page OCRs to a handful of
  numeric labels, falls under the eight-token floor, scores `None`, and keeps its garbled layer even
  though the OCR was observed to be better. `None` is also what keeps a CJK page safe from rules
  written for alphabets with vowels, so the floor is load-bearing in the other direction.

- **Validated the OCR reading-order fix on real scans, which is the only population it serves.**
  Everything the fix was originally measured on was a rendered DIGITAL PDF — but only a page with
  no text layer reaches OCR at all, so the whole calibration had been done on a proxy for the
  target rather than the target. Skew was the specific worry: a scan rotated a fraction of a degree
  widens every line's bounding quad and drifts its vertical centre, and those are exactly the two
  numbers the ordering keys on.

  **It transfers.** Physical Review Letters, December 1958, a genuine two-column scan (with the
  facing page bleeding into the right margin, as scans do): 16 pages, **0.329 -> 0.509**, the split
  applied on every one of them, spanning fractions 0.01-0.05 — the same band the clean renders
  produced. The absolute numbers sit lower than the digital measurements because the reference is
  Abbyy's OCR of degraded 1958 print, so two OCR engines disagree at the character level no matter
  what the ordering does; the delta is the part that means anything. One page moved -0.005.

  **Skew was then isolated rather than left confounded** with sensor noise, old typography and the
  reference OCR's own errors: rotating a clean two-column render by 0.25, 0.5, 1.0 and 2.0 degrees
  held the spanning fraction at 0.00-0.08 and the split fired at every angle. Two degrees is well
  past what a scanner introduces, so the mechanism that prompted this check is not a risk in the
  range that occurs.

  **The first sample was wrong and the negative results are worth keeping.** Three other real scans
  (an IRE monograph, Scientific American Supplement 1890, a declassified typescript) all measured
  +0.000, which read as "inert on real scans" until the pages were actually looked at: the monograph
  is single-column, the typescript is single-column, and the 1890 magazine is THREE-column. Leaving
  all three untouched is the correct behaviour — a three-column page puts its middle column across
  the centre and so declines itself by the same arithmetic that recognises a single-column page. The
  reading was assumed from the journal's name; rendering one page to an image settled it in seconds.

  **Noted in passing, and now evidenced rather than theoretical**: that IRE scan's own embedded text
  layer is garbage on some pages (`'‘ \r\n“ i \r\nsi - a \r\nal 2 yt 7 wo'`). `_MIN_TEXT_CHARS = 1`
  sees characters, declines to run OCR, and that string is what would reach the corpus — the
  garbled-but-present text layer invariant 7 records as an open gap, in a document anyone could
  ingest today. *(Later in this same section: invariant 74 narrows that gap but does not close it,
  and this particular string is one it still misses — four Latin tokens is under the scoring floor,
  so the layer is never challenged. The entry below states the limit.)*

- **Rejected: `PaddlePaddle/PicoDet-S_layout_3cls` as a shipped default.** Evaluated after the
  OCR reading-order defect above was suspected, since a layout model is the textbook answer to it.
  Licensing was NOT the problem — Apache-2.0 on the model card and in the Hugging Face repo
  metadata, the same footing as RapidOCR and Tesseract, with none of the AGPL/Artifex trouble that
  removed `pymupdf` (invariant 7).

  **It detects table, image and stamp — there is no text class**, so it cannot recover reading
  order, columns or headings, which is the one thing that was actually broken. The same PicoDet-S
  backbone ships as `PicoDet-S_layout_17cls` at the SAME 4.8 MB and the same ~17.5 ms CPU latency
  (mAP 87.4 vs 88.2) with 17 categories including Text, Paragraph Title, Header and Footer — so
  within one model family the 3cls checkpoint is the least useful one available at that size.

  **The published checkpoint is Paddle's own inference format** (`inference.pdiparams` +
  `inference.json`, 4.8 MB), not ONNX: running it as documented needs `paddlepaddle` — measured at
  **104.5 MB for the macOS arm64 wheel and 194.8 MB for manylinux x86_64** — plus `paddleocr`, next
  to an OCR stack that is entirely ONNX today. An ONNX detour exists (`rapid-layout`, Apache-2.0,
  reusing the `onnxruntime`/`numpy`/`opencv`/`Pillow` this project already installs), so the runtime
  cost is avoidable, but only by taking the weights from somewhere other than this repo.

  **Nothing in the schema could consume the output either**: `SourceBlock` is text-only at
  `page:<n>` granularity, and a table bounding box is useless without a table-structure model
  (SLANet) behind it — that is PP-StructureV3, not one small model. **One objection was measured and
  withdrawn**: rasterising every page to feed a detector was assumed expensive, but 12-15 pages at
  2x measured 0.13-0.19s, the same order as text extraction.

  **If layout detection is revisited**, the checkpoint is `PicoDet-S_layout_17cls` or PP-DocLayout-S
  (4.83 MB, 23 categories), packaged as ONNX, and opt-in first per invariant 43's "installed and run
  before adopted" bar. Its remaining value is narrow: dropping figure-internal label noise from OCR
  text, which is what survives the geometric fix above.

- **First slice: ingestion (text/web/PDF with local hybrid OCR) + citation-grounded chat, driven
  from a CLI.** No session persistence, no API/UI, no Notebook Guide, no Audio Overview yet — see
  AGENTS.md's Scope note. Everything below is what this slice actually contains, and the design
  calls that shaped it.

  **All sources become one blob, not a vector index.** `corpus.py` concatenates every ingested
  source into a single string tagged with `[[SRC:<id>|<locator>]]` markers and hands the whole thing
  to `AnswerQuestion` as one signature field — the model explores it in the sandboxed REPL
  (`.find()`/slicing) rather than through embedding similarity search. This is rlm-harness's native
  mechanic (an RLM signature field *is* a REPL variable), not a new indexing layer; a vector-search
  fallback for corpora too large for one blob is deferred until real usage shows the size cap
  (invariant 8) actually binds.

  **No fetch/network tool is reachable at question-answering time.** Early designs considered
  reusing `rlm_harness.tools.fetch.make_fetch_tool` as a live tool so the model could pull in more
  context on demand; adversarial review found this turns a prompt-injected source into a live data
  exfiltration path, since the SSRF guard only blocks internal targets, not legitimate-looking
  external ones. Ingestion-time fetching is host-side and one-shot instead — see invariant 1. A
  second, independent review then found that the ingestion-time fetch itself had a gap: the
  default `urllib` opener follows a redirect's `Location` header unconditionally, so an
  initially-safe URL could 302 to an internal/metadata target with no further check. Fixed with a
  redirect handler that re-validates every hop (invariant 2), verified against a real redirect
  target before landing.

  **Citation verification is coordinate-only, and says so.** `citations.py` confirms a `Citation`'s
  `source_id`/`locator` resolves to real corpus text; it does not attempt to verify the model's
  prose is faithful to that text, and no docstring or UI copy should imply otherwise (invariant 5).
  `AnswerQuestion` also validates its own draft against `Answer`'s schema in-REPL, before SUBMIT,
  via `rlm_harness.tools.validation.make_schema_validator` — chosen over a post-hoc whole-run retry
  because rlm-harness's own retry policy defaults to `max_retries=1` specifically because a full RLM
  re-run rarely fixes a persistent (rather than transient) coercion failure. Not yet verified
  against a real model, only an offline scripted one — see invariant 4's residual-risk note.

  **`injection_scan.py` flags, never blocks.** A deterministic heuristic scan runs at ingestion
  time; a flagged source's content still reaches the model and its answer still returns, with the
  flag surfaced as metadata alongside it (invariant 6) — this is a transparency mechanism, not a
  gate, matching the reward-free/judgement-only posture this whole family of rlm-harness consumers
  shares. Its rules favor recall over precision on purpose (invariant 6's note).

  **OCR ships enabled, not merely pluggable.** `parsers/pdf.py` uses `pymupdf4llm`'s built-in hybrid
  OCR (RapidOCR primary, Tesseract fallback) for scanned/image PDF pages, with the backends as core
  `dependencies` rather than an opt-in extra left uninstalled by default — an independent review
  caught an earlier draft doing exactly that (an `ocr` extra CI's plain `uv sync` never installed,
  reproduced with a real failing test against a clean sync), the same mistake a sibling open-source
  project shipped and had silently fail to parse image sources in its default Docker image; see
  invariant 7.

  **Execution model: still in-process for this slice.** An earlier design iterated on how to isolate
  each chat turn (a `serving.py`/`harness_serve.py`-based subprocess pool was proposed, then
  adversarial review found that mechanism is built for one-shot hierarchical task delegation, not
  high-frequency low-latency turns, and its `stdout` contract blocks any progress-event side
  channel). The simplification landed on was: one plain subprocess per turn, `start_new_session=True`
  for a reliable `killpg`-based cancel, no pre-warmed pool. That runner (`runner.py`/`worker.py`) is
  not implemented in this slice — `cli.py` calls `AnswerQuestion.run()` in-process — and lands with
  the API/UI slice that actually needs concurrent turns and cancellation.

- **Second slice: a persistent, multi-turn `Notebook`** (`schema.Notebook`/`notebook.py`) — sources
  and chat history now survive across `ask` invocations via `--notebook <id>`, one JSON file per
  notebook (`notebooks/<slug(id)>.json`), no database. Without `--notebook`, `ask` is unchanged
  from the first slice (ephemeral, nothing persisted).

  **History is a third signature field, not folded into `question`.** `AnswerQuestion.signature`
  is now `sources: str, history: str, question: str -> answer: Answer`. Kept as its own field
  (rather than string-concatenated into the question) so `AnswerQuestion.instructions` can draw a
  sharp line: `history` is for understanding what a follow-up question refers to, never a source
  of facts or citations — `citations.py` verifies every citation fresh against the current
  `sources` blob every turn regardless of what an earlier turn cited (invariant 11). A past answer
  being wrong, or a source having been removed since, must not carry forward silently.

  **No summarization or truncation of growing history yet.** `notebook.history_text` renders every
  prior turn verbatim, oldest first. An earlier round of design discussion flagged unbounded
  history growth as something that would compound with a since-abandoned subprocess-per-turn
  cold-start cost; with execution still in-process (see above), that compounding doesn't currently
  apply, so truncation/summarization is deferred until real usage shows the corpus-blob size cap
  (invariant 8) or per-turn latency actually motivates it — not implemented preemptively.

  **Extending a notebook dedupes by origin, and ids are never reassigned.** `cli._ingest_new` skips
  any `--source` value already present as an existing source's `origin`, and numbers genuinely new
  sources starting from `len(notebook.sources) + 1` (invariant 12) — re-passing the same source on
  a later turn is a no-op, and a source a saved `ChatTurn.answer` already cites can never have its
  id silently repointed at different text.

  **A notebook id is sanitized before it becomes a filename** (`notebook.slug`, invariant 10) — the
  same `[A-Za-z0-9._-]`-then-length-cap treatment ctx-distillery's `cli._slug` gives a run id,
  since `--notebook` is user input that becomes a path component.

  **`notebook.save_notebook` writes atomically** (temp file in the same directory, `fsync`, then
  `os.replace` onto the real path) rather than writing the real path directly. An independent
  review found the direct-write version left a truncated, unparseable JSON file behind if the
  process was interrupted mid-write (Ctrl+C, crash, power loss), with no recovery but deleting the
  whole conversation and starting over; verified by simulating the interruption (`os.fsync`
  monkeypatched to raise mid-save) and confirming the original file is untouched afterward.
  `cli._cmd_ask` also now catches a `pydantic.ValidationError` from `load_notebook` — a hand-edited
  or otherwise externally-corrupted file — and reports it clearly instead of an uncaught traceback.

  **`_ingest_new`'s dedupe also covers repeats WITHIN one invocation**, not just across separate
  `ask` calls against the same notebook. The first version only checked the caller's static
  `skip_origins` set, so `--source a.txt --source a.txt` in a single command ingested `a.txt`
  twice under two different ids — a `seen` set that grows as the loop runs fixes it. A second,
  related gap the same review found — two different path SPELLINGS of the same file (e.g. a
  relative vs. an absolute path) aren't recognized as the same origin, since `origin` is compared
  as a plain string with no `Path.resolve()` normalization — is NOT fixed in this slice; it's a
  data-duplication/context-dilution issue, not a correctness or security one, and is deferred.

  **`AnswerQuestion`'s sandbox pin is now a numbered invariant** (9), not just a `config.py`
  comment — found while renumbering AGENTS.md for this slice's additions: the pin was already
  enforced in code and tested, just never promoted to the Invariants list the way the sibling
  projects promote theirs.

- **Third slice: a Notebook Guide** — `rlm-notebook guide {summary,faq,timeline,insight}`
  generates a whole-corpus artifact (`guide.py`: `GenerateSummary`/`GenerateFAQ`/
  `GenerateTimeline`/`GenerateKeyInsight`), the same citation-grounded `RLMTask` pattern as
  `AnswerQuestion` — one input field (`sources`, no `question`/`history`) and one output field per
  task. Guide artifacts share `ask`'s citation verification (`citations.py`) unmodified — it was
  already generic over any `list[Citation]` + `Corpus`, so nothing needed to change there.

  **Citation-marker and validate-before-submit instructions are now factored into
  `instructions.py`** (`CITATION_RULES`, `validate_before_submit_rule`), shared by `AnswerQuestion`
  and all four Guide tasks (invariant 13) — five near-identical copies of the same paragraph was a
  drift hazard (a wording fix landing on one task and not the others), not a stylistic preference.
  Invariant 4 (citation-marker copying) is reworded to say it applies to every grounded task, not
  just `AnswerQuestion`, since it's now literally the same instruction text. The task-specific
  "ground only in sources" OPENING sentence each task supplies is deliberately NOT unified into
  `instructions.py` — `AnswerQuestion`'s is worded for a missing *answer*, the Guide tasks'
  (`guide.py:_grounded_instructions`, shared across just those four) for an unsupported *claim* —
  and an earlier draft of this entry (and of `guide.py`'s docstring) overstated that this opening
  was shared too, which it never was; corrected by the same independent review that found the two
  gaps below.

  **`guide` printed nothing at all for a legitimately empty FAQ/timeline.** `GenerateFAQ`/
  `GenerateTimeline`'s instructions explicitly allow "the sources don't support any items" as an
  honest answer (schema.py's Timeline/FAQ default to an empty list) — but `cli._cmd_guide`'s
  per-item loop then printed literally nothing, so a source with a legitimately empty timeline
  looked identical to a hung or broken command. Fixed with an explicit "(no FAQ items — ...)" /
  "(no timeline — ...)" message when the list comes back empty.

  **A citation-less answer printed a stray trailing blank line.** Refactoring `_cmd_ask`'s output
  around the new shared `_print_citations` helper left every call site printing its own
  unconditional blank line before calling it, so `"...text\n"` became `"...text\n\n"` even when
  there were no citations to print. Fixed by moving the leading blank line INTO
  `_print_citations` itself, printed only when there's something to print after it.

  **`cli._prepare` factors out the load-or-create-notebook / ingest-new-sources / print-flags setup
  `ask` and `guide` both need**, returning `(notebook, corpus)` or `None` (an error already
  printed). `_cmd_ask` and `_cmd_guide` differ only in which RLMTask they run afterward and how
  they print the result — a second command was the forcing function to notice this setup wasn't
  `ask`-specific.

  **Timeline events use free-text `when`, not a parsed date** — sources rarely give a full
  calendar date for every event, and `GenerateTimeline`'s instructions explicitly allow (and
  `Timeline.events`'s default empty list explicitly supports) "the sources describe no sequence of
  events at all" as a valid, non-fabricated answer rather than forcing a timeline into existence.

  **Guide artifacts are not cached onto the notebook or made citable as sources for later `ask`
  turns.** An early design discussion floated treating a generated summary/FAQ/timeline as a
  "generated" source type other answers could cite. Deferred: it adds a second citable-content
  shape (generated vs. ingested) that `citations.py`/`corpus.py` don't yet distinguish, and no
  concrete need for it has shown up yet. Each `guide` call regenerates from the current `sources`
  blob fresh every time.

- **Fourth slice: an Audio Overview** — `rlm-notebook audio` generates a two-host podcast script
  (`audio.py`'s `GeneratePodcastScript`, same citation-grounded `RLMTask` pattern, sharing
  `instructions.py`'s citation rules) and synthesizes it to an MP3 (`tts.py`). The transcript
  prints first, with citations, regardless of whether synthesis succeeds afterward — a TTS
  failure (network, misconfigured voice) doesn't lose the script, since it was already generated
  and printed before synthesis is even attempted.

  **Script generation and audio synthesis are two fully separate steps with no RLM-side coupling**
  (invariant 14): `GeneratePodcastScript` doesn't import `tts.py` at all, and the TTS provider is
  never a tool the model can call — the same "the model's job is done before this step runs"
  reasoning invariants 1/3 already establish for ingestion/fetching. `tts.py` only ever receives
  an already-generated, already-schema-validated `PodcastScript`.

  **Default TTS provider is `edge-tts` — free, no API key, no paid account** (invariant 15),
  matching the OCR default's "ship a working default" reasoning (invariant 7) rather than leaving
  `rlm-notebook audio` usable only after separately acquiring TTS credentials. Verified against
  the REAL edge-tts network service (not just the offline-injected-fake unit tests) before
  landing this: a two-utterance script produced a 52KB MP3 starting with a valid MPEG frame sync
  header. The known-provider list lives in exactly one place, `tts.py`'s `_PROVIDERS` — unlike
  `RN_OCR_PROVIDER`, `config.py` does not keep a second copy to validate against, so the two lists
  can't drift apart the way a duplicated list eventually does.

  **`EdgeTTSProvider` synthesizes per-utterance and concatenates raw MP3 bytes, no re-encoding**
  (invariant 17) — `edge-tts` is one-voice-per-call, and re-encoding a proper gapless multi-speaker
  file would need `pydub` + a system `ffmpeg` binary (not pip-installable) for what's ultimately a
  playback-smoothness cosmetic improvement. Documented, deliberate tradeoff, not an oversight.

  **The cast is a fixed two hosts, `host_a`/`host_b`** (invariant 18) — not a per-episode
  configurable roster. Keeps `Utterance.speaker` a closed enum and the voice-selection surface
  (`RN_TTS_VOICE_HOST_A`/`_B`) two fixed variables rather than an open-ended cast config; a
  deliberate MVP scope cut matching how NotebookLM's own Audio Overview also ships a fixed
  two-host format.

  **An empty `PodcastScript` is a legitimate answer, and `cli._cmd_audio` says so explicitly**
  rather than printing nothing — the identical fix (and the identical bug shape) `guide`'s empty
  FAQ/timeline needed; applied proactively here rather than waiting for a second independent
  review to find the same class of bug again.

  **Found and fixed two invariant cross-references that had gone stale across earlier
  renumberings and survived three prior independent reviews: `pyproject.toml`'s inline comments
  (citing invariant 1/6 where the actual invariants were 3/7) and `.env.example`'s (citing
  invariant 7/6 where they were 8/7, and still describing OCR as behind an `ocr` extra that no
  longer exists).** Earlier renumbering passes grepped `.py`/`.md` files only — `.toml`/`.env.example`
  were never included, so these survived undetected. Worth remembering next time invariants are
  renumbered: grep needs `--include` for every text format the repo actually has comments in, not
  just the two most common ones.

  **A fourth independent review reproduced two real, previously-uncaught crashes and fixed both**
  (invariant 19): (1) `cli._cmd_audio` called `get_tts_provider(config.tts_provider)` AFTER
  `GeneratePodcastScript().run(...)`, so a mistyped `RN_TTS_PROVIDER` only surfaced as an uncaught
  `TTSError` once a real model call had already run and the transcript had already printed —
  reordered so the provider is resolved (and its error handled) first. (2)
  `EdgeTTSProvider.synthesize`'s `out_path.write_bytes(...)` sat outside its own try/except, so a
  `--out` path whose parent directory doesn't exist raised an uncaught `OSError` AFTER a real
  network synthesis call had already succeeded and been spent — reproduced against the real
  edge-tts service (not just the offline fake) both before and after the fix. Also added a spy
  test asserting `_cmd_audio` passes `config.tts_provider` (not some other, wrongly-named config
  field) to `get_tts_provider` — every prior audio test had monkeypatched that function wholesale
  and would have passed even if the wrong field were wired in. Documented (not fixed, low
  priority) that `EdgeTTSProvider.synthesize`'s internal `asyncio.run()` would raise if ever called
  from inside an already-running event loop — harmless for today's synchronous CLI, a real
  constraint for the planned API/UI slice to keep in mind if it calls this directly. Added a
  tripwire test pinning that `cli._SPEAKER_LABELS` covers every `schema.Speaker` value, since
  nothing in this project's CI (ruff + pytest, no type checker) would otherwise catch the two
  drifting apart.

- **Fifth slice: an HTTP API** (`api.py`, the `api` extra: `uv sync --extra api`) —
  `POST/GET /notebooks/{id}`, `POST /notebooks/{id}/ask`, `POST /notebooks/{id}/guide/{kind}`,
  `POST /notebooks/{id}/cancel`. This is the first place a run is isolated in its own subprocess
  rather than executed in-process; `cli.py` is completely unaffected and unchanged in behavior.

  **The subprocess-per-run execution model an earlier design round sketched and then deferred is
  now implemented**: `worker.py` is the subprocess entrypoint (resolves an RLMTask by dotted
  `module:ClassName`, runs it, records a full trace, prints exactly one JSON line as its result);
  `runner.py` is the host-side launcher (`start_new_session=True` so the worker is its own process
  group leader, `killpg` on cancel/timeout so a stuck Deno grandchild dies with it rather than
  becoming an orphan). Verified with a real test that spawns an actual grandchild subprocess and
  confirms it dies on cancellation, not just the worker's own PID (invariant 22) — this was the
  exact failure mode an earlier design round worried an over-eager `process.kill()` would miss.

  **`api.py` never imports `dspy`/`rlm_harness` itself** (invariant 21) — only `worker.py`, inside the
  subprocess, does. A crash deep in the model stack takes down a worker subprocess, never the API
  server process.

  **Extracted `ingest.py` and two new `notebook.py` functions (`load_or_create`,
  `extend_with_sources`) out of `cli.py`**, so `api.py` doesn't have to import from `cli.py` (or
  vice versa) to reuse the identical "get me a notebook, ingest new sources into it" step
  (invariant 20). `cli._prepare` is now a thin argparse-`Namespace`-shaped wrapper around the same
  shared functions `api.py` calls directly. Existing `_is_url`/`_ingest_one`/`_ingest_new` tests
  moved to `tests/test_ingest.py` unchanged in substance, just relocated with the code.

  **`api._config()` converts `NotebookConfig.from_env()`'s `SystemExit` into an HTTP 500** rather
  than letting it escape a request handler (invariant 24) — `cli.py` legitimately lets the same
  `SystemExit` exit the process, which is wrong for a server. Verified against a REAL running
  server with `curl` (not just the mocked test suite): an unset `RN_MAIN_MODEL` now returns a
  clean 500 with `cli.py`'s own error message, not a broken connection or a raw traceback. The
  rest of the API was also smoke-tested end to end against a real running server this way —
  `add_sources` (including that re-adding the same source is a no-op, not a duplicate),
  `get_notebook`, 404s on a missing notebook, and 404 on `cancel` with no in-flight run.

  **`_ACTIVE_RUNS` is single-process, in-memory, keyed by notebook id** (invariant 23) — a known,
  documented limitation (no multi-worker `uvicorn` deployment story yet), not a silent gap:
  running more than one `uvicorn` worker would split this dict across processes and `cancel` would
  only reach whichever worker happens to hold a given notebook's in-flight run.

  **Deliberately NOT in this slice** (deferred, not forgotten): an `/audio` endpoint (Audio
  Overview synthesis is slower/heavier than `ask`/`guide` and deserved its own wiring rather than
  being rushed in here), SSE/progress streaming (a request currently blocks until its subprocess
  finishes or `RN_RUN_TIMEOUT_SECONDS` — default 300s, a NEW config field distinct from
  `RN_MAX_ITERATIONS`/`RN_MAX_LLM_CALLS`, which bound loop steps, not wall-clock time — elapses),
  and any browser UI at all.

- **An independent review of `feat/api` found and reproduced two real security/robustness issues
  before merging, both fixed:**

  **`add_sources` was an unauthenticated arbitrary-file-read vector (invariants 25, 26).**
  `ingest.ingest_one` treats any non-URL string as a local file path with no allowlist — correct
  for `cli.py`, where the operator already trusts their own machine, and a vulnerability the moment
  the exact same function sat behind an unauthenticated HTTP endpoint. The review reproduced the
  full chain: `POST {"sources": ["/etc/passwd"]}` read the file, and a mocked `ask` echoed its
  contents back through a citation that passed coordinate verification. Fixed by rejecting any
  non-URL value in `add_sources` before it reaches ingestion. This also surfaced that the API has
  NO authentication at all (invariant 25) — now stated explicitly in `api.py`'s module docstring
  and README, not left implicit.

  **Four id-taking endpoints crashed with a raw 500 on a notebook id that reduces to an empty
  slug** (invariant 27) — e.g. `GET /notebooks/!!!`. `_load_notebook_or_404`/`add_sources` only
  caught `pydantic.ValidationError` (a corrupted file), not the `ValueError` `notebook.notebook_path`
  raises for an empty slug; reproduced on `GET`, `sources`, `ask`, and `guide/{kind}` with nothing
  more exotic than a notebook id made of punctuation. Fixed by catching `ValueError` too (→ 400).
  The review also checked route-level path-traversal payloads (`../../../tmp/evil`) and confirmed
  they never reach this code at all — Starlette's path converter refuses a literal `/` inside one
  `{notebook_id}` segment, so those 404 at the routing layer first; a real finding, but not a bug.

  **Verified the `_ACTIVE_RUNS` single-slot-per-notebook-id design is a capacity limitation, not a
  race**, with an `asyncio`-interleaved test: the `finally` block's `is run` identity check
  correctly lets only the request that OWNS an entry clear it, even when a second concurrent
  request for the same notebook id has already overwritten the slot. Documented this more
  precisely (invariant 23) — the previous wording only mentioned the multi-worker-process
  limitation, not this same-process one.

  **Added a tripwire test for `cli._GUIDE_TASKS`/`api._GUIDE_TASKS` staying in sync** (invariant
  28) — the same class of gap the PREVIOUS slice's own `_SPEAKER_LABELS` drift was found to have,
  applied proactively here instead of waiting for a fourth review to find the fourth instance of
  the same lesson.

- **Sixth slice: a web UI (`rlm_notebook/web/`), Phase 1 of a 3-phase blueprint** — Web shell +
  Sources + Chat. Gives the HTTP API added in the previous slice a real end-user product surface;
  before this slice it was only usable via `curl`/tests. Two small, additive API changes support
  it: `GET /notebooks` (a listing endpoint for the notebook switcher) and `GET /notebooks/{id}` now
  returning full turn history instead of just a count, so a re-opened notebook's past conversation
  renders immediately (citations re-verified fresh against the current corpus on every read, same
  discipline as a brand-new answer — invariant 11).

  **Deliberately NOT another instance of the sibling projects' replay-only trace console.**
  `ctx-distillery`/`cve-reverser`/`diff-sentry`/`toolscout` each ship a `studio/` that's a
  single-verdict security/review console; this project's persistent, multi-notebook, multi-turn
  knowledge workspace is structurally different on purpose (invariant 29). An original visual
  identity — two full first-class OKLCH themes, Paper (light, default) and Study (dark), sharing
  one hue family for brand continuity rather than the siblings' cool blue-slate security-console
  dark — and a citation-as-highlighter-stroke signature interaction, not a footnote number.

  **Went through a pre-implementation independent design audit before any code was written**
  (the web-UI blueprint, gitignored, same convention as `docs/research/`). The audit
  found 4 blockers: the originally planned SSE reasoning-trace fusion was unbuildable as scoped (no
  `run_id` ever reaches a client mid-run from `ask`/`guide`'s synchronous contract, and
  citation-to-trace-turn linking had no data model at all) — pulled from this round entirely rather
  than patched under pressure, and held for its own future design pass; a top-level `web/` directory
  would have silently vanished from an installed wheel (no `pyproject.toml` packaging entry) — fixed
  by moving assets under `rlm_notebook/web/`, verified by actually building a wheel and confirming
  the files are inside it; `GET /notebooks`' original design cited a `NotebookConfig` field that
  doesn't exist — fixed to read the same bare `notebook.DEFAULT_NOTEBOOKS_DIR` constant every other
  notebook operation already uses; and two real, COMPUTED (not eyeballed) WCAG contrast failures in
  the original palette (Paper's `--text-faint` measured 3.08:1 against `--surface-3`, Study's
  2.97:1 — both below the 4.5:1 AA floor for normal text) plus a third the audit's own checklist
  didn't anticipate (Study's citation highlight wash was self-contrast ≈1.0 against an elevated
  panel, i.e. invisible) — all three fixed with recomputed, re-verified OKLCH values, and the
  citation highlight gained a border backstop so its perceptibility never depends on wash luminance
  alone.

  **A second, independent completion check after implementation** (the project's standard
  pre-merge gate) re-verified every one of those fixes was actually real in the shipped code, not
  just described in a commit message — rebuilt the wheel and confirmed the static assets were
  inside it, independently recomputed the WCAG contrast ratios from the real `style.css` values,
  and ran the real test suite and a live `curl` smoke test against a running server. It also caught
  that `app.js`'s citation renderer built an HTML attribute via string interpolation
  (`<span title="...">`), which a `"` character inside a model-echoed `source_id`/`locator` could
  have broken out of under a prompt-injected source (invariant 6) — found and fixed (rebuilt with
  `createElement`/`textContent`/`element.title` throughout, never `innerHTML`) before the audit
  even ran, then independently confirmed landed cleanly.

  **Deliberately NOT in this slice**: Phase 2 (Guide tabs + podcast player, needs a new `/audio`
  endpoint) and Phase 3 (the live reasoning-trace ticker, held back per the audit above) are
  separate, not-yet-scheduled slices. Paste-text and file-upload source ingestion in the UI are
  visible tabs that say plainly they aren't wired to the API yet, rather than silently failing or
  pretending to work — the API itself still only accepts http(s) URLs (invariant 26).

- **Seventh slice: web UI Phase 2 — Studio panel (Guide tabs + podcast player)**. Adds
  `POST /notebooks/{id}/audio` and wires the Studio panel Phase 1 left as a placeholder.

  **`/audio` is two host-side steps, not one, and deliberately doesn't touch `worker.py`/
  `runner.py` at all.** `GeneratePodcastScript` runs in the exact same isolated subprocess `ask`/
  `guide` already use — the only step that touches `dspy`/`rlm_harness`, and the only one cancellable
  via `POST .../cancel`. TTS synthesis (`tts.py`) then runs AFTER that subprocess returns,
  IN-PROCESS inside `api.py` itself: `tts.py` imports neither `dspy` nor `rlm_harness`, so this doesn't
  reopen invariant 21, and it's the same precedent `api.py` already sets by importing the Guide/
  `AnswerQuestion` RLMTask classes at module load purely for introspection, never calling `.arun()`
  on them itself.

  **`EdgeTTSProvider.synthesize()`'s own previously-flagged residual risk finally landed for real,
  and got its predicted fix.** Its docstring already said a future async caller would need to
  route around its internal `asyncio.run()` call rather than changing `synthesize()` itself — this
  slice is that caller, dispatching through `asyncio.to_thread` (a fresh OS thread has no event
  loop of its own, so `asyncio.run()` inside it never collides with the request handler's own
  running loop). `tts.py` is unmodified; `cli.py`'s existing synchronous call site is unaffected.

  **No audio is ever persisted past one request** — synthesis writes to a temp file, the bytes are
  read back and base64-encoded into the JSON response, and the temp file is deleted whether
  synthesis succeeded or failed. Deliberately no `GET .../audio/{run_id}.mp3`-style file-serving
  endpoint and no retention policy to get right, unlike the reasoning-trace files Phase 3 left
  unresolved.

  **Went through the same pre-implementation independent design audit Phase 1 established**
  (the web-UI blueprint's Phase 2 addendum) before any code was written. Found 2
  blockers, both fixed before implementation started: the ordering list omitted the notebook-load/
  corpus/blob-size steps every other endpoint performs first, which as originally written would
  have surfaced a 500 (bad `RN_TTS_PROVIDER`) ahead of a 404/413 whenever both conditions held,
  inverting `cli._cmd_audio`'s real precedence; and the temp-file cleanup plan only covered the
  success path, which would have leaked a `.mp3` per failed synthesis (`tts.py`'s `synthesize()`
  has two real `TTSError` raise sites that fire after the file already exists on disk). Two
  non-blocking fixes folded in too: the Guide-tab cache now invalidates on a source being added,
  not just on a notebook switch; and the podcast player's object-URL revocation order is now
  explicit (assign the new URL before revoking the old one, so a previous episode being played
  when "regenerate" is clicked is never yanked out from under a live `<audio>` element).

  **Studio panel**: four Guide tabs (`Summary`/`FAQ`/`Timeline`/`Insight`), each fetched only on
  first activation or an explicit `↻ Regenerate` click — never automatically, including on
  notebook open, since a guide run is a real RLM loop and auto-fetching on open would burn a model
  call for nothing (a mistake caught and fixed during this slice's own implementation, before it
  ever shipped, not by the audit). Results are cached client-side per notebook and invalidated on a
  source being added. A `Generate podcast` button below produces a `Blob`/`ObjectURL`-backed
  `<audio controls>` player (not a `data:` URI, which would keep a multi-MB episode's whole
  base64 string live in a DOM attribute) plus a transcript, reusing Phase 1's citation-highlighter
  rendering verbatim.

  **Known, accepted limitation, stated explicitly (invariant 29)**: only `/audio`'s script-
  generation half is cancellable — by the time synthesis begins, `_run_isolated`'s `finally` has
  already cleared this notebook's `_ACTIVE_RUNS` entry, so a stuck synthesis call blocks its
  request with no `killpg`-equivalent to reach it. Not a regression (`cli._cmd_audio` has no
  cancellation story for this phase either), but new: an API request's total latency can now
  include a real network TTS call serialized after an RLM run.

  **Deliberately NOT in this slice**: Phase 3 (the live reasoning-trace ticker) remains held back,
  same reasons as before. The full source-text viewer (and Literata, the typeface reserved for it)
  is still unbuilt.

- **Eighth slice: web UI Phase 3 — reasoning-trace fusion (live ticker + citation-turn linking)**.
  The blueprint's Phase 3 addendum was redesigned from scratch (its own two audit rounds, before
  any code was written) to resolve the two blockers the ORIGINAL Phase 3 design was pulled over:
  no `run_id` ever reached a client mid-run, and citation-to-trace-turn linking had no data model.

  **The client picks the run id, never the server** — `ask`/`guide`/`audio` all gain an optional
  `run_id` body field (a shared `RunOptions` model); when given, it's sanitized through the SAME
  whitelist `notebook.slug()` already uses and always prefixed with `notebook_id`. This is the
  toolscout-studio pattern (a previewed run id the solve call sends explicitly), not a fire-and-poll
  rewrite of endpoints Phase 1/2 already shipped and audited — fully additive, byte-for-byte
  unchanged behavior for any caller that doesn't supply one.

  **Real concurrency bugs found and fixed before implementation, not discovered as runtime bugs.**
  The redesign's own first pre-implementation audit found 3 blockers, all clustered around one
  blind spot: same-notebook concurrency was never stress-tested against a client-controlled run id.
  (1) Two concurrent requests deriving the same run id would have let two independent worker
  subprocesses append interleaved, duplicate-`step_id` events to one trace file —
  `TraceRecorder`'s own lock is process-local and provides zero cross-process serialization. Fixed
  with a hard uniqueness gate: `_run_isolated` now exclusively creates the trace file
  (`O_CREAT|O_EXCL`) before spawning anything, mapping a collision to 409. (2) The originally
  planned cancelled-run liveness check reused `_ACTIVE_RUNS` (notebook-id-keyed, one slot per
  invariant 23), which would misfire the moment a second concurrent request on the same notebook
  overwrote the first's entry — fixed with a NEW, run-id-keyed `_RUN_PROCESSES` map, decoupled
  entirely from `_ACTIVE_RUNS`'s single-slot semantics. (3) The citation-lookup search's field list
  was verified wrong against `rlm_harness.sub_lm`'s real `sub_call` payload shape (`input`/`raw`/
  `processed`/etc, not `reasoning`/`code`/`output`) — fixed by searching a trace event's ENTIRE
  serialized payload rather than a hardcoded field list. A second, targeted audit round then found
  2 more real gaps in the collision-gate fix itself (a directory-existence race with a fresh
  checkout's very first run, and a missing cleanup path that would have permanently false-409'd a
  retry after a failed subprocess spawn) — both fixed before implementation started.

  **`GET /notebooks/{id}/runs/{run_id}/stream`** — one SSE endpoint serving both a live tail (the
  run is still in progress) and a replay (the run already finished) from the same polling loop,
  verified safe against `rlm_harness/trace.py`'s actual write behavior: `TraceRecorder.record()` writes
  one complete, flushed JSON line per event under its own lock, so a reader that buffers any
  trailing partial line can never see a torn or interleaved line. Synthesizes a terminal event for
  a `killpg`-cancelled run whose `TraceRecorder.__exit__` never got to write `run_end`, the same fix
  `ctx-distillery-studio` already documents for the identical failure mode.

  **`GET /notebooks/{id}/runs/{run_id}/citation-turn`** — a small, separate lookup (not a reuse of
  the live stream, which would ship a whole trace to the client just to search it) for "which trace
  turn shows the model reading this citation's source span." A heuristic, stated as one: finding
  the marker proves the model's REPL saw it, never that this occurrence is what the model relied
  on — the same "coordinate, not faithfulness" limit invariant 5 already states for citation
  verification generally. `schema.ChatTurn.run_id` (new, optional, backward-compatible) is the ONE
  schema change needed — Guide/Audio results still aren't persisted onto a notebook at all, so
  their citation links only need to work within the current browser session, which the client's
  own in-memory run id already satisfies with no server round-trip or schema change.

  **Post-merge follow-up**: a code-vs-docs consistency check (dispatched separately from this
  slice's own implementation/completion checks) found `stream_run` was missing the same
  `run_id`-belongs-to-`notebook_id` check `citation_turn` already had, so a mismatched
  `notebook_id` in the URL could still stream a trace belonging to a different notebook. Fixed in
  a small follow-up commit; both endpoints now apply the check consistently.

  **Frontend**: every `ask`/Guide-tab/podcast-generate call opens a live ticker alongside the
  actual request, replacing static "Thinking…"/"Generating…" copy with live-updating copy in the
  SAME pending slot — deliberately not a new UI element, and deliberately a SECONDARY layer: losing
  the ticker (a dropped SSE connection) never blocks or alters the request's own result. Every
  citation with a known run id becomes clickable, filling one shared detail slot per answer with
  the matching trace turn. The Phase 2 Guide-tab cache's value shape widened to `{result, runId}`
  (an earlier draft only cached the result, which would have lost the run id the moment a user
  switched tabs and back — found and fixed during the redesign, before implementation).

  **Known, stated limitations, not solved by this phase**: no trace-file retention policy exists
  anywhere in this project — a citation's "view reasoning" link is only as durable as a file
  nobody has committed to keeping (a missing trace degrades that ONE affordance, never the rest of
  the page); a `sub_call` event's `input` field is truncated to 4000 characters upstream
  (`rlm_harness.sub_lm`), a real source of false negatives in the citation-turn search. The trace
  stream and citation-turn endpoints inherit invariant 25's no-auth posture as a materially
  different, sharper exposure than every other endpoint (they can surface full ingested source
  text, not just metadata/prose) — stated explicitly in AGENTS.md, not left implicit.

- **Ninth slice: file upload + paste-text ingestion, wiring up the Sources panel's previously-inert
  "File" and "Paste text" tabs.** Prompted by a Gemini-Notebook feature-parity assessment that
  named this the single highest-priority gap: a browser user dragging a PDF into the Sources panel
  used to hit an `alert()` and nothing happened — NotebookLM's single most common operation.

  **`POST /notebooks/{id}/sources/upload`** (new) and `add_sources`'s new `texts` field are a
  genuinely different, safe mechanism alongside invariant 26's local-path ban, never a way around
  it — the server only ever receives opaque bytes/text the caller already had, never a path it
  reads from its own filesystem. `ingest.ingest_uploaded_file` dispatches on the claimed filename's
  suffix (`.pdf`/`.txt`/`.md` only, anything else a clear 422) and reuses the two parsers that
  already existed unchanged; `ingest.ingest_pasted_text` gives pasted text a readable-snippet-plus-
  content-hash origin (a bare hash was found, during design, to be a real UX regression — the
  Sources list renders `origin` verbatim as its only label).

  **A real, verified-before-landing security fix**: the upload size cap (`RN_MAX_UPLOAD_BYTES`,
  default 50MB) doesn't work the way the first draft assumed. Declaring the endpoint the natural
  FastAPI way (`file: UploadFile = File(...)`) makes FastAPI itself parse the entire multipart body
  BEFORE the handler (or any in-handler check) ever runs, for ANY route shaped that way, regardless
  of `Content-Length` — confirmed live against the installed version (a 5MB body was already fully
  spooled to disk the instant a test handler started, with an accurate `Content-Length` header,
  not just in a chunked-encoding edge case). Starlette's own `max_part_size` never applies to file
  parts either. Fixed by taking `request: Request` directly instead — `Content-Length` is checked
  BEFORE ever calling `request.form()`, so an oversized declared size is rejected with the body
  never read off the socket at all; a missing `Content-Length` (chunked encoding) is refused
  outright (411), not accepted with a disclosed gap. Verified live (a standalone test app, a 5MB
  POST against a 1000-byte cap) before this was believed rather than just reasoned about.

  **Deliberately NOT gated behind `NotebookConfig.from_env()`**: `config.max_upload_bytes()` is a
  standalone function — gating it on a full model config (which raises `SystemExit` whenever
  `RN_MAIN_MODEL` is unset) would make uploading a source fail with "server misconfigured" for a
  reason that has nothing to do with what the caller is trying to do. Caught while designing this,
  not left for an audit to find — `add_sources` already established this same discipline for the
  URL-based path.

  **Deliberately NOT in this slice**: Word/Slides/Docs native-format parsing (would need new parser
  dependencies — this only wires up the two parsers that already existed), multi-file batch upload,
  YouTube/audio source ingestion, and a source-text viewer (still open gaps from the same
  feature-parity assessment, not attempted here).

- **Tenth slice: a source-text viewer — NotebookLM's most basic closed loop (click a citation, see
  the highlighted original passage).** The second of the three remaining gaps from the same
  Gemini-Notebook feature-parity assessment; the first (file upload) shipped the previous slice.

  **`GET /notebooks/{id}/sources/{source_id}`** (new) returns a source's full text, every block —
  `{id, kind, origin, flags, blocks: [{locator, text}]}`. Reuses `corpus.Corpus.get(source_id)`,
  the same lookup `citations.py` already performs on every `ask`/`guide` request, confirmed cheap
  before reuse rather than assumed. A materially different exposure than most other endpoints here
  (invariant 31) — before this, no caller could read more of a source than a citation's short
  `quote`.

  **The web UI's citation-list row is now clickable, opening a source-viewer modal** — the first
  stacking-context component in `rlm_notebook/web/` (`.modal-overlay`/`.modal`, closing via `✕`/
  backdrop/`Esc`, the same family convention the sibling projects' own `studio/`s already use for
  their trace-replay drawers). The matching block is highlighted (reusing the existing `.citation`
  highlighter-stroke styling) and scrolled into view. The pre-existing reasoning-trace view
  (`showCitationTurn`, Phase 3) is demoted to a secondary `⌁ trace` icon inside the same row rather
  than removed — the two click targets coexist, the icon calling `event.stopPropagation()` so
  clicking it never also opens the source viewer.

  **Two staleness-guard bugs, one new and one pre-existing, both fixed in this slice.** The
  pre-implementation audit required a guard against a slower first fetch overwriting a faster
  second one's render for the brand-new source-viewer fetch (fixed with a module-level
  `AbortController`), then found the SAME class of defect already present, unfixed, in the
  pre-existing `showCitationTurn` from Phase 3 — retrofit with an equivalent monotonic-token guard
  there (`detailArea._requestToken`), chosen over `AbortController` for that one site since it's a
  plain GET with no browser-level cleanup worth invoking.

  **A pre-existing concurrency bug found, and explicitly NOT fixed here**: `notebook.py`'s
  single-writer assumption doesn't hold once `api.py` serves concurrent requests — two concurrent
  `POST /notebooks/{id}/sources` calls on the same notebook can silently discard one via
  `save_notebook`'s non-merging atomic replace (invariant 31's closing paragraph). Read-only, so
  not a blocker for this slice; a per-notebook lock (or a merging write) is a separate follow-up.

  **Deliberately NOT in this slice**: source editing, next/prev-citation navigation, caching across
  viewer opens (each open re-fetches), and pagination for very large sources. YouTube/audio source
  ingestion and a Notes research loop remain the last two open gaps from the same feature-parity
  assessment.

- **Eleventh slice: Notes — the research-loop closing feature.** The third of the four gaps named
  by the same Gemini-Notebook feature-parity assessment; only YouTube/audio source ingestion
  remains after this. NotebookLM's own differentiating loop — read a source, write a note (or save
  an AI answer as one), promote it into a full source, keep going — had no concept at all in this
  project before this slice: `schema.Notebook` had only `sources` and `turns`.

  **`schema.Note`/`Notebook.notes`** (new): a note is freeform, uncited text — grounded and citable
  only once PROMOTED into a real `Source`, never before (invariant 32). Backward-compatible via
  pydantic's default, the same precedent `ChatTurn.run_id` already established.

  **`notebook.add_note`/`delete_note`/`promote_note`** (new): `promote_note` reuses
  `ingest.ingest_pasted_text` UNCHANGED — the exact function pasted-text sources already go
  through — so a promoted note gets the identical content-derived-origin, dedup, and
  injection-scan treatment any other pasted text already gets, rather than a parallel code path.
  Removes the note from `notes` regardless of outcome (a dedup hit against already-identical text
  returns `None` and appends nothing new) — promotion is a completed action either way.

  **Three new API endpoints, one extended response**: `POST /notebooks/{id}/notes` (uses
  `load_or_create`, like `add_sources`), `DELETE /notebooks/{id}/notes/{note_id}` (this API's FIRST
  `DELETE` route), `POST /notebooks/{id}/notes/{note_id}/promote` — the latter two use
  `_load_notebook_or_404`, matching `ask`/`guide`'s existing-notebook-only precedent.
  `NotebookResponse` gains a `notes` field, so every endpoint that already returns a notebook gets
  it for free through the one shared `_notebook_response` conversion function.

  **Web UI**: a Notes section in the Studio panel (below Audio Overview), each note with a
  `→ Promote to source` and a `✕` delete button; a "+ Save as note" button on every Chat answer.

  **A real pre-implementation-audit catch, not found live afterward**: the original design would
  have put the "+ Save as note" button inside `renderAnswerWithCitations` — a function SIX
  different call sites share (Chat plus all four Guide kinds and the podcast transcript) — which
  would have leaked the button onto generated artifacts a user never curates into notes. Fixed
  before any code was written: the button lives in `renderTurn` (Chat's own call site) instead.

  **A real bug found by the independent post-implementation completion check, fixed before
  merge**: the original `n{len(notes)+1}` id scheme let two LIVE notes share one id the moment a
  non-last note was deleted (delete `n1` out of `[n1, n2]`, add a third — the old scheme reused
  `n2`, colliding with the note still alive under that id) — reproduced live, and confirmed to
  cause a real silent data loss: promoting one of a colliding pair discarded the other with no
  source ever created and no error raised. Fixed at the root with `_next_note_id` (derives the
  next id from the MAX id actually in use, not the count, so a new id can never collide with one
  still alive); `delete_note`/`promote_note` also now remove exactly the first matching note by
  index rather than filtering every id-equal match, as defense in depth on top of the id fix, not
  instead of it (invariant 32). An id can still be safely reused once NO live note holds it.

  **Deliberately NOT in this slice**: note editing (delete-and-recreate is the only revision path),
  rich-text/markdown notes, note-to-note linking or tagging, and retroactively re-citing past `ask`
  turns after a note they referenced gets promoted (a note was never a citable source before
  promotion, so there's nothing to retroactively fix). YouTube/audio source ingestion is the one
  remaining gap from the feature-parity assessment.

- **Twelfth slice: YouTube caption ingestion.** The last of the four gaps named by the same
  Gemini-Notebook feature-parity assessment. Pasting a YouTube URL used to silently mis-ingest as
  a generic web page (`parse_web` against YouTube's own HTML shell, which has no transcript text
  at all — the page loads captions via client-side JS, not server-rendered markup).

  **MVP scope, decided WITH the user, not guessed.** Two real technical forks existed: captions-
  only via `yt-dlp` vs. full audio-download-plus-transcription, and — had the latter been chosen —
  local Whisper vs. a cloud transcription API. The user picked captions-only: no video/audio
  download, no `ffmpeg`, no Whisper, no transcription API key. A video with neither official nor
  auto-generated captions is a clean ingestion-time error, not a silent partial ingestion; full
  audio transcription remains a separate, later, independently-mergeable follow-up.

  **A real ToS/legal caveat, disclosed and accepted, not glossed over**: YouTube's Terms of
  Service prohibit automated access outside its own interfaces; `yt-dlp` (new, but a CORE
  dependency — pure Python, no `ffmpeg` needed for this path, same "ship a working default"
  reasoning as OCR/TTS) operates in the same long-standing gray area every YouTube-downloading
  tool does. Fetching only captions is narrower/lower-risk than downloading media, but not
  risk-free — the risk is accepted by whoever deploys this project.

  **`parsers/youtube.py`** (new): `is_youtube_url` dispatches ahead of the existing generic
  `is_url` → `parse_web` fallback in `ingest.ingest_one`, so `cli.py`'s `--source` and `api.py`'s
  `POST /sources` both get this for free with no per-entry-point change. `parse_youtube` fetches a
  caption track via `yt-dlp` (`skip_download: True` — no video/audio ever touches disk), parses
  WebVTT into `(start, text)` cues, collapses auto-caption's "rolling karaoke" duplication, and
  chunks into `~120`-second blocks with a new `"ts:<mm:ss>"` locator prefix.

  **Three real bugs found and fixed against REAL caption data across two independent review
  rounds, not assumed correct from reasoning alone** (invariant 33 has the full account). A first
  design kept only each cue's last non-blank line, which WRONGLY dropped real content from
  genuine multi-line official dialogue cues — fixed (pre-implementation) by keying the extraction
  rule on whether a cue contains ANY `<...>` tag markup. An independent POST-implementation
  completion check then found that fix itself still under-collapses: a real auto-caption
  "building" cue advancing by exactly ONE new word often carries NO tag at all, so the
  tag-presence heuristic misclassified it and left a duplicated word pair in a live-fetched
  transcript. Fixed by replacing the whole classification approach with something simpler:
  flatten EVERY non-blank line into its own entry and leave all deduplication to plain adjacent-
  collapse — sidesteps the tag-presence question entirely, since a rolling-karaoke transition
  line always collides with something the preceding cue already emitted regardless of tags,
  while genuine multi-line dialogue lines never collide with anything. A separate, still-correct
  fix treats a whitespace-only line as part of a cue's OWN payload (not a separator), since real
  auto-caption VTT uses a single-space line for exactly that. All fixes re-verified live against a
  real public video's official AND auto-generated caption tracks, checking for adjacent duplicate
  words across the WHOLE reconstructed transcript, not just the hand-written test fixtures.

  **A real pre-implementation-audit catch**: `CaptionError` was first drafted as a bare
  `RuntimeError`; `cli._prepare`/`api.add_sources` both catch ingestion failures as
  `except (FetchError, ValueError, OSError)`, so a captionless video would have escaped as an
  unhandled 500/traceback instead of the clean error this slice promises. Fixed by making
  `CaptionError` a `ValueError` subclass — found and fixed before any code was written, verified
  live afterward with a dedicated test.

  **A separate, unrelated dependency gap surfaced (not caused) by adding `yt-dlp`**:
  `python-multipart` (needed by `POST /notebooks/{id}/sources/upload`'s multipart form parsing,
  invariant 30) had never been an explicit dependency — it arrived transitively, silently, until
  `yt-dlp` shifted dependency resolution enough that it stopped being pulled in and the upload
  tests broke with no code change of their own. Pinned explicitly in the `api` extra now.

  **Deliberately NOT in this slice**: any video/audio download (the user's explicit MVP decision),
  a captionless video, a non-YouTube video URL, or a directly-uploaded audio file (all out of
  scope); timestamp-precise single-cue citation granularity (the 120-second chunking window is a
  deliberate coarser grain, matching text/web's own single-locator precedent); playlist/channel
  ingestion. This closes out the four-gap Gemini-Notebook feature-parity assessment that started
  with file upload.

- **Thirteenth slice: replace `pymupdf`/`pymupdf4llm` — a real AGPL-vs-MIT license conflict, found
  and fixed, not a preemptive style choice.** `pymupdf`/`pymupdf4llm` are dual-licensed "GNU AGPL
  v3 OR Artifex Commercial License" (confirmed via `importlib.metadata` against the actually-
  installed distributions and the vendor's own file header) — no free non-AGPL option exists. A
  transitive `pymupdf4llm` dependency, `pymupdf-layout`, carried a SECOND, even stricter Artifex
  license (Polyform Noncommercial — bars commercial use outright, no source-disclosure escape
  valve at all). This project is `license = "MIT"` and ALSO ships an HTTP API meant to run as a
  network service (invariant 25) — AGPL-3.0's network-use clause obligates anyone running a
  covered program as a network service to offer the combined work's complete source, and nothing
  in `LICENSE`/`README.md`/`pyproject.toml` ever disclosed this. Found while auditing the
  project's overall dependency licensing after a direct user question; the user decided to
  replace the dependency rather than relicense to AGPL, gate PDF support behind an extra, or
  merely disclose the risk.

  **`pypdfium2`** (BSD-3-Clause/Apache-2.0, wraps Google's PDFium — the engine Chromium itself
  uses) replaces `pymupdf`/`pymupdf4llm` in `parsers/pdf.py`. Verified permissive down to every
  bundled native dependency (`freetype`/`zlib`/`libpng`/`libtiff`/`libjpeg_turbo`/`libopenjpeg`/
  `lcms`/`icu`/`abseil` — no AGPL/GPL anywhere in the tree, confirmed by listing the actual bundled
  license files, not trusting the top-level metadata field alone). `Pillow` was ALSO added as an
  explicit direct dependency — `pypdfium2` declares zero runtime dependencies of its own, and
  `.render(...).to_pil()` only worked before by luck via `rapidocr-onnxruntime`'s own transitive
  dependency, the exact same "worked by luck until resolution shifted" class already documented
  for `python-multipart` (invariant 30) — caught proactively this time, before it broke anything.

  **`parsers/_ocr.py`** (new): RapidOCR primary, Tesseract fallback, hand-implemented now that
  `pymupdf4llm`'s built-in OCR dispatch goes away with it. Deliberately simpler than
  `pymupdf4llm`'s former ML-based OCR-need classifier — a plain "extracted text below a small
  character threshold" check, which does NOT catch a GARBLED-but-present text layer the way the
  old ONNX classifier did. This project's own actual scanned-PDF case (a page with no text layer
  at all) is unaffected; a bad-character-ratio heuristic for the garbled case is a smaller, later,
  independently-mergeable follow-up if it ever turns out to matter — a disclosed tradeoff, not
  silently assumed equivalent (`docs/invariants/07-ocr-ships-enabled-by-default.md` has the full
  account).

  **`tests/_pdf_fixtures.py`** (new): builds test PDFs with `reportlab` (BSD), a `dev`-only
  dependency — never a runtime dependency of the shipped package. Replaces this project's former
  `fitz` (`pymupdf`) based fixture-building across THREE test files
  (`test_parsers_pdf.py`/`test_ingest.py`/`test_api.py`) — an independent pre-implementation audit
  found the first draft of this slice's design named only one of the three, before any code was
  written.

  **Also disclosed, not fixed here**: `edge-tts` (the default TTS provider) is LGPLv3 — lower
  risk (LGPL generally permits an unmodified dependency relationship from a permissively-licensed
  program without forcing that program under LGPL itself), but named in `README.md`'s new
  "Licensing" section rather than left undisclosed alongside everything else.

- **Fourteenth slice: durable notebook writes + trace retention.** Not a feature — the one known
  defect in this project that silently LOSES a user's data, fixed at the root, plus the retention
  policy `traces/` had never had. Chosen over the remaining feature backlog deliberately: shipping
  more features on top of a store that can silently drop writes compounds the risk.

  **The defect was reproduced live over real HTTP against a real `uvicorn` server BEFORE anything
  was designed, and it is materially worse than what invariant 31 had recorded.** That entry
  described a race between two concurrent `POST /sources` calls — millisecond-wide, needing two
  browser tabs or a load test to hit. The actual reproduction needed no concurrency trickery at
  all: ask a question, and while the model works (which is exactly when a person has time to do
  something else) add a source and save a note from the panels the web UI leaves fully enabled
  during a run — `app.js`'s `pending` state gates only the Chat composer. Both writes returned 200.
  Both were gone the moment the answer was saved. `api.ask` held its notebook snapshot across the
  WHOLE run (up to `RN_RUN_TIMEOUT_SECONDS`, 300s by default) and wrote it back whole;
  `add_sources`/`upload_source` held theirs across ingestion (network fetch, PDF+OCR, YouTube
  captions).

  **Two faults, and the fix needs both halves.** A stale snapshot (the handler mutates an object it
  read minutes ago) and interleaved critical sections. A lock ALONE would not have prevented the
  reproduction above, because the two writes never overlapped in the file-writing instant — which
  is why `notebook.mutate_notebook` re-loads the file from disk INSIDE the lock and applies a
  caller-supplied DELTA. Its closure never sees the caller's snapshot, so "write back the object I
  built earlier" is not expressible. Every mutating path became: expensive work unlocked against a
  snapshot → `mutate_notebook` with the delta. Critical sections are now bounded by a JSON load
  plus a JSON write. Full account in AGENTS.md invariant 34.

  **`extend_with_sources` was DELETED, not kept alongside its replacement pair** (`ingest_sources_for`
  + `append_sources`). Ingesting and appending in one breath is precisely what forces a caller to
  hold a snapshot across ingestion, so leaving it available would let a later caller silently
  reintroduce the bug. `save_notebook` now has exactly one caller in the whole package.

  **`fcntl.flock`, not `fcntl.lockf`, and both load-bearing properties verified with a probe rather
  than assumed**: `flock` locks attach to the open file description, so ONE mechanism serializes
  two threads of a `uvicorn` server as well as two processes (POSIX record locks are per-process —
  two threads would pass straight through each other), and it releases the GIL while blocked. The
  cross-process guarantee has its own test that spawns a REAL second process and times how long the
  parent blocks, the same discipline `test_runner.py`'s real-grandchild cancellation test already
  applies. POSIX-only, stated rather than papered over: without `fcntl` it degrades to a
  process-local `threading.Lock`.

  **Four real problems found by this slice's own pre-implementation audit, all fixed before any
  code was written.** (1) Building the prune's protected set inside a worker thread races the event
  loop's own mutation of `_RUN_PROCESSES` — `RuntimeError: dictionary changed size during
  iteration`, raised from a `finally` on an otherwise successful request; the snapshot is taken on
  the loop instead. (2) `ask` persisting with `create=False` would have thrown away an
  already-generated, already-paid-for answer if the notebook file vanished mid-run — the same
  "never discard work that already succeeded" reasoning invariant 19 applies to a TTS failure after
  a transcript exists. (3) Six handlers each hand-writing invariant 27's `ValueError`/
  `ValidationError`/`FileNotFoundError` mapping is exactly the drift that produced invariant 27 in
  the first place — one shared `_mutate_or_http` instead, which also validates the notebook id
  BEFORE the thread so `notebook_path`'s invalid-id `ValueError` can't be confused with
  `delete_note`'s same-typed "no such note" one (that confusion would report a missing note as
  "invalid notebook id"). (4) `cli._prepare` returning its own snapshot rather than the notebook
  `mutate_notebook` produced would have made every citation in a CLI run silently wrong —
  `append_sources` renumbers ids against the fresh notebook, so the model would cite `s2` for a
  source persisted as `s4`. The audit also checked whether the API's `ask` had the same exposure
  and found it does not (its snapshot holds only already-persisted sources, whose ids are never
  renumbered) — checked rather than assumed equivalent.

  **One intended behavior change**: `cli._prepare` now persists freshly ingested sources
  immediately, before the model runs, so a run that fails or is Ctrl+C'd partway no longer discards
  ingestion the user already paid for in OCR or network time. `_cmd_guide`/`_cmd_audio`'s trailing
  `save_notebook` calls existed only for that ingestion and are gone.

  **Trace retention (`traces.py`, new)** — `traces/{run_id}.jsonl` no longer accumulates forever.
  These are the one artifact here that can hold FULL ingested source text (the model echoes corpus
  spans into its REPL output while reading), in front of an API with no authentication. Sweeps by
  age (`RN_TRACE_RETENTION_DAYS`, default 7) and count (`RN_MAX_TRACE_FILES`, default 500), `0`
  disabling either, at startup and after every run. Two rules outrank both sweeps: an in-flight run
  id, and any file younger than a one-hour floor — **deleting a live run's trace wouldn't just
  break its SSE stream, it would free a run id `_run_isolated`'s exclusive-create collision gate
  (invariant 29) is still relying on being taken**, letting a second request append into the same
  file. The floor covers what the protected set cannot: the window between that exclusive create
  and the `_RUN_PROCESSES` registration a few lines later, and a just-finished run whose trace is
  exactly what the answer now on screen links to. Consequence stated rather than hidden: the count
  cap is a SOFT cap under a burst of runs.

  **`prune_traces` never raises, so the lifespan validates the settings itself.** Housekeeping in a
  `finally` must not turn a completed, paid-for `ask` into a 500 — but that same defensiveness
  would make a typo'd `RN_TRACE_RETENTION_DAYS` mean "silently never prune." Split: the per-run
  sweep stays defensive, and startup reads the values directly so a malformed one refuses to boot,
  matching what `config.py` already does for every other bad `RN_*` value. Verified against a real
  `uvicorn` server ("Application startup failed. Exiting.", nonzero exit) — the test drives the
  lifespan directly rather than through `TestClient`, whose anyio portal re-raises a startup
  failure wrapped in a `BaseExceptionGroup`; asserting on that would pin TestClient's wrapping
  rather than this project's behavior.

  **Three independent reviews (concurrency, security, test-quality) then found five more real
  problems, all fixed before merge.** The concurrency pass came back clean on its own axis.

  **A destructive sink with no ownership check (security, MEDIUM).** `_TRACE_DIR` is a bare
  relative `Path("traces")` resolved against whatever directory the server was started in, and
  this project's siblings all write `.jsonl` traces of their own — the review reproduced a
  co-located directory belonging to ANOTHER tool being emptied at server startup, on nothing but a
  filename glob and an mtime. Age and the protected set bound only WHEN a file dies, never WHOSE
  it is. Fixed with `traces._is_ours` (first line must parse as JSON carrying `rlm_harness.trace`'s
  schema marker, or the file must be empty — the abandoned `O_CREAT|O_EXCL` reservation case, which
  still has to stay collectable), plus logging of what each sweep removed; the first version
  discarded `prune_traces`'s return value entirely, so the one destructive operation in this
  project was also silent. Re-verified live against a real server with a mixed directory.

  **The count cap did the opposite of its own docstring (security, LOW but real).** It charged
  protected and too-young files against the cap while drawing every deletion from the eligible
  ones, so N concurrent runs — a client-influenceable number, since `_run_isolated` reserves the
  trace file before spawning — could force well-within-retention traces to be deleted early.
  Retention days was a function of load rather than a floor. Fixed so the cap governs how many
  PRUNABLE traces are kept, matching what the docstring already claimed. One of this slice's own
  tests had pinned the WRONG behavior and was rewritten.

  **404s left permanent lock files (security, LOW).** Entering `notebook_lock` creates its sidecar
  file, so every unauthenticated `DELETE /notebooks/<anything>/notes/n1` left a zero-byte file
  behind for a notebook that never existed — 503 requests, 503 files, invisible to
  `list_notebook_summaries`. Fixed by checking the `create=False` miss before taking the lock as
  well as inside it. Re-verified live: 100 such requests now leave zero files.

  **The entire CLI half of the fix had no test coverage (test-quality).** The review proved it by
  restoring the exact pre-slice defect in `cli._cmd_ask` and watching all 321 tests still pass.
  Four CLI regression tests added, each verified by mutation to actually fail on the code it
  guards. One of them failed that check on its first draft — it wrote concurrently BEFORE
  `_prepare` ran, where snapshot and fresh notebook are identical, so it passed against the very
  defect it was named for; rewritten to inject the write DURING ingestion, the only window where
  the two disagree.

  **Two hollow trace tests (test-quality).** Both were named for the young-file floor and both
  passed with the floor removed from `prune_traces` entirely: one file against a cap of one is AT
  the cap, not over it, so nothing was ever eligible. Rewritten to two files against a cap of one,
  and confirmed to fail without the floor. A third gap — `api._prune_traces` passing the real
  `_RUN_PROCESSES` keys rather than an empty set — had no coverage at all and now does.

  **Verification**: 329 tests pass (from 291), `uvx ruff@0.16.0 check .` clean. Every fix above was
  mutation-tested in a scratch copy (never the working tree) to confirm its test fails on the
  unfixed code. Both original live reproductions re-run after the fix — the single-user sequence
  (all writes now survive) and a cross-process one where a SEPARATE OS PROCESS writes the same
  notebook while a real server is mid-`ask`, which only `flock` covers.

  **Deliberately NOT in this slice**: a merging write (needs conflict semantics that lock +
  re-read makes unnecessary), a multi-worker `uvicorn` story for `_ACTIVE_RUNS`/`_RUN_PROCESSES`
  (the notebook FILE is now safe across processes; those in-memory maps still are not), any
  retention policy for `notebooks/` itself, and every remaining feature-backlog item (Guide/Audio
  artifacts as citable sources, Word/Slides/Docs parsing, full audio transcription).

- **Fifteenth slice: run on a Claude subscription instead of an API key — and this project's FIRST
  real live run.** Prompted by trying to actually start the thing: it turned out nothing here had
  ever been exercised against a real model. Every slice to date was verified offline or against a
  mocked runner.

  **`claude-agent-sdk/<id>` as a model-string sentinel** (`config.SUBSCRIPTION_PREFIX`) routes that
  role onto the user's Claude Pro/Max subscription through rlm-harness's `ClaudeAgentLM`. The
  crucial detail, confirmed by reading `rlm_harness/runtime.py` rather than assumed: **`configure`
  does NOT route on the prefix.** It calls `dspy.LM(cfg.main_model)` unconditionally for any seat
  left unsupplied, so the sentinel alone reaches litellm as a nonexistent provider — it works only
  because `config.setup` injects a pre-built LM through the public `main_lm=`/`sub_lm=` seam.
  Because `worker.py` calls the same `setup`, one change covers both the CLI's in-process path and
  the API's isolated subprocess.

  **Copied from the sibling `cve-reverser`, which shipped this pattern first** — same sentinel,
  same placement of the constant in the dspy-free config module, same lazy import of the adapter
  inside the sentinel branch only (so an API-key-only install never touches the optional SDK), same
  `subscription` extra MIRRORED as a `subscription-sdk` dev group under `[tool.uv] default-groups`.
  That mirror is not redundancy: an extra is not synced by default, so a bare `uv sync` prunes the
  SDK back out and the next subscription run dies with an `ImportError` nobody caused. Deliberately
  not re-invented in a second spelling.

  **One deliberate divergence from cve-reverser, pinned by a test**: an unset `RN_SUB_MODEL`
  inheriting the sentinel from `RN_MAIN_MODEL` is a HAZARD there (its generator is a separate tool
  that must stay on its own endpoint) and simply correct here, since this project has no such role.

  **First live evidence for invariants 4 and 11**, both of which had carried an explicit "residual
  risk, not yet verified" note since the first slice — the offline tests drive a scripted LM, which
  proves the tool-wiring, never that a real model behaves. A real model copied a `[[SRC:s1|whole]]`
  marker verbatim out of the corpus blob and `citations.py` verified it; a follow-up turn that
  needed `history` to resolve "those two launches" still re-derived its citation from `sources` and
  verified independently. It also answered a deliberately planted trap correctly (Voyager 2 launched
  first despite the name), so it was reading the corpus rather than reciting general knowledge. One
  run is evidence, not proof — the invariants' notes are updated, not deleted.

  **A real product defect this surfaced, recorded but NOT fixed here**: an authentication failure
  reaches the client as `RLMTaskError: Failed to produce a valid 'answer' after 1 attempts` —
  indistinguishable from a model that genuinely failed to produce valid output — and the trace file
  records only that same string, because `rlm_harness._retry` wraps the cause with `raise ... from`
  and the `__cause__` never reaches `TraceRecorder`. Diagnosing it required abandoning the API and
  re-running through the CLI to see a traceback, a route no browser user has. Surfacing the cause
  in the trace, and separating "misconfigured" from "the model failed", is its own follow-up.

- **Web UI: two real bugs found by opening the page, both fixed.** Neither was reachable by any
  test this project had.

  **The entire UI was dead from the first paint.** `.modal-overlay { display: flex }` outranks the
  UA stylesheet's `[hidden] { display: none }` — author styles beat UA styles regardless of
  specificity — so the source-viewer overlay was permanently visible, and with `inset: 0` and
  `z-index: 1000` it swallowed every click on the page. The ✕ looked unclickable because closing
  set an attribute that no longer changed anything. Shipped this way in the source-viewer slice.
  Fixed with the `.modal-overlay[hidden]` rule that must accompany any such `display` declaration.

  **The same defect had a SECOND instance, and the first fix shipped with a false justification.**
  `.ticker-detail` carried the identical `display: flex`-without-`[hidden]` bug from Phase 3,
  leaving the reasoning-step log permanently expanded with a dead `⌁ N steps` pill — and the
  `.modal-overlay` fix argued that a citation detail should toggle "because the ticker already
  does", which it never did. An independent review caught the missed instance and the claim built
  on it. Both are fixed; the tripwire below now keys on CSS classes so it can see elements built
  with `createElement`, and asserts up front that it still detects both known instances.

  **A re-click on an open citation detail now collapses it** instead of blanking the panel to
  "Loading…" and re-fetching the identical payload, which read as a flash with nothing ever
  closing. Keyed on which citation is shown — including its `quote`, since text and web sources all
  use locator `"whole"` and `source_id|locator` alone would make clicking a second citation into
  the same source CLOSE the panel rather than switch. Collapsing bumps the staleness token so an
  in-flight response cannot repopulate a panel the user just closed.

  **`tests/test_web_assets.py`** (new) asserts on the SOURCE TREE, because the stylesheet bug is
  invisible to every layer otherwise testable here: the Python suite never renders a page, and a
  unit test of `closeSourceViewer()` would have passed against the broken stylesheet — the JS was
  always correct. **Its first version was itself reviewed and found badly wrong**, every fault the
  same shape — it only looked at what was easy to parse. It harvested ids from `index.html` only,
  so it could not see either `createElement`-built element, including the one carrying a live
  unfixed instance of the very bug it claimed to prevent; it matched `X.hidden` by bare variable
  name, giving three confirmed false positives waiting on the next styling change; and its
  comment-stripping never ran, because a `{` inside a CSS comment splits that comment across two
  regex blocks. Rewritten to key on CSS CLASSES — the axis the hazard lives on, spelled identically
  by the markup and the JS. Both instances are now mutation-verified, the demonstrated false
  positive no longer fires, and the `innerHTML` check covers its `outerHTML`/`insertAdjacentHTML`/
  `document.write` siblings too. **Stated gap**: there is no JavaScript test runner here at all (zero-build
  vanilla JS, by design), so interactive UI state — a toggle that stops toggling — still has no
  test seam. A source-tree assertion cannot reach it.

- **Sixteenth slice: a notebook names itself.** The web UI refused to add a source until the user
  had invented a notebook id (`Open or name a notebook first`), which made the very first
  interaction with this product a naming puzzle about a thing that did not exist yet. I deferred
  this once as "its own slice"; the user pushed back, correctly — the blocker was never that the
  naming was unsophisticated, it was that naming was mandatory at all.

  **`id` and `title` are now two fields.** The id is a handle the UI mints itself
  (`nb-<uuid8>`), and it still backs every filename, `ChatTurn.run_id` prefix and URL, so it has to
  stay stable. `schema.Notebook.title` is the label a person reads and is free to be anything —
  which is exactly why splitting them beats renaming a notebook (which would move its file and
  invalidate its run ids). Optional, defaulting to `None`, so older notebooks still load.

  **`naming.SuggestTitle` is deliberately not an `RLMTask`**: a full REPL loop in the pyodide
  sandbox is right for exploring a multi-MB corpus with verifiable citations and absurd for five
  words. It is one plain `dspy.Predict` over a 4000-character excerpt — ~8s live, versus a sandbox
  boot plus planner turns. It still runs in the API's isolated subprocess, so invariant 21 is
  untouched: `worker.py` only calls `.arun(**kwargs)`, so satisfying that one method is the whole
  contract and `api.py` still imports neither `dspy` nor `rlm_harness`.

  **A title never costs the user their source.** `POST /notebooks/{id}/title` is separate from
  `add_sources` (ingestion must not wait on, or fail because of, a model call), fired on the first
  source only, and every failure path falls back to a deterministic title derived from the origins.
  An existing title is never overwritten.

  Verified live end to end with no name ever typed: an English source titled itself
  `Voyager 1 Interstellar Mission`, a Chinese one `蜜蜂的偏振光導航` (the prompt asks for the
  sources' own language), and the fallbacks were exercised directly.

- **Seventeenth slice: a "generate overview" action, in the conversation.** A user asked where the
  Gemini-style "produce the research artifact, then ask follow-ups from it" moment was. The
  functionality existed — Studio's Summary/FAQ/Timeline/Insight tabs — but adding a source left the
  screen doing nothing: Chat said "ask a question once you've added a source", Studio said "pick a
  tab to generate it", and both waited on the user to discover the next move. Even finding the
  Summary led nowhere, because it renders in a right-hand tab disconnected from the thread.

  `#chat-overview` sits above the chat history and holds either a primary `✨ Generate overview`
  button or the generated artifact: the Summary rendered through the SAME
  `renderAnswerWithCitations` a Chat answer uses (so its citations, source viewer and trace links
  all behave identically), then up to three clickable starter questions from the FAQ task. **No
  server-side change at all** — both endpoints already existed.

  **Still an explicit button, never auto-generated on open**: Phase 2's reasoning (a guide run is a
  real RLM loop; never spend one nobody asked for) is unchanged. What changed is that the action is
  obvious instead of hidden behind a tab. Summary and FAQ run CONCURRENTLY — two independent runs,
  so serial execution would double the wait for nothing (measured 34s live, against ~30s for one).
  FAQ is reused rather than adding a cheap ungrounded question generator: its questions are already
  grounded by a task that exists, and starter questions gesturing at something the sources don't
  cover would be worse than none. `allSettled`, so an FAQ failure never costs the user the summary.

  **An independent review found 8 problems in the first version, all fixed.** The worst was
  self-inflicted and 100% reproducible: the client sent a bare UUID as `run_id` and then used that
  bare value locally, but the server derives `{notebook_id}-{token}` and both trace endpoints reject
  anything without the prefix — so every citation's "view reasoning" in the overview 404'd. The
  shape was copied from `suggestTitle`, where a bare token is correct precisely because it is never
  used client-side. Verified after the fix by hitting both trace endpoints with each shape: old
  → 404, new → 200. Also fixed: a trace affordance rendering a dead "⌁ 0 steps" because
  `openTicker` was never called; starter chips bypassing the `chat:pending` lockout via
  `requestSubmit()` (which submits as if by the form, so a disabled submit button never blocks it)
  and producing two pending turns, one of which visibly vanished; the overview never being
  invalidated when the corpus changed, unlike the Studio cache next to it; no per-request guard, so
  two concurrent generations raced last-writer-wins; an unbounded flex item that would collapse the
  chat history and push the ask box off screen; and a silent FAQ failure. The button also moved out
  of `#chat-empty` — `chat:turnAdded` hides that node, so it vanished after the first question and
  was permanently unreachable for any notebook that already had turns, which is exactly the set most
  likely to want one.

- **The overview can be saved as a note — closing the loop this project already had every piece
  of.** Prompted by a direct question: does NotebookLM persist its overview? It does, and the
  mechanism is not a special one — its generated artifacts BECOME notes, which is how they survive
  at all. This project has had `Note`, `promote_note` and note-to-citable-source since the eleventh
  slice; the overview simply had no way in.

  `saveAsNoteButton` is a factory two call sites opt into (`renderTurn` and `generateOverview`),
  NOT a line inside `renderAnswerWithCitations` — the restriction invariant 32 records still holds,
  but its stated REASON was wrong. "Generated output is not something a user curates into notes" is
  contradicted by the product being chased; the line that actually holds is about the surface:
  things rendered IN the chat thread are the user's to curate, a Studio tab's artifact and a
  podcast transcript are not part of that thread.

  Verified live end to end: overview -> note -> promote -> a new source that later questions can
  cite. A toy source whose summary restated it verbatim instead hit the documented dedup no-op,
  which is the correct behaviour and worth having seen.

- **Eighteenth slice: the overview persists, and goes stale instead of vanishing.** A user
  re-opened a notebook holding a full conversation and still saw the first-run `✨ Generate
  overview` button. The overview had never been persisted — it lived as a flag on a DOM node — so
  every notebook opened in the "never generated" state. The second half was worse: adding a source
  DELETED the overview and reverted to that same button, making "never generated" and "generated
  but the sources moved since" render identically, and confiscating an artifact that cost a real
  RLM run.

  `schema.Overview` on `Notebook.overview` (optional, so old files still load), with the source ids
  it was computed from as the staleness key — a comparison, not a timestamp. Three states, and the
  stale one KEEPS the overview on screen with a marker plus `↻ Regenerate`, because it is still
  true about the sources it was computed from. A deliberately narrow cut of the long-deferred
  "guide artifacts aren't cached" item: the overview only, never the four Studio tabs.

  Generation moved server-side (`POST /notebooks/{id}/overview`, running Summary and FAQ
  concurrently), not because of provenance but because closing the tab between a client-side
  generate and a store call would lose a paid-for run.

  **A pre-implementation audit found 2 blockers and 6 should-fixes, all folded in before any code
  was written** — both blockers were cases where the natural implementation is silently wrong.
  Building the `Overview` inside the `mutate_notebook` closure would have captured the source ids
  at PERSIST time, claiming coverage of a source the model never read. And forming
  `<token>-summary` before slugging breaks twice: an absent `run_id` yields the literal
  deterministic `None-summary`, so the first anonymous request wins the exclusive-create gate and
  every later one 409s for as long as retention keeps the trace; and `slug`'s 120-char cap merges
  the two suffixes for a long token (`slug("a"*119 + "-summary") == slug("a"*119 + "-faq")`,
  verified). Both fixes are mutation-tested.

  The audit also caught a PRE-EXISTING bug it would have made permanent: `stream_run` and
  `citation_turn` compared the RAW notebook id against a run id `_derive_run_id` had slugged, so
  every trace link was dead for `"my notebook"` or any non-Latin id (invariant 10). Harmless while
  the affordance was ephemeral; a dead link on the front page once `Overview.run_id` persists.

  Verified live end to end: generate → reload (survives, `stale: false`) → add a source (still
  there, `stale: true`) → trace link still 200. Plus both blockers checked directly: two anonymous
  requests in a row both 200 with distinct run ids, and a 121-character token no longer collapses
  its two run ids into one.

- **Nineteenth slice: output language.** Every model-authored string came out in the SOURCES'
  language, so a Traditional-Chinese reader feeding in English papers got an English notebook. The
  language you read should not be decided by the documents you happen to be reading.

  **The carve-out turned out to be the load-bearing half.** `verify_citations` compares `locator`
  with an exact `==` and never inspects `quote` at all, so a model told "write everything in
  Chinese" that localises `page:1` to `第1頁` makes every citation UNVERIFIED, and one that
  translates a quote leaves a ✓ badge on something that is no longer the source's words. The design
  named only `quote`; the pre-implementation audit caught that and the rule now covers `source_id`,
  `locator`, the marker syntax and `quote` together, composed BEFORE the citation rules.
  `CITATION_RULES` also gained the "a quote is copied verbatim" sentence it had never contained, and
  `schema.py`'s "faithful summary" wording that muddied it is fixed.

  **The resolution is a model judgement, not a header lookup — and a sibling project
  already paid for the alternative.** Its ASR seeded itself from `Locale.current`, which answers
  "what language should this app's UI be in" while ASR was asking "what language is this person
  speaking", and transcribed Chinese speech as syllable-by-syllable English gibberish.
  `Accept-Language` is the same shape of wrong question. `naming.SuggestLanguage` (a cheap
  `dspy.Predict`, not an RLMTask) weighs the header, the sources' language, and any questions
  already asked, with questions weighted highest. Two more of that project's lessons applied directly: a
  ladder cannot correct its own input, and an instrument that cannot reproduce production's shape is
  not evidence — so the live check sends the `Accept-Language` a real browser sends.

  `RN_OUTPUT_LANGUAGE` is a hard override and applies to CHAT too. The value reaches a task as a
  signature field and is never empty: instructions are composed at import time, so "a signature
  field" and "byte-identical prompts when unset" were a contradiction in the design, resolved with a
  literal default.

  **The Audio Overview is deliberately excluded, as a stated scope cut.** `tts.py` maps no language
  to a voice, so a forced-Chinese notebook would produce a correct Chinese script read by the en-US
  default cast — quietly breaking invariant 15. A tripwire asserts the podcast task does NOT declare
  the field (so the exclusion stays deliberate) and every other grounded task does, because a
  missing required input surfaces only as the opaque `RLMTaskError` while an undeclared extra kwarg
  is silently accepted — a partial rollout fails silently in both directions.

  The audit found 4 blockers and 8 should-fixes before any code was written, including two run-id
  collisions: sharing the artifact's derived id 409s on the exclusive-create gate, and `/overview`
  gathering two runs would have fired two concurrent resolutions deriving the same `-lang` id.

  **Verified live, both paths**, since the offline tests drive a scripted LM and can demonstrate
  none of it: forced Chinese against English sources gave Chinese prose with `s1`/`whole`
  untranslated, English quotes verbatim, every citation verified; and with the override unset,
  `Accept-Language: zh-TW` against the same English sources resolved to "Traditional Chinese",
  persisted it, and did not re-resolve for the next artifact.

- **Twentieth slice: language-aware default voices — the podcast rejoins the language story.**
  The previous slice excluded the Audio Overview as a stated scope cut; this closes it.

  **The gap was never "edge-tts is the wrong TTS".** Nothing in this project mapped a language to a
  voice: `voice_map` came straight from `RN_TTS_VOICE_HOST_A`/`_B` and `synthesize` spoke whatever
  it was handed. Every provider would have had the same hole, so swapping providers would not have
  fixed it — a correct Chinese script read by the en-US default cast is a routing bug, not a
  synthesis one.

  `tts.default_voices_for` maps a language to a voice pair, matching loosely because the value
  arrives either as a model-authored name ("Traditional Chinese") or as whatever an operator typed
  ("zh-TW"), with a BCP-47 tag falling back to its primary subtag. **Every voice id was read out of
  a real `edge_tts.list_voices()` response rather than written from memory** — a plausible-looking
  but nonexistent id fails only at synthesis time, after a real model call has already been spent on
  the script, exactly the waste invariant 19 exists to prevent.

  An explicitly set env voice beats the language default, read from the RAW environment rather than
  by comparing against the default value: setting `RN_TTS_VOICE_HOST_A=en-US-GuyNeural` on a Chinese
  notebook is a choice, and an equality check would overrule it. The two resolve independently.

  **The previous slice's tripwire earned itself immediately.** It pinned that
  `GeneratePodcastScript` did NOT declare `output_language`, so adding the field failed the test
  rather than letting a stated scope cut erode unnoticed — the exclusion had to be un-made
  deliberately.

  Verified live end to end: an English source in a forced-Chinese notebook produced a Chinese
  two-host script and synthesized it with the zh-TW cast into a valid 203KB MP3.

- **A download link on the podcast player.** A user asked where the generated mp3 was. Nowhere —
  by design: the server writes a temp file and unlinks it in a `finally`, so the episode exists only
  as the browser tab's `Blob` and a reload loses it. `<audio controls>` exposes a download in some
  browsers' overflow menu, which is neither discoverable nor uniform. An explicit `↓ Download mp3`
  now sits beside the player, sharing the player's object URL so the existing
  assign-new-then-revoke-old ordering keeps both valid together. The filename is slugged from the
  notebook title rather than interpolated — `download` is an attribute the browser turns into a path
  component, and that title is model-authored.

- **Twenty-first slice: a settings page — presentation settings only.** The user picked this shape
  after three were put on the table, and the reason is not preference: this API has no
  authentication (invariant 25) and today holds NO secrets, so a page that persisted API keys
  server-side would let anyone who can reach the server read or spend them.

  **"Non-secret" turned out to be the wrong filter.** Two candidates are levers an unauthenticated
  caller does not have today: lowering `RN_TRACE_RETENTION_DAYS` DELETES trace files that can hold
  ingested source text, and raising `RN_MAX_UPLOAD_BYTES` is a straight DoS lever. Moving a safety
  BOUND onto an unauthenticated page is the same mistake as moving a key there, just quieter. So the
  page carries the output language and the two podcast voices, and nothing else. `RN_BASE_URL` is
  the sharpest exclusion: `config.setup` hands it to `rlm_harness.configure` alongside `api_key`, so
  a writable base_url exfiltrates the key on the next run without anyone ever reading it.

  A pre-implementation audit found 4 blockers. The language ladder has FOUR rungs, not the two the
  design named — a one-line "read the file too" would have silently made a browser-typed language a
  hard override over every notebook's persisted resolution, in the CLI as well, with no test
  failing. The TTS provider is a `NotebookConfig` field, so reporting it needs `_config()`, which
  raises `SystemExit` → 500 when `RN_MAIN_MODEL` is unset — on the one page an operator opens when
  the server is misconfigured; it was cut from the slice. The voice ladder's position was undefined
  against invariant 40. And both proposed file locations were wrong: a repo-root `settings.json` is
  not gitignored, and `pathlib`'s `*.json` glob matches dotfiles, so `notebooks/.settings.json`
  would have been reported as a corrupt notebook.

  **A live check then caught a bug the tests had missed.** Pydantic DROPS unknown keys before the
  handler's validator sees them, and combined with full-replacement semantics a request carrying
  only a typo'd key silently WIPED every setting — while a test asserting "nothing outside the three
  settings is persisted" passed. Fixed with `extra="forbid"`, and the regression is mutation-tested.

  That same live check left a settings file in the working directory and turned an unrelated TTS
  test red, because every path here resolves against the process CWD. Rather than delete the file,
  `tests/conftest.py` now isolates every test into its own directory — a developer's local state
  silently changing a test result is the same class a sibling project's ASR-locale design records.

- **Twenty-second slice: the Audio Overview persists and plays from the page.** Phase 2 deliberately
  kept no audio past one request — no file-serving endpoint, no retention to get right — and it cost
  the user their episode on every reload, since it existed only as the browser tab's `Blob`. Reported
  after they asked where the mp3 was.

  One mp3 per notebook (`notebooks/audio/<slug>.mp3`), replaced on regenerate, which is what makes
  retention a non-question: growth is bounded by how many notebooks exist, not by how many times
  anyone pressed the button — unlike `traces/`, which needed a whole sweep. The transcript persists
  on the notebook; the audio does NOT go in the JSON, because a multi-MB base64 blob would be
  re-parsed on every read of that notebook. `GET .../audio/file` serves it instead, which also lets
  the browser range-request it — verified live: a `Range` header returns `206 Partial Content`.

  The audio is written BEFORE the notebook record, so a crash between the two leaves an orphan file
  (harmless — overwritten on the next generate) rather than a notebook pointing at audio that isn't
  there. Same staleness treatment as the overview, citations re-verified on every read, and ONE
  `renderPodcast` serving both the just-generated and the reopened case so a persisted episode can
  never render differently from a fresh one.

  **Two features had shipped completely inert, found while investigating this.** `initSettings()`
  and `initNotebookTitle()` were never called: a scripted edit's anchor didn't match the file's
  actual indentation and `str.replace` silently did nothing. So the settings button was dead on
  click and the header's notebook title had NEVER displayed since it was added. Nothing else could
  catch it — there is no JavaScript test runner, and a defined-but-uncalled function is valid JS —
  so `tests/test_web_assets.py` now fails the build on any `init*()` that is defined and never
  called. Mutation-tested. The settings icon also reused `.theme-toggle`, whose `margin-left: auto`
  then applied to two elements at once; one `.header-actions` wrapper owns the push-right now.

- **Twenty-third slice: a fully local TTS provider.** `RN_TTS_PROVIDER=kokoro` (the `kokoro`
  extra) synthesizes with no network call at all — no API key, and none of the undocumented-endpoint
  grey area `edge-tts` operates in with its hardcoded client token.

  **Two recommendations were wrong before this one, both from unverified sources.** NeuTTS: no CJK,
  which is the language the whole output-language work exists for. Qwen3-TTS: recommended from a
  blog summary claiming CPU inference, but the repository documents `device_map="cuda:0"` and never
  mentions CPU — it would not run on the machine this project is developed on. (Its licence claim
  did hold up on checking the HF model card, but I had asserted it before looking.) Kokoro was
  chosen only after being installed and RUN: Apache-2.0, ~82M parameters, 17.4s one-time load then
  4.4s for 8.9s of Mandarin on CPU.

  **A `TTSProvider` now owns its output FORMAT and its own language→voice map.** A voice name is
  provider-specific — `zh-TW-YunJheNeural` versus `zf_xiaobei` — so one shared map would have leaked
  one provider's names into the other's request. Kokoro emits 24kHz WAV, and forcing it through an
  MP3 encoder would drag in the ffmpeg/pydub dependency invariant 17 refused. Handled rather than
  assumed: `find_audio` looks for whichever format is present (switching providers must not orphan
  an existing episode), `clear_audio` removes every format before a regenerate, and the file
  endpoint derives its media type from the file rather than the configured provider.

  An EXTRA, never core: 87 packages including torch, transformers and spacy (measured with
  `--dry-run`), plus weights on first use. Invariant 15's "works out of the box" rests on the
  DEFAULT provider needing neither a key nor a download.

  Verified end to end through the real product: a 14-turn Chinese episode generated with no network
  TTS call, written as `notebooks/audio/<slug>.wav` (2m53s, 24kHz), the previous `.mp3` removed, and
  served as `audio/wav` with range support.

- **A code-vs-docs consistency audit across all sixteen commits, and one real bug it found.**
  Requested after several slices had gone through pre-implementation design audits but no
  post-implementation review. It found 7 blockers, 10 should-fixes and a page of nits.

  **The bug: a persisted podcast never rendered on notebook open** — the entire point of persisting
  it. `initPodcastPlayer` registered two `notebook:switched` handlers, and `store.emit` runs them in
  registration order, so the later `clearPlayer` blanked the panel the first had just filled. The
  invariant claiming "one `renderPodcast` serving both the just-generated and the reopened case"
  was therefore false in practice. `tests/test_web_assets.py` now fails the build on two
  subscriptions to the same event inside one `init*` function; mutation-tested.

  **One invariant was simply FALSE, and verified false**: invariant 21 claimed `api.py` never
  imports `dspy`/`rlm_harness`. It does, transitively, through the task classes it imports for
  `_dotted()`'s introspection — `import rlm_notebook.api` loads both. The guarantee that actually
  holds is about EXECUTION (no `RLMTask` is ever run in the API process), and it now says so.

  **"No audio is ever persisted" survived in three places** after the previous slice reversed it —
  `api.py`'s module docstring (which is also the OpenAPI description), README, and a paragraph of
  invariant 29 whose neighbouring paragraph HAD been amended. Also fixed: invariant 40's voice
  ladder was missing the settings-file rung invariant 39's had gained, invariant 41's stated reason
  for excluding the TTS provider ("only one exists") stopped being true when kokoro landed,
  invariant 27's worked example was superseded by invariant 10, the Scope note was nine invariants
  behind, README still listed trace retention as unbuilt twenty-five lines after describing it, and
  `DESIGN.md` still specified the Blob player, a two-state overview and a header without the title,
  settings or wordmark button.

  **Two format assumptions the previous slice claimed were "handled" were not**: the download link
  hardcoded `.mp3` for a file that may be WAV, and the CLI's `--out` default did the same. The
  server now REPORTS the episode's suffix rather than leaving the client to infer it from the
  configured provider, and the CLI corrects its default extension only when the user did not choose
  the path themselves.

- **A Traditional Chinese interface.** Batch two of the UX pass.

  Kept SEPARATE from the notebook's output language, which is a server setting deciding what the
  model writes. This one is a browser preference deciding what the buttons say — a reader may well
  want a Chinese interface over English papers, and folding the two together makes that
  unexpressible. It lives in `localStorage`, never reaches the server, and never reaches a prompt.
  Detected from the browser, switchable in Settings.

  The English table is deliberately empty: English is whatever the markup and the code already say,
  with every call site carrying its own fallback, so there is no second copy to drift. Two tripwires
  guard the parts that fail silently — a key used but not translated (the interface would just stay
  half-English) and a call with no English fallback (an English reader would see the key).
  Simplified Chinese deliberately does not resolve to the Traditional table.

- **A UX pass over the whole product surface, from a user's list of seven.** Batch one of three.

  **"Pressed generate, it said Finished, then nothing appeared."** Reproduced as a design fault
  rather than a crash: the response arrives, a staleness guard drops it silently, and the last
  ticker line sits there looking stuck. What trips that guard is pressing the button again — which
  is the natural move when a minute-long run shows no progress and offers no way out. So the three
  are one fix: every long action now shows a pulsing dot, the live action and a ticking timer, a
  superseded generation says so instead of returning silently, and there is a Stop button.

  **Stop cancels by run id.** `/overview` fires two runs and `_ACTIVE_RUNS` holds one slot per
  notebook, so the existing notebook-scoped cancel would leave the second one burning a model call
  to completion. The new run-scoped endpoint kills exactly what was asked for — verified live:
  both halves killed mid-run, exit -9, zero orphan workers.

  **Selecting a Studio tab no longer runs anything.** It used to fire a real RLM call on click, so
  browsing the four kinds to see what they were cost four model runs. Each tab now says what it is
  (on hover) and offers a button.

  Also: "Audio Overview" is "Podcast"; Studio, Podcast and Notes each carry one sentence saying what
  they are for; and `+ Save as note` explains that promoting a note is what makes it citable.

- **Fix `no run '…-summary' found` on the first overview of a new notebook.** Reported from real
  use and reproduced on the first attempt.

  The ticker opens before the request and waits five seconds for the run's trace file. But every
  run-taking handler resolves the output language first, and that is a real model round trip in its
  own subprocess — on a new notebook it always happens, because the language has by definition never
  been resolved, and it always takes longer than five seconds. So the client gave up while the
  language run was still going, on a request that then succeeded normally. `traces/…-lang.jsonl`
  sitting beside the summary trace is the fingerprint.

  This is a different window from the one the trace-stream slice already closed: that one was
  microseconds between reserving the trace file and registering the process, this one is minutes
  and sits before either. Run ids are now ANNOUNCED before any pre-work, and the stream waits
  indefinitely for an announced run while still bounding one nobody will ever write. Applied to all
  five run-taking handlers, including `/title`, which no client streams today but could.

  The first regression test was hollow — it pinned the mechanism and stayed green with the fix
  deleted from the very endpoint that was reported. Mutation-testing caught that; the behavioural
  test now makes language resolution slow and opens a ticker alongside the request the way a browser
  does.

- **Twenty-fifth slice: the local TTS provider is Chatterbox now, not Kokoro — and the reason is the
  language matrix, not audio quality.**

  The user's audience is English first, Chinese (both scripts) second, Japanese and Korean third,
  with foreign words mixed into all of them. Nothing about that was true of the local provider:
  Kokoro's Chinese G2P passes Latin straight through (its "phonemes" for `NASA` are the literal
  string `NASA` — that is the mechanism behind the mangled audio a user reported), it has no Korean
  at all, and its own model card grades every Chinese voice D.

  **MeloTTS was measured as the replacement first, approved after a listening test, and then
  rejected on the matrix.** Its Japanese module DELETES embedded Latin; its Korean needs a package
  that destructively overwrites the one its Japanese needs, so the two cannot coexist in a single
  environment at all; its English needs an NLTK resource its own installer never fetches. Recording
  that here because the listening test had already picked it — the requirement is what disqualified
  it, not the sound.

  Everything else was checked against its LICENSE file or model card rather than a summary: Fish
  Speech, Higgs Audio v3, IndexTTS-2 and F5-TTS are all licence-blocked; CosyVoice 3 is zero-shot
  only (every synthesis needs a reference clip); VibeVoice is English and Chinese only and embeds an
  audible AI disclaimer in every output.

  **Chatterbox is MIT for both code and weights, covers all four languages, and handles a foreign
  word inside a sentence for free** — it has no G2P stage to fail at, which is the structural reason
  the G2P-based engines all break the same way.

  **Three costs, measured rather than assumed, and none of them hidden.** It runs at RTF ~4.5
  against Kokoro's ~0.2 — a 3.4-minute episode took 16.1 minutes end to end through the real
  product, 15 of them synthesis, where Kokoro took about forty seconds. Its output LENGTH is
  unstable — the same Traditional Chinese sentence came back at 34.80s / 5.48s / 11.68s against an
  expected ~7s, and the long take was the decoder looping, not trailing silence — so
  `ChatterboxProvider._generate_one` re-rolls against a character-count estimate that is calibrated
  against four real measured utterances and pinned by a test. And it ships exactly ONE built-in
  voice, so two distinguishable hosts need reference clips.

  **Those two clips are synthesized, not recorded**, so no person's voice is being cloned — and the
  provenance chain behind them is disclosed in `rlm_notebook/voices/README.md` rather than left to
  be discovered, because it is three hops long and this project has paid once already for taking a
  licence chain on trust.

  Also: `TTSProvider.synthesize` now takes the resolved `language`, because a cross-lingual
  provider's voice and language are independent axes; a path to a custom reference clip is reachable
  from the environment but deliberately NOT from the unauthenticated settings page; and the extra
  carries two odd-looking pins (`numba>=0.61`, `setuptools<82`) that are what make it install and
  import at all on Python 3.13.

  **Verified live end to end**: a 16-turn Traditional-Chinese episode from English sources, 16
  offsets each landing on its own line's audio, `NASA` rendered `美國航空暨太空總署` with zero Latin
  runs, the two hosts measurably distinct (median F0 126 Hz against 201 Hz), served as `audio/wav`
  with range support. The runaway guard did not fire — which shows the ceiling is not set so tight
  that it burns re-rolls on correct takes, and is NOT evidence the instability is gone.

  **An independent review then found two blockers**, both silent failures. CI would have gone red:
  the new provider test faked `soundfile` and `chatterbox.mtl_tts` but not `torch`, whose only root
  in the dependency graph is `chatterbox-tts` — verified fixed by running the whole suite under a
  meta-path blocker that makes the extra genuinely unimportable. And mixing `built-in` with a
  reference clip collapsed BOTH hosts into one voice, because the built-in conditioning exists only
  as `model.conds` and the first `prepare_conditionals` overwrote it.

  From the same review: `validate()` moved ahead of the script run (a language chatterbox has no id
  for used to burn a whole model call before failing); the language pass-through had zero coverage
  at either call site; the lazy-import test was a vacuous disjunction that a module-scope
  `import torch` still satisfied; the settings page's voice help was edge-tts-only; and the
  provenance file pointed at a regeneration command that shipped nowhere. Every fix mutation-tested.

- **A code-vs-docs consistency audit across the whole repo, and the eleven fixes it produced.**
  Run as the closing step of the slice above, over all 45 invariants rather than just the diff. It
  found doc claims in both directions — things the docs promised that the code did not do, and
  things the code did that no doc mentioned — plus four invariants whose "confirmed by a test"
  turned out to rest on nothing.

  **Real defects, all mutation-tested:**

  - `RN_MAX_UPLOAD_BYTES=not-an-int` returned a raw 500 with a traceback. Invariant 24 claimed every
    `SystemExit` in `config.py` was reachable only through `from_env()`, so `_config()` covered them
    all; `max_upload_bytes` has one of its own and is the first statement of the upload handler.
    (It is standalone *because* invariant 30 says an upload must not depend on a model being
    configured — which is exactly how it fell outside the wrapper.)
  - Trace links were dead for `"my notebook"` or any non-Latin notebook id — the ids invariant 10
    exists to support. The server-side half of this was fixed two slices ago; the CLIENT was still
    building run ids from the raw id. `NotebookResponse.slug` now carries the server's own
    transform rather than a second copy of it in JS.
  - `RN_TTS_PROVIDER=kokoro` plus a language kokoro does not know fell through to the shipped
    `en-US-GuyNeural` — an edge-tts name handed to `KPipeline`, so synthesis failed *after* a real
    model call. The language map moved onto the provider in the previous slice; the last resort had
    not moved with it. And the settings page's voice pattern rejected every kokoro id, so a user
    could not name a voice for the provider they had configured.
  - Generating a podcast whose script came back empty left the previous episode on disk, so
    `GET .../audio/file` kept serving audio the notebook no longer had.

  **Four invariants that claimed a test and had none** — each now pinned, each verified by mutating
  the code and watching the new test go red: invariant 2's "do not swap back to plain `urlopen`"
  (swapping it left the suite green — the redirect tests call the handler directly and never
  exercise which opener fetches); invariant 22's `start_new_session=True` (deleting it left the
  suite green, because the existing test hardcodes the flag itself instead of calling
  `runner.start_run`); invariant 29's pre-spawn `_RUN_PROCESSES` reservation, the fix for the
  user-reported "run ended without a final event"; and invariant 23's identity check, which the
  invariant said was "confirmed with an interleaved-`asyncio` test" that did not exist. The first
  attempt at that last one was itself hollow — asserting both entries are gone afterwards is
  satisfied by the buggy version too — and only caught the bug once rewritten to check that a
  *finishing* run leaves a *later* run's slot alone.

  One test was also quietly downloading spaCy models over the network and skipping on CI; it fakes
  `kokoro` and `soundfile` through `sys.modules` now, verified with a meta-path blocker rather than
  by trusting its own docstring.

  **Doc corrections worth naming**, since several were overclaims of the exact kind invariant 5
  exists to prevent: the size cap fires at question time, not at ingestion time; there is no
  model-side injection conclusion to union with, and the flags reach the CLI only; `GET /notebooks`
  is no longer "metadata only" now that it carries a model-authored title; synthesis runs on
  schema-validated output, not "citation-checked" output; there are six citation-grounded tasks, not
  five; `NotebookConfig.ocr_provider` has zero consumers; the CLI's `audio` persists nothing. Two
  design documents referenced from 21 places had never existed, and the rest of `docs/` is
  gitignored anyway.

- **Twenty-fourth slice: subtitle-style transcript, a podcast that lands, and speakable prose.**
  All three reported by a user listening to a real episode.

  **The transcript is now subtitles**: the line being spoken is highlighted, a timecode sits beside
  each line, and clicking a line seeks to it. Timing comes from the PROVIDER — every provider here
  already synthesizes utterance by utterance — rather than from parsing the audio. `Podcast.offsets`
  is parallel to `utterances` rather than a field on `Utterance`, because `Utterance` is the model's
  output shape and the model cannot know how long its own words take to say; anything but one
  strictly-increasing offset per utterance means "no timing" and renders a plain transcript.

  **A bug the offsets themselves revealed**: the first version keyed on edge-tts's `WordBoundary`,
  but the installed version defaults to `boundary="SentenceBoundary"` and emits only that — so every
  offset came back 0.0, a transcript highlighting nothing. Found by generating a real episode and
  reading the numbers.

  **An independent review then found the safety net for that case did not exist.** A provider
  reporting no boundaries returns `[0.0, 0.0, ...]` — the RIGHT LENGTH, so the documented length
  check could never fire; simulated, it stamps every line `0:00`, highlights the second row for the
  whole episode and seeks every click to zero. The guard is monotonicity now, and the claim in the
  docstring is gone. The same review showed by mutation that the entire API side of `offsets` (the
  response, what gets persisted, and the reopen path) had no coverage at all — deleting all three
  left the suite green — and that the edge-tts offset test could not catch a per-utterance state bug
  because its fixture gave every utterance the same duration. Both are pinned now, and kokoro's
  gap-before-offset rule moved into a pure function (`tts.sequence_offsets`) so CI can check it
  without the extra, a model download, or any audio. Every fix here was mutation-tested.

  Also from that review, all in the player: clicking into an expanded trace payload (or the mouseup
  ending a drag-selection) seeked and autoplayed; the hover state was the colour the row already had
  AND outranked `.is-speaking`, so hovering the playing line deleted its highlight; `formatTimecode`
  had no hour component; and the playhead follower used `scrollIntoView`, which walks every
  scrollable ancestor — the transcript is its own scroll box now, so following the playhead can no
  longer drag the studio column back from whatever the reader had scrolled to.

  **The episode has a shape.** `audio.py` asked only for "a natural conversation" — no opening, no
  segment plan, and no close, so episodes simply stopped when the model ran out of facts.
  NotebookLM's Audio Overview was never used as a reference; that gap is closed after a user named
  it. There is now an opening that frames the sources, a body that follows the interesting thread,
  and a close that draws the threads together and says what it adds up to, grounded in the sources.

  **Prose is written to be SPOKEN in one language.** A TTS voice for one language cannot pronounce
  another script, which the user heard. The mechanism was confirmed rather than assumed: kokoro's
  Chinese G2P returns the literal string `NASA`, and `Voyager i→`, as its own "phonemes" — raw
  Latin letters reach the acoustic model as unknown tokens. Foreign proper nouns are now rendered
  the way a native speaker would say them, scoped to what is actually spoken and exempting a
  `Citation.quote`. Two things the first draft of the rule got wrong, both caught by checking a real
  episode rather than re-reading the prompt: it invited the original in parentheses (the exact
  failure it exists to prevent — an utterance is both the transcript AND what the voice reads), and
  it let acronyms through, which a live run duly demonstrated. Both closed, and re-verified by
  regenerating: `NASA` became `美國國家航空暨太空總署`, every proper noun renders spoken, each
  citation kept its verbatim English quote and verified, and the episode closes on a genuine
  reflection rather than a stray fact. One Latin letter survives — the `E` in `泰坦三號E半人馬座運
  載火箭`, which is how the designation is written in Chinese — and is left stated rather than
  chased with a stricter sentence.

  Also: kokoro now inserts a short gap between utterances (free, since it holds raw samples — unlike
  edge-tts, where invariant 17 refuses re-encoding), and `.btn` sets `color`/`text-decoration`
  because it has to work on an `<a>` — the download link had been rendering as UA-blue underlined
  text on the dark theme.

- **Three more UX defects, all reported by a user actually using the thing.**

  **A notebook named in Chinese was rejected outright.** `notebook.slug`'s `[A-Za-z0-9._-]`
  whitelist strips every CJK/Arabic/Cyrillic/emoji character, so `"模型要睡覺"` reduced to the
  empty string and came back as `400 invalid notebook id … reduces to an empty token` — a message
  that says nothing about the name being the problem. `slug` now falls back to `nb-<sha256[:16]>`
  for any id the whitelist empties: deterministic, collision-resistant, inside the same whitelist,
  and affecting the FILENAME only (`Notebook.id` keeps what the user typed, and
  `list_notebook_summaries` already reported the stored id rather than the filename stem — a
  property it was given for exactly this reason). Verified end to end against the running server: a
  Chinese-named notebook accepts sources, lists under its own name, and lands on disk as
  `nb-55de69c77d45b935.json`. A genuinely empty id still 400s. **Deliberate consequence, not a
  regression**: `"!!!"` is an ordinary notebook now rather than a 400 (invariant 27's arm), since
  once a Chinese name had to work there was no principled line left between "punctuation only" and
  "non-Latin only" — the unhandled 500 that invariant was created to fix is still gone.

  **Editing the notebook-id box without pressing Open silently wrote to the previously-opened
  notebook**, with the box on screen showing a different name entirely — reported as "I can't
  create a second notebook without reloading the page", and visible in the user's screenshot as an
  error naming a notebook that was no longer in the box. Everything mutating acts on
  `state.notebookId`, which only `openNotebook` sets. Two fixes together: the box is rewritten from
  state on every switch so it can never disagree with what the app is acting on, and the wordmark
  is now a real button that starts an empty notebook. That also surfaced a latent bug it made
  one-click reachable — switching from a notebook with turns to an empty one left a blank chat
  panel with no placeholder, because `chat:turnAdded` hides it and nothing un-hid it.

- **A working session with the thing, turned into one slice.** Everything below was reported by a
  user driving the real product, and each item names what was actually broken rather than what was
  improved.

  **The highlighter strokes had silently stopped existing, and could never have come back on their
  own.** A citation was drawn as a stroke through the sentence it backs by searching the answer for
  the citation's `quote` — which works only while the answer and the source share a language. Since
  invariant 39 the prose follows the READER and the quote stays in the SOURCE's words, so the two
  never share a substring and no span was ever found. `schema.Citation.answer_span` (new, optional,
  backward-compatible) is the model's own pointer at the stretch of ITS OWN text a citation
  supports; `citations.locate_answer_spans` drops any span that does not occur in that prose
  verbatim, keeping the citation — the same coordinate-existence discipline invariant 5 applies to
  `source_id`/`locator`, aimed at the model's prose instead of at the corpus. `_citation_responses`
  now takes the exact string each artifact renders, so a chat answer, an FAQ item, a timeline event
  and a podcast utterance each check their span against their own text.

  **A source could not be removed**, and adding removal broke id numbering the moment it landed:
  `append_sources` numbered from `len(sources) + 1`, so deleting `s2` and appending produced a
  SECOND live `s3`. Reproduced before the fix. `notebook.next_source_id` derives from the max id in
  use — the same bug `_next_note_id` was written for (invariant 32) one field over. Nothing is
  renumbered on removal, which is what makes removal safe: a citation into a removed source comes
  back unverified with a reason rather than resolving to different text.

  **A pasted URL showed as a bare link.** `parsers/web.extract_preview` scrapes title/description/
  site from the html `parse_web` ALREADY fetched — one request, as invariant 1 requires — into
  `Source.preview`, which is display-only and never reaches the corpus blob. **`og:image` is
  deliberately absent**: rendering it makes the reader's browser fetch a URL the page author chose,
  turning every pasted link into a beacon, in exchange for a thumbnail.

  **The live ticker said far less than the sibling studios' feeds**, because
  `_translate_trace_event` emitted a fixed sentence per event type and threw the payload away. It
  now carries `{kind, primary, detail, meta}` — the model's own reasoning, the tool's name, the
  sub-model escalation's attempt number. The step's `output` is deliberately NOT streamed; its SIZE
  is, which is the part that says whether a step did much. `summary` is kept as the concatenation of
  the first two, so a consumer written against the old shape keeps working.

  **`⚠ instruction-like phrase matching '\bsystem\s*:\s*'` was shown to a person.** Invariant 6's
  flags gate nothing, so their entire value is whether a human can act on them — and a raw regex
  names an implementation detail and says nothing about what to do. Every pattern now carries a
  sentence. That same pattern was also measured firing on ordinary prose ("The operating system: a
  set of layers"), so it is anchored to a role label opening a line.

  **Renaming a notebook.** `PUT /notebooks/{id}/title` is a separate VERB from the model-generated
  `POST` — setting a title is an instant write that always succeeds, generating one is a run that
  can fail, take seconds and be superseded, and folding them together would give rename the failure
  semantics of a model call. `naming.normalize_title` is split out of `clean_title` because the two
  callers need opposite things from an unusable value: generation falls back to a derived label, a
  rename is REFUSED, since substituting a title for what someone typed would be the UI lying.

  **The picker.** Model-authored titles are not unique — a user hit three notebooks with
  near-identical generated names — so the list is ordered by file mtime and carries `updated_at`.
  `derived_title` (the same `fallback_title` the generate path uses, no model call) now appears in
  BOTH `NotebookSummary` and `NotebookResponse`, because the header and the picker row disagreed:
  one said "Untitled notebook" while the other showed a derived label for the same notebook.
  `GET /settings/choices` serves the settings page's dropdown values for the CONFIGURED provider —
  a voice name is provider-specific (invariant 43), and a second copy in JS would drift from
  `tts._LANGUAGE_VOICES`. Like `GET /settings` it never calls `_config()` (invariant 41).

  **Titling is LAZY now.** It used to fire from adding a source, which a user called too
  aggressive: pasting a link spent a model call naming something they had not started working on
  yet. `ensureTitle()` is called from the actions that already run a model. `derived_title` is what
  keeps an untitled-but-populated notebook from reading as "Untitled" in the picker.

  **Front end.** The right column is now a resizable, collapsible rail with four switchable views
  (Studio / Podcast / References / Notes), the shape `cloud.projectdiscovery.io` uses: drag the grip
  to size it, drag past the threshold to put it away. The two tab rows are structurally different
  (underline vs pill) because two identical rows said nothing about which contained the other. Two
  defects found while building it are pinned as source-tree assertions, since this project still has
  no JS test runner (invariant 29): a tooltip host that clips its own tooltip erases it outright
  (two real instances, one of which took out every tip inside the Sources card), and inverted
  hysteresis on the drag thresholds makes the panel flip state on every pointer event.

- **What three independent reviews then found, all of it fixed here.** Listed because each one is a
  defect this slice introduced, not a pre-existing one.

  **`promote_note` still numbered sources by length**, so the collision the fix above was written
  for was alive on the ONE path that makes a note citable (invariant 32): the corpus blob emitted
  one id twice and the promoted note was unreachable by any citation. Reproduced over real HTTP.

  **`extract_preview`'s regexes backtracked catastrophically.** A page of unclosed `<meta` tags took
  38 seconds at 19.7KB, cubic, with `re` holding the GIL the whole time — a one-request freeze of
  the entire server, reachable by anyone who can paste a URL into a no-auth API. Every quantifier is
  bounded and the input is windowed to the `<head>` now: a constant ~330ms whatever the input size,
  while a well-formed 681KB page with 5000 meta tags still parses in 0.019s.

  **`_citation_responses`' `prose` argument failed OPEN.** It defaulted to `""` and then skipped
  validation entirely when empty, returning the model's raw unchecked span — the opposite of what
  the docstring promised. It is required now. Worse, a reviewer removed it from all eight call sites
  — completely disabling the highlighter strokes — and the whole suite stayed green; two tests pin
  the wiring.

  **`remove_source` returned `False` on a miss**, and `mutate_notebook` writes unless the delta
  raises, so a 404-ing DELETE still saved the file and bumped the mtime the picker now sorts by.

  **The settings page offered languages the configured provider cannot speak** — Thai/Vietnamese/
  Indonesian to a chatterbox deployment, while hiding the eleven it can. Picking one persisted a
  GLOBAL `output_language` and then failed every `/audio` request. `supported_languages()` is on the
  provider now, where `default_voices` already lives (invariant 43).

  **The References view could not contain the citations that linked to it.** Every citation in a
  guide artifact or the podcast transcript was clickable and switched to a list built only from the
  overview and chat. It only looked like it worked when the same coordinate happened to be cited in
  chat too — which, since text and web sources all use locator `"whole"`, is most of the time.

  Also: three source-tree assertions were repaired after mutation testing showed they passed with
  their own documented defect reintroduced (the drag thresholds' state PAIRING, two hidden-toggled
  classes the harvester could not see, and every `data-i18n-tip` key); `normalize_title` now strips
  control characters; a malformed trace payload can no longer abort an SSE connection mid-stream;
  and a set of smaller UI defects — three tooltips lost while restyling the header, a duplicate
  translation key, a `t` shadowed in three closures, Escape-during-rename that could still commit,
  arrow keys silently rewriting a collapsed panel's width, `localStorage` written on every
  `pointermove`, and hover rules that were inert on the element they were pointing at.

- **Five things a user asked for after reading real answers on the page.**

  **Markdown is rendered.** Answers arrived full of raw `**bold**`, `## headings` and `- lists`,
  because the model writes markdown whether or not anyone asked. The renderer is hand-written and
  builds DOM nodes — no library, no HTML strings, the exception a sibling studio states outright
  for the reason that applies here too: every string came out of a model that has been reading
  source content an attacker may have written, and one missed `esc()` in a string-building renderer
  is an XSS sink. Headings, nested lists, blockquotes, inline and fenced code, tables, rules, bold
  and italic. **A link is shown but not clickable** — invariant 1 refuses to let the model reach a
  URL because a prompt-injected source could steer it into exfiltrating notebook contents, and an
  `<a href>` in an answer is that same hazard with the reader's click as the transport. The URL is
  visible so it can be copied deliberately.

  The renderer never creates a text node: it walks raw offsets and appends through `emit`, which
  owns citation splitting. That is what lets markdown structure and highlighter strokes compose — a
  stroke crossing an inline `**bold**` is split into fragments, and only the last carries the
  reference number. Verified against a real DOM shim under `node` before it was believed: nested
  lists land inside their `<li>`, a `<script>` in a code fence stays text, zero anchors created.

  **Every answer now suggests what to ask next.** `Answer.follow_ups` comes from the SAME run that
  wrote the answer, so it costs no extra model call; starter questions previously existed only on
  the overview, appearing once per notebook and never again. Not citation-grounded — a question is a
  prompt, not a claim. The overview keeps "Start with" and a turn says "Ask next", deliberately not
  unified: the overview's appears before any conversation exists.

  **The overview stopped covering the conversation.** It was a sibling above the thread with
  `max-height: 45%`, so it permanently owned half the chat column. It is the thread's first entry
  now and scrolls away as the conversation grows.

  **The References view is a list of rows again.** It rendered every quote as an always-visible
  blockquote, so one source cited eight times filled the column. Now: number, title, a hostname
  chip, the use count, one clamped line of the passage, everything else behind a click — the shape
  Kagi's assistant and Google's AI answers both use. And the part a user actually pointed at:
  pointing at a reference lights up the strokes it backs, pointing at a stroke lights up its row.

  **The run log is a timeline** — one rail with a node per step, the current one pulsing and open,
  past ones clamped and expandable, each timestamp carrying how long that step took. Four separate
  left borders read as four unrelated items; a rail reads as one process advancing.

  Also: the reference link under an answer gets its own line and real space above it.

- **What two independent reviews then found in that slice.** Both ran the real code rather than
  reading it — one fuzzed the markdown renderer against a DOM shim under `node` (~62,000
  documents), the other drove `app.js` in headless Chrome.

  **The reciprocal highlight had never worked, in this slice or the one that introduced
  `focusReference`.** `referenceKey` joined its coordinate with U+0000, and `CSS.escape` maps
  U+0000 to U+FFFD by spec — as does the CSS tokenizer parsing the selector — so every
  `[data-ref-key="..."]` lookup matched nothing at all. Measured in a browser; invisible to the
  Python suite and to any amount of reading. The separator is U+001F now.

  **A citation's reference number vanished whenever its span ended on markdown syntax the renderer
  drops** — a closing `**`, a backtick, a link's `](url)`. `isLast` was decided while emitting, and
  no emit ever reached the span's end in those cases, so the stroke got no number while the
  References panel numbered it anyway. Stamped after the render now, where every fragment is known.

  Also fixed: emphasis follows a flanking rule, so `3 * 4 * 5` and `my_var and other_var_name` are
  left alone; a table written directly under a sentence is no longer swallowed by the paragraph, and
  prose containing a pipe is no longer swallowed by a table; a list whose first item is indented no
  longer emits `<ul>` inside `<ul>`; the run log's step duration is visible text rather than a
  tooltip clipped by the log's own scroller, and the first row measures from the run's start;
  `is-current` is cleared when a run finishes; `.is-focused` and `.is-linked` are genuinely disjoint
  now rather than only claimed to be; the new pulse has a reduced-motion opt-out; opening a notebook
  no longer lands scrolled past the overview; and a markdown link's URL can actually be copied,
  which the tooltip alone never allowed.

  Three tests were widened after mutation testing walked past them: the navigable-link check missed
  `setAttribute("href")`, a template-literal `createElement(`a`)` and a `window.location`
  assignment, and nothing pinned the chat overview's position inside the thread.

- **`RN_MAX_ITERATIONS` is 25 and `RN_RUN_TIMEOUT_SECONDS` depends on how the model is served.** A
  user hit `502 ... timed out after 300.0s` on the subscription path, with a trace file holding one
  `run_start` and nothing else — cancelled before its first step ever returned. That path spawns a
  Claude Code CLI subprocess per LM call (invariant 35), so the default is 1800s there and stays
  300s for a direct API model. The step budget went from rlm-harness's own 10 to 25 because the
  failure modes are not symmetric: exhausting it loses a run already paid for, unused headroom costs
  nothing, and a runaway is bounded by the wall-clock timeout instead. A judgement, not a
  measurement about the ceiling — but what IS measured is that 10 was about to bind: an 8-source
  notebook's Summary took NINE main steps, one short of the old limit, having already spent three
  minutes of model time. The same overview's FAQ half died on the 300s timeout, which is why that
  notebook has a summary and no starter questions at all. The timeout error names the variable now,
  and an overview that comes back without suggested questions says so instead of rendering nothing —
  it read as the feature having been removed.

- **A model switch turned three budget defaults into real failures, and one of them was already
  written down in a sibling.** Pointing `RN_MAIN_MODEL` at a Qwen3 MoE behind a proxy made
  `GeneratePodcastScript` fail instantly with `RLMTaskError: Failed to produce a valid 'script'
  after 1 attempts` — a two-event trace, nothing to read, while Summary, FAQ and chat all worked on
  the same model.

  The cause was `max_tokens`, not the podcast. dspy reads `content` and DISCARDS
  `reasoning_content`, so a reasoning model's chain-of-thought is billed against a cap it never
  appears in; `ctx-distillery` documents that trap and recommends 16384, having watched a sibling
  hit it on its first live turn. Verified as a single-variable change here: same notebook, same
  model, same 146,284-character corpus, `max_retries` untouched — 8192 died at turn 0, 16384
  produced 8 utterances and 11 citations in 121.5s. The podcast went first because its instructions
  are the longest and its output schema the deepest.

  `max_retries` stays PINNED at 1. It was briefly raised on the argument that a turn-0 parse failure
  is transient and cheap to re-run; that is wrong, because the second attempt hits the same ceiling
  and fails identically — and every sibling pins 1 for the reason that a re-run also writes a second
  copy of the same failure into the trace. It is readable from `RN_MAX_RETRIES` now, so raising it
  is a deliberate act rather than a code edit.

  `worker.py` now carries the ROOT CAUSE across the process boundary. The wrapper named the symptom
  and the `AdapterParseError` underneath named the cause; diagnosing this took a trace dump and an
  in-process re-run when it should have taken reading the error.

- **Podcast generation says which of its two phases it is in, and a long wait says something new.**
  Only the script half is a traced, cancellable subprocess run; synthesis then happens in-process
  with no trace and no way to stop it, and the label said "Writing the script" throughout. A user
  also watched "waiting for the model's first response" for seven minutes and read it as a crash —
  nothing more CAN be observed before the model replies, so after 90 seconds the status says that,
  and points at Stop, instead of repeating a phrase that has already failed to reassure.

  The steps affordance survives a reload: `tickerLogs` lives for one page session, so every "N
  steps" pill vanished on refresh even though the trace file is still on the server and the stream
  endpoint replays it from the start. It loads on demand now, and says so honestly when retention
  has already collected the record.

- **What two more independent reviews found, both by running the code rather than reading it.** One
  monkeypatched `rlm_harness.configure` and drove a real worker subprocess; the other drove the page
  in headless Chrome and in jsdom.

  **The error-cause change deleted the diagnostic it existed to surface.** dspy orders
  `AdapterParseError.__str__` as adapter-name, then the WHOLE LM completion, then the
  expected/actual summary — so a head truncation drops the only two useful lines. Measured cutoff: a
  completion over ~534 characters. rlm-harness already ships `_short_error`, which head+tail elides
  with the same constant and whose docstring names this exact case; it is used now instead of a
  worse re-implementation. The output is bounded on BOTH halves too — an unwrapped
  `AdapterParseError` was producing a 20,000-character HTTP body.

  **The guards were on the wrong knob.** Both `RN_MAX_TOKENS` mutations — hardcoding the default,
  and deleting the forwarding line — survived the whole suite, while the pinned `max_retries` had
  two guards. The forwarding test is behavioural now and covers all five budgets.

  **`max_output_chars` was the fourth field of the same shape**, left at rlm-harness's 10000 while
  `ctx-distillery`'s own audit (which names exactly these two fields) had raised its own to 40000.
  It bounds how much of a REPL output reaches the planner's prompt, and every task here explores the
  corpus by `.find()`/slicing and prints spans — a truncated one costs an iteration to re-fetch.

  **Front end**: the podcast's new synthesis label was silently overwritten 20 seconds later by
  "waiting for the model's first response", and the 90-second tier then offered a Stop that was
  greyed out — reintroducing, in the same diff, the complaint that tier was added to fix. A disabled
  Stop was pixel-identical to a live one. Regenerating the overview mid-question deleted the
  question, its status and its Stop. And the stroke-numbering fix covered the chat thread only, so
  adding a turn left every podcast and guide stroke pointing at the wrong row.

  Also fixed: the guide cache lost `delete` when it moved onto `state`, so Studio's ↻ Regenerate
  threw `TypeError` and did nothing; an empty cached trace log counted as a cache hit, so a dropped
  stream left a permanent `0 steps` pill; `data-reference="0"` rendered a literal superscript zero;
  `raise X from None` had its suppressed context resurfaced; a falsy exception had its cause
  skipped; an `ExceptionGroup` swallowed the real fault; and an exception whose `__str__` raises
  would have killed the worker's only JSON line.

  **Six of twelve front-end mutations walked past the tests** — including `i + 1` → `i`, the exact
  off-by-one the numbering change exists to fix — because every assertion checked that a token
  appeared somewhere rather than what it did. They assert structure now.

- **Clicking a transcript timecode had silently stopped seeking, and it was a rename that did not
  reach the body.** Fixing a shadowed `t` (the i18n function) renamed the parameter of the podcast's
  `seek` to `seconds` and left `player.currentTime = t` behind — assigning a function coerces to
  NaN, so every seek did nothing, with valid syntax, a resolvable identifier and no error anywhere.
  `t` is now pinned as call-only: every occurrence in `app.js` must be a call, never a value.

  **Three layout defects in the same panel, each the consequence of the previous fix.** The
  utterance rows carried negative margins from when they were bare text, so inside the now-scrolling
  transcript every row was wider than its box and the whole thing gained a horizontal scrollbar. The
  transcript's fixed `22rem` (chosen when the podcast shared a column with two other sections) left
  a blank strip below it; `60vh` then made the panel taller than the column, so the column itself
  scrolled and took the heading away. Only a flex chain sizes this correctly, and the `display:
  flex` it needs on a `hidden`-toggled class is safe because a longer `[hidden]` selector outranks
  it. That flex column then stretched the download link and the steps pill to full width.

  **The Generate podcast button now has the overview's three states** — offer / quieter regenerate /
  regenerate-because-sources-moved — instead of one permanent primary button sitting above a player
  that already existed.

  Also: the answer-footer spacing added for chat answers was applying inside every transcript line;
  and two `forEach` parameters named `body` collided with the podcast panel's own local, which made
  the hidden-toggle tripwire flag `.podcast-body` — fixed by renaming the locals, which is what that
  test's own docstring prescribes for its known false positive rather than loosening the check.

- **A listening comparison retired an assumption, and the assumption was load-bearing.** The record
  said "a TTS voice cannot pronounce another script" — established for kokoro, and merely ASSUMED
  for `edge-tts`, the provider that actually ships by default. One hostile line synthesized through
  both settles it: Chinese prose carrying `NASA`, `Voyager 1`, `CVE-2026-1234`, `RAPTOR`, `harness`
  and a whole English clause took **8.2s / 81KB on edge-tts** and **273.4s / 749KB on chatterbox**,
  and edge-tts handled the mixed script — some pronunciations odd, none mangled.

  So `GeneratePodcastScript`'s rule to transliterate foreign proper nouns (acronyms included, no
  original in parentheses) was solving a problem the default provider does not have, while costing
  something real: `Utterance.text` is BOTH the transcript and what the voice reads, and a rewritten
  name is exactly the word a listener cannot look up when the audio is unclear. The rule is gone.
  Names stay as their source wrote them; numbers, dates and units still get spoken form, because
  those read aloud badly everywhere and nobody looks them up.

  Also recorded: chatterbox's position is the LOCAL/privacy option, not "the only one that handles
  mixed script" — 33x the wall clock and 9x the bytes is a trade a reader whose sources cannot leave
  the machine should be able to make, and one nobody should be made to take by default.

- **Two defects a user found in one notebook, and the smaller-looking one was the dangerous one.**

  **The notebook was titled by transliterating its first source's paper title**, because the titler
  reads a WINDOW of the corpus and that window was `blob()[:4000]` — a prefix of a string that
  concatenates sources in order. Source one alone was 69,859 characters, so sources two, three and
  four were never seen. `Corpus.excerpt(n)` gives every source an equal share from its opening
  lines; verified against the reported notebook, where the old prefix saw `s1` and the new excerpt
  sees `s1 s2 s3 s4`. **Language resolution read the same prefix**, which is worse than a bad title:
  a notebook whose later sources are in another language would resolve the wrong one, and that guess
  is then persisted (invariant 39). The prompt now names "translate source one's title" as the
  failure mode instead of leaving it to be inferred.

  **Raw `[[SRC:s1|whole]]` markers were on screen in the overview** — the model wrote the coordinate
  into its own prose, which the rules never covered because they only ever said where a marker
  BELONGS. Stripped at the display boundary, so nothing stored is rewritten and every notebook
  already on disk is fixed with no migration. The same strip runs on `answer_span`, or a span
  carrying a marker silently stops matching and every highlighter stroke vanishes.

  Also measured, in answer to a question rather than a bug report: the two podcast hosts speak at
  different speeds (5.43 vs 4.84 characters per second, consistent across every line) because they
  are two different edge-tts voices and this project sets no rate at all.

- **The podcast got a length, and then the length broke it in a way worth recording.** Three tiers
  (`short`/`default`/`long`, ~3-5/8-12/18-25 minutes), chosen at generation time and carried by both
  entry points. The tiers are numbers because the previous instruction — "a natural episode length
  given how much the sources contain" — measurably did nothing: four episodes all landed near three
  minutes and the eight-source notebook produced the shortest.

  `long` then failed outright: written as one code block it exceeded the per-call generation cap and
  the salvaged fragment parsed as an empty object. dspy named the cause in a warning. The fix was
  NOT to raise the cap — it was to build the script across REPL turns, which is what the sandbox is
  for. Same corpus, same budget: 80 utterances and 44 citations.

- **A user asked where the markers were coming from, and the answer was worse than a render bug.**
  One episode had 20 markers written across 19 of its 47 utterances and ZERO citations: the model had
  abandoned the `citations` field entirely and was citing by writing coordinates into the prose. So
  the voices read them aloud, the transcript had no references, and the display-layer strip added
  earlier made the evidence vanish rather than recovering it. Three layers now: a pre-SUBMIT
  validator that rejects a marker in prose, the display strip, and a strip before synthesis.

  That validator started life on the podcast alone, because that is where the failure made a noise —
  `GenerateSummary` had produced the same defect silently, four markers in an overview. It is shared
  by all six tasks now, from one factory.

- **This project had no `rlm_harness.skills` at all, which a user had to point out.** It is
  `rlm-harness`'s own progressive-disclosure mechanism for downstream RLMs — distinct from the
  Claude Code skills a coding agent reads and this task never sees — and four sibling projects
  already shipped the same `discovery="inject"` shape.

  Two skills so far: `podcast-craft` (tension, pacing, the reveal — from the NotebookLM team's own
  account of how the format is made, plus the one technique this project cannot copy and why) and
  `corpus-navigation` (every measured way a run has been lost here: the one-code-block truncation,
  printing what you are accumulating, a truncated span costing a whole turn, the nine-of-ten step
  budget, and the marker incident). Nothing was moved out of the four Guide prompts, which are
  entirely must-apply — inventing craft to have something to move would have been worse than an
  empty directory.

  `podcast-craft` also records a mistake made while writing it: its no-disfluencies rule was
  justified with a quote attributed to the NotebookLM team that was actually their hosts' show note,
  and the guest contradicts it when asked directly. It came from a fetched summary nobody opened the
  transcript to check. The rule now stands on this project's own measurement — a Chinese sentence
  with six characters of written filler synthesized to 4.08s against the plain sentence's 2.90s.

- **The independent review of this batch found the marker net could destroy the episode it was
  protecting.** A line that is nothing but a coordinate strips to empty or to a lone piece of
  punctuation, and edge-tts raises on punctuation-only text — a 502 that discards the whole
  paid-for run. In the incident that motivated the strip, those nineteen utterances were merely
  garbled; with the strip they would have been a lost episode. It falls back to the original text
  when nothing speakable survives.

  The same review found the strip's punctuation tidy running over the whole string rather than the
  hole the marker left, which normalises text that never had a marker and — because the strip
  early-returns on a marker-free string — makes the prose and the `answer_span` disagree, so every
  highlighter stroke vanishes. And in the validator itself: `model_fields` read off the instance
  (a silent fail-open under pydantic 3), dict fields skipped, a rejection message giving impossible
  advice when the offender is a citation field, and the skills catalog opened without being closed.

  Two behaviours that had shipped undocumented are written down now: the display strip's
  whitespace-before-punctuation rule, and the podcast length being remembered per browser in
  `localStorage` rather than on the notebook — a per-reader habit, the same split invariant 48 draws
  for the interface language.

  The CLI half of the length feature was not pinned at all: the review changed `target_length` to a
  hardcoded `"default"` and renamed the tier choices, and the whole suite stayed green both times,
  because the assertions read the flag's own help text. They read the parser and drive `_cmd_audio`
  now.

- **A fact-check of the documentation against the code found a fix that had only been written
  down.** `apply_skills` gated the skills CATALOG on a manifest existing but appended the
  `read_skill` TOOL whenever the directory did — so an empty skills directory handed the model a
  tool whose description points at a list that is not in its instructions, while AGENTS.md said
  that was prevented. The code does it now and a test pins both directions.

  Five other doc claims did not survive the same pass and are corrected rather than quietly
  dropped: the podcast length was described as browser-local "never sent to the server" when it is
  sent on every generate and reaches the prompt (only the REMEMBERING is browser-local); the
  marker-strip fallback was justified partly by a chatterbox failure mode that does not exist
  (its runaway ceiling floors at one second, so a short line burns no re-rolls and never raises);
  the marker count disagreed with four other files; invariant 20 was cited for a feature-parity rule
  it does not state; and the skills work was framed as content MOVED out of prompts when almost
  nothing was — both skills are new material, and the two rules that appear in a prompt and a skill
  are there deliberately, the prompt stating a must-apply rule and the skill carrying its reason.

- **A user's overview came back with five red "unverified" badges, and the cause was not what the
  badge said.** Every web source is one block with locator `whole`; the model had written the
  section heading it was citing into `locator` instead. The chat turns on the same notebook were
  12/12 clean, so this was a per-task behaviour, not a corpus problem.

  The pre-SUBMIT validator now checks each citation's coordinate against the markers that actually
  occur in the blob this run was given — the same ground truth the server checks afterwards, applied
  while the model can still fix it. Its rejection shows a REAL coordinate, because a message that
  only says "wrong" invites the model to compose a different sentence.

  That needed a per-run value, which a class-level tool list cannot hold, so the six tasks share one
  base class now. It deleted six byte-identical `__init__`s and six per-task validator declarations
  — and exposed six test functions that asserted "no network tool is ever registered" against a
  ClassVar that is now empty, i.e. against nothing.

  The reader-facing half was fixed too: a reference card now explains what "unverified" MEANS (the
  coordinate could not be found — the quote may be fine and filed at the wrong address), shows the
  server's own reason, and no longer renders an empty box for the one citation someone most wants to
  inspect. A long locator can no longer stretch the card until the rest of the row falls out of it.

- **`long` podcasts could not finish.** One 502'd at the 300s default backstop with a trace holding
  three events: started, read two skills at 6.8s, then nothing for 293 seconds until `killpg`. An
  ordinary chat answer on the same notebook and model took 77s across 4-5 turns, one of them 54s
  alone — so the tier shipped unable to complete under its own default. The backstop scales with the
  requested tier now; a runaway chat turn stays bounded where it always was.

- **A Traditional-Chinese interface produced an English notebook title.** The one place the reader
  had actually said which language they read was never sent — language resolution weighed the OS's
  `Accept-Language`, the sources, and any typed questions. The interface language is a fourth signal
  now, ranked above `Accept-Language` because it was chosen rather than inherited. The two settings
  stay separate: a Chinese interface over English papers is still expressible, just stated rather
  than default.

  And no artifact translates a proper noun any more. "Trinity" stays "Trinity" — a translated name
  is the one term a reader then cannot search for. One shared rule, in every task and the titler.

- **The run's reasoning moved out of the chat bubble into a Trajectory drawer.** The inline step log
  put the planner's own prose inside the answer, which a user reported as unreadable and
  space-consuming. Full parity with a sibling project's own trajectory drawer, at the user's
  explicit choice: turn nav, a tool timeline whose segment width tracks real elapsed time, a detail
  pane, search, and a replay that dwells on each turn for the time it really took.

  The decomposition is server-side and keeps the run's two clocks apart — per-turn timing is
  reported only when the trace was live-stamped, never invented for an older one. It reads a trace
  that is still being written, which is the point for a run that takes minutes. Verified with a DOM
  shim under `node` against a real 12-turn trace, since this project has no JS test runner.

- **Scrollbars are themed.** The UA paints them from the OS theme, not the page's, so the dark theme
  had a near-white bar down the middle of every scroller. Both spellings ship, because neither
  covers the other's browsers.

- **A citation's hover says what the source IS.** It read `s1 · whole` — the interface's own filing
  system. Clicking one now OPENS its reference card at the quote that was clicked, rather than
  scrolling to a collapsed row and leaving the reader to work out which of its quotes was theirs.

- **The independent review of this batch found the podcast-timeout fix revertible with a green
  suite.** Its tripwire asserted the tier factors were monotonic, which is true of an all-equal
  table — i.e. of no scaling at all, the exact state that 502'd the reported episode. Flattening it
  to `{1.0, 1.0, 1.0}` passed 539 tests. The same review disabled descent into nested models in the
  new coordinate check and the suite stayed green too, which would have silently unguarded FAQ,
  Timeline and the podcast — three of the six tasks, including the one the marker check had already
  spent a slice living only on.

  Three real UI defects came out of the same pass. The drawer's live poll rebuilt everything every
  four seconds, throwing away the reader's selection and search box — in the one case reading a
  live trace exists to serve. The backdrop kept eating clicks for the 280ms of its own fade-out, a
  short-lived form of the failure invariant 36 records. And five new controls carried both
  `data-tip` and the native `title`, which invariant 47 had removed for showing two tooltips.

  Every one of those is pinned now, and each mutation was replayed to confirm it fails — including
  one where the first fix was itself defeated: a token check on `markWantedQuote` passed with the
  function's body replaced by `return;`.

- **The build-across-turns rule reaches all six tasks now, not just the podcast.** It is must-apply
  by its own account — skipping it loses the whole run to a truncated reply — and it lived in one
  prompt while the other five relied on an OPTIONAL skill a model may never open. Invariant 65 had
  recorded that as the single unclean line of the prompt/skill split; this closes it.

  Worded conditionally, because the rule is not "always accumulate": a short answer built across
  turns wastes the step budget just as surely as a long one written in a single reply loses the
  run. The podcast keeps its tier-specific warning (60-90 utterances is a fact about that task) and
  no longer restates the mechanic — one copy, pinned by a tripwire over all six.

- **A user asked whether the chat should be frozen while an overview regenerates. It should not —
  but the question found a real bug next door.** `renderChatOverview` clears the element that holds
  the run's progress dot and its only Stop, and adding or removing a source calls it. So a source
  added mid-generation wiped both, while a deliberate decision one line away (not bumping the
  generation token, so a paid-for run is never stranded) kept the run alive with no way to see or
  cancel it until it landed minutes later. Two individually-right decisions that had never been
  checked together. The panel is owned by its run now, exactly as invariant 60 already does for a
  pending chat turn.

  A notebook switch has to RELEASE that ownership rather than only strand the run, or the new
  notebook keeps the old one's status node — and a pre-existing sibling turned up in the same
  function: the "superseded" note was written into `#chat-overview` even when the reader had
  switched notebooks, overwriting a different notebook's overview with a note about a run it never
  started.

  The original question's answer: the two runs are independent, both writes land under the
  per-notebook lock, and neither repaint can now delete the other's run. Blocking the composer for
  a multi-minute run would cost more than it protects.

  **REVERSED later in this same slice** — see "The chat composer is frozen while an overview
  generates" below. The technical half of this paragraph still holds (nothing was ever at risk);
  what changed is that the user asked twice, and whether two runs LOOK like they are fighting is
  their call rather than a question the locking answers.

- **An overview could only be regenerated if something had INVALIDATED it.** A user asked how to
  press "↻ Regenerate" while looking at an overview whose five citations had all failed coordinate
  verification — the stored form of the defect fixed earlier in this slice. The button was gated on
  the overview being stale or incomplete; their sources had not moved and the FAQ half had
  succeeded, so it was not on the page at all. An artifact that is current and complete but simply
  wrong is a real state, and it was the one with no way out.

  It is always offered now. The flag picks the label and the weight rather than the existence:
  quiet when nothing is wrong, because regenerating costs two real model runs and must not be the
  loudest control on a panel that already holds what it makes; louder and explicit when stale or
  incomplete. The same three-state shape the podcast's own button has had since it was persisted.

- **"完成" appeared next to a live Stop button, and the pairing was the tell.** `/overview` runs two
  tasks and its ticker follows only the summary; forwarding that run's terminal event made
  "Finished" the whole action's headline while the FAQ half was still going and the POST had not
  returned. Measured on the user's own run: a 63KB summary trace beside a 226-byte FAQ trace whose
  worker was still alive. Invariant 60's rule broken by a second RUN rather than by a phase — so the
  fix reuses the same `setPhase` seam that invariant added, naming the second half honestly and
  keeping Stop available, because that half really is cancellable.

- **The chat composer is frozen while an overview generates.** Asked for by the user twice, and not
  because of a race: the runs are independent, both writes land under the per-notebook lock, and
  neither repaint can delete the other's run. Nothing was ever lost. The reason is that a question
  asked into a thread whose overview is being rewritten reads as two things fighting whether or not
  they are — a product decision, recorded as one so it does not get simplified away later as
  redundant with the locking.

  The composer only. Clearing the conversation was the offered alternative and is the one thing not
  to do: it would destroy history to signal a transient state.

- **A user pressed the steps pill and got the old inline reasoning log back.** Their browser was
  running the previous `app.js`; the server was serving the new one. Starlette's static files carry
  an ETag but no `Cache-Control`, so the browser was on heuristic caching — and this is a zero-build
  app whose filenames carry no content hash, so there was no cache-busting URL either. The assets
  now say `no-cache`, which means revalidate rather than don't store: unchanged assets still cost
  one conditional request and a 304 with no body.

- **The steps pill still expanded inline after a hard reload, and the cache was not the reason.**
  There are TWO "⌁ N steps" affordances: the live one during a run, and the persisted one under a
  finished artifact — which is the one a reader presses most, because most of the time the run is
  over. Only the live one had been moved into the Trajectory drawer. The previous entry's
  cache-revalidation fix is a real improvement and was not the cause of this.

  Both open the drawer now. `.ticker-detail`/`.ticker-row` and their CSS are gone, and the
  invariant-36 tripwire — which had `.ticker-detail` as one of its two anti-vacuity sentinels —
  gained a route for a bare `hidden` attribute in the markup. That is the ordinary spelling of the
  very attribute the tripwire polices, and all four of its existing routes were blind to it.

- **The Trajectory drawer was cramped, and the first pass is the lesson.** The sibling's data model
  had been ported faithfully and then a UI was invented for it: 0.75rem rows, a 0.85rem-tall bar
  strip, `flex-grow` segments that divided the strip into slivers. A user put the two side by side
  and rejected it — every fact was present and none of it was legible.

  The structure and proportions are ported now: a header carrying the task name and the run's
  totals, transport as one segmented control, the timing note as a labelled callout, timeline
  BLOCKS with icon/label/duration that keep a readable minimum width and scroll rather than squash,
  a turn nav of cards each with a preview line and a duration bar, and a detail pane that sets the
  model's reasoning as prose rather than as another monospace dump.

  The worker also records what the run was configured with — model names and budgets, never
  credentials — because the "Initial state" panel was built from a meta holding only the task name,
  which the header already showed.

- **A timeline segment was slicing its own label in half.** Three stacked lines in a 72px box with
  `overflow: hidden`, and at the browser's default line-height they measured 74.3px. A test now
  recomputes that sum from the stylesheet and fails when it exceeds the box, so the next size change
  cannot reintroduce it quietly.

- **"Initial state" carries the run's real metadata now.** It held the task name — which the drawer
  already shows as its headline — and nothing else. It carries the models, the budgets, the corpus
  size and every short scalar input the run was given: the question, the resolved language, the
  requested podcast tier. The corpus text never goes in, only its size; credentials never go in at
  all. Verified against a real run rather than assumed.

- **The timeline's sizing was reimplemented from memory and wrong twice, in opposite directions.**
  `flex-grow` against the strip's total made slivers; a fixed width then left a run with one tool
  call sitting at 316px beside empty space, which a user reported. It is `flex: <duration> 0
  <floor>px` now — the sibling's own sizing, read out of its `renderTimeline` rather than guessed
  from its stylesheet. Grow fills a short run's strip; the floor keeps a fast call legible and lets
  a long run scroll instead of squashing.

  A segment's label is the TARGET now (`corpus-navigation`), not `skill corpus-navigation` — the
  family is already the icon and the colour. Its offset and owning turn moved to the detail pane,
  where clicking a segment lands anyway and where nothing clips them: a tooltip on a segment is
  clipped by the segment AND by the scroller around it.

- **The model was numbering its own citations.** One overview carried `[1]`..`[8]` in its prose
  while holding six citations, so the page showed two numbering systems and they disagreed. The
  interface numbers them; the prompt now says so. Prompt-only on purpose — `arr[1]` is ordinary
  prose here, so a display-layer strip would corrupt real text to tidy a number.

- **A chat answer can be regenerated now.** The overview, the podcast and every Guide kind had a way
  to be redone; a chat answer did not, so one the reader was unhappy with was permanent. It sits in
  the row that answer's other affordances already occupy, at the same quiet weight — re-answering
  costs a full model run and should not be the loudest thing under an answer.

  The LAST turn only, and that is correctness: every later answer was produced with this one in its
  history, so redoing a middle turn would leave the answers after it derived from a conversation
  that no longer exists. The server re-checks inside its lock and appends instead of replacing when
  the question no longer matches, so a regenerate that lands late can never overwrite a turn it did
  not mean to.

- **The empty "Initial state" now names which empty it is.** A user asked whether the
  "recorded before the app saved these details" branch could go away once the old traces were
  deleted. It cannot: the trace file is reserved before the run spawns, so a run opened in its first
  moments — or one whose spawn failed, or one killed instantly — has a real file with zero events.
  What had to go was the WORDING, which named a cause the cleanup makes unreachable.

- **A conversation can be cleared.** Turns were append-only — a source could be deleted and a note
  could be deleted, but a chat could only grow — so "start over" was impossible, and regenerate
  reaches the last answer only (every later one was produced with it in `history`). Sources, notes,
  the overview and the podcast are kept, and the confirmation says so: losing sources is the fear a
  destructive control in the chat panel invites.

- **A tooltip at the left edge of the chat was clipped**, photographed arriving with its first
  characters sliced off. The default tip anchors right, so a 15rem panel on a left-edge control
  extends off the scroller — which clips horizontally, because an `overflow-y: auto` box computes
  `overflow-x` to `auto` too. Anchoring it into the space the control actually has is the fix, and
  this stylesheet already did exactly that elsewhere. Deleting the tooltips was the first instinct
  and would have removed working information to avoid a positioning bug.

- **An independent fact-check of this batch's documentation against its code found nine problems,
  and the sharpest was a claim in an OLDER invariant that today's work had quietly falsified.**
  Invariant 48 still said the interface language "is never sent to the server, and never reaches a
  prompt" — both halves untrue since it became a language-resolution signal earlier in this same
  slice. `i18n.js`'s own header had been rewritten for exactly that; the invariant had not.

  Also corrected: a sentinel list miscounted as two when it has six; a stylesheet comment whose
  arithmetic said 64.6px where recomputing from its own values gives 66.7px (the fix was right, the
  sum beside it was not); two contradictory CHANGELOG entries on freezing the chat composer, with
  nothing saying the first had been reversed; an invariant asserting a root cause that a LATER
  invariant records as having been wrong; an enumeration of "three callers" that was five, listed
  one of them twice, and disagreed with the code comment beside it; a `tickerLogs` comment keeping
  a paragraph the next paragraph retracts; and `web/DESIGN.md` — tracked and shipped in the wheel —
  still documenting an element that was deleted.

  And one new test did not pin what it claimed: inserting `return;` at the top of `syncClearBtn`
  left the suite green, because every substring it checked still matched the dead code below. That
  is the identical defeat this batch already recorded fixing for `markWantedQuote`, made again in
  the very next test written.

- **An independent review of the clear-conversation slice found three real defects in one handler,
  all by driving the shipped source under stubs rather than reading it.** Clearing while a question
  ran deleted the turns and then let that question's answer be appended to the empty list, so the
  conversation came back with one entry; the repaint took the running question's row and its only
  Stop with it; and nulling the pending turn made the ask's own error handler throw on a null, so a
  run that failed after a clear showed nothing at all. Clearing is disabled during a run now, and
  the handler carries the pending row and the notebook generation the way every other awaiting flow
  here already did.

  Its test was hollow in both directions — deleting every call site (leaving the control permanently
  hidden, the feature entirely dead) and inverting the visibility condition both left 563 tests
  green. It pins the condition as an expression, the five call sites by count, and each of the three
  handlers by name now. The first rewrite of that assertion matched a DIFFERENT init function's
  `notebook:switched` subscription, which is its own small lesson: in a file where four inits spell
  the same event, a test that says "the handler" has to say which.

- **`line-length = 110` was never enforced.** It is a formatter setting, ruff's default rule set has
  no `E501`, and the name scrub duly left a 157-character line that `check` passed. AGENTS.md said
  the command enforced it; it says what is true now. Twenty over-long lines predate this and
  rewrapping them plus enabling `E501` is a follow-up, not a silent bundled edit. *(Done later in
  this same section: the rule is selected via `extend-select` and all 19 offenders are rewrapped.)*

- **The Chinese interface carried English dashes, which is a translation artifact rather than a
  translation.** A user photographed "PDF、TXT 或 Markdown——一次一個檔案。" — the dash renders as a
  long rule and reads like a glyph run that failed to resolve. Fifteen strings had it, in three
  different spellings within one file: `——`, a SPACED `——` (the dash is already full-width, the
  spaces are the English habit) and a half-width `—`. Chinese punctuation carries the same joins a
  dash was standing in for: a comma continues, a semicolon separates two complete thoughts, a colon
  labels. A test now fails on any dash inside the string table, and only inside it — the file's own
  comments are English prose and keep theirs.
