"""`distill.py`: the summary pass, on the kit's labelling pass, around the Horizon's captures.

No `importorskip` and no model: every test passes its own `run_short` (and `run_long`), so the host's
half — which captures, their state, what counts as their failure, a capture with no text, a capture
removed mid-pass, the language — runs for real against the kit's store.
"""

from __future__ import annotations

from pathlib import Path

from penumbra import distill, horizon, memory_store
from penumbra.schema import Source, SourceBlock
from tests._labels import labels

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _source(origin: str = "https://example.com/a", text: str = "the body text") -> Source:
    return Source(id="s0", kind="web", origin=origin, blocks=[SourceBlock(locator="whole", text=text)])


def _captured(text: str = "the body text", origin: str = "https://example.com/a"):
    """A capture at `ready_undistilled`, which is what intake leaves behind."""
    return horizon.add_node(_source(origin, text), origin_is_the_identity=True)


def _short(answer: dict | None = None, *, seen: list | None = None, raises: Exception | None = None):
    def run(fields: dict) -> dict:
        if seen is not None:
            seen.append(fields)
        if raises is not None:
            raise raises
        return answer or labels(title="T", summary="S", tags=["Sleep"], entities=["hippocampus"])
    return run


def _store():
    return memory_store.store(horizon.DEFAULT_HORIZON_DIR)


# --- the pass writes the kit's labels and the capture's state ---------------------------------------


def test_a_pass_labels_each_waiting_capture_and_moves_it_to_ready():
    node = _captured("the hippocampus and memory during sleep")
    done = distill.distil_pending(run_short=_short())
    assert done == [node.id]
    after = horizon.get_node(node.id)
    assert (after.state, after.title, after.summary) == ("ready", "T", "S")
    assert after.tags == ["sleep"], "folded as the store keeps tags"
    assert after.entities == ["hippocampus"] and after.distilled_at is not None
    assert _store().labels(node.id).provenance["title"] == "inferred"
    assert horizon.waiting_ids() == []


def test_a_step_is_given_its_own_fields_only():
    _captured("a short note about tides")
    seen: list = []
    distill.distil_pending(run_short=_short(seen=seen), language="Traditional Chinese")
    assert set(seen[0]) == {"text", "language", "known"}
    assert seen[0]["text"] == "a short note about tides" and seen[0]["language"] == "Traditional Chinese"


def test_the_operators_language_wins_over_the_callers(monkeypatch):
    monkeypatch.setenv("PN_OUTPUT_LANGUAGE", "Japanese")
    _captured()
    seen: list = []
    distill.distil_pending(run_short=_short(seen=seen), language="English")
    assert seen[0]["language"] == "Japanese"


def test_a_title_the_reader_set_outranks_the_summary_before_or_after_it():
    node = _captured()
    horizon.edit_node(node.id, title="Mine", tags=["kept"])
    distill.distil_pending(run_short=_short(labels(title="Model's", summary="S", tags=["other"])))
    after = horizon.get_node(node.id)
    assert (after.title, after.tags, after.summary) == ("Mine", ["kept"], "S")
    assert after.edited == ["title", "tags"]


def test_a_capture_with_no_text_is_labelled_empty_without_a_call():
    node = horizon.add_node(_source("pasted:   ", text="   "))
    seen: list = []
    assert distill.distil_pending(run_short=_short(seen=seen)) == [node.id]
    assert seen == [], "its item's text is its origin, which is never summarised"
    after = horizon.get_node(node.id)
    assert after.state == "ready" and after.summary == ""


# --- failures, the cap, and what does not count -----------------------------------------------------


def test_a_failed_summary_leaves_the_capture_waiting_with_its_reason():
    node = _captured()
    reasons: list = []
    ticks: list = []
    done = distill.distil_pending(run_short=_short(raises=ValueError("unusable reply")),
                                  on_error=lambda i, r: reasons.append((i, r)),
                                  on_node=lambda: ticks.append(1))
    assert done == [] and reasons == [(node.id, "ValueError: unusable reply")] and ticks == [1]
    assert horizon.get_node(node.id).state == "ready_undistilled"
    assert horizon.waiting_ids() == [node.id]


def test_three_failures_take_a_capture_out_of_the_queue_and_a_press_still_runs_it():
    node = _captured()
    for _ in range(horizon.DISTILL_MAX_FAILURES):
        distill.distil_pending(run_short=_short(raises=ValueError("unusable reply")))
    assert horizon.waiting_ids() == [], "the automatic queue gave up on it"
    paused = horizon.get_node(node.id).summary_paused
    assert paused is not None and paused.tries == 3 and "unusable reply" in paused.error
    assert horizon.waiting_ids(node_ids=[node.id]) == [node.id], "a press that names it"
    assert distill.distil_pending(node_ids=[node.id], run_short=_short()) == [node.id]
    assert horizon.get_node(node.id).summary_paused is None


def test_an_unreachable_model_or_a_stop_never_counts_toward_the_cap():
    node = _captured()
    for _ in range(5):
        distill.distil_pending(run_short=_short(raises=ConnectionError("ConnectError: refused")),
                               not_counted=lambda reason: "ConnectError" in reason)
    assert horizon.waiting_ids() == [node.id] and horizon.get_node(node.id).summary_paused is None
    stopping = {"now": False}

    def stop_during(fields):
        stopping["now"] = True
        raise RuntimeError("the worker was killed")

    for _ in range(5):
        stopping["now"] = False
        distill.distil_pending(run_short=stop_during, should_stop=lambda: stopping["now"])
    assert horizon.waiting_ids() == [node.id], "a stopped call is not the capture's failure"


def test_a_capture_removed_before_its_call_costs_nothing_and_reports_nothing():
    first = _captured(origin="https://example.com/a")
    second = _captured(origin="https://example.com/b")
    seen: list = []
    reasons: list = []

    def remove_the_other(fields):
        seen.append(fields["text"])
        horizon.remove_node(first.id)   # newest first: `second` is the one being summarised
        return labels(title="T", summary="S")

    assert distill.distil_pending(run_short=remove_the_other,
                                  on_error=lambda i, r: reasons.append(i)) == [second.id]
    assert len(seen) == 1, "the removed capture was never sent"
    assert reasons == []


def test_a_capture_removed_during_its_call_is_not_reported_as_a_failure():
    node = _captured()
    reasons: list = []

    def remove_it(fields):
        horizon.remove_node(node.id)
        return labels(title="T", summary="S")

    assert distill.distil_pending(run_short=remove_it, on_error=lambda i, r: reasons.append(i)) == []
    assert reasons == [] and horizon.get_node(node.id) is None


# --- long captures -----------------------------------------------------------------------------------


def test_a_long_capture_goes_to_the_long_runner_with_its_own_fields():
    node = _captured("word " * (distill.SHORT_LIMIT // 4))
    seen: list = []

    def long_run(fields):
        seen.append(fields)
        return {"title": "Long", "summary": "S", "tags": ["t"], "entities": []}

    assert distill.distil_pending(run_short=_short(), run_long=long_run) == [node.id]
    assert set(seen[0]) == {"text", "section_map", "language", "known"}
    assert horizon.get_node(node.id).title == "Long"


def test_without_a_long_runner_a_long_capture_waits():
    node = _captured("word " * (distill.SHORT_LIMIT // 4))
    short = _captured("a short one", origin="https://example.com/s")
    seen: list = []
    assert distill.distil_pending(run_short=_short(seen=seen)) == [short.id]
    assert horizon.waiting_ids() == [node.id]
    assert horizon.waiting_ids(defer_long=True) == []


def test_the_queue_measures_long_by_the_kits_own_length():
    node = _captured("x" * distill.SHORT_LIMIT)
    item = _store().get(node.id)
    assert horizon.get_node(node.id).chars == len(item.text)


# --- the queue ---------------------------------------------------------------------------------------


def test_the_queue_holds_only_stored_captures_waiting_for_a_summary():
    waiting = _captured(origin="https://example.com/w")
    summarised = _captured(origin="https://example.com/s")
    distill.distil_pending(node_ids=[summarised.id], run_short=_short())
    queued = horizon.add_pending_node("https://example.com/q", "web")
    assert horizon.waiting_ids() == [waiting.id]
    assert queued.id not in horizon.waiting_ids()


def test_a_summary_written_just_before_a_crash_is_summarised_after_the_restart():
    node = _captured()
    _store().label(node.id, title="T", summary="S", provenance="inferred")
    horizon.update_node(node.id, state="distilling")   # the state write after it was lost
    horizon.reset_interrupted_states()
    assert horizon.get_node(node.id).state == "ready"
    assert horizon.waiting_ids() == []


def test_a_typed_tag_is_cleaned_as_the_store_keeps_tags():
    assert distill.clean_tags(["Rust", "rust ", "Ｒｕｓｔ", "", "a" * 50]) == ["rust", "a" * 40]
    assert distill.clean_tags("one, Two") == ["one", "two"]


def test_importing_distill_does_not_drag_in_dspy_or_the_extras():
    """`import dspy` happens only when a short capture is summarised (`summarise_short`, through the
    kit's `memory_tasks`), so `cli.py`'s imports never pay for it. In a SUBPROCESS: an in-process
    blocker cannot see what another test already imported."""
    import subprocess
    import sys

    probe = """
import sys

BLOCKED = {"fastapi", "starlette", "httpx", "uvicorn", "chatterbox", "soundfile"}


class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("blocked by the test: " + name)


sys.meta_path.insert(0, Blocker())
import penumbra.distill  # noqa: F401

assert "dspy" not in sys.modules, "dspy was imported at module scope"
print("OK")
"""
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                            cwd=str(_REPO_ROOT), check=False)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_two_passes_at_once_never_pay_for_one_capture_twice():
    import threading
    import time

    for n in range(3):
        _captured(f"note {n}", origin=f"https://example.com/{n}")
    calls: list = []
    lock = threading.Lock()

    def slow(fields):
        with lock:
            calls.append(fields["text"])
        time.sleep(0.05)
        return labels(title="T", summary="S")

    passes = [threading.Thread(target=lambda: distill.distil_pending(run_short=slow)) for _ in range(2)]
    for p in passes:
        p.start()
    for p in passes:
        p.join(timeout=30)
    assert sorted(calls) == ["note 0", "note 1", "note 2"], "each capture summarised once"
    assert horizon.waiting_ids() == []
