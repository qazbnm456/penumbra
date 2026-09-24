# Invariant 2: The SSRF guard is re-checked on every redirect

**`parsers/web.py` re-validates the SSRF guard on every redirect hop, not just the requested URL.**

`_SafeRedirectHandler` runs `is_safe_url` and `resolved_host_is_safe` again on each `Location` target before following it. Without this, a safe-looking URL could redirect to an internal, loopback or metadata address, and the default `urllib` opener would follow it unchecked. Do not go back to plain `urllib.request.urlopen`.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
