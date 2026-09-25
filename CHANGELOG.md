# Changelog

All notable changes to Penumbra are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Penumbra is a personal knowledge hub built on [`rlm-harness`](https://github.com/qazbnm456/rlm-harness). It runs as a desktop app that lives in the notch: you throw anything into the Horizon, see how it connects on a star map and in knowledge graphs, ask questions grounded in it with citations you can check, and take a distilled artifact away.

Each entry states what the product does now and why. The reasoning behind each rule lives in [`docs/invariants/`](docs/invariants/), and the rulebook index is [`AGENTS.md`](AGENTS.md). Nothing has been released yet, so everything below is in `[Unreleased]`.

## [Unreleased]

### Added

#### Capture: the Horizon (Tier 0)

- The Horizon is the default screen. You paste a link or text, drop files, or upload them, and each capture lands at once as a node you can find again later. An orbit is a place you go into, and a node is filed into one or more orbits by copying it (invariant 78).
- The Horizon is an index, not a corpus. Nodes live in a SQLite index plus one JSON file each, every write is a SQL delta, and nothing at Tier 0 assembles a blob, so the Horizon can hold thousands of items without touching the orbit size cap (invariants 8 and 78).
- A capture always lands. Submitting creates a `queued` node before anything is fetched, intake runs one item at a time, and a failed parse becomes a `failed` node that keeps its reason, so a bad link can never stall the queue behind it (invariant 79).
- Distillation writes a short title, summary, tags and entities for each capture so it can be found again. It is off by default and bounded by an environment-only cap, because summarising every capture of a 200-bookmark import would silently spend 200 model calls. A failed summary leaves the node usable (invariant 80).
- Search reads titles, summaries, tags, entities and origins. Several words must all match, and a query with no spaces (such as Chinese) is matched as one substring.

#### Asking the Horizon

- You can ask a question over everything you kept, one tag or one entity, or a tag or entity within one orbit, not only inside an orbit. The first press decides locally, at no cost, which captures the question will read and says how many; the second press asks (invariant 47).
- The captures are picked with a full-text index inside the Horizon's own database. Chinese, Japanese and Korean text is indexed as overlapping character pairs instead of through a dictionary: jieba's default dictionary split 關係 on Traditional text, every dictionary variant split 海馬迴 so a search for it found nothing, and FTS5's own trigram tokenizer cannot match a two-character word at all. The index is derived from the captures and rebuilt on demand (invariant 78).
- A scope that fits is read whole. A larger one reads what the question's words found, best first, up to `PN_HORIZON_ASK_CHARS` (1,000,000 characters, never above the orbit cap) and `PN_HORIZON_ASK_ITEMS` (40). When the words find nothing, it reads the newest captures and says so. Both bounds are set in the environment only (invariant 41).
- Each answer is kept in the Horizon's ask history with the captures it read. Reopening one checks its citations again against the captures as they are now, so a removed capture leaves its citations unverified. A question about one orbit is still asked inside that orbit and joins its conversation.
- Horizon asks run under the reserved handle `horizon-ask`, so the live ticker, Stop, the Trajectory drawer and recovery after a reload work exactly as they do in an orbit. No orbit id may start with that handle.

#### The star map and the knowledge graph

- The Horizon opens as a star map: the Horizon is the black hole at the centre with the captures filed nowhere circling it, each orbit is a planet whose moons are its captures (copper once summarised, grey before), closer rings mean more recent activity, and a dashed bridge joins two orbits whose captures name the same entity. The map moves: planets travel their rings, moons circle their planet and the accretion disk turns, and all of it holds still while the pointer or focus is on the map, or when the system asks for reduced motion. A header toggle switches to the list, and the choice is remembered in the browser.
- Selecting a planet opens a card with its sources, its most-named entities, a way in, and a button that summarises only that orbit's unsummarised captures, which names the number of model calls before the press and shows progress with a Stop while it runs (invariants 47 and 80).
- An orbit opens as its knowledge graph: its captures' entities are the nodes, two entities are joined when one capture names both, and the line thickens with every capture that does. Tags are lenses above the graph that light up what carries them. The side panel lists the captures behind a selection, and the header toggle switches to the three columns. An orbit with no sources yet opens in the columns, where they are added.
- Relations come only from what a summary wrote, never from a model call made to draw the picture. An unsummarised capture names nothing, so it is counted in its own box with the spend button rather than drawn as if it were linked (`topology.py`, invariant 78).
- A summary now counts named concepts as entities (a theory, a method, a stage, a part of the body) as well as people, places and products, and keeps tags for broad subjects. That is what gives the graph nodes worth drawing.

#### Summaries, concepts and filing

- A short capture is summarised by one call that reads all of it, up to 12,000 characters, instead of its first 4,000. A longer one is summarised by an RLM run in a worker subprocess that reads the whole document from a map of its sections, the way a planner is handed a compact summary of a tree; each entity it names carries the coordinate of a block that names it, checked before SUBMIT and again by the host, which drops any it cannot find (invariants 21, 67 and 80).
- The summarise buttons state the cost before the press, as a range when long captures are waiting (`/horizon/distil/estimate`), and Stop ends a long-document run at once rather than after it finishes.
- Concept alignment runs once at the end of a summary pass the reader pressed (never after the automatic one, which runs on the intake thread and also leaves long captures for a press), over the entity names no alignment has seen, and decides which are the same thing (Matthew Walker and 馬修·沃克). The answer is an alias table every reader applies: the star map, the graph, the tag and entity lists and scoped asks. Stored summaries are never rewritten, so a merge is undone with one press in the graph's side panel, and an undone pair is not proposed again (invariant 80).
- Filing suggestions are computed locally: a capture in no orbit, or only in the landing orbit, is offered for the orbit whose captures share at least two of its entities, or one entity and one tag. Nothing is filed until the reader presses Add, and a declined pair is not offered again.
- The notch island shows three facts on hover in one glyph: an arc for how much of the Horizon is summarised (it breathes while a pass runs), the ring inside it turning faster while something is being read, and four dots for filing suggestions waiting. A screen reader hears the same facts when they change.

#### Local relations

- Settings has a Local relations row: one press downloads an embedding model (multilingual-e5-small, int8, about 130 MB) pinned to one revision and checked against its SHA-256, with progress and a Stop; another deletes it and every stored vector. Nothing is bundled, so a reader who never turns it on pays nothing (invariant 82).
- With it on, every capture is embedded on this computer in the background, free and without a model call, and the knowledge graph draws a dashed line between captures whose text is alike, including an unsummarised capture, which is otherwise not linked to anything until it is paid for. Filing suggestions can offer an unsummarised capture for the orbit of the filed capture it most resembles.
- The signal is kept weak on purpose, because similarity on this model sits in a narrow band and leans towards text in the same language: a line needs a score of 0.86 and mutual nearness, text under 40 characters is not compared, and a similarity suggestion ranks below one by shared entities.

#### Asking from anywhere

- The ask panel rests as a handle at the foot of the star map, the list and the knowledge graph, and slides up when the pointer nears the bottom edge. At rest it is only a grip that breathes, and while it is open the map's legend and summary note fade out beneath it. Its scope follows the selection on screen: everything, a tag lens, a planet, or an entity or tag inside the orbit on screen. An orbit chip asks straight into that orbit's conversation in the three columns; every other scope is a Horizon ask.

#### Orbits and grounded chat

- Ingestion covers text, web pages, PDFs (including scans, through local hybrid OCR that ships on by default) and YouTube captions. Ingestion runs on the host and one source at a time, because PDFium is not thread-safe: four PDFs ingested concurrently crashed the process (invariants 3, 7 and 33).
- OCR reads two-column scans in reading order, and a garbled PDF text layer is detected by comparing it with OCR rather than by a threshold, since no threshold separated good pages from mis-decoded ones (invariants 73 and 74).
- An orbit is one JSON file. Every write re-reads it inside a per-orbit lock and applies a delta, which fixed a real case of concurrent writes silently dropping data (invariant 34). Source ids are never reused, so a saved citation can never start pointing at different text after a source is removed (invariants 12 and 50).
- Questions are answered by an RLM run in an isolated subprocess and a Pyodide sandbox, with the previous turns as context only, never as a source of facts (invariants 9, 11 and 21).
- Answers come back in the reader's language while citation coordinates stay exactly as the source has them. The interface language is a separate browser preference, and it counts as a signal when the orbit's output language is first chosen (invariants 39, 48 and 69).
- Each answer carries follow-up questions from the same run, at no extra cost (invariant 56). A chat answer can be regenerated, and a conversation can be cleared.
- Notes are free text that can be promoted into a real, citable source. A note on its own is never cited (invariant 32).
- An orbit names itself from its sources, can be renamed at any time, and can be deleted (invariants 37 and 53).

#### Citations you can verify

- Every grounded task echoes opaque `[[SRC:<id>|<locator>]]` coordinates, and a validator checks each citation's coordinate against the corpus before the run may submit (invariants 4, 13, 66 and 67).
- Verification proves that a coordinate exists, not that the quote supports the claim, and nothing in the product says otherwise. A citation that no longer resolves, for example after its source was removed, is shown as unverified on every surface and in every export (invariant 5).
- Citations are numbered by the interface, never by the model, and the numbers follow reading order on every surface: answers, the overview, the four guides and the podcast transcript (invariants 48.5 and 49).
- Pointing at a citation lights up its reference and the reverse. Opening a citation marks the cited words in the References card's passage and scrolls them into view. Clicking a source opens its full text in a viewer (invariant 58).

#### Studio

- The overview is persisted on the orbit and marked stale when the sources change, instead of disappearing (invariant 38). Its "Start with" questions invite the first question and give way to the latest answer's "Ask next".
- Four guide kinds (summary, FAQ, timeline, insight) are generated on demand. They live in page memory only, and a result produced while the sources changed is kept but marked stale.
- The Audio Overview writes a two-host script with an opening, a plan and exactly one close, at a chosen length, and synthesises it on the host. Long scripts are built across REPL turns. The episode is persisted as one file per orbit, plays in the page with a subtitle-style transcript, and can be downloaded (invariants 14, 42, 44, 45, 63 and 64).
- TTS works out of the box with `edge-tts`, which needs no key. Chatterbox is the local option because it handles English, Chinese, Japanese and Korean with mixed-in foreign words, and the voice follows the output language (invariants 15, 40 and 43).
- The Trajectory drawer shows a run's reasoning: each planner turn in the model's own words, a tool timeline scaled to real time, the token budget and what the validator rejected (invariants 70 and 75).

#### Taking the artifact out

- Copy puts Markdown with its numbered references on the clipboard, from any answer, the overview or a guide. Export downloads the whole orbit as one Markdown file. Printing drops the application chrome, starts with the orbit's title and appends the reference list the printed numbers point to.
- Exported and printed references keep the "unverified" label, so an artifact never presents a failed citation as verified.

#### Web UI

- A zero-build web UI is the desktop app's workspace, and `penumbra serve` serves the same UI from a source install (invariant 29). It has a warm paper theme and a dark theme, Literata for reading and Public Sans for the interface, one copper accent, and an English and a Traditional Chinese interface.
- Every long-running action shows that it is running, with elapsed time and a Stop, and starts only on an explicit press (invariant 47).
- Below 640px wide (a narrow desktop window or high zoom), an orbit shows one panel at a time through a Sources, Chat and Studio tab row.
- An empty orbit offers Paste a link, Paste text and Upload a file as its first move. An answer's references link, steps pill and Regenerate share one footer row. The Studio's tab strip stays pinned while its column scrolls.
- The source viewer is headed by the page's own title, which the source-detail response now carries.
- Server-written sentences are translated in the interface: injection-scan flags, a citation's "why unverified" reason and source kinds all follow the interface language, and the steps pill and the missing-audio line follow a live language switch. Markdown `~~strikethrough~~` renders as a deletion. The printed "unverified" tag uses weight instead of a synthesised CJK italic.
- A settings page covers presentation and behaviour choices only: interface and output language, local relations, podcast voices, the auto-summary toggle and where new captures land. Keys and safety bounds stay in the configuration file or the environment (invariant 41), and in the desktop app the page says so.

#### Server, CLI and deployment

- `penumbra serve` starts the API and the web UI on loopback. Every request needs the API token the server prints, and a non-loopback `--host` warns, because the token authenticates the app and there is still no per-user authorization (invariants 25 and 77).
- `serve` quits on one Ctrl-C or a terminal hangup even with a run in flight, and it kills the run's whole process group, so no worker keeps billing after the server is gone (invariant 22).
- A model string prefixed `claude-agent-sdk/` runs that role on the user's Claude subscription (invariant 35).
- A `Dockerfile` carries the two binaries no Python manifest can express, `deno` and `tesseract`.
- The CLI can ingest, ask, generate guides and podcasts, and write a trace with `--trace`. It cannot reach the Horizon or manage orbits.

#### The desktop app

- `desktop/` is a Tauri 2 app for macOS 13 or later, Windows and Linux. It bundles a relocatable Python with Penumbra installed and the deno binary, so nothing else needs installing. A relocatable interpreter was chosen over a freezer such as PyInstaller because dspy and litellm import by name at run time. The installers are about 800 MB unpacked, almost all of it the dependency set.
- The shell starts `serve` on a remembered loopback port with a per-launch token (passed in the URL fragment, and blanked out of the access log wherever a URL must still carry it), shows the web UI in a native window, lets the page receive dropped files, saves downloads, prints with File > Print and opens other sites in the system browser. The web UI gets no IPC (invariant 81). Restarts are serialised and repeated presses fold into one, so a Restart pressed during a start can no longer pair an old token with a new server.
- If the app is killed rather than quit, the server shuts itself down when its stdin pipe closes; measured before the fix, it stayed up and could keep billing a run nobody could stop.
- Model settings live in a configuration file the File menu opens in a text editor (no app claims `.env`, so handing it to the OS did nothing), and errors that name a `PN_*` setting say where to find it in the app. A fetch refused because a fake-IP proxy rewrites DNS now says so and names `PN_FETCH_ALLOW_CIDRS`, instead of the generic "not one this can fetch". The menu and the splash follow the OS language.
- **At rest the app is the notch.** Penumbra runs as a background app, with no Dock icon and no menu bar, and its only presence is a black shape in the MacBook notch (the top centre of a screen without one, the left edge on Windows and Linux) that is indistinguishable from the notch until the pointer rests on it. Dragging a file or a link toward it opens it before the pointer arrives, and dropping swallows the item: it falls into a ring, the ring pulls while the server works, and it flares when the item has landed or turns red and shakes for a file type it cannot read. It says nothing in words; a screen reader hears each state instead. It opens only for a real drag-and-drop (on macOS, a drag that changed the drag pasteboard, started off the island and moved), so clicking the notch, selecting text or moving a window near it never opens it as a drop target. It follows the notch when displays change, and the pointer watch slows to a few checks a second when nothing is near.
- Clicking the notch, or launching Penumbra again from Finder or Spotlight, opens the workspace, and the Dock icon and menus come back while it is open. Closing the workspace returns the app to the background; right-clicking the notch opens, configures, restarts or quits it. A second launch on Windows or Linux brings the running app forward instead of starting another.
- Everything captured lands somewhere it can be asked about: a capture that has not been filed by hand is also filed, once parsed, into an automatically created first orbit titled in the reader's language. It stays in the Horizon either way. Filing stops before the first orbit would pass the corpus cap, and the setting "Where new captures land" turns it off.
- The configuration file's template lists every setting an error message in the app can name, with its default, and links to the full reference online instead of a repository file a desktop user does not have. A file created before this keeps its old contents until it is deleted and opened again. The app installs the `api` extra only, so the Claude subscription path and the Chatterbox voice need a source install, and the docs and messages say so.
- A setting the server cannot run with reaches the page with its reason and where to change it, and is written to the server log. It used to read "its log has the detail" over a log that had nothing, so a typo in the configuration file was invisible. In the app, the settings page says where the model and key are set, and a lost connection asks for File > Restart Server rather than a token the app never printed.
- The builds are unsigned: macOS carries an ad-hoc signature on the app and every bundled binary, Windows and Linux none. A manually run CI workflow checks the shell and builds every installer on all three platforms; the Windows and Linux builds have not been run yet.

### Changed

- **The project is Penumbra now, and it was called rlm-notebook.** It stopped being a NotebookLM-style notebook with a web server: it is a personal knowledge hub whose main surface is the desktop app, with its server on loopback. `penumbra serve`, the CLI and the container remain for source installs. The vocabulary changed with it: a notebook is an **Orbit**, the Inbox is the **Horizon**, the package and command are `penumbra`, the API lives at `/orbits` and `/horizon`, and every setting is `PN_*` instead of `RN_*`.
- Nothing is lost in the rename. On its first start `penumbra` moves `notebooks/` to `orbits/` and `inbox/` to `horizon/`, and renames the one database column that carried the old name; it never merges into a folder that already exists. A leftover `RN_*` variable is named in a warning and ignored rather than silently honoured. The desktop app moves its data folder to the new identifier (`tw.boik.penumbra`) and rewrites its configuration file with the new setting names. The on-disk hash prefix for orbits whose names reduce to nothing (`nb-<hash>`) is unchanged, because it is part of existing file names. Prompts the model reads say "collection", a word it understands without context.
- The agent guide is `AGENTS.md`, an index of the invariants with one argument file each under `docs/invariants/`. `CLAUDE.md` is a one-line bridge.
- OCR moved to `rapidocr`, which unblocks Python 3.13 and 3.14. `pymupdf` was replaced by `pypdfium2` because its only licences were AGPL or commercial.
- `rlm-harness` is pinned to 1.10.0, and the worker uses only its public API.
- Budgets were sized against measured distributions: `max_tokens` is 32768 because a smaller cap cut replies off mid-JSON, the step budget is 25, and the run timeout is 300s for API models and 1800s on the subscription path, scaled up for long podcasts (invariants 59 and 68).
- Regenerate bypasses the model cache, so it actually produces a new run.
- Every RLM task carries `rlm_harness.skills`. Anything that would corrupt the output if skipped stays in the prompt (invariant 65).

### Fixed

These are the few failures that shaped the current design. Smaller fixes are not listed.

- A run's state was repeatedly lost, duplicated or misplaced when the page repainted, a run failed, or the reader switched orbits or reloaded. Now:
  - Each run owns its status row and its Stop.
  - A result lands only in its own orbit and its own tab.
  - Stop or a failure keeps the previous result.
  - A lock is released only by the run that holds it, and the composer stays locked while either the overview or a question runs.
  - A run found still going after a reload keeps a working Stop.
  - Stopping a question keeps the previous answer's follow-ups and Regenerate, and focus lands on a sensible control instead of the page body.
  - Every control comes back once its run has ended.

  An independent sweep of 60 combinations (run kind, context change, outcome) found no stuck or wrongly unlocked control (invariants 47, 60 and 71).
- Deleting an orbit is refused while any work on it is in flight, including audio synthesis. An orbit that disappears mid-synthesis takes its audio with it, so a later orbit of the same name is never served someone else's episode.
- Removing a source re-verifies every saved citation on screen right away, not only after a reload.
- A stored desktop layout choice (the collapsed Studio) no longer breaks narrow windows, and tooltip and control styles no longer override each other because of CSS source order.
- Dark-theme printing produced cream text on white paper; print now always uses the light palette.
- Cancelling a run called `os.killpg`, and `serve` set a SIGHUP handler; neither exists on Windows, so a cancel raised and `serve` crashed at startup there. Cancellation now kills the process tree portably (`runner.kill_tree`).
- Five `margin: -var(...)` declarations were invalid CSS and silently dropped, including the one centring the podcast scrubber's thumb; a test now rejects the pattern.
- A PDF that failed to parse reported the server's temporary file path; the error now names the uploaded file.

### Security

- The SSRF guard is re-checked on every redirect hop, and operators behind a fake-IP resolver can carve out a range with `PN_FETCH_ALLOW_CIDRS` (invariants 2 and 76).
- The chat task has no network tool, `add_sources` accepts only http(s) URLs, and no upload surface can read a server path (invariants 1, 26 and 30).
- Source previews never reference an image, so a pasted link cannot turn the reader's browser into a beacon (invariant 51).
- Model-written Markdown is rendered by a DOM builder with no `innerHTML`, and links in answers are shown but not clickable (invariant 55).
- Injection-scan flags are shown but never block a run (invariant 6).

### Decided against

- A public demo page. A static, server-free replay of the web UI (`playground/`) ran at `boik.tw/rlm-notebook`; it showed a NotebookLM-style product that Penumbra no longer is, so the page was taken down and the builder removed.
- Concurrent source ingestion, because PDFium crashes under it (invariant 3).
- A Traditional Chinese OCR recognition model and a layout-detection model as shipped defaults, because measured accuracy did not justify them.
- A phone layout. This is a desktop application, and the server binds loopback.
- A graph drawn from sources added straight into an orbit. Only captures filed through the Horizon carry entities, so such an orbit's graph says there is nothing to draw and points to the columns.

### Known limitations

- Guides are not persisted, and a guide run that outlives an orbit switch cannot be recovered.
- The in-memory run maps have no multi-worker story, and the API has one shared token with no accounts.
- Traditional and Simplified spellings of the same word do not match each other in Horizon search, and a Horizon ask stands alone, with no follow-up thread. The Horizon's find box still matches summaries, tags and origins by substring; the full-text index serves asks.
