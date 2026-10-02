# Invariant 85: A planet keeps its place until the reader moves it

**Where an orbit sits on the star map is a ring and an angle, given once by `mapstore.placements` (outward in the order orbits began, into the first free slot) and changed only by the reader: by dragging it (`PUT /horizon/map/planets/{orbit}`), or by changing how many planets a ring holds in the map's settings, which places every planet again (`mapstore.save_settings`). Nothing about an orbit's activity, size or order in a list decides where its planet is drawn.**

## Why a place is not derived

Planets used to be placed by their index in the orbit list sorted by recency, the newer the nearer the centre. Every write to an orbit changed that order: moving a capture from one orbit to another writes both files, so the two planets traded places, and a chat turn or an overview did the same. A map whose planets move whenever anything happens cannot be learnt, and the reader could not arrange it. `planetLayout` now reads each planet's place on its own, and `tests/test_web_behaviour.py::test_each_planet_sits_at_its_own_place_whatever_the_order_or_the_neighbours` fails if a place comes from the list order again.

## Why the server keeps it

A place is presentation, but it is the reader's arrangement, so it lives with their data rather than in one browser: in the Horizon's database (`map_planets`, created by migration step 3). Export everything writes it to `data/map.json`, and clearing everything empties it. A place for an orbit that no longer exists is dropped when the map is next read, which frees its slot. Writing a place never touches the orbit file, so its mtime, and everything that reads it, is unaffected.

## When an orbit began

The order is the first capture filed into each orbit (`memberships.promoted_at`), and an orbit's file time only for an orbit nothing was ever filed into. The file's birth time is not usable: `orbit.save_orbit` writes a new file and renames it over the old one, so its birth time is its last save, and ordering by it would place planets by activity again. The places come from the orbit files by their stems, so an orbit whose file does not parse keeps its planet's place rather than being taken for deleted.

## The shape of a place

- The angle is the planet's place at the start of its turn; the map turns it from there at its ring's pace. A planet dropped while the map has been turning for a while is shifted in that page by how far the map had turned (`starMap.dropShift`), so it stays where it was let go, and a fresh page shows it at the stored angle.
- Automatic placement uses `first + step × i` evenly spaced slots on ring `i` (3 and 3 by default, set in the map's settings), so fewer slots set planets further apart. Changing either number rearranges every planet, the dragged ones included, because the reader asked for a new arrangement; changing the ring sizes moves nothing, since a place is a ring and an angle and the planet scales with its ring.
- Automatic placement fills rings out to `mapstore.MAX_RING` (40). With one place on the inner ring and none added per ring, that is 41 places, and every orbit past them shares the outermost ring's first slot until the reader drags it or chooses more places per ring.
- A slot is free when no planet sits within half a slot's width of it. A dragged planet can sit at any angle, and several may share a ring past its slots; the map fades whichever is behind while two overlap.
- A drag snaps to the ring whose ellipse is nearest, out to one ring beyond the outermost in use, so the map grows outward only when the reader takes a planet there.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
