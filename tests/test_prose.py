"""`prose.polish`: fixed, model-free tidying of model-written prose at the display boundary."""

from __future__ import annotations

from penumbra.prose import polish


def test_a_chinese_summary_loses_its_announcing_opening():
    assert polish("本文件為 NCA 2026 年度會議的招募通知。") == "NCA 2026 年度會議的招募通知。"
    assert polish("本文介紹成立於2006年的POC研討會，該活動…") == "成立於2006年的POC研討會，該活動…"
    assert polish("重點一。總的來說，這很重要。") == "重點一。這很重要。"
    assert polish("本文檔為 OWASP 於 2026 年發布的清單。") == "OWASP 於 2026 年發布的清單。", "whole words"
    assert polish("本文的重點是睡眠。") == "本文的重點是睡眠。", "a bare 本文 without its verb stays"


def test_an_english_opening_goes_and_the_sentence_is_capitalised_again():
    assert polish("This document describes the OWASP list. In summary, it matters.") == (
        "The OWASP list. It matters."
    )
    assert polish("iOS apps are covered.") == "iOS apps are covered.", "other sentences are left alone"


def test_dashes_become_commas_and_ranges_keep_a_hyphen():
    assert polish("研討會——成立於二〇〇六年") == "研討會，成立於二〇〇六年"
    assert polish("the list — revised yearly — is short") == "the list, revised yearly, is short"
    assert polish("from 2006–2024") == "from 2006-2024"


def test_ascii_punctuation_between_chinese_turns_full_width():
    assert polish("資安,駭客;漏洞") == "資安，駭客；漏洞"
    assert polish("OWASP, LLM") == "OWASP, LLM", "English punctuation stays"


def test_polishing_is_idempotent_and_leaves_plain_prose_alone():
    text = "睡眠鞏固記憶，午睡二十分鐘就有效。"
    assert polish(text) == text
    once = polish("本文件為測試——一段文字。")
    assert polish(once) == once
    assert polish("本文") == "本文", "an opener with nothing after it stays"


def test_a_citation_span_is_polished_like_the_prose_so_its_highlight_still_lands():
    """The span is the model pointing at its own words (invariant 49). The prose is tidied on the
    way out, so the span must be tidied the same way or the highlight disappears."""
    import pytest

    api = pytest.importorskip("penumbra.api")
    from penumbra.schema import Citation

    raw = "本文件為研討會——成立於二〇〇六年。"
    prose = api._prose(raw)
    assert prose == "研討會，成立於二〇〇六年。"
    cite = Citation(source_id="s1", locator="whole", quote="q", answer_span="研討會——成立於二〇〇六年")

    class _Corpus:
        def get(self, _):
            return None

    (response,) = api._citation_responses([cite], _Corpus(), prose)
    assert response.answer_span == "研討會，成立於二〇〇六年"

