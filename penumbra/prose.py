"""Model-written prose, tidied at the display boundary by fixed rules: no model, no tokens.

A model writing Chinese or English falls into the same few habits whatever it is told: an opening
that announces the document ("本文件為", "This document describes"), a closing that announces a
conclusion ("總的來說", "In summary,"), dashes where a comma belongs, and ASCII punctuation between
Chinese characters. The summary prompt already forbids "This document"-style preambles, and a real
Chinese summary still began "本文件為", so the prompt alone does not hold.

`polish` removes only those fixed shapes and never rewrites a sentence. It runs where invariant 62
strips `[[SRC:...]]` markers, on the way OUT: what is stored is what the model wrote, so every
orbit and capture already on disk reads the tidied way with no migration, and a rule can be
changed or withdrawn without touching data. A citation's `answer_span` is polished the same way
before it is located (`api._citation_responses`), so a highlight still lands on the words it
marks; a span that no longer matches loses only its highlight, never lands on the wrong words.

What it cannot do is the judgement a writer (or a model) brings: it cuts stock phrases, it does not
make prose better.
"""

from __future__ import annotations

import re

_CJK = r"⺀-鿿가-힯＀-￯"

#: Openings and signposts that say nothing, at the start of the text or of a sentence. Each is
#: removed with the punctuation that follows it; the sentence it introduced keeps everything else.
#: Longer phrases come first, and a bare "本文" counts only with the verb that makes it an opening:
#: without that, "本文檔為…" lost "本文" and read "檔為…", half a word.
_ZH_OPENERS = (
    r"本文(?:件|檔)(?:為|是)?",
    r"這份(?:文件|文檔)(?:為|是)?",
    r"本篇(?:文章|文件)?(?:為|是|主要)?(?:介紹了?|探討了?|說明了?)?",
    r"本文(?:主要)?(?:介紹了?|探討了?|說明了?|描述了?|討論了?)",
    r"總的來說",
    r"總而言之",
    r"綜上所述",
    r"簡而言之",
    r"值得注意的是",
    r"需要注意的是",
)
_EN_OPENERS = (
    (r"This (?:document|article|page|text|source) "
     r"(?:describes|discusses|explains|covers|presents|outlines|is about) "),
    r"In (?:summary|conclusion|short), ",
    r"Overall, ",
    r"It is worth noting that ",
    r"Notably, ",
)

_SENTENCE_START = r"(?:^|(?<=[\n。！？]))[ \t]*"
_ZH_OPENER_RE = re.compile(rf"{_SENTENCE_START}(?:{'|'.join(_ZH_OPENERS)})[，,：:]?[ \t]*")
_EN_OPENER_RE = re.compile(rf"(?:^|(?<=[\n.!?] ))(?:{'|'.join(_EN_OPENERS)})")


def _drop_zh_openers(text: str) -> str:
    def cut(match: re.Match[str]) -> str:
        rest = text[match.end():match.end() + 1]
        # Only when something follows to carry the sentence: "本文" alone, or a phrase at the very
        # end, is left as written.
        return "" if rest and rest not in "。！？\n" else match.group(0)

    return _ZH_OPENER_RE.sub(cut, text)


def _drop_en_openers(text: str) -> str:
    # Right to left, so earlier offsets stay valid; the sentence that lost its opener, and only
    # that one, starts with a capital again.
    for match in reversed(list(_EN_OPENER_RE.finditer(text))):
        after = text[match.end():match.end() + 1]
        if after.isalpha():
            text = text[:match.start()] + after.upper() + text[match.end() + 1:]
    return text


def _no_dashes(text: str) -> str:
    # A number range keeps a plain hyphen: 2006–2024.
    text = re.sub(r"(\d)\s*[–—]\s*(\d)", r"\1-\2", text)
    # Between Chinese, a dash (or the doubled ——) is a pause: a full-width comma.
    text = re.sub(rf"(?<=[{_CJK}])\s*[—–]{{1,2}}\s*|\s*[—–]{{1,2}}\s*(?=[{_CJK}])", "，", text)
    # In English, a spaced or tight em dash between words is a comma.
    text = re.sub(r"\s+[—–]\s+|(?<=\w)—(?=\w)", ", ", text)
    return text


def _cjk_punctuation(text: str) -> str:
    """ASCII punctuation between two Chinese characters becomes its full-width form."""
    table = {",": "，", ";": "；", ":": "：", "?": "？", "!": "！"}
    return re.sub(rf"(?<=[{_CJK}])([,;:?!])(?=[{_CJK}])", lambda m: table[m.group(1)], text)


def polish(text: str) -> str:
    """`text` with the fixed habits removed. Idempotent: polishing twice changes nothing more."""
    if not text:
        return text or ""
    out = _no_dashes(text)
    out = _cjk_punctuation(out)
    out = _drop_zh_openers(out)
    out = _drop_en_openers(out)
    return out.strip()
