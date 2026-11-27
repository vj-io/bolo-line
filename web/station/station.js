// Operator screen (PRD 5.1): the state machine, hold-to-speak, the read-back, the value boxes,
// the yes and no buttons, the engine badge and the tester panel.
// Modes: idle, readback, asking, confirm, saved. Listening and busy are flags on top of a mode,
// so an answer spoken at read-back still knows it is an answer.
import {
  sketchBox, sketchCircle, sketchLoop, sketchSwash, sketchStrike, sketchTick, sketchArrow, drawOn, icon, reducedMotion,
} from "/shared/sketch.js";
import { sarvamConfigured, transcribe } from "/shared/stt_sarvam.js";
import * as speech from "/station/speech.js";

const FIELDS = ["batch_no", "machine", "temperature_c", "rejects"];
const LABELS = { batch_no: "Batch", machine: "Machine", temperature_c: "Temp °C", rejects: "Rejects" };
const ICONS = { batch_no: "batch", machine: "machine", temperature_c: "temperature", rejects: "rejects" };
const LANG_KEY = "bolo.lang"; // localStorage: the language last chosen on this device
const SHORT_PRESS_MS = 500;
const SAVED_MS = 2500;
const BOIL_MS = 135;

const $ = (id) => document.getElementById(id);
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}
const wait = (ms) => new Promise((r) => setTimeout(r, reducedMotion() ? 0 : ms));

let station, prompts, languages, lang; // lang: the selected entry of config.languages; prompts: its prompts
const st = {
  mode: "loading", res: null, utterances: [], source: null, audioUrl: null, unclear: 0,
  busy: false, listening: false, micOk: false, engine: "browser", gen: 0,
  loop: null, savedTimer: 0, arrow: null, press: null, boil: 0,
};
const boxes = {}; // field -> { wrap, box, labelText, heard, value, note, swash, strike }
const sampleButtons = [];
const langButtons = [];

// ---------- server ----------
async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(data.message || `HTTP ${r.status}`), { status: r.status });
  return data;
}
const parse = (text, draft = null, expect = null) => api("/api/parse", { station_id: station.id, text, draft, expect, lang: lang.code });

async function busy(fn) {
  st.busy = true;
  $("error").hidden = true; // a note from an earlier failed call must not outlive the next attempt
  renderControls();
  try {
    await fn();
  } catch (err) {
    showError(err);
  } finally {
    st.busy = false;
    renderControls();
  }
}

// ---------- voice ----------
async function say(p) {
  const spoken = await speech.speak(p.text, lang.locale);
  $("voice-note").hidden = spoken;
}

// ---------- building the page ----------
function buildBoxes() {
  for (const f of FIELDS) {
    const wrap = el("div", "field");
    const box = el("div", "value-box");
    box.id = `box-${f}`;
    const label = el("span", "label");
    const labelText = el("span", null, LABELS[f]);
    label.append(icon(ICONS[f]), labelText);
    const heard = el("span", "heard write");
    heard.hidden = true;
    const value = el("span", "value write");
    value.id = `val-${f}`;
    box.append(label, heard, value);
    const note = el("p", "field-note");
    wrap.append(box, note);
    $("values").append(wrap);
    boxes[f] = { wrap, box, labelText, heard, value, note, swash: null, strike: null };
  }
}

function buildEngine(config) {
  const e = $("engine");
  if (sarvamConfigured(config)) {
    const set = el("fieldset", "engine-switch");
    set.append(el("legend", null, "Speech engine"));
    for (const [value, text] of [["browser", "Browser (no key needed)"], ["sarvam", "Sarvam"]]) {
      const label = el("label");
      const input = el("input");
      Object.assign(input, { type: "radio", name: "engine", value, checked: value === st.engine });
      input.addEventListener("change", () => { st.engine = value; renderMic(); });
      label.append(input, ` ${text}`);
      set.append(label);
    }
    e.append(set);
  } else {
    e.append(el("span", "engine-badge", "Speech engine: Browser (no key needed)"),
      el("span", "note", `Sarvam: ${config.engines.sarvam.message}`));
  }
  sketchBox(e, { fill: "marker-1", shadow: false });
}

// One button per language pack, each in its own script. The selected one carries a tick and a
// yellow fill (never colour alone) and aria-pressed.
function buildLangs() {
  for (const l of languages) {
    const b = el("button", "btn lang");
    b.type = "button";
    b.dataset.code = l.code;
    const name = el("span", null, l.name);
    name.lang = l.code;
    b.append(icon("tick"), name);
    if (l.status === "beta") b.append(el("span", "beta", "beta"));
    b.addEventListener("click", () => setLang(l.code));
    $("langs").append(b);
    langButtons.push(b);
  }
}

function buildSamples(samples) {
  for (const s of samples) {
    const b = el("button", "btn sample");
    b.type = "button";
    b.dataset.when = s.when;
    b.dataset.lang = s.lang ?? "hi"; // the samples outside a language pack are the Hindi ones
    b.append(el("span", null, s.label), el("span", "note", s.audio_url ? "Recorded sample" : "Sample sentence, no recording"));
    if (s.audio_url) b.dataset.recorded = "yes";
    b.addEventListener("click", () => runSample(s));
    $("samples").append(b);
    sampleButtons.push(b);
    sketchBox(b, { shadow: false });
  }
}

// ---------- rendering ----------
function setMode(mode) {
  st.mode = mode;
  document.body.dataset.state = mode;
  renderControls();
}

const whenKey = () => (st.mode === "idle" ? "idle" : st.mode === "asking" ? `ask:${st.res.ask}` : null);

function renderControls() {
  const locked = st.busy || st.listening;
  $("yesno").hidden = !(st.mode === "readback" || st.mode === "confirm");
  $("yes").disabled = $("no").disabled = locked;
  const key = whenKey();
  for (const b of sampleButtons) {
    b.hidden = b.dataset.when !== key || b.dataset.lang !== lang.code;
    b.disabled = locked;
  }
  for (const b of langButtons) b.disabled = locked;
  $("typed").disabled = $("send").disabled = locked || st.mode === "saved" || st.mode === "loading";
  document.body.dataset.listening = st.listening ? "yes" : "no";
}

function renderMic(ok = st.engine === "sarvam" ? speech.canRecord() : speech.canListen()) {
  st.micOk = ok;
  $("mic").disabled = !st.micOk;
  $("mic-label").textContent = st.micOk ? lang.labels.mic : lang.labels.mic_unavailable;
  $("mic-note").textContent = st.micOk ? "hold and speak" : "Use a sample or type below";
  sketchCircle($("mic-disc"), { fill: st.micOk ? "yellow" : "marker-1" });
  if (!st.micOk) $("tester").open = true;
}

// Everything on the screen that is written in the selected language.
function renderLang() {
  for (const b of langButtons) {
    const on = b.dataset.code === lang.code;
    b.setAttribute("aria-pressed", String(on));
    b.classList.toggle("on", on);
    sketchBox(b, { fill: on ? "yellow" : "paper", shadow: false });
  }
  $("yes-label").textContent = lang.labels.yes;
  $("no-label").textContent = lang.labels.no;
  $("saved-text").textContent = prompts.saved.roman;
  $("voice-note").textContent = `${lang.name_en} voice not available on this device`;
  $("voice-note").hidden = true;
  const recorded = sampleButtons.some((b) => b.dataset.lang === lang.code && b.dataset.recorded);
  $("tester-summary").textContent = `No ${lang.name_en}? No mic? Try a ${recorded ? "recorded sample" : "sample sentence"}`;
}

function setLang(code) {
  if (st.busy || st.listening || code === lang.code) return;
  lang = languages.find((l) => l.code === code);
  prompts = lang.prompts;
  try {
    localStorage.setItem(LANG_KEY, code);
  } catch { /* storage refused: the choice lasts until the page is reloaded */ }
  speech.stopSpeaking();
  renderLang();
  renderMic(st.micOk);
  toIdle(); // a row half said in the old language is dropped
}

// The machine is shown as its number, large, with its type as the label (design contract: 56 px values).
function display(f, v) {
  if (v == null) return { value: "", label: LABELS[f] };
  if (f === "machine") {
    const m = station.machines.find((x) => x.name === v);
    if (m) return { value: String(m.number), label: v.replace(/\s*\d+$/, "") };
  }
  return { value: String(v), label: LABELS[f] };
}

function paintBoxes(fields, problems = []) {
  for (const f of FIELDS) {
    const b = boxes[f];
    const v = fields?.[f] ?? null;
    b.swash?.remove();
    b.strike?.remove();
    b.swash = b.strike = null;
    const d = display(f, v);
    b.value.textContent = d.value;
    b.labelText.textContent = d.label;
    b.heard.hidden = true;
    b.note.hidden = false;
    b.note.replaceChildren();
    sketchBox(b.box, { fill: v == null ? "marker-1" : "paper" });
  }
  for (const p of problems) {
    if (p.reason !== "impossible") continue;
    const s = el("span", "struck write");
    s.append(el("span", "sr-only", "Not possible: "), String(p.value));
    boxes[p.field].note.append(s);
    sketchStrike(s);
  }
}

const fill = (template, values) => template.replace(/\{(\w+)\}/g, (_, k) => values[k]);

function noteFlags(flags) {
  const t = station.limits.temperature_c;
  const r = station.limits.rejects;
  if (flags.temp_out_of_limit) {
    boxes.temperature_c.note.append(el("span", "warn write", fill(lang.labels.temp_limit, t)));
  }
  if (flags.rejects_over_limit) {
    boxes.rejects.note.append(el("span", "warn write", fill(lang.labels.rejects_limit, r)));
  }
}

const freshOf = (fields, before) => new Set(FIELDS.filter((f) => fields[f] != null && fields[f] !== before?.[f]));

// Draws the listed boxes on left to right; then each value just captured gets a yellow swash and
// the box's note (a flag or a crossed-out value) is written under it.
function drawFields(list, fresh) {
  const gen = st.gen;
  list.forEach((f, i) => {
    const b = boxes[f];
    b.note.hidden = !reducedMotion();
    drawOn(b.box, { delay: i * 350 }).then(() => {
      if (gen !== st.gen) return;
      if (fresh.has(f)) {
        b.swash = sketchSwash(b.value);
        drawOn(b.value);
      }
      b.note.hidden = false;
      drawOn(b.note);
    });
  });
}

function setPrompt(text) {
  $("prompt").textContent = text;
  $("prompt").hidden = !text;
  if (text) drawOn($("prompt-wrap"));
}

function showReply(text, bad) {
  const r = $("reply");
  r.replaceChildren();
  r.classList.toggle("bad", bad);
  if (bad) r.append(icon("cross"));
  r.append(el("span", null, text));
  r.hidden = false;
  drawOn($("reply-wrap"));
}

function clearMessages() {
  $("reply").hidden = true;
  $("error").hidden = true;
}

function showError(err) {
  $("error").textContent = err.status ? `Server said: ${err.message}` : "Could not reach the server. Try again.";
  $("error").hidden = false;
}

// ---------- transcript ----------
function showExample() {
  $("transcript").replaceChildren(el("span", "note", `Example: ${lang.labels.example}`));
}

// A new utterance from any source: leave the saved screen at once, stop the read-back voice, and
// start a fresh transcript line where earlier utterances of this row stay as plain text.
function beginUtterance() {
  if (st.mode === "saved") toIdle();
  speech.stopSpeaking();
  clearMessages();
  const t = $("transcript");
  t.replaceChildren();
  if (st.utterances.length) t.append(el("span", "prev", `${st.utterances.join(" / ")} /`));
}

// Words appear as they are reported, each with a yellow swash (the operator's voice).
function writeWords(text) {
  const t = $("transcript");
  const words = text.split(/\s+/).filter(Boolean);
  const spans = [...t.querySelectorAll(".word")];
  words.forEach((w, i) => {
    let s = spans[i];
    if (s && s.dataset.word === w) return;
    if (!s) {
      s = el("span", "word");
      t.append(" ", s); // the space keeps words apart for screen readers; flex layout ignores it
    }
    s._swash?.remove();
    s.dataset.word = w;
    s.textContent = w;
    s._swash = sketchSwash(s);
    drawOn(s);
  });
  spans.slice(words.length).forEach((s) => s.remove());
}

async function typeWords(text) {
  const words = text.split(/\s+/).filter(Boolean);
  for (let i = 1; i <= words.length; i += 1) {
    writeWords(words.slice(0, i).join(" "));
    await wait(260);
  }
}

function strikeWords() {
  for (const s of $("transcript").querySelectorAll(".word")) {
    s._swash?.remove();
    s._swash = null;
    sketchStrike(s);
    drawOn(s);
  }
}

// ---------- arrow to the box being asked for ----------
function pointAt(f) {
  clearArrow();
  const b = boxes[f];
  const from = el("span", "arrow-from");
  const to = el("span", "arrow-to");
  b.wrap.append(from);
  b.box.append(to);
  const handle = sketchArrow(from, to);
  st.arrow = { handle, from, to };
  drawOn(handle.svg);
}

function clearArrow() {
  if (!st.arrow) return;
  st.arrow.handle.remove();
  st.arrow.from.remove();
  st.arrow.to.remove();
  st.arrow = null;
}

// ---------- states ----------
function toIdle({ keepTranscript = false } = {}) {
  st.gen += 1;
  clearTimeout(st.savedTimer);
  clearArrow();
  st.loop?.remove();
  Object.assign(st, { loop: null, res: null, utterances: [], source: null, audioUrl: null, unclear: 0 });
  paintBoxes(null);
  setPrompt("");
  clearMessages();
  $("saved").hidden = true;
  if (!keepTranscript) showExample();
  setMode("idle");
}

function focusIfLost(id) {
  if (!document.activeElement || document.activeElement === document.body) $(id).focus();
}

function showReadback(res, before) {
  st.gen += 1;
  clearArrow();
  st.unclear = 0;
  setMode("readback");
  paintBoxes(res.fields, res.problems);
  noteFlags(res.flags);
  setPrompt(res.say.roman);
  say(res.say);
  drawFields(FIELDS, freshOf(res.fields, before));
  focusIfLost("yes");
  $("yesno").scrollIntoView({ block: "nearest" });
}

function showAsking(res, before) {
  st.gen += 1;
  setMode("asking");
  const fresh = freshOf(res.fields, before);
  paintBoxes(res.fields, res.problems);
  setPrompt(res.say.roman);
  say(res.say);
  pointAt(res.ask);
  drawFields(FIELDS.filter((f) => fresh.has(f) || res.problems.some((p) => p.field === f)), fresh);
  focusIfLost(st.micOk ? "mic" : "typed");
}

function showConfirm(res, before) {
  st.gen += 1;
  clearArrow();
  st.unclear = 0;
  setMode("confirm");
  paintBoxes(res.fields, res.problems);
  const b = boxes.machine;
  const heard = res.problems.find((p) => p.field === "machine")?.value;
  if (heard != null) {
    b.heard.textContent = heard;
    b.heard.hidden = false;
    b.strike = sketchStrike(b.heard);
  }
  const d = display("machine", res.suggest?.value ?? null);
  b.value.textContent = d.value;
  b.labelText.textContent = d.label;
  sketchBox(b.box, { fill: "paper" });
  setPrompt(res.say.roman);
  say(res.say);
  drawFields(FIELDS, freshOf(res.fields, before));
  focusIfLost("yes");
}

// not_understood and no_speech: the heard words are crossed out, the reply is written in red pen.
function showMisheard(reply) {
  toIdle({ keepTranscript: true });
  strikeWords();
  showReply(reply.roman, true);
  say(reply);
}

// The words are in another script than the selected language's, so nothing was read. The language
// buttons come into view; a question that is open stays open.
function wrongLanguage(res) {
  $("langs").scrollIntoView({ block: "nearest" });
  if (st.mode === "idle") return showMisheard(res.say);
  strikeWords();
  showReply(res.say.roman, true);
  say(res.say);
}

function showSaved() {
  st.gen += 1;
  const gen = st.gen;
  clearArrow();
  setMode("saved");
  setPrompt("");
  st.loop = sketchLoop($("values"));
  sketchTick($("tick"));
  $("saved").hidden = false;
  $("dash-link").hidden = false; // stays after the return to idle, so a tester can still follow it
  say(prompts.saved);
  Promise.all([
    drawOn($("values").querySelector(':scope > svg[data-sketch="loop"]')),
    drawOn($("saved"), { delay: 450 }),
  ]).then(() => {
    if (gen === st.gen) st.savedTimer = setTimeout(() => toIdle(), SAVED_MS);
  });
}

function discard() {
  toIdle();
  showReply(prompts.retry.roman, false);
  say(prompts.retry);
}

function unclear() {
  st.unclear += 1;
  if (st.unclear >= 2) return discard();
  setPrompt(prompts.unclear_confirm.roman);
  say(prompts.unclear_confirm);
}

function route(res) {
  const before = st.res?.fields;
  st.res = res;
  if (res.status === "complete") return showReadback(res, before);
  if (res.status === "need_field") return showAsking(res, before);
  if (res.status === "confirm_machine") return showConfirm(res, before);
  return showMisheard(res.say);
}

// ---------- input from any source ----------
async function handleText(text, source, audioUrl = null) {
  if (st.mode === "readback" || st.mode === "confirm") {
    const { answer } = await api("/api/confirm", { text, lang: lang.code });
    return answerWith(answer);
  }
  const asking = st.mode === "asking";
  const res = await parse(text, asking ? st.res.fields : null, asking ? st.res.ask : null);
  if (res.hint === "wrong_language") return wrongLanguage(res);
  if (text && !st.utterances.length) Object.assign(st, { source, audioUrl });
  if (text) st.utterances.push(text);
  route(res);
}

async function answerWith(answer) {
  if (answer === "unclear") return unclear();
  if (st.mode === "confirm") {
    const fields = { ...st.res.fields };
    if (answer === "yes") fields.machine = st.res.suggest.value;
    return route(await parse("", fields, null));
  }
  if (answer === "no") return discard();
  await api("/api/rows", {
    station_id: station.id, ...st.res.fields,
    transcript: st.utterances.join(" / "), source: st.source, audio_url: st.audioUrl,
  });
  showSaved();
}

function playClip(url) {
  if (!url) return Promise.resolve();
  const audio = new Audio(url);
  return new Promise((resolve) => {
    const done = () => { clearTimeout(cap); resolve(); };
    const cap = setTimeout(done, 15000);
    audio.addEventListener("ended", done, { once: true });
    audio.addEventListener("error", done, { once: true });
    audio.play().catch(done); // a missing clip must not block the sample: its transcript is still used
  });
}

function runSample(s) {
  if (st.busy || st.listening) return;
  busy(async () => {
    beginUtterance();
    const clip = playClip(s.audio_url);
    await typeWords(s.text);
    await clip;
    await handleText(s.text, "sample", s.audio_url);
  });
}

function sendTyped(e) {
  e.preventDefault();
  const text = $("typed").value.trim();
  if (!text || st.busy || st.listening) return;
  $("typed").value = "";
  busy(async () => {
    beginUtterance();
    writeWords(text);
    await handleText(text, "typed");
  });
}

// ---------- hold to speak ----------
function startBoil() {
  const ring = $("mic-ring");
  ring.hidden = false;
  const draw = () => sketchCircle(ring, { fill: "paper", shadow: false, seed: 1 + Math.floor(Math.random() * 2e6) });
  draw();
  if (!reducedMotion()) st.boil = setInterval(draw, BOIL_MS);
}

function stopBoil() {
  clearInterval(st.boil);
  $("mic-ring").hidden = true;
}

function pressStart() {
  if (st.press || st.busy || !st.micOk || st.mode === "loading") return;
  beginUtterance();
  const engine = st.engine;
  let ctl;
  try {
    ctl = engine === "sarvam" ? speech.record() : speech.listen(writeWords, lang.locale);
  } catch {
    return micUnavailable();
  }
  const press = { t0: performance.now(), ctl, cancelled: false };
  st.press = press;
  st.listening = true;
  renderControls();
  startBoil();
  ctl.done.then((result) => heard(press, engine, result));
}

function pressEnd() {
  const press = st.press;
  if (!press || press.released) return;
  press.released = true;
  if (performance.now() - press.t0 < SHORT_PRESS_MS) {
    press.cancelled = true;
    press.ctl.abort();
    endListening(press);
    return noSpeech();
  }
  press.ctl.stop();
}

function endListening(press) {
  if (st.press === press) st.press = null;
  st.listening = false;
  stopBoil();
  renderControls();
}

function heard(press, engine, result) {
  if (press.cancelled) return;
  endListening(press);
  if (speech.MIC_ERRORS.has(result.error)) return micUnavailable();
  busy(async () => {
    if (engine === "sarvam") {
      const r = await transcribe(result.blob, lang.locale);
      writeWords(r.text);
      return handleText(r.text, "mic_sarvam", r.audio_url ?? null);
    }
    return handleText(result.text, "mic_browser");
  });
}

// A press under 0.5 s: nothing was said. In the middle of a question the question stays open.
function noSpeech() {
  if (st.mode === "idle") return showMisheard(prompts.no_speech);
  showReply(prompts.no_speech.roman, true);
  say(prompts.no_speech);
}

const micUnavailable = () => renderMic(false);

function wireMic() {
  const mic = $("mic");
  const isHoldKey = (e) => e.key === " " || e.key === "Enter";
  mic.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    mic.setPointerCapture(e.pointerId);
    pressStart();
  });
  mic.addEventListener("pointerup", pressEnd);
  mic.addEventListener("pointercancel", pressEnd);
  mic.addEventListener("lostpointercapture", pressEnd);
  mic.addEventListener("keydown", (e) => {
    if (!isHoldKey(e)) return;
    e.preventDefault();
    if (!e.repeat) pressStart();
  });
  mic.addEventListener("keyup", (e) => {
    if (!isHoldKey(e)) return;
    e.preventDefault();
    pressEnd();
  });
  mic.addEventListener("blur", pressEnd);
  mic.addEventListener("contextmenu", (e) => e.preventDefault());
}

// ---------- start ----------
async function init() {
  buildBoxes();
  let config;
  try {
    config = await api("/api/config");
  } catch (err) {
    showError(err);
    return;
  }
  station = config.station;
  languages = config.languages;
  let saved = null;
  try {
    saved = localStorage.getItem(LANG_KEY);
  } catch { /* storage refused: start in the first language */ }
  lang = languages.find((l) => l.code === saved) ?? languages[0];
  prompts = lang.prompts;
  $("station-name").textContent = station.name;
  $("operator").textContent = `Operator: ${station.operator}`;
  showExample();
  if (sarvamConfigured(config) && !speech.canListen()) st.engine = "sarvam";
  await document.fonts.ready;

  $("mic-disc").append(icon("mic"));
  buildEngine(config);
  buildLangs();
  buildSamples([...config.samples, ...languages.flatMap((l) => l.samples)]);
  sketchBox($("tester-card"));
  sketchBox($("typed-wrap"), { shadow: false });
  sketchBox($("send"), { shadow: false });
  sketchBox($("yes"), { fill: "yellow" });
  sketchBox($("no"));
  $("tester").open = matchMedia("(min-width: 900px)").matches;
  renderLang();
  renderMic();
  wireMic();
  $("yes").addEventListener("click", () => busy(() => answerWith("yes")));
  $("no").addEventListener("click", () => busy(() => answerWith("no")));
  $("typed-form").addEventListener("submit", sendTyped);
  new ResizeObserver(() => st.arrow?.handle.redraw()).observe($("values"));
  toIdle();
}

init();
