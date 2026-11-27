// End-of-shift card and the first-try figure (package 7). Both come from GET /api/stats, which counts the current
// day in Asia/Kolkata on the server, so the day boundary is tested in one place (tests/test_events.py).
// Polls every 2 seconds like the log: a discarded attempt adds no row, so only the stats call can show it.
import { sketchBox } from "/shared/sketch.js";

const POLL_MS = 2000;
const $ = (id) => document.getElementById(id);
const ENGINES = { browser: "Browser speech", sarvam: "Sarvam", sample: "Sample", typed: "Typed" };

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}

const pct = (t) => `${Math.round(t.first_try_share * 100)}%`;

// Viewer's local time, 24-hour, as in the log, plus how long ago.
function lastLog(iso) {
  if (!iso) return "No batches yet today";
  const d = new Date(iso);
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const min = Math.max(0, Math.floor((Date.now() - d.getTime()) / 60000));
  const ago = min < 1 ? "just now" : min < 60 ? `${min} min ago` : `${Math.floor(min / 60)} h ${min % 60} min ago`;
  return `${time} (${ago})`;
}

function render(s) {
  const shift = s.shift;
  $("shift-batches").textContent = shift.batches;
  $("shift-last").textContent = lastLog(shift.last_log_at);

  const out = $("shift-out");
  out.replaceChildren(...shift.out_of_limit.map((o) => o.field === "temperature_c"
    ? el("li", "bad", `Batch ${o.batch_no}, ${o.machine}: ${o.value} °C, temp out of limit`)
    : el("li", "warn", `Batch ${o.batch_no}, ${o.machine}: ${o.value} rejects, rejects high`)));
  if (!shift.out_of_limit.length) out.append(el("li", "note", "None today"));

  $("shift-rejects").replaceChildren(...Object.entries(shift.rejects_by_machine).map(([machine, n]) => {
    const li = el("li");
    li.append(`${machine}: `, el("span", "shift-v", String(n)));
    return li;
  }));

  const t = s.total;
  $("first-try").textContent = t.attempts ? `First try: ${t.first_try} of ${t.attempts} (${pct(t)})` : "First try: no attempts yet today";
  $("first-try-by").textContent = Object.entries(s.by_engine)
    .map(([engine, e]) => `${ENGINES[engine] ?? engine} ${e.first_try} of ${e.attempts}`).join(" · ");
}

async function poll() {
  try {
    const res = await fetch("/api/stats", { cache: "no-store" });
    if (res.ok) render(await res.json());
  } catch {
    // the log's own poll shows the server-unreachable note
  }
  setTimeout(poll, POLL_MS);
}

await document.fonts.ready;
sketchBox($("shift"));
poll();
