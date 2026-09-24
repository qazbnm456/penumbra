"""Web page ingestion: fetch (host-side, one-shot) + extract main content with trafilatura.

AGENTS.md invariant 1: the fetch happens exactly ONCE, here, during ingestion — this module is
never handed to the RLM as a `tools=` entry. Reuses `rlm_harness.tools.fetch`'s pure SSRF-guard
functions (`is_safe_url`, `resolved_host_is_safe`), not `make_fetch_tool` itself — that factory
builds a live RLM *tool*, which is exactly what invariant 1 says this call site must never become.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

import trafilatura
from rlm_harness.tools.fetch import is_safe_url, parse_cidrs, resolved_host_is_safe

from ..config import fetch_allow_cidrs, max_upload_bytes
from ..schema import Source, SourceBlock

Fetcher = "Callable[[str], str]"  # documented shape; see parse_web's `fetcher` param


class FetchError(RuntimeError):
    """A URL was unsafe to fetch, or the fetch/extraction otherwise failed."""


def allow_nets() -> tuple:
    """The operator's SSRF carve-out, resolved fresh per call — the ONE place either host-side
    fetcher gets it (`parsers/youtube.py` imports this rather than re-reading the variable, so the
    two can never disagree about what is permitted).

    Read per call rather than cached at import: a module-level constant would freeze whatever the
    environment held when `web.py` was first imported, which a test cannot then change and a
    long-running server cannot pick up. `parse_cidrs` on a one- or two-entry tuple costs nothing
    beside a network fetch. `config.fetch_allow_cidrs` has already rejected an unparseable entry,
    so `parse_cidrs`'s own warn-and-skip can never silently empty this."""
    return parse_cidrs(fetch_allow_cidrs())


def _check_safe(url: str) -> None:
    if not is_safe_url(url):
        raise FetchError(f"refused: {url!r} is not a permitted external http(s) URL")
    parsed = urlparse(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not resolved_host_is_safe(parsed.hostname or "", port, allow_nets=allow_nets()):
        raise FetchError(
            f"refused: {url!r} resolves to a disallowed address "
            "(if you are behind a fake-IP proxy or split-DNS VPN, set RN_FETCH_ALLOW_CIDRS)"
        )


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validates EVERY redirect hop against the SSRF guard before following it.

    The default opener follows a `Location` header unconditionally, which would let a single 3xx
    response bounce an initially-safe URL to an internal/loopback/metadata target with no further
    check — `rlm_harness.tools.fetch`'s own docstring calls this out explicitly ("call it INSIDE your
    fetcher at connection time, and on every redirect hop"); found by an independent review of the
    first version of this module, which fetched with the default opener and had no per-hop check.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_safe(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirectHandler)


def _fetch(url: str, *, timeout: float = 15.0) -> tuple[bytes, str]:
    """The bytes and the declared content type, both of which the caller needs.

    **Bounded.** The read used to be `resp.read()` with no argument, on an endpoint where any token
    holder can paste any URL — one link to a large file was a memory spike the server had no say
    in. `max_upload_bytes()` is the same bound an upload gets, for the same reason and with the same
    independence from `NotebookConfig` (invariant 30): bytes arriving from outside in one request,
    on a path that must work whether or not a model is configured. Read one byte PAST the cap, so
    hitting it is distinguishable from a file that happens to be exactly that size.
    """
    _check_safe(url)
    cap = max_upload_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "rlm-notebook/0.1"})
    try:
        with _opener.open(req, timeout=timeout) as resp:
            raw = resp.read(cap + 1)
            content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    except FetchError:
        raise
    except (urllib.error.URLError, TimeoutError) as exc:
        raise FetchError(f"fetch error for {url!r}: {exc}") from exc
    if len(raw) > cap:
        raise FetchError(f"{url!r} is larger than the {cap}-byte limit")
    return raw, content_type


def _default_fetcher(url: str, *, timeout: float = 15.0) -> str:
    """The html-only seam the `fetcher=` parameter documents. Kept as-is so every existing caller
    and every test fake keeps the shape it was written against."""
    raw, _ = _fetch(url, timeout=timeout)
    return raw.decode("utf-8", errors="replace")


#: The `<meta>` tags worth showing in a Sources row, in the order they are preferred. Open Graph
#: first because a page that bothers to set it has written copy meant to be shown as a card.
_PREVIEW_META = {
    "title": ("og:title", "twitter:title"),
    "description": ("og:description", "twitter:description", "description"),
    "site": ("og:site_name",),
}

#: Every quantifier here is BOUNDED, and `extract_preview` windows its input as well. Both are
#: required, and neither is defensive tidying: with `[^>]*?` an independent security review measured
#: CATASTROPHIC BACKTRACKING on `'<meta name="a" ' * n` — unclosed tags, so `[^>]*?` never reaches a
#: `>` and every `<meta ` start position rescans the whole run. Cubic, measured end to end through
#: `parse_web`: 6.5KB took 0.50s, 15.3KB took 12.98s, 19.7KB took 38.08s. `re` does NOT release the
#: GIL — a watchdog thread saw a 14s hard pause — so `asyncio.to_thread` buys the event loop
#: nothing. On an API where any token holder can paste any URL (invariant 25), and where
#: `_default_fetcher` reads a response of any size, that is a one-request freeze of the whole
#: server. A WELL-FORMED 681KB page with 5000 meta tags parsed in 0.019s, because a real
#: `<meta …>` closes its `>`; the pathological input is the only one these bounds cost anything on.
_ATTR_GAP = r"[^>]{0,300}?"
_META_TAG = re.compile(
    rf"""<meta\s{_ATTR_GAP}(?:property|name)\s*=\s*["']([^"']{{1,200}})["']{_ATTR_GAP}"""
    rf"""content\s*=\s*["']([^"']{{0,2000}})["']"""
    rf"""|<meta\s{_ATTR_GAP}content\s*=\s*["']([^"']{{0,2000}})["']{_ATTR_GAP}"""
    rf"""(?:property|name)\s*=\s*["']([^"']{{1,200}})["']""",
    re.IGNORECASE | re.DOTALL,
)
_TITLE_TAG = re.compile(r"<title[^>]{0,200}>(.{0,2000}?)</title>", re.IGNORECASE | re.DOTALL)

#: How much of the document the scraper looks at. A preview only ever lives in `<head>`, so this is a
#: WINDOW, not a truncation of the source: `parse_web` still hands the whole document to
#: `trafilatura`, and nothing a reader can cite is affected.
_PREVIEW_WINDOW = 64 * 1024


def extract_preview(html: str) -> dict[str, str]:
    """DISPLAY-ONLY page metadata, parsed from HTML this function was already handed.

    **No extra request is made, and no image is ever referenced.** `og:image` is deliberately absent:
    rendering one would make the reader's browser fetch a URL the page author chose, handing that
    third party the reader's IP and a request to log, for a thumbnail. The value of a preview is the
    title and the description; the picture is not worth turning every pasted link into a beacon.

    Regex rather than a parser because the whole point is to add no dependency to an ingestion path
    that already has `trafilatura` doing the real work. Values are whitespace-collapsed and
    truncated here and rendered with `textContent` in the UI (never `innerHTML` — invariant 29), so
    a malformed match is a cosmetic miss, never a hazard. No ESCAPING happens here, and an earlier
    draft of this docstring claimed it did.

    Every pattern above is bounded and the input is windowed — see `_META_TAG` for the measured
    denial-of-service that made both mandatory.
    """
    # Window FIRST. Everything below is bounded too, but bounding the INPUT is what makes the worst
    # case a constant rather than a function of what someone chose to serve.
    window = html[:_PREVIEW_WINDOW]
    head_end = window.lower().find("</head>")
    if head_end != -1:
        window = window[:head_end]

    found: dict[str, str] = {}
    tags: dict[str, str] = {}
    for match in _META_TAG.finditer(window):
        key = (match.group(1) or match.group(4) or "").strip().lower()
        value = match.group(2) if match.group(1) else match.group(3)
        if key and value and key not in tags:
            tags[key] = " ".join(value.split())

    for field, candidates in _PREVIEW_META.items():
        for candidate in candidates:
            if tags.get(candidate):
                found[field] = tags[candidate][:300]
                break

    if "title" not in found:
        match = _TITLE_TAG.search(window)
        if match:
            title = " ".join(re.sub(r"<[^>]+>", "", match.group(1)).split())
            if title:
                found["title"] = title[:300]
    return found


#: Content types this parser knows how to read as something OTHER than a web page.
#:
#: **A URL is not a synonym for "an HTML page", and treating it as one made the most obvious act on
#: a research inbox impossible.** `trafilatura.extract` ran unconditionally, so an arXiv PDF link
#: came back `FetchError: no extractable text content` — a message that reads like the fetch failed
#: rather than like the format was never tried. The same for an RFC `.txt` and a raw `.rst` on
#: GitHub. Local PDF UPLOAD worked the whole time, which is what made it a routing bug rather than
#: a missing feature.
_PDF_TYPES = frozenset({"application/pdf", "application/x-pdf"})
_PLAIN_TYPES = frozenset({"text/plain", "text/markdown", "text/x-markdown", "text/csv", "text/x-rst"})


def _looks_like_pdf(raw: bytes, content_type: str) -> bool:
    """Type first, magic bytes second. A server that mislabels a PDF as `application/octet-stream`
    is common enough to be worth the five-byte check, and `%PDF-` cannot be mistaken for html."""
    return content_type in _PDF_TYPES or raw[:5] == b"%PDF-"


def parse_web(url: str, source_id: str, *, fetcher=None) -> Source:
    """Ingest a URL: a web page, a PDF, or plain text, decided by what actually came back.

    `fetcher` is an injection seam for tests (a fake returning canned HTML); when it is supplied the
    reply is treated as html, which is the shape every existing caller was written against. The
    default fetches over the real network with the SSRF guard applied first.
    """
    if fetcher is not None:
        return _from_html(fetcher(url), url, source_id)

    raw, content_type = _fetch(url)
    if _looks_like_pdf(raw, content_type):
        # Through a real file, because PDFium wants one — and through `parse_pdf`, so a PDF reached
        # by URL gets the identical page-per-block treatment, the OCR ladder and the `_PDFIUM_LOCK`
        # serialisation (invariant 3) that an uploaded one gets. Imported here rather than at module
        # scope: `parsers/pdf.py` pulls in pypdfium2 and the OCR stack, and a text-only capture
        # should not pay for them.
        import tempfile

        from .pdf import parse_pdf

        with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
            handle.write(raw)
            handle.flush()
            source = parse_pdf(handle.name, source_id)
        # `parse_pdf` names the temp file as the origin; the ORIGIN is the URL the reader pasted,
        # and it is what dedupe and every citation coordinate key off.
        return source.model_copy(update={"origin": url})

    if content_type in _PLAIN_TYPES:
        from .text import parse_text

        return parse_text(raw.decode("utf-8", errors="replace"), source_id, origin=url)

    return _from_html(raw.decode("utf-8", errors="replace"), url, source_id)


def _from_html(html: str, url: str, source_id: str) -> Source:
    text = trafilatura.extract(html, url=url)
    if not text or not text.strip():
        raise FetchError(f"no extractable text content at {url!r}")
    return Source(
        id=source_id,
        kind="web",
        origin=url,
        blocks=[SourceBlock(locator="whole", text=text)],
        # From the SAME html already in hand — one fetch, as invariant 1 requires.
        preview=extract_preview(html),
    )
