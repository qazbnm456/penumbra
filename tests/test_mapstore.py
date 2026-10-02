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


def test_the_order_comes_from_the_first_capture_filed_not_the_file_time():
    """Every save writes a new orbit file and renames it over the old one, so a file's birth time is
    its last save. The first capture filed into an orbit does not move."""
    from penumbra import horizon
    from penumbra.schema import Source, SourceBlock

    def filed(orbit_id: str, origin: str, at: float) -> None:
        block = SourceBlock(locator="whole", text="x")
        node = horizon.add_node(Source(id="s1", kind="text", origin=origin, blocks=[block]))
        with horizon._connect() as conn:
            conn.execute(
                "INSERT INTO memberships (node_id, orbit_id, source_id, promoted_at) VALUES (?, ?, 's1', ?)",
                (node.id, orbit_id, at),
            )

    filed("late", "pasted:a", 50.0)
    filed("early", "pasted:b", 10.0)
    # The fallbacks say the opposite; the memberships win. "bare" has none, so its fallback counts.
    got = mapstore.placements([("late", 1.0), ("early", 99.0), ("bare", 30.0)])
    order = sorted(got, key=lambda key: got[key]["placed_at"])
    assert order == ["early", "bare", "late"]
    assert got["early"]["angle"] == pytest.approx(mapstore.slot_angle(0, 0))


def test_all_places_reads_what_is_stored_for_the_export():
    mapstore.placements([("a", 1.0)])
    mapstore.place("a", 4, 0.5)
    stored = mapstore.all_places()["a"]
    assert (stored["ring"], stored["angle"]) == (4, 0.5)


def test_settings_default_and_a_new_slot_rule_rearranges_every_planet():
    """The reader chose this: changing how many planets a ring holds rearranges the whole map,
    dragged planets included. Changing only the ring sizes or the sky moves nothing."""
    assert mapstore.settings() == mapstore.DEFAULT_SETTINGS
    mapstore.placements([("a", 1.0), ("b", 2.0), ("c", 3.0)])
    mapstore.place("a", 5, 1.0)
    events = {**mapstore.DEFAULT_SETTINGS["events"], "comet": "off"}
    bigger = {**mapstore.DEFAULT_SETTINGS, "inner_ring": 300, "events": events}
    _, rearranged = mapstore.save_settings(bigger)
    assert not rearranged and mapstore.all_places()["a"]["ring"] == 5
    assert mapstore.settings()["events"]["comet"] == "off"
    one_each = {**bigger, "first_ring_slots": 1, "slots_step": 1}
    _, rearranged = mapstore.save_settings(one_each)
    assert rearranged and mapstore.all_places() == {}
    got = mapstore.placements([("a", 1.0), ("b", 2.0), ("c", 3.0)])
    assert [got[k]["ring"] for k in ("a", "b", "c")] == [0, 1, 1], "ring 0 holds one, ring 1 two"


def test_settings_out_of_bounds_are_refused_never_clamped():
    good = mapstore.DEFAULT_SETTINGS
    for bad in (
        {**good, "inner_ring": 50},
        {**good, "first_ring_slots": 0},
        {**good, "ring_gap": 1.5},
        {**good, "slots_step": True},
        {**good, "events": {**good["events"], "comet": "always"}},
        {**good, "events": {"meteor": "off"}},
        {k: v for k, v in good.items() if k != "ring_gap"},
        {**good, "extra": 1},
    ):
        with pytest.raises(ValueError):
            mapstore.validate_settings(bad)
