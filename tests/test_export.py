"""Exporting everything (`GET /data/export`, `export.write_export`): a zip with the lossless data, a
Markdown vault, a bookmark file and a manifest whose hashes match."""

from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, auth, horizon, intake
from penumbra.orbit import mutate_orbit
from penumbra.schema import Answer, ChatTurn, Citation


@pytest.fixture(autouse=True)
def _fresh_queue():
    yield
    if intake._SHARED is not None:
        intake._SHARED.stop(timeout=5)
    intake._SHARED = None


@pytest.fixture
def client():
    with TestClient(
        api.app, base_url="http://127.0.0.1", headers={"Authorization": f"Bearer {auth.api_token()}"}
    ) as c:
        yield c


def _capture(client, text: str) -> str:
    node_id = client.post("/horizon", json={"texts": [text]}).json()["nodes"][0]["id"]
    for _ in range(150):
        if horizon.get_node(node_id).state == "ready_undistilled":
            return node_id
        time.sleep(0.02)
    raise AssertionError("the capture never became readable")


def _export(client) -> zipfile.ZipFile:
    reply = client.get("/data/export")
    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"] == "application/zip"
    assert "penumbra-export-" in reply.headers["content-disposition"]
    return zipfile.ZipFile(io.BytesIO(reply.content))


def test_the_export_holds_the_data_a_vault_bookmarks_and_a_true_manifest(client):
    loose = _capture(client, "Lighthouses guide ships along the coast at night.")
    filed = _capture(client, "Origami is the art of folding paper into shapes.")
    horizon.update_node(filed, title="Origami", tags=["craft"], entities=["Akira Yoshizawa"],
                        summary="Folding paper [[SRC:s1|whole]] into shapes.")
    promoted = client.post(f"/horizon/{filed}/promote", json={"orbit_id": "crafts", "create": True}).json()
    source_id = promoted["membership"]["source_id"]
    mutate_orbit("crafts", lambda orb: orb.turns.append(ChatTurn(
        question="What is origami?",
        answer=Answer(text=f"Folding paper. [[SRC:{source_id}|whole]]",
                      citations=[Citation(source_id=source_id, locator="whole", quote="folding paper")]),
    )), create=False)

    client.get("/horizon/map")
    assert client.put("/horizon/map/planets/crafts", json={"ring": 2, "angle": 0.5}).status_code == 200

    zf = _export(client)
    names = set(zf.namelist())
    # The reader's arrangement of the map is theirs too (invariant 85).
    star_map = json.loads(zf.read("data/map.json"))
    assert star_map["planets"]["crafts"]["ring"] == 2 and star_map["settings"]["inner_ring"] == 260
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["format"] == "penumbra-export" and manifest["schema_version"] == 1
    assert manifest["counts"]["captures"] == 2 and manifest["counts"]["orbits"] == 1
    for path, digest in manifest["files"].items():
        assert hashlib.sha256(zf.read(path)).hexdigest() == digest, path

    captures = [json.loads(line) for line in zf.read("data/captures.jsonl").decode().splitlines()]
    assert {c["id"] for c in captures} == {loose, filed}
    assert f"data/blocks/{filed}.json" in names and "data/orbits/crafts.json" in names
    assert "README.md" in names and "bookmarks.html" in names

    note = "markdown/Captures/Origami.md"
    text = zf.read(note).decode()
    assert text.startswith("---\n") and 'type: "capture"' in text and 'tags: ["craft"]' in text
    assert "[[Akira Yoshizawa]]" in text and "### whole" in text
    assert "[[SRC:" not in text, "markers never reach a note (invariant 62)"
    assert "markdown/Entities/Akira Yoshizawa.md" in names

    chat = next(n for n in names if n.startswith("markdown/Orbits/") and n.endswith(" Conversation.md"))
    conversation = zf.read(chat).decode()
    assert "## What is origami?" in conversation and "[[SRC:" not in conversation
    assert "#whole]]" in conversation and "“folding paper”" in conversation


def test_an_empty_penumbra_exports_a_valid_package(client):
    zf = _export(client)
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["counts"]["captures"] == 0
    assert zf.read("data/captures.jsonl") == b""


def test_the_notes_follow_a_chinese_interface(client):
    _capture(client, "A lighthouse guides ships.")
    reply = client.get("/data/export", headers={"X-Penumbra-Interface-Language": "Traditional Chinese"})
    zf = zipfile.ZipFile(io.BytesIO(reply.content))
    assert zf.read("README.md").decode().startswith("# Penumbra 匯出")
    note = next(n for n in zf.namelist() if n.startswith("markdown/Captures/"))
    assert "## 內容" in zf.read(note).decode()


def test_names_never_clash_and_long_titles_fit_a_filesystem(client):
    texts = ["Orchards in spring.", "A phone maker's history.", "A language for systems.",
             "The letter after B.", "Old console devices.", "A film about a prison plane.", "Characters."]
    for title, text in zip(["Apple", "apple", "C#", "C", "CON", "Con.Air", "漢" * 120], texts):
        node_id = _capture(client, text)
        horizon.update_node(node_id, title=title)
    names = [n for n in _export(client).namelist() if n.startswith("markdown/Captures/")]
    folded = [n.casefold() for n in names]
    assert len(names) == 7 and len(set(folded)) == 7, names
    assert all(len(n.rsplit("/", 1)[-1].encode("utf-8")) <= 200 for n in names)
    assert "markdown/Captures/_CON.md" in names and "markdown/Captures/_Con.Air.md" in names


def test_a_capture_row_that_does_not_parse_is_still_exported(client):
    good = _capture(client, "A readable capture.")
    bad = _capture(client, "A capture whose tags were written badly.")
    later = _capture(client, "A capture after it.")
    with horizon._connect() as conn:
        conn.execute("UPDATE nodes SET tags = ? WHERE id = ?", ('{"not": "a list"}', bad))
    zf = _export(client)
    ids = {json.loads(line)["id"] for line in zf.read("data/captures.jsonl").decode().splitlines()}
    assert {good, bad, later} <= ids


def test_a_footnote_never_reopens_a_code_fence():
    from penumbra.export import _answer_markdown
    from penumbra.schema import Citation as C
    text = _answer_markdown("Run this:\n\n```\nls\n```", [C(source_id="s1", locator="whole", quote="q")],
                            {"s1": "Note"}.get, "t1-")
    assert "```[^" not in text and "\n\n[^t1-1]\n\n[^t1-1]:" in text
