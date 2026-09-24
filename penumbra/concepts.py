"""Concept alignment's memory: which entity names are the same thing, kept as aliases.

Summaries are written one capture at a time, so the same entity arrives under several names
(`Matthew Walker`, `馬修·沃克`, `M. Walker`). `align.AlignConcepts` decides which are the same, and
the answer is kept HERE as an alias table rather than written back into any node. Stored summaries
are never rewritten, so a merge is undone by deleting its row, and every reader (the star map, the
graph, a scoped ask) applies the table when it reads.

`entity_seen` records which names alignment has already considered, so a pass only ever asks about
names it has not seen, and a Horizon that grows by ten captures pays to align ten captures' names.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import horizon
from .horizon import DEFAULT_HORIZON_DIR

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_aliases (
    alias      TEXT PRIMARY KEY,
    canonical  TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS entity_seen (
    name TEXT PRIMARY KEY
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


def aliases(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict[str, str]:
    """alias -> canonical."""
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        return {row[0]: row[1] for row in conn.execute("SELECT alias, canonical FROM entity_aliases")}


def resolver(*, base_dir: str | Path = DEFAULT_HORIZON_DIR):
    """A function mapping a name to its canonical form, for a reader applying the table."""
    table = aliases(base_dir=base_dir)
    return lambda name: table.get(name, name)


def names_for(canonical: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> list[str]:
    """`canonical` and every alias of it: what a scope on that entity has to match."""
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        rows = conn.execute(
            "SELECT alias FROM entity_aliases WHERE canonical = ? ORDER BY alias", (canonical,)
        ).fetchall()
    return [canonical, *[row[0] for row in rows]]


def all_names(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict[str, int]:
    """Every entity name summaries have written, with how many captures name it."""
    placeholders = ", ".join("?" for _ in horizon_readable_states())
    with horizon._connect(base_dir) as conn:
        rows = conn.execute(
            f"""SELECT json_each.value AS name, COUNT(*) AS n
                FROM (SELECT entities FROM nodes WHERE state IN ({placeholders})
                      AND CASE WHEN json_valid(entities) THEN json_type(entities) = 'array' ELSE 0 END)
                     AS readable, json_each(readable.entities)
                WHERE json_each.type = 'text'
                GROUP BY json_each.value""",
            horizon_readable_states(),
        ).fetchall()
    return {row["name"]: int(row["n"]) for row in rows}


def horizon_readable_states() -> tuple[str, ...]:
    from .search import SEARCHABLE_STATES

    return SEARCHABLE_STATES


def unseen(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> list[str]:
    """Names no alignment has considered yet, most named first."""
    counts = all_names(base_dir=base_dir)
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        seen = {row[0] for row in conn.execute("SELECT name FROM entity_seen")}
    return sorted((n for n in counts if n not in seen), key=lambda n: (-counts[n], n))


def mark_seen(names: list[str], *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> None:
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        conn.executemany("INSERT OR IGNORE INTO entity_seen (name) VALUES (?)", [(n,) for n in names])


def apply_merges(
    merges: list[tuple[str, str]],
    allowed: set[str],
    *,
    batch: set[str] | None = None,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> list[tuple[str, str]]:
    """Record `alias -> canonical` pairs the host accepts, and return them.

    Accepted only when both names are real entity names (`allowed`), they differ, the alias is one
    of the names this run was asked about (`batch`), and it is not already the canonical form of
    something else; a canonical that is itself an alias is followed to its own canonical, so the
    table never holds a chain.
    """
    table = aliases(base_dir=base_dir)
    canonicals = set(table.values())
    accepted: list[tuple[str, str]] = []
    for alias, canonical in merges:
        alias, canonical = alias.strip(), canonical.strip()
        canonical = table.get(canonical, canonical)
        if alias == canonical or alias not in allowed or canonical not in allowed:
            continue
        # Only a name this run was ASKED about can become an alias: a name seen before (and perhaps
        # separated by the reader since) is never merged by a later run's say-so.
        if batch is not None and alias not in batch:
            continue
        if alias in canonicals or alias in table:
            continue
        table[alias] = canonical
        # Updated as the batch is applied, so a later pair in the same batch cannot turn this
        # canonical into an alias and leave a chain behind.
        canonicals.add(canonical)
        accepted.append((alias, canonical))
    if accepted:
        now = time.time()
        with horizon._connect(base_dir) as conn:
            _ensure(conn)
            conn.executemany(
                "INSERT OR IGNORE INTO entity_aliases (alias, canonical, created_at) VALUES (?, ?, ?)",
                [(a, c, now) for a, c in accepted],
            )
    return accepted


def remove_alias(alias: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> bool:
    """Undo one merge. The name stays seen, so alignment does not simply merge it again."""
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        return bool(conn.execute("DELETE FROM entity_aliases WHERE alias = ?", (alias,)).rowcount)


def known_listing(counts: dict[str, int], exclude: set[str]) -> str:
    """The names alignment compares against, one per line with their counts."""
    rows = sorted(((n, c) for n, c in counts.items() if n not in exclude), key=lambda r: (-r[1], r[0]))
    return "\n".join(f"{name} ({count})" for name, count in rows)


def json_list(names: list[str]) -> str:
    return json.dumps(names, ensure_ascii=False)
