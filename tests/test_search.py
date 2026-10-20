"""The Horizon's full-text index and the selection a Horizon ask reads (`search.py`).

Offline and model-free: nodes are written straight into a temporary Horizon.
"""

from __future__ import annotations

import json
import sqlite3
import time

import pytest

from penumbra import horizon, memory_store, search
from penumbra.schema import Source, SourceBlock
from tests._labels import label

BASE = "h"


def _capture(url: str, text: str, *, tags=(), entities=(), title=None) -> str:
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(
        node_id,
        Source(id=node_id, kind="web", origin=url, blocks=[SourceBlock(locator="whole", text=text)]),
        base_dir=BASE,
    )
    # Stored, the capture carries its kit item id; the temporary id is only its `former_id`.
    node_id = horizon.resolve_id(node_id, base_dir=BASE)
    fields = {"tags": list(tags), "entities": list(entities)}
    if title:
        fields["title"] = title
    label(node_id, base_dir=BASE, state=None, **{k: v for k, v in fields.items() if v})
    return node_id


def _raw_tags(node_id: str, value_json: str) -> None:
    """A tags label row written straight into the kit's memory store, past its validation: labels
    are append-only, so the newest row is the current one."""
    conn = sqlite3.connect(memory_store.store_path(BASE))
    try:
        conn.execute(
            "INSERT INTO labels (item_id, kind, value_json, provenance, run_id, created_at) "
            "VALUES (?, 'tags', ?, 'inferred', NULL, ?)",
            (int(node_id[1:]), value_json, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def _found(question: str) -> list[str]:
    """The captures an ask over everything would read, in order, with room for all of them."""
    return search.select_for_ask(question, budget_chars=10_000_000, max_items=100, base_dir=BASE).node_ids


def _matched(question: str) -> list[str]:
    """Only the captures the question's words found, best first."""
    picked = search.select_for_ask(question, budget_chars=10_000_000, max_items=100, base_dir=BASE)
    return [p.node_id for p in picked.items if p.matched]


def test_a_two_character_chinese_word_is_found():
    """The failure that ruled out FTS5's trigram tokenizer: most Chinese words are two characters."""
    a = _capture("https://x.example/a", "睡眠紡錘波與記憶鞏固的關係")
    _capture("https://x.example/b", "Rust ownership and borrowing")
    assert _matched("關係") == [a]


def test_a_term_a_dictionary_segmenter_cut_wrongly_is_found():
    """jieba cut 海馬迴 into 海馬 / 迴在 with every dictionary tried, so a search for it missed."""
    b = _capture("https://x.example/b", "這篇論文討論海馬迴在空間記憶裡扮演的角色")
    _capture("https://x.example/c", "海邊的馬")
    assert _matched("海馬迴")[0] == b


def test_a_natural_question_ranks_the_document_that_matches_more_of_it_first():
    a = _capture("https://x.example/a", "睡眠紡錘波與記憶鞏固的關係")
    b = _capture("https://x.example/b", "空間記憶")
    assert _matched("睡眠和記憶有什麼關係？") == [a, b]


def test_a_label_counts_for_more_than_the_body():
    body_only = _capture("https://x.example/a", "a long text that mentions caffeine once")
    described = _capture("https://x.example/b", "unrelated body", tags=["caffeine"])
    assert _matched("caffeine") == [described, body_only]


def test_an_edit_is_picked_up_by_the_next_ask():
    node = _capture("https://x.example/a", "plain text")
    assert _matched("serotonin") == []
    label(node, base_dir=BASE, state=None, summary="about serotonin")
    assert _matched("serotonin") == [node]


def test_a_readers_title_is_found():
    node = _capture("https://x.example/a", "plain text")
    horizon.edit_node(node, title="Mitochondria notes", base_dir=BASE)
    assert _matched("mitochondria") == [node]


def test_a_summarised_node_is_searchable():
    """Summarising moves a node to `ready`. A hand-written state list once said `distilled`, a state
    that does not exist, and every summarised capture dropped out of search."""
    node = _capture("https://x.example/a", "hippocampus")
    label(node, base_dir=BASE, summary="memory")
    assert _matched("hippocampus") == [node]
    assert search.select_for_ask("memory", budget_chars=10_000, max_items=5, base_dir=BASE).node_ids == [node]


def test_every_state_with_text_on_disk_is_searchable():
    assert set(search.SEARCHABLE_STATES) == {"ready_undistilled", "distilling", "ready"}


def test_a_removed_capture_is_never_selected():
    node = _capture("https://x.example/a", "hippocampus")
    assert _matched("hippocampus") == [node]
    horizon.remove_node(node, base_dir=BASE)
    assert _found("hippocampus") == []


def test_a_capture_without_an_item_is_never_selected(monkeypatch):
    """A capture still being read, or one whose text is stored but is not an item, has no place in
    the kit's index and is outside the readable states."""
    horizon.add_pending_node("https://x.example/q", "web", base_dir=BASE)

    def busy(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(memory_store.store(BASE), "add", busy)
    url = "https://x.example/waiting"
    temp = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(
        temp, Source(id=temp, kind="web", origin=url, blocks=[SourceBlock(locator="whole", text="anything")]),
        base_dir=BASE,
    )
    waiting = horizon.get_node(temp, base_dir=BASE)
    # Its text is on disk, but the kit refused it, so it keeps its temporary id and is no item.
    assert waiting.id == temp and horizon.node_blocks_path(temp, base_dir=BASE).is_file()
    assert _found("anything") == []


def test_an_origin_is_found():
    """A URL is often the one word a reader remembers (`memory_store` indexes origins)."""
    node = _capture("https://penguins.example/a", "plain text")
    assert _matched("penguins") == [node]


# --- select_for_ask ---------------------------------------------------------------------------


def test_a_scope_that_fits_is_read_whole_with_matches_first():
    a = _capture("https://x.example/a", "sleep and memory", tags=["sleep"])
    b = _capture("https://x.example/b", "dreams", tags=["sleep"])
    _capture("https://x.example/c", "coffee", tags=["coffee"])
    picked = search.select_for_ask("dreams", "tag", "sleep", budget_chars=10_000, max_items=10, base_dir=BASE)
    assert picked.strategy == "all"
    assert picked.in_scope == 2
    assert picked.node_ids == [b, a]


def test_an_entity_scope_matches_the_entity_list_exactly():
    a = _capture("https://x.example/a", "x", entities=["Matthew Walker"])
    _capture("https://x.example/b", "y", entities=["Matthew"])
    picked = search.select_for_ask("?", "entity", "Matthew Walker", budget_chars=10_000, max_items=10,
                                   base_dir=BASE)
    assert picked.node_ids == [a]


def test_a_large_scope_reads_only_what_the_question_found():
    a = _capture("https://x.example/a", "caffeine half life " + "x" * 400)
    _capture("https://x.example/b", "unrelated " + "y" * 400)
    picked = search.select_for_ask("caffeine", budget_chars=500, max_items=10, base_dir=BASE)
    assert picked.strategy == "matched"
    assert picked.node_ids == [a]


def test_a_question_that_matches_nothing_falls_back_to_the_newest_and_says_so():
    _capture("https://x.example/a", "x" * 400)
    newest = _capture("https://x.example/b", "y" * 400)
    picked = search.select_for_ask("zebra", budget_chars=500, max_items=10, base_dir=BASE)
    assert picked.strategy == "recent"
    assert picked.node_ids == [newest]


def test_the_item_cap_holds():
    for i in range(5):
        _capture(f"https://x.example/{i}", "same words")
    picked = search.select_for_ask("same", budget_chars=10_000, max_items=3, base_dir=BASE)
    assert len(picked.items) == 3
    assert picked.in_scope == 5


def test_a_capture_larger_than_the_whole_budget_is_reported_not_silently_dropped():
    big = _capture("https://x.example/big", "caffeine " + "z" * 2000)
    small = _capture("https://x.example/small", "caffeine")
    picked = search.select_for_ask("caffeine", budget_chars=500, max_items=10, base_dir=BASE)
    assert picked.node_ids == [small]
    assert [p.node_id for p in picked.too_large] == [big]


def test_an_unknown_scope_is_refused():
    with pytest.raises(ValueError):
        search.select_for_ask("x", "orbit", "a", budget_chars=10, max_items=1, base_dir=BASE)
    with pytest.raises(ValueError):
        search.select_for_ask("x", "tag", None, budget_chars=10, max_items=1, base_dir=BASE)


def test_a_malformed_tag_column_does_not_break_a_tag_scope_or_the_concept_list():
    good = _capture("https://x.example/a", "x", tags=["sleep"])
    bad = _capture("https://x.example/b", "y")
    # Tags are a label row in the kit's memory store now, which refuses a malformed value outright
    # (a CHECK and a trigger), so none can reach the scope or the concept list.
    for malformed in ("{broken", '{"x": "sleep"}', '[7, null, {"x": "sleep"}]'):
        with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
            _raw_tags(bad, malformed)
    picked = search.select_for_ask("x", "tag", "sleep", budget_chars=10_000, max_items=10, base_dir=BASE)
    assert picked.node_ids == [good]
    assert search.concepts(base_dir=BASE)["tags"] == [{"name": "sleep", "count": 1}]


def test_concepts_count_tags_and_entities_most_used_first():
    _capture("https://x.example/a", "x", tags=["sleep", "memory"], entities=["REM"])
    _capture("https://x.example/b", "y", tags=["sleep"])
    found = search.concepts(base_dir=BASE)
    assert found["tags"] == [{"name": "sleep", "count": 2}, {"name": "memory", "count": 1}]
    assert found["entities"] == [{"name": "REM", "count": 1}]


def test_a_scope_is_ranked_inside_the_query_not_after_a_global_cut():
    """With the scope applied after the top hits, many better matches outside a tag left nothing
    inside it, and the ask fell back to the newest while saying the words found nothing."""
    for i in range(30):
        _capture(f"https://x.example/out{i}", "sleep memory memory memory")
    inside = _capture("https://x.example/in", "memory", tags=["t1"])
    _capture("https://x.example/in2", "unrelated", tags=["t1"])
    picked = search.select_for_ask("memory", "tag", "t1", budget_chars=100, max_items=5, base_dir=BASE)
    assert picked.strategy == "matched"
    assert picked.node_ids == [inside]


def test_when_every_match_is_too_large_the_newest_that_fit_are_read():
    big = _capture("https://x.example/big", "hippocampus " + "z" * 2000)
    small = _capture("https://x.example/small", "notes")
    picked = search.select_for_ask("hippocampus", budget_chars=500, max_items=5, base_dir=BASE)
    assert picked.strategy == "recent"
    assert picked.node_ids == [small]
    assert [p.node_id for p in picked.too_large] == [big]


def test_concepts_never_offer_a_value_a_scope_would_refuse():
    # The kit caps a tag at 40 characters, so only a row written past it (an older store, a
    # hand-edit) can carry one this long; the concept list must still not offer it.
    node = _capture("https://x.example/a", "x")
    _raw_tags(node, json.dumps(["t" * (search.SCOPE_VALUE_MAX + 1), "ok"]))
    assert [row["name"] for row in search.concepts(base_dir=BASE)["tags"]] == ["ok"]


def test_an_empty_question_matches_nothing():
    """The kit lists every item for an empty query; an ask must not call that a match."""
    _capture("https://x.example/a", "hippocampus")
    picked = search.select_for_ask("   ", budget_chars=10_000, max_items=5, base_dir=BASE)
    assert picked.strategy == "all" and not any(p.matched for p in picked.items)
