// Sketch kit: hand-drawn shapes for the sketchnote look, built on the vendored rough.js.
// Colours are read from tokens.css. Every shape is drawn at the element's measured pixel size and
// redrawn when the element resizes. The resting state is always the finished drawing; drawOn() only
// animates it when the user has not asked for reduced motion.
import rough from "/vendor/rough.esm.js";

const NS = "http://www.w3.org/2000/svg";
const PAD = 16; // room around an element for shadows, loops and overshoot

const tok = (name) => getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---- registry: one ResizeObserver redraws every sketch on an element ----
const drawers = new WeakMap(); // el -> Map(kind -> draw fn)
const observer = new ResizeObserver((entries) => {
  for (const { target } of entries) {
    const kinds = drawers.get(target);
    if (kinds) requestAnimationFrame(() => kinds.forEach((draw) => draw()));
  }
});

function register(el, kind, draw) {
  let kinds = drawers.get(el);
  if (!kinds) {
    kinds = new Map();
    drawers.set(el, kinds);
    observer.observe(el);
  }
  kinds.set(kind, draw);
  draw();
  return {
    redraw: draw,
    remove() {
      kinds.delete(kind);
      el.querySelector(`:scope > svg[data-sketch="${kind}"]`)?.remove();
    },
  };
}

function hashSeed(str) {
  let h = 7;
  for (const ch of str) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return (h % 2147483646) + 1;
}

// An SVG layer inside el, PAD px larger on each side. behind = under el's content.
function layer(el, kind, behind) {
  if (getComputedStyle(el).position === "static") el.style.position = "relative";
  el.style.isolation = "isolate";
  let svg = el.querySelector(`:scope > svg[data-sketch="${kind}"]`);
  if (!svg) {
    svg = document.createElementNS(NS, "svg");
    svg.dataset.sketch = kind;
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("class", "sketch-layer");
    behind ? el.prepend(svg) : el.append(svg);
  }
  const w = el.offsetWidth;
  const h = el.offsetHeight;
  svg.setAttribute("width", w + 2 * PAD);
  svg.setAttribute("height", h + 2 * PAD);
  svg.style.left = `${-PAD - el.clientLeft}px`;
  svg.style.top = `${-PAD - el.clientTop}px`;
  svg.style.zIndex = behind ? "-1" : "1";
  svg.replaceChildren();
  return { svg, rc: rough.svg(svg), w, h, x: PAD, y: PAD };
}

function part(node, name) {
  node.dataset.part = name;
  return node;
}

function roundRect(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  return `M${x + r} ${y} H${x + w - r} Q${x + w} ${y} ${x + w} ${y + r} V${y + h - r} Q${x + w} ${y + h} ${x + w - r} ${y + h} H${x + r} Q${x} ${y + h} ${x} ${y + h - r} V${y + r} Q${x} ${y} ${x + r} ${y} Z`;
}

const marker = (color, seed, gap = 3.5) => ({
  stroke: "none", fill: tok(color), fillStyle: "hachure", hachureAngle: -41,
  hachureGap: gap, fillWeight: 3, roughness: 1.2, seed,
});
const paperFill = (seed) => ({ stroke: "none", fill: tok("paper"), fillStyle: "solid", roughness: 0.6, seed });
const fineliner = (seed, width = 2) => ({ stroke: tok("ink"), strokeWidth: width, roughness: 1.1, bowing: 1, seed });

/** A wobbly rounded box behind el. fill: "paper" | "marker-1" | "yellow"; shadow: grey marker down-right. */
export function sketchBox(el, { fill = "paper", shadow = true, seed, radius = 14 } = {}) {
  seed = seed ?? hashSeed(el.id || el.className || "box");
  el.classList.add("sketched");
  return register(el, "box", () => {
    const { svg, rc, w, h, x, y } = layer(el, "box", true);
    if (w === 0 || h === 0) return;
    if (shadow) svg.append(part(rc.path(roundRect(x + 9, y + 9, w, h, radius), marker("marker-2", seed, 3)), "shadow"));
    svg.append(part(rc.path(roundRect(x, y, w, h, radius), paperFill(seed)), "paper"));
    if (fill && fill !== "paper") svg.append(part(rc.path(roundRect(x + 3, y + 3, w - 6, h - 6, radius), marker(fill, seed)), "fill"));
    svg.append(part(rc.path(roundRect(x, y, w, h, radius), fineliner(seed)), "outline"));
  });
}

/** The same for a disc (the mic button). */
export function sketchCircle(el, { fill = "yellow", seed, shadow = true } = {}) {
  seed = seed ?? hashSeed(el.id || "circle");
  el.classList.add("sketched");
  return register(el, "circle", () => {
    const { svg, rc, w, h, x, y } = layer(el, "circle", true);
    if (w === 0 || h === 0) return;
    const cx = x + w / 2;
    const cy = y + h / 2;
    if (shadow) svg.append(part(rc.ellipse(cx + 8, cy + 8, w, h, marker("marker-2", seed, 3)), "shadow"));
    svg.append(part(rc.ellipse(cx, cy, w, h, paperFill(seed)), "paper"));
    if (fill && fill !== "paper") svg.append(part(rc.ellipse(cx, cy, w - 6, h - 6, marker(fill, seed, 3)), "fill"));
    svg.append(part(rc.ellipse(cx, cy, w, h, fineliner(seed, 2.4)), "outline"));
  });
}

/** A yellow loop around el (a confirmed value). */
export function sketchLoop(el, { seed } = {}) {
  seed = seed ?? hashSeed(el.id || "loop");
  return register(el, "loop", () => {
    const { svg, rc, w, h, x, y } = layer(el, "loop", false);
    if (w === 0 || h === 0) return;
    const opts = { stroke: tok("yellow-deep"), strokeWidth: 3, roughness: 1.6, bowing: 2, seed };
    svg.append(part(rc.ellipse(x + w / 2, y + h / 2, w + 22, h + 18, opts), "stroke"));
  });
}

/** A yellow marker swash under el's text (the value just captured). */
export function sketchSwash(el, { seed } = {}) {
  seed = seed ?? hashSeed(el.id || "swash");
  return register(el, "swash", () => {
    const { svg, rc, w, h, x, y } = layer(el, "swash", true);
    if (w === 0 || h === 0) return;
    const thick = Math.max(8, Math.min(18, h * 0.32));
    const opts = { stroke: tok("yellow"), strokeWidth: thick, roughness: 1.4, bowing: 1.5, seed };
    svg.append(part(rc.line(x - 3, y + h * 0.74, x + w + 3, y + h * 0.68, opts), "stroke"));
  });
}

/** A red-pen line through el (a misheard or impossible value). */
export function sketchStrike(el, { seed } = {}) {
  seed = seed ?? hashSeed(el.id || "strike");
  return register(el, "strike", () => {
    const { svg, rc, w, h, x, y } = layer(el, "strike", false);
    if (w === 0 || h === 0) return;
    const opts = { stroke: tok("red-pen"), strokeWidth: 2.6, roughness: 1.3, seed };
    svg.append(part(rc.line(x - 5, y + h * 0.58, x + w + 5, y + h * 0.44, opts), "stroke"));
  });
}

/** A green tick drawn into el (saved). */
export function sketchTick(el, { seed } = {}) {
  seed = seed ?? hashSeed(el.id || "tick");
  return register(el, "tick", () => {
    const { svg, rc, w, h, x, y } = layer(el, "tick", false);
    if (w === 0 || h === 0) return;
    const pts = [[x + w * 0.12, y + h * 0.55], [x + w * 0.4, y + h * 0.85], [x + w * 0.9, y + h * 0.12]];
    const opts = { stroke: tok("green-tick"), strokeWidth: 4, roughness: 1, seed };
    svg.append(part(rc.linearPath(pts, opts), "stroke"));
  });
}

/** A fat yellow arrow from one element to another. Lives in a page-level layer; returns { redraw, remove }. */
export function sketchArrow(fromEl, toEl, { seed = 11 } = {}) {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", "sketch-layer");
  svg.dataset.sketch = "arrow";
  Object.assign(svg.style, { left: "0", top: "0", zIndex: "2" });
  document.body.append(svg);

  const draw = () => {
    const doc = document.documentElement;
    svg.setAttribute("width", doc.scrollWidth);
    svg.setAttribute("height", doc.scrollHeight);
    svg.replaceChildren();
    const a = fromEl.getBoundingClientRect();
    const b = toEl.getBoundingClientRect();
    if (!a.width || !b.width) return;
    const ax = a.left + a.width / 2 + scrollX, ay = a.top + a.height / 2 + scrollY;
    const bx = b.left + b.width / 2 + scrollX, by = b.top + b.height / 2 + scrollY;
    const len = Math.hypot(bx - ax, by - ay);
    const ux = (bx - ax) / len, uy = (by - ay) / len;
    // start and stop at the boxes' edges (approximated by half their smaller side)
    const s = Math.min(a.width, a.height) / 2 + 6, e = Math.min(b.width, b.height) / 2 + 8;
    const x0 = ax + ux * s, y0 = ay + uy * s, x1 = bx - ux * e, y1 = by - uy * e;
    const shaft = 9, head = 22, headLen = 26;
    const nx = -uy, ny = ux;
    const hx = x1 - ux * headLen, hy = y1 - uy * headLen;
    const pts = [
      [x0 + nx * shaft, y0 + ny * shaft], [hx + nx * shaft, hy + ny * shaft], [hx + nx * head, hy + ny * head],
      [x1, y1], [hx - nx * head, hy - ny * head], [hx - nx * shaft, hy - ny * shaft], [x0 - nx * shaft, y0 - ny * shaft],
    ];
    const rc = rough.svg(svg);
    svg.append(part(rc.polygon(pts, marker("yellow", seed, 3)), "fill"));
    svg.append(part(rc.polygon(pts, fineliner(seed)), "outline"));
  };
  draw();
  addEventListener("resize", draw);
  return { svg, redraw: draw, remove() { removeEventListener("resize", draw); svg.remove(); } };
}

// ---- draw-on: outline, then fill, then shadow, then strokes, then .write text ----
const ORDER = { outline: [0, 380], paper: [300, 0], fill: [300, 380], shadow: [600, 260], stroke: [0, 420] };

/** Plays the draw-on for every sketch shape inside el (or el itself). Resolves when finished. */
export function drawOn(el, { delay = 0 } = {}) {
  if (reducedMotion()) return Promise.resolve();
  const anims = [];
  const layers = el.matches?.("svg[data-sketch]") ? [el] : [...el.querySelectorAll("svg[data-sketch]")];
  let end = delay;
  for (const svg of layers) {
    for (const g of svg.querySelectorAll("[data-part]")) {
      const [start, dur] = ORDER[g.dataset.part] ?? [0, 380];
      if (!dur) continue;
      for (const p of g.querySelectorAll("path")) {
        if (p.getAttribute("stroke") === "none") continue; // solid fills appear with their outline
        p.setAttribute("pathLength", "1");
        anims.push(p.animate(
          [{ strokeDasharray: "1 1", strokeDashoffset: 1 }, { strokeDasharray: "1 1", strokeDashoffset: 0 }],
          { duration: dur, delay: delay + start, easing: "ease-out", fill: "backwards" },
        ));
        end = Math.max(end, delay + start + dur);
      }
    }
  }
  // Words are written left to right at about 0.3 s a word, after the shapes.
  for (const t of el.querySelectorAll(".write")) {
    const words = Math.max(1, (t.textContent || "").trim().split(/\s+/).length);
    anims.push(t.animate(
      [{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0 0 0)" }],
      { duration: Math.min(1400, 300 * words), delay: end, easing: "linear", fill: "backwards" },
    ));
  }
  return Promise.all(anims.map((a) => a.finished)).then(() => undefined);
}

// ---- icons: fineliner outlines with a grey marker volume, drawn once per name ----
const ICONS = {
  batch: (rc) => [
    rc.rectangle(6, 26, 36, 14, marker("marker-1", 3)), rc.rectangle(6, 26, 36, 14, ink(3)),
    rc.rectangle(11, 13, 26, 13, ink(4)), rc.line(16, 19, 32, 19, ink(5, 1.5)),
  ],
  machine: (rc) => [
    rc.rectangle(6, 8, 36, 32, marker("marker-1", 6)), rc.rectangle(6, 8, 36, 32, ink(6)),
    rc.rectangle(12, 19, 24, 15, ink(7)), rc.circle(14, 13.5, 4, ink(8, 1.5)), rc.circle(22, 13.5, 4, ink(9, 1.5)),
    rc.line(14, 26, 34, 26, ink(10, 1.2)),
  ],
  temperature: (rc) => [
    rc.path(roundRect(19, 5, 10, 30, 5), ink(11)), rc.circle(24, 38, 13, marker("marker-1", 12, 2.5)),
    rc.circle(24, 38, 13, ink(12)), rc.line(24, 34, 24, 14, ink(13, 3)),
    rc.line(31, 12, 35, 12, ink(14, 1.5)), rc.line(31, 18, 35, 18, ink(15, 1.5)), rc.line(31, 24, 35, 24, ink(16, 1.5)),
  ],
  rejects: (rc) => [
    rc.circle(24, 24, 34, marker("marker-1", 17)), rc.circle(24, 24, 34, ink(17)),
    rc.line(15, 15, 33, 33, ink(18, 2.5)), rc.line(33, 15, 15, 33, ink(19, 2.5)),
  ],
  mic: (rc) => [
    rc.path(roundRect(17, 5, 14, 24, 7), marker("marker-1", 20, 2.5)), rc.path(roundRect(17, 5, 14, 24, 7), ink(20)),
    rc.path("M11 22 Q11 36 24 36 Q37 36 37 22", ink(21)), rc.line(24, 36, 24, 43, ink(22)), rc.line(16, 43, 32, 43, ink(23)),
  ],
  tick: (rc) => [rc.linearPath([[9, 26], [20, 37], [40, 11]], ink(24, 3.5))],
  cross: (rc) => [rc.line(12, 12, 36, 36, ink(25, 3)), rc.line(36, 12, 12, 36, ink(26, 3))],
};
function ink(seed, width = 2) {
  return { stroke: "currentColor", strokeWidth: width, roughness: 1, bowing: 1, seed };
}

/** An inline SVG icon (48x48 viewBox, sized by the .icon class). Lines use currentColor. */
export function icon(name, { label } = {}) {
  const make = ICONS[name];
  if (!make) throw new Error(`unknown icon: ${name}`);
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 48 48");
  svg.setAttribute("class", `icon icon-${name}`);
  if (label) {
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", label);
  } else {
    svg.setAttribute("aria-hidden", "true");
  }
  for (const node of make(rough.svg(svg))) svg.append(node);
  return svg;
}
