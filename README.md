# Bolo Line

**Say it once. It is logged.**

Bolo Line is a voice logbook for small factory floors. A line operator holds one button and says a batch record in Hindi or Hinglish: "Batch chaudah, oven do, ek sau assi degree, teen reject". The app reads it back, the operator says "haan", and the row appears on the owner's English dashboard. A value outside its limit is saved and flagged in the same shift.

Built for the Scaler x Wispr Flow hackathon "India Runs on Voice", Round 2. Theme: Livelihoods and small business.

- Live link: https://bolo-line.onrender.com/demo
- Demo video: [YouTube link to add]
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

## Start it

You need Docker. You do not need a key, an account or a `.env` file.

```bash
git clone https://github.com/vj-io/bolo-line
cd bolo-line
docker compose up --build
```

Then open **http://localhost:8000/demo**. It shows the operator's phone on the left and the owner's dashboard on the right. On a screen narrower than 900 px, open the two screens separately:

| Address | Screen |
|---|---|
| http://localhost:8000/ | The operator's phone |
| http://localhost:8000/dashboard | The owner's dashboard |
| http://localhost:8000/audit | The day's production record, ready to print |

If `docker compose up` stops with `ports are not available` and `bind: address already in use`, another program is using port 8000. Stop that program, or change the left number of `"8000:8000"` in `docker-compose.yml` (for example to `"8001:8000"`) and open that port instead.

To start again with the five starting rows: `docker compose down -v`, then `docker compose up`.

## Try it in one minute, with no Hindi and no microphone

1. On the operator's phone, scroll down to the sample buttons under **No Hindi? No mic? Try a sample**. In `/demo` they are already open; on the phone's own page at a narrow width, click that line to open them.
2. Click **Normal batch**. The clip plays, four values fill in (batch 14, Oven 2, 180 °C, 3 rejects) and the app asks "Sahi hai?" ("Is that right?").
3. Click **Haan** (yes). The row lands on the dashboard.
4. Click **Temperature too high**, then **Haan**. This row lands marked "Temp out of limit": a real fault is saved and flagged, never refused.
5. Click **Forgot the temperature**. The app asks only for what is missing. Click **Answer: ek sau pachattar**, then **Haan**.
6. Or type in **Type instead**: `batch 21, oven 1, 180 degree, 2 reject`, press **Send**, then click **Haan**. English words and digits work.
7. On the dashboard, look at **Today's shift**, then open **Production record to print**.

The sample clips are a computer voice with prepared transcripts; each button says "Sample clip (computer voice)". Everything after the transcript (parsing, read-back, confirmation, saving, the dashboard) runs live.

## Speak to it

Hold the yellow button ("Daba ke bolo"), say the sentence, release. Then say "haan" to save or "nahi" to throw the row away.

| Say | What happens |
|---|---|
| "Batch chaudah, oven do, ek sau assi degree, teen reject" | Batch 14, Oven 2, 180 °C, 3 rejects |
| "Batch pandrah, oven ek, do sau das degree, do reject" | Saved and flagged: 210 °C is outside 170 to 190 |
| "Batch solah, oven do, chaar reject" | It asks "Temperature kitna tha?"; answer "ek sau pachattar" |
| "batch seventeen, oven two, one eighty five degree, saat reject" | Mixed Hindi and English works; 7 rejects is flagged |
| "nahi" at the read-back | Nothing is saved; say the record again |

The microphone needs a page served over `https` or from `localhost`, and your permission.

## What needs a key, and what does not

| Feature | With no key (the default) | With `SARVAM_API_KEY` set |
|---|---|---|
| Starting the app, samples, typed text, parsing, saving, dashboard, export | Works | Works |
| Live microphone | The browser's own speech recognition in Hindi, built for Chrome and Edge; the browser sends the audio to its vendor. In a browser without it, the microphone note says "Use a sample or type below" and the samples open. | Sarvam speech-to-text, in any browser that can record. Selected by default; a switch on the operator screen goes back to the browser engine. If Sarvam fails or has not answered in 12 seconds, the screen says "Sarvam is not available right now. Using the browser's speech." and switches to the browser engine. |
| Spoken read-back | The browser's Hindi voice, if the device has one. Otherwise the read-back is shown on screen only. | Sarvam's Hindi voice. If it fails or has not started in 5 seconds, the browser's voice speaks. |
| The engine badge | "Speech engine: Browser (no key needed)" and "Sarvam: key not set" | A "Speech engine" switch: Browser or Sarvam |

To use Sarvam, put the key in a file named `.env` next to `docker-compose.yml`, then run `docker compose up` again:

```bash
SARVAM_API_KEY=your-key
```

Nothing else changes. The key stays on the server; the browser never sees it.

**Daily limits (optional).** Two more settings cap what Sarvam can spend in one India-time day: `SARVAM_DAILY_STT_CALLS` (speech-to-text calls) and `SARVAM_DAILY_TTS_CHARS` (characters sent to the voice; a phrase served from the voice cache costs nothing). Use plain digits. Unset means no limit; `0` turns that half of Sarvam off. Over a limit the server answers `503 budget_reached` without calling Sarvam, and the operator screen falls back to the browser as above. The counts are kept in memory, so a restart sets them back to zero.

## The live link

https://bolo-line.onrender.com/demo runs the same code with a Sarvam key set.

- **It is on free hosting.** After 15 minutes with no visitors it sleeps, and the next visit waits about a minute on the host's loading page. Please wait; it does start. Until 3 Dec 2026, a scheduled request keeps it awake from 07:30 to 00:30 IST, so a daytime visit should rarely meet that page.
- **The data is shared and temporary.** Everyone who opens the link writes to the same log. A restart brings back the five starting rows. The service sleeps at night, so each day starts with the five starting rows.
- **If Sarvam stops answering** (an outage, used-up credit or a daily limit), the operator screen says so and switches to the browser's speech.
- **Recordings.** A sentence spoken through the Sarvam engine is recorded and stored on the server until the next reset, and its row keeps a link to the recording. Do not say anything private.

## What is in this build

- **One spoken sentence, four fields.** Batch number, machine, temperature, rejects.
- **Read-back and an explicit yes.** Nothing is saved without "haan". Two unclear answers discard the row.
- **Follow-up questions.** A missing value is asked for by itself. An unknown machine gets the closest match offered ("Oven 2 bola?").
- **Impossible against out-of-limit.** A temperature outside 0 to 400 °C or more than 1000 rejects is treated as misheard and asked again. A value that is possible but outside the station's limits (170 to 190 °C, at most 5 rejects) is saved and flagged for the owner.
- **Owner's dashboard.** New rows appear within about 2 seconds, with out-of-limit values marked.
- **Heard right first time.** The dashboard counts how many attempts were saved from one sentence and one "haan", in total and per speech engine. The count is shown beside the percentage.
- **Today's shift.** Batches logged, time of the last log, the out-of-limit list, rejects per oven.
- **Record export.** Today's rows as a CSV file, and a printable production record with lines for a supervisor's signature. This is a record export, not a compliance tool.
- **Falls back by itself.** When Sarvam fails, is slow or hits its daily limit, speech goes to the browser and the voice to the browser's voice, and the operator keeps the screen.

## Languages

Hindi and Hinglish are ready: Hindi number words in Latin or Devanagari script, English number words and digits, in any mix. Marathi is in **beta**: choose it with the language buttons at the top of the operator screen. Its words were written without a native speaker and have not been checked against real recordings; with Sarvam, its read-back uses the model's default voice. A language is a data pack in `server/lang/`; number words for 0 to 999 are generated from the Unicode CLDR 49 spell-out rules. Gujarati and Tamil are next; see the [roadmap](docs/ROADMAP.md).

## How it works

```
operator's browser                      server (FastAPI)                     owner's browser
hold and speak ──audio──▶ /api/stt ──▶ Sarvam (only with a key)
        or browser speech ──text──┐
                                  ▼
                          /api/parse    rule-based parser, fixed station vocabulary
                          /api/confirm  "haan" / "nahi" / unclear
                          /api/rows     SQLite ──────────────────────────▶ /dashboard (asks every 2 s)
read-back ◀── /api/tts (Sarvam voice) or the browser's voice             /api/stats, /api/rows.csv, /audit
```

- **Understanding is ours.** The parser is plain rules over a fixed station vocabulary (`server/parser/`). There is no language model and no cost per request. Speech-to-text is the only rented part, and it can be swapped.
- **One station.** "Oven Line" with Oven 1 and Oven 2, its limits and its words are in `server/stations.json`.
- **Storage.** SQLite in a Docker volume. Postgres when `DATABASE_URL` is set.
- **No build step.** The three screens are plain HTML, CSS and JavaScript modules in `web/`.
- The API is listed at `/docs` on a running server.

## Develop and test

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DATA_DIR=./.data .venv/bin/uvicorn server.main:app --port 8000 --reload
.venv/bin/python -m pytest -q
```

The tests need no key and no network: the Sarvam routes are tested against a stand-in shaped like Sarvam's documented replies. The tests that need Postgres are skipped unless `BOLO_TEST_PG_URL` holds a Postgres address.

## What is not proven yet

- Accuracy on a real factory floor. The first-try figure exists so a pilot can measure it.
- Sarvam on real voices. [docs/measurements.md](docs/measurements.md) records all four values right for 5 of 5 sample clips and for 10 of 10 repeats, with replies in 0.66 to 1.51 s. The clips are a computer voice and are the same clips the settings were chosen on, so that is a settings check, not accuracy for real speech.
- Noise, accents and more than one station.

## Credits

- Speech-to-text and voice: Sarvam (optional, with your own key).
- Fonts: Kalam (Indian Type Foundry) and Patrick Hand (Patrick Wagesreiter), SIL Open Font License 1.1, in `web/shared/fonts/`.
- rough.js 4.6.6 (MIT), vendored in `web/vendor/`.
- Number words: Unicode CLDR 49 spell-out rules, in `tools/cldr/release-49/`.
- Look: the "sketchnote" style from the Lemo-Opuscar style library, translated into a UI theme.
- Built during the hackathon with an AI coding assistant; the commit history records it.
