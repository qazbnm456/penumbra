"""`auth.py` — the local API token and the Host check (AGENTS.md invariant 77).

**No `importorskip` here, deliberately.** `auth.py` imports nothing but the standard library, so
these tests run on a bare `uv sync` exactly like `test_runner.py`'s do. `test_api.py` covers the
same rules end-to-end through the middleware, but it is invisible without the `api` extra — and a
security control whose only tests can silently not be collected is the trap AGENTS.md's Verify
section already describes for `chatterbox`. This file is the floor that always runs.
"""

from __future__ import annotations

import pytest

from penumbra import auth


def test_api_token_prefers_the_environment(monkeypatch):
    """`PN_API_TOKEN` is the channel the desktop shell injects a token it minted itself."""
    monkeypatch.setenv("PN_API_TOKEN", "shell-supplied")
    assert auth.api_token() == "shell-supplied"
    assert auth.token_is_minted() is False


def test_api_token_is_minted_and_stable_when_the_environment_is_silent(monkeypatch):
    monkeypatch.delenv("PN_API_TOKEN", raising=False)
    assert auth.token_is_minted() is True
    first = auth.api_token()
    assert first and first == auth.api_token()
    # 256 bits of urandom, url-safe — long enough that appending it to a query string is safe and
    # guessing it is not a strategy.
    assert len(first) >= 40


def test_whitespace_only_environment_token_does_not_disable_the_token(monkeypatch):
    """`PN_API_TOKEN="   "` must not read as "authentication off". Falling back to the minted token
    is the safe direction: the server stays protected and the operator finds out because their own
    value does not work, rather than because nothing does."""
    monkeypatch.setenv("PN_API_TOKEN", "   ")
    assert auth.token_is_minted() is True
    assert auth.api_token().strip() != ""
    assert not auth.token_matches("")
    assert not auth.token_matches("   ")


def test_token_matches_only_the_real_token(monkeypatch):
    monkeypatch.setenv("PN_API_TOKEN", "correct-horse")
    assert auth.token_matches("correct-horse")
    for wrong in (None, "", "correct-hors", "correct-horsee", "CORRECT-HORSE", " correct-horse"):
        assert not auth.token_matches(wrong), wrong


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "127.0.0.1:8000",
        "localhost",
        "localhost:8000",
        "[::1]",
        "[::1]:8000",
        # A trusted-network deployment reached by IP (invariant 25 sanctions this). A literal
        # address cannot be the product of DNS rebinding, so the rule does not need to reject it.
        "192.168.1.5:8000",
    ],
)
def test_host_is_allowed_for_literal_addresses_and_localhost(host, monkeypatch):
    monkeypatch.delenv("PN_ALLOWED_HOSTS", raising=False)
    assert auth.host_is_allowed(host) is True


@pytest.mark.parametrize(
    "host",
    [
        None,
        "",
        "   ",
        # The whole point: an attacker's page keeps its own origin, and its name re-resolves to
        # 127.0.0.1. The browser still sends the NAME, and that is what this rejects.
        "evil.example",
        "evil.example:8000",
        "orbit.local",
        "[::1",  # malformed bracket — must not be parsed into something permissive
    ],
)
def test_host_is_refused_for_dns_names_and_junk(host, monkeypatch):
    monkeypatch.delenv("PN_ALLOWED_HOSTS", raising=False)
    assert auth.host_is_allowed(host) is False


def test_allowed_hosts_carve_out_is_explicit_and_case_insensitive(monkeypatch):
    """The operator's opt-out, for a genuinely-theirs name (mDNS, internal DNS). Same shape as
    invariant 76's `PN_FETCH_ALLOW_CIDRS`: the guard cannot see the operator's network, so the
    operator gets to say so — explicitly, never by the guard guessing."""
    monkeypatch.setenv("PN_ALLOWED_HOSTS", "orbit.local, Desk.Example ")
    assert auth.host_is_allowed("orbit.local:8000") is True
    assert auth.host_is_allowed("DESK.EXAMPLE") is True
    assert auth.host_is_allowed("evil.example") is False


def test_public_paths_are_the_static_assets_and_nothing_else():
    """Deny-by-default: the allowlist is the web directory, so an API route added later is covered
    without anyone remembering. Invariant 24 already names the opposite shape as the failure."""
    assert "/" in auth.PUBLIC_PATHS
    assert "/index.html" in auth.PUBLIC_PATHS
    assert "/app.js" in auth.PUBLIC_PATHS
    assert "/style.css" in auth.PUBLIC_PATHS
    for protected in ("/orbits", "/settings", "/orbits/x/ask", "/docs", "/openapi.json"):
        assert protected not in auth.PUBLIC_PATHS, protected


def test_public_paths_are_derived_from_the_directory_not_hand_listed():
    """A hand-written asset list goes stale the first time an asset is added, and the symptom is a
    blank page nobody connects to this file. Every ASSET in `web/` must be reachable.

    **Assets, not every file.** `web/` also holds `DESIGN.md`, a 47 KB internal spec that shipped in
    the wheel and answered unauthenticated because the allowlist was the whole directory listing —
    which is an argument about assets applied to something that is not one. The derivation stays
    (a hand-written list is the failure this test exists for); what it filters on is the suffix,
    which keeps deny-by-default intact: something with a suffix nobody listed needs a token.
    """
    web_dir = auth._WEB_DIR
    assets = {
        "/" + path.relative_to(web_dir).as_posix()
        for path in web_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in auth._ASSET_SUFFIXES
    }
    assert assets, "web/ has no assets — the assertion below would be vacuous"
    assert assets <= set(auth.PUBLIC_PATHS)
    # ...and everything the page needs is in there, or nothing could load the token.
    for needed in ("/index.html", "/app.js", "/style.css", "/i18n.js"):
        assert needed in assets, needed

    # A non-asset in the same directory is NOT public. `.md` is the case that put it there.
    non_assets = {
        "/" + path.relative_to(web_dir).as_posix()
        for path in web_dir.rglob("*")
        if path.is_file() and path.suffix.lower() not in auth._ASSET_SUFFIXES
    }
    assert non_assets, "nothing non-asset lives in web/ any more; this half is now vacuous"
    assert not (non_assets & set(auth.PUBLIC_PATHS)), sorted(non_assets & set(auth.PUBLIC_PATHS))
