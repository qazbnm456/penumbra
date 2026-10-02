/* Penny, the half-lit moon, in a few seconds of her life: watching the moon's stories on television,
 * tripping and crying, drinking bubble tea, eating a mooncake, letting a sky lantern go, wearing a
 * pomelo-peel hat, dozing and juggling little planets. The desktop app's start screen plays one
 * while the server starts, and the workspace's empty map plays one while there is nothing on it.
 *
 * ONE source, in two places. This file and `penny-scenes.css` are the canonical copies; the start
 * screen cannot read them from the server (it is shown before the server exists), so
 * `desktop/splash/` carries byte-identical copies, and `tests/test_web_assets.py` fails when the two
 * differ. Edit here, then copy.
 *
 * Built with the DOM, never `innerHTML` (invariant 29), as inline SVG animated by CSS keyframes:
 * a few kilobytes a scene, themed by nothing outside it, and still under reduced motion.
 */
(function () {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  let made = 0;

  function el(tag, attrs, parent) {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (parent) parent.appendChild(node);
    return node;
  }

  function group(parent, cls, origin) {
    const g = el("g", cls ? { class: cls } : {}, parent);
    if (origin) g.style.transformOrigin = origin;
    return g;
  }

  // --- Penny herself ---------------------------------------------------------------------------------
  //: The mascot's moon (`mascot.svg`): lit on the upper right, in soft shadow on the lower left, with
  //: a face on the lit side. `mood` picks the eyes: happy (closed smiles), watching (open, looking
  //: right), crying (shut tight, with tears drawn by the scene) or sleepy (flat lines).
  function penny(parent, cx, cy, r, mood, defs) {
    const id = `pn-moon-${(made += 1)}`;
    const grad = el("linearGradient", { id, x1: 0, y1: 0.7, x2: 1, y2: 0.25 }, defs);
    [["0.1", "#84462a"], ["0.32", "#b8683a"], ["0.5", "#f6e8ce"], ["1", "#fff6e4"]].forEach(([offset, color]) => {
      el("stop", { offset, "stop-color": color }, grad);
    });
    const g = group(parent, "pn-penny", `${cx}px ${cy}px`);
    // A faint rim, so the lit side still has an edge on a light page.
    el("circle", { cx, cy, r, fill: `url(#${id})`, stroke: "#c9a37a", "stroke-width": 0.8, "stroke-opacity": 0.7 }, g);
    const u = r / 44; // the mascot is drawn at r = 44
    const fx = (dx) => cx + dx * u;
    const fy = (dy) => cy + dy * u;
    el("ellipse", { cx: fx(-2), cy: fy(6), rx: 6 * u, ry: 3.4 * u, fill: "#b8683a", opacity: 0.32 }, g);
    el("ellipse", { cx: fx(30), cy: fy(6), rx: 6 * u, ry: 3.4 * u, fill: "#b8683a", opacity: 0.32 }, g);
    const ink = { fill: "none", stroke: "#3a283c", "stroke-width": 2.6 * u, "stroke-linecap": "round" };
    if (mood === "watching") {
      el("circle", { cx: fx(6), cy: fy(-4), r: 3.2 * u, fill: "#3a283c" }, g);
      el("circle", { cx: fx(26), cy: fy(-4), r: 3.2 * u, fill: "#3a283c" }, g);
      el("ellipse", { cx: fx(16), cy: fy(7), rx: 3 * u, ry: 2.4 * u, fill: "#3a283c" }, g);
    } else if (mood === "crying") {
      el("path", { d: `M${fx(-1)} ${fy(-6)} l${7 * u} ${3 * u} l${-7 * u} ${3 * u}`, ...ink }, g);
      el("path", { d: `M${fx(31)} ${fy(-6)} l${-7 * u} ${3 * u} l${7 * u} ${3 * u}`, ...ink }, g);
      el("path", { d: `M${fx(10)} ${fy(10)} a${6 * u} ${5 * u} 0 0 1 ${12 * u} 0`, ...ink }, g);
    } else if (mood === "sleepy") {
      el("path", { d: `M${fx(0)} ${fy(-4)} h${8 * u} M${fx(20)} ${fy(-4)} h${8 * u}`, ...ink }, g);
      el("path", { d: `M${fx(12)} ${fy(6)} a${4 * u} ${3 * u} 0 0 0 ${8 * u} 0`, ...ink, "stroke-width": 2 * u }, g);
    } else {
      el("path", { d: `M${fx(0)} ${fy(-4)} a${4 * u} ${4 * u} 0 0 0 ${8 * u} 0 M${fx(20)} ${fy(-4)} a${4 * u} ${4 * u} 0 0 0 ${8 * u} 0`, ...ink }, g);
      el("path", { d: `M${fx(10)} ${fy(5)} a${4 * u} ${4 * u} 0 0 0 ${8 * u} 0`, ...ink, "stroke-width": 2.2 * u }, g);
    }
    return g;
  }

  function stars(parent, points) {
    points.forEach(([x, y, r], i) => {
      // Coloured by the stylesheet (`--pn-star`), pale on a dark page and deeper on a light one.
      const star = el("circle", { cx: x, cy: y, r, class: "pn-twinkle" }, parent);
      star.style.animationDelay = `${(i * 0.37) % 2}s`;
    });
  }

  // --- the television, and what is on it ------------------------------------------------------------
  function television(svg, defs) {
    const id = `pn-screen-${(made += 1)}`;
    const clip = el("clipPath", { id }, defs);
    el("rect", { x: 136, y: 40, width: 78, height: 54, rx: 4 }, clip);
    el("path", { d: "M160 30 L172 38 L186 26", fill: "none", stroke: "#84462a", "stroke-width": 2, "stroke-linecap": "round" }, svg);
    el("rect", { x: 128, y: 34, width: 94, height: 66, rx: 9, fill: "#3a2c4a", stroke: "#84462a", "stroke-width": 2 }, svg);
    el("rect", { x: 136, y: 40, width: 78, height: 54, rx: 4, fill: "#1d2442" }, svg);
    el("path", { d: "M146 100 l-4 10 M204 100 l4 10", stroke: "#84462a", "stroke-width": 2.4, "stroke-linecap": "round" }, svg);
    const screen = el("g", { "clip-path": `url(#${id})` }, svg);
    el("circle", { cx: 200, cy: 52, r: 7, fill: "#f6e8ce", opacity: 0.85 }, screen);
    return screen;
  }

  function watcher(svg, defs) {
    el("ellipse", { cx: 66, cy: 128, rx: 34, ry: 5, fill: "#000", opacity: 0.18 }, svg);
    const g = group(svg, "pn-bob", "66px 92px");
    penny(g, 66, 92, 32, "watching", defs);
  }

  const SCENES = {
    wugang: {
      caption: { zh: "電視上，吳剛又在砍桂樹了", en: "On television, Wu Gang is chopping the osmanthus again" },
      draw(svg, defs) {
        const screen = television(svg, defs);
        el("rect", { x: 166, y: 62, width: 6, height: 32, fill: "#6b4a2e" }, screen);
        el("circle", { cx: 169, cy: 58, r: 15, fill: "#3f6a33" }, screen);
        [[160, 54], [175, 52], [168, 64], [178, 62]].forEach(([x, y]) => el("circle", { cx: x, cy: y, r: 1.8, fill: "#ffb347" }, screen));
        el("circle", { cx: 152, cy: 74, r: 3.4, fill: "#f6e8ce" }, screen);
        el("path", { d: "M152 78 v10 M152 88 l-3 6 M152 88 l3 6", stroke: "#f6e8ce", "stroke-width": 2, "stroke-linecap": "round" }, screen);
        const axe = group(screen, "pn-chop", "153px 81px");
        el("path", { d: "M153 81 L163 74", stroke: "#c9a37a", "stroke-width": 2, "stroke-linecap": "round" }, axe);
        el("path", { d: "M161 71 l5 2 l-2 5 z", fill: "#dfe6ee" }, axe);
        watcher(svg, defs);
      },
    },
    rabbit: {
      caption: { zh: "電視上，月兔在搗藥", en: "On television, the Jade Rabbit pounds the elixir" },
      draw(svg, defs) {
        const screen = television(svg, defs);
        el("ellipse", { cx: 158, cy: 80, rx: 9, ry: 8, fill: "#f4f1ec" }, screen);
        el("circle", { cx: 164, cy: 71, r: 5, fill: "#f4f1ec" }, screen);
        el("ellipse", { cx: 162, cy: 61, rx: 1.8, ry: 6, fill: "#f4f1ec" }, screen);
        el("ellipse", { cx: 167, cy: 61, rx: 1.8, ry: 6, fill: "#f4f1ec" }, screen);
        el("circle", { cx: 166, cy: 70, r: 0.9, fill: "#3a283c" }, screen);
        el("path", { d: "M174 82 h20 l-3 10 h-14 z", fill: "#a88a63" }, screen);
        const pestle = group(screen, "pn-pound", "184px 70px");
        el("rect", { x: 182, y: 62, width: 4, height: 20, rx: 2, fill: "#d6b48c" }, pestle);
        watcher(svg, defs);
      },
    },
    change: {
      caption: { zh: "電視上，嫦娥奔月……是奔向我嗎？", en: "On television, Chang'e flies to the moon. Is it me?" },
      draw(svg, defs) {
        const screen = television(svg, defs);
        stars(screen, [[146, 50, 0.9], [184, 46, 0.8], [150, 86, 0.7]]);
        const flyer = group(screen, "pn-rise", "170px 80px");
        el("circle", { cx: 168, cy: 72, r: 3, fill: "#f6e8ce" }, flyer);
        el("path", { d: "M168 75 l-6 12 h12 z", fill: "#e8615a" }, flyer);
        el("path", { d: "M162 80 C154 84 152 90 146 92 M174 80 C182 84 184 90 190 90", fill: "none", stroke: "#ffd9a0", "stroke-width": 1.4, "stroke-linecap": "round" }, flyer);
        watcher(svg, defs);
      },
    },
    trip: {
      caption: { zh: "跌倒了……嗚嗚", en: "Tripped over. Sniff." },
      draw(svg, defs) {
        el("path", { d: "M20 126 H220", stroke: "#84462a", "stroke-width": 2, "stroke-linecap": "round", opacity: 0.6 }, svg);
        el("ellipse", { cx: 160, cy: 123, rx: 7, ry: 4, fill: "#8a847f" }, svg);
        const fallen = group(svg, "pn-tumble", "120px 96px");
        penny(fallen, 120, 96, 30, "crying", defs);
        [[104, 96], [138, 96]].forEach(([x, y], i) => {
          const tear = el("path", { d: `M${x} ${y} q-3 6 0 8 q3 -2 0 -8 z`, fill: "#8fc4ff", class: "pn-tear" }, svg);
          tear.style.animationDelay = `${i * 0.6}s`;
        });
        const spin = group(svg, "pn-spin", "120px 56px");
        [[106, 56], [134, 56], [120, 48]].forEach(([x, y]) => el("path", { d: `M${x} ${y - 4} l1.2 3 3 1.2 -3 1.2 -1.2 3 -1.2 -3 -3 -1.2 3 -1.2 z`, fill: "#ffd9a0" }, spin));
      },
    },
    boba: {
      caption: { zh: "來杯珍珠奶茶補充能量", en: "A bubble tea to recharge" },
      draw(svg, defs) {
        penny(group(svg, "pn-bob", "84px 88px"), 84, 88, 32, "happy", defs);
        el("path", { d: "M138 58 h40 l-6 62 h-28 z", fill: "#f3e6d3", opacity: 0.35, stroke: "#c9a37a", "stroke-width": 1.6 }, svg);
        el("path", { d: "M141 76 h34 l-4.4 44 h-25.2 z", fill: "#c99a6b" }, svg);
        [[148, 112], [156, 116], [164, 112], [170, 116], [152, 106], [166, 106]].forEach(([x, y]) => el("circle", { cx: x, cy: y, r: 3, fill: "#3a2626" }, svg));
        el("rect", { x: 160, y: 30, width: 6, height: 70, rx: 2, fill: "#e8615a" }, svg);
        [0, 1, 2].forEach((i) => {
          const pearl = el("circle", { cx: 163, cy: 96, r: 2.6, fill: "#3a2626", class: "pn-sip" }, svg);
          pearl.style.animationDelay = `${i * 0.8}s`;
        });
        el("rect", { x: 134, y: 52, width: 48, height: 8, rx: 3, fill: "#fff6e4", stroke: "#c9a37a", "stroke-width": 1.4 }, svg);
      },
    },
    mooncake: {
      caption: { zh: "中秋節，先吃一口月餅", en: "Mid-Autumn: a bite of mooncake first" },
      draw(svg, defs) {
        penny(group(svg, "pn-chew", "86px 86px"), 86, 86, 32, "happy", defs);
        const cake = group(svg, "", null);
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9].forEach((i) => {
          const a = (i / 10) * Math.PI * 2;
          el("circle", { cx: 168 + Math.cos(a) * 24, cy: 92 + Math.sin(a) * 24, r: 6, fill: "#c98a45" }, cake);
        });
        el("circle", { cx: 168, cy: 92, r: 24, fill: "#d99a52" }, cake);
        el("circle", { cx: 168, cy: 92, r: 14, fill: "none", stroke: "#a86c33", "stroke-width": 2 }, cake);
        el("path", { d: "M162 92 h12 M168 86 v12", stroke: "#a86c33", "stroke-width": 2, "stroke-linecap": "round" }, cake);
        // Bites: dark circles that appear one by one on the cake's edge, then the cake is whole again.
        [[150, 76], [146, 90], [152, 104]].forEach(([x, y], i) => {
          // Filled with the page's background by the stylesheet (`--pn-bg`), so a bite is a gap.
          const bite = el("circle", { cx: x, cy: y, r: 8, class: "pn-bite" }, svg);
          bite.style.animationDelay = `${i * 0.7}s`;
        });
      },
    },
    lantern: {
      caption: { zh: "放一盞天燈，許個願", en: "A sky lantern, and a wish" },
      draw(svg, defs) {
        stars(svg, [[30, 24, 1.2], [210, 30, 1], [180, 14, 0.8], [60, 40, 0.9]]);
        penny(svg, 78, 104, 30, "happy", defs);
        const up = group(svg, "pn-float", "160px 80px");
        const glowId = `pn-glow-${(made += 1)}`;
        const glow = el("radialGradient", { id: glowId }, defs);
        el("stop", { offset: 0, "stop-color": "#ffd9a0", "stop-opacity": 0.8 }, glow);
        el("stop", { offset: 1, "stop-color": "#ffd9a0", "stop-opacity": 0 }, glow);
        el("circle", { cx: 160, cy: 86, r: 30, fill: `url(#${glowId})` }, up);
        el("path", { d: "M146 70 Q160 58 174 70 L170 100 H150 Z", fill: "#ffcf7a", stroke: "#e0892f", "stroke-width": 1.4 }, up);
        el("path", { d: "M152 84 h16", stroke: "#e0892f", "stroke-width": 1.4 }, up);
        el("ellipse", { cx: 160, cy: 101, rx: 4, ry: 2, fill: "#ff7b2f" }, up);
      },
    },
    pomelo: {
      caption: { zh: "戴上柚子帽，賞月去", en: "A pomelo-peel hat for moon-gazing" },
      draw(svg, defs) {
        const g = group(svg, "pn-wobble", "110px 110px");
        penny(g, 110, 96, 32, "happy", defs);
        el("path", { d: "M84 74 Q110 34 136 74 Q110 66 84 74 Z", fill: "#a8c94a", stroke: "#6f8a2a", "stroke-width": 1.6 }, g);
        el("path", { d: "M110 46 v-8", stroke: "#6b4a2e", "stroke-width": 2.4, "stroke-linecap": "round" }, g);
        el("path", { d: "M110 40 q8 -6 12 0 q-6 4 -12 0", fill: "#5a8f42" }, g);
        el("circle", { cx: 184, cy: 112, r: 16, fill: "#c6d65a" }, svg);
        el("path", { d: "M184 96 v-5", stroke: "#6b4a2e", "stroke-width": 2, "stroke-linecap": "round" }, svg);
      },
    },
    sleepy: {
      caption: { zh: "再睡五分鐘就好", en: "Five more minutes" },
      draw(svg, defs) {
        stars(svg, [[40, 30, 1], [200, 40, 1.2], [170, 20, 0.8]]);
        penny(group(svg, "pn-breathe", "100px 92px"), 100, 92, 34, "sleepy", defs);
        [0, 1, 2].forEach((i) => {
          const z = el("text", { x: 138 + i * 12, y: 64 - i * 12, fill: "#c9a37a", "font-size": 12 + i * 3, "font-family": "Georgia, serif", class: "pn-z" }, svg);
          z.textContent = "z";
          z.style.animationDelay = `${i * 0.6}s`;
        });
      },
    },
    planets: {
      caption: { zh: "整理一下星星", en: "Tidying the planets" },
      draw(svg, defs) {
        penny(svg, 120, 100, 30, "happy", defs);
        const ring = group(svg, "pn-orbit", "120px 70px");
        [["#3e6ec3", 0], ["#d9663a", 1], ["#5a8f42", 2]].forEach(([color, i]) => {
          const a = (i / 3) * Math.PI * 2;
          el("circle", { cx: 120 + Math.cos(a) * 42, cy: 70 + Math.sin(a) * 16, r: 7, fill: color }, ring);
        });
        el("ellipse", { cx: 120, cy: 70, rx: 42, ry: 16, fill: "none", stroke: "#c9a37a", "stroke-width": 1, "stroke-dasharray": "2 4", opacity: 0.6 }, svg);
      },
    },
  };

  //: Play one scene in `container`: the named one, or one at random. `lang` is "zh" or "en" for the
  //: caption. Returns the scene's name, so a caller can avoid showing the same one twice in a row.
  function mount(container, { name, lang = "en" } = {}) {
    const names = Object.keys(SCENES);
    const chosen = SCENES[name] ? name : names[Math.floor(Math.random() * names.length)];
    const scene = SCENES[chosen];
    container.textContent = "";
    const box = document.createElement("figure");
    box.className = "penny-scene";
    box.dataset.scene = chosen;
    const svg = el("svg", { viewBox: "0 0 240 150", role: "img" });
    const caption = scene.caption[lang === "zh" ? "zh" : "en"];
    svg.setAttribute("aria-label", caption);
    const defs = el("defs", {}, svg);
    scene.draw(svg, defs);
    box.appendChild(svg);
    const words = document.createElement("figcaption");
    words.className = "penny-caption";
    words.textContent = caption;
    box.appendChild(words);
    container.appendChild(box);
    return chosen;
  }

  window.PennyScenes = { names: Object.keys(SCENES), mount };
})();
