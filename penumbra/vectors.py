"""Local relations: an embedding per capture, computed on this machine, and the captures near it.

Relations drawn from summaries (`topology.py`) need a summary first, and a summary is a model call
the reader pays for (invariant 80). Embeddings are the free route: `multilingual-e5-small`, int8
quantised, runs on the CPU through `onnxruntime` in roughly 70 to 100 milliseconds per capture
(measured at 1,500 characters, English and Chinese), so an unsummarised capture can still be linked
to what it is like, and a first pass over a thousand captures takes a minute or two in the background.

**The model is downloaded when the reader turns this on, never bundled.** It is about 130 MB, pinned
to one upstream revision and checked against its SHA-256 before it is used, so a changed or
truncated file is refused rather than run. It is fetched from a fixed address on the host, like a
package, never from anything a capture or a model supplied (invariants 1 and 2 are about fetches a
source can steer; this one cannot be steered).

**The vectors live in the Horizon's own database** as a `sqlite-vec` table, derived like the search
index: every row can be rebuilt from the capture, and removing the model and the table loses
nothing but time. The table is touched only by connections that load the extension, which is why it
has no trigger: a node deleted through a connection without the extension would otherwise fail to
delete. Orphaned vectors are swept by `sync` instead.

**Similarity is a weak signal, and it is used as one.** Measured on this model, cosine similarity
sits in a narrow band (0.75 to 0.92) and leans towards text in the same language: a Chinese note on
coffee scored closer to a Chinese note on sleep (0.854) than to an English one on coffee (0.817). So
a link is drawn only above a high threshold and only between mutual near neighbours, and a missing
link means nothing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from . import horizon
from .atomic import atomic_write_text
from .horizon import DEFAULT_HORIZON_DIR

_log = logging.getLogger(__name__)

#: The one model, pinned. A new revision is a deliberate change here, with new hashes.
_REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
_BASE = f"https://huggingface.co/Xenova/multilingual-e5-small/resolve/{_REVISION}"
MODEL_FILES = {
    "model.onnx": {
        "url": f"{_BASE}/onnx/model_quantized.onnx",
        "sha256": "f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193",
        "size": 118_308_185,
    },
    "tokenizer.json": {
        "url": f"{_BASE}/tokenizer.json",
        "sha256": "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
        "size": 17_082_730,
    },
}
MODEL_BYTES = sum(f["size"] for f in MODEL_FILES.values())
DIMENSIONS = 384

#: How much of a capture is embedded: its description and the head of its text. The model reads at
#: most 512 tokens, and a capture's subject is stated early.
_TEXT_CHARS = 1500

#: Text shorter than this is not compared at all. Measured: an eleven-character note ("untidy notes")
#: scored 0.875 against an unrelated paper, because a vector of almost nothing sits near everything.
_MIN_TEXT = 40

#: A link is drawn only between captures at least this similar AND each among the other's nearest.
SIMILAR_THRESHOLD = 0.86
_NEIGHBOURS = 4


def model_dir(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> Path:
    return horizon.horizon_dir(base_dir) / "models" / "multilingual-e5-small-int8"


def installed(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> bool:
    """The model is present and complete. Sizes are checked here; hashes were checked on download."""
    folder = model_dir(base_dir)
    return all(
        (folder / name).is_file() and (folder / name).stat().st_size == spec["size"]
        for name, spec in MODEL_FILES.items()
    ) and (folder / "verified.json").is_file()


class DownloadStopped(Exception):
    """The reader stopped the download."""


def download(
    *,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
    on_progress=None,
    should_stop=None,
    opener=urllib.request.urlopen,
) -> None:
    """Fetch the model files, resuming a partial one, and verify each against its SHA-256 before
    moving it into place. A file that fails verification is deleted and the download fails."""
    folder = model_dir(base_dir)
    folder.mkdir(parents=True, exist_ok=True)
    done_bytes = 0
    for name, spec in MODEL_FILES.items():
        final = folder / name
        if final.is_file() and final.stat().st_size == spec["size"]:
            done_bytes += spec["size"]
            continue
        part = folder / f"{name}.part"
        have = part.stat().st_size if part.exists() else 0
        if have > spec["size"]:
            part.unlink()
            have = 0
        if have < spec["size"]:
            have = _fetch(spec, part, have, done_bytes, opener, on_progress, should_stop)
        # A part already at full size (a Stop or a quit during the last chunk, or during hashing)
        # goes straight to verification: asking for `bytes=<size>-` would be answered 416 forever.
        digest = hashlib.sha256()
        with part.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
        if digest.hexdigest() != spec["sha256"] or part.stat().st_size != spec["size"]:
            part.unlink(missing_ok=True)
            raise ValueError(f"{name} did not match its published checksum; nothing was installed")
        part.replace(final)
        done_bytes += spec["size"]
    atomic_write_text(folder / "verified.json", json.dumps({"revision": _REVISION}))


def _fetch(spec, part: Path, have: int, done_bytes: int, opener, on_progress, should_stop) -> int:
    request = urllib.request.Request(spec["url"], headers={"User-Agent": "penumbra"})
    if have:
        request.add_header("Range", f"bytes={have}-")
    try:
        response = opener(request, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code != 416 or not have:
            raise
        # The server has nothing past what we hold, so what we hold is not a prefix it recognises:
        # start the file over rather than failing the same way on every press.
        part.unlink(missing_ok=True)
        return _fetch(spec, part, 0, done_bytes, opener, on_progress, should_stop)
    with response:
        if have and getattr(response, "status", 200) != 206:
            have = 0  # the server ignored the range: start this file over
        with part.open("ab" if have else "wb") as out:
            while True:
                if should_stop is not None and should_stop():
                    raise DownloadStopped()
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                have += len(chunk)
                if on_progress is not None:
                    on_progress(done_bytes + have, MODEL_BYTES)
    return have


def compared(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> int:
    """How many captures have a vector, for the settings line."""
    with _vec_connect(base_dir) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM node_vectors").fetchone()[0])


def remove(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> None:
    """Delete the model and every stored vector. Turning the feature off."""
    folder = model_dir(base_dir)
    for child in folder.glob("*"):
        child.unlink(missing_ok=True)
    if folder.exists():
        folder.rmdir()
    with _vec_connect(base_dir) as conn:
        conn.execute("DELETE FROM vector_rows")
        conn.execute("DELETE FROM node_vectors")
    _EMBEDDERS.pop(str(model_dir(base_dir)), None)


# --- the embedder -----------------------------------------------------------------------------------


def _real_numpy():
    """Make `numpy` in `sys.modules` the real module before `onnxruntime` imports it.

    dspy (imported by the API) installs a lazy proxy for `numpy` that loads on first attribute
    access. `onnxruntime`'s compiled module imports numpy through the C API, which gets the proxy
    and fails with "import numpy failed"; measured in the server, every embedding failed so. Touching
    one attribute swaps the real module in.
    """
    import numpy

    numpy.ndarray  # noqa: B018 - the attribute access IS the point
    return sys.modules["numpy"]


class Embedder:
    """The model loaded once per process. Imports live here so a server that never turns this on
    never loads `onnxruntime` for it."""

    def __init__(self, folder: Path) -> None:
        _real_numpy()
        import onnxruntime
        from tokenizers import Tokenizer

        self._tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._tok.enable_truncation(512)
        self._tok.enable_padding()
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = 2  # a background job, not the foreground
        self._session = onnxruntime.InferenceSession(
            str(folder / "model.onnx"), options, providers=["CPUExecutionProvider"]
        )
        self._inputs = {i.name for i in self._session.get_inputs()}

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Unit vectors, one per text. `query: ` for every text, which is what the model's authors
        prescribe for symmetric similarity between two passages."""
        import numpy as np

        encoded = self._tok.encode_batch([f"query: {t}" for t in texts])
        ids = np.array([e.ids for e in encoded], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._inputs:
            feeds["token_type_ids"] = np.zeros_like(ids)
        hidden = self._session.run(None, feeds)[0]
        weights = mask[..., None].astype(np.float32)
        pooled = (hidden * weights).sum(1) / np.maximum(weights.sum(1), 1e-9)
        pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
        return pooled.astype(np.float32).tolist()


_EMBEDDERS: dict[str, Embedder] = {}
_EMBEDDER_LOCK = threading.Lock()


def embedder(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> Embedder:
    key = str(model_dir(base_dir))
    with _EMBEDDER_LOCK:
        if key not in _EMBEDDERS:
            _EMBEDDERS[key] = Embedder(model_dir(base_dir))
        return _EMBEDDERS[key]


# --- the index --------------------------------------------------------------------------------------

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS vector_rows (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     TEXT NOT NULL UNIQUE REFERENCES nodes(id) ON DELETE CASCADE,
    embedded_at REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS node_vectors
    USING vec0(embedding float[{DIMENSIONS}] distance_metric=cosine);
"""


@contextmanager
def _vec_connect(base_dir: str | Path = DEFAULT_HORIZON_DIR):
    import sqlite_vec

    with horizon._connect(base_dir) as conn:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.executescript(_SCHEMA)
        yield conn


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _capture_text(row, base_dir) -> str:
    parts = [row["title"] or "", row["summary"] or ""]
    try:
        blocks = json.loads(horizon.node_blocks_path(row["id"], base_dir=base_dir).read_text("utf-8"))
        body = "\n".join(b.get("text", "") for b in blocks if isinstance(b, dict))
    except (OSError, ValueError):
        body = ""
    parts.append(body[:_TEXT_CHARS])
    return "\n".join(p for p in parts if p).strip()


def sync(
    *, base_dir: str | Path = DEFAULT_HORIZON_DIR, model: Embedder | None = None, should_stop=None
) -> int:
    """Embed every readable capture that has no vector or changed since its vector was made, and
    sweep vectors whose capture is gone. Returns how many were embedded."""
    from .search import SEARCHABLE_STATES

    model = model or embedder(base_dir)
    marks = ", ".join("?" for _ in SEARCHABLE_STATES)
    with _vec_connect(base_dir) as conn:
        conn.execute("DELETE FROM node_vectors WHERE rowid NOT IN (SELECT rowid FROM vector_rows)")
        rows = conn.execute(
            f"""SELECT n.id, n.title, n.summary, n.updated_at FROM nodes n
                LEFT JOIN vector_rows v ON v.node_id = n.id
                WHERE n.state IN ({marks}) AND (v.node_id IS NULL OR n.updated_at > v.embedded_at)""",
            SEARCHABLE_STATES,
        ).fetchall()
    done = 0
    was_installed = installed(base_dir)
    for start in range(0, len(rows), 16):
        if should_stop is not None and should_stop():
            break
        if was_installed and not installed(base_dir):
            break  # the reader turned relations off mid-sync; nothing more is written
        batch = rows[start : start + 16]
        texts = [_capture_text(r, base_dir) for r in batch]
        long_enough = [i for i, text in enumerate(texts) if len(text) >= _MIN_TEXT]
        embedded = model.embed([texts[i] for i in long_enough]) if long_enough else []
        by_index = dict(zip(long_enough, embedded, strict=True))
        with _vec_connect(base_dir) as conn:
            if was_installed and not installed(base_dir):
                break  # turned off while this batch was being embedded: it is not written
            for i, row in enumerate(batch):
                vector = by_index.get(i)
                if conn.execute("SELECT 1 FROM nodes WHERE id = ?", (row["id"],)).fetchone() is None:
                    continue
                rowid = conn.execute(
                    """INSERT INTO vector_rows (node_id, embedded_at) VALUES (?, ?)
                       ON CONFLICT(node_id) DO UPDATE SET embedded_at = excluded.embedded_at
                       RETURNING rowid""",
                    (row["id"], row["updated_at"]),
                ).fetchone()[0]
                conn.execute("DELETE FROM node_vectors WHERE rowid = ?", (rowid,))
                if vector is None:
                    continue  # recorded as considered, with no vector: too short to compare
                conn.execute(
                    "INSERT INTO node_vectors (rowid, embedding) VALUES (?, ?)", (rowid, _pack(vector))
                )
                done += 1
    return done


def similar_pairs(node_ids: list[str], *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> list[dict]:
    """Pairs among `node_ids` that are similar enough and mutual near neighbours, strongest first.
    Captures with no vector yet simply have no pairs."""
    wanted = set(node_ids)
    if len(wanted) < 2:
        return []
    near: dict[str, dict[str, float]] = {}
    marks = ", ".join("?" for _ in wanted)
    with _vec_connect(base_dir) as conn:
        by_node = {
            r[0]: r[1]
            for r in conn.execute(
                f"SELECT node_id, rowid FROM vector_rows WHERE node_id IN ({marks})", list(wanted)
            )
        }
        by_rowid = {rowid: node for node, rowid in by_node.items()}
        k = _NEIGHBOURS + 1 + len(by_node) // 50
        for node, rowid in by_node.items():
            vector = conn.execute("SELECT embedding FROM node_vectors WHERE rowid = ?", (rowid,)).fetchone()
            if vector is None:
                continue
            hits = conn.execute(
                "SELECT rowid, distance FROM node_vectors WHERE embedding MATCH ? AND k = ?", (vector[0], k)
            ).fetchall()
            scores = {
                by_rowid[h[0]]: 1.0 - float(h[1]) for h in hits if h[0] in by_rowid and by_rowid[h[0]] != node
            }
            near[node] = dict(sorted(scores.items(), key=lambda kv: -kv[1])[:_NEIGHBOURS])
    pairs = []
    for a, others in near.items():
        for b, score in others.items():
            # Mutual: each is among the other's nearest, which filters the one-way pull a generic
            # capture has on everything.
            if a < b and score >= SIMILAR_THRESHOLD and a in near.get(b, {}):
                pairs.append({"a": a, "b": b, "score": round(score, 3)})
    pairs.sort(key=lambda p: -p["score"])
    return pairs


def _index_size(conn) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM vector_rows").fetchone()[0])


def neighbours(
    node_id: str,
    *,
    k: int = _NEIGHBOURS,
    among: set[str] | None = None,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
    conn=None,
) -> list[tuple[str, float]]:
    """The `k` captures nearest `node_id`, best first, from ONE vector search. With `among`, only
    those captures count: the search asks for enough hits that a crowd of other captures cannot
    fill every place before a wanted one is reached."""
    def run(c) -> list[tuple[str, float]]:
        row = c.execute(
            "SELECT v.rowid, e.embedding FROM vector_rows v JOIN node_vectors e ON e.rowid = v.rowid "
            "WHERE v.node_id = ?", (node_id,)
        ).fetchone()
        if row is None:
            return []
        wide = k + 1 if among is None else max(k + 1, 16 + _index_size(c) // 20)
        hits = c.execute(
            "SELECT e.rowid, e.distance, v.node_id FROM node_vectors e "
            "JOIN vector_rows v ON v.rowid = e.rowid WHERE e.embedding MATCH ? AND k = ?",
            (row[1], wide),
        ).fetchall()
        found = [(h[2], 1.0 - float(h[1])) for h in hits if h[2] != node_id]
        if among is not None:
            found = [(n, s) for n, s in found if n in among]
        return found[:k]

    if conn is not None:
        return run(conn)
    with _vec_connect(base_dir) as c:
        return run(c)


def mutual_matches(
    node_id: str, among: set[str] | None = None, *, base_dir: str | Path = DEFAULT_HORIZON_DIR
) -> list[tuple[str, float]]:
    """Captures in `among` (all, if omitted) that are above the threshold and mutual near
    neighbours of `node_id`, best first. A few vector searches, whatever the size of the index.

    Mutual in the same sense as `similar_pairs`, where each side's nearest are counted among the
    captures in play: `node_id` has to be among the other's nearest when the other looks at
    `node_id` and its own peers, not when a crowd of unrelated captures is in the way."""
    with _vec_connect(base_dir) as conn:
        mine = [(n, s) for n, s in neighbours(node_id, among=among, conn=conn) if s >= SIMILAR_THRESHOLD]
        peers = None if among is None else among | {node_id}
        return [(n, s) for n, s in mine if node_id in dict(neighbours(n, among=peers, conn=conn))]


def nearest(
    node_id: str, among: list[str], *, base_dir: str | Path = DEFAULT_HORIZON_DIR
) -> list[tuple[str, float]]:
    """The captures in `among` most similar to `node_id`, above the threshold, best first."""
    pairs = similar_pairs([node_id, *among], base_dir=base_dir)
    out = [
        (p["b"] if p["a"] == node_id else p["a"], p["score"]) for p in pairs if node_id in (p["a"], p["b"])
    ]
    return sorted(out, key=lambda kv: -kv[1])


# --- the background worker --------------------------------------------------------------------------


class Worker:
    """Embeds new captures in the background, one sync at a time, when the model is installed.
    `nudge()` after a capture lands; the worker coalesces nudges and never blocks the caller."""

    def __init__(self, base_dir: str | Path = DEFAULT_HORIZON_DIR, on_synced=None) -> None:
        self.base_dir = Path(base_dir).resolve()
        #: Called after a sync that embedded something, on this thread; what it raises is logged.
        self._on_synced = on_synced
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.state = {"running": False, "error": "", "embedded": 0, "at": 0.0}

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="penumbra-vectors", daemon=True)
            self._thread.start()

    def nudge(self) -> None:
        self._wake.set()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.wait()
            self._wake.clear()
            if self._stop.is_set() or not installed(self.base_dir):
                continue
            self.state.update(running=True, error="")
            try:
                n = sync(base_dir=self.base_dir, should_stop=self._stop.is_set)
                self.state.update(embedded=self.state["embedded"] + n, at=time.time())
                if n and self._on_synced is not None:
                    self._on_synced()
            except Exception as exc:  # noqa: BLE001 - a background job reports; it never takes the server down
                self.state["error"] = f"{type(exc).__name__}: {exc}"[:300]
                _log.warning("vectors: %s", exc)
            finally:
                self.state["running"] = False
