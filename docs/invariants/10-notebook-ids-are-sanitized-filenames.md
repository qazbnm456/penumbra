# Invariant 10: Notebook ids are sanitised filenames

**A notebook id is sanitised (`notebook.slug`) before it becomes a filename, and an id the whitelist empties falls back to a content hash instead of being rejected.**

`--notebook` and the API's `{notebook_id}` become `<notebooks_dir>/<slug(id)>.json`. Unsanitised, an id could become a traversal segment (`..`, an absolute path, a nested directory) or exceed a path-component length limit.

The whitelist `[A-Za-z0-9._-]` strips every CJK, Arabic, Cyrillic and emoji character, so a notebook named in Chinese used to reduce to nothing and be rejected. It now falls back to `nb-<sha256[:16]>`. The id is NFC-normalised before hashing, so two spellings reach the same file, and encoded with `surrogatepass`, because `api._derive_run_id` calls `slug()` outside every error handler and a raising `slug` would be a bare HTTP 500. The hash affects only the filename: `Notebook.id` keeps what the user typed, and listings report that value, so non-Latin names round-trip. A truly empty or whitespace-only id still raises.

This supersedes part of invariant 27: `"!!!"` is now an ordinary notebook rather than a 400. The unhandled 500 that invariant 27 fixed is still gone; that input simply no longer reaches that path.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
