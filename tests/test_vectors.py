"""Local relations (`vectors.py`): the download, the index and similarity, over the kit's
`MemoryVectors` with a fake embedder, so nothing is downloaded and no model runs."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import sqlite3
import threading

import pytest
from rlm_harness.memory import vectors_path
from rlm_harness.memory_vectors import MemoryVectors, ModelFile

from penumbra import horizon, memory_store, vectors
from penumbra.schema import Source, SourceBlock
from tests._labels import label

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
            v = [0.0] * vectors.MODEL.dimensions
            for i, word in enumerate(self.AXES):
                if word in text:
                    v[i] = 1.0
            if not any(v):
                v[10] = 1.0
            norm = sum(x * x for x in v) ** 0.5
            out.append([x / norm for x in v])
        return out


def _install() -> None:
    """The model's files at their published sizes (sparse, so nothing is written) and the marker a
    verified download leaves, which is what `installed` reads."""
    folder = vectors.model_dir(BASE)
    folder.mkdir(parents=True, exist_ok=True)
    for name, spec in vectors.MODEL.files.items():
        with (folder / name).open("wb") as fh:
            fh.truncate(spec.size)
    (folder / "verified.json").write_text(json.dumps({"revision": vectors.MODEL.revision}), "utf-8")


def _use(model) -> MemoryVectors:
    """The cached index for this Horizon, running `model` instead of the ONNX one."""
    _install()
    store = memory_store.store(BASE)
    made = MemoryVectors(store, vectors.model_dir(BASE), model=vectors.MODEL, embedder=model)
    vectors._INDEXES[str(store.path)] = (store, made)
    return made


def _stored() -> int:
    """Rows in the vectors file, embedded or skipped."""
    path = vectors_path(memory_store.store_path(BASE))
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM vectors WHERE embedding IS NOT NULL").fetchone()[0]


def _capture(url, text, state="ready_undistilled") -> str:
    text = f"{text} " + "filler " * 10  # past the minimum length for comparison
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web", base_dir=BASE)
    horizon.store_blocks(node_id, Source(id=node_id, kind="web", origin=url,
                                          blocks=[SourceBlock(locator="whole", text=text)]), base_dir=BASE)
    if state != "ready_undistilled":
        horizon.update_node(node_id, base_dir=BASE, state=state)
    # Stored, the capture carries its kit item id; the temporary id is only its `former_id`.
    return horizon.resolve_id(node_id, base_dir=BASE)


def test_sync_embeds_once_and_again_after_a_change():
    _use(FakeModel())
    a = _capture("https://x.example/a", "sleep notes")
    _capture("https://x.example/b", "coffee notes")
    assert vectors.sync(base_dir=BASE) == 2
    assert vectors.sync(base_dir=BASE) == 0
    label(a, base_dir=BASE, state=None, summary="more about sleep")
    assert vectors.sync(base_dir=BASE) == 1


def test_a_readers_title_is_embedded():
    """The title is part of what is embedded, so a rename re-embeds (the API nudges the worker)."""
    _use(FakeModel())
    a = _capture("https://x.example/a", "notes")
    assert vectors.sync(base_dir=BASE) == 1
    horizon.edit_node(a, title="Coffee", base_dir=BASE)
    assert vectors.sync(base_dir=BASE) == 1
    horizon.edit_node(a, tags=["drinks"], base_dir=BASE)
    assert vectors.sync(base_dir=BASE) == 0, "tags are not embedded"


def test_similar_pairs_need_the_threshold_and_mutual_nearness():
    _use(FakeModel())
    a = _capture("https://x.example/a", "sleep one")
    b = _capture("https://x.example/b", "sleep two")
    c = _capture("https://x.example/c", "coffee")
    vectors.sync(base_dir=BASE)
    pairs = vectors.similar_pairs([a, b, c], base_dir=BASE)
    assert [(p["a"], p["b"]) for p in pairs] == [tuple(sorted((a, b)))]
    # Not `pytest.approx`: under dspy's lazy numpy import it recurses when this file runs after others.
    assert abs(pairs[0]["score"] - 1.0) < 1e-3


def test_pairs_are_counted_within_the_captures_compared():
    """Nearness is judged among the captures being drawn, exactly: a crowd outside them does not
    take a neighbour's place, which the old global search with a widened `k` only approximated."""
    _use(FakeModel())
    a = _capture("https://x.example/a", "sleep one")
    b = _capture("https://x.example/b", "sleep two")
    for i in range(8):
        _capture(f"https://x.example/crowd{i}", f"sleep crowd {i}")
    vectors.sync(base_dir=BASE)
    assert [(p["a"], p["b"]) for p in vectors.similar_pairs([a, b], base_dir=BASE)] == [tuple(sorted((a, b)))]


def test_two_chinese_captures_need_the_higher_threshold():
    """0.86 drew 14 wrong links beside 8 right ones between Chinese texts; they are held to 0.90."""
    class Angled(FakeModel):
        def embed(self, texts):
            # cos = 0.88: above 0.86, below 0.90.
            return [[1.0, 0.0] + [0.0] * (vectors.MODEL.dimensions - 2) if "一" in t
                    else [0.88, (1 - 0.88 ** 2) ** 0.5] + [0.0] * (vectors.MODEL.dimensions - 2)
                    for t in texts]

    _use(Angled())
    a = _capture("https://x.example/zh1", "一" + "睡眠與記憶的關係很密切" * 8)
    b = _capture("https://x.example/zh2", "睡眠與記憶的關係很密切" * 8)
    c = _capture("https://x.example/en1", "one sleep and memory")
    d = _capture("https://x.example/en2", "sleep and memory")
    vectors.sync(base_dir=BASE)
    assert vectors.similar_pairs([a, b], base_dir=BASE) == []
    assert len(vectors.similar_pairs([c, d], base_dir=BASE)) == 1


def test_a_removed_capture_leaves_no_vector_behind():
    _use(FakeModel())
    a = _capture("https://x.example/a", "sleep one")
    b = _capture("https://x.example/b", "sleep two")
    vectors.sync(base_dir=BASE)
    assert _stored() == 2
    horizon.remove_node(a, base_dir=BASE)   # the kit's purge erases its vector
    assert _stored() == 1
    assert vectors.similar_pairs([a, b], base_dir=BASE) == []


def test_a_capture_with_no_readable_text_is_not_embedded():
    _use(FakeModel())
    horizon.add_pending_node("https://x.example/q", "web", base_dir=BASE)
    assert vectors.sync(base_dir=BASE) == 0


def test_nothing_is_embedded_while_the_model_is_not_installed():
    model = FakeModel()
    _use(model)
    _capture("https://x.example/a", "sleep notes")
    for child in vectors.model_dir(BASE).glob("*"):
        child.unlink()
    assert vectors.sync(base_dir=BASE) == 0 and model.calls == 0


def test_an_older_download_still_counts_as_installed():
    """A download made before relations moved to the kit left `{"revision": ...}` alone in its
    marker, in the same folder; the kit's check accepts it, so nothing is fetched again."""
    _install()
    assert vectors.installed(BASE)
    assert vectors.model_dir(BASE).name == "multilingual-e5-small-int8"


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
    files = {name: ModelFile(url=f"https://example.invalid/{name}", size=len(data),
                             sha256=hashlib.sha256(data).hexdigest()) for name, data in blobs.items()}
    model = dataclasses.replace(vectors.MODEL, files=files)
    monkeypatch.setattr(vectors, "MODEL", model)
    monkeypatch.setattr(vectors, "MODEL_BYTES", model.total_bytes)
    return {f.url: blobs[name] for name, f in files.items()}


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


def test_remove_deletes_the_model_and_every_vector():
    _use(FakeModel())
    _capture("https://x.example/a", "sleep")
    vectors.sync(base_dir=BASE)
    assert _stored() == 1
    vectors.remove(BASE)
    assert not vectors.installed(BASE)
    assert not vectors_path(memory_store.store_path(BASE)).exists()
    assert str(memory_store.store(BASE).path) not in vectors._INDEXES


def test_an_index_whose_file_was_deleted_under_it_is_made_again():
    """An index cached in the moment between turning off and the file going would open an empty
    file with no schema on every later call; one is made afresh instead."""
    _use(FakeModel())
    _capture("https://x.example/a", "sleep")
    held = vectors.index(BASE)
    path = vectors_path(memory_store.store_path(BASE))
    path.unlink()
    assert vectors.index(BASE) is not held
    assert path.exists() and vectors.compared(base_dir=BASE) == 0


def test_a_capture_too_short_to_compare_gets_no_vector_and_is_not_asked_again():
    model = FakeModel()
    _use(model)
    node_id = horizon.node_id_for("https://x.example/tiny")
    horizon.add_pending_node("https://x.example/tiny", "web", base_dir=BASE)
    horizon.store_blocks(node_id, Source(id=node_id, kind="web", origin="https://x.example/tiny",
                                          blocks=[SourceBlock(locator="whole", text="note")]), base_dir=BASE)
    assert vectors.sync(base_dir=BASE) == 0
    assert model.calls == 0
    assert vectors.sync(base_dir=BASE) == 0, "a short capture was reconsidered every sync"


def test_mutual_matches_each_answers_every_capture_from_one_load(monkeypatch):
    index = _use(FakeModel())
    a = _capture("https://x.example/a", "sleep one")
    b = _capture("https://x.example/b", "sleep two")
    c = _capture("https://x.example/c", "coffee one")
    d = _capture("https://x.example/d", "coffee two")
    vectors.sync(base_dir=BASE)
    loads = []
    real = index._snapshot
    monkeypatch.setattr(index, "_snapshot", lambda: loads.append(1) or real())
    got = vectors.mutual_matches_each([a, c], {b, d}, base_dir=BASE)
    assert [n for n, _ in got[a]] == [b] and [n for n, _ in got[c]] == [d]
    assert len(loads) == 1


def test_a_crowd_of_similar_unfiled_captures_still_reaches_the_filed_one():
    """Five near-duplicates used to fill all four nearest places, so the filed capture they all
    resemble was never reached and none of them was suggested."""
    _use(FakeModel())
    filed = _capture("https://x.example/f", "sleep filed")
    crowd = [_capture(f"https://x.example/u{i}", f"sleep {i}") for i in range(6)]
    vectors.sync(base_dir=BASE)
    got = vectors.mutual_matches_each(crowd, {filed}, base_dir=BASE)
    assert all([n for n, _ in got[node]] == [filed] for node in crowd)


def test_removing_the_model_mid_sync_writes_nothing_more():
    """The reader pressed Turn off while a batch was embedding: that batch is the last one."""
    for i in range(40):
        _capture(f"https://x.example/{i}", "sleep")

    class RemovingModel(FakeModel):
        def embed(self, texts):
            out = super().embed(texts)
            if self.calls == 1:
                for child in vectors.model_dir(BASE).glob("*"):
                    child.unlink()
            return out

    model = RemovingModel()
    _use(model)
    assert vectors.sync(base_dir=BASE) == 16
    assert model.calls == 1


def test_the_worker_stops_before_its_file_can_go():
    """`stop` says whether the thread has ended, which the API waits for before deleting."""
    started, release = threading.Event(), threading.Event()

    class Slow(FakeModel):
        def embed(self, texts):
            started.set()
            release.wait(10)
            return super().embed(texts)

    _use(Slow())
    _capture("https://x.example/a", "sleep")
    worker = vectors.Worker(BASE)
    worker.start()
    worker.nudge()
    assert started.wait(10)
    assert worker.stop(0.2) is False, "a batch still embedding is not stopped yet"
    release.set()
    assert worker.stop(10) is True
