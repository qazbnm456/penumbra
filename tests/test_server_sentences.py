"""Server-written English sentences that reach the reader get translated, and stay translatable.

`injection_scan.py` flags and `citations.verify_citations` reasons are English sentences built on the
server. The web UI maps each known one to an i18n key (`FLAG_KEYS`, `readableReason` in
`rlm_notebook/web/app.js`). Two ways that breaks silently, and one test for each:

- a new scan pattern ships with no entry in `FLAG_KEYS`, so a zh-Hant reader sees English again;
- `citations.py` rewords a reason, the regex stops matching, and the raw sentence comes back.

The second test EXECUTES `readableReason` in node against strings produced by the real
`citations.verify_citations`, for the reason `tests/test_readable_error.py` gives: a test that pins a
function's inputs is not a test of the function. `node` is required, never skipped.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from rlm_notebook import injection_scan
from rlm_notebook.citations import verify_citations
from rlm_notebook.corpus import Corpus
from rlm_notebook.schema import Citation, Source, SourceBlock

WEB = Path(__file__).resolve().parents[1] / "rlm_notebook" / "web"


def test_every_injection_flag_has_a_translation_key():
    app = (WEB / "app.js").read_text(encoding="utf-8")
    table = app[app.index("const FLAG_KEYS = {") : app.index("function readableFlag(")]
    descriptions = [d for _, d in injection_scan._INSTRUCTION_PATTERNS]
    descriptions.append(injection_scan.scan_source("A" * 240)[0])
    missing = [d for d in descriptions if json.dumps(d) not in table]
    assert not missing, f"flags with no entry in FLAG_KEYS (they would show untranslated): {missing}"

    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")
    keys = set(re.findall(r'"(flag\.\w+)"', table))
    assert keys and all(f'"{k}":' in i18n for k in keys), "a flag key has no zh-Hant string"


def _reasons() -> list[str]:
    source = Source(
        id="s2",
        kind="pdf",
        origin="paper.pdf",
        blocks=[SourceBlock(locator=f"page:{n}", text=f"page {n}") for n in range(1, 9)],
    )
    corpus = Corpus([source])
    checked = verify_citations(
        [
            Citation(source_id="s9", locator="whole", quote="q"),
            Citation(source_id="s2", locator="page:12", quote="q"),
        ],
        corpus,
    )
    return [c.reason for c in checked]


def test_readable_reason_turns_both_verifier_sentences_into_plain_ones():
    node = shutil.which("node")
    assert node, "node is required; see AGENTS.md's Verify section"
    app = (WEB / "app.js").read_text(encoding="utf-8")
    start = app.index("function readableReason(")
    body = app[start : app.index("\n}\n", start) + 2]
    script = (
        "const t = (key, fallback) => fallback;\n"
        + body
        + "\nlet input='';process.stdin.on('data',d=>input+=d);process.stdin.on('end',()=>{"
        "const raw=JSON.parse(input);"
        "const out=[...raw.map((r)=>readableReason(r)), readableReason(raw[1],'paper.pdf')];"
        "process.stdout.write(JSON.stringify(out));});"
    )
    raw = _reasons()
    done = subprocess.run(
        [node, "-e", script],
        input=json.dumps(raw),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,  # the assertion below reports node's own stderr
    )
    assert done.returncode == 0, done.stderr
    no_source, no_block, named = json.loads(done.stdout)

    assert no_source == "There is no source s9 in this notebook. It may have been removed.", raw[0]
    assert no_block.startswith("Source s2 has no page:12. It has: page:1, page:2"), raw[1]
    assert no_block.endswith(", ….") and "page:7" not in no_block, "only the first six are named"
    # The card names the source by its title, so the reason does too when the caller knows it.
    assert named.startswith("Source paper.pdf has no page:12."), named
    for text in (no_source, no_block):
        assert "'" not in text and "[" not in text, f"Python repr leaked into the UI: {text}"
