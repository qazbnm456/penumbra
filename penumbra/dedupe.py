"""Knowing a capture is already in the Horizon, beyond an identical address or identical text.

The Horizon already dedupes an identical URL (a queued capture's id is its address) and identical
text (every other capture's id folds its text in). That misses the two duplicates people make most:

- **The same address with tracking attached.** `?utm_source=...`, `fbclid`, a share link's `?s=20`
  and `twitter.com` against `x.com` name one page. `normalize_url` drops what only tracks.
- **The same page captured twice as it changed a little.** A social post re-rendered with a new
  relative time or a new count is a different text by one character, so a second press made a
  second capture. `find_duplicate` compares text by overlapping character 5-grams (Jaccard), which
  works across scripts without word boundaries, among the captures of the same page or the same
  title only, so it never compares against the whole Horizon.

It is deliberately NOT semantic similarity: two articles on one subject are two sources, and the
local relations model (`vectors.py`) already says how close they are without merging anything.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path

from . import horizon
from .horizon import DEFAULT_HORIZON_DIR
from .schema import Source

#: Query parameters that only track where a click came from. Dropped, never the ones that choose
#: the content (`?v=` on YouTube, `?id=`, a search's `?q=`).
_TRACKING = frozenset({
    "fbclid", "gclid", "dclid", "msclkid", "yclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src",
    "ref_url", "spm", "si", "_hsenc", "_hsmi", "mkt_tok",
})
#: Per host: parameters that are only tracking there (X's share links add `s` and `t`).
_TRACKING_ON = {"x.com": frozenset({"s", "t"})}
#: Hosts that are one site.
_SAME_SITE = {"twitter.com": "x.com", "mobile.twitter.com": "x.com", "m.youtube.com": "www.youtube.com",
              "youtu.be": "youtu.be"}

#: Two texts this close are one capture: a page re-rendered with a changed count or time, not a
#: different document.
NEAR_DUPLICATE = 0.85
_SHINGLE = 5
_COMPARE_CHARS = 20_000


def normalize_url(url: str) -> str:
    """`url` without what only tracks: `utm_*` and known click ids, `www.`, a default port, a
    trailing slash and the fragment (a text fragment is kept, since it names a passage). Hosts
    that are one site become one name. An address that does not parse comes back as it was."""
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return url
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return url
    host = parts.hostname.lower()
    host = _SAME_SITE.get(host, host)
    if host.startswith("www.") and host != "www.youtube.com":
        host = host[4:]
    port = parts.port
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    extra = _TRACKING_ON.get(host, frozenset())
    query = [
        (k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING and k not in extra
    ]
    path = parts.path.rstrip("/") or "/"
    fragment = parts.fragment if parts.fragment.startswith(":~:text=") else ""
    return urllib.parse.urlunsplit(("https", netloc, path, urllib.parse.urlencode(query), fragment))


def _page(url: str) -> str:
    """The page a capture came from, without the passage its text fragment names."""
    return normalize_url(url).split("#", 1)[0]


#: What changes when a page is shown again: counts and times. Digits and Chinese numerals are left
#: out of the comparison, so "3 minutes ago, 120 likes" and "5 minutes ago, 121 likes" match.
_VOLATILE = re.compile(r"[0-9〇零一二三四五六七八九十百千萬万兩两]+")


def _shingles(text: str) -> set[str]:
    flat = _VOLATILE.sub("", "".join(text[:_COMPARE_CHARS].split()).lower())
    if len(flat) <= _SHINGLE:
        return {flat} if flat else set()
    return {flat[i:i + _SHINGLE] for i in range(len(flat) - _SHINGLE + 1)}


def resemblance(a: str, b: str) -> float:
    """Jaccard overlap of the two texts' character 5-grams, whitespace ignored: 1.0 is the same
    text, and a page re-rendered with a changed number stays well above `NEAR_DUPLICATE`."""
    left, right = _shingles(a), _shingles(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def find_duplicate(source: Source, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> horizon.Node | None:
    """An existing capture that is this one again: the same page (or, for a passage, the same page
    and passage) or the same title, with text at least `NEAR_DUPLICATE` alike. None when there is
    none, which is the common case and costs one indexed read of origins and titles."""
    text = "\n".join(block.text for block in source.blocks)
    page = _page(source.origin)
    passage = normalize_url(source.origin) if "#:~:text=" in source.origin else ""
    title = " ".join((source.preview.get("title") or "").split())
    with horizon._connect(base_dir) as conn:
        rows = conn.execute(
            "SELECT id, origin, preview FROM nodes WHERE state IN ('ready', 'ready_undistilled')"
        ).fetchall()
    candidates = []
    for row in rows:
        origin = row["origin"] or ""
        try:
            their_title = " ".join((json.loads(row["preview"] or "{}").get("title") or "").split())
        except ValueError:
            their_title = ""
        same_page = _page(origin) == page and (not passage or normalize_url(origin) == passage)
        same_title = len(title) >= 8 and their_title == title
        if same_page or same_title:
            candidates.append(row["id"])
    for node_id in candidates:
        try:
            theirs = "\n".join(block.text for block in horizon.node_source(node_id, base_dir=base_dir).blocks)
        except (OSError, ValueError):
            continue
        if resemblance(text, theirs) >= NEAR_DUPLICATE:
            return horizon.get_node(node_id, base_dir=base_dir)
    return None
