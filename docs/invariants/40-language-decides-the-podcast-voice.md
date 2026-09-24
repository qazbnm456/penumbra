# Invariant 40: Language decides the podcast voice

**`tts.default_voices_for` maps a language to a voice, which is how the podcast joined invariant 39's language rules.**

Before it, `voice_map` came straight from `RN_TTS_VOICE_HOST_A` and `RN_TTS_VOICE_HOST_B`, so a correct Chinese script was read by the default English voices. That is a routing bug, not a synthesis one, and any provider would have had it.

Every voice id in the table was read from a real `edge_tts.list_voices()` response, never written from memory. A plausible but nonexistent id fails only at synthesis, after the script has already cost a model call, which is the waste invariant 19 prevents. A test checks the shape of every id against hand edits.

Precedence: an explicitly set `RN_TTS_VOICE_HOST_A` or `RN_TTS_VOICE_HOST_B` beats the settings file (invariant 41), which beats the language default, which beats the shipped English cast. The file ranks above the language default because both it and the environment are a person choosing a voice. Explicitness is read from the raw environment, not by comparing against the default value, because an operator who deliberately picks the English default for a Chinese notebook is making a choice. The two voices resolve independently. For an unknown language, `default_voices` returns `None` and the configured voices stand; a voice in the wrong language is bad, but substituting a voice for a language nobody asked for is worse.

`fallback_voices` is a separate provider method that ranks below the language default and above the shipped config value. Without it, a provider other than edge-tts plus an unknown language would fall through to an edge-tts voice name and fail at synthesis after a model call. It is deliberately not `default_voices(None)`, which must keep returning `None`. `_VOICE_PATTERN` accepts both providers' naming schemes by widening the accepted shapes, never the accepted characters, so the SSML hole closed in invariant 41 stays closed.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
