"""The Horizon's full-text index and the selection a Horizon ask reads (`search.py`).

Offline and model-free: nodes are written straight into a temporary Horizon.
"""

from __future__ import annotations

import sqlite3

import pytest

from penumbra import horizon, search
from penumbra.schema import Source, SourceBlock

BASE = "h"


def _capture(url: str, text: str, *, tags=(), entities=(), title=None) -> str:
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(
        node_id,
        Source(id=node_id, kind="web", origin=url, blocks=[SourceBlock(locator="whole", text=text)]),
        base_dir=BASE,
    )
    fields = {"tags": list(tags), "entities": list(entities)}
    if title:
        fields["title"] = title
    horizon.update_node(node_id, base_dir=BASE, **fields)
    return node_id


def test_grams_pairs_unspaced_runs_and_leaves_latin_alone():
    assert search.grams("海馬迴").split() == ["海馬", "馬迴"]
    assert search.grams("記").split() == ["記"]
    assert search.grams("REM 睡眠").split() == ["REM", "睡眠"]
    # NFKC: a full-width PDF is the same word as a half-width one.
    assert search.grams("ＰＤＦ").split() == ["PDF"]


def test_query_terms_are_distinct_and_drop_single_latin_letters():
    assert search.query_terms("a memory, memory 記憶") == ["memory", "記憶"]


def test_match_expression_quotes_every_term_so_nothing_is_read_as_syntax():
    assert search.match_expression(['a"b', "OR"]) == '"a""b" OR "OR"'


def test_a_two_character_chinese_word_is_found():
    """The failure that ruled out FTS5's trigram tokenizer: most Chinese words are two characters."""
    a = _capture("https://x.example/a", "睡眠紡錘波與記憶鞏固的關係")
    _capture("https://x.example/b", "Rust ownership and borrowing")
    assert search.search("關係", base_dir=BASE) == [a]


def test_a_term_a_dictionary_segmenter_cut_wrongly_is_found():
    """jieba cut 海馬迴 into 海馬 / 迴在 with every dictionary tried, so a search for it missed."""
    b = _capture("https://x.example/b", "這篇論文討論海馬迴在空間記憶裡扮演的角色")
    _capture("https://x.example/c", "海邊的馬")
    assert search.search("海馬迴", base_dir=BASE)[0] == b


def test_a_natural_question_ranks_the_document_that_matches_more_of_it_first():
    a = _capture("https://x.example/a", "睡眠紡錘波與記憶鞏固的關係")
    b = _capture("https://x.example/b", "空間記憶")
    assert search.search("睡眠和記憶有什麼關係？", base_dir=BASE) == [a, b]


def test_the_description_counts_for_more_than_the_body():
    body_only = _capture("https://x.example/a", "a long text that mentions caffeine once")
    described = _capture("https://x.example/b", "unrelated body", tags=["caffeine"])
    assert search.search("caffeine", base_dir=BASE) == [described, body_only]


def test_an_edit_is_picked_up_by_the_next_search():
    node = _capture("https://x.example/a", "plain text")
    assert search.search("serotonin", base_dir=BASE) == []
    horizon.update_node(node, base_dir=BASE, summary="about serotonin")
    assert search.search("serotonin", base_dir=BASE) == [node]


def test_a_summarised_node_is_searchable():
    """Summarising moves a node to `ready`. A hand-written state list once said `distilled`, a state
    that does not exist, and every summarised capture dropped out of search."""
    node = _capture("https://x.example/a", "hippocampus")
    horizon.update_node(node, base_dir=BASE, state="ready", summary="memory")
    assert search.search("hippocampus", base_dir=BASE) == [node]
    assert search.select_for_ask("memory", budget_chars=10_000, max_items=5, base_dir=BASE).node_ids == [node]


def test_every_state_with_text_on_disk_is_searchable():
    assert set(search.SEARCHABLE_STATES) == {"ready_undistilled", "distilling", "ready"}


def test_sync_is_idempotent():
    _capture("https://x.example/a", "one")
    assert search.sync(base_dir=BASE) == 1
    assert search.sync(base_dir=BASE) == 0


def test_removing_a_node_removes_its_index_row():
    node = _capture("https://x.example/a", "hippocampus")
    assert search.search("hippocampus", base_dir=BASE) == [node]
    horizon.remove_node(node, base_dir=BASE)
    conn = sqlite3.connect(horizon.index_path(BASE))
    try:
        assert conn.execute("SELECT COUNT(*) FROM search_rows").fetchone()[0] == 0
        left = conn.execute("SELECT rowid FROM search_fts WHERE search_fts MATCH 'hippocampus'").fetchall()
        assert left == []
    finally:
        conn.close()


def test_a_node_without_readable_text_is_not_searchable():
    horizon.add_pending_node("https://x.example/q", "web", base_dir=BASE)
    assert search.sync(base_dir=BASE) == 0


def test_an_unreadable_blocks_file_still_indexes_the_description():
    node = _capture("https://x.example/a", "body", title="Mitochondria notes")
    horizon.node_blocks_path(node, base_dir=BASE).write_text("{not json", encoding="utf-8")
    horizon.update_node(node, base_dir=BASE, summary="energy")
    assert search.search("mitochondria", base_dir=BASE) == [node]


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
    conn = sqlite3.connect(horizon.index_path(BASE))
    conn.execute("UPDATE nodes SET tags = '{broken' WHERE id = ?", (bad,))
    conn.commit()
    conn.close()
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
    _capture("https://x.example/a", "x", tags=["t" * (search.SCOPE_VALUE_MAX + 1), "ok"])
    assert [row["name"] for row in search.concepts(base_dir=BASE)["tags"]] == ["ok"]
