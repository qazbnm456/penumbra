# Invariant 76: The SSRF carve-out for fake-IP resolvers

**The SSRF guard's DNS check accepts an operator-supplied carve-out (`RN_FETCH_ALLOW_CIDRS`), resolved in one place (`web.allow_nets`) that both host-side fetchers read.**

A split-DNS VPN or fake-IP proxy (Clash, Mihomo or Surge, with a default range of `198.18.0.0/16`) answers every public hostname with a synthetic address in a reserved range. `resolved_host_is_safe` then refuses it, correctly on the information it has, and every web and YouTube ingestion on that machine fails with "resolves to a disallowed address". The guard is not wrong; it cannot tell the operator's own resolver from an attacker's redirect, which is why the carve-out must be opt-in and supplied by the operator rather than inferred.

## A value that would disable the guard is refused

`allow_nets` short-circuits every property `resolved_host_is_safe` checks (loopback, private, link-local, reserved, unspecified, multicast), so a wide value would not widen the carve-out, it would switch the DNS-rebinding defence off. `config._NEVER_ALLOWED` therefore refuses any entry overlapping those ranges, and `0.0.0.0/0`, `::/0` and RFC 1918 ranges cannot be configured.

`is_safe_url` is not a backstop. It refuses a URL whose host is a literal blocked IP, and accepts `http://evil.example.com/` however that name resolves, so it never sees the resolved address; the DNS check is the only layer that does. An early version claimed otherwise, and under `0.0.0.0/0` a public-looking hostname resolving to `127.0.0.1` was fetchable end to end. Its test was vacuous: it used literal-IP URLs, which `is_safe_url` rejects before the DNS check runs, so it passed with the DNS check deleted. A guard test that never reaches the guard is worse than no test, because it is cited as proof. The replacement resolves a public-looking hostname to each internal address in turn.

Checking only that a value parses caught harmless typos, not dangerous ones: a dropped character turns `198.18.0.0/16` into `198.18.0.0/1`, which normalises to `128.0.0.0/1`, half the address space including cloud metadata. `_NEVER_ALLOWED` is an explicit list rather than `ipaddress`'s `is_private` and `is_reserved`, because `198.18.0.0/16` reports `is_private` and a property-based rule would refuse the one value this setting exists to accept.

The accepted cost: a split-DNS VPN that maps internal names into RFC 1918 space cannot be carved out. That is the SSRF this guard exists to prevent, and there is deliberately no override.

## One reader, read at the boundary

`parsers/youtube.py` imports `web.allow_nets` rather than reading the variable again, so the two fetchers can never disagree about what is permitted (invariant 13's one-copy rule for a guard); a source-tree assertion pins it. It is resolved on every call, never cached at import, so tests and a long-running server see changes. `config.fetch_allow_cidrs` is a standalone reader, not a `NotebookConfig` field, for invariant 30's reason: ingesting a URL has nothing to do with whether a model is configured.

An unparseable entry raises instead of being skipped, which inverts `rlm_harness.tools.parse_cidrs`. Skipping is right for a tool the model calls mid-run, and wrong for an operator setting read once: dropping the only entry restores full strictness and reproduces the exact symptom the setting was meant to fix, with nothing connecting the two. The resulting `SystemExit` is handled as invariant 24 requires, so a malformed value is a clean 500, not an escaped exception, and the refusal names the variable, because otherwise it looks exactly like a genuine SSRF refusal.

This was found through a test that failed on one developer's machine and passed in CI, and it was dismissed three times as a sandbox artifact. The test was doing live DNS, and it was correctly reporting that the product refused every URL on that machine. A test that fails on one machine and passes in CI is evidence about the product until proven otherwise. The test is hermetic now and still catches the mutation it exists for.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
