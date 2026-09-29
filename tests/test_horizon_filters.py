"""The list's conditions (`horizon.NodeFilter`), ANDed across kinds, and removals recorded so the
list can show them (`horizon_events`)."""

from __future__ import annotations

from penumbra import horizon
from penumbra.schema import Source, SourceBlock


def _node(origin: str, *, tags=(), orbits=(), state="ready", created: float = 0.0) -> str:
    node = horizon.add_pending_node(origin, "web")
    horizon.store_blocks(node.id, Source(id="s0", kind="web", origin=origin,
                                         blocks=[SourceBlock(locator="whole", text=f"text of {origin}")]))
    horizon.update_node(node.id, state=state, title=origin.rsplit("/", 1)[-1], tags=list(tags))
    with horizon._connect() as conn:
        if created:
            conn.execute("UPDATE nodes SET created_at = ? WHERE id = ?", (created, node.id))
        for i, orbit in enumerate(orbits):
            conn.execute(
                "INSERT INTO memberships VALUES (?, ?, ?, ?)", (node.id, orbit, f"s{i + 1}", created or 1.0)
            )
    return node.id


def _ids(**kw) -> set[str]:
    return {n.id for n in horizon.list_nodes(filters=horizon.NodeFilter(**kw))}


def test_conditions_combine_and_tags_can_be_any_or_all():
    a = _node("https://x.example/sleep", tags=["sleep", "health"], orbits=["body"], created=100)
    b = _node("https://x.example/coffee", tags=["coffee", "health"], orbits=["food"], created=200)
    c = _node("https://x.example/loose", tags=["sleep"], created=300, state="ready_undistilled")
    assert _ids(tags=("sleep", "coffee")) == {a, b, c}, "any"
    assert _ids(tags=("sleep", "health"), tag_mode="all") == {a}, "all"
    assert _ids(tags=("health",), orbits=("food",)) == {b}, "different kinds AND together"
    assert _ids(orbits=(horizon.NO_ORBIT,)) == {c}
    assert _ids(orbits=("body", horizon.NO_ORBIT)) == {a, c}
    assert _ids(states=("ready_undistilled",)) == {c}
    assert _ids(since=150, until=300) == {b}
    assert horizon.count_nodes(filters=horizon.NodeFilter(tags=("health",))) == 2


def test_the_list_can_be_ordered():
    _node("https://x.example/b-mid", created=200)
    _node("https://x.example/a-old", created=100)
    _node("https://x.example/c-new", created=300)
    titles = lambda sort: [n.title for n in horizon.list_nodes(sort=sort)]
    assert titles("newest") == ["c-new", "b-mid", "a-old"]
    assert titles("oldest") == ["a-old", "b-mid", "c-new"]
    assert titles("title") == ["a-old", "b-mid", "c-new"]


def test_a_removal_is_recorded_with_what_it_carried_and_filters_like_the_list():
    a = _node("https://x.example/lighthouse", tags=["navigation"], orbits=["sea"])
    horizon.remove_node(a, detail={"everywhere": True})
    events = horizon.removal_events()
    assert [(e["node_id"], e["title"], e["orbits"], e["everywhere"]) for e in events] == [
        (a, "lighthouse", ["sea"], True)
    ]
    assert horizon.removal_events(query="light") and not horizon.removal_events(query="origami")
    assert horizon.removal_events(filters=horizon.NodeFilter(tags=("navigation",)))
    assert not horizon.removal_events(filters=horizon.NodeFilter(orbits=(horizon.NO_ORBIT,)))
    assert not horizon.removal_events(filters=horizon.NodeFilter(states=("ready",))), "no states"


def test_every_tag_is_listed_with_its_count():
    _node("https://x.example/1", tags=["sleep", "health"])
    _node("https://x.example/2", tags=["health"])
    assert horizon.all_tags()[:2] == [{"name": "health", "count": 2}, {"name": "sleep", "count": 1}]


def test_a_delete_that_fails_leaves_no_removal_record():
    """The record and the delete are one transaction: a list must never show "Removed" beside a
    capture that is still there."""
    import sqlite3

    import pytest

    a = _node("https://x.example/still-here")
    with horizon._connect() as conn:
        conn.execute("CREATE TRIGGER refuse BEFORE DELETE ON nodes BEGIN SELECT RAISE(ABORT, 'busy'); END")
    with pytest.raises(sqlite3.IntegrityError):
        horizon.remove_node(a)
    assert horizon.removal_events() == []
    assert horizon.get_node(a) is not None
    with horizon._connect() as conn:
        conn.execute("DROP TRIGGER refuse")
    assert horizon.remove_node(a) and len(horizon.removal_events()) == 1
    assert not horizon.remove_node(a) and len(horizon.removal_events()) == 1, "a second press records nothing"


def test_only_the_newest_removal_records_are_kept(monkeypatch):
    monkeypatch.setattr(horizon, "MAX_REMOVAL_EVENTS", 3)
    ids = [_node(f"https://x.example/r{i}") for i in range(5)]
    for node_id in ids:
        horizon.remove_node(node_id)
    kept = [e["node_id"] for e in horizon.removal_events()]
    assert sorted(kept) == sorted(ids[-3:]), "the two oldest records went"
