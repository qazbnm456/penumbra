"""Everything the reader has made, as one zip they can keep or take to another tool.

The package has a lossless half and a readable half, side by side:

- `data/` is canonical: every capture with its stored text, every orbit file exactly as stored, the
  alias table, removal records and Horizon asks. It is what a later restore would read, and nothing
  else in the zip is meant to be parsed back.
- `media/` holds the generated audio, one file per orbit.
- `markdown/` is a folder of notes that Obsidian opens as a vault, and that Logseq, Capacities,
  Heptabase, Bear, Notion, Apple Notes and NotebookLM can import: one note per capture, per orbit
  (with its conversation) and per entity, linked with wikilinks.
- `bookmarks.html` is the Netscape bookmark file every browser and read-later app imports.
- `manifest.json` names the format, its version and the SHA-256 of every file.

Model-written prose is tidied and stripped of corpus markers on the way out, as it is on screen
(invariant 62); the stored files under `data/` are copied as they are.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from . import __version__, asks, concepts, horizon
from .citations import strip_markers
from .horizon import DEFAULT_HORIZON_DIR
from .orbit import DEFAULT_ORBITS_DIR, find_audio, list_orbit_summaries, orbit_path
from .prose import polish

FORMAT = "penumbra-export"
#: Bumped when a file under `data/` changes shape; a restore refuses a major version it does not know.
SCHEMA_VERSION = 1
_PAGE = 500
_NAME_CHARS = 80

#: The words the Markdown notes and the README are written in, following the reader's interface
#: language: a vault read in Chinese should not be headed in English.
_LABELS = {
    "en": {"text": "Text", "notes": "Notes", "sources": "Sources", "conversation": "Conversation",
           "overview": "Overview", "audio": "Audio overview", "named_by": "Named by:",
           "audio_file": "in this export", "horizon": "Horizon"},
    "zh": {"text": "內容", "notes": "筆記", "sources": "來源", "conversation": "對話",
           "overview": "概覽", "audio": "語音概覽", "named_by": "提到它的收錄：",
           "audio_file": "（在這份匯出裡）", "horizon": "視界"},
}

_README_ZH = """# Penumbra 匯出

匯出時 Penumbra 保存的一切：{captures} 則收錄、{orbits} 個軌道。

- `markdown/` 可以直接用 Obsidian 打開，也能匯入 Logseq、Capacities、Heptabase、Bear、Notion、Apple Notes
  或 NotebookLM。`Captures/` 每則收錄一篇筆記，含摘要和全文；
  `Orbits/` 每個軌道一篇，含概覽、筆記、來源和對話；
  `Entities/` 每個被提到的人、地方或概念一篇，列出它的其他名稱。
- `bookmarks.html` 可以匯入任何瀏覽器或稍後閱讀工具（Raindrop、Pocket、Readwise Reader）。
- `data/` 是完整紀錄（JSON），日後還原就讀這裡；`media/` 是語音概覽。
- `manifest.json` 記錄格式版本和每個檔案的 SHA-256。

引用在產生時檢查過它指向的位置確實存在於來源中；這只代表位置存在，不代表引文忠於原文。
"""

_README = """# Penumbra export

Everything this Penumbra held when it was exported: {captures} captures and {orbits} orbits.

- `markdown/` opens as an Obsidian vault, and imports into Logseq, Capacities, Heptabase, Bear, Notion,
  Apple Notes or NotebookLM. `Captures/` holds one note per capture with its summary and full text,
  `Orbits/` one note per orbit with its overview, notes, sources and conversation, and `Entities/` one
  note per named person, place or idea, with the other names it goes by.
- `bookmarks.html` imports into any browser or read-later app (Raindrop, Pocket, Readwise Reader).
- `data/` is the complete record, in JSON: what a restore reads. `media/` holds the audio overviews.
- `manifest.json` gives the format version and a SHA-256 for every file.

A citation's place in its source was checked to exist when it was made. That check says the place is
there, not that the quoted words are faithful to it.
"""


def _iso(seconds: float | None) -> str:
    if not seconds:
        return ""
    return datetime.fromtimestamp(seconds, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(text: str | None) -> str:
    """Model prose as the screen shows it: markers stripped, habits tidied."""
    return polish(strip_markers(text or ""))


def _safe(name: str, fallback: str) -> str:
    """A filename (and wikilink) part: no path separators or characters links treat specially."""
    cleaned = re.sub(r'[\\/:*?"<>|#^\[\]\x00-\x1f]+', " ", name or "")
    cleaned = " ".join(cleaned.split()).strip(" .")[:_NAME_CHARS].strip(" .")
    return cleaned or fallback


def _heading(locator: str) -> str:
    """A block's locator as a heading a wikilink can point at (`#`, `:` and `|` break links)."""
    return _safe(locator.replace(":", " "), "text")


def _yaml(value) -> str:
    """A YAML scalar or flow list, quoted as JSON (JSON strings are valid YAML)."""
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def _frontmatter(fields: dict) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value in (None, "", []):
            continue
        lines.append(f"{key}: {_yaml(value)}")
    lines.append("---\n")
    return "\n".join(lines)


def _blocks_markdown(source) -> str:
    parts = []
    for block in source.blocks:
        parts.append(f"### {_heading(block.locator)}\n\n{block.text.strip()}\n")
    return "\n".join(parts)


class _Zip:
    """A zip that remembers each file's hash for the manifest."""

    def __init__(self, target: Path):
        self.zf = zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED)
        self.hashes: dict[str, str] = {}

    def put(self, path: str, data: bytes | str) -> None:
        raw = data.encode("utf-8") if isinstance(data, str) else data
        self.hashes[path] = hashlib.sha256(raw).hexdigest()
        self.zf.writestr(path, raw)

    def put_file(self, path: str, source: Path) -> None:
        digest = hashlib.sha256()
        with source.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        self.hashes[path] = digest.hexdigest()
        self.zf.write(source, path)

    def close(self) -> None:
        self.zf.close()


def _all_nodes(base_dir) -> list:
    nodes, offset = [], 0
    while True:
        page = horizon.list_nodes(limit=_PAGE, offset=offset, sort="oldest", base_dir=base_dir)
        nodes.extend(page)
        if len(page) < _PAGE:
            return nodes
        offset += _PAGE


def _all_asks(base_dir) -> list:
    found, offset = [], 0
    while True:
        page = asks.list_asks(limit=_PAGE, offset=offset, base_dir=base_dir)
        found.extend(page)
        if len(page) < _PAGE:
            return found
        offset += _PAGE


def labels_for(language: str | None) -> str:
    """`zh` for a Chinese interface, `en` otherwise."""
    text = (language or "").lower()
    return "zh" if ("chinese" in text or "中文" in text or text.startswith("zh")) else "en"


def write_export(
    target: Path,
    *,
    orbits_dir: str | Path = DEFAULT_ORBITS_DIR,
    horizon_dir: str | Path = DEFAULT_HORIZON_DIR,
    language: str | None = None,
) -> dict:
    """Write the whole package to `target` and return its counts. `language` is the reader's
    interface language, which the notes' headings and the README follow."""
    out = _Zip(Path(target))
    try:
        counts = _write(out, Path(orbits_dir), Path(horizon_dir), _LABELS[labels_for(language)],
                        labels_for(language))
        manifest = {
            "format": FORMAT,
            "schema_version": SCHEMA_VERSION,
            "app_version": __version__,
            "exported_at": _iso(time.time()),
            "counts": counts,
            "files": dict(sorted(out.hashes.items())),
        }
        out.put("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    finally:
        out.close()
    return counts


def _write(out: _Zip, orbits_dir: Path, horizon_dir: Path, words: dict, lang: str) -> dict:
    nodes = _all_nodes(horizon_dir)
    by_id = {n.id: n for n in nodes}
    members = horizon.memberships_for_nodes(list(by_id), base_dir=horizon_dir) if by_id else {}
    orbits, unreadable = list_orbit_summaries(base_dir=orbits_dir)
    orbit_titles = {o.id: (o.title or (o.sources[0].preview.get("title") if o.sources else "") or o.id)
                    for o in orbits}
    orbit_notes = {o.id: f"{_safe(orbit_titles[o.id], 'Orbit')}--{_safe(o.id, 'orbit')}" for o in orbits}
    slug_to_id = {}
    for o in orbits:
        slug_to_id[orbit_path(o.id, base_dir=orbits_dir).stem] = o.id
    capture_notes = {n.id: f"{_safe(_clean(n.title) or n.preview.get('title', ''), 'Capture')}--{n.id[-6:]}"
                     for n in nodes}
    resolve = concepts.resolver(base_dir=horizon_dir)
    alias_table = concepts.aliases(base_dir=horizon_dir)

    # --- data/: the lossless half -------------------------------------------------------------
    lines = []
    for node in nodes:
        record = node.model_dump()
        record["orbits"] = [m.model_dump() for m in members.get(node.id, [])]
        lines.append(json.dumps(record, ensure_ascii=False))
    out.put("data/captures.jsonl", "\n".join(lines) + ("\n" if lines else ""))
    sources = {}
    for node in nodes:
        path = horizon.node_blocks_path(node.id, base_dir=horizon_dir)
        if path.exists():
            out.put_file(f"data/blocks/{node.id}.json", path)
            try:
                sources[node.id] = horizon.node_source(node.id, base_dir=horizon_dir)
            except Exception:  # noqa: BLE001 - an unreadable text file is still copied as it is
                sources[node.id] = None
    for o in orbits:
        path = orbit_path(o.id, base_dir=orbits_dir)
        out.put_file(f"data/orbits/{path.name}", path)
        audio = find_audio(o.id, base_dir=orbits_dir)
        if audio is not None:
            out.put_file(f"media/audio/{path.stem}{audio.suffix}", audio)
    for stem in unreadable:
        path = orbits_dir / f"{stem}.json"
        if path.exists():
            out.put_file(f"data/orbits/unreadable/{path.name}", path)
    out.put("data/concepts.json", json.dumps(alias_table, ensure_ascii=False, indent=2))
    removals = horizon.removal_events(limit=horizon.MAX_REMOVAL_EVENTS, base_dir=horizon_dir)
    out.put("data/removals.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in removals))
    ask_list = _all_asks(horizon_dir)
    out.put("data/asks.jsonl", "".join(a.model_dump_json() + "\n" for a in ask_list))

    # --- markdown/: the readable half ---------------------------------------------------------
    entity_captures: dict[str, list[str]] = {}
    for node in nodes:
        names = sorted({resolve(e) for e in node.entities})
        for name in names:
            entity_captures.setdefault(name, []).append(node.id)
        filed = [o_id for o_id in (slug_to_id.get(m.orbit_id, m.orbit_id) for m in members.get(node.id, []))
                 if o_id in orbit_notes]
        head = _frontmatter({
            "id": node.id,
            "type": "capture",
            "title": _clean(node.title) or node.preview.get("title", ""),
            "source": node.origin if node.origin.startswith(("http://", "https://")) else "",
            "kind": node.kind,
            "created": _iso(node.created_at),
            "tags": list(node.tags),
            "entities": [f"[[{_safe(n, 'Entity')}]]" for n in names],
            "orbits": [f"[[{orbit_notes[o]}]]" for o in filed],
        })
        body = [f"# {_clean(node.title) or node.preview.get('title') or node.origin}\n"]
        if node.summary:
            body.append(_clean(node.summary) + "\n")
        source = sources.get(node.id)
        if source is not None and source.blocks:
            body.append(f"## {words['text']}\n\n" + _blocks_markdown(source))
        out.put(f"markdown/Captures/{capture_notes[node.id]}.md", head + "\n".join(body))

    also = {}
    for alias, canonical in alias_table.items():
        also.setdefault(canonical, []).append(alias)
    for name, ids in sorted(entity_captures.items()):
        head = _frontmatter({"type": "entity", "aliases": sorted(also.get(name, []))})
        links = "\n".join(f"- [[{capture_notes[i]}]]" for i in ids)
        out.put(f"markdown/Entities/{_safe(name, 'Entity')}.md",
                f"{head}# {name}\n\n{words['named_by']}\n\n{links}\n")

    for o in orbits:
        stem = orbit_path(o.id, base_dir=orbits_dir).stem
        _orbit_markdown(out, o, orbit_notes[o.id], orbit_titles[o.id], stem,
                        horizon_dir, capture_notes, find_audio(o.id, base_dir=orbits_dir), words)

    # --- bookmarks.html ------------------------------------------------------------------------
    out.put("bookmarks.html", _bookmarks(nodes, members, orbit_titles, slug_to_id, words["horizon"]))

    counts = {
        "captures": len(nodes),
        "orbits": len(orbits) + len(unreadable),
        "entities": len(entity_captures),
        "asks": len(ask_list),
        "removals": len(removals),
    }
    out.put("README.md", (_README_ZH if lang == "zh" else _README).format(**counts))
    return counts


def _answer_markdown(text: str, citations, target_for, prefix: str) -> str:
    """An answer's prose, then its citations as footnotes pointing at the source's heading."""
    lines = [_clean(text)]
    notes = []
    seen: dict[tuple[str, str], int] = {}
    for citation in citations:
        key = (citation.source_id, citation.locator)
        if key in seen:
            continue
        seen[key] = len(seen) + 1
        n = seen[key]
        target = target_for(citation.source_id)
        where = f"[[{target}#{_heading(citation.locator)}]]" if target else citation.source_id
        quote = " ".join((citation.quote or "").split())
        notes.append(f"[^{prefix}{n}]: “{quote}” {where}")
    if notes:
        # The references close the prose they back, rather than standing on a line of their own.
        lines[0] = lines[0] + "".join(f"[^{prefix}{i}]" for i in range(1, len(notes) + 1))
        lines.append("\n".join(notes))
    return "\n\n".join(lines) + "\n"


def _orbit_markdown(out: _Zip, orbit, note: str, title: str, slug_stem: str, horizon_dir,
                    capture_notes: dict, audio: Path | None, words: dict) -> None:
    from_capture = {m.source_id: m.node_id for m in horizon.nodes_in_orbit(slug_stem, base_dir=horizon_dir)}
    source_notes = {}
    for source in orbit.sources:
        node_id = from_capture.get(source.id)
        if node_id in capture_notes:
            source_notes[source.id] = capture_notes[node_id]
        else:
            label = _safe(source.preview.get("title") or source.origin, "Source")
            source_notes[source.id] = f"{note}/Sources/{source.id} {label}"
            head = _frontmatter({"type": "source", "orbit": f"[[{note}]]", "source": source.origin
                                 if source.origin.startswith(("http://", "https://")) else ""})
            out.put(f"markdown/Orbits/{source_notes[source.id]}.md",
                    f"{head}# {source.preview.get('title') or source.origin}\n\n{_blocks_markdown(source)}")
    target_for = source_notes.get

    head = _frontmatter({"id": orbit.id, "type": "orbit", "title": title, "language": orbit.output_language})
    body = [f"# {title}\n"]
    if orbit.overview is not None and orbit.overview.text:
        overview = orbit.overview
        body.append(f"## {words['overview']}\n\n" + _answer_markdown(overview.text, overview.citations,
                                                        target_for, "o"))
    if orbit.notes:
        body.append(f"## {words['notes']}\n\n" + "\n\n".join(n.text.strip() for n in orbit.notes) + "\n")
    if orbit.sources:
        listed = "\n".join(f"- [[{source_notes[s.id]}]]" for s in orbit.sources)
        body.append(f"## {words['sources']}\n\n{listed}\n")
    if orbit.turns:
        body.append(f"## {words['conversation']}\n\n[[{note}/Conversation]]\n")
        chat = [f"# {title} \u00b7 {words['conversation']}\n"]
        for i, turn in enumerate(orbit.turns, 1):
            chat.append(f"## {turn.question.strip()}\n\n"
                        + _answer_markdown(turn.answer.text, turn.answer.citations, target_for, f"t{i}-"))
        out.put(f"markdown/Orbits/{note}/Conversation.md", "\n".join(chat))
    if orbit.podcast is not None and orbit.podcast.utterances:
        lines = [f"**{u.speaker}**: {_clean(u.text)}" for u in orbit.podcast.utterances]
        where = f"`media/audio/{slug_stem}{audio.suffix}` {words['audio_file']}\n\n" if audio else ""
        body.append(f"## {words['audio']}\n\n" + where + "\n\n".join(lines) + "\n")
    out.put(f"markdown/Orbits/{note}.md", head + "\n".join(body))


def _bookmarks(nodes, members, orbit_titles: dict, slug_to_id: dict, loose: str) -> str:
    """The Netscape bookmark file: a folder per orbit, and the Horizon for what is filed nowhere."""
    folders: dict[str, list] = {}
    for node in nodes:
        if not node.origin.startswith(("http://", "https://")):
            continue
        filed = [slug_to_id.get(m.orbit_id, m.orbit_id) for m in members.get(node.id, [])]
        for orbit_id in [o for o in filed if o in orbit_titles] or [None]:
            folders.setdefault(orbit_id, []).append(node)
    rows = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>",
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
            "<TITLE>Penumbra</TITLE>", "<H1>Penumbra</H1>", "<DL><p>"]
    for orbit_id, items in folders.items():
        name = orbit_titles[orbit_id] if orbit_id else loose
        rows.append(f"    <DT><H3>{html.escape(name)}</H3>")
        rows.append("    <DL><p>")
        for node in items:
            title = _clean(node.title) or node.preview.get("title") or node.origin
            tags = html.escape(",".join(node.tags), quote=True)
            rows.append(f'        <DT><A HREF="{html.escape(node.origin, quote=True)}" '
                        f'ADD_DATE="{int(node.created_at)}" TAGS="{tags}">{html.escape(title)}</A>')
        rows.append("    </DL><p>")
    rows.append("</DL><p>")
    return "\n".join(rows) + "\n"
