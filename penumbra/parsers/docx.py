"""Word (`.docx`) ingestion with the standard library: a `.docx` is a zip of XML, and the text a
reader wrote is in `word/document.xml`.

**Sections are the coordinates.** A heading starts a new block (`section:1`, `section:2`, ...), the
way a PDF's page does (`page:N`), so a citation points at the part of the document it came from
rather than at the whole file. A stretch with no heading is cut every `_SECTION_CHARS` characters
at a paragraph boundary, so a heading-less report still gets coordinates finer than "whole".
Tables are read row by row with ` | ` between cells, and list items keep a leading "- ".

**Bounded before it is read.** The upload cap bounds the zip, not what it inflates to, so the
document part's declared size is checked against `_MAX_XML_BYTES` before decompressing and the read
itself stops one byte past it. The XML is parsed by `xml.etree`, which resolves no external
entities, and the expat it runs on refuses exponential entity expansion.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

from ..schema import Source, SourceBlock

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DOCUMENT = "word/document.xml"
#: The largest `document.xml` read, inflated. A 300-page report is a few megabytes of XML.
_MAX_XML_BYTES = 64 * 1024 * 1024
#: Where a heading-less stretch is cut into its own section.
_SECTION_CHARS = 6000
_HEADING_STYLE = re.compile(r"^(?:heading|title|標題|标题)\s*\d*$", re.IGNORECASE)


def _paragraph_text(p: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in p.iter():
        if node.tag == f"{_W}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{_W}tab":
            parts.append("\t")
        elif node.tag in (f"{_W}br", f"{_W}cr"):
            parts.append("\n")
    return "".join(parts).strip()


#: A paragraph with no heading style still reads as one when it is short, bold throughout and at
#: least this size, in half-points (14pt): converters and apps other than Word write headings that
#: way, and without it such a document was one section.
_LOOKS_LIKE_HEADING_SIZE = 28
_LOOKS_LIKE_HEADING_CHARS = 80


def _looks_like_heading(p: ElementTree.Element) -> bool:
    runs = [r for r in p.iter(f"{_W}r") if "".join(t.text or "" for t in r.iter(f"{_W}t")).strip()]
    if not runs or len(_paragraph_text(p)) > _LOOKS_LIKE_HEADING_CHARS:
        return False
    for run in runs:
        props = run.find(f"{_W}rPr")
        if props is None:
            return False
        bold = props.find(f"{_W}b")
        if bold is None or bold.get(f"{_W}val", "true") in ("0", "false"):
            return False
        size = props.find(f"{_W}sz")
        try:
            if size is None or int(size.get(f"{_W}val", "0")) < _LOOKS_LIKE_HEADING_SIZE:
                return False
        except ValueError:
            return False
    return True


def _is_heading(p: ElementTree.Element) -> bool:
    props = p.find(f"{_W}pPr")
    if props is not None:
        if props.find(f"{_W}outlineLvl") is not None:
            return True
        style = props.find(f"{_W}pStyle")
        name = style.get(f"{_W}val", "") if style is not None else ""
        if _HEADING_STYLE.match(name):
            return True
    return _looks_like_heading(p)


def _is_list_item(p: ElementTree.Element) -> bool:
    props = p.find(f"{_W}pPr")
    return props is not None and props.find(f"{_W}numPr") is not None


def _lines(body: ElementTree.Element):
    """`(is_heading, text)` for each paragraph and table row of the body, in document order."""
    for child in body:
        if child.tag == f"{_W}p":
            text = _paragraph_text(child)
            if text:
                yield _is_heading(child), f"- {text}" if _is_list_item(child) else text
        elif child.tag == f"{_W}tbl":
            for row in child.iter(f"{_W}tr"):
                cells = [
                    " ".join(_paragraph_text(p) for p in cell.iter(f"{_W}p")).strip()
                    for cell in row.iter(f"{_W}tc")
                ]
                if any(cells):
                    yield False, " | ".join(cells)


def _read_document(data: bytes, filename: str) -> bytes:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{filename!r} is not a Word document (.docx)") from exc
    with archive:
        try:
            info = archive.getinfo(_DOCUMENT)
        except KeyError as exc:
            raise ValueError(f"{filename!r} has no document text; is it a .docx?") from exc
        if info.file_size > _MAX_XML_BYTES:
            raise ValueError(f"{filename!r} is too large to read")
        with archive.open(info) as part:
            xml = part.read(_MAX_XML_BYTES + 1)
    if len(xml) > _MAX_XML_BYTES:
        raise ValueError(f"{filename!r} is too large to read")
    return xml


def parse_docx(data: bytes, source_id: str, *, origin: str) -> Source:
    """A `.docx` file's bytes as a `Source` with one block per section. Raises `ValueError` for a
    file that is not a Word document or holds no text, never an empty citable source."""
    try:
        root = ElementTree.fromstring(_read_document(data, origin))
    except ElementTree.ParseError as exc:
        raise ValueError(f"{origin!r} could not be read as a Word document: {exc}") from exc
    body = root.find(f"{_W}body")
    if body is None:
        raise ValueError(f"{origin!r} has no document body")

    sections: list[list[str]] = []
    current: list[str] = []
    size = 0
    for heading, text in _lines(body):
        if current and (heading or size + len(text) > _SECTION_CHARS):
            sections.append(current)
            current, size = [], 0
        current.append(text)
        size += len(text) + 2
    if current:
        sections.append(current)
    blocks = [
        SourceBlock(locator=f"section:{n}", text="\n\n".join(lines))
        for n, lines in enumerate(sections, start=1)
    ]
    if not blocks:
        raise ValueError(f"no extractable text in {origin!r}")
    return Source(id=source_id, kind="docx", origin=origin, blocks=blocks)
