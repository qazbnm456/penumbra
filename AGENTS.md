# rlm-notebook: agent guide

`rlm-notebook` builds on [`rlm-harness`](https://github.com/qazbnm456/rlm-harness). You paste in sources of any kind (text, web pages, PDFs including scanned ones), ask questions grounded in them with citations you can verify, and take a distilled research artifact away. See `README.md` for the overview.

`rlm-harness` comes from PyPI, pinned to an exact version in `pyproject.toml`. To develop against a local checkout, install it editable over the top:

```
uv pip install -e ../rlm-harness
```

This file is the index of the rulebook: one entry per invariant, stating what must hold and the one thing that would stop you breaking it. The argument behind each rule lives in [`docs/invariants/`](docs/invariants/), one file per invariant. `CHANGELOG.md` records what the product does now and why, as conclusions organised by topic.

## Verify

- `uvx ruff@0.16.0 check .` lints the code. `line-length = 110` is enforced by selecting `E501` through `extend-select`. Never use `select`, because it replaces ruff's defaults, and a hand-written list pulled in `E402` and broke the deliberate `importorskip` lines in the suite. The ruff version is pinned so a new ruff release cannot turn CI red on its own.
- `uv run python -m pytest -q` runs the whole suite offline. `test_task.py` drives a real `dspy.RLM.aforward` through `rlm_harness.testing.ScriptedInterpreter` and `scripted_lm`.
- `test_api.py`, `test_api_inbox.py` and `test_distil_live.py` need the `api` extra and are silently skipped without it, so a bare `uv sync` looks greener than CI. CI runs `uv sync --extra api` once. `tests/test_runner.py` imports only the standard library and `rlm_notebook.runner`, so its tests, including invariant 22's grandchild-kill tripwire, run without the extra.
- The reverse trap applies to `chatterbox`, which CI does not install. No test may `importorskip` a package from an extra CI skips; `tests/test_tts.py` fakes `chatterbox.mtl_tts` and `soundfile` through `sys.modules`. Check this with a meta-path blocker rather than by trusting a docstring.
- `node` must be on `PATH`. `tests/test_readable_error.py` and `tests/test_web_behaviour.py` run functions out of `rlm_notebook/web/app.js` instead of asserting on its text, because a source-text assertion cannot see whether code is reachable. Without `node`, every test in both files fails rather than being skipped, so a local run can never look greener than CI. CI installs it with `actions/setup-node`.
- A live run also needs real model credentials and a Deno sandbox (`brew install deno`). Do not run it in CI; it costs money.
- Before claiming done, run both commands and paste the output.

## Scope note

What exists:

- Ingestion of text, web pages, PDFs (with local hybrid OCR) and YouTube captions.
- Citation-grounded chat over a persistent multi-turn `Notebook`, stored as one JSON file with no database.
- A Notebook Guide (`guide.py`: summary, FAQ, timeline, insight) and an Audio Overview (the `audio.py` script plus `tts.py` synthesis).
- An HTTP API (`api.py`, the `api` extra) with a live reasoning-trace stream and a Trajectory drawer.
- A web UI (`rlm_notebook/web/`) that is a real end-user product. It is the only way an artifact leaves the product: Copy (Markdown) on an answer, the overview or a guide, a whole-notebook Markdown export, and a print stylesheet that appends the reference list.
- `inbox.py`, Tier 0: a global capture Inbox (a SQLite index plus `inbox/nodes/<id>.json`) whose nodes are filed into notebooks (invariant 78). `intake.py` is its serial capture queue (79), and `distill.py` is the separate summary pass (80). All three are reachable at `/inbox/*` and from the web UI, where the Inbox is the default screen.

The API is the only place a run is isolated in a subprocess (`runner.py` and `worker.py`); `cli.py` runs in-process.

`rlm-notebook serve` starts the API and the web UI on loopback by default (invariant 25). The `Dockerfile` carries the two system binaries no Python manifest can express: `deno`, which every live run needs (invariant 9), and `tesseract`, the OCR fallback (invariant 7). `playground/` builds the same web UI into a static, backend-free demo from recorded notebooks; it has its own `README.md` and `smoke.mjs`, and CI runs neither (`.github/workflows/ci.yml` is pytest and ruff only).

Still unbuilt. Do not assume any of these exist because a design discussion mentioned them:

- The four guide kinds are not stored on a notebook; only the overview is (invariant 38). No guide is citable in a later `ask` unless it is promoted through a note (32).
- There is no multi-worker `uvicorn` story for the in-memory maps: `_ACTIVE_RUNS`, `_RUN_PROCESSES`, `_BUSY`, `_DISTIL`, `_CANCELLED_BEFORE_SPAWN`, `intake._SHARED` and `inbox._INITIALIZED`. The notebook file and the Inbox database are safe across processes; those maps are not.
- The API has one shared token and no accounts, sessions or per-user authorization (25, 77).
- `cli.py` cannot reach the Inbox (78, 79, 80), and it has no notebook-management verbs: no list, rename or delete. The API and the web UI have all three.
- Folders and archives cannot be captured, because invariant 26 keeps local paths out of the API and the native shell that would supply them is unbuilt.
- The Tauri desktop shell and the browser extension are unbuilt, so every capture today is a paste, a drop or an upload in a browser tab.
- Word, Slides and Docs native formats are not parsed, and full audio transcription is not done. YouTube captions do ship.

## Invariants: do not break

Each entry states the rule and the one thing that would stop you breaking it. The argument, the evidence and the traps live in [`docs/invariants/`](docs/invariants/), one file per invariant under the same number. Read that file before overturning, narrowing or simplifying a rule: a rule without its argument is easy to talk yourself out of. If the code contradicts either file, flag it as drift instead of picking a different design.

Each new piece of knowledge belongs in exactly one place:

| | goes to |
|---|---|
| The rule, and the sentence that stops you breaking it | this index |
| Why it holds, what it costs, what a later reader will try instead | `docs/invariants/<n>-<slug>.md` |
| What the product does now and why, as a topic-organised conclusion | `CHANGELOG.md` |

This index does not grow. An entry that has gained a second paragraph has taken on something that belongs in one of the other two files. On a sibling repository that made the same split, the indexed section stayed near 5,100 tokens while an unindexed section beside it grew to about 55,600.

1. **No fetch or network tool is ever registered on the chat task's `RLMTask(tools=…)`.** An instruction hidden in a source could otherwise steer the model into sending the notebook to a URL the SSRF guard cannot recognise as hostile. ([why](docs/invariants/01-no-network-tool-in-chat-repl.md))

2. **`parsers/web.py` re-validates the SSRF guard on every redirect hop, not just the requested URL.** A safe URL can redirect to a loopback or metadata address, and the default opener follows it unchecked. ([why](docs/invariants/02-ssrf-guard-revalidated-per-redirect.md))

3. **Ingestion runs on the host and serially: never inside the sandbox, never in a thread pool.** PDFium is not thread-safe; four PDFs ingested concurrently crashed with `rc=134` while 614 tests stayed green, because none drove two PDFs at once. ([why](docs/invariants/03-ingestion-is-host-side-and-serial.md))

4. **The corpus blob uses `[[SRC:<id>|<locator>]]` markers, and every citation-grounded task's instructions teach the model to treat them as opaque and echo them verbatim in a `Citation`.** Without an explicit rule the model has no reason to keep an ad hoc marker intact, and `citations.py` has nothing to verify against. ([why](docs/invariants/04-citation-markers-are-opaque-coordinates.md))

5. **`citations.py` verifies that a coordinate exists, never that the content is faithful.** No docstring, log line or UI string may imply the stronger guarantee; that gap is the grounded-but-unverified failure found in NotebookLM itself. ([why](docs/invariants/05-citations-verify-coordinates-not-faithfulness.md))

6. **`injection_scan.py`'s flags are deterministic and additive, and they gate nothing.** They are a transparency mechanism; wiring them to refuse a run would turn a deliberately imprecise regex into a gate. ([why](docs/invariants/06-injection-flags-are-advisory.md))

7. **OCR ships enabled by default, not merely pluggable and off.** `pypdfium2` replaced `pymupdf` over a real AGPL conflict, and `ocr_provider` has no consumers even though it is validated on read. ([why](docs/invariants/07-ocr-ships-enabled-by-default.md))

8. **`corpus.py` caps the size of the assembled blob and fails loudly past it.** The single-blob-as-REPL-variable design has a real memory ceiling, and the cap is what prevents a mysteriously slow chat turn later. ([why](docs/invariants/08-corpus-blob-size-cap-fails-loudly.md))

9. **`AnswerQuestion` always runs in the `pyodide` sandbox, and `NotebookConfig.from_env` refuses any other `RN_INTERPRETER` value instead of silently overriding it.** An operator who set `RN_INTERPRETER=local` believes something about the run that a silent correction would make false. ([why](docs/invariants/09-answerquestion-always-runs-in-pyodide.md))

10. **A notebook id is sanitised (`notebook.slug`) before it becomes a filename, and an id the whitelist empties falls back to a content hash instead of being rejected.** An unsanitised id becomes a traversal segment, and the `nb-<sha256>` fallback is what lets a notebook named in Chinese exist at all. ([why](docs/invariants/10-notebook-ids-are-sanitized-filenames.md))

11. **`history` (earlier turns) is context only, never a source of facts or citations.** A past answer that was wrong, or a source removed since, must not be inherited by a new answer. ([why](docs/invariants/11-history-is-context-not-a-source.md))

12. **Extending a notebook with `--source` dedupes by origin and never reassigns an existing source's id.** A source already cited in a saved turn must never have its id repointed at different text. ([why](docs/invariants/12-source-ids-are-never-reassigned.md))

13. **Every citation-grounded `RLMTask` takes its citation-marker and validate-before-submit instructions from `instructions.py`, never from a hand-copied paragraph.** A wording fix must never land on one task's local copy, so there must be no local copy. ([why](docs/invariants/13-grounded-tasks-share-one-instruction-set.md))

14. **TTS synthesis (`tts.py`) runs on the host, on an already generated and validated `PodcastScript`; it is never a tool the model can call, and `GeneratePodcastScript` (`audio.py`) does not depend on `tts.py`.** Synthesis is a real network call, and the model's job is done long before any audio exists. ([why](docs/invariants/14-tts-is-host-side-never-a-tool.md))

15. **The default TTS provider (`RN_TTS_PROVIDER=edge-tts`) needs no API key or paid account, so `rlm-notebook audio` works out of the box.** Ship a working default, not just an interface, and keep the provider list in one place, because a second list drifts. ([why](docs/invariants/15-default-tts-provider-needs-no-key.md))

16. **`PodcastScript.utterances` may legitimately be empty, and `cli._cmd_audio` says so explicitly instead of printing nothing.** Silently printing nothing was a real bug in `Timeline.events` and `FAQ.items` before it could be one here. ([why](docs/invariants/16-an-empty-podcast-script-says-so.md))

17. **`EdgeTTSProvider` synthesises one utterance at a time (one voice per `edge-tts` call) and concatenates the raw MP3 streams without re-encoding.** This deliberately avoids an `ffmpeg` or `pydub` dependency for what would only be a gapless-playback nicety. ([why](docs/invariants/17-edge-tts-concatenates-without-reencoding.md))

18. **The Audio Overview has a fixed cast of two hosts, `host_a` and `host_b` (`schema.Speaker`), not freely named per episode.** It keeps `Utterance.speaker` a closed enum that citations and voice mapping can rely on; `config.tts_voice_map` hardcodes both keys with no tripwire. ([why](docs/invariants/18-the-podcast-cast-is-two-fixed-hosts.md))

19. **`cli._cmd_audio` resolves the TTS provider before the potentially expensive script-generation call, not after.** The original order wasted a real model call whenever `RN_TTS_PROVIDER` was misconfigured. ([why](docs/invariants/19-resolve-the-tts-provider-before-the-model-call.md))

20. **`ingest.py` and `notebook.py` (`is_url`, `ingest_one`, `ingest_new`, `load_or_create`, `ingest_sources_for`, `append_sources`, `mutate_notebook`) are shared by `cli.py` and `api.py`, and neither entry point depends on the other.** A fix to source handling cannot land on only one of them. ([why](docs/invariants/20-shared-ingestion-module-for-both-entry-points.md))

21. **Every API request that runs an `RLMTask` does so in an isolated subprocess (`runner.py` and `worker.py`), never in the server process.** `worker.py` is the only place an `RLMTask` runs, so a crash takes down a subprocess and never the server. The guarantee is about execution, not imports. ([why](docs/invariants/21-api-runs-every-task-in-a-subprocess.md))

22. **Cancellation calls `killpg` on the whole process group (spawned with `start_new_session=True`), not just the worker's PID.** A stuck Deno grandchild must not survive as an orphan; a test spawns a real grandchild and confirms it dies. ([why](docs/invariants/22-cancellation-kills-the-process-group.md))

23. **`api._ACTIVE_RUNS` is a single-process, in-memory map with one slot per notebook id.** Both halves are documented limitations, not silent bugs: there is no multi-worker story, and a notebook has one cancellable slot. ([why](docs/invariants/23-active-runs-is-one-slot-per-notebook.md))

24. **Every `SystemExit` a request handler can reach is turned into an HTTP 500 instead of escaping.** An unhandled `SystemExit` in a handler is a crash, not an error response. The rule is the invariant, not the current list of places it applies. ([why](docs/invariants/24-systemexit-never-escapes-a-handler.md))

25. **The API has no authorization of any kind (authentication is invariant 77), so `rlm-notebook serve` binds 127.0.0.1 and a non-loopback `--host` warns.** The token authenticates the app, not a person, so every holder is fully privileged over every notebook. ([why](docs/invariants/25-the-api-has-no-authorization.md))

26. **`add_sources` accepts only http(s) URLs, never a local file path, unlike `cli.py`'s `--source`.** The attack was reproduced end to end: `POST {"sources": ["/etc/passwd"]}` read the file and echoed it back through a citation that passed verification. ([why](docs/invariants/26-add-sources-refuses-local-paths.md))

27. **Every endpoint that resolves a notebook by id catches both `pydantic.ValidationError` (a corrupted file, 409) and `ValueError` (an id `notebook.slug` reduces to nothing, 400).** Without both, an unhandled `ValueError` escapes as a raw 500. ([why](docs/invariants/27-notebook-lookup-catches-both-error-types.md))

28. **`cli._GUIDE_TASKS` and `api._GUIDE_TASKS` are two independent registries kept in sync by the tripwire `test_api.py::test_guide_task_registries_stay_in_sync_between_cli_and_api`, not by shared code.** Invariant 20 explains why `api.py` does not import `cli.py`. ([why](docs/invariants/28-guide-registries-kept-in-sync-by-tripwire.md))

29. **The web UI (`rlm_notebook/web/`) is a real end-user product, not a replay-only trace console like the sibling projects' `studio/`.** It rests on five rules for the live trace stream and on never using `innerHTML`, and its assets must live under `rlm_notebook/web/` or they vanish from the wheel. ([why](docs/invariants/29-the-web-ui-is-a-product-surface.md))

30. **No upload surface reopens invariant 26's local-path ban: not `sources/upload`, not `add_sources`'s `texts`, not `/inbox/upload`, not the fetch inside `parse_web`.** The size cap is checked before FastAPI parses the body, and `max_upload_bytes()` is deliberately not a `NotebookConfig` field. ([why](docs/invariants/30-upload-and-paste-do-not-reopen-the-path-ban.md))

31. **An endpoint that returns a whole document is a deliberate decision, stated openly. There are three: `sources/{source_id}`, the trace pair (29) and `/inbox/{node_id}/source`.** Before the first one, no caller could read more of a source than a citation's short `quote`. ([why](docs/invariants/31-the-source-text-endpoint-is-a-new-exposure.md))

32. **Notes (`schema.Note`, `Notebook.notes`) are free, uncited text, grounded and citable only once promoted into a real `Source`.** A note carries no citations and is never re-verified; note ids come from the highest live id, because length-based ids let two live notes share one. ([why](docs/invariants/32-notes-are-uncited-until-promoted.md))

33. **YouTube ingestion (`parsers/youtube.py`) fetches captions only, never the video or audio stream.** A video without captions is a loud ingestion error, and `CaptionError` subclasses `ValueError` so both call sites already catch it. ([why](docs/invariants/33-youtube-ingestion-is-captions-only.md))

34. **Every write to a notebook goes through `notebook.mutate_notebook`, which re-loads the file inside a per-notebook lock and applies a caller-supplied delta, never a snapshot read earlier.** A stale snapshot and interleaved critical sections are two distinct faults, and a lock alone would not have fixed the first. ([why](docs/invariants/34-every-write-goes-through-mutate-notebook.md))

35. **A model string prefixed `claude-agent-sdk/` runs that role on the user's Claude Pro or Max subscription, through an LM that `config.setup` injects into `configure`'s `main_lm=` and `sub_lm=` seam.** `rlm-harness` 1.10.0 routes on the same prefix itself, so the injection decides which LM wins rather than making it work at all; do not restore the old claim that `configure` ignores the prefix. ([why](docs/invariants/35-the-subscription-path-needs-an-injected-lm.md))

36. **An element in `rlm_notebook/web/` that is toggled with `hidden` never gets an author `display` rule without a matching `[hidden]` rule, and `tests/test_web_assets.py` fails the build if one does.** An author `display` beats the browser's `[hidden]` rule regardless of specificity; this shipped broken twice, and no other layer here can test it. ([why](docs/invariants/36-hidden-toggles-need-a-matching-hidden-rule.md))

37. **A notebook's `id` is a handle and `schema.Notebook.title` is the label people read. The UI mints the id itself and never asks for one.** Requiring a name before the first source turned the first interaction into a naming puzzle. Titling is lazy and never overwrites. ([why](docs/invariants/37-the-notebook-id-is-a-handle-not-a-label.md))

38. **The chat overview is the one guide artifact stored on a notebook (`schema.Overview`, `Notebook.overview`), and it is marked stale rather than deleted when the sources change.** It has three states, not two; "never generated" and "generated, but the sources have moved" used to look identical. ([why](docs/invariants/38-the-overview-is-persisted-and-marked-stale.md))

39. **Model-written prose follows the reader's language, not the documents'. Citation coordinates follow nothing, and naming a language guarantees neither its script nor its idiom.** A model told to write Chinese that helpfully turns `page:1` into `第1頁` makes every citation unverifiable. ([why](docs/invariants/39-prose-follows-the-reader-coordinates-follow-nothing.md))

40. **`tts.default_voices_for` maps a language to a voice, which is how the podcast joined invariant 39's language rules.** A correct Chinese script read by the default English voices is a routing bug, not a synthesis one. ([why](docs/invariants/40-language-decides-the-podcast-voice.md))

41. **No safety bound goes on the settings page; that is what "presentation only" protects.** Moving a bound onto a page every token holder can write is the same mistake as moving a key there. A behaviour toggle whose bound stays in the environment is fine (80). ([why](docs/invariants/41-settings-expose-presentation-only.md))

42. **An Audio Overview generated through the API is persisted as one file per notebook and served as a real file.** One file per notebook is what makes retention a non-question, unlike `traces/`. ([why](docs/invariants/42-the-generated-episode-is-persisted.md))

43. **A `TTSProvider` owns its output format and its cast, and since it may be cross-lingual it receives the language as a separate input. None of the three belongs to the caller.** A shared voice map would leak one provider's voice names into another's request. Chatterbox takes 33 times the wall-clock time and is deliberately not the default. ([why](docs/invariants/43-a-tts-provider-owns-its-format-and-cast.md))

44. **The podcast transcript behaves like subtitles, and its timing comes from the provider rather than from measuring the audio.** A provider that reports no boundaries yields one entry per utterance, all stamped `0:00`, so the consumer checks that times increase. ([why](docs/invariants/44-the-transcript-is-subtitles-timed-by-the-provider.md))

45. **The podcast script has a stated shape and is written to be spoken in one language.** Asking only for "a natural conversation" gave episodes no opening, no plan and no close. There is exactly one close, written last. ([why](docs/invariants/45-the-podcast-script-has-a-stated-shape.md))

46. **Every run-taking handler announces its run id (`api._announced`) before any preparatory work, not just before the spawn.** On a new notebook `_resolve_language` always runs and always outlasts the 5s grace period, so without this the client reports a missing run while the request succeeds. ([why](docs/invariants/46-run-ids-are-announced-before-any-pre-work.md))

47. **Every long-running action shows that it is running and offers a way to stop it, and no action starts without an explicit press.** A Tier 1 Stop names a run id and can reach a run that has not spawned yet; the Tier 0 Stop is global because nothing there can be ambiguous. ([why](docs/invariants/47-every-long-run-is-visible-and-stoppable.md))

48. **The interface language (`web/i18n.js`) is a browser preference, kept separate from the output language (invariant 39), which is a server setting.** A reader in Taiwan may want a Chinese interface over English papers, and merging the two would make that impossible to express. ([why](docs/invariants/48-interface-language-is-separate-from-output.md))

48.5. **The model must not number its own citations.** The interface numbers them, so a `[1]` written into the prose is a second, competing scheme. ([why](docs/invariants/48.5-the-model-must-not-number-its-citations.md))

49. **`Citation.answer_span` is the model pointing at its own prose, and it exists because locating the highlight by `quote` stopped working.** Invariant 39 made prose follow the reader while the quote stays in the source's words, so `answer.indexOf(quote)` could no longer find anything. ([why](docs/invariants/49-answer-span-is-the-model-pointing-at-itself.md))

50. **A source can be removed, so ids are no longer append-only: survivors are never renumbered and no id is ever allocated twice.** `max(live ids) + 1` handled only the middle of the range; removing the highest source freed its id, and a citation saved against it then read `verified: true` against different text. The high-water mark is persisted and only rises. ([why](docs/invariants/50-removal-ended-append-only-source-ids.md))

51. **`Source.preview` is display-only page metadata, scraped from HTML already in hand, and it never references an image.** Rendering `og:image` would make the reader's browser fetch a URL chosen by the page author, turning every pasted link into a beacon. ([why](docs/invariants/51-source-preview-never-references-an-image.md))

52. **The live ticker's event shape is `{kind, primary, detail, meta}`, and it carries the model's own words but never a step's output.** The branch used to emit the fixed word `Tool` and discard the payload, and nobody noticed because this project emitted no `tool_call` events at all. ([why](docs/invariants/52-the-ticker-carries-words-never-the-output.md))

53. **Renaming is a separate action from generating a title, and a rename refuses rather than derives.** Setting a title is an instant write while generating one is a model call that can fail; merging them gives renaming the failure modes of a model call. ([why](docs/invariants/53-renaming-and-generating-a-title-are-separate.md))

54. **Two more web UI hazards can only be caught by a source-tree assertion, extending invariant 36's reasoning.** A tooltip host that clips its own tooltip erases it, and an inverted drag-threshold pair makes every `pointermove` flip the state. ([why](docs/invariants/54-two-web-hazards-only-a-source-assertion-catches.md))

55. **Markdown in an answer is rendered by a hand-written renderer that builds DOM nodes, and links in it are shown but not clickable.** One missed `esc()` in a string-building renderer is an XSS hole, and a clickable link is invariant 1's hazard with the reader's click as the transport. ([why](docs/invariants/55-markdown-builds-nodes-and-links-are-inert.md))

56. **`Answer.follow_ups` comes from the same run that produced the answer, never from a second model call, and is not verified against anything.** The model already holds the corpus and its own answer, so asking in the same SUBMIT costs nothing extra. ([why](docs/invariants/56-follow-ups-come-from-the-same-run.md))

57. **The chat overview is the thread's first entry, inside the scroller, not a panel pinned above it.** As a sibling of `.chat-history` it permanently took up to half the chat column. ([why](docs/invariants/57-the-overview-is-the-threads-first-entry.md))

58. **A reference is a compact row that opens, and pointing at either end of a citation lights up the other.** Rendering every quote as a `blockquote` let one source cited eight times fill the column. `referenceKey`'s separator is `\u001f` because `CSS.escape` maps U+0000 to U+FFFD. ([why](docs/invariants/58-a-reference-is-a-row-that-opens.md))

59. **The four budget defaults are each a decision, and `max_tokens` is the one that silently kills a run.** `max_tokens` is billed against a cap the reasoning never appears in, so an undersized cap returns a reply cut off mid-JSON. Raise it against a distribution, never against one truncation. ([why](docs/invariants/59-the-four-budget-defaults.md))

60. **A status line may not claim something the page is not doing, and a repaint may not delete a run.** `setPhase` names a stage the trace cannot see, and rebuilding the thread from `state.turns` alone deletes a running question. ([why](docs/invariants/60-a-status-line-may-not-lie.md))

61. **The cheap `dspy.Predict` callers read `Corpus.excerpt`, never `blob()[:n]`; a prefix is source one, not the notebook.** The blob concatenates sources in order, so a 69,859-character first source hid sources two to four. ([why](docs/invariants/61-cheap-predict-callers-read-an-excerpt.md))

62. **A `[[SRC:...]]` marker is a coordinate for the interface and must never reach the reader. It is stripped at the display boundary, not before storage.** Stripping on the way out means nothing stored is rewritten, and every notebook already on disk is fixed with no migration. ([why](docs/invariants/62-markers-are-stripped-at-the-display-boundary.md))

63. **The podcast has a length, chosen at generation time, and the tiers are numbers rather than adjectives.** "Aim for a natural episode length" did nothing: four measured episodes all landed near three minutes. ([why](docs/invariants/63-the-podcast-has-a-chosen-length.md))

64. **A `long` script is built across REPL turns, which is what the sandbox is for.** Written as one code block it was cut off mid-structure and the run failed; built up across turns under the same cap it produced 80 utterances. ([why](docs/invariants/64-long-scripts-are-built-across-turns.md))

65. **Every RLM task here carries `rlm_harness.skills` with `discovery="inject"`, and the split between prompt and skill is a rule, not a preference.** Anything that corrupts the output when skipped stays in the prompt, because the model reads a skill only if it chooses to. ([why](docs/invariants/65-the-prompt-skill-split.md))

66. **Every task's pre-SUBMIT validator is `instructions.make_grounded_validator` (schema plus "no `[[SRC:...]]` marker in the model's own prose"), and SUBMIT belongs on a later REPL turn than the call that validated.** A run once printed the verdict beside its SUBMIT and shipped the very character it had just been warned about. ([why](docs/invariants/66-the-pre-submit-validator.md))

67. **The pre-SUBMIT validator checks each citation's coordinate against the corpus the run was given, and the six tasks share one base class instead of six identical `__init__` methods.** A model once wrote the section heading it was citing into `locator`, which made every citation in an overview unverifiable. ([why](docs/invariants/67-the-validator-checks-citation-coordinates.md))

68. **A wall-clock backstop scales with the work requested (`schema.PODCAST_TIMEOUT_FACTOR`).** A `long` podcast asking for 60 to 90 utterances could not fit under the 300s default it shipped with. ([why](docs/invariants/68-the-timeout-scales-with-the-tier.md))

69. **The interface language is a signal for choosing the output language, a fourth one ranked above `Accept-Language`, which narrows invariant 48 without merging the two.** The one place a reader had actually said which language they read was invisible to `naming.SuggestLanguage`. ([why](docs/invariants/69-interface-language-signals-output-language.md))

70. **The Trajectory drawer (`trajectory.py` plus `GET .../runs/{run_id}/trajectory`) is where a run's reasoning lives, not the chat bubble.** The inline step log put the planner's prose inside the answer, and because the validator recorded no calls its timeline was empty on every run. ([why](docs/invariants/70-the-trajectory-drawer.md))

71. **A repaint may not delete a run, and `#chat-overview` belongs to its generation while one is in flight (`overviewRunning`).** `renderChatOverview` clears the element that holds the run's only Stop, and several callers invoke it for reasons unrelated to the run. ([why](docs/invariants/71-a-repaint-may-not-delete-a-run.md))

72. **The web assets are served with `Cache-Control: no-cache`, because a zero-build app has no other way to stop a browser running last week's JavaScript.** `StaticFiles` sends no `Cache-Control`, and there is no content hash in the filenames to bust the cache with. ([why](docs/invariants/72-web-assets-are-served-no-cache.md))

73. **RapidOCR's region coordinates decide reading order (`_ocr.reading_order`); joining regions in detection order interleaves the columns of a two-column scan.** RapidOCR emits regions line by line across the page, so detection order jumps between columns mid-sentence. ([why](docs/invariants/73-ocr-reading-order-for-two-column-scans.md))

74. **A garbled text layer is detected by comparing it with OCR, never by a threshold alone (`pdf._page_text`, `_ocr.wordlike_ratio`).** No threshold separates good pages from mis-decoded ones, so the score only decides whether to spend an OCR pass and the comparison decides what to keep. ([why](docs/invariants/74-a-garbled-text-layer-is-decided-by-comparison.md))

75. **A trace's token budget has three readings, and the third is the one that matters (`trajectory.budget_summary`, the drawer's budget note).** Reading an absent field as "nothing was truncated" turns a corpus boundary into a property of the code. ([why](docs/invariants/75-three-readings-of-a-token-budget.md))

76. **The SSRF guard's DNS check accepts an operator-supplied carve-out (`RN_FETCH_ALLOW_CIDRS`), resolved in one place (`web.allow_nets`) that both host-side fetchers read.** A fake-IP resolver answers every public hostname with a reserved address, so full strictness refuses every ingestion on that machine. The guard is not wrong; it cannot see that the operator's own resolver is lying to it. ([why](docs/invariants/76-the-ssrf-carve-out-for-fake-ip-resolvers.md))

77. **Every request needs the API token (`auth.py`), the static assets are the only exception, and a `Host` header that is a DNS name is refused.** Being reachable only from this machine is not the same as being reachable only by this app: every browser the user runs is on this machine too. ([why](docs/invariants/77-the-local-api-token.md))

78. **The Inbox (`inbox.py`) is an index, not a corpus: nothing at Tier 0 ever assembles a blob, and every write to it is a SQL delta (`update_node`; there is deliberately no `save_node`).** The 8,000,000-character cap governs a notebook (8), and an Inbox meant to hold thousands of nodes can coexist with it only by never building one. ([why](docs/invariants/78-the-inbox-is-an-index-not-a-corpus.md))

79. **A capture always lands: submitting creates a `queued` node before anything is fetched, a parse failure becomes a `failed` node that keeps its message, and intake (`intake.py`) runs one item at a time.** A worker that dies on one bad link would otherwise leave every later capture `queued` forever, which looks exactly like still working. ([why](docs/invariants/79-a-capture-always-lands.md))

80. **Capture makes no model call unless the operator turns it on: distillation (`distill.py`) is a separate pass, off by default and bounded by an environment-only cap, and a failed summary leaves the node at `ready_undistilled` instead of costing the capture.** With your own API key and a habit of throwing everything in, distilling at intake by default would silently spend 200 calls on a 200-bookmark import. ([why](docs/invariants/80-capture-never-pays-for-a-summary.md))
