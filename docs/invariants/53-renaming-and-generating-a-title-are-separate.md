# Invariant 53: Renaming and generating a title are separate

**Renaming is a separate action from generating a title, and a rename refuses rather than derives.**

`PUT /notebooks/{id}/title` sets what the user typed, and `POST` to the same path runs `naming.SuggestTitle`. Setting a title is an instant write that always succeeds; generating one is a model run that can fail, take seconds and be superseded, and merging them would give renaming the failure modes of a model call. `naming.normalize_title` is split out of `clean_title` because the two callers need opposite things from an unusable value: generation falls back to a derived label, because a notebook must end up with one, while a rename returns 422, because silently replacing what someone typed would mislead them. A rename is still normalised, because the API authenticates the app rather than a person (invariants 25 and 77).

Model-written titles are not unique, so the picker orders notebooks by file modification time. The id is no longer shown anywhere (invariant 37), so "which one did I touch last" is what tells two same-named notebooks apart. The time is carried outside the schema (`notebook._MTIMES`, `last_modified`), because it is a property of the file and a schema field would mean writing an unread timestamp on every change.

`derived_title` appears in both `NotebookSummary` and `NotebookResponse`, or the header would say "Untitled notebook" while the picker showed a derived label for the same notebook. It comes from `naming.fallback_title` and costs no model call, which matters because titling is lazy (invariant 37).

`GET /settings/choices` serves the settings page's dropdown values and must never call `_config()`, for invariant 41's reason. Voice names depend on `RN_TTS_PROVIDER`, read straight from the environment, and an unknown provider returns an empty voice list so the page still renders. The values are served rather than hardcoded in JavaScript, because a second copy would drift from `tts._LANGUAGE_VOICES`.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
