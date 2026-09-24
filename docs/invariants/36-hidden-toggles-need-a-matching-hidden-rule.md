# Invariant 36: Hidden toggles need a matching hidden rule

**An element in `penumbra/web/` that is toggled with `hidden` never gets an author `display` rule without a matching `[hidden]` rule, and `tests/test_web_assets.py` fails the build if one does.**

`hidden` works through the browser stylesheet's `[hidden] { display: none }`, and any author `display` declaration outranks it regardless of specificity. This shipped broken twice: `.modal-overlay { display: flex }` left an overlay permanently visible whose `inset: 0` swallowed every click on the page, and `.ticker-detail` left the reasoning log permanently expanded. In both cases the JavaScript was correct, so only the stylesheet could show the fault.

The check is a source-tree assertion keyed on CSS class names, which markup and JavaScript spell the same way. It first asserts that it can still see every known instance, so a future extraction failure fails the build instead of passing without checking anything. The same file pins invariant 29's rule against `innerHTML` with an interpolated string, along with `outerHTML`, `insertAdjacentHTML` and `document.write`.

A visible author `display` on a hidden-toggled class is allowed if a guard outranks it: a `[hidden]` rule whose selector is one token longer, so it wins on specificity regardless of source order. The class-name tripwire would also accept a guard that loses the cascade; `test_the_podcast_transcript_is_not_capped_by_a_fixed_height` computes specificity and is the check that actually proves it.

More generally, CSS source order decides ties between equal specificity, and several fixes were lost to it: a touch-reveal rule overridden by a later base rule, and a tooltip anchor overriding a control's own positioning. Rules that must win are placed last or given more specificity, and `test_the_touch_escape_comes_after_every_rule_it_overrides` pins one such order. A flex column stretches its children to full width by default, so only what should span may span.

Behaviour is tested separately: the node harness in `tests/web_dom_harness.mjs` runs real functions out of `app.js` against a small DOM shim. It covers logic, not the cascade, which is why this invariant still needs its source-tree assertion.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
