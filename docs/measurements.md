# Sarvam speech-to-text: what was measured

To re-run, from a clone of this repository (needs your own Sarvam key; at most 20 paid calls, about Rs 0.44 for the default run):

```bash
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
read -rs SARVAM_API_KEY && export SARVAM_API_KEY   # paste the key; it stays out of the shell history
DATA_DIR=./.data .venv/bin/uvicorn server.main:app --port 8000
```

Then, in a second terminal in the same folder:

```bash
.venv/bin/python tools/measure_sarvam.py --base http://127.0.0.1:8000
```

The script refuses a second run on the same commit unless given `--again`, refuses any server that is not on this machine, and sends at most 20 `/api/stt` calls. `.venv/bin/python tools/measure_sarvam.py --self-test` checks its scoring and guards offline, with no key and no network.

## In one paragraph

On 27 Nov 2026 we sent the app's five sample clips through Sarvam speech-to-text (`saaras:v4`, mode `transcribe`, with the station's words as key terms) by way of a local server, then sent one clip 10 more times. All 15 calls answered; none failed. All four values were right for 5 of 5 clips (4 of 4 rows, since one row takes two clips), and for 10 of 10 repeats. Replies took 0.66 to 1.51 seconds over 14 calls (median 0.84 s); the first call after the server started took 1.08 s. The clips are a computer voice, and the same five clips were used to choose the mode and the key terms, so this is a settings check, not an accuracy figure for real speech.

## The run

| | |
|---|---|
| Date | 27 Nov 2026, 22:01 IST |
| Commit | `ba6b50ad5364b03fd75164e4c0ee626e9370c03a` (the script's commit; `server/` and `web/` are identical to `49401d9467ae06e904866f9b97c708cc4bf497cb`, checked with `git diff`) |
| Server | local, `http://127.0.0.1:8111`, started 22:00:49 IST, about 12 s before the first call; empty data folder |
| Model and mode | `saaras:v4`, `transcribe`, language `hi-IN` (read by the script from `server/stt_sarvam.py`) |
| Key terms | on: batch, reject, degree, oven, Oven 1, Oven 2 |
| Clips | 5 (`web/samples/s1, s2, s3, s3b, s4.m4a`), 1.1 to 4.4 s long |
| Calls | 15 `/api/stt` calls: 5 clips once, then s1 ten more times. 15 POST lines in the server log and 15 stored clips agree with the script's count |
| Errors and exclusions | 0. A call that fails for a reason that is not the model's (no key, no credit, rate limit, network) would be listed as an error, would stop the run, and would not count as a wrong answer |
| Spend | 54.4 s of audio; about Rs 0.44 at Rs 0.49 a minute before GST, if billed per second with no minimum (not checked against the account) |

How a clip is judged: the transcript goes to `/api/parse` exactly as the operator screen sends it (s3 leaves out the temperature, the parser asks for it, and s3b is sent as the answer). A row is right when all four values (batch, machine, temperature, rejects) equal the ones the specification gives for that sample (PRD section 3.5: 14, Oven 2, 180, 3; 15, Oven 1, 210, 2; 16, Oven 2, 175, 4; 17, Oven 2, 185, 7). s3 is right when its three values are right and the temperature is still empty. As a control, the parser alone was run on each sample's reference sentence from `server/samples.json` (no Sarvam call): 4 of 4 rows right, so a wrong row would have been the speech-to-text's.

| Call | Clip | Said (reference) | Heard (Sarvam) | Clip right | Row saved as | Reply (s) |
|---|---|---|---|---|---|---|
| 1 | s1 | Batch chaudah, oven do, ek sau assi degree, teen reject | बैच 14 ओवन 2, 180 डिग्री, 3 रिजेक्ट। | yes | 14, Oven 2, 180, 3 | 1.08 |
| 2 | s2 | Batch pandrah, oven ek, do sau das degree, do reject | बैच 15 ओवन 1, 210 डिग्री, 2 रिजेक्ट। | yes | 15, Oven 1, 210, 2 | 0.84 |
| 3 | s3 | Batch solah, oven do, chaar reject | बैच 16, ओवन 2, 4 रिजेक्ट। | yes | asks for the temperature | 1.04 |
| 4 | s3b | ek sau pachattar | 175। | yes | 16, Oven 2, 175, 4 | 0.66 |
| 5 | s4 | batch seventeen, oven two, one eighty five degree, saat reject | बैच 17 ओवन 2, 185 डिग्री, 7 रिजेक्ट। | yes | 17, Oven 2, 185, 7 | 0.74 |
| 6 to 15 | s1, ten times | | the same transcript as call 1, all ten times | yes, 10 of 10 | 14, Oven 2, 180, 3 | 0.76, 1.51, 1.04, 0.83, 0.89, 0.86, 0.85, 0.75, 0.98, 0.74 |

Reply times are measured by the script, so each one includes the upload to the local server, the server's call to Sarvam over a new HTTPS connection, and the server saving the clip. Sarvam's own share is somewhat less.

- First call after the server start: 1.08 s (one call).
- The other 14 calls: min 0.66 s, median 0.84 s, max 1.51 s.

## How this compares with the earlier figures

The deck's earlier figures came from a commit message (`2b04b1d`: 5 of 5 with key terms) and a hand-over note (0.6 to 1.7 s; one first call of 15.9 s). This run agrees on 5 of 5 and on the range. It did not see a slow first call: the one first call here took 1.08 s, and the earlier 15.9 s was also a single call, so neither says how often a slow first call happens.

## What these clips are

The five clips are the placeholders the first commit shipped: made with the macOS Hindi computer voice (`say -v Lekha`, then converted to AAC; PRD section 3.5). `git log -- web/samples` shows one commit, `bbb0cf0`, so nobody has replaced them. They are the same clips the mode and the key terms were chosen on (`2b04b1d`). The app's screens call them "Recorded sample" (task T9 relabels them). The repeats on s1 send identical audio, so they show that the answer is stable, not that it is right more often.

## What was not measured

- A human voice. No real person's speech, no accent (including Bhojpuri-accented Hindi), no fast or mumbled speech.
- Noise. No factory floor, no machine noise, no phone microphone at arm's length; the clips are clean computer audio.
- Sentences other than the five samples, and any sentence longer than 4.4 s.
- Settings other than the shipped ones. Without key terms the earlier run had 3 of 5 (`2b04b1d`); that was not repeated here.
- Marathi, or any language but Hindi.
- The live link. Every call went through a local server on one machine on one evening; Render's own network, cold starts and Sarvam's load at other times were not measured.
- The browser's own speech recognition (the engine used without a key).
