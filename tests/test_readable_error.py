"""**`readableError` is EXECUTED here, not described.**

The previous test for this function re-compiled its regex literals with Python's `re` and never
called it. Replacing the whole body with `return String(text || "")` left all 917 tests green —
while the live function was returning the EMPTY STRING for two of the commonest provider failures,
so the page rendered a blank reason and an error toast whose only content was its dismiss button.
A test that pins a function's inputs is not a test of the function.

Every raw string below was captured from a running server or from `litellm` itself. None is
invented, because the whole difficulty of this function is that real messages nest their noise in
ways an invented sample does not.

`node` is required rather than skipped-if-absent. `AGENTS.md` records the trap already: a test that
silently disappears when a tool is missing makes a local run greener than CI, and CI installs node
for exactly this file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).with_name("readable_error_harness.mjs")


def _clean(*messages: str, session: dict | None = None, ui: str = "en") -> list[str]:
    node = shutil.which("node")
    assert node, (
        "node is required to run the shipped `readableError`. CI installs it; see "
        ".github/workflows/ci.yml. A skip here would make a local run greener than CI, which is "
        "the trap AGENTS.md's Verify section is about."
    )
    done = subprocess.run(
        [node, str(HARNESS)],
        input=json.dumps({"cases": list(messages), "session": session, "ui": ui}),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,  # the assertion below reports the harness's own stderr, which is more useful
    )
    assert done.returncode == 0, f"harness failed: {done.stderr}"
    return json.loads(done.stdout)["results"]


#: What must NEVER reach a reader, per the rule this function exists to keep: a status code, an
#: exception class, an OpenSSL source line, a run UUID, a signal number, a shell incantation, a
#: Python repr. `PN_MAIN_MODEL` and `PN_MAX_TOKENS` are exempt — naming the variable IS the action.
FORBIDDEN = (
    "litellm", "Exception", "Error code", "OpenAIException", "PdfiumError", "Traceback",
    "{'", '{"', "_ssl.c", "exit -9", "set -a",
)


def _assert_readable(raw: str, cleaned: str) -> None:
    assert cleaned.strip(), f"{raw[:60]!r} was cleaned away to nothing"
    for token in FORBIDDEN:
        assert token not in cleaned, f"{token!r} reached the reader in {cleaned!r}"


def test_a_provider_failure_says_what_to_do_and_keeps_the_model_name():
    wrong_key, no_model, too_long, context = _clean(
        "[openai/gpt-4o-mini] litellm.AuthenticationError: AuthenticationError: OpenAIException - "
        "Incorrect API key provided: unused. - caused by AuthenticationError: Error code: 401 - "
        "{'error': {'message': 'x', 'code': 'invalid_api_key'}}",
        "[openai/no-such-model] litellm.NotFoundError: model_not_found",
        "LMInvalidRequestError('[openai/gpt-4o-mini] litellm.BadRequestError: OpenAIException - "
        "max_tokens is too large: 32768. This model supports at most 16384 completion tokens.')",
        "ContextWindowExceededError: [openai/gpt-4o-mini] litellm.ContextWindowExceededError: "
        "This model's maximum context length is 128000 tokens.",
    )
    for raw, cleaned in zip(("key", "model", "tokens", "context"), (wrong_key, no_model, too_long, context)):
        _assert_readable(raw, cleaned)
    # The model string is the one actionable thing in a provider error: it says which credential
    # and which line of the environment to go and look at.
    assert "openai/gpt-4o-mini" in wrong_key
    assert "PN_API_KEY" in wrong_key, (
        "the sentence never names the variable the product actually reads, while the sibling "
        "branches name PN_MAIN_MODEL"
    )

    # **`Missing credentials` is the FIRST-RUN failure** — no key configured at all, the commonest
    # thing a new BYOK install can do — and it reached the reader raw on the Horizon front page. Two
    # independent causes: the shape was unrecognised, and `LEADING_NOISE` being `^`-anchored let a
    # class-name prefix shield the `[vendor/model]` tag from the only rule that strips it. The chat
    # path could not match `FROM_PROVIDER` either: `\bLM[A-Za-z]*Error\b` has no word boundary
    # inside `RLMTaskError`.
    first_run, chat_path = _clean(
        "LMServerError: [openai/gpt-4o-mini] litellm.InternalServerError: InternalServerError: "
        "OpenAIException - Missing credentials. Please pass an `api_key`, `workload_identity`, "
        "`admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.",
        "RLMTaskError: [openai/gpt-4o-mini] litellm.InternalServerError: OpenAIException - "
        "Missing credentials.",
    )
    # **`RLMTaskError` has no word boundary before `LM`**, so a provider failure carrying only that
    # class — no `litellm`, no `[vendor/model]` tag — failed the provenance gate and fell through to
    # the tail, printing the provider's own wording instead of the actionable sentence.
    (bare_task,) = _clean("RLMTaskError: Missing credentials for the configured provider.")
    assert "PN_API_KEY" in bare_task, (
        f"a provider failure was not recognised as one: {bare_task!r}"
    )

    for cleaned in (first_run, chat_path):
        _assert_readable("missing-credentials", cleaned)
        assert "PN_API_KEY" in cleaned, f"the actionable variable is missing: {cleaned!r}"
        assert "[openai/" not in cleaned, f"the vendor/model tag survived: {cleaned!r}"
        for noise in ("workload_identity", "admin_api_key", "OPENAI_ADMIN_KEY"):
            assert noise not in cleaned, (
                f"{noise} is a credential this product has no concept of: {cleaned!r}"
            )
    assert "openai/no-such-model" in no_model
    # The two SIZE refusals are different problems with different actions, and naming the lever is
    # the point of each.
    assert "PN_MAX_TOKENS" in too_long
    assert "PN_MAX_TOKENS" not in context and "PN_MAIN_MODEL" not in context

    # **`Received Model Group=` is litellm ROUTER BOILERPLATE, not evidence of a missing model.**
    # It appears in every router error, so with it in the pattern a `max_tokens` refusal rendered
    # as "your provider has no model called gpt-4o-mini" - sending the reader to pick another
    # OpenAI model, which fails identically, while the Horizon strip on the same page correctly
    # blamed something else. This is the exact string the running server produced.
    (routed,) = _clean(
        "LMInvalidRequestError: [openai/gpt-4o-mini] litellm.BadRequestError: OpenAIException - "
        "max_tokens is too large: 32768. This model supports at most 16384 completion tokens, "
        "whereas you provided 32768.. Received Model Group=gpt-4o-mini\n"
        "Available Model Group Fallbacks=None"
    )
    _assert_readable("router", routed)
    assert "PN_MAX_TOKENS" in routed, f"the actual cause was lost: {routed!r}"
    assert "PN_MAIN_MODEL" not in routed, (
        f"a router error was read as a missing model: {routed!r}"
    )


def test_a_website_status_is_never_reported_as_a_credential_problem():
    """**`403` means one thing from a provider and another from a web page**, and matching the bare
    number told a reader their API key was wrong because a site had blocked a bot — then sent them
    to change it. A paywalled or bot-blocked page is the commonest capture failure there is.
    """
    forbidden, gone, busy, broken = _clean(
        "FetchError: fetch error for 'https://example.com/a': HTTP Error 403: FORBIDDEN",
        "FetchError: fetch error for 'https://example.com/b': HTTP Error 404: NOT FOUND",
        "FetchError: fetch error for 'https://example.com/c': HTTP Error 429: TOO MANY REQUESTS",
        "FetchError: fetch error for 'https://example.com/d': HTTP Error 503: SERVICE UNAVAILABLE",
    )
    for status, cleaned in (("403", forbidden), ("404", gone), ("429", busy), ("503", broken)):
        _assert_readable("fetch", cleaned)
        for word in ("API key", "PN_MAIN_MODEL", "quota", "provider"):
            assert word not in cleaned, f"a website's status was blamed on the model: {cleaned!r}"
        # TRANSLATED, not merely un-blamed. A status code is the thing this function exists to
        # replace, and passing the sentence through with the number still in it is not doing that.
        assert status not in cleaned and "HTTP Error" not in cleaned, (
            f"the raw status reached the reader: {cleaned!r}"
        )
        assert "example.com" not in cleaned, (
            f"the URL is already on screen in the row this is reporting on: {cleaned!r}"
        )
    assert forbidden != gone != busy != broken, "four different statuses must not read alike"

    # **Every URL above is `example.com`, and that is what let this through.** The provenance gate
    # is a word test: `litellm`, `OpenAIException` and the rest are ordinary words that appear in
    # ordinary addresses, so capturing a page ON one of those sites answered the bot-block with
    # "Your API key was rejected" and sent the reader to change a credential that was fine. A URL
    # says where a message is ABOUT, never where it came FROM.
    for url in (
        "https://docs.litellm.ai/docs/proxy",
        "https://github.com/BerriAI/litellm/issues/1",
        "https://example.com/OpenAIException",
        "https://blog.example.com/AnthropicException-explained",
    ):
        cleaned = _clean(f"FetchError: fetch error for '{url}': HTTP Error 403: FORBIDDEN")[0]
        assert cleaned == forbidden, (
            f"a provider's name inside a URL changed the diagnosis: {url} -> {cleaned!r}"
        )
        for word in ("API key", "PN_API_KEY", "credential", "quota"):
            assert word not in cleaned, f"a blocked page was blamed on the model: {cleaned!r}"

    # ...while a real provider failure that merely MENTIONS a URL is still a provider failure.
    keyed = _clean(
        "[openai/gpt-4o-mini] litellm.AuthenticationError: OpenAIException - Incorrect API key "
        "provided. See https://platform.openai.com/account/api-keys for details."
    )[0]
    assert keyed != forbidden, "a genuine credential failure must not read as a blocked page"
    assert "API key" in keyed, keyed

    # **A status the branch has no words for must still not print the number or the URL.** 402, 406,
    # 451 and a bare 400 are ordinary paywall and bot-block answers and every one of them fell
    # through to the tail, rendering `fetch error for 'https://…': HTTP Error 402: PAYMENT
    # REQUIRED`. And a website answering 499 (nginx's "client closed request") was reported as
    # "You stopped this one." about a capture the reader had never touched.
    odd = _clean(
        "FetchError: fetch error for 'https://example.com/p': HTTP Error 402: PAYMENT REQUIRED",
        "FetchError: fetch error for 'https://example.com/q': HTTP Error 451: UNAVAILABLE",
        "FetchError: fetch error for 'https://example.com/r': HTTP Error 406: NOT ACCEPTABLE",
        "FetchError: fetch error for 'https://example.com/s': HTTP Error 499: CLIENT CLOSED",
    )
    for status, cleaned in zip(("402", "451", "406", "499"), odd):
        _assert_readable("odd-status", cleaned)
        assert status not in cleaned and "example.com" not in cleaned, (
            f"HTTP {status} reached the reader raw: {cleaned!r}"
        )
    assert "stopped" not in odd[3].lower(), (
        f"a website's 499 was read as the reader cancelling their own run: {odd[3]!r}"
    )

    # And a real cancellation still reads as one.
    (stopped,) = _clean("499: run 'reading-abc' was stopped before it started")
    assert "499" not in stopped and "reading-abc" not in stopped

    # A fetch failure that carries a status WITHOUT the `HTTP Error NNN` wording, so it falls past
    # the branch above and reaches the provider branches. This is what the `FROM_PROVIDER` gate is
    # for: without it `\b40[13]\b` fires and the reader is told to go and check their API key.
    (odd,) = _clean(
        "FetchError: fetch error for 'https://example.com/e': 403 Client Error: Forbidden for url"
    )
    _assert_readable("fetch-403-no-wording", odd)
    for word in ("API key", "PN_MAIN_MODEL", "quota"):
        assert word not in odd, f"a website's 403 was blamed on the model provider: {odd!r}"


def test_nothing_is_ever_cleaned_away_to_nothing():
    """The failure that made this file necessary. An unanchored strip matched the `[vendor/model]`
    tag at position 0 and returned `""`, so the reason vanished from the page entirely. A guess
    about what is noise that eats the whole sentence is worse than the raw text it replaced.
    """
    raws = [
        "ContextWindowExceededError: [openai/gpt-4o-mini] litellm.SomethingNobodyHasSeen: odd",
        "[openai/gpt-4o-mini] litellm.BrandNewError: a shape this build does not know",
        "The locator [page:3] is not in this corpus",
        "SomeFutureError: {'not': 'a dict we know'}",
        "a plain sentence with no decoration at all",
        "422: could not ingest: SomeOddError: the file ended early",
        # NOTHING BUT NOISE. Every strip in the tail applies and there is no sentence underneath,
        # which is the case the `|| raw` fallback exists for: showing the raw text is worse than
        # showing a sentence, and infinitely better than showing a blank.
        "[openai/gpt-4o-mini] litellm.SomeError:",
        "SomeError:",
    ]
    for raw, cleaned in zip(raws, _clean(*raws)):
        assert cleaned.strip(), f"{raw!r} was cleaned away to nothing"
    # And a bracket in ordinary prose is prose, not a blob to strip.
    assert _clean("The locator [page:3] is not in this corpus")[0] == (
        "The locator [page:3] is not in this corpus"
    )


def test_an_unrecognised_message_keeps_its_sentence_and_loses_only_the_noise():
    nested, tagged, blob = _clean(
        "422: could not ingest: SomeOddError: the file ended early",
        "[openai/gpt-4o-mini] litellm.SomeError: no route to that host",
        "the real reason - {'error': {'message': 'internal', 'code': 500}}",
    )
    assert nested == "could not ingest: the file ended early"
    assert tagged == "no route to that host"

    # **A class name SHIELDS a leading `[vendor/model]` tag from the only rule that strips it**, and
    # `OpenAIException - ` joins with a dash rather than a colon. Both were true of the real
    # first-run failure, and both are invisible unless the message falls through to the tail — every
    # earlier sample here is caught by a branch first.
    (shielded,) = _clean(
        "SomeFutureError: [openai/gpt-4o-mini] litellm.InternalServerError: OpenAIException - "
        "a reason nobody has a branch for"
    )
    assert shielded == "a reason nobody has a branch for", (
        f"the tag or the class name survived into the reader's sentence: {shielded!r}"
    )
    assert blob == "the real reason"

    # **Router boilerplate with no recognised cause behind it.** `Received Model Group=` is in
    # every litellm router error; reading it as "no such model" sends the reader to change
    # `PN_MAIN_MODEL` over a failure that has nothing to do with the model's name. With nothing
    # else to go on, the honest answer is the sentence the server actually sent.
    (routed,) = _clean(
        "LMError: Failed to produce a valid 'answer' after 1 attempts - caused by Error code: 400. "
        "Received Model Group=gpt-4o-mini\nAvailable Model Group Fallbacks=None"
    )
    assert "PN_MAIN_MODEL" not in routed, (
        f"router boilerplate was read as a missing model: {routed!r}"
    )
    assert "Failed to produce a valid 'answer'" in routed, (
        f"the sentence the server sent was thrown away: {routed!r}"
    )


def test_a_stopped_run_is_not_an_error_and_a_missing_model_names_its_variable():
    stopped, killed, no_lm = _clean(
        "499: run 'reading-4d2662ef-79ea-4598-83a0-00a573fc9dff' was stopped before it started",
        "502: worker for run 'reading-faac4924' produced no output (exit -9); stderr:",
        "PN_MAIN_MODEL is not set. Set it and restart, e.g. `set -a; . ./.env; set +a`",
    )
    assert stopped == killed, "both halves of a cancellation read the same to the person who asked"
    for cleaned in (stopped, killed):
        assert "499" not in cleaned and "exit -9" not in cleaned and "4d2662ef" not in cleaned
    assert "PN_MAIN_MODEL" in no_lm, "the variable name is the actionable half"
    assert "set -a" not in no_lm, "a shell command in a chat bubble is the terminal's voice"


@pytest.mark.parametrize(
    "raw",
    [
        "413: upload declares 60000184 bytes, exceeding the 50000000-byte limit",
        (
            "422: could not ingest: ValueError: unsupported file type '.csv' - expected one of "
            "['.md', '.pdf', '.txt']"
        ),
        "422: could not ingest: PdfiumError: Failed to load document (PDFium: Data format error).",
        (
            "<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of "
            "protocol (_ssl.c:1028)>"
        ),
    ],
)
def test_every_known_shape_reaches_the_reader_clean(raw: str) -> None:
    _assert_readable(raw, _clean(raw)[0])


def test_losing_the_server_says_so_instead_of_quoting_the_browser():
    """**Three browsers, three internal strings, none of them meaning anything to a reader.**

    A rejected `fetch` carries no status at all, so none of the status branches could see it and the
    raw message went straight to the surface: a capture said "Could not capture that: Failed to
    fetch", a question failed with "Failed to fetch", and in a zh-Hant interface both stayed in
    English. It never said the one thing that is true and actionable — this all runs on loopback, so
    the overwhelmingly likely cause is that `penumbra serve` is no longer running.

    Distinct from `UNREACHABLE`, which is the SERVER failing to fetch a source the reader asked for.
    """
    chrome, firefox, safari, bare = _clean(
        "TypeError: Failed to fetch",
        "NetworkError when attempting to fetch resource.",
        "Load failed",
        "Failed to fetch",
    )
    assert chrome == firefox == safari == bare, (
        f"the same failure reads differently per browser: {chrome!r} {firefox!r} {safari!r} {bare!r}"
    )
    for cleaned in (chrome, firefox, safari, bare):
        _assert_readable("no-server", cleaned)
        assert "fetch" not in cleaned.lower(), f"the browser's own wording reached the reader: {cleaned!r}"
        assert "serve" in cleaned, f"it must name what to check: {cleaned!r}"

    # A source URL the SERVER could not reach is a different sentence, and must stay one.
    unreachable = _clean(
        "FetchError: fetch error for 'https://example.com/a': <urlopen error [Errno 8] "
        "nodename nor servname provided, or not known>"
    )[0]
    assert unreachable != chrome, "the page losing its server is not a source being unreachable"


def test_a_run_that_hit_the_time_limit_is_not_reported_as_a_network_fault():
    """**The wall-clock backstop firing is a DESIGNED outcome**, and `UNREACHABLE` matched the bare
    words "timed out" anywhere, above every provider branch.

    So a `long` Audio Overview that hit `PN_RUN_TIMEOUT_SECONDS` — the thing invariant 68 exists
    for, since 60-90 accumulated utterances (invariant 64) could not fit under the 300s default —
    told the reader "Could not reach that address." for a run in which no address was involved,
    right after they had paid for a 5x-budget episode. `runner.py` names the knob in the message
    precisely so they can act; this kept the knob in the raw text and threw away the diagnosis.
    """
    timed_out, refused_provider, page, source_url = _clean(
        "502: run 'nb-x-abc' timed out after 300.0s and was cancelled (the wall-clock backstop; "
        "raise PN_RUN_TIMEOUT_SECONDS if the model is simply slow)",
        "502: RLMTaskError: ... caused by APIConnectionError: [Errno 61] Connection refused",
        "Failed to produce a valid 'answer' after 1 attempts — caused by <!doctype html> <html> "
        "<head> <meta charset=\"utf-8\"> <title>Unable to connect</title> <style> * { margin: 0; }",
        "FetchError: fetch error for 'https://example.com/a': <urlopen error [Errno 8] "
        "nodename nor servname provided, or not known>",
    )

    # Four different failures, four different sentences.
    assert len({timed_out, refused_provider, page, source_url}) == 4, (
        f"{timed_out!r} {refused_provider!r} {page!r} {source_url!r}"
    )
    for cleaned in (timed_out, refused_provider, page, source_url):
        _assert_readable("err", cleaned)

    # The timeout names the knob, because that is the only thing the reader can do about it.
    assert "PN_RUN_TIMEOUT_SECONDS" in timed_out, timed_out
    assert "address" not in timed_out.lower(), "a run has no address to be unreachable at"

    # A dead local model server is the commonest first-run failure for a BYOK product.
    assert "PN_BASE_URL" in refused_provider, refused_provider

    # A proxy answering a model request with a web page: none of the markup reaches the reader.
    assert "<" not in page and "doctype" not in page.lower(), page

    # ...and a SOURCE URL that really is unreachable still says so.
    assert "address" in source_url.lower(), source_url


def test_a_fake_ip_refusal_keeps_the_setting_that_fixes_it():
    """Behind a fake-IP proxy every link is refused, and the server's sentence names the fix. The
    generic "not one this can fetch" dropped it, and a user could not add a single URL."""
    raw = (
        "refused: 'https://example.com/' resolves to a disallowed address "
        "(if you are behind a fake-IP proxy or split-DNS VPN, set PN_FETCH_ALLOW_CIDRS)"
    )
    (cleaned,) = _clean(raw)
    assert "PN_FETCH_ALLOW_CIDRS" in cleaned and "198.18.0.0/15" in cleaned, cleaned
    (plain,) = _clean("refused: 'file:///etc' is not a permitted external http(s) URL")
    assert plain == "That address is not one this can fetch."


def test_a_setting_the_server_cannot_run_with_keeps_its_reason():
    """Every `server misconfigured` 500 read "its log has the detail", over a log that had none,
    so a typo in the configuration file was invisible from the page."""
    reason = "PN_FETCH_ALLOW_CIDRS entry '198.18.0.0/1' is too broad"
    (cleaned,) = _clean(f"500: server misconfigured: {reason}")
    assert reason in cleaned and "log" not in cleaned, cleaned
    (cap,) = _clean("413: assembled corpus is 9000001 chars, over the 8000000 cap (PN_MAX_CORPUS_CHARS) — x")
    assert "PN_MAX_CORPUS_CHARS" in cap and "Remove a source" in cap, cap


def test_a_desktop_hint_quotes_the_menu_in_the_language_the_menu_bar_uses():
    """The menu follows the OS language and the page its own setting. A Chinese interface on an
    English Mac quoted 「檔案 > 開啟設定檔…」 at a menu reading "File > Open Configuration File…"."""
    raw = "PN_MAIN_MODEL is not set"
    (english_menu,) = _clean(raw, session={"penumbra-shell": "desktop", "penumbra-menu": "en"}, ui="zh-Hant")
    assert "File > Open Configuration File…" in english_menu, english_menu
    (chinese_menu,) = _clean(raw, session={"penumbra-shell": "desktop", "penumbra-menu": "zh"})
    assert "檔案 > 開啟設定檔…" in chinese_menu, chinese_menu
    (unknown,) = _clean(raw, session={"penumbra-shell": "desktop"}, ui="zh-Hant")
    assert "檔案 > 開啟設定檔…" in unknown, "without the shell's word, the interface language is the guess"
    (browser,) = _clean(raw)
    assert "File >" not in browser and "檔案" not in browser, "a browser tab has no menu to point at"


def test_a_missing_claude_code_says_what_to_install_not_how_to_edit_path():
    raw = (
        "Failed to produce a valid 'answer' after 1 attempts — caused by Claude Code not found. "
        "Install with: npm install -g @anthropic-ai/claude-code If already installed locally, try: "
        'export PATH="$HOME/node_modules/.bin:$PATH"'
    )
    (cleaned,) = _clean(raw)
    assert "Install Claude Code" in cleaned and "npm" not in cleaned and "PATH" not in cleaned, cleaned
