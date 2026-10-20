"""Orbits as the kit's topics: one topic per orbit, so filing suggestions and organising run on
the kit's memory store (`rlm_harness.memory_organise.suggest_topics`, `memory_tasks.organize_pending`).

**An orbit is still the truth for what it holds.** `memberships` in the Horizon's index keeps the
source id each capture became and when it was filed (invariant 85 reads it), and every reader of
"where is this capture" keeps reading it. The kit's topic memberships are a mirror kept for the
kit's passes, which read nothing else: `sync` writes whatever differs before each of them, so a
mirror write that failed heals at the next suggestion.

**A reader's decision is written as theirs at once** (`placed(said=True)`, `removed`, `dismiss`):
the kit refuses an `inferred` placement of a pair a person took apart, which is how a capture the
reader took out of an orbit is never suggested or organised straight back. `sync` itself writes
only `inferred` rows, because it cannot know who made a membership.

`orbit_topics` maps an orbit's slug to its topic and the name the topic was last given, so a sync
that finds nothing changed writes nothing. One process holds `LOCK` around every write here and
around the host's side of organising (a new orbit's file and its row), and `organizing()` marks a
pass in flight, during which a topic the pass opened has no row yet and must not be retired.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from pathlib import Path

from . import horizon, memory_store
from .horizon import DEFAULT_HORIZON_DIR
from .naming import fallback_title
from .orbit import DEFAULT_ORBITS_DIR, list_orbit_summaries, load_orbit, orbit_path, slug

_log = logging.getLogger(__name__)

#: Held around every write to `orbit_topics` and the kit's topics, and by the organising pass's
#: hooks. Single-process, like the other in-memory maps (AGENTS.md).
LOCK = threading.RLock()
_ORGANIZING = {"passes": 0}
#: Pairs the kit refused a mirror write for, logged once each rather than at every sync.
_REFUSED: set[tuple[str, str, str]] = set()


@contextmanager
def organizing():
    """Mark an organising pass in flight: a topic it opens gets its orbit row from the pass's own
    hook, a moment later, so `sync` must not take it for an orphan meanwhile."""
    with LOCK:
        _ORGANIZING["passes"] += 1
    try:
        yield
    finally:
        with LOCK:
            _ORGANIZING["passes"] -= 1


def orbit_name(orbit) -> str:
    """The name an orbit's topic carries: its title, or what an untitled orbit is called."""
    sources = orbit.sources
    return orbit.title or fallback_title([s.origin for s in sources],
                                         [s.preview.get("title", "") for s in sources]) or slug(orbit.id)


def _rows(base_dir) -> dict[str, tuple[str, str]]:
    with horizon._connect(base_dir) as conn:
        return {r[0]: (r[1], r[2]) for r in conn.execute("SELECT orbit_id, topic_id, name FROM orbit_topics")}


def _set_row(orbit: str, topic_id: str, name: str, base_dir) -> None:
    with horizon._connect(base_dir) as conn:
        conn.execute("INSERT OR REPLACE INTO orbit_topics (orbit_id, topic_id, name) VALUES (?, ?, ?)",
                     (orbit, topic_id, name))


def _drop_row(orbit: str, base_dir) -> None:
    with horizon._connect(base_dir) as conn:
        conn.execute("DELETE FROM orbit_topics WHERE orbit_id = ?", (orbit,))


def topic_of(orbit_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> str | None:
    """The topic an orbit is, or None when it has none yet."""
    row = _rows(base_dir).get(slug(orbit_id))
    return row[0] if row else None


def orbits_by_topic(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict[str, str]:
    return {topic: orbit for orbit, (topic, _name) in _rows(base_dir).items()}


def link(orbit_id: str, topic_id: str, name: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> None:
    """Record that an orbit is this topic (for an orbit the organising pass made for its topic)."""
    with LOCK:
        _set_row(slug(orbit_id), topic_id, name, base_dir)


def _ensure(orbit: str, name: str, rows: dict, store, base_dir) -> str:
    """The orbit's live topic, made (or replaced, if it was retired) when it has none, renamed when
    its name changed. Called under `LOCK`."""
    row = rows.get(orbit)
    topic = store.topic(row[0]) if row else None
    if topic is None or topic.retired:
        topic = store.create_topic(name, provenance="inferred")
        _set_row(orbit, topic.id, name, base_dir)
    elif row[1] != name:
        store.rename_topic(topic.id, name, provenance="inferred")
        _set_row(orbit, topic.id, name, base_dir)
    return topic.id


def _refused(kind: str, item_id: str, topic_id: str, exc: Exception) -> None:
    key = (kind, item_id, topic_id)
    if key not in _REFUSED:
        _REFUSED.add(key)
        _log.info("topics: the kit refused to %s %s in %s: %s", kind, item_id, topic_id, exc)


def sync(*, orbits_dir: str | Path = DEFAULT_ORBITS_DIR, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> None:
    """Bring the kit's topics in line with the orbits and what they hold, writing only what
    differs. Before every suggestion and every organising pass."""
    store = memory_store.store(base_dir)
    with LOCK:
        orbits, unreadable = list_orbit_summaries(base_dir=orbits_dir)
        named = {slug(o.id): orbit_name(o) for o in orbits}
        rows = _rows(base_dir)
        for orbit, name in named.items():
            _ensure(orbit, name, rows, store, base_dir)
        # A file that does not parse is still an orbit: its topic waits, untouched, rather than
        # being retired and its name given up.
        present = set(named) | {slug(stem) for stem in unreadable}
        rows = _rows(base_dir)
        for orbit, (topic_id, _name) in rows.items():
            if orbit in present or orbit_path(orbit, base_dir=orbits_dir).exists():
                continue
            _retire(store, topic_id)
            _drop_row(orbit, base_dir)
        rows = _rows(base_dir)
        mapped = {topic_id for topic_id, _name in rows.values()}
        if not _ORGANIZING["passes"]:
            for topic in store.topics():
                if topic.id not in mapped:
                    _retire(store, topic.id)   # opened by a pass whose orbit was never made
        topic_for = {orbit: topic_id for orbit, (topic_id, _name) in rows.items()}
        with horizon._connect_labels(base_dir) as conn:
            wanted = {
                (f"m{r[0]}", topic_for[r[1]])
                for r in conn.execute(
                    "SELECT n.memory_rowid, m.orbit_id FROM memberships m JOIN nodes n ON n.id = m.node_id "
                    "WHERE n.memory_rowid IS NOT NULL")
                if r[1] in topic_for
            }
            held = {(f"m{r[0]}", f"t{r[1]}") for r in conn.execute(
                "SELECT item_id, topic_id FROM mem.current_members")}
        held = {pair for pair in held if pair[1] in mapped}
        for item_id, topic_id in sorted(wanted - held):
            try:
                store.place(item_id, topic_id, provenance="inferred")
            except (KeyError, ValueError) as exc:
                _refused("place", item_id, topic_id, exc)
        for item_id, topic_id in sorted(held - wanted):
            try:
                store.unplace(item_id, topic_id, provenance="inferred")
            except (KeyError, ValueError) as exc:
                _refused("unplace", item_id, topic_id, exc)


def _retire(store, topic_id: str) -> None:
    try:
        store.retire_topic(topic_id, provenance="inferred")
    except (KeyError, ValueError) as exc:
        _log.info("topics: %s stays: %s", topic_id, exc)


def _topic_for_orbit(orbit_id: str, store, base_dir, orbits_dir) -> str | None:
    """The orbit's topic, made now when it has none and its file exists."""
    orbit = load_orbit(orbit_id, base_dir=orbits_dir)
    if orbit is None:
        return topic_of(orbit_id, base_dir=base_dir)
    return _ensure(slug(orbit_id), orbit_name(orbit), _rows(base_dir), store, base_dir)


def _item_id(node_id: str, base_dir) -> str | None:
    """The kit item a capture is, or None while it is not one."""
    node = horizon.get_node(node_id, base_dir=base_dir)
    return node.id if node is not None and node.id.startswith("m") else None


def placed(node_id: str, orbit_id: str, *, said: bool, base_dir: str | Path = DEFAULT_HORIZON_DIR,
           orbits_dir: str | Path = DEFAULT_ORBITS_DIR) -> None:
    """A capture was filed into an orbit: by the reader (`said`), whose decision then stands over
    any earlier removal, or automatically, which `sync` would mirror anyway."""
    item_id = _item_id(node_id, base_dir)
    if item_id is None:
        return
    store = memory_store.store(base_dir)
    with LOCK:
        topic_id = _topic_for_orbit(orbit_id, store, base_dir, orbits_dir)
        if topic_id is None:
            return
        try:
            store.place(item_id, topic_id, provenance="said" if said else "inferred")
        except (KeyError, ValueError) as exc:
            _refused("place", item_id, topic_id, exc)


def removed(node_id: str, orbit_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR,
            orbits_dir: str | Path = DEFAULT_ORBITS_DIR) -> None:
    """The reader took a capture out of an orbit: the pair stays apart for good, so neither a
    suggestion nor organising files it straight back. The orbit gets its topic now if no sync has
    made one yet, since the decision must be kept either way."""
    item_id = _item_id(node_id, base_dir)
    if item_id is None:
        return
    store = memory_store.store(base_dir)
    with LOCK:
        topic_id = _topic_for_orbit(orbit_id, store, base_dir, orbits_dir)
        if topic_id is not None:
            store.unplace(item_id, topic_id, provenance="said")


def dismiss(node_id: str, orbit_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR,
            orbits_dir: str | Path = DEFAULT_ORBITS_DIR) -> None:
    """Never suggest this capture for this orbit again."""
    item_id = _item_id(node_id, base_dir)
    if item_id is None:
        return
    store = memory_store.store(base_dir)
    with LOCK:
        topic_id = _topic_for_orbit(orbit_id, store, base_dir, orbits_dir)
        if topic_id is not None:
            store.dismiss(item_id, topic_id)


def orbit_gone(orbit_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> None:
    """An orbit was deleted: its topic is retired, as a pass's own retirement, so its name stays
    free for organising to open again, and its row goes."""
    key = slug(orbit_id)
    with LOCK:
        row = _rows(base_dir).get(key)
        if row is None:
            return
        _retire(memory_store.store(base_dir), row[0])
        _drop_row(key, base_dir)
