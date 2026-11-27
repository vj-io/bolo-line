// Production record for one day (Asia/Kolkata), from GET /api/rows.json; the browser's print dialog makes the PDF.
import { sketchBox } from "/shared/sketch.js";

const $ = (id) => document.getElementById(id);
const IST = "Asia/Kolkata";
const SOURCES = { mic_browser: "Mic (browser)", mic_sarvam: "Mic (Sarvam)", sample: "Sample", typed: "Typed", seed: "Seed row" };
const time = new Intl.DateTimeFormat("en-GB", { timeZone: IST, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
const longDate = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", weekday: "long", day: "numeric", month: "long", year: "numeric" });
const todayIst = () => new Intl.DateTimeFormat("en-CA", { timeZone: IST }).format(new Date()); // YYYY-MM-DD

function cell(tr, text, cls) {
  const td = document.createElement("td");
  td.textContent = text;
  if (cls) td.className = cls;
  tr.append(td);
}

function status(row) {
  const words = [];
  if (row.temp_out_of_limit) words.push("Temp out of limit");
  if (row.rejects_over_limit) words.push("Rejects high");
  return words.length ? words.join(", ") : "OK";
}

async function load(day) {
  const url = new URL(location.href);
  url.searchParams.set("date", day);
  history.replaceState(null, "", url);
  $("csv").href = `/api/rows.csv?from=${day}&to=${day}`;
  $("date").textContent = longDate.format(new Date(`${day}T00:00:00Z`));
  $("state").hidden = false;
  $("state").textContent = "Reading the record...";
  try {
    const [config, data] = await Promise.all(["/api/config", `/api/rows.json?from=${day}&to=${day}`].map(async (path) => {
      const res = await fetch(path, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    }));
    render(config.station, data.rows);
  } catch {
    $("record").hidden = true;
    $("state").textContent = "Server unreachable. Reload the page to try again.";
  }
}

function render(station, rows) {
  const lim = station.limits;
  $("station").textContent = station.name;
  $("operator").textContent = [...new Set(rows.map((r) => r.operator))].join(", ") || station.operator;
  $("n-all").textContent = rows.length;
  $("n-temp").textContent = rows.filter((r) => r.temp_out_of_limit).length;
  $("n-rejects").textContent = rows.filter((r) => r.rejects_over_limit).length;
  $("limits").textContent = `Limits: temperature ${lim.temperature_c.min} to ${lim.temperature_c.max} °C, `
    + `at most ${lim.rejects.max} rejects a batch. Times in IST (UTC+05:30).`;
  const body = $("rows");
  body.replaceChildren();
  for (const row of rows) {
    const tr = document.createElement("tr");
    cell(tr, time.format(new Date(row.created_at)));
    cell(tr, String(row.batch_no), "num");
    cell(tr, row.machine);
    cell(tr, String(row.temperature_c), row.temp_out_of_limit ? "num bad" : "num");
    cell(tr, String(row.rejects), row.rejects_over_limit ? "num warn" : "num");
    cell(tr, status(row), row.temp_out_of_limit ? "bad" : row.rejects_over_limit ? "warn" : "");
    cell(tr, SOURCES[row.source] ?? row.source);
    cell(tr, row.transcript || "–", "heard");
    body.append(tr);
  }
  $("record").hidden = rows.length === 0;
  $("state").hidden = rows.length > 0;
  $("state").textContent = "No batches logged on this day.";
}

await document.fonts.ready;
sketchBox($("head"), { shadow: false });
const day = new URLSearchParams(location.search).get("date") || todayIst();
$("day").value = day;
$("day").max = todayIst();
$("day").addEventListener("change", () => { if ($("day").value) load($("day").value); });
$("print").addEventListener("click", () => print());
load(day);
