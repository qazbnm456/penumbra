"""Local relations (`vectors.py`): the download, the index and similarity, with a fake embedder so
nothing is downloaded and no model runs."""

from __future__ import annotations

import hashlib
import io

import pytest

from penumbra import horizon, vectors
from penumbra.schema import Source, SourceBlock

BASE = "h"


class FakeModel:
    """Fixed unit vectors by keyword, so similarity is known exactly."""

    AXES = ("sleep", "coffee", "rust")

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        out = []
        for text in texts:
            v = [0.0] * vectors.DIMENSIONS
            for i, word in enumerate(self.AXES):
                if word in text:
                    v[i] = 1.0
            if not any(v):
                v[10] = 1.0
            norm = sum(x * x for x in v) ** 0.5
            out.append([x / norm for x in v])
        return out


def _capture(url, text, state="ready_undistilled") -> str:
    text = f"{text} " + "filler " * 10  # past the minimum length for comparison
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(node_id, Source(id=node_id, kind="web", origin=url,
                                          blocks=[SourceBlock(locator="whole", text=text)]), base_dir=BASE)
    if state != "ready_undistilled":
        horizon.update_node(node_id, base_dir=BASE, state=state)
    return node_id


def test_sync_embeds_once_and_again_after_a_change():
    model = FakeModel()
    a = _capture("https://x.example/a", "sleep notes")
    _capture("https://x.example/b", "coffee notes")
    assert vectors.sync(base_dir=BASE, model=model) == 2
    assert vectors.sync(base_dir=BASE, model=model) == 0
    horizon.update_node(a, base_dir=BASE, summary="more about sleep")
    assert vectors.sync(base_dir=BASE, model=model) == 1


def test_similar_pairs_need_the_threshold_and_mutual_nearness():
    model = FakeModel()
    a = _capture("https://x.example/a", "sleep one")
    b = _capture("https://x.example/b", "sleep two")
    c = _capture("https://x.example/c", "coffee")
    vectors.sync(base_dir=BASE, model=model)
    pairs = vectors.similar_pairs([a, b, c], base_dir=BASE)
    assert [(p["a"], p["b"]) for p in pairs] == [tuple(sorted((a, b)))]
    # Not `pytest.approx`: under dspy's lazy numpy import it recurses when this file runs after others.
    assert abs(pairs[0]["score"] - 1.0) < 1e-3


def test_a_removed_capture_leaves_no_vector_behind():
    model = FakeModel()
    a = _capture("https://x.example/a", "sleep one")
    b = _capture("https://x.example/b", "sleep two")
    vectors.sync(base_dir=BASE, model=model)
    horizon.remove_node(a, base_dir=BASE)  # a connection without the extension deletes fine
    vectors.sync(base_dir=BASE, model=model)
    with vectors._vec_connect(BASE) as conn:
        assert conn.execute("SELECT COUNT(*) FROM node_vectors").fetchone()[0] == 1
    assert vectors.similar_pairs([a, b], base_dir=BASE) == []


def test_a_capture_with_no_readable_text_is_not_embedded():
    horizon.add_pending_node("https://x.example/q", "web", base_dir=BASE)
    assert vectors.sync(base_dir=BASE, model=FakeModel()) == 0


# --- the download ---------------------------------------------------------------------------------


def _serve(files: dict[str, bytes], seen: list):
    class Resp(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(request, timeout=0):
        seen.append(request)
        data = files[request.full_url]
        rng = request.get_header("Range")
        if rng:
            start = int(rng.split("=")[1].rstrip("-"))
            resp = Resp(data[start:])
            resp.status = 206
            return resp
        return Resp(data)

    return opener


@pytest.fixture
def small_model(monkeypatch):
    blobs = {"model.onnx": b"m" * 3000, "tokenizer.json": b"t" * 1000}
    files = {
        name: {"url": f"https://example.invalid/{name}", "sha256": hashlib.sha256(data).hexdigest(),
               "size": len(data)}
        for name, data in blobs.items()
    }
    monkeypatch.setattr(vectors, "MODEL_FILES", files)
    monkeypatch.setattr(vectors, "MODEL_BYTES", sum(len(d) for d in blobs.values()))
    return {f["url"]: blobs[name] for name, f in files.items()}


def test_the_download_is_verified_before_it_counts_as_installed(small_model):
    progress = []
    vectors.download(base_dir=BASE, opener=_serve(small_model, []),
                     on_progress=lambda d, t: progress.append(d))
    assert vectors.installed(BASE)
    assert progress[-1] == 4000


def test_a_file_that_fails_its_checksum_installs_nothing(small_model):
    bad = {url: data[:-1] + b"X" for url, data in small_model.items()}
    with pytest.raises(ValueError, match="checksum"):
        vectors.download(base_dir=BASE, opener=_serve(bad, []))
    assert not vectors.installed(BASE)
    assert not list(vectors.model_dir(BASE).glob("*.part"))


def test_a_partial_file_resumes_with_a_range_request(small_model):
    folder = vectors.model_dir(BASE)
    folder.mkdir(parents=True)
    first = next(iter(small_model.values()))
    (folder / "model.onnx.part").write_bytes(first[:1200])
    seen = []
    vectors.download(base_dir=BASE, opener=_serve(small_model, seen))
    assert seen[0].get_header("Range") == "bytes=1200-"
    assert vectors.installed(BASE)


def test_stop_ends_the_download_and_installs_nothing(small_model):
    with pytest.raises(vectors.DownloadStopped):
        vectors.download(base_dir=BASE, opener=_serve(small_model, []), should_stop=lambda: True)
    assert not vectors.installed(BASE)


def test_remove_deletes_the_model_and_every_vector(small_model):
    vectors.download(base_dir=BASE, opener=_serve(small_model, []))
    _capture("https://x.example/a", "sleep")
    vectors.sync(base_dir=BASE, model=FakeModel())
    vectors.remove(BASE)
    assert not vectors.installed(BASE)
    with vectors._vec_connect(BASE) as conn:
        assert conn.execute("SELECT COUNT(*) FROM vector_rows").fetchone()[0] == 0



def test_a_capture_too_short_to_compare_gets_no_vector_and_is_not_asked_again():
    node_id = horizon.node_id_for("https://x.example/tiny")
    horizon.add_pending_node("https://x.example/tiny", "web", base_dir=BASE)
    horizon.store_blocks(node_id, Source(id=node_id, kind="web", origin="https://x.example/tiny",
                                          blocks=[SourceBlock(locator="whole", text="note")]), base_dir=BASE)
    model = FakeModel()
    assert vectors.sync(base_dir=BASE, model=model) == 0
    assert model.calls == 0
    assert vectors.sync(base_dir=BASE, model=model) == 0, "a short capture was reconsidered every sync"



def test_mutual_matches_costs_a_few_searches_and_finds_the_pair():
    model = FakeModel()
    a = _capture("https://x.example/a", "sleep one")
    b = _capture("https://x.example/b", "sleep two")
    _capture("https://x.example/c", "coffee")
    vectors.sync(base_dir=BASE, model=model)
    got = vectors.mutual_matches(a, base_dir=BASE)
    assert [n for n, _ in got] == [b]


def test_a_part_already_at_full_size_is_verified_without_asking_for_more(small_model):
    folder = vectors.model_dir(BASE)
    folder.mkdir(parents=True)
    first_url, first = next(iter(small_model.items()))
    (folder / "model.onnx.part").write_bytes(first)
    seen = []
    vectors.download(base_dir=BASE, opener=_serve(small_model, seen))
    assert all(r.full_url != first_url for r in seen), "a full part asked the server for bytes past its end"
    assert vectors.installed(BASE)


def test_a_416_starts_the_file_over(small_model):
    import urllib.error

    folder = vectors.model_dir(BASE)
    folder.mkdir(parents=True)
    (folder / "model.onnx.part").write_bytes(b"x" * 10)
    inner = _serve(small_model, [])

    def opener(request, timeout=0):
        if request.get_header("Range"):
            raise urllib.error.HTTPError(request.full_url, 416, "Range Not Satisfiable", {}, None)
        return inner(request, timeout)

    vectors.download(base_dir=BASE, opener=opener)
    assert vectors.installed(BASE)


def test_turning_relations_off_mid_sync_writes_nothing_more(small_model):
    vectors.download(base_dir=BASE, opener=_serve(small_model, []))
    for i in range(20):
        _capture(f"https://x.example/{i}", "sleep")

    class RemovingModel(FakeModel):
        def embed(self, texts):
            out = super().embed(texts)
            vectors.remove(BASE)  # the reader pressed "Turn off" while the first batch was embedding
            return out

    vectors.sync(base_dir=BASE, model=RemovingModel())
    with vectors._vec_connect(BASE) as conn:
        assert conn.execute("SELECT COUNT(*) FROM node_vectors").fetchone()[0] == 0
    # And the background worker, the only caller that syncs on its own, syncs only while installed.
    assert not vectors.installed(BASE)



def test_a_crowd_of_similar_unfiled_captures_still_reaches_the_filed_one():
    """Five near-duplicates used to fill all four nearest places, so the filed capture they all
    resemble was never reached and none of them was suggested."""
    model = FakeModel()
    filed = _capture("https://x.example/f", "sleep filed")
    crowd = [_capture(f"https://x.example/u{i}", f"sleep {i}") for i in range(6)]
    vectors.sync(base_dir=BASE, model=model)
    for node in crowd:
        assert [n for n, _ in vectors.mutual_matches(node, {filed}, base_dir=BASE)] == [filed]
