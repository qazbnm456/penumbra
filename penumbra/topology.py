"""What the star map and the knowledge graph draw, read straight from the Horizon's index.

Nothing here is stored and nothing here calls a model. Relations come only from what a summary
already wrote: a node's `entities` and `tags`. Two entities are linked when one capture names both,
and two orbits are bridged when captures filed into each name the same entity. A capture that has
not been summarised has no entities, so it appears as an unlinked point and is counted, never
guessed at.

Reads index rows only, never a node's text (invariant 78), and caps what each drawing returns.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from . import concepts, horizon
from .horizon import DEFAULT_HORIZON_DIR
from .search import SEARCHABLE_STATES

#: How much one drawing may carry. Past these a graph stops being readable long before it stops
#: being computable, so the least-used entities and the oldest captures are the ones left out, and
#: the response says how many were.
MAX_ENTITIES = 60
MAX_CAPTURES = 300
MAX_BRIDGES = 12
TOP_PER_ORBIT = 6
#: How many captures the map names one by one: the moons around one planet and the dots around the
#: Horizon. The map draws no more than these, so a name for each drawn dot is all it needs.
MAX_MOONS = 12
MAX_LOOSE = 28


def _names(raw: str | None) -> list[str]:
    try:
        values = json.loads(raw or "[]")
    except ValueError:
        return []
    if not isinstance(values, list):
        return []
    seen: dict[str, None] = {}
    for value in values:
        if isinstance(value, str) and value.strip():
            seen.setdefault(value.strip(), None)
    return list(seen)


def _label(row) -> str:
    if row["title"]:
        return row["title"]
    try:
        preview = json.loads(row["preview"] or "{}")
    except ValueError:
        preview = {}
    title = preview.get("title") if isinstance(preview, dict) else None
    if title:
        return title
    origin = row["origin"] or ""
    # A paste's origin is `pasted:<opening words> #<hash>`: the words are the label, the hash is an
    # internal key that must not reach a tooltip (the list view shows the words the same way).
    if origin.startswith("pasted:"):
        return origin[len("pasted:"):].split(" #")[0].strip() or origin
    return origin


def _newest(stamped: list[tuple[float, dict]], limit: int) -> list[dict]:
    return [item for _, item in sorted(stamped, key=lambda pair: -pair[0])[:limit]]


def _entity(name: str, count: int, alias_table: dict[str, str]) -> dict:
    """An entity as drawn, with the other names a merge folded into it, so the reader can see and
    undo each one."""
    entry: dict = {"name": name, "count": count}
    merged = sorted(alias for alias, canonical in alias_table.items() if canonical == name)
    if merged:
        entry["aliases"] = merged
    return entry


def star_map(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict:
    """Per orbit (keyed by `slug`, the filename token memberships are written with, which
    `/orbits` also reports): how many captures are filed into it, how many of those are unsummarised, when it
    last gained one, and its most-named entities and tags. Plus the captures filed nowhere, and the
    bridges between orbits that share an entity."""
    with horizon._connect(base_dir) as conn:
        rows = conn.execute(
            """SELECT n.id, n.state, n.entities, n.tags, n.created_at, n.title, n.origin, n.preview,
                      m.orbit_id, m.promoted_at
               FROM nodes n LEFT JOIN memberships m ON m.node_id = n.id"""
        ).fetchall()

    # Aliases applied as the rows are read (`concepts.py`): a merge changes what is drawn and
    # nothing that was stored.
    resolve = concepts.resolver(base_dir=base_dir)
    orbits: dict[str, dict] = {}
    entity_sets: dict[str, set[str]] = defaultdict(set)
    loose = {"count": 0, "undistilled": 0, "busy": 0}
    loose_items: list[tuple[float, dict]] = []
    moons: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    # Every orbit each node is in, so a moon carried to another planet knows where it already is.
    filed_in: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["orbit_id"] is not None:
            filed_in[row["id"]].append(row["orbit_id"])
    total = {"count": 0, "distilled": 0}
    counted: set[str] = set()
    for row in rows:
        node_id = row["id"]
        if node_id not in counted:
            counted.add(node_id)
            total["count"] += 1
            if row["state"] == "ready":
                total["distilled"] += 1
        item = {"id": node_id, "title": _label(row), "state": row["state"], "orbits": filed_in[node_id],
                # So a tag lens can light the moon itself, not only the planet it circles.
                "tags": _names(row["tags"])}
        if row["orbit_id"] is None:
            loose_items.append((float(row["created_at"] or 0), item))
            loose["count"] += 1
            if row["state"] == "ready_undistilled":
                loose["undistilled"] += 1
            elif row["state"] in ("queued", "parsing", "distilling"):
                loose["busy"] += 1
            continue
        entry = orbits.setdefault(row["orbit_id"], {
            "slug": row["orbit_id"], "captures": 0, "undistilled": 0, "last_filed_at": 0.0,
            "_entities": Counter(), "_tags": Counter(),
        })
        entry["captures"] += 1
        moons[row["orbit_id"]].append((float(row["promoted_at"] or 0), item))
        if row["state"] == "ready_undistilled":
            entry["undistilled"] += 1
        entry["last_filed_at"] = max(entry["last_filed_at"], float(row["promoted_at"] or 0))
        entities = list(dict.fromkeys(resolve(e) for e in _names(row["entities"])))
        entry["_entities"].update(entities)
        entry["_tags"].update(_names(row["tags"]))
        entity_sets[row["orbit_id"]].update(entities)

    out_orbits = []
    for entry in orbits.values():
        out_orbits.append({
            "slug": entry["slug"],
            "captures": entry["captures"],
            "undistilled": entry["undistilled"],
            "last_filed_at": entry["last_filed_at"],
            "entities": [name for name, _ in entry["_entities"].most_common(TOP_PER_ORBIT)],
            "tags": [name for name, _ in entry["_tags"].most_common(TOP_PER_ORBIT)],
            # Every tag any of its captures carries, for the map's lens. `tags` is the top few, for
            # display, and a lens matched against it left a planet dark whenever the tag was one of
            # many named once (an orbit of two captures easily carries twelve).
            "all_tags": sorted(entry["_tags"]),
            "moons": _newest(moons[entry["slug"]], MAX_MOONS),
        })
    out_orbits.sort(key=lambda o: -o["last_filed_at"])

    bridges = []
    for a, b in combinations(sorted(entity_sets), 2):
        shared = entity_sets[a] & entity_sets[b]
        if shared:
            bridges.append({"a": a, "b": b, "shared": sorted(shared)[:5], "weight": len(shared)})
    bridges.sort(key=lambda br: (-br["weight"], br["a"], br["b"]))
    loose["items"] = _newest(loose_items, MAX_LOOSE)
    return {
        "orbits": out_orbits, "loose": loose, "total": total, "bridges": bridges[:MAX_BRIDGES],
        "omitted": {"bridges": max(0, len(bridges) - MAX_BRIDGES)},
    }


def graph(
    orbit_id: str | None = None, *, similar=None, base_dir: str | Path = DEFAULT_HORIZON_DIR
) -> dict:
    """The entity graph over one orbit's captures, or over every readable capture when `orbit_id`
    is `None`.

    `entities` are the nodes, sized by how many captures name them; `edges` join two entities named
    by the same capture, weighted by how many do; `captures` carry which entities and tags they
    name, so the client can draw them as points and light up a lens; `tags` are the lenses.
    `undistilled` are the captures with no summary yet, which therefore name nothing.
    """
    placeholders = ", ".join("?" for _ in SEARCHABLE_STATES)
    sql = (f"SELECT n.id, n.title, n.origin, n.preview, n.state, n.entities, n.tags, n.created_at "
           f"FROM nodes n WHERE n.state IN ({placeholders})")
    params: list[object] = list(SEARCHABLE_STATES)
    if orbit_id is not None:
        sql += " AND EXISTS (SELECT 1 FROM memberships m WHERE m.node_id = n.id AND m.orbit_id = ?)"
        params.append(orbit_id)
    sql += " ORDER BY n.created_at DESC, n.id ASC"
    with horizon._connect(base_dir) as conn:
        rows = conn.execute(sql, params).fetchall()

    resolve = concepts.resolver(base_dir=base_dir)
    alias_table = concepts.aliases(base_dir=base_dir)
    entity_count: Counter[str] = Counter()
    tag_count: Counter[str] = Counter()
    parsed = []
    undistilled = []
    for row in rows:
        entities = list(dict.fromkeys(resolve(e) for e in _names(row["entities"])))
        tags = _names(row["tags"])
        if row["state"] == "ready_undistilled" and not entities and not tags:
            undistilled.append({"node_id": row["id"], "title": _label(row)})
            continue
        entity_count.update(entities)
        tag_count.update(tags)
        parsed.append((row, entities, tags))

    kept = {name for name, _ in entity_count.most_common(MAX_ENTITIES)}
    pairs: Counter[tuple[str, str]] = Counter()
    captures = []
    for row, entities, tags in parsed:
        named = [e for e in entities if e in kept]
        for a, b in combinations(sorted(named), 2):
            pairs[(a, b)] += 1
        if len(captures) < MAX_CAPTURES:
            captures.append({
                "node_id": row["id"], "title": _label(row), "origin": row["origin"],
                "state": row["state"], "entities": named, "tags": tags,
            })
    # Local relations, when they are on (`vectors.py`): pairs of captures whose text is alike. An
    # unsummarised capture that has one is drawn too, linked by that alone, which is the one way it
    # can join the picture before anyone pays for its summary.
    alike: list[dict] = []
    if similar is not None:
        drawn = {c["node_id"] for c in captures}
        waiting = {u["node_id"]: u for u in undistilled}
        alike = similar(list(drawn | waiting.keys()))
        linked = {n for p in alike for n in (p["a"], p["b"])}
        by_id = {row["id"]: row for row in rows}
        for node_id in linked & waiting.keys():
            if len(captures) >= MAX_CAPTURES:
                break
            row = by_id[node_id]
            captures.append({"node_id": node_id, "title": _label(row), "origin": row["origin"],
                             "state": row["state"], "entities": [], "tags": []})
        shown = {c["node_id"] for c in captures}
        alike = [p for p in alike if p["a"] in shown and p["b"] in shown]
    return {
        "similar": alike,
        "entities": [_entity(name, entity_count[name], alias_table)
                     for name in sorted(kept, key=lambda n: (-entity_count[n], n))],
        "edges": [{"a": a, "b": b, "weight": w} for (a, b), w in sorted(pairs.items())],
        "tags": [{"name": name, "count": n} for name, n in tag_count.most_common()],
        "captures": captures,
        "undistilled": undistilled,
        "omitted": {
            "entities": max(0, len(entity_count) - len(kept)),
            "captures": max(0, len(parsed) - len(captures)),
        },
    }


def bridge(a: str, b: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict:
    """What two orbits share, and where each says it: for every entity the captures filed into both
    orbits name, the captures on each side that name it. Aliases apply, as everywhere a reader sees
    an entity (`concepts.py`). Derived from summaries only, never a model call."""
    resolve = concepts.resolver(base_dir=base_dir)
    with horizon._connect(base_dir) as conn:
        rows = conn.execute(
            """SELECT n.id, n.title, n.origin, n.preview, n.entities, m.orbit_id
               FROM nodes n JOIN memberships m ON m.node_id = n.id
               WHERE m.orbit_id IN (?, ?)""",
            (a, b),
        ).fetchall()
    sides: dict[str, dict[str, list[dict]]] = {a: defaultdict(list), b: defaultdict(list)}
    for row in rows:
        names = dict.fromkeys(resolve(e) for e in _names(row["entities"]))
        for name in names:
            sides[row["orbit_id"]][name].append({"id": row["id"], "title": _label(row)})
    shared = sorted(set(sides[a]) & set(sides[b]), key=lambda n: (-(len(sides[a][n]) + len(sides[b][n])), n))
    return {
        "a": a, "b": b,
        "shared": [{"name": n, "a": sides[a][n], "b": sides[b][n]} for n in shared],
    }
