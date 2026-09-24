"""The distillation pass with NOTHING monkeypatched, against a loopback stub LM.

**This file exists because 869 green tests covered a feature that had never once run.**

`POST /inbox/distil` was dead in every shipped configuration. `config.setup()` — the only caller of
`rlm_harness.configure`, and therefore the only thing that gives `dspy` a model — was invoked in
`cli.py` and in `worker.py`, and `worker.py` is the isolated subprocess every `RLMTask` runs in
(invariant 21). That is why `ask`, the guides, the podcast and `_resolve_language` all work.
`distill.py` is deliberately NOT an `RLMTask`: it is a plain `dspy.Predict` (invariant 80), and it
runs on a thread inside the server process, where nothing had ever called `setup`. Every node came
back `ValueError: No LM is loaded` and returned to `ready_undistilled`.

The suite could not see it, and the reason is worth stating plainly: **every other distillation test
monkeypatches `distill.distil_source`** — precisely the function whose real body could not work.
Patching the unit under test at exactly the seam where the bug lives makes a green suite say nothing
at all. An independent review found it by pointing `RN_BASE_URL` at a stub and noticing that zero
HTTP requests arrived.

So the scenario here patches NOTHING on the way down: an OpenAI-compatible HTTP server on loopback,
`RN_*` pointed at it, and an assertion that real bytes arrive. Offline in the sense the rest of the
suite is offline — 127.0.0.1 is not the network.

**It runs in a FRESH INTERPRETER, and that is not fussiness.** Two process-global caches make an
in-suite version of this test quietly meaningless:

  * `rlm_harness.configure` keeps the first LM a process builds. Configure against port A and then
    against port B and the LM still talks to A — verified, the second LM comes back with no
    `base_url` in its kwargs at all. Any earlier test in the run that configures `test/model` wins
    for the rest of the process, and this file's requests never go near the stub.
  * `dspy` caches completions on disk. The first run hit the stub twice and passed; every run after
    it hit the stub ZERO times and still reported `done: 2, failed: 0`, served from `~/.dspy_cache`.

Either one turns "bytes reached the model" into an assertion that passes over a re-broken build,
which is the exact failure mode this file was written to end. A subprocess has neither.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from rlm_notebook import api, auth, inbox, intake
from rlm_notebook.schema import Source, SourceBlock

ROOT = Path(__file__).resolve().parents[1]


#: The scenario, run in its own interpreter. Prints one JSON object on its last line.
#:
#: Written as a script rather than assembled from fixtures because the whole point is that nothing
#: in this process has touched `dspy`, `rlm_harness` or the settings before it starts.
_SCENARIO = textwrap.dedent(
    '''
    import json, os, sys, tempfile, threading, time
    from http.server import BaseHTTPRequestHandler, HTTPServer

    HITS = []

    class Stub(BaseHTTPRequestHandler):
        """Just enough of POST /v1/chat/completions for dspy to parse a reply."""
        def log_message(self, *a): pass
        def do_POST(self):
            HITS.append(json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}"))
            content = json.dumps({"title": "Stubbed title",
                                  "summary": "A stubbed one-line summary of the captured node.",
                                  "tags": ["stub"], "entities": ["Stub"]})
            reply = {"id": "c", "object": "chat.completion", "created": 0, "model": "stub",
                     "choices": [{"index": 0, "finish_reason": "stop",
                                  "message": {"role": "assistant", "content": content}}],
                     "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
            body = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    auto = os.environ.get("SCENARIO_AUTO") or ""
    os.environ.update(
        RN_MAIN_MODEL="openai/gpt-4o-mini",
        RN_SUB_MODEL="openai/gpt-4o-mini",
        RN_API_KEY="sk-stub",
        RN_BASE_URL="http://127.0.0.1:%d/v1" % port,
        # The toggle takes the word "on"; `SCENARIO_AUTO` additionally says WHICH non-queue path
        # to exercise, and conflating the two set `RN_AUTO_DISTIL=paste`, which reads as off.
        RN_AUTO_DISTIL="on" if auto else "",
    )
    os.chdir(tempfile.mkdtemp())

    import dspy
    dspy.configure_cache(enable_disk_cache=False, enable_memory_cache=False)

    from fastapi.testclient import TestClient
    from rlm_notebook import api, auth, inbox
    from rlm_notebook.schema import Source, SourceBlock

    def seed(n):
        for i in range(n):
            text = "The body of note %d. " % i * 20
            inbox.add_node(Source(id="s0", kind="text", origin="pasted:note %d" % i,
                                  blocks=[SourceBlock(locator="whole", text=text)]))

    out = {}
    with TestClient(api.app, base_url="http://127.0.0.1",
                    headers={"Authorization": "Bearer " + auth.api_token()}) as c:
        if auto:
            # The AUTO path, and specifically through a PASTE: pasted text never enters the intake
            # queue, so only `IntakeQueue.nudge` can make the idle hook see it.
            seed(6)
            # BOTH non-queue capture paths, because both bypass the intake queue and the earlier
            # version of this test named both in its docstring and asserted only the paste. A
            # reviewer removed `nudge()` from `/inbox/upload` and the suite stayed green.
            which = os.environ.get("SCENARIO_AUTO")
            if which == "upload":
                c.post("/inbox/upload", files={"file": ("dropped.md", b"a dropped note", "text/markdown")})
            else:
                c.post("/inbox", json={"texts": ["a pasted note the auto pass should pick up"]})
            # The status is SAMPLED while it runs. The auto pass used to report through nothing at
            # all - thirteen measured model calls behind `{running: false, done: 0, total: 0}` and a
            # hidden strip - so "it reached the model" was never the whole assertion.
            seen = []
            for _ in range(400):
                st = c.get("/inbox/status").json()["distil"]
                seen.append(st)
                if HITS and not st["running"] and st["done"]:
                    break
                time.sleep(0.05)
            out["autoRunningSeen"] = any(x["running"] for x in seen)
            out["autoTotalSeen"] = max(x["total"] for x in seen)
            out["autoDoneSeen"] = max(x["done"] for x in seen)
            time.sleep(0.3)
        else:
            seed(2)
            out["undistilled_before"] = c.get("/inbox").json()["undistilled"]
            out["started"] = c.post("/inbox/distil", json={"limit": 2}).json()
            for _ in range(400):
                out["distil"] = c.get("/inbox/status").json()["distil"]
                if not out["distil"]["running"]:
                    break
                time.sleep(0.05)
        body = c.get("/inbox").json()
        out["hits"] = len(HITS)
        out["undistilled_after"] = body["undistilled"]
        out["states"] = sorted(n["state"] for n in body["nodes"])
        out["titles"] = sorted({n["title"] for n in body["nodes"]})
        out["tags"] = sorted({t for n in body["nodes"] for t in n["tags"]})
    print("RESULT " + json.dumps(out))
    '''
)


#: **Mutating a COPY of the tree does not test these.** The scenario runs as `sys.executable -c`,
#: and `rlm_notebook` resolves through the editable install, not through the subprocess's cwd - so a
#: mutation applied to a copied tree is invisible here and the test passes, which looks exactly like
#: a test that does not catch it. A reviewer hit this and reported the seam as untested; it is not.
#: To mutation-check anything in this file, mutate the REAL tree with the change staged
#: (`git add -A` first, `git checkout -- <path>` after), which is the safety net the copy was
#: standing in for.
def _run_scenario(*, auto: str = "") -> dict:
    import os

    env = dict(os.environ)
    # Every `RN_*` the outer environment might carry is cleared: the scenario sets its own, and an
    # operator running the suite with a real `.env` exported must not have their own model called.
    for name in list(env):
        if name.startswith("RN_"):
            del env[name]
    env["SCENARIO_AUTO"] = auto or ""
    proc = subprocess.run(
        [sys.executable, "-c", _SCENARIO],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=ROOT,
        env=env,
        check=False,
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert line, (
        f"the scenario never reported:\nSTDOUT\n{proc.stdout[-3000:]}\nSTDERR\n{proc.stderr[-3000:]}"
    )
    return json.loads(line[len("RESULT ") :])


def test_a_real_distil_pass_actually_reaches_the_model():
    """The regression test for the dead feature, asserted on BYTES rather than on a mock.

    `hits` is the only assertion here that could not have been satisfied by the broken build:
    `done == 2` was reported on every failing run too, because progress was counted per ATTEMPT.
    Two HTTP requests arriving is the thing that was never true.
    """
    out = _run_scenario()
    assert out["undistilled_before"] == 2
    assert out["started"]["started"] is True
    assert out["hits"] == 2, f"no request reached the model: {out}"
    assert out["distil"]["failed"] == 0, out["distil"]["error"]
    assert out["distil"]["done"] == 2
    assert out["undistilled_after"] == 0
    assert out["states"] == ["ready", "ready"]
    assert out["titles"] == ["Stubbed title"]
    assert out["tags"] == ["stub"]


def test_the_auto_pass_reaches_the_model_through_an_upload():
    """**The other non-queue path, and the one the previous test only NAMED.**

    Its docstring said "an operator who turned the toggle on got nothing for a paste or a drop" and
    then asserted the paste. A reviewer replaced `_inbox_queue().nudge()` in `/inbox/upload` with
    `pass`, ran the suite green, then ran that tree as a real server with `RN_AUTO_DISTIL=on`: an
    uploaded node stayed `ready_undistilled` forever and nothing reported anything. Two paths, two
    assertions.
    """
    out = _run_scenario(auto="upload")
    assert out["hits"] >= 1, f"the auto pass never reached the model after an upload: {out}"
    assert out["autoRunningSeen"], f"the upload's auto pass never reported itself: {out}"
    assert out["undistilled_after"] == 0


def test_the_auto_pass_reaches_the_model_through_a_paste():
    """The other in-process path, and the gap it uncovered.

    `_auto_distil_after_intake` runs on the intake queue's worker thread, so it needs the same
    configuration. It also only fires when the QUEUE goes idle — and pasted text and uploads never
    enter the queue at all (both are bytes in hand; `capture_into_inbox` says so). A queue that was
    never busy never goes idle, so an operator who turned the toggle on got nothing for a paste or a
    drop: the two most common captures on a surface whose whole promise is "throw anything in".
    `IntakeQueue.nudge` is what closes it, and this asserts it through a paste specifically.
    """
    out = _run_scenario(auto="paste")
    assert out["hits"] >= 1, f"the auto pass never reached the model: {out}"
    assert out["titles"] == ["Stubbed title"]

    # **And it is VISIBLE while it runs.** This is the assertion that was missing: the pass reached
    # the model perfectly well and reported through nothing, so the one batch that runs WITHOUT a
    # press was the one with no progress, no Stop and no failure channel - invariant 47 inverted.
    # It shares `_DISTIL` with the manual pass now, which is also what stops a reader starting a
    # second pass on top of it (the 409 guard reads the same state).
    assert out["autoRunningSeen"], f"the auto pass never reported itself as running: {out}"
    assert out["autoTotalSeen"] >= 1, f"the auto pass reported no total: {out}"
    assert out["autoDoneSeen"] >= 1, f"the auto pass reported no progress: {out}"


# --- the failure half, which needs no model and is therefore safe in this process ------------------


@pytest.fixture(autouse=True)
def _fresh_queue():
    yield
    existing = intake._SHARED
    if existing is not None:
        existing.stop(timeout=5)
    intake._SHARED = None


def test_a_missing_model_is_reported_rather_than_counted_as_done(tmp_path, monkeypatch):
    """The half that made the other half invisible.

    With no `RN_MAIN_MODEL` the pass cannot run at all. What it must NOT do is what it used to: tick
    `done` once per attempted node, finish at `total / total`, clear `running`, and leave the nodes
    untouched — a success shape, indistinguishable from fifty summaries that worked.

    In-process, unlike the two above: this never reaches `dspy`, so neither global cache can affect
    it. `_MODEL_CONFIGURED` is forced back to `False` because an earlier test in the run may have
    configured one successfully.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RN_MAIN_MODEL", raising=False)
    monkeypatch.setattr(api, "_MODEL_CONFIGURED", False)

    for n in range(2):
        inbox.add_node(
            Source(
                id="s0",
                kind="text",
                origin=f"pasted:note {n}",
                blocks=[SourceBlock(locator="whole", text=f"The body of note {n}. " * 20)],
            )
        )

    with TestClient(
        api.app, base_url="http://127.0.0.1", headers={"Authorization": f"Bearer {auth.api_token()}"}
    ) as client:
        assert client.post("/inbox/distil", json={"limit": 2}).json()["started"] is True
        for _ in range(400):
            distil = client.get("/inbox/status").json()["distil"]
            if not distil["running"]:
                break
            time.sleep(0.05)

        # `error` is the report, and `failed` is a count of NODES that were TRIED. Nothing was
        # tried here, so the count stays 0 — an earlier version wrote `max(1, failed)` so that
        # something would show, and "1 could not be summarised" for a pass that never started is
        # the status line claiming something the page is not doing (invariant 60). The page says
        # "the summary pass could not start" for exactly this shape.
        assert distil["error"], "a pass that could not run reported nothing at all"
        assert "RN_MAIN_MODEL" in distil["error"], distil["error"]
        assert distil["failed"] == 0, "nothing was attempted, so nothing can have failed"
        # `done` did not run ahead of the spend, and nothing was consumed.
        assert distil["done"] == 0
        assert client.get("/inbox").json()["undistilled"] == 2
