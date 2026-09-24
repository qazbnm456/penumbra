# Invariant 72: Web assets are served no-cache

**The web assets are served with `Cache-Control: no-cache`, because a zero-build app has no other way to stop a browser running last week's JavaScript.**

Starlette's `StaticFiles` sends `ETag` and `Last-Modified` but no `Cache-Control`, which leaves the browser on heuristic caching, free to reuse a stale copy without asking. Invariant 29's zero-build choice means filenames carry no content hash, so there is no cache-busting URL to fall back on.

`no-cache` is not `no-store`. The copy stays cached and the ETag short-circuits the transfer, so an unchanged asset costs one conditional request and a 304 with no body. `no-store` would re-download a script of about 190KB on every navigation, which is why the test checks the ETag and the 304 as well as the header.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
