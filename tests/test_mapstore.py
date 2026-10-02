"""Where planets sit on the star map (`mapstore.py`): placed once, outward in creation order, then
the reader's. Their place used to follow recency, so filing one capture swapped two planets."""

from __future__ import annotations

import math

import pytest

from penumbra import mapstore


def test_new_orbits_are_placed_outward_in_the_order_they_were_created():
    got = mapstore.placements([("c", 3.0), ("a", 1.0), ("b", 2.0), ("d", 4.0)])
    assert [got[k]["ring"] for k in ("a", "b", "c", "d")] == [0, 0, 0, 1], "ring 0 holds three"
    assert got["a"]["angle"] == pytest.approx(mapstore.slot_angle(0, 0))
    assert got["b"]["angle"] == pytest.approx(mapstore.slot_angle(0, 1))


def test_a_place_never_moves_when_others_come_and_go():
    """The swap the reader saw: activity elsewhere must not move a planet."""
    first = mapstore.placements([("a", 1.0), ("b", 2.0)])
    again = mapstore.placements([("a", 1.0), ("b", 2.0), ("new", 0.5)])
    assert again["a"] == first["a"] and again["b"] == first["b"]
    assert again["new"]["ring"] == 0 and again["new"]["angle"] == pytest.approx(mapstore.slot_angle(0, 2))


def test_a_dragged_planet_keeps_its_place_and_a_removed_orbit_frees_its_slot():
    mapstore.placements([("a", 1.0), ("b", 2.0)])
    moved = mapstore.place("a", 2, 7.0)
    assert moved["ring"] == 2 and moved["angle"] == pytest.approx(math.remainder(7.0, math.tau))
    assert mapstore.placements([("a", 1.0), ("b", 2.0)])["a"]["ring"] == 2
    # "b" is removed; a new orbit takes the first free slot on ring 0, which "a" left.
    got = mapstore.placements([("a", 1.0), ("c", 3.0)])
    assert "b" not in got and got["c"]["ring"] == 0
    assert got["c"]["angle"] == pytest.approx(mapstore.slot_angle(0, 0))


def test_a_slot_a_planet_was_dragged_onto_is_taken():
    mapstore.place("a", 0, mapstore.slot_angle(0, 0) + 0.1)
    got = mapstore.placements([("a", 1.0), ("b", 2.0)])
    assert got["b"]["angle"] == pytest.approx(mapstore.slot_angle(0, 1))


def test_place_refuses_a_ring_out_of_range_or_a_non_finite_angle():
    for ring, angle in ((-1, 0.0), (mapstore.MAX_RING + 1, 0.0), (0, math.nan), (0, math.inf)):
        with pytest.raises(ValueError):
            mapstore.place("a", ring, angle)
