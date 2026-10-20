"""Concept alignment's alias table, kept in the kit's memory store (`concepts.py`), and how readers
apply it."""

from __future__ import annotations

import pytest
from rlm_harness.memory import fold_name

from penumbra import concepts, horizon, memory_store, search, topology
from penumbra.schema import Source, SourceBlock
from tests._labels import label

BASE = "h"


def _capture(url: str, entities, text="t") -> str:
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(node_id, Source(id=node_id, kind="web", origin=url,
                                          blocks=[SourceBlock(locator="whole", text=text)]), base_dir=BASE)
    # Stored, the capture carries its kit item id; the temporary id is only its `former_id`.
    item_id = horizon.resolve_id(node_id, base_dir=BASE)
    label(item_id, base_dir=BASE, entities=list(entities))
    return item_id


def _store():
    return memory_store.store(BASE)


def test_unseen_names_are_the_ones_no_alignment_has_considered():
    _capture("https://x.example/a", ["Matthew Walker", "REM"])
    _capture("https://x.example/b", ["REM"])
    assert _store().unseen_entities() == ["REM", "Matthew Walker"]
    _store().mark_seen(["REM"])
    assert _store().unseen_entities() == ["Matthew Walker"]


def test_the_store_accepts_only_merges_between_real_distinct_names_and_never_a_chain():
    _capture("https://x.example/a", ["Matthew Walker", "REM"])
    _capture("https://x.example/b", ["馬修·沃克", "M. Walker"])
    store = _store()
    assert store.merge("馬修·沃克", "Matthew Walker") == "Matthew Walker"
    with pytest.raises(ValueError):
        store.merge("REM", "REM")            # names itself
    with pytest.raises(ValueError):
        store.merge("Invented", "REM")       # not a name in use
    # Pointing at an alias is followed to its canonical instead of forming a chain.
    assert store.merge("M. Walker", "馬修·沃克") == "Matthew Walker"
    table = concepts.aliases(base_dir=BASE)
    assert table == {"馬修·沃克": "Matthew Walker", "m. walker": "Matthew Walker"}
    with pytest.raises(ValueError):
        store.merge("Matthew Walker", "REM")  # a canonical other names point at
    assert concepts.aliases(base_dir=BASE) == table, (
        "a canonical that other names point at was itself merged away"
    )


def test_a_merge_changes_what_readers_see_and_nothing_stored():
    a = _capture("https://x.example/a", ["Matthew Walker"])
    b = _capture("https://x.example/b", ["馬修·沃克"])
    _store().merge("馬修·沃克", "Matthew Walker")
    graph = topology.graph(base_dir=BASE)
    assert graph["entities"] == [{"name": "Matthew Walker", "count": 2, "aliases": ["馬修·沃克"]}]
    assert horizon.get_node(b, base_dir=BASE).entities == ["Matthew Walker"], "a reader skipped the table"
    assert concepts.all_names(base_dir=BASE) == {"Matthew Walker": 1, "馬修·沃克": 1}, (
        "a stored summary was rewritten"
    )
    picked = search.select_for_ask("?", "entity", "Matthew Walker", budget_chars=10_000, max_items=5,
                                   base_dir=BASE)
    assert set(picked.node_ids) == {a, b}


def test_undoing_a_merge_restores_both_names_and_keeps_them_seen():
    _capture("https://x.example/a", ["Matthew Walker"])
    _capture("https://x.example/b", ["馬修·沃克"])
    _store().mark_seen(["Matthew Walker", "馬修·沃克"])
    _store().merge("馬修·沃克", "Matthew Walker")
    assert concepts.remove_alias("馬修·沃克", base_dir=BASE)
    assert not concepts.remove_alias("馬修·沃克", base_dir=BASE), "a name merged into nothing was undone"
    names = {e["name"] for e in topology.graph(base_dir=BASE)["entities"]}
    assert names == {"Matthew Walker", "馬修·沃克"}
    assert _store().unseen_entities() == [], "an undone merge would simply be proposed again"


def test_a_batch_cannot_leave_a_chain_behind():
    _capture("https://x.example/a", ["M. Walker", "Walker", "Matthew Walker"])
    store = _store()
    batch = ["M. Walker", "Walker", "Matthew Walker"]
    for alias, canonical in (("M. Walker", "Walker"), ("Walker", "Matthew Walker")):
        try:
            store.merge(alias, canonical, provenance="inferred", batch=batch)
        except ValueError:
            pass
    table = concepts.aliases(base_dir=BASE)
    folded = set(table)
    assert all(fold_name(canonical) not in folded for canonical in table.values()), f"a chain: {table}"


def test_only_a_name_the_run_was_asked_about_becomes_an_alias():
    _capture("https://x.example/a", ["M. Walker", "Matthew Walker"])
    store = _store()
    store.merge("M. Walker", "Matthew Walker", provenance="inferred", batch=["M. Walker"])
    assert concepts.remove_alias("M. Walker", base_dir=BASE)
    with pytest.raises(ValueError):
        store.merge("M. Walker", "Matthew Walker", provenance="inferred", batch=["Other"])
    with pytest.raises(ValueError):
        # Asked about it this time, but the reader separated the two: a model may not rejoin them.
        store.merge("M. Walker", "Matthew Walker", provenance="inferred", batch=["M. Walker"])
    assert concepts.aliases(base_dir=BASE) == {}, "a name the reader separated was merged back by a later run"
