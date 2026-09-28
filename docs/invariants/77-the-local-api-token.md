# Invariant 77: The local API token

**Every request needs the API token (`auth.py`), the static web assets are the only exception, and a `Host` header that is a DNS name is refused.**

`api._require_api_token` is the single middleware that applies the rules. `penumbra serve` mints a token per launch and prints it; `PN_API_TOKEN` supplies one instead, which is how the desktop shell passes the token it mints at every launch.

## Why loopback alone stopped being enough

Binding `127.0.0.1` was adequate while the only client was a page the same server had just handed the user. The desktop shell, and the browser extension still planned, make a second client normal, and "reachable only from this machine" is not the same as "reachable only by this app": every browser the user runs is on this machine too.

- Writes need no response. Any page in any tab can send a request to `127.0.0.1:<port>` and ignore the reply: deleting a source, a note or the whole conversation, or rewriting global settings.
- DNS rebinding reaches reads. A page served from an attacker's name that re-resolves to `127.0.0.1` keeps its origin, so the browser treats the requests as same-origin and lets it read every response, including a source's full text (invariant 31) and traces that can contain source text (invariant 29).
- An extension that talks to a fixed port publishes that port to anyone who reads the extension.

## Two defences for two attacks

The token is the main defence. A cross-origin page cannot read the URL the token arrived in, so it cannot present it; this is what makes "local" mean "this app".

The `Host` check answers DNS rebinding specifically: the header must be a literal IP address or `localhost`. Rebinding needs a name, because what it rebinds is a DNS answer; `evil.example` can resolve to `127.0.0.1`, but the browser still sends `Host: evil.example`, and that is rejected. A trusted-network deployment reached at `192.168.1.5:8000` is unaffected. `PN_ALLOWED_HOSTS` lets the operator allow a name that is genuinely theirs (mDNS or internal DNS), for the same reason as invariant 76's carve-out: the guard cannot see the operator's network, so the operator says so explicitly.

## Deny by default

`auth.PUBLIC_PATHS` is the allowlist, computed from the static directory rather than written by hand, and it includes only files with a web-asset extension (`.html`, `.css`, `.js`, `.svg`, fonts, `.json` and similar). A route added later is protected without anyone doing anything, while per-route protection would give one chance to forget per route, silently (invariant 24's warning about lists). An asset added later keeps working, because a hand-kept list would go stale and show up as a blank page. A document such as `web/DESIGN.md` is not an asset and requires the token.

The allowlist is computed at import, which is exact for a packaged wheel; in development, a file added to `web/` while the server runs is not public until a restart, which shows up as a 401 on a file that plainly exists. `tests/test_api.py::test_every_registered_api_route_is_protected` walks the real route table and asserts that no API route overlaps the allowlist.

## The token may travel in the query string

`EventSource`, `<audio src>` and a download link cannot set request headers. The live trace stream (invariant 29) and the stored episode (invariant 42) are reached that way, so a header-only token would break both, and the ticker would fail silently. A token in a query string can end up in access logs or a `Referer`; for a loopback, single-user server that is the lesser harm, and Jupyter makes the same trade. Two things limit it: `app.js` removes the token from the address bar as soon as it reads it (`searchParams.delete` plus `replaceState`, so Back cannot return to it), and `serve`'s non-loopback warning names the query-string exposure. `tests/test_web_assets.py::test_every_server_url_the_browser_fetches_itself_carries_the_token` checks that every such URL goes through `withToken()`.

## What this is not

- It is not authorization. The token authenticates the application, not a person, and every holder is fully privileged over every orbit and over global settings. Invariant 25 is unchanged.
- It is not multi-user: no accounts and no sessions.
- It cannot be turned off. A `--no-token` flag would recreate the hole and be reached for the first time anything felt inconvenient. An operator behind their own auth proxy sets `PN_API_TOKEN` to a value the proxy injects.
- It does not replace the loopback default, which stays in code for invariant 25's reasons.

## Two traps

`PN_API_TOKEN="   "` must not mean "authentication off". Whitespace falls back to the minted token, so the server stays protected and the operator notices that their value does not work. A test pins it.

`TestClient`'s default `base_url` is `http://testserver`, a DNS name the `Host` check refuses. The fix is to point tests at a literal address (`test_api.py::_authed_client`), never to allow `testserver` in the guard; a test hostname inside a security control is how the control stops being one.

## The browser extension's capture key

The extension cannot hold the API token: it is minted per launch and handed only to the shell's own windows. Pairing gives it a second key instead (`auth.capture_token`, `horizon/.capture-token`, readable by this user only), kept on disk so it survives restarts. That key opens exactly five routes, matched by method and path (`auth.CAPTURE_ROUTES`): `GET /extension/status`, `GET /extension/orbits` (ids and names only), `POST /extension/capture`, and `POST /extension/file` and `POST /extension/undo`, which act only on a capture this key made in the last ten minutes (`api._EXTENSION_RECENT`), so the confirmation card can file it or take it back. A leaked capture key can add captures, read the orbits' names and move or remove what it just added; it cannot read a source, touch anything else, change a setting or pair again, all of which need the API token.

Pairing is started from the workspace with the API token (`POST /extension/pairing`), which mints a fresh key, replacing and so un-pairing any earlier one, and returns the address of `pair.html` with the key in its fragment. The workspace opens that address in the reader's browser; a fragment is never sent to a server, and the page removes it from the address bar once the extension's content script has read it. The content script accepts a key only from a page on `127.0.0.1` or `localhost`, and the extension keeps it only after the server answers `/extension/status` with it. `DELETE /extension/pairing` revokes it.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
