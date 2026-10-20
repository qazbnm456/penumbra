"""Concept alignment's memory, read from the kit: which entity names are the same thing.

Summaries are written one capture at a time, so the same entity arrives under several names
(`Matthew Walker`, `馬修·沃克`, `M. Walker`). The kit's alignment pass (`align_pending`, run at the end of
a pressed summary pass, `api._align_after_pass`) decides which are the same and keeps the answer as
an alias table in the memory store; no label is rewritten, and every reader applies the table when it
reads. A reader's own decision is a `said` row: removing a merge here is `unmerge`, which also keeps
a later pass from merging the two again.

Names are compared the way the store compares them (`fold_name`: NFKC, casefolded, spaces
collapsed), so case and width variants of a canonical read as the canonical too. What a reader is
shown is the names as summaries wrote them (`entity_names`), grouped by how they are read.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from rlm_harness.memory import fold_name

from . import memory_store
from .horizon import DEFAULT_HORIZON_DIR


def readings(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict[str, str]:
    """Folded name -> the name it is read as (the kit's own map)."""
    return memory_store.store(base_dir).readings()


def resolver(*, base_dir: str | Path = DEFAULT_HORIZON_DIR):
    """A function mapping a name to the name it is read as, for a reader applying the table."""
    table = readings(base_dir=base_dir)
    return lambda name: table.get(fold_name(name), name)


def all_names(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict[str, int]:
    """Every entity name the current labels carry, as written, with how many captures name it."""
    return memory_store.store(base_dir).entity_names()


def alias_groups(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict[str, list[str]]:
    """Each canonical that other spellings are read as, with those spellings as summaries wrote them
    (the graph's "Also written as"), sorted."""
    read = resolver(base_dir=base_dir)
    merged = aliases(base_dir=base_dir)
    groups: dict[str, set[str]] = defaultdict(set)
    for name in all_names(base_dir=base_dir):
        # Merged names only: a case variant of the canonical reads as it too, but nothing merged it,
        # so there is nothing to separate.
        if fold_name(name) in merged:
            groups[read(name)].add(name)
    return {canonical: sorted(names) for canonical, names in groups.items()}


def names_for(canonical: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> list[str]:
    """`canonical` and every spelling read as it: what a scope on that entity has to match."""
    read = resolver(base_dir=base_dir)
    target = read(canonical)
    spellings = sorted(name for name in all_names(base_dir=base_dir)
                       if read(name) == target and name != target)
    return [target, *spellings]


def aliases(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict[str, str]:
    """Every live alias, folded alias name -> canonical (the kit's table, for the export)."""
    return memory_store.store(base_dir).aliases()


def remove_alias(alias: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> bool:
    """Undo one merge, named by any spelling of the alias. A reader's decision: a later alignment
    pass never merges the two again. False when the name is not merged into anything."""
    store = memory_store.store(base_dir)
    if fold_name(alias) not in store.aliases():
        return False
    store.unmerge(alias, provenance="said")
    return True
