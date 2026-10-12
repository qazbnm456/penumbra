# Invariant 86: The fine sky is only a background

**The star map's fine sky (`sky-gl.js`) draws the Horizon as a black hole whose light is bent, on a canvas behind the map's SVG that takes no pointer and is hidden from assistive technology. Every planet, ring, label and control stays in the SVG. It runs only in the dark theme, only on a hardware WebGL2 GPU, and only where it measured smooth; the browser decides that, not the server.**

## Why it is a layer, not a new map

The map's SVG already carries everything a reader acts on: dragging planets onto rings (invariant 85), carrying moons, the arrow-key walk and its announcements, the camera, the tooltips, and the accessible names of every planet and moon. A map redrawn in WebGL would have had to rebuild all of that and keep it in step with a scene a screen reader cannot see. Drawing only the background keeps the whole interactive surface where it was, so the sky can be switched on and off without anything a reader presses changing. With it on, the SVG hides only the parts the canvas now paints (`.starmap.is-fine`): its own black hole and disk, its star points and its deep sky of nebulae, galaxies and double stars. The hole's rim goes too: it is a circle about the map's centre, the bent shadow is not, and lit for a pointed or chosen Horizon it drew a ring that missed the hole, as did the keyboard's focus ring on the same circle. The Horizon's name lights instead, and is underlined for focus.

The canvas follows the SVG rather than the other way round: every frame, `skyView` reads the world group's transform (`getScreenCTM`) for where the Horizon's centre is and how large one map unit is, and lays the canvas over the SVG's box. A pan, a zoom, a resize or a new ring therefore moves the sky exactly, with no camera of its own to drift.

## Why only the dark theme

A photographed black hole needs deep space around it. In the light theme the map would have been a dark rectangle in a paper page, which the reader rejected as tearing the screen in two. So the sky is offered only in the dark theme, where its edges fade into the page (`mask-image` on `.starmap-sky`), and the light theme keeps the drawn map.

## Why the browser decides, and how

Whether a machine can afford a ray traced per pixel depends on its GPU, and only the page can see the GPU. The server cannot, and in the desktop app the page and the server share one machine anyway, so asking the server would add a round trip that learns nothing the page does not already know.

- No WebGL2: never offered.
- A GPU that is the processor in disguise (SwiftShader, llvmpipe, Microsoft Basic Render Driver; `PenumbraSky.isSoftware`): never offered, however a benchmark would go. A sky drawn per pixel on these costs whole seconds a frame.
- Otherwise a short benchmark the first time, at medium quality, picks high, medium or low, or none (`chooseQuality`). High draws about four times what medium does, so it is chosen only where that still fits a 60 Hz frame. The result is remembered for that GPU at about that size in that browser (`localStorage`), which is a convenience only: losing it means measuring again.
- While it runs, a sky that misses most 60 Hz frames over two seconds of wall time steps down one quality; a steady 30 counts as missing, since the whole page would be held there with it. At the bottom, in Auto, it turns itself off and says so, and Fine may ask for it again on a new canvas.

The reader's choice (Auto, Fine, Power saving) sits in the map's settings with a line saying what it does on this computer. It is a presentation setting with no bearing on any safety bound (invariant 41), and it is kept in the browser rather than on the server because it belongs to a device, not to the reader's data.

## The traps

- **`gl.finish()` does not wait in WebKit.** It may return before the GPU is done, and in WebKit it does, so a benchmark built on it measured 0.125 ms a frame on a machine that took 4.9. The benchmark reads one pixel back after each frame, which cannot return early.
- **The disk is seen nearly edge on, by a camera, not from the rings' angle.** The first sky put the disk in the plane of the map's rings (a circle seen about 48 degrees off its axis) and traced parallel rays. From that height the disk's far side, bent round the hole, closed into a thin ring hugging the shadow, which three rounds of dimming could not remove because it is made by rays that skim the photon sphere and cross the disk once, and it never looked like the reference renders. A perspective camera 26 radii out, about 9 degrees above the disk, gives the familiar arch over the shadow and the arc beneath it. Beyond 24 radii the sky is bent by the weak-lensing angle (about 2/b) rather than traced, and the galaxy band is soft cloud only: a crisp dust lane, or a straight sky meeting a traced one, drew an arc across the open sky.
- **An `<svg>` has no `offsetLeft`.** The canvas is placed from the difference of the SVG's and the map's rects; placed from `offsetLeft`, it sat at its static position over the tag row, 40px above the rings it was meant to lie under.
- **The SVG is positioned but takes no z-index**, so it paints over the canvas before it and under Penny and the empty map's line after it. Given `z-index: 1`, it covered both.
- **Tearing the sky down loses its context on purpose**, and that loss is not reported as the graphics failing; a sky asked for again gets a new canvas, since a lost context cannot draw.
- **The settings note is worked out from the state on every change** (`skyStatus`), never set along the way, so it cannot describe a sky the page is not drawing (invariant 60).
- **The disk is the light, and copper on copper disappears.** Under the fine sky each planet is lit from the hole (`.map-planet-sun`, turned towards it every frame in `placeStarMap`) instead of from the top left, and every moon and dot is a small dark rock whose edge carries its state (a flat bright fill read as an orange stone), with passing rocks edged neutrally, so none is lost against the bright disk or black space; states that are not resting keep their own colours. Images of the disk after the first, light bent round the hole again, are dimmed hard: at the map's size they drew a line round the shadow. A class name already used by the map (`map-planet-rim`) once picked up the selection ring's copper and drew a second ring.
- **Reduced motion freezes the disk** and draws only when the view moves, rather than turning the sky off.

`tests/test_browser.py::test_the_fine_sky_runs_only_in_the_dark_theme_and_says_why_when_it_cannot` fails if the light theme draws it, if the dark theme's state and its stated reason disagree, or if the shaders stop compiling wherever WebGL2 exists; `tests/test_web_behaviour.py::test_the_fine_sky_picks_its_quality_from_a_measured_frame_and_refuses_software_gpus` pins the three decisions.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
