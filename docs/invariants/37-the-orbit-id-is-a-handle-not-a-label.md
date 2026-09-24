# Invariant 37: The orbit id is a handle, not a label

**An orbit's `id` is a handle and `schema.Orbit.title` is the label people read. The UI mints the id itself and never asks for one.**

Requiring a name before the first source turned the first interaction into a naming puzzle about something that did not exist yet. The id backs every filename, run-id prefix and URL, so it must stay stable, while the title can be anything; that is why they are two fields. `title` is optional and defaults to `None`, so older orbits still load.

`naming.SuggestTitle` is deliberately not an `RLMTask`. The full REPL loop suits exploring a large corpus and producing verifiable citations; for five words it would cost a sandbox boot and several planner turns. Titling is one `dspy.Predict` over a corpus excerpt (invariant 61), and it still runs in the API's isolated subprocess, so invariant 21 holds.

Titling is its own endpoint (`POST /orbits/{id}/title`), never part of `add_sources`, so ingestion never waits on or fails because of a model call.

It is lazy. `ensureTitle()` in `app.js` runs from actions that already call a model (generating an overview, asking, generating a guide or a podcast), never from ingestion, because pasting a link should not spend a model call naming something nobody has started using. `test_titling_never_fires_from_adding_a_source` checks the add-source path. An orbit with sources and no title is the result, which is why `derived_title` exists (invariant 53).

Nothing about a title may cost the user a source. `SuggestTitle.arun` catches every exception, and `suggest_title` catches the `HTTPException` a failed or timed-out run raises, both falling back to `naming.fallback_title`. An existing title is never overwritten, because renaming an orbit on every source add would change a name the user had already learned, so the endpoint is idempotent. `clean_title` is the only guard on this one model output with no schema behind it, and the UI renders it with `textContent`, like every other model-derived string (invariants 6 and 29).

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
