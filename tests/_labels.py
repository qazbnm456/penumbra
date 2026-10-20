"""Test helpers for a capture's labels, which live in the kit's memory store.

`label` writes them as the summary pass would (`inferred` rows) and moves the capture to `ready`,
so a test can set up a summarised capture without a model; `labels` is what a stand-in for the
pass's short step returns.
"""

from __future__ import annotations

from penumbra import horizon, memory_store


def label(
    node_id: str,
    *,
    base_dir=horizon.DEFAULT_HORIZON_DIR,
    state: str | None = "ready",
    provenance: str = "inferred",
    **labels,
):
    """Write `labels` (title, summary, tags, entities) for a capture that is a kit item, as the
    summary pass would, and set its state (`None` leaves it). Returns the node as it now is."""
    node = horizon.get_node(node_id, base_dir=base_dir)
    assert node is not None and node.id.startswith("m"), f"{node_id} is not a stored capture"
    if labels:
        memory_store.store(base_dir).label(node.id, provenance=provenance, **labels)
    fields = {"state": state} if state is not None else {}
    horizon.update_node(node.id, base_dir=base_dir, **fields)   # bumps updated_at, as the pass does
    return horizon.get_node(node.id, base_dir=base_dir)


def labels(title: str = "", summary: str = "", tags=(), entities=()) -> dict:
    """What a stand-in for the summary pass's short step returns."""
    return {"title": title, "summary": summary, "tags": list(tags), "entities": list(entities)}
