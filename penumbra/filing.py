"""Filing suggestions: which orbit a capture probably belongs in, computed locally.

A capture that sits in no orbit, or only in the landing orbit everything is filed into by default,
is compared with each other orbit by what their summaries named: the entities (after alignment's
aliases) and the tags its captures share, or, for a capture with no summary yet, how alike its text
is to a filed capture's when local relations are on. The best match past a threshold is offered;
nothing is filed until the reader accepts, and a declined pair, or one the reader took apart, is
not offered again. No model call is made, so suggesting is free and happens whenever it is asked for.

The scoring is the kit's `suggest_topics` over each orbit's topic (`topics.py`); this module maps
its answer back to orbits and captures, in the shape the workspace reads.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rlm_harness.memory_organise import suggest_topics

from . import horizon, memory_store, topics
from .horizon import DEFAULT_HORIZON_DIR
from .orbit import DEFAULT_ORBITS_DIR

_log = logging.getLogger(__name__)


def _title(row) -> str:
    try:
        preview = json.loads(row["preview"] or "{}")
    except ValueError:
        preview = {}
    page_title = preview.get("title") if isinstance(preview, dict) else None
    return row["title"] or page_title or row["origin"]


def suggestions(
    landing: str | None = None,
    *,
    limit: int = 50,
    vectors=None,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
    orbits_dir: str | Path = DEFAULT_ORBITS_DIR,
) -> list[dict]:
    """Best orbit per capture worth filing, strongest first.

    `landing` is the landing orbit's slug: membership in it alone still counts as unfiled, since
    everything lands there by default, and it is never itself suggested. `vectors` is the kit's
    vector index when local relations are on, for captures with no summary yet.
    """
    topics.sync(orbits_dir=orbits_dir, base_dir=base_dir)
    orbit_of = topics.orbits_by_topic(base_dir=base_dir)
    landing_topic = topics.topic_of(landing, base_dir=base_dir) if landing else None
    store = memory_store.store(base_dir)
    try:
        found = suggest_topics(store, limit=limit, landing=landing_topic, vectors=vectors)
    except Exception as exc:  # similarity is the weak signal; the labels still suggest
        if vectors is None:
            raise
        _log.warning("filing: similarity unavailable: %s", exc)
        found = suggest_topics(store, limit=limit, landing=landing_topic, vectors=None)
    with horizon._connect_labels(base_dir) as conn:
        rows = {r["id"]: r for r in conn.execute(
            "SELECT id, title, origin, preview FROM labelled WHERE state IN ('ready', 'ready_undistilled')")}
        filed = {r[0] for r in conn.execute(
            "SELECT node_id FROM memberships WHERE orbit_id != ?", (landing or "",))}
    out: list[dict] = []
    for s in found:
        orbit = orbit_of.get(s.topic_id)
        row = rows.get(s.item_id)
        # Only a capture that is readable and filed nowhere else: the orbits are the truth for
        # where a capture is, and the kit's copy may lag a write by one sync.
        if orbit is None or row is None or s.item_id in filed:
            continue
        item = {"node_id": s.item_id, "title": _title(row), "orbit": orbit,
                "shared": list(s.shared_entities), "tags": list(s.shared_tags), "score": s.score}
        if s.similar_to is not None:
            like = rows.get(s.similar_to)
            item.update(like=_title(like) if like is not None else "", similarity=s.similarity)
        out.append(item)
    return out


def dismiss(node_id: str, orbit_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR,
            orbits_dir: str | Path = DEFAULT_ORBITS_DIR) -> None:
    """Never suggest this capture for this orbit again. Either of the capture's ids names it."""
    node_id = horizon.resolve_id(node_id, base_dir=base_dir) or node_id
    topics.dismiss(node_id, orbit_id, base_dir=base_dir, orbits_dir=orbits_dir)
