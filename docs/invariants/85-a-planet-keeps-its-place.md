# Invariant 85: A planet keeps its place until the reader moves it

**Where an orbit sits on the star map is a ring and an angle, given once by `mapstore.placements` (outward in creation order, into the first free slot) and changed only by the reader dragging it (`PUT /horizon/map/planets/{orbit}`). Nothing about an orbit's activity, size or order in a list decides where its planet is drawn.**

## Why a place is not derived

Planets used to be placed by their index in the orbit list sorted by recency, the newer the nearer the centre. Every write to an orbit changed that order: moving a capture from one orbit to another writes both files, so the two planets traded places, and a chat turn or an overview did the same. A map whose planets move whenever anything happens cannot be learnt, and the reader could not arrange it. `planetLayout` now reads each planet's place on its own, and `tests/test_web_behaviour.py::test_each_planet_sits_at_its_own_place_whatever_the_order_or_the_neighbours` fails if a place comes from the list order again.

## Why the server keeps it

A place is presentation, but it is the reader's arrangement, so it lives with their data rather than in one browser: in the Horizon's database (`map_planets`, created by migration step 3), which travels with Export everything and is emptied by clearing everything. A place for an orbit that no longer exists is dropped when the map is next read, which frees its slot. Writing a place never touches the orbit file, so its mtime, and everything that reads it, is unaffected.

## The shape of a place

- The angle is the planet's place at the start of its turn; the map turns it from there at its ring's pace. A planet dropped while the map has been turning for a while is shifted in that page by how far the map had turned (`starMap.dropShift`), so it stays where it was let go, and a fresh page shows it at the stored angle.
- Automatic placement uses `3 + 3i` evenly spaced slots on ring `i`, and a slot is free when no planet sits within half a slot's width of it. A dragged planet can sit at any angle, and several may share a ring past its slots; the map fades whichever is behind while two overlap.
- A drag snaps to the ring whose ellipse is nearest, out to one ring beyond the outermost in use, so the map grows outward only when the reader takes a planet there.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
