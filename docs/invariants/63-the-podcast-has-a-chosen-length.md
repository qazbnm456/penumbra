# Invariant 63: The podcast has a chosen length

**The podcast has a length, chosen at generation time, and the tiers are numbers rather than adjectives.**

The tiers are `short`, `default` and `long`: about 3 to 5, 8 to 12 and 18 to 25 minutes, or 12 to 18, 30 to 45 and 60 to 90 turns. They are numbers because "aim for a natural episode length given how much the sources contain" did nothing: four measured episodes all landed near three minutes, and the eight-source orbit produced the shortest.

The length is chosen when generating, not on the settings page, because that is when a reader knows how long they want to listen, and changing it afterwards costs a model run plus synthesis. It also keeps invariant 41's surface narrow. Both entry points accept it (`POST /audio`'s `length`, `penumbra audio --length`), and it reaches the model as a signature field, like `output_language`.

`AudioOptions` subclasses `RunOptions` instead of re-declaring `run_id`, so a field added to the shared body later reaches `/audio` too. It keeps `extra="forbid"`, because pydantic drops unknown keys and `{"len": "long"}` would otherwise produce a default-length episode with no sign the option was ignored.

The browser remembers the choice (`localStorage`, key `penumbra-podcast-length`), not the server. It is a reader's habit, not a property of an orbit; one person who always wants long episodes should not impose that on a shared orbit. It is still sent with every generate request, because it changes what the model writes.

## Calibration

Turn counts are met and minutes are not. A long episode produced 80 turns, inside its target, but lasted about 14 to 15 minutes instead of 18 to 25, because the minutes assumed about 90 characters per turn and the real figure is about 56. One sample per tier is not enough to recalibrate, so both numbers stand.

Across eight long episodes the target is met at its floor, and length follows the corpus at least as much as the tier: on an 18,466-character corpus the runs produced 70, 70, 65, 65, 61, 60 and 43 turns, and on a 131,057-character one, 80. The 43-turn run hit an error, spent turns recovering and submitted without ever comparing its count with the target. Building across turns keeps the count in a variable, out of the model's view, so `GeneratePodcastScript` now tells the model to compare the count with the target before validating and, if short, to go back to the sources rather than forward to the close. That is deliberately different from the filler rule beside it, which covers a corpus with nothing left to use. This is prompt compliance, with invariant 4's caveat.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
