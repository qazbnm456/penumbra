"""The selection a Horizon ask reads, ranked by the kit's full-text search.

The full-text index is the kit's memory store's (`memory.db`, `rlm_harness.memory`): each capture's
text up to `memory_store.INDEX_CHARS`, its origin and its current labels, with Chinese, Japanese and
Korean text indexed as overlapping character pairs (invariant 78 has the measurement that ruled out
a dictionary segmenter). The store keeps it in step with every write, so nothing here syncs.

Penumbra decides what a scope is (a tag, an entity and its aliases, an orbit, the readable states)
from the Horizon's own rows, and asks the kit only for the order. Nothing here assembles a corpus:
`select_for_ask` returns node ids and sizes, and the caller builds the bounded corpus from them
(invariant 78).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import get_args

from rlm_harness.memory import fold_name

from . import concepts as aliases_store
from . import horizon, memory_store
from .horizon import DEFAULT_HORIZON_DIR
from .prose import polish
from .schema import NodeState

#: The node states a search may return: a capture that is a memory item. `queued`, `parsing` and
#: `failed` may have no text yet, and `stored_unindexed` has text that is not an item yet.
#: Derived from `schema.NodeState` minus those four, so a renamed or added state cannot silently
#: drop out of search: a summarised node is `ready`, and a hand-written list once said `distilled`.
SEARCHABLE_STATES = tuple(
    s for s in get_args(NodeState) if s not in ("queued", "parsing", "stored_unindexed", "failed")
)


# --- the selection a Horizon ask reads ------------------------------------------------------------

#: What a scope may be. `orbit` is absent on purpose: a question about one orbit is asked in that
#: orbit, where the answer joins its conversation.
SCOPE_KINDS = ("all", "tag", "entity")

#: Joins several tags into one tag scope's value: a lens of more than one tag asks over the captures
#: carrying any of them. The unit separator, because a tag is free text and may hold a comma.
TAG_SEPARATOR = "\x1f"

#: The longest tag or entity a scope may name. `concepts` offers nothing longer, so the picker never
#: shows a choice the API would refuse.
SCOPE_VALUE_MAX = 200
#: How many tags one lens, or a question over it, may hold at once. The tag row lets a reader turn on
#: as many as they like, and eight here met a reader with thirteen on with a 422 the page printed as
#: "[object Object]". Each tag is one bound parameter of an indexed `IN`, read locally, so the bound
#: is about a sane request, not cost.
LENS_TAGS_MAX = 50


@dataclass
class Picked:
    node_id: str
    title: str
    origin: str
    chars: int
    matched: bool


@dataclass
class Selection:
    """What an ask over a scope will read, decided without a model.

    `strategy` says how: `all` (the whole scope fits the budget), `matched` (the captures the
    question's words found, best first), or `recent` (the question matched nothing, so the newest
    captures in scope). `too_large` are captures that alone exceed the budget and were left out.
    """

    items: list[Picked] = field(default_factory=list)
    in_scope: int = 0
    chars: int = 0
    strategy: str = "all"
    too_large: list[Picked] = field(default_factory=list)

    @property
    def node_ids(self) -> list[str]:
        return [item.node_id for item in self.items]


#: Room left per capture for its citation markers when estimating a corpus from `chars`. The real
#: blob is measured again before the run; this only keeps the estimate from running under.
_MARKER_SLACK = 64


def _scope_clause(
    kind: str, value: str | None, orbit: str | list[str] | None = None,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> tuple[str, list[object]]:
    """The WHERE fragment (over `nodes`) that keeps a readable node inside the scope. `orbit`
    narrows any scope to the captures filed into that orbit, which is what a tag or an entity means
    on the knowledge graph of one orbit; a list narrows it to captures filed into any of them, which
    is what an entity on the link between two orbits means."""
    if kind not in SCOPE_KINDS:
        raise ValueError(f"unknown scope {kind!r} (expected one of {', '.join(SCOPE_KINDS)})")
    placeholders = ", ".join("?" for _ in SEARCHABLE_STATES)
    sql = f"nodes.state IN ({placeholders})"
    params: list[object] = list(SEARCHABLE_STATES)
    if kind in ("tag", "entity"):
        if not value:
            raise ValueError(f"a {kind} scope needs a value")
        column = "tags" if kind == "tag" else "entities"
        # CASE, not `json_valid(...) AND EXISTS(...)`: SQLite does not promise to short-circuit
        # AND, and `json_each` over a malformed column raises instead of matching nothing.
        # An entity scope matches every name alignment folded into it (`concepts.py`).
        names = (aliases_store.names_for(value, base_dir=base_dir) if kind == "entity"
                 else [fold_name(name) for name in value.split(TAG_SEPARATOR) if name])
        marks = ", ".join("?" for _ in names)
        sql += (f" AND CASE WHEN json_valid(nodes.{column}) THEN EXISTS "
                f"(SELECT 1 FROM json_each(nodes.{column}) WHERE json_each.value IN ({marks})) "
                f"ELSE 0 END")
        params.extend(names)
    if isinstance(orbit, list):
        marks = ", ".join("?" for _ in orbit)
        sql += (" AND EXISTS (SELECT 1 FROM memberships m WHERE m.node_id = nodes.id "
                f"AND m.orbit_id IN ({marks}))")
        params.extend(orbit)
    elif orbit is not None:
        sql += " AND EXISTS (SELECT 1 FROM memberships m WHERE m.node_id = nodes.id AND m.orbit_id = ?)"
        params.append(orbit)
    return sql, params


def _scope_rows(kind: str, value: str | None, base_dir: str | Path, orbit: str | None = None):
    clause, params = _scope_clause(kind, value, orbit, base_dir)
    sql = (f"SELECT id, title, origin, chars, preview FROM labelled nodes WHERE {clause} "
           "ORDER BY created_at DESC, id ASC")
    with horizon._connect_labels(base_dir) as conn:
        return conn.execute(sql, params).fetchall()


def _ranked(question: str, base_dir: str | Path) -> list[str]:
    """Every item id the kit's search matches `question` with, best first.

    No limit, so the caller's scope keeps whatever falls inside it: with a global `LIMIT`, five
    hundred better matches outside a tag once left nothing inside it, and the ask fell back to the
    newest captures while telling the reader their words had found nothing.
    """
    if not question.strip():
        return []   # the kit lists every item, newest first, for an empty query
    return memory_store.store(base_dir).search_ids(question, limit=None)


def _label(row) -> str:
    if row["title"]:
        return row["title"]
    try:
        preview = json.loads(row["preview"] or "{}")
    except ValueError:
        preview = {}
    return (preview.get("title") if isinstance(preview, dict) else None) or row["origin"]


def select_for_ask(
    question: str,
    kind: str = "all",
    value: str | None = None,
    *,
    budget_chars: int,
    max_items: int,
    orbit: str | list[str] | None = None,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> Selection:
    """Pick the captures an ask over a scope reads.

    A scope that fits the budget whole is read whole: asking about a tag with nine captures reads
    all nine, matched ones first. A larger scope reads what the question's words found, best first,
    until the budget or the item cap is reached. Only when the words find nothing in scope does it
    fall back to the newest captures, and `strategy` says so, because that answer rests on recency
    rather than relevance.
    """
    rows = _scope_rows(kind, value, base_dir, orbit)
    by_id = {row["id"]: row for row in rows}
    ranked = [node_id for node_id in _ranked(question, base_dir) if node_id in by_id]
    matched = set(ranked)

    def picked(row) -> Picked:
        return Picked(row["id"], _label(row), row["origin"], int(row["chars"]), row["id"] in matched)

    def cost(row) -> int:
        return int(row["chars"]) + _MARKER_SLACK

    selection = Selection(in_scope=len(rows))
    everything = sum(cost(row) for row in rows)
    if rows and everything <= budget_chars and len(rows) <= max_items:
        order = ranked + [row["id"] for row in rows if row["id"] not in matched]
        selection.strategy = "all"
    elif ranked:
        order = ranked
        selection.strategy = "matched"
    else:
        order = [row["id"] for row in rows]
        selection.strategy = "recent"

    def fill(order: list[str]) -> None:
        used = 0
        for node_id in order:
            row = by_id[node_id]
            if cost(row) > budget_chars:
                if all(p.node_id != node_id for p in selection.too_large):
                    selection.too_large.append(picked(row))
                continue
            if len(selection.items) >= max_items or used + cost(row) > budget_chars:
                continue
            selection.items.append(picked(row))
            used += cost(row)

    fill(order)
    if not selection.items and selection.strategy == "matched":
        # Every match was too large to read. The newest captures that fit are still an answer,
        # and `strategy` and `too_large` say that is what happened.
        selection.strategy = "recent"
        fill([row["id"] for row in rows])
    selection.chars = sum(item.chars for item in selection.items)
    return selection


def concepts(*, limit: int = 60, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict[str, list[dict]]:
    """The tags and entities in use across readable captures, most used first: what a scope can be
    narrowed to. Read from the summaries' own lists, so an unsummarised capture contributes none."""
    placeholders = ", ".join("?" for _ in SEARCHABLE_STATES)
    out: dict[str, list[dict]] = {}
    with horizon._connect_labels(base_dir) as conn:
        for key, column in (("tags", "tags"), ("entities", "entities")):
            rows = conn.execute(
                f"""SELECT json_each.value AS name, COUNT(*) AS n
                    FROM (SELECT {column} AS list FROM labelled
                          WHERE state IN ({placeholders})
                            AND CASE WHEN json_valid({column}) THEN json_type({column}) = 'array'
                                     ELSE 0 END) AS readable,
                         json_each(readable.list)
                    WHERE json_each.type = 'text' AND length(json_each.value) <= ?
                    GROUP BY json_each.value ORDER BY n DESC, name ASC LIMIT ?""",
                (*SEARCHABLE_STATES, SCOPE_VALUE_MAX, limit),
            ).fetchall()
            out[key] = [{"name": row["name"], "count": int(row["n"])} for row in rows]
    # Entities are listed under their canonical names, so a scope picked from here matches every
    # name folded into it.
    resolve = aliases_store.resolver(base_dir=base_dir)
    merged: dict[str, int] = {}
    for row in out.get("entities", []):
        name = resolve(row["name"])
        merged[name] = merged.get(name, 0) + row["count"]
    ranked = sorted(merged.items(), key=lambda r: (-r[1], r[0]))
    out["entities"] = [{"name": n, "count": c} for n, c in ranked]
    return out


def lens(tags: list[str], *, limit: int = 40, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict:
    """The captures carrying any of `tags`, newest first, with what the map's lens card shows for
    each: its title, its summary, which of the tags it carries and the orbits it is in. Read from the
    index alone, no blocks (invariant 78), and bounded by `limit`; `total` is the full count."""
    names = [name for name in dict.fromkeys(tags) if name]
    if not names:
        return {"captures": [], "total": 0}
    marks = ", ".join("?" for _ in names)
    where = (f"CASE WHEN json_valid(nodes.tags) THEN EXISTS (SELECT 1 FROM json_each(nodes.tags) "
             f"WHERE json_each.value IN ({marks})) ELSE 0 END")
    with horizon._connect_labels(base_dir) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM labelled nodes WHERE {where}", names).fetchone()[0]
        rows = conn.execute(
            "SELECT id, former_id, title, origin, preview, summary, tags, state, created_at "
            f"FROM labelled nodes "
            f"WHERE {where} ORDER BY created_at DESC, id ASC LIMIT ?",
            [*names, limit],
        ).fetchall()
        ids = [row["id"] for row in rows]
        filed: dict[str, list[str]] = {node_id: [] for node_id in ids}
        if ids:
            id_marks = ", ".join("?" for _ in ids)
            for m in conn.execute(
                f"SELECT node_id, orbit_id FROM memberships WHERE node_id IN ({id_marks}) "
                "ORDER BY promoted_at", ids,
            ):
                filed[m["node_id"]].append(m["orbit_id"])
    wanted = set(names)
    captures = []
    for row in rows:
        try:
            carried = [t for t in json.loads(row["tags"] or "[]") if isinstance(t, str)]
        except ValueError:
            carried = []
        captures.append({
            "id": row["id"], "former_id": row["former_id"], "title": polish(_label(row)),
            "summary": polish(row["summary"] or ""),
            "matched": [t for t in carried if t in wanted], "tags": carried,
            "state": row["state"], "created_at": row["created_at"], "orbits": filed[row["id"]],
        })
    return {"captures": captures, "total": total}

