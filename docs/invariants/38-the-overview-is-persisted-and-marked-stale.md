# Invariant 38: The overview is persisted and marked stale

**The chat overview is the one guide artifact stored on an orbit (`schema.Overview`, `Orbit.overview`), and it is marked stale rather than deleted when the sources change.**

It used to live only in the page, so reopening an orbit offered the first-run button again, and adding a source deleted an overview that had cost a real run. "Never generated" and "generated, but the sources have moved" also looked the same. There are now three states: never generated shows the button, current shows the overview, and stale shows the overview marked as stale with `↻ Regenerate`.

Only the overview is stored, not the four guide kinds. The overview is the orbit's front page and what a returning reader expects to find; a guide is an on-demand tool. Saving the overview as a note is still useful: the stored overview is replaced on regeneration, while a note is a copy the reader chose to keep, and only a note can be promoted into a citable source. A guide whose sources change while it is being generated is kept in the page but marked the same way, so it never reads as current.

`Overview.source_ids` is captured when the run starts, never when it is stored. Building it inside the `mutate_orbit` closure would list a source added mid-run as covered by an overview the model never read. An overview can therefore land already stale if a source was added while it ran, which is the honest result, the same reasoning `ask` uses when it verifies against the snapshot corpus.

Staleness is set equality on source ids, computed on the server in `_overview_response` and `_podcast_response`, not by each client. It is a set rather than a length check so that removing a source (invariant 50) also marks it stale.

`/overview` runs two tasks and suffixes their run ids after derivation: `base = _derive_run_id(id, token)`, then `f"{base}-summary"` and `f"{base}-faq"`, with `token = body.run_id or uuid4().hex` capped at `_RUN_TOKEN_MAX`. Slugging `<token>-summary` instead would give every anonymous request the same `None-summary` id, and `slug`'s 120-character cap would merge the two suffixes for a long token. The cap also keeps the filename under the 255-byte `NAME_MAX`.

Generation happens on the server, not as a client `PUT` of text it already has, because closing the tab between the guide response and a store call would lose a paid run. If the FAQ half fails, the summary is stored without starter questions; if the summary fails, nothing is stored.

Run-id checks compare `slug(orbit_id)`, not the raw id, on both ends: `stream_run` and `citation_turn` on the server, and `app.js` through `OrbitResponse.slug`. Comparing raw ids broke every trace link for any id the slug changes, such as `"my orbit"` or any non-Latin id (invariant 10). The server returns the slug so the client never re-implements the hash fallback.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
