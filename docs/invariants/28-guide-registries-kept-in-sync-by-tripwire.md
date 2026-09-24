# Invariant 28: Guide registries are kept in sync by a tripwire

**`cli._GUIDE_TASKS` and `api._GUIDE_TASKS` are two independent registries kept in sync by the tripwire `test_api.py::test_guide_task_registries_stay_in_sync_between_cli_and_api`, not by shared code.**

Invariant 20 explains why `api.py` does not import from `cli.py`. A new guide kind must be added to both dictionaries; if it is added to one, the tripwire fails at once instead of the two drifting apart silently.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
