# Invariant 86: The fine sky is only a background

**The star map's fine sky (`sky-gl.js`) draws the Horizon as a black hole whose light is bent, on a canvas behind the map's SVG that takes no pointer and is hidden from assistive technology. Every planet, ring, label and control stays in the SVG. It runs only in the dark theme, only on a hardware WebGL2 GPU, and only where it measured smooth; the browser decides that, not the server.**

## Why it is a layer, not a new map

The map's SVG already carries everything a reader acts on: dragging planets onto rings (invariant 85), carrying moons, the arrow-key walk and its announcements, the camera, the tooltips, and the accessible names of every planet and moon. A map redrawn in WebGL would have had to rebuild all of that and keep it in step with a scene a screen reader cannot see. Drawing only the background keeps the whole interactive surface where it was, so the sky can be switched on and off without anything a reader presses changing. With it on, the SVG hides only its own black hole, disk, star points and nebulae (`.starmap.is-fine`), the parts the canvas now paints.

The canvas follows the SVG rather than the other way round: every frame, `skyView` reads the world group's transform (`getScreenCTM`) for where the Horizon's centre is and how large one map unit is, and lays the canvas over the SVG's box. A pan, a zoom, a resize or a new ring therefore moves the sky exactly, with no camera of its own to drift.

## Why only the dark theme

A photographed black hole needs deep space around it. In the light theme the map would have been a dark rectangle in a paper page, which the reader rejected as tearing the screen in two. So the sky is offered only in the dark theme, where its edges fade into the page (`mask-image` on `.starmap-sky`), and the light theme keeps the drawn map.

## Why the browser decides, and how

Whether a machine can afford a ray traced per pixel depends on its GPU, and only the page can see the GPU. The server cannot, and in the desktop app the page and the server share one machine anyway, so asking the server would add a round trip that learns nothing the page does not already know.

- No WebGL2: never offered.
- A GPU that is the processor in disguise (SwiftShader, llvmpipe, Microsoft Basic Render Driver; `PenumbraSky.isSoftware`): never offered, however a benchmark would go. A sky drawn per pixel on these costs whole seconds a frame.
- Otherwise a short benchmark the first time, at medium quality, picks high, medium or low, or none (`chooseQuality`). The result is remembered for that GPU in that browser (`localStorage`), which is a convenience only: losing it means measuring again.
- While it runs, a sky that stays under about 30 frames a second for most of two seconds steps down one quality. At the bottom, in Auto, it turns itself off and says so.

The reader's choice (Auto, Fine, Power saving) sits in the map's settings with a line saying what it does on this computer. It is a presentation setting with no bearing on any safety bound (invariant 41), and it is kept in the browser rather than on the server because it belongs to a device, not to the reader's data.

## The traps

- **`gl.finish()` does not wait in WebKit.** It may return before the GPU is done, and in WebKit it does, so a benchmark built on it measured 0.125 ms a frame on a machine that took 4.9. The benchmark reads one pixel back after each frame, which cannot return early.
- **Parallel rays see one patch of sky.** The rays run parallel so the disk lines up with the map's rings, which are true ellipses. A sky looked up along those rays is the same colour for every pixel the hole does not bend, so the sky is looked up through a little perspective added per pixel instead.
- **The disk lies in the rings' plane.** The rings' height is about 0.673 of their width (`ringGeometry`), a circle seen about 48 degrees off its axis, and the eye sits at that angle. Change one and the disk stops lining up with the other.
- **Reduced motion freezes the disk** and draws only when the view moves, rather than turning the sky off.

`tests/test_browser.py::test_the_fine_sky_runs_only_in_the_dark_theme_and_says_why_when_it_cannot` fails if the light theme draws it, if the dark theme's state and its stated reason disagree, or if the shaders stop compiling wherever WebGL2 exists; `tests/test_web_behaviour.py::test_the_fine_sky_picks_its_quality_from_a_measured_frame_and_refuses_software_gpus` pins the three decisions.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
