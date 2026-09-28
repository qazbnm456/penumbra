# Invariant 2: The SSRF guard is re-checked on every redirect

**`parsers/web.py` re-validates the SSRF guard on every redirect hop, not just the requested URL.**

`_SafeRedirectHandler` runs `is_safe_url` and `resolved_host_is_safe` again on each `Location` target before following it. Without this, a safe-looking URL could redirect to an internal, loopback or metadata address, and the default `urllib` opener would follow it unchecked. Do not go back to plain `urllib.request.urlopen`.

A captured link follows at most five hops (`web._TrailRedirectHandler`, a subclass of the guarded handler, so every hop is still checked), and the hops are recorded: when a link leads to another site, the capture keeps the address it was given as its origin and records the page it reached and the hosts in between (`preview.final_url`, `preview.via`), shown as "via t.co" so a shortener never stands in for the page. A wrapper that carries its destination in the address (a platform's click-through page, a mail filter's rewrite) is unwrapped from the address with no request to the wrapper (`web.unwrap_url`), as a mail-security gateway decodes a rewritten link. Nothing checks a destination's reputation with a third party: that would send every captured address off this machine. The reader's browser never follows the link; the server fetches it with no cookies and runs no script.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
