"""Filing suggestions: which orbit a capture probably belongs in, computed locally.

A capture that sits in no orbit, or only in the landing orbit everything is filed into by default,
is compared with each other orbit by what their summaries named: the entities (after alignment's
aliases) and the tags its captures share. The best match past a threshold is offered; nothing is
filed until the reader accepts, and a declined pair is not offered again. No model call is made, so
suggesting is free and happens whenever it is asked for.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from pathlib import Path

from . import concepts, horizon
from .horizon import DEFAULT_HORIZON_DIR

#: A shared entity counts for more than a shared tag: entities are specific, tags are broad.
_ENTITY_WEIGHT = 2
_TAG_WEIGHT = 1
#: The weakest match offered: two shared entities, or one entity and one tag.
_THRESHOLD = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS filing_dismissed (
    node_id      TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    orbit_id     TEXT NOT NULL,
    dismissed_at REAL NOT NULL,
    PRIMARY KEY (node_id, orbit_id)
);
"""

_READY: set[str] = set()
_READY_LOCK = threading.Lock()


def _ensure(conn) -> None:
    key = str(conn.execute("PRAGMA database_list").fetchone()[2])
    with _READY_LOCK:
        if key in _READY and Path(key).exists():
            return
        conn.executescript(_SCHEMA)
        _READY.add(key)


def _names(raw: str | None) -> list[str]:
    try:
        values = json.loads(raw or "[]")
    except ValueError:
        return []
    return [v.strip() for v in values if isinstance(v, str) and v.strip()] if isinstance(values, list) else []


#: How many unsummarised captures one call compares by similarity, newest first. Each costs at most
#: five vector searches (`vectors.mutual_matches`).
_SIMILAR_CANDIDATES = 30


def suggestions(
    landing: str | None = None,
    *,
    limit: int = 50,
    similar=None,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> list[dict]:
    """Best orbit per capture worth filing, strongest first.

    `landing` is the landing orbit's slug: membership in it alone still counts as unfiled, since
    everything lands there by default, and it is never itself suggested.
    """
    resolve = concepts.resolver(base_dir=base_dir)
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        rows = conn.execute(
            "SELECT id, title, origin, preview, state, entities, tags FROM nodes WHERE state = 'ready'"
        ).fetchall()
        members = conn.execute("SELECT node_id, orbit_id FROM memberships").fetchall()
        dismissed = {(r[0], r[1]) for r in conn.execute("SELECT node_id, orbit_id FROM filing_dismissed")}

    orbits_of: dict[str, set[str]] = defaultdict(set)
    for node_id, orbit_id in members:
        orbits_of[node_id].add(orbit_id)
    node_entities = {r["id"]: {resolve(e) for e in _names(r["entities"])} for r in rows}
    node_tags = {r["id"]: set(_names(r["tags"])) for r in rows}

    orbit_entities: dict[str, set[str]] = defaultdict(set)
    orbit_tags: dict[str, set[str]] = defaultdict(set)
    for node_id, orbit_id in members:
        if orbit_id == landing:
            continue
        orbit_entities[orbit_id] |= node_entities.get(node_id, set())
        orbit_tags[orbit_id] |= node_tags.get(node_id, set())

    out: list[dict] = []
    for row in rows:
        node_id = row["id"]
        filed = orbits_of.get(node_id, set()) - ({landing} if landing else set())
        if filed:
            continue
        best = None
        for orbit_id in orbit_entities.keys() | orbit_tags.keys():
            if (node_id, orbit_id) in dismissed:
                continue
            shared = sorted(node_entities[node_id] & orbit_entities[orbit_id])
            tags = sorted(node_tags[node_id] & orbit_tags[orbit_id])
            score = _ENTITY_WEIGHT * len(shared) + _TAG_WEIGHT * len(tags)
            if score >= _THRESHOLD and (best is None or score > best["score"]):
                best = {"orbit": orbit_id, "shared": shared, "tags": tags, "score": score}
        if best:
            try:
                preview = json.loads(row["preview"] or "{}")
            except ValueError:
                preview = {}
            page_title = preview.get("title") if isinstance(preview, dict) else None
            title = row["title"] or page_title or row["origin"]
            out.append({"node_id": node_id, "title": title, **best})
    if similar is not None:
        out.extend(_by_similarity(similar, landing, orbits_of, dismissed, base_dir))
    out.sort(key=lambda s: (-s["score"], s["title"]))
    return out[:limit]


def _by_similarity(similar, landing, orbits_of, dismissed, base_dir) -> list[dict]:
    """Unsummarised captures, offered for the orbit of the filed capture they most resemble, when
    local relations are on. `similar(node_id, filed)` returns that capture's mutual matches among
    the filed ones. The score is placed at the threshold, below any match by shared entities,
    because similarity is the weaker signal (`vectors.py`)."""
    with horizon._connect(base_dir) as conn:
        rows = conn.execute(
            "SELECT id, title, origin, preview FROM nodes WHERE state = 'ready_undistilled' "
            "ORDER BY created_at DESC LIMIT ?",
            (_SIMILAR_CANDIDATES,),
        ).fetchall()
        titles = {r[0]: r[1] or r[2] for r in conn.execute("SELECT id, title, origin FROM nodes")}
    filed = {node for node, orbits in orbits_of.items() if orbits - ({landing} if landing else set())}
    out: list[dict] = []
    for row in rows:
        node_id = row["id"]
        if orbits_of.get(node_id, set()) - ({landing} if landing else set()):
            continue
        # A handful of vector searches for this capture, never one per filed capture: the first
        # version searched once for every filed capture, per candidate, and took 27 seconds at a
        # thousand captures on an endpoint the island polls every four seconds.
        best = None
        for other, score in similar(node_id, filed):
            if other not in filed:
                continue
            for orbit_id in orbits_of.get(other, set()) - ({landing} if landing else set()):
                if (node_id, orbit_id) in dismissed:
                    continue
                if best is None or score > best[2]:
                    best = (orbit_id, other, score)
        if best:
            try:
                preview = json.loads(row["preview"] or "{}")
            except ValueError:
                preview = {}
            page_title = preview.get("title") if isinstance(preview, dict) else None
            out.append({
                "node_id": node_id, "title": row["title"] or page_title or row["origin"],
                "orbit": best[0], "shared": [], "tags": [], "score": _THRESHOLD,
                "like": titles.get(best[1], ""), "similarity": best[2],
            })
    return out


def dismiss(node_id: str, orbit_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> None:
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        conn.execute(
            "INSERT OR IGNORE INTO filing_dismissed (node_id, orbit_id, dismissed_at) VALUES (?, ?, ?)",
            (node_id, orbit_id, time.time()),
        )
