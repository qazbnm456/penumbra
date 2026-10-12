// The star map's fine sky: the Horizon drawn as a black hole whose light is bent, in WebGL2.
//
// Every pixel sends one ray of light backwards from the eye and follows it past a Schwarzschild
// black hole, step by step, bending it as gravity would (`d²x/dλ² = -3/2 · h² · x / r⁵` in units
// where the Schwarzschild radius is 1, with `h` the ray's conserved angular momentum). A ray that
// falls inside r = 1 is black; one that crosses the accretion disk's plane between its inner and
// outer edge picks up the disk's light; one that escapes picks up the sky behind, so the stars and
// the far side of the disk are seen bent around the hole. The disk glows at the temperature of a
// thin disk at that radius, shifted by its orbital speed (Doppler: the side turning towards the eye
// is bluer and brighter) and by climbing out of the hole's well (gravitational redshift), with
// brightness rising as the fourth power of the shift (beaming). The scene is rendered in high
// dynamic range, bright parts bleed a little light (bloom), and a filmic curve brings it to screen.
//
// It draws only the background: the planets, rings, labels and every control stay in the SVG above
// it, untouched, so nothing a reader can press or a screen reader can read depends on this file.
// No library and nothing fetched: one triangle that covers the canvas and four small shaders.
//
// The disk lies in the plane the map's rings lie in. The rings are ellipses whose height is about
// two thirds of their width (`ringGeometry` in app.js), which is a circle seen from about 48 degrees
// off its axis, so the eye sits at that angle here too and the disk lines up with the rings.
(function () {
  "use strict";

  //: Ray steps, a multiplier on each step's length (smaller is finer), the canvas resolution as a
  //: fraction of the screen's, and whether bright light bleeds. The step count is a ceiling: most
  //: rays escape or fall in long before it.
  const QUALITY = {
    high: { steps: 300, stepScale: 0.45, scale: 1.0, bloom: true },
    medium: { steps: 200, stepScale: 0.65, scale: 0.75, bloom: true },
    low: { steps: 120, stepScale: 1.0, scale: 0.5, bloom: false },
  };
  const ORDER = ["high", "medium", "low"];

  //: GPUs that are a CPU pretending to be one. A sky drawn per pixel on these costs whole seconds a
  //: frame, so they are never offered it, however the benchmark would have gone.
  const SOFTWARE = /swiftshader|llvmpipe|softpipe|software rasterizer|basic render|microsoft basic|mesa offscreen/i;

  function isSoftware(renderer) {
    return SOFTWARE.test(String(renderer || ""));
  }

  //: The quality a measured frame time allows, measured at `medium`. `high` draws about four times
  //: what `medium` does (finer steps, full resolution) and `low` about a third (half resolution, no
  //: bloom), so each is chosen only where it would still fit a 60 Hz frame with room left for the SVG
  //: and the rest of the page; null when even `low` would not.
  function chooseQuality(msPerFrame) {
    if (!(msPerFrame > 0)) return null;
    if (msPerFrame <= 2.5) return "high";
    if (msPerFrame <= 9) return "medium";
    if (msPerFrame <= 30) return "low";
    return null;
  }

  //: One step down, or null at the bottom.
  function lower(quality) {
    const at = ORDER.indexOf(quality);
    return at >= 0 && at < ORDER.length - 1 ? ORDER[at + 1] : null;
  }

  //: Whether this browser can draw the fine sky at all, without drawing it: WebGL2, and a real GPU.
  function probe() {
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl2");
      if (!gl) return { ok: false, reason: "no-webgl2", renderer: "" };
      const info = gl.getExtension("WEBGL_debug_renderer_info");
      const renderer = String(info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
      const lose = gl.getExtension("WEBGL_lose_context");
      if (lose) lose.loseContext();
      if (isSoftware(renderer)) return { ok: false, reason: "software", renderer };
      return { ok: true, reason: "", renderer };
    } catch (err) {
      return { ok: false, reason: "error", renderer: "" };
    }
  }

  const VERTEX = `#version 300 es
const vec2 CORNERS[3] = vec2[3](vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
out vec2 vUv;
void main() {
  vec2 p = CORNERS[gl_VertexID];
  vUv = p * 0.5 + 0.5;
  gl_Position = vec4(p, 0.0, 1.0);
}`;

  // The scene, in high dynamic range. STEPS and STEP_SCALE come from the quality.
  const SCENE = `#version 300 es
precision highp float;
uniform vec2 uCenter;      // the hole's centre, in this canvas's pixels, from its bottom left
uniform float uPxPerRs;    // pixels per Schwarzschild radius
uniform float uTime;       // seconds
uniform vec2 uView;        // (sin, cos) of the eye's height above the disk's plane
out vec4 outColor;

const float DISK_IN = 3.0;   // the innermost stable orbit
const float DISK_OUT = 9.0;
const float FAR = 60.0;      // where every ray starts, and past which it has escaped

// Hashes and value noise, small and portable (no sin(), which drifts between GPUs).
float hash1(vec3 p) {
  p = fract(p * vec3(0.1193, 0.1471, 0.1663));
  p += dot(p, p.zxy + 23.17);
  return fract((p.x + p.z) * p.y);
}

float noise3(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  vec3 u = f * f * (3.0 - 2.0 * f);
  float a = mix(hash1(i), hash1(i + vec3(1, 0, 0)), u.x);
  float b = mix(hash1(i + vec3(0, 1, 0)), hash1(i + vec3(1, 1, 0)), u.x);
  float c = mix(hash1(i + vec3(0, 0, 1)), hash1(i + vec3(1, 0, 1)), u.x);
  float d = mix(hash1(i + vec3(0, 1, 1)), hash1(i + vec3(1, 1, 1)), u.x);
  return mix(mix(a, b, u.y), mix(c, d, u.y), u.z);
}

float fbm(vec3 p) {
  float sum = 0.0;
  float amp = 0.5;
  for (int i = 0; i < 4; i++) {
    sum += amp * noise3(p);
    p = p * 2.07 + 13.3;
    amp *= 0.5;
  }
  return sum / 0.9375;
}

// The colour of a body at a temperature, a fit to the blackbody curve, in linear light.
vec3 blackbody(float kelvin) {
  float t = clamp(kelvin, 1000.0, 40000.0) / 100.0;
  float r = t <= 66.0 ? 1.0 : clamp(1.2929 * pow(t - 60.0, -0.1332), 0.0, 1.0);
  float g = t <= 66.0 ? clamp(0.3901 * log(t) - 0.6318, 0.0, 1.0)
                      : clamp(1.1299 * pow(t - 60.0, -0.0755), 0.0, 1.0);
  float b = t >= 66.0 ? 1.0 : (t <= 19.0 ? 0.0 : clamp(0.5432 * log(t - 10.0) - 1.1963, 0.0, 1.0));
  return pow(vec3(r, g, b), vec3(2.2));
}

vec3 starLayer(vec3 dir, float density) {
  vec3 p = dir * density;
  vec3 cell = floor(p);
  float pick = hash1(cell);
  if (pick < 0.9) return vec3(0.0);
  vec3 at = vec3(hash1(cell + 3.7), hash1(cell + 9.1), hash1(cell + 17.3)) * 0.7 + 0.15;
  float d = length(p - cell - at);
  float glow = exp(-d * d * 60.0);
  float bright = pow((pick - 0.9) * 10.0, 5.0) * 3.0 + 0.08;
  return blackbody(mix(3200.0, 12000.0, hash1(cell + 5.3))) * glow * bright;
}

// The sky behind the hole: a faint band of the galaxy and two layers of stars.
vec3 sky(vec3 dir) {
  vec3 col = vec3(0.0025, 0.0025, 0.0045);
  vec3 plane = normalize(vec3(0.25, 0.85, 0.46));
  float h = dot(dir, plane);
  float band = exp(-h * h * 14.0);
  float cloud = fbm(dir * 3.2 + 7.0);
  float dust = smoothstep(0.5, 0.75, fbm(dir * 6.5 + 31.0));
  col += mix(vec3(0.42, 0.45, 0.62), vec3(0.75, 0.6, 0.45), cloud) * band * (0.15 + cloud) * (1.0 - 0.7 * dust) * 0.05;
  col += starLayer(dir, 70.0) + 0.6 * starLayer(dir, 150.0);
  return col;
}

// The disk's light where a ray crosses its plane, and how much of what lies behind it it hides.
vec4 disk(vec3 p, vec3 v) {
  float r = length(p.xz);
  if (r < DISK_IN || r > DISK_OUT) return vec4(0.0);
  // A thin disk's temperature, highest a little outside its inner edge.
  float x = DISK_IN / r;
  float kelvin = 4600.0 * pow(x, 0.75) * pow(max(1.0 - sqrt(x), 0.0), 0.25) / 0.42;
  // Orbital speed as a static observer sees it, the shift it gives towards the eye, and the
  // redshift of climbing out of the well.
  float beta = min(sqrt(0.5 / max(r - 1.0, 0.05)), 0.95);
  vec3 along = normalize(vec3(-p.z, 0.0, p.x));
  float gamma = inversesqrt(1.0 - beta * beta);
  float doppler = 1.0 / (gamma * (1.0 - beta * dot(along, -normalize(v))));
  float g = doppler * sqrt(max(1.0 - 1.0 / r, 0.0));
  // Streaks that turn with the disk, faster inside (a Kepler orbit's 1/r^1.5). Gas is sheared into
  // long arcs, so the noise runs fine across the radius and slow around it: read on a circle of
  // the turned angle (no seam where the angle wraps) at a high radial frequency.
  float turn = atan(p.z, p.x) - uTime * 0.9 * pow(r, -1.5);
  vec2 around = vec2(cos(turn), sin(turn));
  float arcs = fbm(vec3(around * 1.6, r * 5.5));
  float clumps = fbm(vec3(around * 4.0 + r * 0.7, r * 1.3));
  float streak = 0.65 * arcs + 0.35 * clumps;
  // The inner edge fades over more than a radius: a sharp one, bent round the hole, drew a thin
  // hard ring hugging the shadow that read as a line drawn on top rather than as light.
  float edge = smoothstep(DISK_IN, DISK_IN + 1.6, r) * smoothstep(DISK_OUT, DISK_OUT - 3.5, r);
  float density = edge * (0.2 + 1.15 * streak * streak * 1.6);
  vec3 light = blackbody(kelvin * g) * pow(g, 4.0) * density * 0.85;
  return vec4(light, clamp(density * 0.95, 0.0, 1.0));
}

void main() {
  vec2 b = (gl_FragCoord.xy - uCenter) / uPxPerRs;
  vec3 eye = vec3(0.0, uView.x, uView.y);
  vec3 right = vec3(1.0, 0.0, 0.0);
  vec3 up = vec3(0.0, uView.y, -uView.x);
  vec3 pos = eye * FAR + right * b.x + up * b.y;
  vec3 vel = -eye;
  vec3 col = vec3(0.0);
  float alpha = 0.0;
  // Far from the hole light barely bends and no disk lies in the way: the sky, straight.
  // Rays run parallel, so the map's rings stay true ellipses; the sky behind is looked up through a
  // little perspective instead, or every straight ray would see the same patch of it.
  vec3 spread = (right * b.x + up * b.y) * 0.012;
  if (dot(b, b) > 196.0) {
    outColor = vec4(sky(normalize(vel + spread)), 1.0);
    return;
  }
  vec3 hv = cross(pos, vel);
  float h2 = dot(hv, hv);
  bool fell = false;
  // Each crossing of the disk's plane is one more image of the disk: the first is the disk itself,
  // the second its light bent once round the hole into a thin ring hugging the shadow, the rest
  // thinner rings still. All are real, but at the map's size they read as a line drawn round the
  // hole rather than as light, so every image after the first is dimmed hard.
  float order = 1.0;
  for (int i = 0; i < STEPS; i++) {
    float r = length(pos);
    float dt = clamp(0.08 * r, 0.015, 1.6) * STEP_SCALE;
    // A leapfrog step: half a kick, a drift, half a kick.
    vec3 half_v = vel - 1.5 * h2 * pos / pow(r, 5.0) * dt * 0.5;
    vec3 next = pos + half_v * dt;
    float rn = length(next);
    vel = half_v - 1.5 * h2 * next / pow(rn, 5.0) * dt * 0.5;
    if (pos.y * next.y < 0.0) {
      vec3 hit = mix(pos, next, pos.y / (pos.y - next.y));
      vec4 d = disk(hit, vel) * order;
      col += (1.0 - alpha) * d.rgb;
      alpha += (1.0 - alpha) * d.a;
      order *= order > 0.99 ? 0.35 : 0.25;
    }
    pos = next;
    if (rn < 1.0) { fell = true; break; }
    if (alpha > 0.995) break;
    if (rn > FAR * 1.3 && dot(pos, vel) > 0.0) break;
  }
  if (!fell) col += (1.0 - alpha) * sky(normalize(normalize(vel) + spread));
  outColor = vec4(col, 1.0);
}`;

  // What is bright enough to bleed, at half resolution.
  const BRIGHT = `#version 300 es
precision highp float;
uniform sampler2D uScene;
uniform vec2 uKnee;        // where light starts and finishes bleeding: lower when the target clamps at 1
in vec2 vUv;
out vec4 outColor;
void main() {
  vec3 c = texture(uScene, vUv).rgb;
  float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
  outColor = vec4(c * smoothstep(uKnee.x, uKnee.y, lum), 1.0);
}`;

  // One direction of a gaussian blur.
  const BLUR = `#version 300 es
precision highp float;
uniform sampler2D uSource;
uniform vec2 uStep;
in vec2 vUv;
out vec4 outColor;
void main() {
  vec3 c = texture(uSource, vUv).rgb * 0.2270;
  c += (texture(uSource, vUv + uStep * 1.3846).rgb + texture(uSource, vUv - uStep * 1.3846).rgb) * 0.3162;
  c += (texture(uSource, vUv + uStep * 3.2308).rgb + texture(uSource, vUv - uStep * 3.2308).rgb) * 0.0703;
  outColor = vec4(c, 1.0);
}`;

  // The scene and its bloom brought to the screen through a filmic curve.
  const FINAL = `#version 300 es
precision highp float;
uniform sampler2D uScene;
uniform sampler2D uBloom;
uniform float uBloomOn;
uniform float uExposure;
in vec2 vUv;
out vec4 outColor;
vec3 filmic(vec3 x) {
  return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
void main() {
  vec3 c = texture(uScene, vUv).rgb + uBloomOn * 0.55 * texture(uBloom, vUv).rgb;
  c = pow(filmic(c * uExposure), vec3(1.0 / 2.2));
  // Half a step of noise, so the near-black sky does not band into rings in eight bits.
  float n = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
  outColor = vec4(c + (n - 0.5) / 255.0, 1.0);
}`;

  function compile(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(`sky shader: ${log}`);
    }
    return shader;
  }

  function program(gl, fragment) {
    const prog = gl.createProgram();
    gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VERTEX));
    gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(`sky program: ${gl.getProgramInfoLog(prog)}`);
    gl.getAttachedShaders(prog).forEach((shader) => {
      gl.detachShader(prog, shader);
      gl.deleteShader(shader);
    });
    const uniforms = {};
    const count = gl.getProgramParameter(prog, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < count; i += 1) {
      const name = gl.getActiveUniform(prog, i).name;
      uniforms[name] = gl.getUniformLocation(prog, name);
    }
    return { prog, uniforms };
  }

  //: A target to render into: a texture and its framebuffer, at a size.
  function target(gl, hdr, onIncomplete = () => {}) {
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const fb = gl.createFramebuffer();
    const t = { tex, fb, w: 0, h: 0 };
    t.size = (w, h) => {
      if (t.w === w && t.h === h) return;
      t.w = w;
      t.h = h;
      gl.bindTexture(gl.TEXTURE_2D, tex);
      if (hdr) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null);
      else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
      gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
      if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) onIncomplete();
    };
    t.free = () => {
      gl.deleteTexture(tex);
      gl.deleteFramebuffer(fb);
    };
    return t;
  }

  //: The sky on one canvas. `view()` is asked every frame for where the hole is: `{cx, cy, pxPerRs}`
  //: in the canvas's own CSS pixels from its top left, or null to skip the frame. `still` freezes the
  //: disk (reduced motion) and draws only when the view moves. `onSlow(quality)` is told each time it
  //: steps down for being slow, with null once there is nothing left to step down to.
  function create(canvas, { quality = "medium", view, still = false, onSlow = () => {}, onLost = () => {} } = {}) {
    const gl = canvas.getContext("webgl2", {
      alpha: false, antialias: false, depth: false, stencil: false,
      premultipliedAlpha: false, preserveDrawingBuffer: false, powerPreference: "high-performance",
    });
    if (!gl) return null;
    let hdr = Boolean(gl.getExtension("EXT_color_buffer_float"));
    const vao = gl.createVertexArray();
    let current = QUALITY[quality] ? quality : "medium";
    // One scene program per quality, compiled the first time it is needed and kept: a step down or
    // the benchmark switches between them without compiling again.
    const scenes = {};
    let scene = null;
    const build = () => {
      if (!scenes[current]) {
        const q = QUALITY[current];
        scenes[current] = program(gl, SCENE.replace("out vec4 outColor;",
          `out vec4 outColor;\n#define STEPS ${q.steps}\n#define STEP_SCALE ${q.stepScale.toFixed(2)}`));
      }
      scene = scenes[current];
    };
    build();
    const passes = { bright: program(gl, BRIGHT), blur: program(gl, BLUR), final: program(gl, FINAL) };
    // A driver that offers half floats but will not render to them gets eight-bit targets instead.
    let targets = null;
    const makeTargets = () => {
      if (targets) Object.values(targets).forEach((t) => t.free());
      const incomplete = () => {
        if (hdr) {
          hdr = false;
          queueMicrotask(makeTargets);
        }
      };
      targets = { scene: target(gl, hdr, incomplete), bright: target(gl, hdr, incomplete), blur: target(gl, hdr, incomplete) };
    };
    makeTargets();
    let raf = 0;
    let running = false;
    let lost = false;
    let destroyed = false;
    let last = null;
    let started = performance.now();
    // Frames counted over a window of wall time, not a count of frames, so a 120 Hz display and a
    // 60 Hz one are judged over the same two seconds.
    const pace = { at: 0, since: 0, slow: 0, frames: 0 };

    const draw = (v, seconds) => {
      const q = QUALITY[current];
      const dpr = Math.min(window.devicePixelRatio || 1, 2) * q.scale;
      const cssW = canvas.clientWidth;
      const cssH = canvas.clientHeight;
      const w = Math.max(1, Math.round(cssW * dpr));
      const h = Math.max(1, Math.round(cssH * dpr));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      targets.scene.size(w, h);
      gl.bindVertexArray(vao);
      // The scene.
      gl.bindFramebuffer(gl.FRAMEBUFFER, targets.scene.fb);
      gl.viewport(0, 0, w, h);
      gl.useProgram(scene.prog);
      gl.uniform2f(scene.uniforms.uCenter, v.cx * dpr, (cssH - v.cy) * dpr);
      gl.uniform1f(scene.uniforms.uPxPerRs, Math.max(v.pxPerRs * dpr, 0.5));
      gl.uniform1f(scene.uniforms.uTime, seconds);
      const lift = (42.3 * Math.PI) / 180; // a circle seen 47.7 degrees off its axis: height 0.673 of width
      gl.uniform2f(scene.uniforms.uView, Math.sin(lift), Math.cos(lift));
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      // The bleed.
      const bw = Math.max(1, w >> 1);
      const bh = Math.max(1, h >> 1);
      if (q.bloom) {
        targets.bright.size(bw, bh);
        targets.blur.size(bw, bh);
        gl.viewport(0, 0, bw, bh);
        gl.bindFramebuffer(gl.FRAMEBUFFER, targets.bright.fb);
        gl.useProgram(passes.bright.prog);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, targets.scene.tex);
        gl.uniform1i(passes.bright.uniforms.uScene, 0);
        if (hdr) gl.uniform2f(passes.bright.uniforms.uKnee, 0.7, 1.6);
        else gl.uniform2f(passes.bright.uniforms.uKnee, 0.5, 0.95);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
        gl.useProgram(passes.blur.prog);
        gl.uniform1i(passes.blur.uniforms.uSource, 0);
        for (let i = 0; i < 2; i += 1) {
          gl.bindFramebuffer(gl.FRAMEBUFFER, targets.blur.fb);
          gl.bindTexture(gl.TEXTURE_2D, targets.bright.tex);
          gl.uniform2f(passes.blur.uniforms.uStep, (1 + i) / bw, 0);
          gl.drawArrays(gl.TRIANGLES, 0, 3);
          gl.bindFramebuffer(gl.FRAMEBUFFER, targets.bright.fb);
          gl.bindTexture(gl.TEXTURE_2D, targets.blur.tex);
          gl.uniform2f(passes.blur.uniforms.uStep, 0, (1 + i) / bh);
          gl.drawArrays(gl.TRIANGLES, 0, 3);
        }
      }
      // To the screen.
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.viewport(0, 0, w, h);
      gl.useProgram(passes.final.prog);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, targets.scene.tex);
      gl.uniform1i(passes.final.uniforms.uScene, 0);
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, targets.bright.tex);
      gl.uniform1i(passes.final.uniforms.uBloom, 1);
      gl.uniform1f(passes.final.uniforms.uBloomOn, q.bloom && targets.bright.w ? 1 : 0);
      gl.uniform1f(passes.final.uniforms.uExposure, 0.95);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.activeTexture(gl.TEXTURE0);
    };

    //: Slower than about 50 frames a second for most of two seconds of wall time: one step down. A
    //: gap over 20ms is a missed 60 Hz frame; holding at a steady 30 would count as slow, since the
    //: whole page would be held there with it.
    const watch = (now) => {
      if (pace.at) {
        pace.frames += 1;
        if (now - pace.at > 20) pace.slow += 1;
        if (now - pace.since >= 2000) {
          if (pace.frames >= 20 && pace.slow > pace.frames * 0.6) {
            const down = lower(current);
            if (down) {
              current = down;
              build();
            }
            onSlow(down);
          }
          pace.since = now;
          pace.frames = 0;
          pace.slow = 0;
        }
      } else {
        pace.since = now;
      }
      pace.at = now;
    };

    const frame = (now) => {
      raf = 0;
      if (!running || lost) return;
      const v = view();
      if (v) {
        const key = `${v.cx.toFixed(1)}|${v.cy.toFixed(1)}|${v.pxPerRs.toFixed(3)}|${canvas.clientWidth}|${canvas.clientHeight}|${current}`;
        if (!still || key !== last) {
          // Wrapped once an hour, so a map left open for days keeps its angles precise; the disk's
          // streaks jump once an hour instead of slowly coarsening.
          draw(v, still ? 0 : ((now - started) / 1000) % 3600);
          last = key;
          if (!still) watch(now);
        }
      }
      raf = requestAnimationFrame(frame);
    };

    canvas.addEventListener("webglcontextlost", (event) => {
      event.preventDefault();
      lost = true;
      running = false;
      // `destroy()` loses the context on purpose; only a loss it did not ask for is news.
      if (!destroyed) onLost();
    });

    return {
      get quality() { return current; },
      setQuality(next) {
        if (!QUALITY[next] || next === current) return;
        current = next;
        build();
        last = null;
      },
      start() {
        if (running || lost) return;
        running = true;
        last = null;
        pace.at = 0;
        started = performance.now();
        raf = requestAnimationFrame(frame);
      },
      stop() {
        running = false;
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
      },
      //: The average milliseconds one frame takes at `medium`, waited for to the end, from a short
      //: run drawn into the canvas while it is still hidden. The hole is drawn large and centred, the
      //: most expensive way it will usually appear.
      benchmark(frames = 8) {
        const was = current;
        if (current !== "medium") {
          current = "medium";
          build();
        }
        const v = { cx: canvas.clientWidth / 2, cy: canvas.clientHeight / 2, pxPerRs: Math.min(canvas.clientWidth, canvas.clientHeight) / 22 };
        // `finish()` is allowed to return before the GPU is done, and in WebKit it does; reading one
        // pixel back cannot, so each frame is waited for by reading one.
        const pixel = new Uint8Array(4);
        const settle = () => gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
        draw(v, 0);
        settle();
        const begin = performance.now();
        for (let i = 0; i < frames; i += 1) {
          draw(v, i * 0.016);
          settle();
        }
        const ms = (performance.now() - begin) / frames;
        if (current !== was) {
          current = was;
          build();
        }
        last = null;
        return ms;
      },
      destroy() {
        this.stop();
        destroyed = true;
        Object.values(scenes).forEach((one) => gl.deleteProgram(one.prog));
        Object.values(passes).forEach((one) => gl.deleteProgram(one.prog));
        Object.values(targets).forEach((t) => t.free());
        gl.deleteVertexArray(vao);
        const lose = gl.getExtension("WEBGL_lose_context");
        if (lose) lose.loseContext();
      },
    };
  }

  window.PenumbraSky = { probe, create, chooseQuality, isSoftware, lower, QUALITY };
})();
