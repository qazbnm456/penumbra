"""What the web UI does differently inside the desktop shell, executed in node.

The shell opens the page at `/#token=…&shell=desktop` (invariant 81). Two things must hold, and
both are run here rather than read from the source, for the reason `tests/test_readable_error.py`
gives: a test that pins a function's text is not a test of the function.

- `captureApiToken` takes the token and the shell flag from the FRAGMENT, stores them, and leaves
  nothing of either in the address bar. The token in the query string reached uvicorn's access log.
- `withShellHint` adds the desktop hint only when the flag is set. The readable-error harness has
  no `sessionStorage`, so its desktop branch was never exercised there.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

APP = (Path(__file__).resolve().parents[1] / "rlm_notebook" / "web" / "app.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = APP.index(f"function {name}(")
    return APP[start : APP.index("\n}\n", start) + 2]


def _node(script: str) -> dict:
    node = shutil.which("node")
    assert node, "node is required; see AGENTS.md's Verify section"
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


STUBS = """
const store = {}; const session = {};
const localStorage = { setItem: (k, v) => { store[k] = v; }, getItem: (k) => store[k] ?? null };
const sessionStorage = { setItem: (k, v) => { session[k] = v; }, getItem: (k) => session[k] ?? null };
const history = { calls: [], replaceState(_s, _t, u) { this.calls.push(u); } };
const window = { location: { href: HREF }, history };
const API_TOKEN_KEY = "rlmnb-api-token"; let apiTokenMemo = null;
const t = (key, fallback) => fallback;
"""


def test_the_token_and_the_shell_flag_come_from_the_fragment_and_leave_no_trace():
    script = (
        'const HREF = "http://127.0.0.1:5000/?nb=rag#token=abc123&shell=desktop";\n'
        + STUBS
        + _fn("captureApiToken")
        + _fn("isDesktopShell")
        + "\ncaptureApiToken();\n"
        "process.stdout.write(JSON.stringify({token: apiTokenMemo, stored: store[API_TOKEN_KEY],"
        " desktop: isDesktopShell(), urls: window.history.calls}));"
    )
    got = _node(script)
    assert got["token"] == "abc123" and got["stored"] == "abc123"
    assert got["desktop"] is True
    assert got["urls"], "the address bar was never rewritten"
    final = got["urls"][-1]
    assert "abc123" not in final and "token" not in final and "shell" not in final, final
    assert final == "/?nb=rag", "the notebook route must survive the strip"


def test_a_plain_page_load_does_not_rewrite_history():
    """A bare `replaceState` would wipe the history entry's state, which the router reads on Back."""
    script = (
        'const HREF = "http://127.0.0.1:5000/?nb=rag";\n'
        + STUBS
        + _fn("captureApiToken")
        + "\ncaptureApiToken();\nprocess.stdout.write(JSON.stringify({urls: window.history.calls}));"
    )
    assert _node(script)["urls"] == []


def test_the_desktop_hint_appears_only_inside_the_shell():
    script = (
        'const HREF = "x";\n'
        + STUBS
        + _fn("isDesktopShell")
        + _fn("withShellHint")
        + '\nconst before = withShellHint("No model is configured.");'
        '\nsession["rlmnb-shell"] = "desktop";'
        '\nconst after = withShellHint("No model is configured.");'
        '\nconst restart = withShellHint("Lost contact.", "restart");'
        "\nprocess.stdout.write(JSON.stringify({before, after, restart}));"
    )
    got = _node(script)
    assert got["before"] == "No model is configured."
    assert "Open Configuration File" in got["after"] and "Restart Server" in got["after"]
    assert got["restart"].endswith("File > Restart Server starts it again.")
