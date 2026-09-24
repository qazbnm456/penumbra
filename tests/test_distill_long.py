"""`DistillLongDocument`, driven through a real offline forward pass (the `test_guide.py` pattern):
no live model, no Deno, no network."""

from __future__ import annotations

import asyncio
import json

import pytest

dspy = pytest.importorskip("dspy")

import rlm_harness.runtime as rt
from rlm_harness import RLMConfig
from rlm_harness.testing import ScriptedInterpreter, assert_repl_safe, call, scripted_lm, submit

from penumbra.distill_long import DistillLongDocument

_SOURCES = "[[SRC:s1|page:1]]\nSlow-wave sleep and the hippocampus.\n\n[[SRC:s1|page:2]]\nREM sleep."


def _configure(turns) -> None:
    dummy = scripted_lm(turns)
    rt.configure(
        RLMConfig(main_model="x", sub_model="x", interpreter="pyodide", observe=False),
        main_lm=dummy,
        sub_lm=dummy,
    )


def test_the_only_tool_is_its_validator_and_it_is_repl_safe():
    _configure([])
    tools = DistillLongDocument(skills_dir=None).tools
    assert {getattr(t, "__name__", "") for t in tools} == {"validate_longdistillation"}
    for tool in tools:
        assert_repl_safe(tool)


def test_an_entity_with_an_invented_coordinate_is_refused_before_submit():
    bad = {"title": "T", "summary": "S", "tags": ["sleep"],
           "entities": [{"name": "REM", "source_id": "s1", "locator": "Chapter One"}]}
    good = {"title": "T", "summary": "S", "tags": ["sleep"],
            "entities": [{"name": "REM", "source_id": "s1", "locator": "page:2"}]}
    _configure([
        {"reasoning": "validate", "code": "validate_longdistillation(...)"},
        {"reasoning": "fix and validate again", "code": "validate_longdistillation(...)"},
        {"reasoning": "submit", "code": "SUBMIT"},
    ])
    verdicts = []
    task = DistillLongDocument(skills_dir=None, interpreter=ScriptedInterpreter(steps=[
        call("validate_longdistillation", data_json_str=json.dumps(bad)),
        call("validate_longdistillation", data_json_str=json.dumps(good)),
        submit({"distillation": good}),
    ]))
    validator = task.tools[0]

    def spy(data_json_str: str) -> str:
        verdict = validator(data_json_str)
        verdicts.append(verdict)
        return verdict

    spy.__name__ = validator.__name__
    task.tools = [spy]
    result = asyncio.run(task.arun(sources=_SOURCES, section_map="page:1 ...", output_language="English"))
    assert verdicts[0].startswith("Validation failed") and "Chapter One" in verdicts[0]
    assert not verdicts[1].startswith("Validation failed")
    assert result.entities[0].locator == "page:2"
