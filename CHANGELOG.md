# Changelog

All notable changes to Penumbra are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Penumbra is a personal knowledge hub built on [`rlm-harness`](https://github.com/qazbnm456/rlm-harness). You capture sources of any kind, ask questions grounded in them with citations you can check, and take a distilled artifact away.

Each entry states what the product does now and why. The reasoning behind each rule lives in [`docs/invariants/`](docs/invariants/), and the rulebook index is [`AGENTS.md`](AGENTS.md). Nothing has been released yet, so everything below is in `[Unreleased]`.

## [Unreleased]

### Added

#### Capture: the Horizon (Tier 0)

- The Horizon is the default screen. You paste a link or text, drop files, or upload them, and each capture lands at once as a node you can find again later. An orbit is a place you go into, and a node is filed into one or more orbits by copying it (invariant 78).
- The Horizon is an index, not a corpus. Nodes live in a SQLite index plus one JSON file each, every write is a SQL delta, and nothing at Tier 0 assembles a blob, so the Horizon can hold thousands of items without touching the orbit size cap (invariants 8 and 78).
- A capture always lands. Submitting creates a `queued` node before anything is fetched, intake runs one item at a time, and a failed parse becomes a `failed` node that keeps its reason, so a bad link can never stall the queue behind it (invariant 79).
- Distillation writes a short title, summary, tags and entities for each capture so it can be found again. It is off by default and bounded by an environment-only cap, because summarising every capture of a 200-bookmark import would silently spend 200 model calls. A failed summary leaves the node usable (invariant 80).
- Search reads titles, summaries, tags, entities and origins. Several words must all match, and a query with no spaces (such as Chinese) is matched as one substring.

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

- A zero-build web UI served by the API is the product's main surface (invariant 29). It has a warm paper theme and a dark theme, Literata for reading and Public Sans for the interface, one copper accent, and an English and a Traditional Chinese interface.
- Every long-running action shows that it is running, with elapsed time and a Stop, and starts only on an explicit press (invariant 47).
- Below 640px wide (a narrow desktop window or high zoom), an orbit shows one panel at a time through a Sources, Chat and Studio tab row.
- An empty orbit offers Paste a link, Paste text and Upload a file as its first move. An answer's references link, steps pill and Regenerate share one footer row. The Studio's tab strip stays pinned while its column scrolls.
- The source viewer is headed by the page's own title, which the source-detail response now carries.
- Server-written sentences are translated in the interface: injection-scan flags, a citation's "why unverified" reason and source kinds all follow the interface language, and the steps pill and the missing-audio line follow a live language switch. Markdown `~~strikethrough~~` renders as a deletion. The printed "unverified" tag uses weight instead of a synthesised CJK italic.
- A settings page covers presentation choices only: interface and output language, podcast voices, and the auto-summary toggle. Safety bounds stay in the environment (invariant 41).

#### Server, CLI and deployment

- `penumbra serve` starts the API and the web UI on loopback. Every request needs the API token the server prints, and a non-loopback `--host` warns, because the token authenticates the app and there is still no per-user authorization (invariants 25 and 77).
- `serve` quits on one Ctrl-C or a terminal hangup even with a run in flight, and it kills the run's whole process group, so no worker keeps billing after the server is gone (invariant 22).
- A model string prefixed `claude-agent-sdk/` runs that role on the user's Claude subscription (invariant 35).
- A `Dockerfile` carries the two binaries no Python manifest can express, `deno` and `tesseract`. `playground/` builds a static, backend-free demo of the web UI from recorded orbits.
- The CLI can ingest, ask, generate guides and podcasts, and write a trace with `--trace`. It cannot reach the Horizon or manage orbits.

#### The desktop app

- `desktop/` is a Tauri 2 app for macOS 13 or later, Windows and Linux. It bundles a relocatable Python with Penumbra installed and the deno binary, so nothing else needs installing. A relocatable interpreter was chosen over a freezer such as PyInstaller because dspy and litellm import by name at run time. The installers are about 800 MB unpacked, almost all of it the dependency set.
- The shell starts `serve` on a remembered loopback port with a per-launch token (passed in the URL fragment, and blanked out of the access log wherever a URL must still carry it), shows the web UI in a native window, lets the page receive dropped files, saves downloads, prints with File > Print and opens other sites in the system browser. The web UI gets no IPC (invariant 81). Restarts are serialised and repeated presses fold into one, so a Restart pressed during a start can no longer pair an old token with a new server.
- If the app is killed rather than quit, the server shuts itself down when its stdin pipe closes; measured before the fix, it stayed up and could keep billing a run nobody could stop.
- Model settings live in a configuration file the File menu opens in a text editor (no app claims `.env`, so handing it to the OS did nothing), and errors that name an `PN_*` setting say where to find it in the app. A fetch refused because a fake-IP proxy rewrites DNS now says so and names `PN_FETCH_ALLOW_CIDRS`, instead of the generic "not one this can fetch". The menu and the splash follow the OS language.
- The builds are unsigned: macOS carries an ad-hoc signature on the app and every bundled binary, Windows and Linux none. A manually run CI workflow checks the shell and builds every installer on all three platforms; the Windows and Linux builds have not been run yet.

### Changed

- **The project is Penumbra now, and it was called rlm-notebook.** It stopped being a NotebookLM-style notebook with a web server: it is a personal knowledge hub whose server exists only for the desktop app, on loopback. The vocabulary changed with it: a notebook is an **Orbit**, the Inbox is the **Horizon**, the package and command are `penumbra`, the API lives at `/orbits` and `/horizon`, and every setting is `PN_*` instead of `RN_*`.
- Nothing is lost in the rename. On its first start `penumbra` moves `notebooks/` to `orbits/` and `inbox/` to `horizon/`, and renames the one database column that carried the old name; it never merges into a folder that already exists. A leftover `RN_*` variable is named in a warning and ignored rather than silently honoured. The desktop app moves its data folder to the new identifier (`tw.boik.penumbra`) and rewrites its configuration file with the new setting names. The on-disk hash prefix for orbits whose names reduce to nothing (`nb-<hash>`) is unchanged, because it is part of existing file names. Prompts the model reads say "collection", a word it understands without context.
- The agent guide is `AGENTS.md`, an index of 80 invariants with one argument file each under `docs/invariants/`. `CLAUDE.md` is a one-line bridge.
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

- Concurrent source ingestion, because PDFium crashes under it (invariant 3).
- A Traditional Chinese OCR recognition model and a layout-detection model as shipped defaults, because measured accuracy did not justify them.
- A phone layout. This is a desktop application, and the server binds loopback.

### Known limitations

- Guides are not persisted, and a guide run that outlives an orbit switch cannot be recovered.
- The in-memory run maps have no multi-worker story, and the API has one shared token with no accounts.
