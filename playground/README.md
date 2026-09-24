# The playground: the web UI as a static product page

`playground/` builds a **server-free, single-page, fully interactive demo** of Penumbra from the web UI this repo already ships and the orbits on the author's machine. The output is a directory of static files, deployed under a personal domain ([`www.boik.tw/rlm-notebook/`](https://www.boik.tw/rlm-notebook/)) so the product page and its author share an origin.

```
uv run --extra api python playground/build.py     # -> playground/dist/
node playground/smoke.mjs                          # headless check, no browser needed
python3 playground/serve.py                        # then open http://127.0.0.1:8899/
```

CI runs neither `build.py` nor `smoke.mjs`, so run both yourself whenever the app changes.

## Why this shape

Penumbra is hard to install for a curious stranger: Python, a model key, a Deno sandbox and an optional OCR stack. Most people who would like it never get far enough to see it. A page that only describes the product persuades almost nobody; a page they can use lets them do the thing.

The interaction model follows [witr's playground](https://pranshuparmar.github.io/witr/): a simulated product with a guided tour, a scenario switcher and an install modal, all honestly labelled as simulated. That page is a separate, hand-written implementation of the real tool.

**This one is not, and that is the whole design.** `app.js`, `style.css` and `i18n.js` are copied byte for byte out of `penumbra/web/`, and the demo runs them. A screenshot of the playground is a screenshot of the product and cannot flatter it. New features appear in the demo on the next build, as long as they need no route the shim lacks.

**The shim is the one part not copied from the product, and it is where the demo can rot.** It did once: when the Horizon became the front door, `shim.js` still answered only `/orbits*` and `/settings*`, and the demo's first screen became a 404 under a guided tour pointing at a button that was not there. Check the shim's route list whenever the app learns an endpoint.

## How it works: three interception points

`app.js` reaches the network in exactly three ways, and `src/shim.js` replaces all three before `app.js` is evaluated. That small count is what makes this approach viable; with thirty entry points, forking the UI would be cheaper.

| # | Surface | Why it needs its own seam |
|---|---|---|
| 1 | `window.fetch` | every `api()` call, about 18 endpoints |
| 2 | `window.EventSource` | the live reasoning-trace stream |
| 3 | `HTMLMediaElement.prototype.src` | the podcast `<audio>`, a browser-issued request `fetch` never sees |

**Script order is the contract.** `app.js` holds no reference to these globals and calls them at request time, so replacing them first is both sufficient and necessary. `build.py` injects `tour.js`, `shim.js`, `i18n.js`, `app.js`, then the tour library, `chrome.js` and `director.js`. Do not reorder them.

## Nothing in the demo is invented

Every pixel is either the shipped UI or output a model really produced.

- **Orbits are real**, and their API responses are computed at build time by the real Python, `api._orbit_response`. Every citation is verified by `citations.py` itself and every `answer_span` located by `locate_answer_spans`. The fixture is the response, and there is no JavaScript re-implementation to drift from it.
- **Reasoning traces are real** `traces/*.jsonl` files from runs that happened, decomposed by the real `trajectory.build_trajectory` and translated by the real `api._translate_trace_event`. The ticker shows the model's own words.
- **Where there is no artifact, the demo says so.** Only the overview is persisted on an orbit (invariant 38), so Studio's Timeline and Insight tabs have no recorded output and show an honest note instead. A reader cannot tell a made-up artifact from a real one, which is exactly why there are none.
- **A source added in the playground is labelled simulated**, because nothing was fetched or parsed.

Two things are deliberately reduced: ingested source text is capped (`MAX_SOURCE_CHARS`) so a public page does not rehost whole third-party articles, and audio is trimmed (`--audio-seconds`) so the page is not 14MB.

**Choose the default scenario deliberately.** `SCENARIOS[0]` is what a first-time visitor lands on. One orbit predates `instructions.NATURAL_REGISTER` and carries thirteen instances of the calque that rule prevents; it still ships, but it greets nobody.

**Use `serve.py`, not `python -m http.server`.** The latter sends no `Cache-Control`, so the browser may reuse a stale copy without revalidating, and with no content hash in the filenames there is nothing to bust. Half an hour once went into a tour step that had already been fixed on disk. This is invariant 72's reasoning applied to the playground's own dev server.

## What the build needs, and what it cannot reproduce

**`orbits/` and `traces/` are gitignored** because they are run artifacts, so `build.py` reads data that exists only on the machine that generated it. A fresh clone can run `smoke.mjs` against an existing `dist/`, but cannot rebuild one without generating orbits of its own. Committing them would put several megabytes of third-party article text into the repo, so **the published `dist/` in the Pages repo is the artifact of record**. Regenerating the data from scratch produces a different, equally real playground, not an identical one.

- **Generate demo data through the API, not the CLI.** The CLI writes a trace only when asked (`--trace PATH`); the API always does. No trace means an empty Trajectory drawer, one of the three things the page leads with.
- **Cover the podcast tiers on purpose.** An orbit holds one episode (invariant 42), so showing short, default and long takes three orbits per language. `smoke.mjs` asserts the matrix.

## Verifying without a browser

The playground has no server, so `smoke.mjs` stubs the handful of web globals, loads `tour.js` and `shim.js` exactly as the page does, and drives every endpoint. **It extracts the endpoint list from `app.js` rather than hardcoding one**, so a new `api()` call in the product fails the smoke test instead of 404ing in front of a reader. It has caught real mismatches that no status-code check would: note ids that are strings (`n1`) where the shim assumed integers, and `GET /orbits` returning `sources` and `turns` where the picker reads `source_count` and `turn_count`, which rendered "undefined sources" instead of failing.

## Deploying

The output is plain static files with no absolute paths, so it drops into any static host at any sub-path:

```
uv run --extra api python playground/build.py \
    --deploy ~/Documents/qazbnm456.github.io/rlm-notebook
```

`--deploy` mirrors rather than merges: it replaces the target directory, because a stale file left from a previous build is exactly what makes a static site serve a mix of two versions. `build_index()` rewrites `/style.css` to `./style.css` and so on, because the app's paths are absolute (the server mounts assets at the root) and a Pages subdirectory is not the root.

## Reusing the pattern

It transfers to any project with a web UI and a narrow client-server seam:

1. **Count the network entry points.** Search for `fetch(`, `EventSource`, `WebSocket`, `.src =` and `XMLHttpRequest`. If there are a handful, shim them. If not, fix that first: a UI with one choke point is easier to test and to demo.
2. **Never fork the UI.** Copy it verbatim in the build. Once you edit a copy, the demo starts lying and you own two codebases.
3. **Compute fixtures with the real server code**, not by hand and not in the front-end language. That is what makes the demo's checkmarks mean what the product's do.
4. **Ship recorded reality and label every gap.** The value is that a stranger sees what the product actually does, and one fabricated artifact costs the whole page its credibility.
5. **Write the headless smoke test**, and derive its endpoint list from the UI source.
