# Invariant 29: The web UI is a product surface

**The web UI (`rlm_notebook/web/`) is a real end-user product, not a replay-only trace console like the sibling projects' `studio/`.**

A persistent, multi-notebook, multi-turn workspace is a different kind of thing, and the divergence is a deliberate design decision. It is zero-build vanilla HTML, CSS and JavaScript, with no framework and no build step.

Its assets live under `rlm_notebook/web/`, not a top-level `web/`. A top-level directory has no entry in `pyproject.toml`'s wheel `packages` list and would silently vanish from an installed wheel.

`app.js` builds every node that could carry model- or source-derived text with `createElement`, `textContent` and `element.title`, never `innerHTML` with an interpolated string. A citation's `source_id`, `locator` or `quote` can echo attacker-supplied text from a prompt-injected source, and injection flags are advisory, not a filter (invariant 6).

## The Audio Overview request

`POST /notebooks/{id}/audio` runs in two host-side steps. `GeneratePodcastScript` runs in the same isolated subprocess as `ask` and `guide`, and TTS synthesis runs after that subprocess returns. Synthesis runs on a daemon thread rather than the event loop, because `EdgeTTSProvider.synthesize()` calls `asyncio.run(...)` internally, and a daemon thread is one a quitting server does not wait for. The script step can be stopped; synthesis cannot, so the UI shows that stage without a working Stop.

Synthesis writes through a temp file whose `finally` covers both success and failure; the `try` must start before `synthesize()`, or a `TTSError` raised inside it leaks the file. The Download link slugs its filename from the model-written notebook title, because the browser turns `download` into a path component, and its extension follows the served file, because a provider may emit WAV (invariant 43).

The generate response is JSON with base64 audio, never a raw binary body, so its error handling matches every other endpoint. `GET .../audio/file` is the exception: it is a `FileResponse` so the browser can range-request an episode instead of downloading it again to seek (invariant 42). The JSON rule is about the endpoint that can fail after spending a model run, not the one that serves a file already on disk.

## The live reasoning-trace stream

The stream rests on five rules.

- The client picks the run id, never the server (`RunOptions.run_id`, an optional body field on `ask`, `guide` and `audio`), so the caller can open `GET .../runs/{run_id}/stream` before or alongside the request that fills it. `_derive_run_id` sanitises the token through the same whitelist as `notebook.slug()` and always prefixes the notebook id.
- `_run_isolated` creates `traces/{run_id}.jsonl` exclusively (`O_CREAT|O_EXCL`, 409 if it exists) before spawning anything. `TraceRecorder`'s lock is process-local, so without this two requests on one run id would have two workers write interleaved events to one file. If the spawn fails after the create, the empty file is removed, so a failed spawn never occupies the id for good.
- `_RUN_PROCESSES` (keyed by run id) is a separate map from `_ACTIVE_RUNS` (keyed by notebook). With one slot per notebook (invariant 23), a second request overwrites the first's entry, which would make the first run's stream think it was cancelled. A run is reserved there with the value `None` before it spawns and announced before any preparatory work (invariant 46): a missing key means finished, cancelled or never started, and `None` means still spawning.
- Linking a citation to the turn that produced it is a separate lookup (`GET .../runs/{run_id}/citation-turn?source_id=&locator=`). It searches the trace's events in step order for the first whose whole serialised payload contains the marker, because a `sub_call` event's keys differ from a `main_step`'s and a fixed field list would miss citations that appear only in a sub-LM call. Both this endpoint and the stream check that the run belongs to the notebook, comparing `slug(notebook_id)`.
- Every artifact that can be reopened stores the run id that produced it: `ChatTurn.run_id`, `Overview.run_id` (invariant 38) and `Podcast.run_id` (invariant 42). Without it a reload has no way back to the trace, and the features above, including invariant 70's steps pill, would last only until a refresh.

A missing trace disables that one feature and nothing else on the page; retention is bounded (invariant 34). The marker search is a heuristic: finding the marker proves the REPL saw it, not that the model relied on that occurrence, the same limit as invariant 5. A `sub_call` event's `input` is truncated to 4000 characters upstream.

The trace endpoints expose more than metadata, because a trace can contain full ingested source text. They inherit invariant 25's posture as a sharper form of the same accepted risk.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
