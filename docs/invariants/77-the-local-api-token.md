# Invariant 77 — The local API token

**Every request this API answers needs the token, and the static web assets are the only
exception.** `auth.py` holds the rules; `api._require_api_token` is the single middleware that
applies them. `rlm-notebook serve` mints one per launch and prints it; `RN_API_TOKEN` supplies one
instead, which is the channel the desktop shell will use.

## What changed, and why "loopback is the access control" stopped being enough

Invariant 25 said this API has no authentication, and that `serve` binding `127.0.0.1` is therefore
the entire access-control story. That was TRUE, and it was ADEQUATE, for as long as the only thing
that ever talked to this server was a page the same server had just handed the user.

It stops being adequate the moment a SECOND client exists — and the Inbox pivot's desktop shell and
browser extension both do, by design. The gap is that **"reachable only from this machine" is not
the same property as "reachable only by this app."** Every browser the user runs is also on this
machine:

- **Writes need no response.** Any page open in any tab can issue a request to `127.0.0.1:<port>`
  and simply ignore what comes back. `DELETE /notebooks/{id}/sources/{id}` destroys a source
  irreversibly; `DELETE .../notes/{id}` and `DELETE .../turns` are the other two; `PUT /settings`
  rewrites global state for notebooks the caller never named. Invariant 25 already enumerates all
  four as things an unauthenticated caller can reach — it just assumed the caller had to be a
  program the user deliberately ran.
- **DNS rebinding reaches READS.** The attacker serves a page from a name they control, and that
  name re-resolves to `127.0.0.1`. The page keeps its origin, so from the browser's point of view
  the requests are same-origin and it can read every response. `GET /notebooks/{id}/sources/{id}`
  returns a source's FULL TEXT (invariant 31 already records this as a materially different
  exposure from every other endpoint), and the trace endpoints can return full ingested source text
  the model echoed while reading (invariant 29).
- **The extension makes the port public knowledge.** Today the port is a weak secret at best. An
  extension that talks to a fixed local port publishes it to anyone who reads the extension.

## Two defences, answering two different attacks

**The token is the real one.** A cross-origin page cannot read the URL the token arrived in, so it
cannot present it. This is what makes "local" mean "this app" instead of merely "this machine".

**The `Host` check answers DNS rebinding specifically**, and the rule is: *a literal IP address, or
`localhost`.* That is the whole property, and it needs to know nothing about what address the
server actually bound — **rebinding requires a NAME, because what it rebinds is a DNS answer.** An
attacker can make `evil.example` resolve to `127.0.0.1`, but the browser still sends
`Host: evil.example`, and that string is what gets rejected. A trusted-network deployment reached
at `192.168.1.5:8000` is unaffected: a literal address cannot be the product of rebinding.
`RN_ALLOWED_HOSTS` is the carve-out for a name that is genuinely the operator's (mDNS, internal
DNS) — the same shape, and the same reasoning, as invariant 76's `RN_FETCH_ALLOW_CIDRS`: the guard
cannot see the operator's network, so the operator gets to say so explicitly rather than the guard
guessing.

## Deny by default, which is why it is a middleware

`auth.PUBLIC_PATHS` is the allowlist, and it is the static mount's own files, **computed from the
directory rather than listed**. Two consequences, both deliberate:

- **A route added later is protected because nobody did anything.** The opposite shape — a list of
  protected paths, or `dependencies=[Depends(...)]` on each route — is exactly what invariant 24
  already names as the failure mode: *"the RULE is the invariant, NOT the current list of places it
  applies."* One chance to forget PER ROUTE, with a failure that is silent and invisible in the
  response. This sentence used to carry a count; it was wrong by ten within one slice (the same incident
  `auth.py` records, told with the same number now — it was written up twice with two different
  ones, which is the rot arriving in the very paragraph about rot), which is
  the argument making itself. The other two copies were de-numbered and this third was missed.
- **An asset added later keeps working.** A hand-written set of asset names goes stale the first
  time someone adds a file, and the symptom is a blank page nobody connects back to this rule.

Computed AT IMPORT, which is exact for a packaged wheel and one papercut in development: a file
dropped into `web/` while a server is running is not public until that process restarts. The
symptom is a 401 on an asset that plainly exists, which is confusing for exactly as long as it takes
to remember this sentence.

`tests/test_api.py::test_every_registered_api_route_is_protected` walks the ACTUAL route table and
asserts no API route overlaps the allowlist, so the rule is enforced rather than stated.

**The corollary, which has to be said out loud: EVERYTHING in `rlm_notebook/web/` is public.** Not
just the three assets the page loads — the allowlist is the whole directory, so `GET /DESIGN.md`
answers 200 without a token. That was already true (`StaticFiles` served it), but this rule now
CODIFIES it, which makes "drop a file in `web/`" a decision about publishing rather than about
where a file is convenient. Anything that should not be world-readable by whoever can reach the
port does not belong in that directory.

## The token is accepted in the query string, and that is forced rather than lazy

`EventSource` cannot set request headers at all. Neither can `<audio src>`, nor a download `href`.
The live reasoning-trace stream (invariant 29) and the persisted episode (invariant 42) are reached
by exactly those, so a header-only token would make both unreachable — and the ticker's failure
mode is *silent*: the answer still arrives, the ticker just never ticks.

The cost is real and is accepted with its eyes open: a token in a query string can land in access
logs and in a `Referer`. For a loopback single-user server that is the lesser harm, and it is the
same trade Jupyter makes for the same reason. Two things bound it — `app.js` strips the token from
the address bar the instant it reads it (`searchParams.delete` + `replaceState`, never
`pushState`, so Back cannot walk onto it either), and `serve`'s non-loopback warning names the
query-string exposure explicitly.

`tests/test_web_assets.py::test_every_server_url_the_browser_fetches_itself_carries_the_token` is
the tripwire, and it exists because this is a hazard only a source assertion can see — the same
argument as invariants 36 and 54. There is no JS runtime in the suite; nothing else executes
`app.js`. A future `EventSource` call site that forgets `withToken()` fails 401 silently.

## What this deliberately is NOT

- **Not authorization.** The token authenticates THE APPLICATION, not a person. Every caller
  holding it is fully privileged over every notebook and over global settings. **Invariant 25's
  authorization half is completely unchanged**, and `api.py`'s served docstring says so in those
  words.
- **Not multi-user, not accounts, not sessions.** This is a single-user local application.
- **Not disable-able.** A `--no-token` flag re-creates the exact hole this closes, and would be
  reached for the first time anything looked inconvenient. An operator fronting this with their own
  auth sets `RN_API_TOKEN` to something their proxy injects; that is the same escape hatch without
  a switch labelled "off".
- **Not a replacement for the loopback default.** Binding `127.0.0.1` stays the default and stays
  in code for invariant 25's reasons. The token is a second layer, not a licence to drop the first.

## Two traps a later reader will walk into

**`RN_API_TOKEN="   "` must not read as "authentication off".** Whitespace falls back to the minted
token, so the server stays protected and the operator discovers the typo because *their* value does
not work — rather than because *nothing* does. Pinned by a test.

**`TestClient`'s default `base_url` is `http://testserver`, a DNS NAME**, which the `Host` check
refuses. The fix is to point the tests at a literal address (`test_api.py::_authed_client`), NOT to
allow `testserver` in the guard. Putting a test hostname inside a security control is how the
control quietly stops being one.

---

One-line index: [`AGENTS.md`](../../AGENTS.md) · Incidents, measurements and superseded drafts: [`CHANGELOG.md`](../../CHANGELOG.md)
