"""The Horizon's text and its kit memory: one `rlm_harness.memory.MemoryStore` per Horizon directory.

A capture becomes an item in this store when it has text (invariant 79 keeps the lifecycle before
that in the Horizon's own `index.db`). The store lives beside the index, in `memory.db`, rather than
inside it, because the kit and the Horizon each number their schema in `PRAGMA user_version` and one
file can hold only one count.

**Opened with three settings that are this product's, not the kit's defaults.** No character cap
on an item, since a Horizon capture has never had one (only an orbit has, invariant 8); the search
index reads the first 1,000,000 characters of each text, the bound the Horizon's own index already
kept; and origins are indexed, since a URL is often the one word a reader remembers.

One store per resolved directory, cached for the process, like `horizon._INITIALIZED`: it holds no
connection (the kit opens one per operation), so sharing it across the intake thread, the summary
pass and request handlers is what the kit designs for.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from rlm_harness.memory import MemoryStore, vectors_path

#: The file the store lives in, inside the Horizon directory.
STORE_FILE = "memory.db"

#: How much of each capture's text the search index reads; the item keeps all of it.
INDEX_CHARS = 1_000_000

_STORES: dict[str, MemoryStore] = {}
_LOCK = threading.Lock()


def store_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / STORE_FILE


def store(base_dir: str | Path) -> MemoryStore:
    """The store for this Horizon directory, created on first use and again if its file was removed
    under a running process (the same reason `horizon._initialize` re-checks the path)."""
    path = store_path(base_dir)
    key = str(path.resolve())
    with _LOCK:
        cached = _STORES.get(key)
        if cached is not None and path.exists():
            return cached
        opened = MemoryStore(path, max_item_chars=sys.maxsize, max_index_chars=INDEX_CHARS,
                             index_origins=True)
        _STORES[key] = opened
        return opened


def erase(base_dir: str | Path) -> None:
    """Delete the store's files (and its vectors file, when there is one) and drop the cached store.
    For clearing everything: the next `store()` creates an empty one."""
    path = store_path(base_dir)
    with _LOCK:
        _STORES.pop(str(path.resolve()), None)
        for candidate in (path, vectors_path(path)):
            for suffix in ("", "-wal", "-shm"):
                Path(f"{candidate}{suffix}").unlink(missing_ok=True)
