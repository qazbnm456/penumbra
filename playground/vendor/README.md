# Vendored third-party assets

**`driver.js` 1.8.0: MIT, no dependencies, about 25KB unminified.** <https://driverjs.com> · <https://github.com/kamranahmedse/driver.js>

It is committed rather than fetched at build time, so the build is reproducible offline and the published page has no third-party origin in its critical path.

## Why this one

The playground's guided script has to spotlight a real control, place a popover beside it, scroll it into view and then **let the reader actually click it**. Spotlighting and positioning are fiddly and well solved. Waiting for the real action is ours: `src/director.js` polls `PG.progress()`, which reads the stage the shim has actually reached.

`driver.js` fits because the highlighted element stays interactive by default, `showButtons: []` plus `moveNext()` gives full programmatic control, and `popoverClass` lets the popover use the application's own custom properties.

**The alternatives were rejected on licence, not features.** Intro.js and Shepherd.js are AGPL unless you buy a commercial licence, and this project is MIT and ships an HTTP API meant to run as a network service, the same reasoning that removed `pymupdf` (invariant 7).

To upgrade, download both files again from the same version tag and rerun `node playground/smoke.mjs`.
