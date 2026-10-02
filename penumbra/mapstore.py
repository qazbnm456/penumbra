"""Where each orbit sits on the star map: a ring and an angle, kept server-side in the Horizon's
database (`map_planets`, added by `horizon._MIGRATIONS`).

**Placed once, then the reader's.** A planet's place used to follow how recently its orbit gained
something, newest innermost, so filing one capture swapped two planets and every chat turn could
reorder the map. Now an orbit is given a place the first time the map sees it, outward in the
order the orbits were created, and keeps it until the reader drags it somewhere else. Time plays
no further part.

The angle is the planet's place at the start of its orbit; the map turns it from there. Ring `i`
offers `3 + 3i` evenly spaced slots for automatic placement, each ring turned a little so planets do
not line up radially. A dragged planet can sit at any angle on any ring, and several may share a
ring beyond its slots; the map fades whichever is behind while two overlap.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

from . import horizon

#: The furthest ring a planet may be placed on, by hand or automatically. Far beyond what a map
#: shows comfortably; it bounds the value a request can store, not the reader.
MAX_RING = 40


def ring_slots(ring: int) -> int:
    """How many evenly spaced places automatic placement uses on `ring`: the outer rings are longer."""
    return 3 + 3 * ring


def slot_angle(ring: int, slot: int) -> float:
    return -math.pi / 2 + (slot / ring_slots(ring)) * math.pi * 2 + ring * 0.7


def _free_place(taken: dict[int, list[float]]) -> tuple[int, float]:
    """The first ring with a free slot, and that slot's angle. A slot is free when no planet on the
    ring sits within half a slot's width of it, so a planet dragged onto a slot takes it."""
    for ring in range(MAX_RING + 1):
        width = math.pi * 2 / ring_slots(ring)
        for slot in range(ring_slots(ring)):
            angle = slot_angle(ring, slot)
            others = taken.get(ring, [])
            if all(abs(math.remainder(angle - other, math.pi * 2)) >= width / 2 for other in others):
                return ring, angle
    return MAX_RING, slot_angle(MAX_RING, 0)


def placements(
    orbits: list[tuple[str, float]], *, base_dir: str | Path = horizon.DEFAULT_HORIZON_DIR
) -> dict:
    """Every orbit's place, `{slug: {"ring", "angle", "placed_at"}}`, for `orbits` given as
    `(slug, created)` pairs. An orbit without a place gets the first free slot, in the order the
    orbits were created; a place whose orbit no longer exists is dropped, so its slot is free again.
    One transaction, so two maps opening at once cannot give two orbits the same slot."""
    present = {key for key, _ in orbits}
    with horizon._connect(base_dir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            rows = {row["orbit_id"]: dict(row) for row in conn.execute("SELECT * FROM map_planets")}
            for gone in set(rows) - present:
                conn.execute("DELETE FROM map_planets WHERE orbit_id = ?", (gone,))
                del rows[gone]
            taken: dict[int, list[float]] = {}
            for row in rows.values():
                taken.setdefault(row["ring"], []).append(row["angle"])
            now = time.time()
            unplaced = sorted((o for o in orbits if o[0] not in rows), key=lambda o: (o[1], o[0]))
            for key, _created in unplaced:
                ring, angle = _free_place(taken)
                conn.execute(
                    "INSERT INTO map_planets (orbit_id, ring, angle, placed_at) VALUES (?, ?, ?, ?)",
                    (key, ring, angle, now),
                )
                rows[key] = {"orbit_id": key, "ring": ring, "angle": angle, "placed_at": now}
                taken.setdefault(ring, []).append(angle)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return {
        key: {"ring": row["ring"], "angle": row["angle"], "placed_at": row["placed_at"]}
        for key, row in rows.items()
    }


def place(
    orbit_slug: str, ring: int, angle: float, *, base_dir: str | Path = horizon.DEFAULT_HORIZON_DIR
) -> dict:
    """The reader moved a planet: it sits at `angle` on `ring` from now on. The angle is kept in
    one turn, (-pi, pi]."""
    if not 0 <= ring <= MAX_RING:
        raise ValueError(f"ring must be between 0 and {MAX_RING}")
    if not math.isfinite(angle):
        raise ValueError("angle must be a finite number")
    angle = math.remainder(angle, math.pi * 2)
    now = time.time()
    with horizon._connect(base_dir) as conn:
        conn.execute(
            "INSERT INTO map_planets (orbit_id, ring, angle, placed_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(orbit_id) DO UPDATE SET ring = excluded.ring, angle = excluded.angle",
            (orbit_slug, ring, angle, now),
        )
    return {"ring": ring, "angle": angle}
