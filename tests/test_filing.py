"""Filing suggestions (`filing.py`): local, from shared entities and tags, never a model call."""

from __future__ import annotations

from penumbra import filing, horizon, memory_store
from penumbra.schema import Source, SourceBlock
from tests._labels import label

BASE = "h"
ORBITS = "o"


def _capture(url, entities=(), tags=(), state="ready", title=None) -> str:
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(node_id, Source(id=node_id, kind="web", origin=url,
                                          blocks=[SourceBlock(locator="whole", text="t")]), base_dir=BASE)
    # Stored, the capture carries its kit item id; the temporary id is only its `former_id`.
    item_id = horizon.resolve_id(node_id, base_dir=BASE)
    given = {"entities": list(entities), "tags": list(tags), "title": title}
    label(item_id, base_dir=BASE, state=state, **{k: v for k, v in given.items() if v})
    return item_id


def _file(node_id, orbit):
    horizon.promote_node(node_id, orbit, base_dir=BASE, orbits_dir=ORBITS, create=True)


def test_a_capture_sharing_enough_with_an_orbit_is_suggested_for_it():
    _file(_capture("https://x.example/a", ["REM", "hippocampus"], ["sleep"]), "sleep")
    loose = _capture("https://x.example/b", ["REM", "hippocampus"], title="New paper")
    got = filing.suggestions(base_dir=BASE)
    assert got == [{"node_id": loose, "title": "New paper", "orbit": "sleep",
                    "shared": ["REM", "hippocampus"], "tags": [], "score": 4}]


def test_a_weak_match_is_not_offered():
    _file(_capture("https://x.example/a", ["REM"], ["sleep"]), "sleep")
    _capture("https://x.example/b", ["REM"])  # one entity, no tag: score 2
    assert filing.suggestions(base_dir=BASE) == []


def test_the_landing_orbit_alone_still_counts_as_unfiled_and_is_never_suggested():
    _file(_capture("https://x.example/a", ["REM", "x"]), "sleep")
    landed = _capture("https://x.example/b", ["REM", "x"])
    _file(landed, "first-orbit")
    got = filing.suggestions("first-orbit", base_dir=BASE)
    assert [(s["node_id"], s["orbit"]) for s in got] == [(landed, "sleep")]


def test_a_filed_capture_is_not_suggested():
    _file(_capture("https://x.example/a", ["REM", "x"]), "sleep")
    other = _capture("https://x.example/b", ["REM", "x"])
    _file(other, "books")
    assert all(s["node_id"] != other for s in filing.suggestions(base_dir=BASE))


def test_a_declined_pair_is_not_offered_again():
    _file(_capture("https://x.example/a", ["REM", "x"]), "sleep")
    loose = _capture("https://x.example/b", ["REM", "x"])
    filing.dismiss(loose, "sleep", base_dir=BASE)
    assert filing.suggestions(base_dir=BASE) == []


def test_aliases_count_as_the_same_entity():
    _file(_capture("https://x.example/a", ["Matthew Walker", "REM"]), "sleep")
    loose = _capture("https://x.example/b", ["馬修·沃克", "REM"])
    memory_store.store(BASE).merge("馬修·沃克", "Matthew Walker")
    got = filing.suggestions(base_dir=BASE)
    assert got[0]["node_id"] == loose and got[0]["shared"] == ["Matthew Walker", "REM"]


def test_an_unsummarised_capture_is_not_suggested():
    _file(_capture("https://x.example/a", ["REM", "x"]), "sleep")
    _capture("https://x.example/b", state="ready_undistilled")
    assert filing.suggestions(base_dir=BASE) == []
