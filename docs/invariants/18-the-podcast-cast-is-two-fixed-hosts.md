# Invariant 18: The podcast cast is two fixed hosts

**The Audio Overview has a fixed cast of two hosts, `host_a` and `host_b` (`schema.Speaker`), not freely named per episode.**

This keeps `Utterance.speaker` a closed `Literal[...]` that citations and voice mapping can rely on, and keeps `RN_TTS_VOICE_HOST_A` and `RN_TTS_VOICE_HOST_B` a fixed pair of settings. It is a deliberate scope cut.

One gap is known: `config.tts_voice_map` hardcodes both speaker keys with no tripwire, unlike `cli._SPEAKER_LABELS`, which `tests/test_cli.py` covers. A third host would need both updated, and only one of them would fail loudly.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
