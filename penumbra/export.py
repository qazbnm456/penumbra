"""Everything the reader has made, as one zip they can keep or take to another tool.

The package has a lossless half and a readable half, side by side:

- `data/` is canonical: every capture row as stored with its text file, every orbit file exactly as
  stored, the alias table, removal records and Horizon asks. It is what a later restore would read,
  and nothing else in the zip is meant to be parsed back.
- `media/` holds the generated audio, one file per orbit.
- `markdown/` is a folder of notes that Obsidian opens as a vault, and that Logseq, Capacities,
  Heptabase, Bear, Notion, Apple Notes and NotebookLM can import: one note per capture, per orbit
  (with its conversation) and per entity, linked with wikilinks.
- `bookmarks.html` is the Netscape bookmark file every browser and read-later app imports.
- `manifest.json` names the format, its version and the SHA-256 of every file.

Model-written prose is tidied and stripped of corpus markers on the way out, as it is on screen
(invariant 62); the stored files under `data/` are copied as they are. Nothing is held for the whole
run beyond names and ids: each capture's text and each orbit are read when their note is written.
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

from pydantic import ValidationError

from . import __version__, asks, concepts, horizon
from .citations import strip_markers
from .horizon import DEFAULT_HORIZON_DIR
from .orbit import DEFAULT_ORBITS_DIR, audio_path
from .prose import polish
from .schema import Node, Orbit

FORMAT = "penumbra-export"
#: Bumped when a file under `data/` changes shape; a restore refuses a major version it does not know.
SCHEMA_VERSION = 1
_PAGE = 500
#: A note name's budget in UTF-8 bytes. Filesystems allow 255 bytes a component, and a name also
#: carries a clash suffix and `.md`; counted in characters, a long Chinese title passed the limit.
_NAME_BYTES = 150
_CHUNK = 500
#: Names Windows refuses as a file.
_RESERVED = {
    "con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10)),
}

#: The words the Markdown notes and the README are written in, following the reader's interface
#: language: a vault read in Chinese should not be headed in English.
_LABELS = {
    "en": {"text": "Text", "notes": "Notes", "sources": "Sources", "conversation": "Conversation",
           "overview": "Overview", "audio": "Audio overview", "named_by": "Named by:",
           "audio_file": "in this export", "horizon": "Horizon", "orbit": "Orbit", "capture": "Capture"},
    "zh": {"text": "內容", "notes": "筆記", "sources": "來源", "conversation": "對話",
           "overview": "概覽", "audio": "語音概覽", "named_by": "提到它的收錄：",
           "audio_file": "（在這份匯出裡）", "horizon": "視界", "orbit": "軌道", "capture": "收錄"},
}

_README_ZH = """# Penumbra 匯出

匯出時 Penumbra 保存的一切：{captures} 則收錄、{orbits} 個軌道。

- `markdown/` 可以直接用 Obsidian 打開，也能匯入 Logseq、Capacities、Heptabase、Bear、Notion、Apple Notes
  或 NotebookLM。`Captures/` 每則收錄一篇筆記，含摘要和全文；
  `Orbits/` 每個軌道一篇，含概覽、筆記、來源，對話另成一篇；
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
  `Orbits/` one note per orbit with its overview, notes and sources, and its conversation beside it,
  and `Entities/` one note per named person, place or idea, with the other names it goes by.
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


def _line(text: str | None) -> str:
    """One line, for a heading: a line break inside a title or a question would end the heading."""
    return " ".join((text or "").split())


def _safe(name: str, fallback: str) -> str:
    """A filename (and wikilink) part: no path separators or characters links treat specially, and
    no more than `_NAME_BYTES` bytes of UTF-8, cut at a character boundary."""
    cleaned = re.sub(r'[\\/:*?"<>|#^\[\]\x00-\x1f]+', " ", name or "")
    cleaned = " ".join(cleaned.split()).strip(" .")
    raw = cleaned.encode("utf-8")[:_NAME_BYTES]
    cleaned = raw.decode("utf-8", errors="ignore").strip(" .")
    return cleaned or fallback


class _Names:
    """Unique note names within one folder, compared the way a case-insensitive disk compares them.
    A clash, a reserved name or a name used by the conversation notes gets a counter suffix."""

    def __init__(self, *taken: str):
        self.used = {t.casefold() for t in taken}

    def take(self, wanted: str, fallback: str) -> str:
        base = _safe(wanted, fallback)
        name, n = base, 1
        while name.casefold() in self.used or name.casefold() in _RESERVED:
            n += 1
            name = f"{base} {n}"
        self.used.add(name.casefold())
        return name


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
    return "\n".join(f"### {_heading(b.locator)}\n\n{b.text.strip()}\n" for b in source.blocks)


class _Zip:
    """A zip that remembers each file's hash for the manifest."""

    def __init__(self, target: Path):
        self.zf = zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED)
        self.hashes: dict[str, str] = {}

    def put(self, path: str, data: bytes | str) -> None:
        raw = data.encode("utf-8") if isinstance(data, str) else data
        self.hashes[path] = hashlib.sha256(raw).hexdigest()
        self.zf.writestr(path, raw)

    def put_file(self, path: str, source: Path) -> bool:
        """Copy a file; False when it vanished since it was listed (a delete ran meanwhile)."""
        try:
            data = source.read_bytes()
        except FileNotFoundError:
            return False
        self.put(path, data)
        return True

    def close(self) -> None:
        self.zf.close()


def _node_rows(base_dir) -> list[dict]:
    """Every capture row as stored, oldest first, JSON columns parsed where they parse and kept as
    text where they do not: nothing is dropped for being malformed, since this is the copy a reader
    is told to keep."""
    with horizon._connect(base_dir) as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM nodes ORDER BY created_at ASC, id ASC")]
    for row in rows:
        for column in horizon._JSON_COLUMNS:
            if isinstance(row.get(column), str):
                try:
                    row[column] = json.loads(row[column])
                except ValueError:
                    pass
    return rows


def _as_node(row: dict):
    try:
        return Node.model_validate(row)
    except (ValidationError, AttributeError):
        return None


def _memberships(ids: list[str], base_dir) -> dict:
    found: dict = {}
    for start in range(0, len(ids), _CHUNK):
        found.update(horizon.memberships_for_nodes(ids[start:start + _CHUNK], base_dir=base_dir))
    return found


def _all_asks(base_dir) -> list:
    found, offset = [], 0
    while True:
        page = asks.list_asks(limit=_PAGE, offset=offset, base_dir=base_dir)
        if not page:
            return found
        found.extend(page)
        offset += len(page)


def _orbit_files(orbits_dir: Path) -> list[Path]:
    return sorted(orbits_dir.glob("*.json")) if orbits_dir.is_dir() else []


def _load_orbit(path: Path) -> Orbit | None:
    try:
        return Orbit.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError):
        return None


def write_export(
    target: Path,
    *,
    orbits_dir: str | Path = DEFAULT_ORBITS_DIR,
    horizon_dir: str | Path = DEFAULT_HORIZON_DIR,
    language: str | None = None,
) -> dict:
    """Write the whole package to `target` and return its counts. `language` is the reader's
    interface language, which the notes' headings and the README follow."""
    lang = labels_for(language)
    out = _Zip(Path(target))
    try:
        counts = _write(out, Path(orbits_dir), Path(horizon_dir), _LABELS[lang], lang)
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


def labels_for(language: str | None) -> str:
    """`zh` for a Chinese interface, `en` otherwise."""
    text = (language or "").lower()
    return "zh" if ("chinese" in text or "中文" in text or text.startswith("zh")) else "en"


def _write(out: _Zip, orbits_dir: Path, horizon_dir: Path, words: dict, lang: str) -> dict:
    rows = _node_rows(horizon_dir)
    ids = [r["id"] for r in rows]
    members = _memberships(ids, horizon_dir) if ids else {}
    nodes = {r["id"]: n for r in rows if (n := _as_node(r)) is not None}

    # Orbits, first pass: names only, one file at a time.
    orbit_names = _Names()
    orbit_notes: dict[str, str] = {}      # file stem -> note name
    orbit_titles: dict[str, str] = {}     # file stem -> title
    unreadable: list[Path] = []
    for path in _orbit_files(orbits_dir):
        orbit = _load_orbit(path)
        if orbit is None:
            unreadable.append(path)
            continue
        title = _clean(orbit.title) or (orbit.sources[0].preview.get("title") if orbit.sources else "")
        orbit_titles[path.stem] = _line(title) or words["orbit"]
        orbit_notes[path.stem] = orbit_names.take(orbit_titles[path.stem], words["orbit"])
        del orbit

    capture_names = _Names()
    capture_notes = {
        node_id: capture_names.take(_line(_clean(n.title) or n.preview.get("title", "")), words["capture"])
        for node_id, n in nodes.items()
    }
    resolve = concepts.resolver(base_dir=horizon_dir)
    alias_table = concepts.aliases(base_dir=horizon_dir)

    # --- data/: the lossless half -------------------------------------------------------------
    lines = []
    for row in rows:
        record = dict(row)
        record["orbits"] = [m.model_dump() for m in members.get(row["id"], [])]
        lines.append(json.dumps(record, ensure_ascii=False, default=str))
    out.put("data/captures.jsonl", "\n".join(lines) + ("\n" if lines else ""))
    blocks_dir = horizon.horizon_dir(horizon_dir) / "nodes"
    if blocks_dir.is_dir():
        for path in sorted(blocks_dir.glob("*.json")):
            if horizon.is_node_id(path.stem):
                out.put_file(f"data/blocks/{path.name}", path)
    for path in _orbit_files(orbits_dir):
        folder = "data/orbits/unreadable" if path in unreadable else "data/orbits"
        out.put_file(f"{folder}/{path.name}", path)
        for suffix in (".mp3", ".wav"):
            audio = audio_path(path.stem, base_dir=orbits_dir, suffix=suffix)
            out.put_file(f"media/audio/{path.stem}{suffix}", audio)
    out.put("data/concepts.json", json.dumps(alias_table, ensure_ascii=False, indent=2))
    removals = horizon.removal_events(limit=horizon.MAX_REMOVAL_EVENTS, base_dir=horizon_dir)
    out.put("data/removals.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in removals))
    ask_list = _all_asks(horizon_dir)
    out.put("data/asks.jsonl", "".join(a.model_dump_json() + "\n" for a in ask_list))

    # --- markdown/: the readable half ---------------------------------------------------------
    entity_names = _Names()
    entity_notes: dict[str, str] = {}
    entity_captures: dict[str, list[str]] = {}
    for node_id, node in nodes.items():
        for name in sorted({_line(_clean(resolve(e))) for e in node.entities} - {""}):
            if name not in entity_notes:
                entity_notes[name] = entity_names.take(name, "Entity")
            entity_captures.setdefault(name, []).append(node_id)
    for node_id, node in nodes.items():
        names = sorted({_line(_clean(resolve(e))) for e in node.entities} - {""})
        filed = [orbit_notes[m.orbit_id] for m in members.get(node_id, []) if m.orbit_id in orbit_notes]
        title = _line(_clean(node.title) or node.preview.get("title") or node.origin)
        head = _frontmatter({
            "id": node.id,
            "type": "capture",
            "title": title,
            "source": node.origin if node.origin.startswith(("http://", "https://")) else "",
            "kind": node.kind,
            "created": _iso(node.created_at),
            "tags": list(node.tags),
            "entities": [f"[[{entity_notes[n]}]]" for n in names],
            "orbits": [f"[[{o}]]" for o in filed],
        })
        body = [f"# {title}\n"]
        if node.summary:
            body.append(_clean(node.summary) + "\n")
        try:
            source = horizon.node_source(node_id, base_dir=horizon_dir)
        except Exception:  # noqa: BLE001 - an unreadable text file is still copied under data/
            source = None
        if source is not None and source.blocks:
            body.append(f"## {words['text']}\n\n" + _blocks_markdown(source))
        out.put(f"markdown/Captures/{capture_notes[node_id]}.md", head + "\n".join(body))

    also: dict[str, list[str]] = {}
    for alias, canonical in alias_table.items():
        also.setdefault(_line(_clean(canonical)), []).append(alias)
    for name, captured in sorted(entity_captures.items()):
        head = _frontmatter({"type": "entity", "aliases": sorted(also.get(name, []))})
        links = "\n".join(f"- [[{capture_notes[i]}]]" for i in captured)
        out.put(f"markdown/Entities/{entity_notes[name]}.md",
                f"{head}# {name}\n\n{words['named_by']}\n\n{links}\n")

    # Orbits, second pass: each read again as its note is written.
    for path in _orbit_files(orbits_dir):
        if path.stem not in orbit_notes:
            continue
        orbit = _load_orbit(path)
        if orbit is None:
            continue
        audio = next((audio_path(path.stem, base_dir=orbits_dir, suffix=s) for s in (".mp3", ".wav")
                      if audio_path(path.stem, base_dir=orbits_dir, suffix=s).exists()), None)
        _orbit_markdown(out, orbit, orbit_notes[path.stem], orbit_titles[path.stem], path.stem,
                        horizon_dir, capture_notes, audio, words, orbit_names)

    out.put("bookmarks.html", _bookmarks(rows, nodes, members, orbit_titles, words["horizon"]))

    counts = {
        "captures": len(rows),
        "orbits": len(orbit_notes) + len(unreadable),
        "entities": len(entity_captures),
        "asks": len(ask_list),
        "removals": len(removals),
    }
    out.put("README.md", (_README_ZH if lang == "zh" else _README).format(**counts))
    return counts


def _answer_markdown(text: str, citations, target_for, prefix: str) -> str:
    """An answer's prose, then its citations as footnotes pointing at the source's heading."""
    prose = _clean(text)
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
    if not notes:
        return prose + "\n"
    refs = "".join(f"[^{prefix}{i}]" for i in range(1, len(notes) + 1))
    last = prose.rstrip().rsplit("\n", 1)[-1].lstrip()
    # The references close the prose they back, except after a code fence or a table row, where
    # they would open the fence again or join the table.
    joined = f"{prose}\n\n{refs}" if last.startswith(("```", "~~~", "|")) or not prose else prose + refs
    return f"{joined}\n\n" + "\n".join(notes) + "\n"


def _orbit_markdown(out: _Zip, orbit, note: str, title: str, slug_stem: str, horizon_dir,
                    capture_notes: dict, audio: Path | None, words: dict, orbit_names: _Names) -> None:
    from_capture = {m.source_id: m.node_id for m in horizon.nodes_in_orbit(slug_stem, base_dir=horizon_dir)}
    source_names = _Names()
    source_notes = {}
    for source in orbit.sources:
        node_id = from_capture.get(source.id)
        if node_id in capture_notes:
            source_notes[source.id] = capture_notes[node_id]
            continue
        label = source_names.take(f"{source.id} {source.preview.get('title') or source.origin}", source.id)
        source_notes[source.id] = f"{note}/{label}"
        head = _frontmatter({"type": "source", "orbit": f"[[{note}]]", "source": source.origin
                             if source.origin.startswith(("http://", "https://")) else ""})
        heading = _line(source.preview.get("title") or source.origin)
        out.put(f"markdown/Orbits/{note}/{label}.md", f"{head}# {heading}\n\n{_blocks_markdown(source)}")
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
        # Beside the orbit's note, under a name of its own, so no two orbits' conversations share one.
        chat_note = orbit_names.take(f"{note} {words['conversation']}", words["conversation"])
        body.append(f"## {words['conversation']}\n\n[[{chat_note}]]\n")
        chat = [f"# {title} · {words['conversation']}\n"]
        for i, turn in enumerate(orbit.turns, 1):
            chat.append(f"## {_line(turn.question)}\n\n"
                        + _answer_markdown(turn.answer.text, turn.answer.citations, target_for, f"t{i}-"))
        out.put(f"markdown/Orbits/{chat_note}.md", "\n".join(chat))
    if orbit.podcast is not None and orbit.podcast.utterances:
        lines = [f"**{u.speaker}**: {_clean(u.text)}" for u in orbit.podcast.utterances]
        where = f"`media/audio/{slug_stem}{audio.suffix}` {words['audio_file']}\n\n" if audio else ""
        body.append(f"## {words['audio']}\n\n" + where + "\n\n".join(lines) + "\n")
    out.put(f"markdown/Orbits/{note}.md", head + "\n".join(body))


def _bookmarks(rows, nodes, members, orbit_titles: dict, loose: str) -> str:
    """The Netscape bookmark file: a folder per orbit, and the Horizon for what is filed nowhere."""
    folders: dict[str | None, list] = {}
    for row in rows:
        origin = str(row.get("origin") or "")
        if not origin.startswith(("http://", "https://")):
            continue
        filed = [m.orbit_id for m in members.get(row["id"], []) if m.orbit_id in orbit_titles]
        for stem in filed or [None]:
            folders.setdefault(stem, []).append(row)
    lines = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>",
             '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
             "<TITLE>Penumbra</TITLE>", "<H1>Penumbra</H1>", "<DL><p>"]
    for stem, items in folders.items():
        name = orbit_titles[stem] if stem else loose
        lines.append(f"    <DT><H3>{html.escape(name)}</H3>")
        lines.append("    <DL><p>")
        for row in items:
            node = nodes.get(row["id"])
            title = (_line(_clean(node.title)) or node.preview.get("title")) if node else ""
            tags = row.get("tags") if isinstance(row.get("tags"), list) else []
            lines.append(f'        <DT><A HREF="{html.escape(row["origin"], quote=True)}" '
                         f'ADD_DATE="{int(row.get("created_at") or 0)}" '
                         f'TAGS="{html.escape(",".join(map(str, tags)), quote=True)}">'
                         f'{html.escape(title or row["origin"])}</A>')
        lines.append("    </DL><p>")
    lines.append("</DL><p>")
    return "\n".join(lines) + "\n"
