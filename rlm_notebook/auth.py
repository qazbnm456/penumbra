"""The local API token — the whole of this API's authentication (AGENTS.md invariant 77).

Invariant 25 says this API has none, and that `serve` binding 127.0.0.1 is therefore the entire
access-control story. That was true, and adequate, while the only thing that ever talked to the
server was a page the same server had just handed the user. It stops being adequate the moment a
SECOND client exists — the planned desktop shell and browser extension both would — because
"reachable only from this machine" is not the same property as "reachable only by this app":

- Any page open in the user's browser can issue state-changing requests to `127.0.0.1:<port>`
  without ever reading a response. `DELETE /notebooks/{id}/sources/{id}` destroys a source
  irreversibly and `PUT /settings` rewrites settings for notebooks the caller never named.
- DNS rebinding goes further and reaches READS: the attacker's own page keeps its origin, the name
  it was served from re-resolves to 127.0.0.1, and from the browser's point of view the requests
  are same-origin. `GET /notebooks/{id}/sources/{id}` returns a source's FULL TEXT, which invariant
  31 already records as a materially different exposure from every other endpoint.

So there are two defences here and they answer different attacks. **The token** is the real one: a
cross-origin page cannot read the URL the token arrived in, so it cannot present it. **The Host
check** is what stops DNS rebinding specifically, and it is cheap enough to keep as depth.

Deliberately NOT here, and each one is a decision rather than an omission:

- **No user accounts, no passwords, no sessions.** This is a single-user local application; the
  token authenticates THE APP, not a person. Invariant 25's "no authorization of any kind" is
  unchanged — every caller who holds the token is still fully privileged.
- **No way to turn the token off.** A `--no-token` flag re-creates the exact hole this closes, and
  would be reached for the first time anything looked inconvenient. An operator fronting this with
  their own auth can still set `RN_API_TOKEN` to a value their proxy injects.
- **The token is accepted in the QUERY STRING as well as a header, and that is forced, not lazy.**
  `EventSource` cannot set request headers at all, and neither can `<audio src>` or a download
  `href` — the live reasoning-trace stream (invariant 29) and the persisted episode (invariant 42)
  are both reached that way. The cost is that the token can land in access logs and in a `Referer`;
  for a loopback single-user server that is the lesser harm, and it is the same trade Jupyter makes
  for the same reason. `app.js` strips it from the address bar as soon as it has read it.
"""

from __future__ import annotations

import ipaddress
import os
import secrets
from pathlib import Path

#: The query parameter the token may be presented in when a header is impossible (see the module
#: docstring's third bullet). Written down once so `api.py`, `app.js` and the tests share one
#: spelling rather than three string literals that can drift apart.
QUERY_PARAM = "token"

#: Minted ONCE per process, at import, and used only when the environment does not supply one.
#: `secrets.token_urlsafe(32)` is 256 bits of `os.urandom`, URL-safe so it survives being pasted
#: into a query string without escaping.
_MINTED = secrets.token_urlsafe(32)

_WEB_DIR = Path(__file__).parent / "web"


#: What the BROWSER needs to render the page, which is the argument the allowlist rests on — not
#: "whatever happens to sit in this directory". `web/` also holds `DESIGN.md`, a 47 KB internal spec
#: that shipped in the wheel and answered unauthenticated on `/DESIGN.md`; the docstring below
#: justifies the allowlist as "the static assets, which are this application's own source code and
#: carry nothing private", which is an argument about ASSETS and a design record is not one. The
#: deny-by-default shape is what makes the fix safe: a suffix nobody listed needs a token, so the
#: next thing dropped in here is protected because nobody did anything.
_ASSET_SUFFIXES = frozenset({".html", ".css", ".js", ".mjs", ".svg", ".png", ".webp", ".ico",
                             ".woff", ".woff2", ".ttf", ".json", ".map"})


def _public_paths() -> frozenset[str]:
    """Every path served by the static mount, computed from the directory rather than listed.

    This is the ALLOWLIST, and the rule it implements is deny-by-default: a request whose path is
    not in here needs a token, so a route added later is protected because nobody did anything.
    The opposite shape — a list of protected paths — is the one invariant 24 already names as the
    failure mode ("the RULE is the invariant, NOT the current list of places it applies"): the next
    endpoint would be unprotected until someone remembered. This sentence used to carry a count of
    them, and the count was wrong by ten within one slice — which is the same rot, one level down,
    in a comment arguing against exactly that.

    Derived from the directory listing for the same reason: a hand-written set of asset names goes
    stale the first time an asset is added, and the symptom would be a blank page.
    """
    paths = {"/"}
    if _WEB_DIR.is_dir():
        for path in _WEB_DIR.rglob("*"):
            if path.is_file() and path.suffix.lower() in _ASSET_SUFFIXES:
                paths.add("/" + path.relative_to(_WEB_DIR).as_posix())
    return frozenset(paths)


#: The static assets, which are this application's own source code and carry nothing private. They
#: must stay reachable without a token or the page that READS the token could never load.
PUBLIC_PATHS = _public_paths()


def api_token() -> str:
    """The token every non-public request must present.

    `RN_API_TOKEN` wins when set — that is the channel the desktop shell will use to inject a token
    it minted itself, and the one an operator fronting this with their own proxy would use. Read on
    every call rather than captured at import so a test (and a reloading dev server) can change it
    without re-importing the module.
    """
    return (os.getenv("RN_API_TOKEN") or "").strip() or _MINTED


def token_is_minted() -> bool:
    """True when nobody supplied a token and this process made one up, which is the only case where
    it has to be PRINTED — otherwise whoever set `RN_API_TOKEN` already knows it."""
    return not (os.getenv("RN_API_TOKEN") or "").strip()


def token_matches(presented: str | None) -> bool:
    """Constant-time compare, so a caller cannot learn the token one character at a time from
    response timing. `compare_digest` needs both sides to be str-with-ascii or bytes; a token that
    somehow contained non-ASCII would raise, so it is encoded explicitly."""
    if not presented:
        return False
    return secrets.compare_digest(presented.encode("utf-8"), api_token().encode("utf-8"))


def _extra_allowed_hosts() -> frozenset[str]:
    """`RN_ALLOWED_HOSTS` — the operator's explicit carve-out from the rule below.

    It exists for one real case: invariant 25 sanctions running this on a network the operator
    fully trusts, and such a deployment may legitimately be reached by a NAME (an mDNS
    `something.local`, an internal DNS record). Refusing that outright would be this module
    deciding something the operator knows better, which is the same reasoning invariant 76 uses for
    `RN_FETCH_ALLOW_CIDRS` and invariant 25 uses for allowing a non-loopback `--host` at all.
    """
    raw = os.getenv("RN_ALLOWED_HOSTS") or ""
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def _hostname(host_header: str) -> str:
    """The name out of a `Host` header, without its port. `[::1]:8000` is the case a naive
    `split(":")` gets wrong — an IPv6 literal is bracketed precisely because it contains colons."""
    host = host_header.strip()
    if host.startswith("["):
        end = host.find("]")
        return host[1:end] if end != -1 else ""
    if host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host


def host_is_allowed(host_header: str | None) -> bool:
    """Whether this request's `Host` header is one a DNS rebinding attack could not have produced.

    The rule is: **a literal IP address, or `localhost`.** That is the whole anti-rebinding
    property and it needs to know nothing about what address the server actually bound — rebinding
    requires a NAME, because what it rebinds is a DNS answer. An attacker serving `evil.com` can
    make it resolve to 127.0.0.1, but the browser still sends `Host: evil.com`, and that is the
    string this rejects.

    Consequently this does NOT reject a trusted-network deployment reached at `192.168.1.5:8000` —
    a literal IP is a literal IP. Names go through `RN_ALLOWED_HOSTS`.
    """
    if not host_header:
        return False
    name = _hostname(host_header).lower()
    if not name:
        return False
    if name in _extra_allowed_hosts():
        return True
    if name == "localhost":
        return True
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True
