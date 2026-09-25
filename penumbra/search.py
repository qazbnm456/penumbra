"""Full-text search over the Horizon, and the selection a Horizon ask reads.

The index lives in the Horizon's own `index.db` as an FTS5 table, so there is no second store to
keep in step and nothing to run beside the server. It is DERIVED: every row can be rebuilt from the
node row and its blocks file, `sync` does exactly that for whatever is missing or older than its
node, and deleting the tables loses nothing but time.

**Chinese is indexed as overlapping character pairs, never through a dictionary.** FTS5's
`unicode61` tokenizer treats a whole run of Han characters as one token, and its `trigram` tokenizer
cannot match a two-character word, which is most of Chinese vocabulary. A segmenter was measured and
refused: jieba's default dictionary cut 關係 in half on Traditional text, and every dictionary
variant cut 海馬迴 into 海馬 / 迴在, so a search for the one term that mattered found nothing. Pairs
need no dictionary, have no Traditional/Simplified bias and never lose a term to a wrong cut; they
are the standard CJK analyzer in Lucene for the same reasons. The pairs are computed here, in
Python, because Python's `sqlite3` cannot register an FTS5 tokenizer.

**Contentless, because the text is already on disk.** Storing the paired text would double every
node's size in the database. `content=''` keeps only the index, and `contentless_delete=1` (SQLite
3.43) still lets a node's row be replaced or removed.

Nothing here assembles a corpus. `select_for_ask` returns node ids and sizes; the caller builds the
bounded corpus from them (invariant 78).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import get_args

from . import concepts as aliases_store
from . import horizon
from .horizon import DEFAULT_HORIZON_DIR
from .schema import NodeState

_log = logging.getLogger(__name__)

#: Scripts written without spaces between words: kana, CJK ideographs (with extension A and the
#: compatibility block) and Hangul syllables. A run of these becomes character pairs.
_UNSPACED = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]+")

#: A node's text beyond this is not indexed. A whole book is a few million characters, and the
#: part a search needs to find it by is never its last half; the cap keeps one capture from
#: dominating the index's size.
_BODY_CAP = 1_000_000

#: The node states whose blocks are on disk. `queued`, `parsing` and `failed` have nothing to read.
#: Derived from `schema.NodeState` minus those three, so a renamed or added state cannot silently
#: drop out of search: a summarised node is `ready`, and a hand-written list once said `distilled`.
SEARCHABLE_STATES = tuple(s for s in get_args(NodeState) if s not in ("queued", "parsing", "failed"))

#: Weight of the distilled description against the body in `bm25`. A match in a title or a tag says
#: more about what a capture is about than one somewhere in its text.
_META_WEIGHT = 3.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_rows (
    rowid      INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id    TEXT NOT NULL UNIQUE REFERENCES nodes(id) ON DELETE CASCADE,
    indexed_at REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
    meta, body, content='', contentless_delete=1, tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS search_rows_forget AFTER DELETE ON search_rows BEGIN
    DELETE FROM search_fts WHERE rowid = old.rowid;
END;
"""
# `AUTOINCREMENT` is load-bearing: without it SQLite may hand a new node the rowid of a deleted one,
# and if that deletion's index row were ever left behind the new node would inherit its words.

_READY: set[str] = set()
_READY_LOCK = threading.Lock()


class SearchUnavailable(RuntimeError):
    """This SQLite build cannot hold the index (FTS5 missing, or older than 3.43)."""


def grams(text: str) -> str:
    """`text` with every unspaced run replaced by its overlapping character pairs.

    `睡眠與記憶` becomes `睡眠 眠與 與記 記憶`; a lone character stays itself; Latin text passes
    through for `unicode61` to split and fold. NFKC first, so a full-width `ＰＤＦ` and `PDF` are
    one word.
    """
    text = unicodedata.normalize("NFKC", text or "")

    def pairs(match: re.Match[str]) -> str:
        run = match.group(0)
        if len(run) == 1:
            return f" {run} "
        return " " + " ".join(run[i : i + 2] for i in range(len(run) - 1)) + " "

    return _UNSPACED.sub(pairs, text)


def query_terms(text: str, limit: int = 64) -> list[str]:
    """The distinct terms a question searches for, in order. Latin words of one letter are dropped;
    they match nearly everything and say nothing."""
    seen: dict[str, None] = {}
    for term in re.findall(r"\w+", grams(text).lower()):
        if len(term) == 1 and not _UNSPACED.match(term):
            continue
        seen.setdefault(term, None)
        if len(seen) >= limit:
            break
    return list(seen)


def match_expression(terms: list[str]) -> str:
    """An FTS5 query that matches ANY of `terms`, each quoted so no term is read as syntax.

    OR rather than AND: a question in natural language carries words no document contains
    (`什麼`, `why`), and requiring all of them would find nothing. `bm25` already ranks a document
    that matches more of the rarer terms higher.
    """
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)


def _ensure(conn) -> None:
    key = str(conn.execute("PRAGMA database_list").fetchone()[2])
    with _READY_LOCK:
        if key in _READY and Path(key).exists():
            return
        try:
            conn.executescript(_SCHEMA)
        except Exception as exc:  # sqlite3.OperationalError, spelled broadly: the message is the point
            raise SearchUnavailable(
                f"this SQLite build cannot create the search index ({exc}); it needs FTS5 and "
                "SQLite 3.43 or newer"
            ) from exc
        _READY.add(key)


def _node_text(node_id: str, base_dir: str | Path) -> str:
    """The node's block text, capped. An unreadable blocks file indexes as empty rather than
    failing the whole sync: the description is still searchable, and the listing already marks
    the node as unreadable when it is opened."""
    try:
        path = horizon.node_blocks_path(node_id, base_dir=base_dir)
        blocks = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _log.warning("search: cannot read the text of %s (%s)", node_id, exc)
        return ""
    parts: list[str] = []
    size = 0
    for block in blocks if isinstance(blocks, list) else []:
        text = block.get("text", "") if isinstance(block, dict) else ""
        parts.append(text)
        size += len(text)
        if size >= _BODY_CAP:
            break
    return "\n".join(parts)[:_BODY_CAP]


def _meta_text(row) -> str:
    fields = [row["title"] or "", row["summary"] or "", row["origin"] or ""]
    for column in ("tags", "entities"):
        try:
            values = json.loads(row[column] or "[]")
        except ValueError:
            values = []
        fields.extend(str(v) for v in values if isinstance(v, str))
    return "\n".join(fields)


def sync(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> int:
    """Index every searchable node that has no row yet or changed since its row was written.
    Returns how many were (re)indexed.

    The row records the node's `updated_at` as it was READ, not the time of writing, so an edit
    that lands while this runs leaves the row older than the node and the next sync picks it up.
    """
    placeholders = ", ".join("?" for _ in SEARCHABLE_STATES)
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        rows = conn.execute(
            f"""SELECT n.id, n.title, n.summary, n.origin, n.tags, n.entities, n.updated_at
                FROM nodes n LEFT JOIN search_rows s ON s.node_id = n.id
                WHERE n.state IN ({placeholders})
                  AND (s.node_id IS NULL OR n.updated_at > s.indexed_at)""",
            SEARCHABLE_STATES,
        ).fetchall()
    done = 0
    for row in rows:
        meta = grams(_meta_text(row))
        body = grams(_node_text(row["id"], base_dir))
        with horizon._connect(base_dir) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if conn.execute("SELECT 1 FROM nodes WHERE id = ?", (row["id"],)).fetchone() is None:
                    conn.execute("ROLLBACK")
                    continue  # removed while its text was being read
                rowid = conn.execute(
                    """INSERT INTO search_rows (node_id, indexed_at) VALUES (?, ?)
                       ON CONFLICT(node_id) DO UPDATE SET indexed_at = excluded.indexed_at
                       RETURNING rowid""",
                    (row["id"], row["updated_at"]),
                ).fetchone()[0]
                conn.execute("DELETE FROM search_fts WHERE rowid = ?", (rowid,))
                conn.execute(
                    "INSERT INTO search_fts (rowid, meta, body) VALUES (?, ?, ?)", (rowid, meta, body)
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        done += 1
    return done


def search(query: str, *, limit: int = 200, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> list[str]:
    """Node ids matching `query`, best first. Syncs the index first, so a capture that landed a
    moment ago is findable."""
    terms = query_terms(query)
    if not terms:
        return []
    sync(base_dir=base_dir)
    placeholders = ", ".join("?" for _ in SEARCHABLE_STATES)
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        rows = conn.execute(
            f"""SELECT s.node_id FROM search_fts
                JOIN search_rows s ON s.rowid = search_fts.rowid
                JOIN nodes n ON n.id = s.node_id
                WHERE search_fts MATCH ? AND n.state IN ({placeholders})
                ORDER BY bm25(search_fts, ?, 1.0) LIMIT ?""",
            (match_expression(terms), *SEARCHABLE_STATES, _META_WEIGHT, limit),
        ).fetchall()
    return [row[0] for row in rows]


# --- the selection a Horizon ask reads ------------------------------------------------------------

#: What a scope may be. `orbit` is absent on purpose: a question about one orbit is asked in that
#: orbit, where the answer joins its conversation.
SCOPE_KINDS = ("all", "tag", "entity")

#: The longest tag or entity a scope may name. `concepts` offers nothing longer, so the picker never
#: shows a choice the API would refuse.
SCOPE_VALUE_MAX = 200


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
        names = aliases_store.names_for(value, base_dir=base_dir) if kind == "entity" else [value]
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
    sql = (f"SELECT id, title, origin, chars, preview FROM nodes WHERE {clause} "
           "ORDER BY created_at DESC, id ASC")
    with horizon._connect(base_dir) as conn:
        return conn.execute(sql, params).fetchall()


def _ranked_in_scope(
    question: str, kind: str, value: str | None, base_dir: str | Path, orbit: str | None = None
) -> list[str]:
    """Node ids in the scope that match `question`, best first.

    The scope is part of the FTS query, not a filter applied to the top hits afterwards: with a
    global `LIMIT`, five hundred better matches outside a tag left nothing inside it, and the ask
    fell back to the newest captures while telling the reader their words had found nothing.
    """
    terms = query_terms(question)
    if not terms:
        return []
    sync(base_dir=base_dir)
    clause, params = _scope_clause(kind, value, orbit, base_dir)
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        rows = conn.execute(
            f"""SELECT s.node_id FROM search_fts
                JOIN search_rows s ON s.rowid = search_fts.rowid
                JOIN nodes ON nodes.id = s.node_id
                WHERE search_fts MATCH ? AND {clause}
                ORDER BY bm25(search_fts, ?, 1.0)""",
            (match_expression(terms), *params, _META_WEIGHT),
        ).fetchall()
    return [row[0] for row in rows]


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
    ranked = [
        node_id for node_id in _ranked_in_scope(question, kind, value, base_dir, orbit) if node_id in by_id
    ]
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
    with horizon._connect(base_dir) as conn:
        for key, column in (("tags", "tags"), ("entities", "entities")):
            rows = conn.execute(
                f"""SELECT json_each.value AS name, COUNT(*) AS n
                    FROM (SELECT {column} AS list FROM nodes
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
