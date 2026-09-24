"""The star map and the knowledge graph (`topology.py`): derived from summaries, never a model."""

from __future__ import annotations

import sqlite3

from penumbra import horizon, search, topology
from penumbra.schema import Source, SourceBlock

BASE = "h"
ORBITS = "o"


def _capture(url: str, text: str = "text", *, state="ready", tags=(), entities=(), title=None) -> str:
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(
        node_id,
        Source(id=node_id, kind="web", origin=url, blocks=[SourceBlock(locator="whole", text=text)]),
        base_dir=BASE,
    )
    fields = {"state": state, "tags": list(tags), "entities": list(entities)}
    if title:
        fields["title"] = title
    horizon.update_node(node_id, base_dir=BASE, **fields)
    return node_id


def _file(node_id: str, orbit_id: str) -> None:
    horizon.promote_node(node_id, orbit_id, base_dir=BASE, orbits_dir=ORBITS, create=True)


def test_orbits_carry_their_filed_captures_and_top_entities():
    a = _capture("https://x.example/a", entities=["REM", "Walker"], tags=["sleep"])
    b = _capture("https://x.example/b", entities=["REM"], tags=["sleep"])
    c = _capture("https://x.example/c", state="ready_undistilled")
    for node in (a, b, c):
        _file(node, "sleep")
    found = topology.star_map(base_dir=BASE)
    (orbit,) = found["orbits"]
    assert orbit["slug"] == "sleep"
    assert orbit["captures"] == 3 and orbit["undistilled"] == 1
    assert orbit["entities"] == ["REM", "Walker"]
    assert orbit["tags"] == ["sleep"]
    assert found["total"] == {"count": 3, "distilled": 2}


def test_loose_captures_are_counted_apart_from_orbits():
    _capture("https://x.example/a", state="ready_undistilled")
    horizon.add_pending_node("https://x.example/q", "web", base_dir=BASE)
    loose = topology.star_map(base_dir=BASE)["loose"]
    assert loose == {"count": 2, "undistilled": 1, "busy": 1}


def test_orbits_that_share_an_entity_are_bridged_by_it():
    a = _capture("https://x.example/a", entities=["caffeine", "REM"])
    b = _capture("https://x.example/b", entities=["caffeine"])
    c = _capture("https://x.example/c", entities=["Rust"])
    _file(a, "sleep")
    _file(b, "coffee")
    _file(c, "code")
    bridges = topology.star_map(base_dir=BASE)["bridges"]
    assert bridges == [{"a": "coffee", "b": "sleep", "shared": ["caffeine"], "weight": 1}]


def test_a_capture_in_two_orbits_counts_once_in_the_total():
    a = _capture("https://x.example/a", entities=["x"])
    _file(a, "one")
    _file(a, "two")
    found = topology.star_map(base_dir=BASE)
    assert found["total"]["count"] == 1
    assert {o["slug"] for o in found["orbits"]} == {"one", "two"}


def test_the_graph_links_entities_named_by_the_same_capture():
    _capture("https://x.example/a", entities=["REM", "memory"], tags=["sleep"])
    _capture("https://x.example/b", entities=["REM", "memory", "Walker"], tags=["sleep", "books"])
    g = topology.graph(base_dir=BASE)
    assert g["entities"][0] == {"name": "REM", "count": 2}
    edges = {(e["a"], e["b"]): e["weight"] for e in g["edges"]}
    assert edges[("REM", "memory")] == 2
    assert edges[("REM", "Walker")] == 1
    assert {t["name"] for t in g["tags"]} == {"sleep", "books"}


def test_an_unsummarised_capture_is_listed_apart_and_links_nothing():
    _capture("https://x.example/a", entities=["REM"])
    pending = _capture("https://x.example/b", state="ready_undistilled", title="Not yet")
    g = topology.graph(base_dir=BASE)
    assert g["undistilled"] == [{"node_id": pending, "title": "Not yet"}]
    assert [c["node_id"] for c in g["captures"]] != [pending]


def test_the_graph_can_be_one_orbit():
    a = _capture("https://x.example/a", entities=["REM"])
    _capture("https://x.example/b", entities=["Rust"])
    _file(a, "sleep")
    g = topology.graph("sleep", base_dir=BASE)
    assert [e["name"] for e in g["entities"]] == ["REM"]


def test_malformed_json_in_a_row_does_not_break_either_drawing():
    _capture("https://x.example/a", entities=["REM"])
    bad = _capture("https://x.example/b", entities=["x"])
    conn = sqlite3.connect(horizon.index_path(BASE))
    conn.execute("UPDATE nodes SET entities = '{broken', tags = 'nope' WHERE id = ?", (bad,))
    conn.commit()
    conn.close()
    assert topology.star_map(base_dir=BASE)["total"]["count"] == 2
    assert [e["name"] for e in topology.graph(base_dir=BASE)["entities"]] == ["REM"]


def test_an_orbit_narrows_an_ask_scope():
    inside = _capture("https://x.example/a", "sleep", entities=["REM"])
    _capture("https://x.example/b", "sleep", entities=["REM"])
    _file(inside, "sleep")
    picked = search.select_for_ask("sleep", "entity", "REM", budget_chars=10_000, max_items=5,
                                   orbit="sleep", base_dir=BASE)
    assert picked.node_ids == [inside]
