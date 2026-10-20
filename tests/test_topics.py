"""Orbits as the kit's topics (`topics.py`): the mapping, the sync that keeps the kit's copy of the
memberships, and the reader's decisions written as theirs."""

from __future__ import annotations

import sqlite3

from penumbra import horizon, memory_store, topics
from penumbra.orbit import delete_orbit, mutate_orbit, orbit_path
from penumbra.schema import Source, SourceBlock

BASE = "h"
ORBITS = "o"


def _capture(url: str, text: str = "a capture with some text in it") -> str:
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(node_id, Source(id=node_id, kind="web", origin=url,
                                          blocks=[SourceBlock(locator="whole", text=text)]), base_dir=BASE)
    return horizon.resolve_id(node_id, base_dir=BASE)


def _orbit(orbit_id: str, title: str = "") -> None:
    def _title(orb):
        orb.title = title

    mutate_orbit(orbit_id, _title, create=True, base_dir=ORBITS)


def _sync() -> None:
    topics.sync(orbits_dir=ORBITS, base_dir=BASE)


def _store():
    return memory_store.store(BASE)


def _kit_rows() -> int:
    """Every row the kit's topic tables hold, to tell a sync that wrote from one that did not."""
    with sqlite3.connect(memory_store.store_path(BASE)) as conn:
        return sum(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                   for t in ("topics", "topic_names", "topic_retired", "topic_members"))


def test_every_orbit_gets_a_topic_named_as_the_orbit_is():
    _orbit("orbit-1", "Sleep")
    _orbit("orbit-2")
    _sync()
    store = _store()
    assert store.topic(topics.topic_of("orbit-1", base_dir=BASE)).name == "Sleep"
    assert store.topic(topics.topic_of("orbit-2", base_dir=BASE)).name == "Untitled orbit", \
        "an untitled orbit is called what the workspace calls it"


def test_a_second_sync_writes_nothing_even_for_a_name_the_kit_cuts():
    _orbit("orbit-1", "A very long title for an orbit that goes well past the sixty characters a topic keeps")
    node = _capture("https://x.example/a")
    horizon.promote_node(node, "orbit-1", base_dir=BASE, orbits_dir=ORBITS)
    _sync()
    before = _kit_rows()
    _sync()
    assert _kit_rows() == before


def test_a_renamed_orbit_renames_its_topic():
    _orbit("orbit-1", "Sleep")
    _sync()
    _orbit("orbit-1", "Sleep and memory")
    _sync()
    assert _store().topic(topics.topic_of("orbit-1", base_dir=BASE)).name == "Sleep and memory"


def test_a_deleted_orbit_retires_its_topic_and_leaves_its_name_free():
    _orbit("orbit-1", "Sleep")
    _sync()
    topic_id = topics.topic_of("orbit-1", base_dir=BASE)
    delete_orbit("orbit-1", base_dir=ORBITS)
    _sync()
    assert _store().topic(topic_id).retired and topics.topic_of("orbit-1", base_dir=BASE) is None
    assert _store().said_retired_names() == set(), "organising may open a topic of that name again"


def test_an_unreadable_orbit_keeps_its_topic():
    _orbit("orbit-1", "Sleep")
    _sync()
    topic_id = topics.topic_of("orbit-1", base_dir=BASE)
    orbit_path("orbit-1", base_dir=ORBITS).write_text("{not json", encoding="utf-8")
    _sync()
    assert not _store().topic(topic_id).retired and topics.topic_of("orbit-1", base_dir=BASE) == topic_id


def test_a_topic_with_no_orbit_is_retired_but_not_while_a_pass_is_organising():
    stray = _store().create_topic("Made by a pass", provenance="inferred")
    with topics.organizing():
        _sync()
        assert not _store().topic(stray.id).retired, "its orbit row is on the way"
    _sync()
    assert _store().topic(stray.id).retired


def test_the_kit_mirrors_where_captures_are_filed():
    _orbit("orbit-1", "Sleep")
    a, b = _capture("https://x.example/a"), _capture("https://x.example/b")
    horizon.promote_node(a, "orbit-1", base_dir=BASE, orbits_dir=ORBITS)
    membership = horizon.promote_node(b, "orbit-1", base_dir=BASE, orbits_dir=ORBITS)
    _sync()
    topic_id = topics.topic_of("orbit-1", base_dir=BASE)
    assert {i.id for i in _store().topic_items(topic_id)} == {a, b}
    horizon.forget_membership("orbit-1", membership.source_id, base_dir=BASE)
    _sync()
    assert {i.id for i in _store().topic_items(topic_id)} == {a}


def test_a_readers_removal_stands_and_their_own_refiling_overrides_it():
    _orbit("orbit-1", "Sleep")
    a = _capture("https://x.example/a")
    topics.removed(a, "orbit-1", base_dir=BASE, orbits_dir=ORBITS)
    topic_id = topics.topic_of("orbit-1", base_dir=BASE)
    assert (a, topic_id) in _store().removed_pairs()
    # Filed again automatically, the kit keeps the reader's removal: the mirror is refused.
    horizon.promote_node(a, "orbit-1", base_dir=BASE, orbits_dir=ORBITS)
    _sync()
    assert _store().item_topics(a) == []
    # Filed again by the reader, it is theirs.
    topics.placed(a, "orbit-1", said=True, base_dir=BASE, orbits_dir=ORBITS)
    assert [t.id for t in _store().item_topics(a)] == [topic_id]


def test_a_dismissal_is_the_kits():
    _orbit("orbit-1", "Sleep")
    a = _capture("https://x.example/a")
    topics.dismiss(a, "orbit-1", base_dir=BASE, orbits_dir=ORBITS)
    assert _store().dismissed() == {(a, topics.topic_of("orbit-1", base_dir=BASE))}


def test_a_capture_not_yet_an_item_is_left_out():
    _orbit("orbit-1", "Sleep")
    pending = horizon.add_pending_node("https://x.example/q", "web", base_dir=BASE)
    topics.placed(pending.id, "orbit-1", said=True, base_dir=BASE, orbits_dir=ORBITS)
    topics.removed(pending.id, "orbit-1", base_dir=BASE, orbits_dir=ORBITS)
    assert _store().removed_pairs() == set()


def test_clearing_the_horizon_forgets_every_mapping():
    _orbit("orbit-1", "Sleep")
    _sync()
    horizon.clear_all(base_dir=BASE)
    assert topics.topic_of("orbit-1", base_dir=BASE) is None
