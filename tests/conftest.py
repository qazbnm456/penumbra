"""Test-wide isolation.

`config.settings_path`, `orbit.DEFAULT_ORBITS_DIR` and `api._TRACE_DIR` are all resolved
against the process's working directory, so without this a test run picks up whatever the developer
happens to have in their own `orbits/` — and a settings file written by a live check silently
changed the result of an unrelated TTS test. That is the same class of failure a sibling
project's ASR-locale design note records: an instrument that does not reproduce production's shape
returns the right answer to the wrong question.

Default arguments bind at definition time (`def settings_path(base_dir=_DEFAULT_ORBITS_DIR)`), so
monkeypatching the constant would not help — the working directory is the only lever that reaches
every caller. `test_api.py` and `test_cli.py` already did this per-file; this makes it the floor for
every test rather than something each file has to remember.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def _dspy_owned_by_no_thread():
    """**Every test starts with dspy configurable from the thread it runs on.**

    dspy lets only the thread that FIRST called `dspy.configure` call it again, and
    `rlm_harness.configure` swallows the `RuntimeError` it raises otherwise. The API configures the
    real model in-process from a summary pass's background thread (`api._configure_in_process_model`),
    so after one API test had run a pass, a later test's `rt.configure(main_lm=scripted)` on the main
    thread silently changed nothing, and its "offline" run called OpenAI with a fake key: six
    failures whenever `test_api_horizon.py` ran before `test_guide.py`, hidden only by the suite's
    usual order. Measured, not guessed: a thread's `dspy.configure` followed by a main-thread
    `rt.configure` left `dspy.settings.lm` the thread's LM.

    Reset after each test, and only for modules already imported, so a bare `uv sync` (no dspy, no
    `api` extra) is unaffected.
    """
    yield
    import sys

    settings = sys.modules.get("dspy.dsp.utils.settings")
    if settings is not None:
        settings.config_owner_thread_id = None
        settings.config_owner_async_task = None
    api = sys.modules.get("penumbra.api")
    if api is not None:
        api._MODEL_CONFIGURED = False
