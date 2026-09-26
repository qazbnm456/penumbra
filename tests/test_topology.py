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


def test_a_lens_can_match_every_tag_an_orbit_carries_not_only_its_top_few():
    """`tags` is the orbit's most common few, for display. The map's lens matched against it, so a
    tag named once in an orbit carrying more than six was never lit: pressing it dimmed every
    planet, including the one that held it."""
    many = [f"t{i}" for i in range(topology.TOP_PER_ORBIT)] + ["supply chain security"]
    _file(_capture("https://x.example/many", tags=many), "sec")
    (orbit,) = topology.star_map(base_dir=BASE)["orbits"]
    assert "supply chain security" not in orbit["tags"], "the display list is still capped"
    assert "supply chain security" in orbit["all_tags"]
    assert sorted(orbit["all_tags"]) == sorted(many)


def test_loose_captures_are_counted_apart_from_orbits():
    _capture("https://x.example/a", state="ready_undistilled")
    horizon.add_pending_node("https://x.example/q", "web", base_dir=BASE)
    loose = topology.star_map(base_dir=BASE)["loose"]
    items = loose.pop("items")
    assert loose == {"count": 2, "undistilled": 1, "busy": 1}
    assert {i["state"] for i in items} == {"ready_undistilled", "queued"}


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


def test_each_drawn_moon_and_loose_dot_carries_a_name_newest_first():
    """The map names what it draws, so a pointer on a moon can say which capture it is."""
    first = _capture("https://x.example/a", title="Older")
    second = _capture("https://x.example/b", title="Newer", state="ready_undistilled")
    _file(first, "sleep")
    _file(second, "sleep")
    _capture("https://x.example/c", title="Loose one")
    found = topology.star_map(base_dir=BASE)
    (orbit,) = found["orbits"]
    assert [m["title"] for m in orbit["moons"]] == ["Newer", "Older"]
    assert orbit["moons"][0] == {
        "id": second, "title": "Newer", "state": "ready_undistilled", "orbits": ["sleep"],
    }
    assert [i["title"] for i in found["loose"]["items"]] == ["Loose one"]


def test_the_named_moons_are_capped_at_what_the_map_draws():
    for i in range(topology.MAX_MOONS + 3):
        _file(_capture(f"https://x.example/{i}"), "big")
    (orbit,) = topology.star_map(base_dir=BASE)["orbits"]
    assert orbit["captures"] == topology.MAX_MOONS + 3
    assert len(orbit["moons"]) == topology.MAX_MOONS


def test_a_pasted_capture_is_named_by_its_words_not_its_origin_key():
    node_id = horizon.node_id_for("pasted:some thought worth keeping #1a2b3c4d")
    horizon.add_pending_node("pasted:some thought worth keeping #1a2b3c4d", "text", base_dir=BASE)
    horizon.update_node(node_id, base_dir=BASE, state="ready_undistilled")
    (item,) = topology.star_map(base_dir=BASE)["loose"]["items"]
    assert item["title"] == "some thought worth keeping"


def test_a_bridge_lists_where_each_orbit_names_what_they_share():
    a1 = _capture("https://x.example/a1", title="Codex notes", entities=["OpenAI Codex", "iOS"])
    b1 = _capture("https://x.example/b1", title="CFP call", entities=["OpenAI Codex"])
    _capture("https://x.example/c1", title="Unrelated", entities=["iOS"])
    _file(a1, "first")
    _file(b1, "cfp")
    found = topology.bridge("first", "cfp", base_dir=BASE)
    assert [s["name"] for s in found["shared"]] == ["OpenAI Codex"]
    (codex,) = found["shared"]
    assert [c["title"] for c in codex["a"]] == ["Codex notes"]
    assert [c["title"] for c in codex["b"]] == ["CFP call"]


def test_an_entity_scope_can_span_two_orbits():
    a1 = _capture("https://x.example/a1", entities=["Codex"])
    b1 = _capture("https://x.example/b1", entities=["Codex"])
    c1 = _capture("https://x.example/c1", entities=["Codex"])
    _file(a1, "one")
    _file(b1, "two")
    _file(c1, "three")
    picked = search.select_for_ask("?", "entity", "Codex", orbit=["one", "two"], budget_chars=10_000,
                                   max_items=5, base_dir=BASE)
    assert set(picked.node_ids) == {a1, b1}
