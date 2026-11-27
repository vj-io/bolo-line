// Browser speech for the operator screen: hold-to-talk recognition (Web Speech API, hi-IN),
// the Hindi read-back voice, and a plain recorder for the optional paid engine.
// listen() and record() return the same shape: { done, stop, abort }, where done resolves to
// { text, error } or { blob, error }.

// Calibration knob (PRD section 8, risk 2): keep listening this long after release so the last
// word is not cut off. Lower it if the live test shows no cut-off.
const RELEASE_TAIL_MS = 600;
const MAX_MS = 15000;

const Recognition = () => window.SpeechRecognition || window.webkitSpeechRecognition;

export const canListen = () => Boolean(Recognition());
export const canRecord = () => Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);

// Errors that mean the microphone cannot work here (refused, missing, offline, unsupported).
export const MIC_ERRORS = new Set(["not-allowed", "service-not-allowed", "audio-capture", "network", "language-not-supported"]);

/** Starts browser recognition. onWords(text) gets the running transcript as the browser reports it. */
export function listen(onWords) {
  const rec = new (Recognition())();
  rec.lang = "hi-IN";
  rec.continuous = true;
  rec.interimResults = true;
  let text = "";
  let error = null;
  rec.onresult = (e) => {
    text = [...e.results].map((r) => r[0].transcript).join(" ").replace(/\s+/g, " ").trim();
    onWords(text);
  };
  rec.onerror = (e) => { error = e.error; };
  const done = new Promise((resolve) => {
    rec.onend = () => { clearTimeout(cap); resolve({ text, error }); };
  });
  const cap = setTimeout(() => rec.stop(), MAX_MS);
  rec.start();
  return { done, stop: () => setTimeout(() => rec.stop(), RELEASE_TAIL_MS), abort: () => rec.abort() };
}

/** Records the microphone for the paid engine (POST /api/stt goes through stt_sarvam.js). */
export function record() {
  let mr;
  let cap;
  let stopped = false;
  const stop = () => {
    stopped = true;
    if (mr && mr.state !== "inactive") mr.stop();
  };
  const done = navigator.mediaDevices.getUserMedia({ audio: true }).then(
    (stream) => new Promise((resolve) => {
      const chunks = [];
      mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => chunks.push(e.data);
      mr.onstop = () => {
        clearTimeout(cap);
        stream.getTracks().forEach((t) => t.stop());
        resolve({ blob: new Blob(chunks, { type: mr.mimeType }), error: null });
      };
      mr.start();
      cap = setTimeout(stop, MAX_MS);
      if (stopped) stop();
    }),
    () => ({ blob: null, error: "not-allowed" }),
  );
  return { done, stop: () => setTimeout(stop, RELEASE_TAIL_MS), abort: stop };
}

let voicesLoaded;
function loadVoices() {
  if (!("speechSynthesis" in window)) return Promise.resolve();
  voicesLoaded ??= new Promise((resolve) => {
    if (speechSynthesis.getVoices().length) return resolve();
    speechSynthesis.addEventListener("voiceschanged", resolve, { once: true });
    setTimeout(resolve, 1500);
  });
  return voicesLoaded;
}

/** Speaks Devanagari text with a Hindi voice. Resolves false when the device has no Hindi voice. */
export async function speak(text) {
  await loadVoices();
  const voice = window.speechSynthesis?.getVoices().find((v) => /^hi([-_]|$)/i.test(v.lang));
  if (!voice) return false;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.voice = voice;
  u.lang = voice.lang;
  speechSynthesis.speak(u);
  return true;
}

export const stopSpeaking = () => window.speechSynthesis?.cancel();
