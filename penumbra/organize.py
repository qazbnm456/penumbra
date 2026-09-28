"""Putting captures into orbits with a model, when filing is automatic: into the orbit that fits, or
into a new one when none does.

The local suggestions (`filing.py`) file what shares entities and tags with an orbit already there,
for free. What they leave behind is either the start of something new or a match they cannot see
(a paper and a talk on one subject that name it differently). With `filing_mode` set to `auto`, the
end of a summary pass hands those leftovers to one model call that sees their summaries and the
orbits there are, and returns where each should go: an existing orbit, a new orbit it names, or
nowhere yet. The reader chose this by choosing automatic filing; manual and assigned filing never
reach it.

`OrganizeCaptures` is `worker.py`-compatible (one `arun(**kwargs)` coroutine), so it runs in the
isolated subprocess every model call uses (invariant 21). `plan_from` checks what came back: only
captures it was shown, only orbits that exist, a bounded number of new orbits, and a new name that
matches an existing orbit's is that orbit.
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path

from . import concepts, horizon
from .horizon import DEFAULT_HORIZON_DIR

#: The most new orbits one call may open, however many the model proposes: enough for the subjects
#: of a large import (a first run over 40 captures on 7 subjects, capped at 5, merged AI with space
#: exploration), few enough that a confused reply cannot scatter the Horizon into dozens of orbits.
MAX_NEW_ORBITS = 10
#: The most captures one call sees; the rest wait for the next pass.
MAX_CAPTURES = 40
#: The fewest captures a new orbit opens with.
MIN_NEW_ORBIT = 2
_NAME_CHARS = 60
_SUMMARY_CHARS = 400
_HELD_TITLES = 6

_INSTRUCTIONS = """You sort a person's captured reading into orbits: named collections they read and ask \
questions about together.

`captures` is a JSON list of captures not in any orbit yet, each with an id, a title, a summary, tags and \
entities. `orbits` is a JSON list of the orbits that exist, each with an id, a title and what it holds.

For each capture decide one of:
- put it into an existing orbit whose subject it belongs to (use that orbit's id);
- put it into a NEW orbit, when no existing orbit fits and at least one other capture here shares its \
subject. Captures on one new subject share one new orbit. A capture whose subject no other capture shares \
goes into the closest existing orbit if it reasonably fits, and is otherwise left: it gets an orbit once a \
second capture on its subject arrives. A \
new orbit's name is short (2 to 6 words), names the subject broadly enough to hold more captures like \
it, and is written in `language` when one is given, otherwise in the language most captures are written in;
- leave it, only when it is too thin to place at all.

Prefer an existing orbit when it reasonably fits. Never invent a new orbit that duplicates an existing one. \
Open at most `max_new_orbits` new orbits. Never put captures on unrelated subjects into one orbit to stay \
under that number, and never file a capture into an orbit whose subject it does not share: leave it \
instead, and it will be placed in a later round.

Answer `plan_json` with JSON only: {"placements": [{"capture": "<capture id>", "orbit": "<existing orbit id \
or empty>", "new_orbit": "<new orbit name or empty>"}]}."""


class OrganizeCaptures:
    """`arun(captures=<json>, orbits=<json>, language=<str>, max_new_orbits=<int>) -> dict`, the raw
    plan as the model gave it (`{"placements": [...]}`), or `{"placements": []}` on a reply that
    does not parse. What it means is decided by `plan_from`, on the host."""

    async def arun(self, *, captures: str = "[]", orbits: str = "[]", language: str = "",
                   max_new_orbits: int = MAX_NEW_ORBITS) -> dict:
        import dspy

        predictor = dspy.Predict(dspy.Signature(
            "captures: str, orbits: str, language: str, max_new_orbits: int -> plan_json: str", _INSTRUCTIONS
        ))
        result = await predictor.acall(captures=captures, orbits=orbits, language=language or "",
                                       max_new_orbits=max_new_orbits)
        return parse_plan(getattr(result, "plan_json", ""))


def parse_plan(text: str) -> dict:
    """The JSON object in a reply, tolerating a fenced block or text around it."""
    raw = (text or "").strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        plan = json.loads(match.group(0) if match else raw)
    except (ValueError, AttributeError):
        return {"placements": []}
    return plan if isinstance(plan, dict) else {"placements": []}


def _key(name: str) -> str:
    return " ".join(name.lower().split())


def plan_from(
    raw: dict, *, captures: set[str], orbits: dict[str, str], max_new: int = MAX_NEW_ORBITS
) -> list[tuple[str, str, str]]:
    """What a model's plan may actually do: `(capture_id, "orbit", orbit_id)` or
    `(capture_id, "new", name)`, in the order given.

    Only a capture it was shown, and each at most once; only an orbit that exists (`orbits` maps id
    to title); a new name equal to an existing orbit's title files into that orbit; new names are
    cut to a sensible length; a new name only one capture was given is not opened
    (`MIN_NEW_ORBIT`); and past `max_new` distinct new names the rest are dropped rather than
    opened.
    """
    by_title = {_key(title): orbit_id for orbit_id, title in orbits.items() if title}
    seen: set[str] = set()
    new_names: dict[str, str] = {}
    out: list[tuple[str, str, str]] = []
    # A new orbit needs two captures: one alone would be an orbit of one source, and the next pass
    # can open it once a second capture on its subject arrives.
    wanted: dict[str, set[str]] = {}
    for item in raw.get("placements") or []:
        if not isinstance(item, dict) or str(item.get("orbit") or "") in orbits:
            continue
        capture = str(item.get("capture") or "")
        name = _key(" ".join(str(item.get("new_orbit") or "").split())[:_NAME_CHARS])
        if capture in captures and name and name not in by_title:
            wanted.setdefault(name, set()).add(capture)
    for item in raw.get("placements") or []:
        if not isinstance(item, dict):
            continue
        capture = str(item.get("capture") or "")
        if capture not in captures or capture in seen:
            continue
        orbit = str(item.get("orbit") or "")
        name = " ".join(str(item.get("new_orbit") or "").split())[:_NAME_CHARS]
        if orbit in orbits:
            seen.add(capture)
            out.append((capture, "orbit", orbit))
        elif name:
            if _key(name) in by_title:
                seen.add(capture)
                out.append((capture, "orbit", by_title[_key(name)]))
                continue
            key = _key(name)
            if len(wanted.get(key, ())) < MIN_NEW_ORBIT:
                continue
            if key not in new_names:
                if len(new_names) >= max_new:
                    continue
                new_names[key] = name
            seen.add(capture)
            out.append((capture, "new", new_names[key]))
    return out


def _preview_title(raw: str | None) -> str:
    try:
        preview = json.loads(raw or "{}")
    except ValueError:
        return ""
    return str(preview.get("title") or "") if isinstance(preview, dict) else ""


def _names(raw: str | None, limit: int) -> list[str]:
    try:
        values = json.loads(raw or "[]")
    except ValueError:
        return []
    if not isinstance(values, list):
        return []
    return [v.strip() for v in values if isinstance(v, str) and v.strip()][:limit]


def gather(
    landing: str | None = None, *, skip: set[str] | frozenset[str] = frozenset(),
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> tuple[list[dict], dict[str, list[str]]]:
    """The summarised captures in no orbit (membership in `landing` alone still counts as none),
    newest first and at most `MAX_CAPTURES`, less `skip`; and, per orbit, the titles of what it
    holds. Only summarised captures: a model placing a capture by its address alone would guess."""
    resolve = concepts.resolver(base_dir=base_dir)
    with horizon._connect(base_dir) as conn:
        rows = conn.execute(
            "SELECT id, title, origin, preview, summary, entities, tags FROM nodes WHERE state = 'ready' "
            "ORDER BY created_at DESC"
        ).fetchall()
        members = conn.execute("SELECT node_id, orbit_id FROM memberships").fetchall()
    title_of = {r["id"]: r["title"] or _preview_title(r["preview"]) or r["origin"] for r in rows}
    filed: set[str] = set()
    held: dict[str, list[str]] = defaultdict(list)
    for node_id, orbit_id in members:
        if orbit_id == landing:
            continue
        filed.add(node_id)
        if node_id in title_of:
            held[orbit_id].append(title_of[node_id])
    captures = [
        {
            "id": r["id"],
            "title": title_of[r["id"]],
            "summary": " ".join((r["summary"] or "").split())[:_SUMMARY_CHARS],
            "tags": _names(r["tags"], 8),
            "entities": sorted({resolve(e) for e in _names(r["entities"], 12)}),
        }
        for r in rows
        if r["id"] not in filed and r["id"] not in skip
    ]
    return captures[:MAX_CAPTURES], dict(held)


_LEFT_SCHEMA = """
CREATE TABLE IF NOT EXISTS organize_left (
    node_id TEXT PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    orbits  TEXT NOT NULL,
    left_at REAL NOT NULL
);
"""


def orbit_signature(orbits: dict[str, str]) -> str:
    """The set of orbits a decision was made against. A capture left against one set is looked at
    again once the set changes, since a new orbit may now take it."""
    return "\u001f".join(sorted(orbits))


def left_ids(signature: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> set[str]:
    """The captures organising left against this set of orbits. Kept in the Horizon's database, so
    the waiting card can still say why they wait after the server restarts."""
    with horizon._connect(base_dir) as conn:
        conn.executescript(_LEFT_SCHEMA)
        rows = conn.execute("SELECT node_id FROM organize_left WHERE orbits = ?", (signature,)).fetchall()
    return {r[0] for r in rows}


def remember_left(ids: set[str], signature: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> None:
    if not ids:
        return
    now = time.time()
    with horizon._connect(base_dir) as conn:
        conn.executescript(_LEFT_SCHEMA)
        conn.executemany(
            "INSERT OR REPLACE INTO organize_left (node_id, orbits, left_at) VALUES (?, ?, ?)",
            [(node_id, signature, now) for node_id in ids],
        )


def orbit_listing(orbits: dict[str, str], held: dict[str, list[str]]) -> list[dict]:
    """What the model is told about each orbit: its title and a few of the captures it holds."""
    return [
        {"id": orbit_id, "title": title, "holds": held.get(orbit_id, [])[:_HELD_TITLES]}
        for orbit_id, title in orbits.items()
    ]
