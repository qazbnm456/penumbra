"""The island page (`penumbra/web/island.*`), the desktop app's presence in the notch.

`readDrop` decides what a drop IS, and a wrong answer sends a link as text or a file as nothing, so
it is executed in node against real drag payloads rather than read. The rest pins the rules the
design depends on: the island draws no words, and it asks the shell for nothing but the three
fixed paths invariant 81 allows.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "penumbra" / "web"
JS = (WEB / "island.js").read_text(encoding="utf-8")


def _nested(name: str) -> str:
    """A function declared inside the island's IIFE (two-space indent), by name."""
    start = JS.index(f"  function {name}(")
    return JS[start : JS.index("\n  }\n", start) + 4]


def _read(drops: list[dict]) -> list:
    node = shutil.which("node")
    assert node, "node is required; see AGENTS.md's Verify section"
    script = (
        _nested("hostOf")
        + _nested("readDrop")
        + """
const drops = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = drops.map((d) => readDrop({
  files: d.files || [],
  getData: (type) => (d.data || {})[type] || "",
}));
process.stdout.write(JSON.stringify(out));
"""
    )
    done = subprocess.run(
        [node, "-e", script], input=json.dumps(drops), capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_a_drop_is_read_as_files_then_links_then_text():
    files, uris, url_text, text, empty = _read(
        [
            {"files": [{"name": "paper.pdf"}], "data": {"text/uri-list": "https://x.org/a"}},
            {"data": {"text/uri-list": "# comment\nhttps://www.example.com/a\nhttp://b.org/"}},
            {"data": {"text/plain": "  https://example.com/page  "}},
            {"data": {"text/plain": "a thought worth keeping"}},
            {"data": {}},
        ]
    )
    assert files["names"] == ["paper.pdf"] and files["urls"] == [], "files win over a link beside them"
    assert uris["urls"] == ["https://www.example.com/a", "http://b.org/"]
    assert uris["names"] == ["example.com", "b.org"]
    assert url_text["urls"] == ["https://example.com/page"], "a lone URL as plain text is a link"
    assert text["texts"] == ["a thought worth keeping"]
    assert empty is None, "an empty drop is nothing, not an empty capture"


def test_the_island_draws_no_words():
    """Icons only (DESIGN.md §11): every sentence the island has goes to the live region, which a
    screen reader hears and nobody sees. A visible text node here is the regression."""
    html = (WEB / "island.html").read_text(encoding="utf-8")
    body = html[html.index("<body") : html.index("<script")]
    visible = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    visible = re.sub(r'<p class="sr-only"[^>]*></p>', "", visible)
    assert not re.search(r">\s*[^<\s][^<]*<", visible), f"the island renders text: {visible}"
    assert "setLine(" not in JS and "textContent = name" not in JS


def test_the_island_asks_the_shell_for_only_the_four_fixed_paths():
    """Invariant 81: the island's only channel to the shell is a navigation to one of four fixed,
    dataless paths. Anything else it navigates to would be a new, unreviewed request."""
    asked = set(re.findall(r'location\.href = "([^"]+)"', JS))
    assert asked == {"/__shell/open", "/__shell/menu", "/__shell/rest", "/__shell/note"}, asked
    shell = (Path(__file__).resolve().parents[1] / "desktop" / "src-tauri" / "src" / "lib.rs").read_text(
        encoding="utf-8"
    )
    for verb in ("open", "menu", "rest", "note"):
        assert f'"{verb}" =>' in shell, f"the shell does not handle /__shell/{verb}"


def test_keys_typed_into_the_note_never_reach_the_islands_own_enter():
    """The field sits inside the hole, whose Enter opens the workspace. Every Return typed there,
    including the one that picks a Zhuyin candidate, bubbled up and opened the workspace too, which
    took the keyboard away mid-thought; and Escape or Return while an input method composes belong
    to the input method."""
    hole_keys = JS[JS.index('hole.addEventListener("keydown"'):]
    hole_keys = hole_keys[: hole_keys.index("});")]
    assert 'event.target.closest(".note")' in hole_keys
    assert "compositionstart" in JS and "compositionend" in JS
    assert "imeOwns(event)" in JS

