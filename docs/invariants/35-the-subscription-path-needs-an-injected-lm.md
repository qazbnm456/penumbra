# Invariant 35: The subscription path uses an injected LM

**A model string prefixed `claude-agent-sdk/` runs that role on the user's Claude Pro or Max subscription, through a `ClaudeAgentLM` that `config.setup` injects into `configure`'s public `main_lm=` and `sub_lm=` seam.**

Every other role is still built from the `PN_*` config.

## The injection decides which LM wins

`rlm-harness==1.10.0`, the version `pyproject.toml` pins, routes the same prefix itself: `runtime.configure` calls its own `_maybe_subscription_lm(cfg.main_model)` for any role left unsupplied. An explicit `main_lm=` is used as is and never reaches that branch, so the injection now decides whose construction is used rather than making the subscription path work at all. Do not bring back the older statement that `configure` ignores the prefix; it was true of an earlier harness and is false now.

Two consequences follow. This project's `_maybe_subscription_lm` duplicates upstream's, and `SUBSCRIPTION_PREFIX` is a second copy of `claude_agent_lm.SUBSCRIPTION_PREFIX`. Both are kept because `config.py` stays free of `dspy` and `rlm_harness` at import time and cannot read upstream's constant. Deleting ours would appear to work, which is the trap: every subscription run would silently move to upstream's construction, whose timeout and error behaviour this project has never tested. Removing it needs a measurement, not a cleanup.

The sentinel string also stays in `RLMConfig`. It does nothing for an injected role, but it labels the trace and the log.

## Where it lives

`SUBSCRIPTION_PREFIX` is in `config.py`, and `_maybe_subscription_lm` imports `ClaudeAgentLM` lazily, only inside the sentinel branch, so an install that uses only API keys never touches the optional SDK. `config.setup` is the one place either entry point configures a model (`cli.py` in-process and `worker.py` in the subprocess both call it), so one change covers both.

`PN_SUB_MODEL` inherits the sentinel from `PN_MAIN_MODEL`. That is correct here, because this project has no role that must stay on its own endpoint, and a test pins it so the difference from the sibling project that forbids it stays deliberate.

`claude-agent-sdk` is the `subscription` extra, mirrored as a `subscription-sdk` dev group listed in `[tool.uv] default-groups`. An extra is not synced by default, so without the mirror a bare `uv sync` would remove the SDK and the next subscription run would fail with an `ImportError`. The SDK also needs the Claude Code CLI installed and logged in, which no manifest can express. `ClaudeAgentLM` refuses to construct when `ANTHROPIC_API_KEY` is set, because the CLI would silently prefer the key over the subscription and bill API credit. A bare `claude-agent-sdk/` with no model name raises `SystemExit`, which reaches the API as a clean 500 through `_config()`.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
