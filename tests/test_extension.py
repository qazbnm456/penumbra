"""The browser extension's side of the API: pairing mints a capture key, the key opens only the
three capture routes, and a rendered page, a selected passage and a link each land as a capture."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, auth, horizon, ingest, intake
from penumbra.schema import Source, SourceBlock


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    def fake(url: str, source_id: str) -> Source:
        block = SourceBlock(locator="whole", text=f"body of {url}")
        return Source(id=source_id, kind="web", origin=url, blocks=[block])

    monkeypatch.setattr(ingest, "parse_web", fake)
    monkeypatch.setenv("PN_FILING_MODE", "manual")
    yield
    if intake._SHARED is not None:
        intake._SHARED.stop(timeout=5)
    intake._SHARED = None


@pytest.fixture
def client():
    with TestClient(api.app, base_url="http://127.0.0.1") as c:
        yield c


def _full():
    return {"Authorization": f"Bearer {auth.api_token()}"}


def _pair(client) -> dict:
    url = client.post("/extension/pairing", headers=_full()).json()["pair_url"]
    code = url.split("#code=", 1)[1]
    assert url.startswith("http://127.0.0.1") and "/pair.html#code=" in url
    return {"Authorization": f"Bearer {code}"}


PAGE = (
    "<html><head><title>Members only</title></head><body><article><h1>Members only</h1>"
    + "<p>" + "This paragraph is only visible after logging in. " * 20 + "</p></article></body></html>"
)


def test_the_capture_key_opens_the_capture_routes_and_nothing_else(client):
    key = _pair(client)
    assert client.get("/extension/status", headers=key).status_code == 200
    assert client.get("/extension/orbits", headers=key).status_code == 200
    for method, path in (("GET", "/orbits"), ("GET", "/horizon"), ("GET", "/settings"),
                         ("POST", "/extension/pairing"), ("DELETE", "/extension/pairing")):
        assert client.request(method, path, headers=key).status_code == 401, (method, path)
    assert client.get("/extension/status").status_code == 401, "no key, no answer"
    assert client.get("/pair.html").status_code == 200, "the pairing page itself is a public asset"


def test_pairing_again_replaces_the_old_key_and_unpairing_revokes_it(client):
    first = _pair(client)
    second = _pair(client)
    assert client.get("/extension/status", headers=first).status_code == 401
    assert client.get("/extension/status", headers=second).status_code == 200
    assert client.get("/extension/pairing", headers=_full()).json()["paired"] is True
    client.delete("/extension/pairing", headers=_full())
    assert client.get("/extension/status", headers=second).status_code == 401


def test_a_rendered_page_lands_as_the_reader_saw_it(client):
    key = _pair(client)
    body = {"kind": "page", "url": "https://example.com/members", "title": "Members only", "html": PAGE}
    got = client.post("/extension/capture", headers=key, json=body)
    assert got.status_code == 200, got.text
    node = got.json()["node"]
    source = horizon.node_source(node["id"])
    assert "only visible after logging in" in source.blocks[0].text
    assert source.origin == "https://example.com/members"
    assert node["preview"]["title"] == "Members only"


def test_an_app_like_page_falls_back_to_its_visible_text(client):
    key = _pair(client)
    body = {"kind": "page", "url": "https://app.example.com/", "title": "App", "html": "<div id=root></div>",
            "text": "Board: three cards due today"}
    node = client.post("/extension/capture", headers=key, json=body).json()["node"]
    assert horizon.node_source(node["id"]).blocks[0].text == "Board: three cards due today"


def test_a_selection_keeps_its_page_and_points_back_at_the_passage(client):
    key = _pair(client)
    text = "Sleep consolidates memory by replaying the day in the hippocampus during slow-wave sleep"
    body = {"kind": "selection", "url": "https://example.com/sleep#top", "title": "Sleep", "text": text}
    node = client.post("/extension/capture", headers=key, json=body).json()["node"]
    source = horizon.node_source(node["id"])
    assert source.blocks[0].locator == "selection" and source.blocks[0].text == text
    assert source.origin.startswith("https://example.com/sleep#:~:text=Sleep%20consolidates%20memory")
    assert node["preview"]["title"] == "Sleep"


def test_a_link_is_queued_and_filed_into_the_chosen_orbit_once_read(client):
    key = _pair(client)
    seed = client.post("/horizon", headers=_full(), json={"texts": ["seed"]}).json()["nodes"][0]["id"]
    client.post(f"/horizon/{seed}/promote", headers=_full(), json={"orbit_id": "reading", "create": True})
    got = client.post("/extension/capture", headers=key,
                      json={"kind": "link", "url": "https://example.com/later", "orbit": "reading"})
    assert got.status_code == 200 and got.json()["queued"] is True
    node_id = got.json()["node"]["id"]
    for _ in range(150):
        if [m.orbit_id for m in horizon.memberships_for(node_id)] == ["reading"]:
            break
        time.sleep(0.02)
    assert [m.orbit_id for m in horizon.memberships_for(node_id)] == ["reading"]


def test_a_local_or_browser_page_is_refused(client):
    key = _pair(client)
    for url in ("file:///etc/passwd", "chrome://settings"):
        got = client.post("/extension/capture", headers=key, json={"kind": "page", "url": url, "html": PAGE})
        assert got.status_code == 422, url


def test_an_oversized_capture_is_refused_before_it_is_parsed(client, monkeypatch):
    key = _pair(client)
    monkeypatch.setattr(api, "max_upload_bytes", lambda: 100)
    got = client.post("/extension/capture", headers=key,
                      json={"kind": "page", "url": "https://example.com/", "html": PAGE})
    assert got.status_code == 413


def test_a_chinese_selection_points_back_by_characters_not_by_the_whole_passage(client):
    key = _pair(client)
    text = "研究發現，慢波睡眠期間海馬迴會重播白天的經驗，把短期記憶轉存到大腦皮質，這就是系統鞏固。"
    body = {"kind": "selection", "url": "https://example.com/zh", "title": "睡眠", "text": text}
    node = client.post("/extension/capture", headers=key, json=body).json()["node"]
    from urllib.parse import unquote

    fragment = unquote(horizon.node_source(node["id"]).origin.split("#:~:text=", 1)[1])
    assert fragment == "研究發現，慢波睡眠期間海,腦皮質，這就是系統鞏固。"


def test_penumbras_own_pages_are_not_captured(client):
    key = _pair(client)
    got = client.post("/extension/capture", headers=key,
                      json={"kind": "page", "url": "http://127.0.0.1/pair.html", "html": PAGE})
    assert got.status_code == 422 and "own pages" in got.json()["detail"]


def test_a_wrapped_link_is_captured_as_its_destination(client):
    key = _pair(client)
    wrapped = "https://l.facebook.com/l.php?u=https%3A%2F%2Fexample.com%2Freal&h=AT0"
    got = client.post("/extension/capture", headers=key, json={"kind": "link", "url": wrapped})
    node = got.json()["node"]
    assert node["origin"] == "https://example.com/real"


def test_the_card_can_file_or_take_back_only_what_this_browser_just_captured(client):
    key = _pair(client)
    seed = client.post("/horizon", headers=_full(), json={"texts": ["seed"]}).json()["nodes"][0]["id"]
    client.post(f"/horizon/{seed}/promote", headers=_full(), json={"orbit_id": "reading", "create": True})
    body = {"kind": "selection", "url": "https://example.com/a", "title": "A", "text": "a passage to keep"}
    node_id = client.post("/extension/capture", headers=key, json=body).json()["node"]["id"]

    filed = client.post("/extension/file", headers=key, json={"node_id": node_id, "orbit": "reading"})
    assert filed.status_code == 200 and filed.json()["filed"] is True
    assert [m.orbit_id for m in horizon.memberships_for(node_id)] == ["reading"]

    undone = client.post("/extension/undo", headers=key, json={"node_id": node_id})
    assert undone.json()["removed"] is True
    assert horizon.get_node(node_id) is None
    assert len(client.get("/orbits/reading", headers=_full()).json()["sources"]) == 1, "only the seed is left"

    # Something the extension did not just capture is out of its reach.
    assert client.post("/extension/undo", headers=key, json={"node_id": seed}).status_code == 404
    refused = client.post("/extension/file", headers=key, json={"node_id": seed, "orbit": "reading"})
    assert refused.status_code == 404
