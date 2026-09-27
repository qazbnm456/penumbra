"""Word (`.docx`) ingestion (`parsers/docx.py`): sections as coordinates, tables and lists kept,
and a file that is not a Word document refused rather than turned into an empty source."""

from __future__ import annotations

import io
import zipfile

import pytest

from penumbra import ingest
from penumbra.parsers.docx import _SECTION_CHARS, parse_docx

_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _p(text: str, style: str = "", numbered: bool = False) -> str:
    props = ""
    if style or numbered:
        inner = f'<w:pStyle w:val="{style}"/>' if style else ""
        inner += "<w:numPr><w:ilvl w:val=\"0\"/></w:numPr>" if numbered else ""
        props = f"<w:pPr>{inner}</w:pPr>"
    return f"<w:p>{props}<w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"


def _docx(body: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", f"<w:document {_NS}><w:body>{body}</w:body></w:document>")
    return buffer.getvalue()


def test_headings_start_sections_and_tables_and_lists_are_kept():
    body = (
        _p("Intro line")
        + _p("Methods", style="Heading1")
        + _p("first step", numbered=True)
        + "<w:tbl><w:tr><w:tc>" + _p("Model") + "</w:tc><w:tc>" + _p("Score") + "</w:tc></w:tr></w:tbl>"
        + _p("結論", style="Heading2")
        + _p("Sleep helps memory.")
    )
    source = parse_docx(_docx(body), "s1", origin="report.docx")
    assert source.kind == "docx" and source.origin == "report.docx"
    assert [b.locator for b in source.blocks] == ["section:1", "section:2", "section:3"]
    assert source.blocks[0].text == "Intro line"
    assert source.blocks[1].text == "Methods\n\n- first step\n\nModel | Score"
    assert source.blocks[2].text == "結論\n\nSleep helps memory."


def test_a_long_stretch_without_headings_is_cut_at_paragraph_boundaries():
    paragraph = "word " * 400
    source = parse_docx(_docx(_p(paragraph) * 8), "s1", origin="long.docx")
    assert len(source.blocks) > 1
    assert all(len(b.text) <= _SECTION_CHARS + len(paragraph) for b in source.blocks)


def test_a_file_that_is_not_a_word_document_is_refused():
    with pytest.raises(ValueError, match="not a Word document"):
        parse_docx(b"plain bytes", "s1", origin="fake.docx")
    with pytest.raises(ValueError, match="no extractable text"):
        parse_docx(_docx(""), "s1", origin="empty.docx")


def test_an_upload_and_a_path_both_reach_the_word_parser(tmp_path):
    data = _docx(_p("Hello from Word"))
    uploaded = ingest.ingest_uploaded_file(data, "notes.docx", "s1")
    assert uploaded.kind == "docx" and uploaded.blocks[0].text == "Hello from Word"
    path = tmp_path / "notes.docx"
    path.write_bytes(data)
    assert ingest.kind_for(str(path)) == "docx"
    assert ingest.ingest_one(str(path), "s2").blocks[0].text == "Hello from Word"


def test_a_short_bold_large_paragraph_counts_as_a_heading_without_a_style():
    """Converters and apps other than Word write headings as bold, large text with no heading
    style; without this such a document was one section."""
    def run(text: str, bold: bool, size: int) -> str:
        props = ("<w:b/>" if bold else "") + f'<w:sz w:val="{size}"/>'
        return f"<w:p><w:r><w:rPr>{props}</w:rPr><w:t>{text}</w:t></w:r></w:p>"

    body = run("Notes", True, 48) + run("body text", False, 24)
    body += run("Result", True, 32) + run("done", True, 24)
    source = parse_docx(_docx(body), "s1", origin="styled.docx")
    assert [b.text for b in source.blocks] == ["Notes\n\nbody text", "Result\n\ndone"]
