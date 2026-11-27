// Owner dashboard: polls GET /api/rows every 2 seconds, draws new rows on at the top,
// and computes the three counts from the rows it holds. No page reload.
import rough from "/vendor/rough.esm.js";
import { sketchBox, drawOn, icon } from "/shared/sketch.js";

const POLL_MS = 2000;
const NS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const tok = (name) => getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
const cardMode = matchMedia("(max-width: 639.98px)");

const COLUMNS = [
  ["time", "Time"], ["station", "Station"], ["operator", "Operator"], ["batch", "Batch"],
  ["machine", "Machine"], ["temp", "Temp (°C)"], ["rejects", "Rejects"], ["status", "Status"],
];
const SOURCES = {
  mic_browser: "Microphone (browser speech)", mic_sarvam: "Microphone (Sarvam speech)",
  sample: "Sample", typed: "Typed", seed: "Seed row",
};

// ponytail: the first load takes the newest 200 rows; counts cover only rows the page holds.
const rows = [];          // every row seen, newest first
const boxes = new Map();  // row element -> sketchBox handle
let maxId = 0;
let loaded = false;
let fresh = [];           // rows from the latest arrival; outlined in table mode until the next one

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}

// Viewer's local time, 24-hour. Rows from another day also get the date.
function when(iso) {
  const d = new Date(iso);
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  if (d.toDateString() === new Date().toDateString()) return time;
  return `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })} ${time}`;
}

// A red-pen ring around a faulty temperature, or an amber-ink underline under a high reject count.
// The kit has neither (its loop is yellow), so the mark is drawn here with the vendored rough.js.
function penMark(target, kind, seed) {
  const pad = 14;
  const w = target.offsetWidth;
  const h = target.offsetHeight;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "sketch-layer");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", w + 2 * pad);
  svg.setAttribute("height", h + 2 * pad);
  svg.dataset.sketch = kind;
  Object.assign(svg.style, { left: `${-pad}px`, top: `${-pad}px` });
  const rc = rough.svg(svg);
  const mark = kind === "ring"
    ? rc.ellipse(pad + w / 2, pad + h / 2, w + 22, h + 10, { stroke: tok("red-pen"), strokeWidth: 2.4, roughness: 1.3, bowing: 1.5, seed })
    : rc.line(pad - 3, pad + h, pad + w + 3, pad + h - 2, { stroke: tok("amber-ink"), strokeWidth: 3, roughness: 1.2, seed });
  mark.dataset.part = "stroke";
  svg.append(mark);
  target.append(svg);
  return svg;
}

function addMarks(rowEl, row) {
  const marks = [];
  if (row.temp_out_of_limit) marks.push(penMark(rowEl.querySelector(".cell-temp .num"), "ring", row.id));
  if (row.rejects_over_limit) marks.push(penMark(rowEl.querySelector(".cell-rejects .num"), "underline", row.id));
  return marks;
}

// Phone: every row is a card with a shadow. Table: only the latest arrival keeps a drawn outline.
function decorate(rowEl) {
  if (cardMode.matches || rowEl.classList.contains("fresh")) {
    boxes.set(rowEl, sketchBox(rowEl, { shadow: cardMode.matches }));
  } else {
    boxes.get(rowEl)?.remove();
    boxes.delete(rowEl);
  }
}

function buildRow(row, write) {
  const w = write ? " write" : "";
  const rowEl = el("div", "log-row");
  rowEl.id = `row-${row.id}`;
  rowEl.setAttribute("role", "row");
  const cells = {};
  for (const [key, label] of COLUMNS) {
    const cell = el("div", `cell cell-${key}`);
    cell.setAttribute("role", "cell");
    cell.dataset.label = label;
    cells[key] = cell;
    rowEl.append(cell);
  }

  const detailId = `detail-${row.id}`;
  const open = el("button", `row-open${w}`, String(row.batch_no));
  open.type = "button";
  open.setAttribute("aria-expanded", "false");
  open.setAttribute("aria-controls", detailId);
  open.setAttribute("aria-label", `Batch ${row.batch_no}: show what was heard`);

  cells.time.append(el("span", `v${w}`, when(row.created_at)));
  cells.station.append(el("span", `v${w}`, row.station_name));
  cells.operator.append(el("span", `v${w}`, row.operator));
  cells.batch.append(open);
  cells.machine.append(el("span", `v${w}`, row.machine));
  cells.temp.append(el("span", `num${row.temp_out_of_limit ? " bad" : ""}${w}`, String(row.temperature_c)));
  cells.rejects.append(el("span", `num${row.rejects_over_limit ? " warn" : ""}${w}`, String(row.rejects)));
  if (row.temp_out_of_limit) cells.status.append(el("span", `chip chip-bad${w}`, "Temp out of limit"));
  if (row.rejects_over_limit) cells.status.append(el("span", `chip chip-warn${w}`, "Rejects high"));
  if (!row.temp_out_of_limit && !row.rejects_over_limit) cells.status.append(el("span", `v${w}`, "OK"));

  const detail = el("div", "detail");
  detail.id = detailId;
  detail.hidden = true;
  detail.setAttribute("role", "cell");
  detail.setAttribute("aria-colspan", String(COLUMNS.length));
  const heard = el("p");
  heard.append(el("span", "detail-k", "Heard: "), el("span", "detail-transcript", row.transcript || "No transcript"));
  const source = el("p");
  source.append(el("span", "detail-k", "Source: "), el("span", "detail-source", SOURCES[row.source] ?? row.source));
  detail.append(heard, source);
  if (row.audio_url) {
    const audio = el("audio");
    audio.controls = true;
    audio.preload = "none";
    audio.src = row.audio_url;
    audio.setAttribute("aria-label", `Recording of batch ${row.batch_no}`);
    detail.append(audio);
  }
  rowEl.append(detail);

  rowEl.addEventListener("click", (event) => {
    if (detail.contains(event.target)) return;
    detail.hidden = !detail.hidden;
    open.setAttribute("aria-expanded", String(!detail.hidden));
  });
  return rowEl;
}

function updateCounts(animate) {
  const values = {
    "count-all": rows.length,
    "count-temp": rows.filter((r) => r.temp_out_of_limit).length,
    "count-rejects": rows.filter((r) => r.rejects_over_limit).length,
  };
  for (const [id, value] of Object.entries(values)) {
    const n = $(id).querySelector(".count-n");
    if (n.textContent === String(value)) continue;
    n.textContent = value;
    if (animate) drawOn(n.parentElement); // rewrites the number only
  }
}

function take(newRows) {
  const first = !loaded;
  if (newRows.length && !first) {
    for (const rowEl of fresh) {
      rowEl.classList.remove("fresh");
      decorate(rowEl);
    }
    fresh = [];
  }
  const body = $("log-body");
  if (newRows.length) $("log").hidden = false; // shown before rows are measured for their pen marks
  for (const row of [...newRows].reverse()) { // the API sends newest first; each goes on top
    if (row.id <= maxId) continue;
    maxId = row.id;
    rows.unshift(row);
    const rowEl = buildRow(row, !first);
    body.prepend(rowEl);
    if (first) {
      decorate(rowEl);
      addMarks(rowEl, row);
    } else {
      rowEl.classList.add("fresh");
      fresh.push(rowEl);
      decorate(rowEl);
      // outline, then values, then the pen marks
      drawOn(rowEl).then(() => addMarks(rowEl, row).forEach((svg) => drawOn(svg)));
    }
  }
  updateCounts(!first);
  loaded = true;
  $("log").hidden = rows.length === 0;
  $("log-state").hidden = rows.length > 0;
  $("log-state").textContent = "No batches logged yet";
  if (first) drawOn(document.querySelector("main"));
}

async function poll() {
  try {
    const res = await fetch(`/api/rows?after_id=${maxId}&limit=200`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    $("offline").hidden = true;
    take(data.rows);
  } catch {
    $("offline").hidden = false;
  }
  setTimeout(poll, POLL_MS);
}

await document.fonts.ready;
$("offline").prepend(icon("cross"));
for (const id of ["count-all", "count-temp", "count-rejects"]) sketchBox($(id));
cardMode.addEventListener("change", () => $("log-body").querySelectorAll(".log-row").forEach(decorate));
poll();
