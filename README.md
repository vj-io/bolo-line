# Bolo Line

A voice logbook for small factory floors. A line operator holds one button and says a batch record in Hindi or Hinglish ("Batch chaudah, oven do, ek sau assi degree, teen reject"). The app reads it back, the operator says "haan", and the row appears on the owner's English dashboard, with out-of-limit values flagged in the same shift.

Built for the Scaler x Wispr Flow "India Runs on Voice" hackathon, Round 2 (theme: Livelihoods and small business).

## Start it

You need Docker. No keys and no `.env` file are needed.

```bash
docker compose up --build
```

Then open:

- http://localhost:8000/ : the operator screen (Chrome or Edge for the live microphone)
- http://localhost:8000/dashboard : the owner's dashboard
- http://localhost:8000/demo : both side by side

No Hindi or no microphone? The operator screen has recorded sample buttons and a "Type instead" field. Sample transcripts were prepared in advance; parsing, read-back, confirmation, saving and the dashboard are live for every source.

## What needs what

| Feature | Needs |
|---|---|
| Sample clips, typed text, parsing, read-back text, saving, dashboard | Nothing. Works offline once the page has loaded. |
| Live microphone (browser speech, `hi-IN`) | Chrome or Edge, microphone permission, internet (the browser sends audio to its vendor) |
| Spoken Hindi read-back | A Hindi voice installed in the browser; otherwise the read-back is shown on screen only |
| Optional Sarvam speech-to-text | `SARVAM_API_KEY` in the environment; without it the app shows "key not set" |

## Develop without Docker

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DATA_DIR=./.data .venv/bin/uvicorn server.main:app --port 8000 --reload
.venv/bin/python -m pytest -q
```

## Credits

- Fonts: Kalam (Indian Type Foundry) and Patrick Hand (Patrick Wagesreiter), SIL Open Font License 1.1, in `web/shared/fonts/`.
- rough.js 4.6.6 (MIT), vendored in `web/vendor/`.
- Look: the "sketchnote" style from the Lemo-Opuscar style library, translated into a UI theme.
