# Invariant 55: Markdown builds nodes, and links are inert

**Markdown in an answer is rendered by a hand-written renderer that builds DOM nodes, and links in it are shown but not clickable.**

Answers arrive full of `**bold**`, `## heading` and `- list` characters because the model writes Markdown whether asked or not.

There is no library and no HTML strings; this is invariant 29's rule where it matters most. Every string came from a model that has been reading content an attacker may have written (invariant 6). One missed `esc()` in a string-building renderer is an XSS hole, and building nodes removes that failure mode instead of guarding it. `test_the_markdown_renderer_builds_nodes_rather_than_markup` pins that rule.

A `[label](url)` renders its label, shows the URL on hover and copies it on click; it is never an `<a href>`. Invariant 1 keeps URLs out of the model's reach because a prompt-injected source could steer it into sending the notebook away, and a clickable link in an answer is the same hazard with the reader's click as the transport, dressed as a grounded reference. A separate test, `test_the_markdown_renderer_never_creates_a_navigable_link`, covers link creation, and it must keep catching the three forms that got past an earlier version: `setAttribute("href", …)`, a template-literal ``createElement(`a`)`` and a click handler that sets `window.location`. Copy-on-click exists because CSS generated content cannot be selected. Links copied into an exported Markdown file become clickable in other viewers; the rule applies to the web UI only.

The renderer never creates its own text nodes. It walks raw offsets into the original string and appends through `emit`, which is where citation ranges are split out, so block structure and citation marks compose rather than one being applied on top of the other.

A citation's number is stamped after the whole answer is built. A mark that crosses inline `**bold**` is emitted in several fragments, and deciding "is this the last fragment" while emitting fails when the span ends in syntax the renderer drops, such as a closing `**`. The renderer collects the fragments and marks the last one with `data-stroke-end`, and a later re-numbering stamps only that fragment, so a split mark never shows its number twice.

Emphasis follows a simplified CommonMark flanking rule; without it `3 * 4 * 5` becomes `3 <em>4</em> 5` and snake_case names are mangled, and both appear in this project's subject matter. Strikethrough is not supported.

Known limits: a blockquote does not nest other blocks, a `.md-link` tooltip inside a table is clipped by `.md-table-wrap`'s scroller (invariant 54's uncovered case, softened by copy-on-click), and `renderMdList` recurses once per indent level, bounded in practice by the corpus cap.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
