"""What the rename from rlm-notebook to Penumbra left on disk and in the environment.

Two things outlive a rename, and both are handled here once, at startup, rather than scattered
through the code that reads them:

- **Data folders.** `notebooks/` is `orbits/` and `inbox/` is `horizon/` now. The files inside
  never carried the old names (the one database column that did is renamed by
  `horizon._migrate_legacy_schema`), so moving the folder is the whole migration.
- **Environment variables.** Every `RN_*` setting is `PN_*` now. An old name is reported and
  NOT honoured: silently mapping it would keep two spellings alive forever, and a run that finds
  no model fails fast with a message naming `PN_MAIN_MODEL`, which costs nothing.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

LEGACY_DIRS = (("notebooks", "orbits"), ("inbox", "horizon"))


def migrate_data_dirs(base: str | Path = ".") -> list[tuple[str, str]]:
    """Rename each legacy data folder under `base` whose new name is still free. Returns the moves
    made. A folder is never merged into an existing one: if both exist, both are left alone."""
    moved = []
    for old, new in LEGACY_DIRS:
        source, target = Path(base) / old, Path(base) / new
        if source.is_dir() and not target.exists():
            source.rename(target)
            moved.append((old, new))
    return moved


def stranded_dirs(base: str | Path = ".") -> list[tuple[str, str]]:
    """Legacy folders left in place because their new name was already taken. Their data is still
    there and nothing reads it, so the caller has to say so rather than let it look lost."""
    return [
        (old, new)
        for old, new in LEGACY_DIRS
        if (Path(base) / old).is_dir() and (Path(base) / new).exists()
    ]


def legacy_env_names(environ: Mapping[str, str] | None = None) -> list[str]:
    """The `RN_*` variables still set, which Penumbra no longer reads."""
    env = os.environ if environ is None else environ
    return sorted(name for name in env if name.startswith("RN_"))
