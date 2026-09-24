"""Concept alignment's alias table (`concepts.py`) and how readers apply it."""

from __future__ import annotations

from penumbra import concepts, horizon, search, topology
from penumbra.schema import Source, SourceBlock

BASE = "h"


def _capture(url: str, entities, text="t") -> str:
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(node_id, Source(id=node_id, kind="web", origin=url,
                                          blocks=[SourceBlock(locator="whole", text=text)]), base_dir=BASE)
    horizon.update_node(node_id, base_dir=BASE, state="ready", entities=list(entities))
    return node_id


def test_unseen_names_are_the_ones_no_alignment_has_considered():
    _capture("https://x.example/a", ["Matthew Walker", "REM"])
    _capture("https://x.example/b", ["REM"])
    assert concepts.unseen(base_dir=BASE) == ["REM", "Matthew Walker"]
    concepts.mark_seen(["REM"], base_dir=BASE)
    assert concepts.unseen(base_dir=BASE) == ["Matthew Walker"]


def test_the_host_accepts_only_merges_between_real_distinct_names_and_never_a_chain():
    allowed = {"Matthew Walker", "馬修·沃克", "M. Walker", "REM"}
    got = concepts.apply_merges(
        [("馬修·沃克", "Matthew Walker"), ("REM", "REM"), ("Invented", "REM"), ("M. Walker", "馬修·沃克")],
        allowed, base_dir=BASE,
    )
    # The second pair names itself and the third an unknown name; the last points at an alias and is
    # followed to its canonical instead of forming a chain.
    assert got == [("馬修·沃克", "Matthew Walker"), ("M. Walker", "Matthew Walker")]
    assert concepts.aliases(base_dir=BASE) == {"馬修·沃克": "Matthew Walker", "M. Walker": "Matthew Walker"}
    assert concepts.apply_merges([("Matthew Walker", "REM")], allowed, base_dir=BASE) == [], (
        "a canonical that other names point at was itself merged away"
    )


def test_a_merge_changes_what_readers_see_and_nothing_stored():
    a = _capture("https://x.example/a", ["Matthew Walker"])
    b = _capture("https://x.example/b", ["馬修·沃克"])
    concepts.apply_merges([("馬修·沃克", "Matthew Walker")], {"Matthew Walker", "馬修·沃克"}, base_dir=BASE)
    graph = topology.graph(base_dir=BASE)
    assert graph["entities"] == [{"name": "Matthew Walker", "count": 2, "aliases": ["馬修·沃克"]}]
    assert horizon.get_node(b, base_dir=BASE).entities == ["馬修·沃克"], "a stored summary was rewritten"
    picked = search.select_for_ask("?", "entity", "Matthew Walker", budget_chars=10_000, max_items=5,
                                   base_dir=BASE)
    assert set(picked.node_ids) == {a, b}


def test_undoing_a_merge_restores_both_names_and_keeps_them_seen():
    _capture("https://x.example/a", ["Matthew Walker"])
    _capture("https://x.example/b", ["馬修·沃克"])
    concepts.mark_seen(["Matthew Walker", "馬修·沃克"], base_dir=BASE)
    concepts.apply_merges([("馬修·沃克", "Matthew Walker")], {"Matthew Walker", "馬修·沃克"}, base_dir=BASE)
    assert concepts.remove_alias("馬修·沃克", base_dir=BASE)
    names = {e["name"] for e in topology.graph(base_dir=BASE)["entities"]}
    assert names == {"Matthew Walker", "馬修·沃克"}
    assert concepts.unseen(base_dir=BASE) == [], "an undone merge would simply be proposed again"



def test_a_batch_cannot_leave_a_chain_behind():
    allowed = {"M. Walker", "Walker", "Matthew Walker"}
    concepts.apply_merges([("M. Walker", "Walker"), ("Walker", "Matthew Walker")], allowed, base_dir=BASE)
    table = concepts.aliases(base_dir=BASE)
    assert all(canonical not in table for canonical in table.values()), f"a chain: {table}"


def test_only_a_name_the_run_was_asked_about_becomes_an_alias():
    allowed = {"M. Walker", "Matthew Walker"}
    concepts.apply_merges([("M. Walker", "Matthew Walker")], allowed, base_dir=BASE)
    concepts.remove_alias("M. Walker", base_dir=BASE)
    again = concepts.apply_merges([("M. Walker", "Matthew Walker")], allowed, batch={"Other"}, base_dir=BASE)
    assert again == [], "a name the reader separated was merged back by a later run"
