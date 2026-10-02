"""Tests do not inherit dspy's configuration owner from one another (`conftest._dspy_owned_by_no_thread`).

The two tests run in file order on purpose: the first does what an API test's summary pass does
(configures dspy from a background thread), the second does what every offline task test does
(configures a scripted LM from the main thread) and checks it took. Without the conftest reset the
second silently keeps the first's LM, which is how `test_guide.py`'s offline passes ended up calling
OpenAI whenever `test_api_horizon.py` ran first.
"""

from __future__ import annotations

import threading

import pytest

dspy = pytest.importorskip("dspy")


def test_a_background_thread_configures_dspy_first():
    real = dspy.LM("openai/gpt-4o-mini", api_key="sk-test")
    worker = threading.Thread(target=lambda: dspy.configure(lm=real))
    worker.start()
    worker.join()
    assert dspy.settings.lm is real


def test_the_next_test_can_still_configure_dspy_on_its_own_thread():
    import rlm_harness as rt
    from rlm_harness.config import RLMConfig
    from rlm_harness.testing import scripted_lm

    dummy = scripted_lm([])
    rt.configure(RLMConfig(main_model="x", sub_model="x", interpreter="pyodide", observe=False),
                 main_lm=dummy, sub_lm=dummy)
    assert dspy.settings.lm is dummy, "a previous test's thread still owns dspy's configuration"
