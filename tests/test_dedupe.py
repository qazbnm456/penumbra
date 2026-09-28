"""Knowing a capture is already in the Horizon (`dedupe.py`): an address that differs only by what
tracks, and a page captured again after it changed a little."""

from __future__ import annotations

from penumbra import dedupe


def test_an_address_loses_only_what_tracks():
    n = dedupe.normalize_url
    assert n("https://www.example.com/a/?utm_source=x&utm_medium=y&id=7#top") == "https://example.com/a?id=7"
    assert n("https://twitter.com/user/status/1?s=20&t=abc") == "https://x.com/user/status/1"
    assert n("https://example.com/a?fbclid=123") == n("http://example.com/a")
    assert n("https://www.youtube.com/watch?v=abc&si=track") == "https://www.youtube.com/watch?v=abc"
    assert n("https://example.com/s?q=sleep") == "https://example.com/s?q=sleep", "a search keeps its query"
    passage = "https://example.com/p#:~:text=Sleep"
    assert n(passage) == passage, "a passage keeps its fragment"
    assert n("not a url") == "not a url"


def test_a_page_that_changed_by_a_number_resembles_itself_and_another_does_not():
    post = "Introducing Prime Sandboxes: MicroVM sandboxes purpose-built for agents. " * 6
    changed = dedupe.resemblance(post + "3 minutes ago · 120 likes", post + "5 minutes ago · 121 likes")
    assert changed >= dedupe.NEAR_DUPLICATE
    other = "Sleep consolidates memory by replaying the day during slow-wave sleep. " * 6
    assert dedupe.resemblance(post, other) < 0.2
    zh = "研究發現，慢波睡眠期間海馬迴會重播白天的經驗，把短期記憶轉存到大腦皮質。" * 4
    assert dedupe.resemblance(zh + "三分鐘前", zh + "五分鐘前") >= dedupe.NEAR_DUPLICATE
