"""A capture's labels read from the kit's memory store: through any path, with no store yet, and the
alias table as the readers see it. Offline, real SQLite in the tmp_path conftest moves into."""

from __future__ import annotations

from pathlib import Path

from penumbra import concepts, distill, horizon, memory_store
from penumbra.schema import Source, SourceBlock
from tests._labels import label, labels


def _source(origin: str, text: str = "a note") -> Source:
    return Source(id="s0", kind="web", origin=origin, blocks=[SourceBlock(locator="whole", text=text)])


def test_labels_are_read_through_a_store_path_with_any_character():
    """An unencoded `#` or `?` in the attach URI silently attaches an empty database."""
    base = Path("Application Support #1 %20 ?x")
    node = horizon.add_node(_source("pasted:x"), base_dir=base)
    label(node.id, base_dir=base, title="Found", tags=["kept"])
    got = horizon.get_node(node.id, base_dir=base)
    assert (got.title, got.tags) == ("Found", ["kept"])
    assert [n.id for n in horizon.list_nodes(base_dir=base, filters=horizon.NodeFilter(tags=("Kept",)))] \
        == [node.id]


def test_a_missing_store_reads_as_no_labels_and_is_made_again():
    node = horizon.add_node(_source("pasted:y"))
    label(node.id, title="Gone soon")
    memory_store.erase(horizon.DEFAULT_HORIZON_DIR)
    got = horizon.get_node(node.id)
    assert got is not None and got.title is None
    assert memory_store.store_path(horizon.DEFAULT_HORIZON_DIR).exists()


def test_only_a_merged_name_is_offered_to_separate_and_any_spelling_separates_it():
    a = horizon.add_node(_source("pasted:a", "Kubernetes notes"))
    b = horizon.add_node(_source("pasted:b", "kubernetes again"))
    c = horizon.add_node(_source("pasted:c", "K8s cluster"))
    label(a.id, entities=["Kubernetes"])
    label(b.id, entities=["kubernetes"])
    label(c.id, entities=["K8s"])
    memory_store.store(horizon.DEFAULT_HORIZON_DIR).merge("K8s", "Kubernetes")
    assert concepts.alias_groups() == {"Kubernetes": ["K8s"]}, "a case variant is not a merge"
    assert concepts.resolver()("kubernetes") == "Kubernetes"
    assert concepts.remove_alias("k8S") is True and concepts.remove_alias("K8s") is False
    assert concepts.alias_groups() == {}


def test_a_pass_stops_between_captures_and_takes_no_more_than_its_limit():
    for n in range(4):
        horizon.add_node(_source(f"pasted:{n}", f"note {n}"))
    calls: list = []
    distill.distil_pending(limit=2, run_short=lambda f: calls.append(f) or labels(title="T", summary="S"))
    assert len(calls) == 2
    stopped: list = []
    distill.distil_pending(run_short=lambda f: stopped.append(f) or labels(title="T", summary="S"),
                           should_stop=lambda: len(stopped) >= 1)
    assert len(stopped) == 1, "stopped before the next capture"
    assert len(horizon.waiting_ids()) == 1
