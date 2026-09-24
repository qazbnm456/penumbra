# Invariant 19: Resolve the TTS provider before the model call

**`cli._cmd_audio` resolves the TTS provider before the potentially expensive script-generation call, not after.**

In the original order, a misconfigured `RN_TTS_PROVIDER` surfaced only after the transcript had been generated, wasting a real model call. Do not move `get_tts_provider(...)` back after `GeneratePodcastScript().run(...)`.

For the same reason, `EdgeTTSProvider.synthesize` wraps its file write in the same try/except as the network call. To a caller both are one operation, "make this file exist", and a bad `--out` directory must not raise after synthesis has already spent a network call.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
