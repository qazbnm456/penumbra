# rlm-notebook

`rlm-notebook` reads sources of any kind (plain text, web pages, PDFs including scanned ones, and YouTube captions) and uses an RLM ([`rlm-harness`](https://github.com/qazbnm456/rlm-harness)) to answer questions grounded in them, with citations you can check against the original text yourself.

**The front door is an Inbox.** Throw anything in, a link, a thought or a dropped file, without deciding where it goes. Each capture lands at once as a *node* in one reverse-chronological stream, whether or not it could be parsed. A separate, opt-in pass distils each node into a title, a summary and tags, so you can find it again months later by describing it. When a handful of nodes turn out to be about the same thing, you file them into a **notebook**, one facet of yourself, and that is where the grounded chat, the Guide and the Audio Overview live. Two tiers: an Inbox you never have to tidy, and notebooks you curate on purpose.

## What it does

- **Ingestion** of text, web pages, PDFs and YouTube captions, with local hybrid OCR for scanned pages. A URL is sniffed, so a link to a PDF is read as a PDF.
- **Grounded chat** in a persistent, multi-turn notebook. Every citation is re-verified against the notebook's current sources.
- **Notes** that stay uncited until you promote one into a real, citable source.
- **A Notebook Guide**: summary, FAQ, timeline and key insight.
- **An Audio Overview**: a two-host podcast script, synthesised speech and a subtitle-style transcript.
- **A way out**: Copy as Markdown, a whole-notebook Export, and a print layout that appends the reference list.

The web UI reaches all of it, and the HTTP API runs each `ask`, `guide` and `audio` request in its own cancellable subprocess. The command line reaches everything except the Inbox and notebook management. A notebook names itself, the model writes in the reader's language rather than the documents', and a model role can run on a Claude Pro/Max subscription instead of an API key.

`AGENTS.md` indexes the invariants the project is built against, one line each, and `docs/invariants/<n>-<slug>.md` holds the argument and the traps behind each one. Those files are the authoritative record; this one is the tour.

## Install and run

`rlm-notebook` is an application, not a library. Nothing here is meant to be imported into your own code, and installing it into a shared environment would bring numpy, an ONNX runtime and a PDF engine along. Give it its own environment:

```bash
uv tool install "rlm-notebook[api] @ git+https://github.com/qazbnm456/rlm-notebook"
# or: pipx install "rlm-notebook[api] @ git+https://github.com/qazbnm456/rlm-notebook"
```

It is not on PyPI yet, hence the repository URL. Drop `[api]` if you only want the CLI. It needs **Python 3.11 or newer**, including 3.13 and 3.14.

It also needs system binaries that no Python manifest can express, which is why there is a container:

```bash
brew install deno         # REQUIRED. Every live run executes in a Deno-hosted Pyodide sandbox
brew install node         # REQUIRED TO RUN THE TESTS. Two test files execute the web UI's own
                          # functions rather than asserting on its source text; see AGENTS.md
brew install tesseract    # optional. The OCR fallback for scanned PDFs. RapidOCR is primary and
                          # ships as a normal dependency, so this only widens coverage
```

Then configure a model in the environment. Nothing loads `.env` automatically:

```bash
export RN_MAIN_MODEL=...   # and RN_API_KEY, or use the subscription path below
rlm-notebook ask "what does it say about X?" --source ./paper.pdf
rlm-notebook serve         # the HTTP API and the web UI, on http://127.0.0.1:8000/
```

### In a container

The image carries deno and tesseract, so it is the one install that is complete on its own:

```bash
docker build -t rlm-notebook .
docker run --rm -p 127.0.0.1:8000:8000 -v "$PWD/data:/data" --env-file .env rlm-notebook
```

**Publish the port to loopback, as above.** A bare `-p 8000:8000` puts an API with no authorization behind its token on every interface of your machine. Keep the volume too: `notebooks/`, `traces/` and `inbox/` are relative to the working directory, so without it, removing the container removes your notebooks and your whole capture history. Generated episodes live in `notebooks/audio/`.

### To develop it

```bash
git clone https://github.com/qazbnm456/rlm-notebook && cd rlm-notebook
uv sync                       # includes the local OCR backends scanned PDFs need; no extra flag
cp .env.example .env          # then fill in RN_MAIN_MODEL / RN_API_KEY
set -a; . ./.env; set +a      # nothing loads .env automatically
brew install deno             # the sandbox a live run executes in
```

### On a Claude subscription

Instead of an API key, a role can run on your **Claude Pro/Max subscription**. Prefix its model with `claude-agent-sdk/`:

```bash
uv sync --extra api --extra subscription   # plus the Claude Code CLI, installed and logged in
export RN_MAIN_MODEL=claude-agent-sdk/claude-sonnet-5
export RN_SUB_MODEL=claude-agent-sdk/claude-fable-5   # or leave unset to inherit the main model
```

A role on that path ignores `RN_API_KEY` and `RN_BASE_URL`, and mixing is fine: one role on the subscription, the other on a proxy. `ClaudeAgentLM` refuses to start when `ANTHROPIC_API_KEY` is set, because the Claude Code CLI silently prefers that key over subscription OAuth and would bill API credit instead (invariant 35).

## The command line

```bash
# ask a one-off question grounded in one or more sources; nothing is saved
uv run rlm-notebook ask "what does the source say about X?" \
    --source ./paper.pdf \
    --source https://example.com/article \
    --source https://www.youtube.com/watch?v=... \
    --source ./notes.txt
```

```bash
# a continuing conversation: --notebook saves sources and history to notebooks/<id>.json
uv run rlm-notebook ask "what does the source say about X?" --source ./paper.pdf --notebook mynb
uv run rlm-notebook ask "and what about Y?" --notebook mynb   # no --source needed to continue
uv run rlm-notebook ask "add this too" --source ./more.txt --notebook mynb   # extends it
```

Every answer carries citations made of a `source_id` and a `locator` (a page number, or the whole document, depending on the source type). Each one is checked to resolve to real text in the notebook, and one that does not resolve is marked unverified rather than dropped or trusted. Verification proves the coordinate exists, not that the quote supports the claim (invariant 5). Earlier turns help the model understand a follow-up question but are never a source of facts, so every citation in every answer is re-verified against the current sources.

A source that matches a prompt-injection pattern (`injection_scan.py`) still answers normally. The flag belongs to the source, not the answer: the CLI prints it, the API returns it on each source, and the web UI shows an amber warning chip on the Sources row and a line in the source viewer.

A YouTube URL ingests that video's captions, official ones if they exist and auto-generated ones otherwise, and never the video or audio stream, so there is no `ffmpeg`, no transcription model and no API key. A video with no captions at all is a clear ingestion error, not an empty source. **Note**: YouTube's Terms of Service prohibit automated access outside its own interfaces. Fetching only captions is narrower than downloading media, but the risk is not zero, and using this feature means accepting it, the same position any `yt-dlp` user is already in (invariant 33).

```bash
# generate a whole-notebook artifact instead of asking a question
uv run rlm-notebook guide summary --source ./paper.pdf
uv run rlm-notebook guide faq --notebook mynb
uv run rlm-notebook guide timeline --notebook mynb
uv run rlm-notebook guide insight --notebook mynb   # the single most important takeaway, in one sentence
```

Guide artifacts are verified the same way answers are. They are not cached, so each `guide` call regenerates from the notebook's current sources.

```bash
# a two-host, podcast-style Audio Overview: a grounded script plus an MP3
uv run rlm-notebook audio --source ./paper.pdf --out episode.mp3
uv run rlm-notebook audio --notebook mynb
```

The transcript prints first, with citations, so a TTS failure never loses the script. Each provider owns its format and its cast: the default, `edge-tts`, needs no API key and writes MP3, while `RN_TTS_PROVIDER=chatterbox` (`uv sync --extra chatterbox`) runs fully local with no network, is multilingual, and writes WAV. Set `RN_TTS_VOICE_HOST_A` and `RN_TTS_VOICE_HOST_B` to override the cast (see `.env.example`).

Choose the local provider when your sources must not leave the machine. Otherwise keep the default, which is far faster and handles mixed scripts well. On the same fourteen-second line of Chinese prose carrying `NASA`, `CVE-2026-1234` and an English clause, edge-tts took **8.2s and 81KB** and Chatterbox took **273.4s and 749KB**. On Apple Silicon, a 3.4-minute episode took Chatterbox 16 minutes end to end, 15 of them synthesis. Chatterbox has only one built-in voice, so its two hosts come from two ten-second reference clips in `rlm_notebook/voices/`. The clips were synthesised rather than recorded from a person, and `rlm_notebook/voices/README.md` explains where they came from.

**Everything the model writes follows the reader's language, not the documents'.** Set `RN_OUTPUT_LANGUAGE` as a hard override for chat and artifacts alike, or leave it unset and the server picks a language per notebook from your interface language, your browser's `Accept-Language`, the sources and the questions already asked, with the questions weighted highest. Citation coordinates and quotes are never translated, because they are what makes a citation checkable. Podcast voices follow the chosen language too.

## HTTP API

**Every request needs a token, and there is no authorization behind it.** `rlm-notebook serve` mints a token at startup and prints it. Send it as `Authorization: Bearer <token>`, or as a `?token=` query parameter where a header is impossible (the browser's `EventSource` and `<audio>` cannot set one). `RN_API_TOKEN` supplies your own token instead. Only the web assets are served without it, because the page that reads the token has to load first.

The token authenticates the application, not a person. Anyone holding it can create, read, question, cancel, rename or permanently delete any notebook, including its sources, notes and conversation, and can change global behaviour through `PUT /settings`. There is no concept of an owner. Run it only on `localhost` or a fully trusted network, and do not expose it to the internet or a shared network as it is.

The token exists because "reachable only from this machine" is not the same as "reachable only by this app": every browser you have open is also on this machine, and any page in it can POST to `127.0.0.1`. For the same reason (DNS rebinding), a `Host` header that is a DNS name is refused. `RN_ALLOWED_HOSTS` is the exception list if you reach the server by a name that is genuinely yours.

```bash
rlm-notebook serve                      # binds 127.0.0.1:8000, loopback on purpose
rlm-notebook serve --host 0.0.0.0       # allowed, with a warning, for the reasons above
```

`serve` binds loopback by default in code, not by convention: the token and the binding are the two layers of access control, and neither should depend on someone reading a paragraph. It starts without a model configured, on purpose, because the settings page exists for exactly that operator. From a source checkout, run `uv sync --extra api` and then `uv run rlm-notebook serve`.

```bash
# Every call below needs the token. Export it once to keep the examples readable.
# This is a SHELL variable, deliberately not named RN_API_TOKEN: the server reads that one, and
# exporting it in the client's shell is one copy-paste away from pinning the server's token too.
export RLMNB_TOKEN="<the token rlm-notebook serve printed>"
curl -H "Authorization: Bearer $RLMNB_TOKEN" localhost:8000/notebooks

# TIER 0: the Inbox. Capture is cheap and makes NO model call (invariant 80). The summary pass is
# a separate verb that names its own limit. A capture always lands, parsed or not (79).
curl -X POST localhost:8000/inbox -H "Content-Type: application/json" \
    -d '{"urls": ["https://example.com/article"], "texts": ["a thought worth keeping"]}'
curl -F file=@notes.md localhost:8000/inbox/upload        # bytes only; a local PATH is still refused
curl -X GET  "localhost:8000/inbox?q=design&limit=25"     # search the distilled fields
curl -X GET  localhost:8000/inbox/status                  # what is parsing, what is summarising
curl -X POST localhost:8000/inbox/distil -H "Content-Type: application/json" \
    -d '{"limit": 20}'                                    # SPENDS: up to 20 summaries on your key
curl -X POST localhost:8000/inbox/cancel                  # stop both at the next item boundary
curl -X GET  localhost:8000/inbox/nd-0123456789abcdef     # one node, plus the notebooks it is filed in
curl -X POST localhost:8000/inbox/nd-0123456789abcdef/promote -H "Content-Type: application/json" \
    -d '{"notebook_id": "mynb"}'                          # Tier 0 -> Tier 1
curl -X DELETE localhost:8000/inbox/nd-0123456789abcdef

# TIER 1: notebooks. "sources" takes URLs only here, never local paths (invariant 26); use the CLI
# for a local file. The Content-Type header is required: a POST body without it is rejected with
# a 422. The Authorization header is left out from here on for readability; add it to every call.
curl -X POST localhost:8000/notebooks/mynb/sources -H "Content-Type: application/json" \
    -d '{"sources": ["https://example.com/article"]}'
curl -X POST localhost:8000/notebooks/mynb/ask -H "Content-Type: application/json" \
    -d '{"question": "what does it say about X?"}'
curl -X POST localhost:8000/notebooks/mynb/guide/summary
curl -X POST localhost:8000/notebooks/mynb/audio         # podcast script plus base64-encoded audio
curl -X GET  localhost:8000/notebooks/mynb/audio/file    # the persisted episode as a file
curl -X POST localhost:8000/notebooks/mynb/overview      # the chat overview, persisted on the notebook
curl -X POST localhost:8000/notebooks/mynb/title         # let the model name the notebook
curl -X GET  localhost:8000/settings                     # language, podcast voices, auto-summary
curl -X PUT  localhost:8000/settings -H "Content-Type: application/json" \
    -d '{"output_language": "Traditional Chinese"}'      # replaces ALL settings; env still wins
curl -X POST localhost:8000/notebooks/mynb/cancel        # cancel that notebook's in-flight run

# Optional on ask/guide/audio: {"run_id": "my-token"} picks your OWN run id (sanitized, then
# prefixed with the notebook id), so you can open the trace stream below before or while firing
# the request that fills it. Leave it out and the server picks one.
curl -X POST localhost:8000/notebooks/mynb/audio -H "Content-Type: application/json" \
    -d '{"run_id": "my-token"}'
curl -X GET  "localhost:8000/notebooks/mynb/runs/mynb-my-token/stream"           # live or replayed SSE
curl -X GET  "localhost:8000/notebooks/mynb/runs/mynb-my-token/citation-turn?source_id=s1&locator=whole"

# Pasted text (the "texts" field) and file upload (a separate multipart endpoint):
curl -X POST localhost:8000/notebooks/mynb/sources -H "Content-Type: application/json" \
    -d '{"texts": ["some text pasted straight in, no URL or path needed"]}'
curl -X POST localhost:8000/notebooks/mynb/sources/upload -F "file=@./paper.pdf"

# A source's full text, every block, as the web UI's source viewer shows it. This exposes far
# more than a citation's short quote (invariant 31).
curl -X GET localhost:8000/notebooks/mynb/sources/s1

# Notes: free, uncited text. Write one directly or save a chat answer as one. A note is grounded
# only once promoted into a real source (invariant 32).
curl -X POST localhost:8000/notebooks/mynb/notes -H "Content-Type: application/json" \
    -d '{"text": "a thought worth keeping around"}'
curl -X DELETE localhost:8000/notebooks/mynb/notes/n1
curl -X POST localhost:8000/notebooks/mynb/notes/n1/promote   # turns it into a real source
```

Every `ask` and `guide` request runs its `RLMTask` in its own isolated, killable subprocess, unlike the CLI, which runs in-process. One slow or stuck request therefore cannot block another, and any of them can be cancelled outright. `/audio` has two host-side steps: script generation runs in a subprocess the same way and is the half you can cancel, then TTS synthesis runs in-process. The episode is persisted as one file per notebook, replaced on regenerate and served by `GET .../audio/file`, so reopening a notebook plays it back without synthesising again. The POST response also carries the audio, base64-encoded.

Three endpoints return far more than metadata and deserve care: the trace stream, the citation-turn lookup and `GET .../sources/{source_id}` can all surface a source's full text. File upload (`.pdf`, `.txt`, `.md`, capped by `RN_MAX_UPLOAD_BYTES`, 50MB by default) accepts only bytes the caller already has and never a local path, so it keeps the path ban that `sources` enforces. See `api.py`'s module docstring, and invariants 20 to 47 and 70 to 72 in `AGENTS.md` for the API and web UI rules.

**Behind a fake-IP proxy or split-DNS VPN?** Clash, Mihomo and Surge resolve every public hostname into a reserved range (by default `198.18.0.0/16`), so the SSRF guard refuses it and every web or YouTube ingestion fails with "resolves to a disallowed address". Set `RN_FETCH_ALLOW_CIDRS=198.18.0.0/16`, or whatever range your resolver actually hands out. A value that would cover loopback, cloud metadata or RFC 1918 addresses is refused outright (invariant 76).

Every write to a notebook (a source, a note, a chat turn) re-reads the notebook from disk under a per-notebook lock and applies only its own change, so a source added while a question is being answered survives when that answer is saved. Slow work such as ingestion and the model run happens outside the lock. Trace files under `traces/` are pruned by policy (`RN_TRACE_RETENTION_DAYS`, `RN_MAX_TRACE_FILES`), and an in-flight run's trace and anything written in the last hour are never touched.

## Web UI

Once `rlm-notebook serve` is running, open the address uvicorn prints with `?token=<the token rlm-notebook printed>` appended. The page stores the token and removes it from the address bar. `serve` prints the token rather than a full URL on purpose: an address announced before the port is bound could be one an occupied port then fails to serve, so uvicorn prints the address once it is true.

The first screen is the **Inbox**: a capture field, one reverse-chronological stream of everything you have captured, your notebooks in a rail on the left, and a search box. Search reads the distilled titles, summaries, tags and entities as well as the origin, since the URL is often the one word you remember. Several words must all match, and a query with no spaces (such as Chinese) is matched as one substring, which is the only correct behaviour for a script without word boundaries. A row opens in place.

Opening a notebook brings you to the second screen: sources (URL, pasted text or file upload), grounded chat, a Studio with the overview, Guide tabs and the podcast player, notes, and a live ticker showing what the model is doing. The address bar follows you, so a notebook can be bookmarked and Back returns to the Inbox. In a narrow window or at high zoom, the three areas become Sources, Chat and Studio tabs shown one at a time. There is no build step: FastAPI serves the files straight out of `rlm_notebook/web/`.

Clicking a citation in an answer lights up its entry in the References panel, which shows the number, the source, a provenance chip, how often it is cited and the passage with the cited words marked. Clicking a row in Sources opens the full original text. This is a transparency mechanism and never claims more faithfulness than `citations.py` checks. Any answer can be saved as a note, and any note can later be promoted into a citable source, so a notebook deepens as you read, write notes and ask again. A generated podcast plays in the page and can be downloaded, with a subtitle-style transcript: each line has a timecode, clicking a line seeks to it, and the line being spoken is highlighted.

Work leaves the product three ways, each carrying the same numbered references the panel shows, with an unverified citation labelled as such. **Copy** on any answer, the overview or a Guide tab puts Markdown on the clipboard. **Export** above the chat downloads the whole notebook (sources, overview, conversation and notes) as one `.md` file. Printing (Cmd/Ctrl+P) drops the application chrome and appends the reference list the printed numbers point to.

The ⚙ settings page holds the interface language, the output language, the two podcast voices and whether new captures are summarised automatically. It holds no keys and no safety bounds, which is the line invariant 41 draws. Summarising is off by default and every summary is a model call on your own key, so importing two hundred bookmarks costs nothing until you turn it on.

Every run shows that it is running, with elapsed time and a Stop, and the Trajectory drawer shows where its reasoning went: each planner turn in the model's own words, a tool timeline scaled to real time, the token budget, and what the validator rejected before accepting the answer. See `rlm_notebook/web/DESIGN.md`, and invariants 29 to 58 and 70 to 72 in `AGENTS.md`.

## What this is not (yet)

- There is no LLM configuration beyond what `rlm-harness`'s own environment variables provide.
- There is no Video Overview, no ingestion of uploaded audio or video files, and no audio transcription. YouTube captions are supported, but only captions.
- There is no rubric, eval or RL-export member, unlike this project's sibling tools.
- There are no accounts and no authorization on the HTTP API. One shared token authenticates the app, and everyone who holds it has full access.
- There is no desktop app package yet. Tauri is the intended shell.

## Licensing

`rlm-notebook` itself is MIT (`LICENSE`). PDF ingestion (`parsers/pdf.py`) uses `pypdfium2` (BSD-3-Clause or Apache-2.0). An earlier version used `pymupdf` and `pymupdf4llm`, which are licensed only under AGPL-3.0 or a paid Artifex commercial licence. That conflicts with this project's MIT licence and with an HTTP API meant to run as a network service, so the dependency was replaced rather than merely disclosed (invariant 7).

The default TTS provider, `edge-tts` (`tts.py`), is LGPLv3. LGPL generally allows an unmodified dependency from a permissively licensed program without putting that program under LGPL. This is common, low-risk practice, and it is named here rather than left undisclosed.
