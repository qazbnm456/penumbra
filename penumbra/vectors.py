"""Local relations: an embedding per capture, computed on this machine, and the captures near it.

Relations drawn from summaries (`topology.py`) need a summary first, and a summary is a model call
the reader pays for (invariant 80). Embeddings are the free route: an unsummarised capture can still
be linked to what it is like. The work is the kit's `rlm_harness.memory_vectors.MemoryVectors` over
the Horizon's memory store; this module is the product's side of it: where the model lives, when it
is fetched, the background worker, and the shapes the graph and filing read.

**The model is downloaded when the reader turns this on, never bundled.** It is the kit's pinned
`DEFAULT_MODEL` (`multilingual-e5-small`, int8, about 135 MB), fetched from its fixed addresses and
checked against its SHA-256 before it is used, so a changed or truncated file is refused rather than
run. Nothing a capture or a model supplied can steer that fetch (invariants 1 and 2).

**The vectors are a derived cache in the store's own vectors file** (`memory.db.vectors.db`): every
row can be rebuilt from the store, a removed capture's vector goes with its purge, and clearing the
Horizon deletes the file with the store.

**Similarity is a weak signal, and it is used as one** (invariant 82). Two captures are linked only
at or above a threshold, 0.90 when both are mostly Chinese, Japanese or Korean and 0.86 otherwise,
and only when each is among the other's nearest within the captures being compared. A missing link
means nothing.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.request
from pathlib import Path

from rlm_harness.memory import vectors_path
from rlm_harness.memory_vectors import (
    DEFAULT_MODEL,
    DownloadStopped,
    MemoryVectors,
    download_model,
    model_installed,
)

from . import horizon, memory_store
from .horizon import DEFAULT_HORIZON_DIR

__all__ = ["DownloadStopped"]

_log = logging.getLogger(__name__)

#: The one model, the kit's pinned default. A new revision is the kit's deliberate change.
MODEL = DEFAULT_MODEL
MODEL_BYTES = MODEL.total_bytes

#: How many captures one round of `sync` embeds; the kit's own cap per call.
_ROUND = 500


def model_dir(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> Path:
    return horizon.horizon_dir(base_dir) / "models" / MODEL.name


def installed(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> bool:
    """The model is present, complete, and a download of this revision verified it."""
    return model_installed(MODEL, model_dir(base_dir))


def download(
    *,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
    on_progress=None,
    should_stop=None,
    opener=urllib.request.urlopen,
) -> None:
    """Fetch the model files, resuming a partial one, each verified against its SHA-256 before it
    is moved into place. Raises `DownloadStopped` on a Stop and `ValueError` on a bad file."""
    download_model(MODEL, model_dir(base_dir), on_progress=on_progress, should_stop=should_stop,
                   opener=opener)


# --- the index --------------------------------------------------------------------------------------

_INDEXES: dict[str, tuple[object, MemoryVectors]] = {}
_INDEX_LOCK = threading.Lock()


def index(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> MemoryVectors:
    """The kit's vector index over this Horizon's store, one per store object, so the model is
    loaded once per process. A clear makes a new store, and with it a new index."""
    store = memory_store.store(base_dir)
    key = str(store.path)
    with _INDEX_LOCK:
        cached = _INDEXES.get(key)
        # Its file deleted under it (relations turned off), an index would open an empty file with
        # no schema on every call: a fresh one recreates the file.
        if cached is not None and cached[0] is store and vectors_path(store.path).exists():
            return cached[1]
        made = MemoryVectors(store, model_dir(base_dir), model=MODEL)
        _INDEXES[key] = (store, made)
        return made


def forget_cache(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> None:
    """Drop the cached index (and the model it loaded): after a clear, or when the feature is off."""
    key = str(memory_store.store_path(base_dir).resolve())
    with _INDEX_LOCK:
        _INDEXES.pop(key, None)


def compared(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> int:
    """How many captures have a vector, for the settings line."""
    return index(base_dir).count()


def remove(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> None:
    """Delete the model and every stored vector: turning the feature off. The caller has stopped the
    worker first, so no sync writes into the file as it goes."""
    folder = model_dir(base_dir)
    for child in folder.glob("*"):
        child.unlink(missing_ok=True)
    if folder.exists():
        folder.rmdir()
    path = vectors_path(memory_store.store_path(base_dir))
    for suffix in ("", "-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)
    forget_cache(base_dir)   # after the file, so no index made meanwhile outlives it


def sync(*, base_dir: str | Path = DEFAULT_HORIZON_DIR, should_stop=None) -> int:
    """Embed every capture that has no vector, or whose title, summary or text changed since its
    vector was made, in rounds of up to 500, and drop the vectors of captures that are gone. Stops
    at `should_stop`, or when the model was removed meanwhile. Returns how many were embedded."""
    vectors = index(base_dir)

    def stop() -> bool:
        return (should_stop is not None and should_stop()) or not installed(base_dir)

    embedded = 0
    while not stop():
        report = vectors.sync(limit=_ROUND, should_stop=stop)
        embedded += report.embedded
        # A round that did nothing cannot be followed by one that does: stop rather than spin.
        if report.stopped or report.waiting <= 0 or not (report.embedded or report.skipped):
            break
    return embedded


def similar_pairs(node_ids: list[str], *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> list[dict]:
    """Pairs among `node_ids` that are similar enough and mutual near neighbours among them,
    strongest first. Captures with no vector yet simply have no pairs."""
    return [{"a": p.a, "b": p.b, "score": round(p.score, 3)}
            for p in index(base_dir).similar_pairs(list(node_ids))]


def mutual_matches_each(
    node_ids: list[str], among: set[str], *, base_dir: str | Path = DEFAULT_HORIZON_DIR
) -> dict[str, list[tuple[str, float]]]:
    """For each of `node_ids`, the captures in `among` above the threshold that are mutual near
    neighbours of it, each side's nearest counted among `among` and itself; best first, from one
    load of the vectors."""
    return index(base_dir).similar_each(list(node_ids), among=sorted(among))


# --- the background worker --------------------------------------------------------------------------


class Worker:
    """Embeds new captures in the background, one sync at a time, when the model is installed.
    `nudge()` after a capture lands or its labels change; the worker coalesces nudges and never
    blocks the caller."""

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

    def finished(self) -> bool:
        """Asked to stop, and its thread has ended (or never started)."""
        return self._stop.is_set() and (self._thread is None or not self._thread.is_alive())

    def stop(self, timeout: float = 5.0) -> bool:
        """Ask the worker to stop and wait up to `timeout`. True when its thread has ended: a batch
        being embedded finishes first, and only then is nothing more written."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
            return not self._thread.is_alive()
        return True

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
