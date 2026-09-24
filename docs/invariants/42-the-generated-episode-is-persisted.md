# Invariant 42: The generated episode is persisted

**An Audio Overview generated through the API is persisted as one file per notebook and served as a real file.**

This is scoped to the API. `cli._cmd_audio` writes `--out` and returns, with no `Podcast` record and no offsets, so a CLI episode never has subtitles; that is right for a one-shot command whose caller named the output path. In the web UI, an episode used to exist only as a `Blob` in the tab, so a reload lost it.

The file is `notebook.audio_path`, `<base_dir>/audio/<slug><suffix>`, where the suffix is the provider's (invariant 43), and a regenerate replaces it. That makes retention a non-question: growth is bounded by the number of notebooks, not by how often anyone pressed the button, unlike `traces/`, which needed invariant 34's sweep. It lives in a subdirectory so the notebook listing's `*.json` glob never sees it.

The transcript is stored on the notebook (`schema.Podcast`); the audio is not. A multi-megabyte base64 blob in the notebook file would be parsed again on every read. `GET /notebooks/{id}/audio/file` serves the file instead, and a `Range` header returns `206`, so seeking does not download the episode again.

The audio is written before the notebook record, so a crash between the two leaves an orphan file rather than a record pointing at missing audio; the next generate overwrites it. A notebook cannot be deleted while its episode is being synthesised, and if the notebook disappears anyway, the audio just written is removed, so a later notebook of the same name is never served someone else's episode. An empty script counts as a regenerate: it clears both the file and the record.

The episode follows invariant 38's staleness rule, and its citations are re-verified against the current corpus on every read. Anyone holding the token can play any notebook's episode, because there is no authorization behind the token.

The generate button has the overview's three states: no episode shows a primary offer, an episode shows a quieter "Regenerate", and stale says the sources have changed. It is not primary once an episode exists, because regenerating costs a model run plus synthesis. Adding or removing a source updates the button only, because re-rendering the panel would rebuild its `<audio>` and interrupt playback. A regeneration that is stopped or fails puts the existing episode back, with the failure shown above it.

`renderPodcast` is one function for both a fresh episode and a reopened one, so the two can never render differently. It plays from the server URL, versioned by the episode's run id so the browser never replays a cached earlier episode, and `preload="none"` keeps a multi-megabyte file from loading on every notebook open.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
