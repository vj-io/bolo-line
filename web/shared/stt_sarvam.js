// Sarvam, the optional paid engine: speech-to-text for the microphone (POST /api/stt) and the
// read-back voice (POST /api/tts). Every language argument is a BCP-47 code such as "hi-IN".

const EXT = { "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav" };

/** True when the server has a Sarvam key (GET /api/config). Both speech-to-text and the voice need it. */
export function sarvamConfigured(config) {
  return Boolean(config?.engines?.sarvam?.configured);
}

async function failure(r) {
  const data = await r.json().catch(() => ({}));
  return Object.assign(new Error(data.message || `HTTP ${r.status}`), { status: r.status, code: data.error });
}

/** Sends one recording to Sarvam. Resolves { text, engine, audio_url }; rejects with { status, code }. */
export async function transcribe(blob, language = "hi-IN") {
  const type = (blob.type || "").split(";")[0];
  const form = new FormData();
  form.append("file", blob, `speech.${EXT[type] || "webm"}`);
  form.append("language", language);
  const r = await fetch("/api/stt", { method: "POST", body: form });
  if (!r.ok) throw await failure(r);
  return r.json();
}

/**
 * Speaks text with Sarvam's voice. Resolves once playback has started; rejects when the voice
 * could not be fetched or played (the caller falls back to the browser voice). Aborting `signal`
 * cancels the fetch or stops the playback; it rejects with an AbortError.
 */
export async function speakSarvam(text, language = "hi-IN", signal = undefined) {
  const r = await fetch("/api/tts", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text, language }),
    signal,
  });
  if (!r.ok) throw await failure(r);
  const wav = await r.blob();
  signal?.throwIfAborted();
  const url = URL.createObjectURL(wav);
  const audio = new Audio(url);
  const release = () => URL.revokeObjectURL(url);
  audio.addEventListener("ended", release, { once: true });
  signal?.addEventListener("abort", () => { audio.pause(); release(); }, { once: true });
  try {
    await audio.play();
  } catch (err) {
    release();
    throw err;
  }
}
