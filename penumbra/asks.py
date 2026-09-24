"""The Horizon's ask history: questions asked over the whole Horizon, a tag or an entity.

A question about one orbit is asked inside that orbit and joins its conversation. Everything wider
has no orbit to belong to, so it is kept here, in the Horizon's own `index.db`, one row per ask.
Rows are only ever inserted or deleted, never rewritten, so there is no snapshot to go stale
(invariant 78's delta rule).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path

from . import horizon
from .horizon import DEFAULT_HORIZON_DIR
from .schema import Answer, AskSource, HorizonAsk

_log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS asks (
    id          TEXT PRIMARY KEY,
    created_at  REAL NOT NULL,
    scope_kind  TEXT NOT NULL,
    scope_value TEXT,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    sources     TEXT NOT NULL,
    strategy    TEXT NOT NULL,
    run_id      TEXT
);
CREATE INDEX IF NOT EXISTS asks_created ON asks(created_at DESC);
"""

_READY: set[str] = set()
_READY_LOCK = threading.Lock()


def _ensure(conn) -> None:
    key = str(conn.execute("PRAGMA database_list").fetchone()[2])
    with _READY_LOCK:
        if key in _READY and Path(key).exists():
            return
        conn.executescript(_SCHEMA)
        _READY.add(key)


def is_ask_id(value: str) -> bool:
    return len(value) == 16 and value.startswith("ask-") and all(c in "0123456789abcdef" for c in value[4:])


def _row(row) -> HorizonAsk:
    return HorizonAsk(
        id=row["id"],
        created_at=row["created_at"],
        scope_kind=row["scope_kind"],
        scope_value=row["scope_value"],
        question=row["question"],
        answer=Answer.model_validate_json(row["answer"]),
        sources=[AskSource.model_validate(s) for s in json.loads(row["sources"])],
        strategy=row["strategy"],
        run_id=row["run_id"],
    )


def add_ask(
    *,
    scope_kind: str,
    scope_value: str | None,
    question: str,
    answer: Answer,
    sources: list[AskSource],
    strategy: str,
    run_id: str | None,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> HorizonAsk:
    record = HorizonAsk(
        id=f"ask-{uuid.uuid4().hex[:12]}",
        created_at=time.time(),
        scope_kind=scope_kind,
        scope_value=scope_value,
        question=question,
        answer=answer,
        sources=sources,
        strategy=strategy,
        run_id=run_id,
    )
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        conn.execute(
            "INSERT INTO asks (id, created_at, scope_kind, scope_value, question, answer, sources, "
            "strategy, run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.created_at,
                record.scope_kind,
                record.scope_value,
                record.question,
                answer.model_dump_json(),
                json.dumps([s.model_dump() for s in sources], ensure_ascii=False),
                record.strategy,
                record.run_id,
            ),
        )
    return record


def get_ask(ask_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> HorizonAsk | None:
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        row = conn.execute("SELECT * FROM asks WHERE id = ?", (ask_id,)).fetchone()
    return _row(row) if row is not None else None


def list_asks(
    *, limit: int = 50, offset: int = 0, base_dir: str | Path = DEFAULT_HORIZON_DIR
) -> list[HorizonAsk]:
    """Newest first."""
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        rows = conn.execute(
            "SELECT * FROM asks ORDER BY created_at DESC, id ASC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
    # One unreadable row must not cost the whole history, the rule `horizon.list_nodes` follows.
    out: list[HorizonAsk] = []
    for row in rows:
        try:
            out.append(_row(row))
        except (ValueError, TypeError) as exc:
            _log.warning("asks: skipping unreadable row %r (%s)", row["id"], exc)
    return out


def remove_ask(ask_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> bool:
    with horizon._connect(base_dir) as conn:
        _ensure(conn)
        return bool(conn.execute("DELETE FROM asks WHERE id = ?", (ask_id,)).rowcount)
