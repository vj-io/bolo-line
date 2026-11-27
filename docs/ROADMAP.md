# Bolo Line roadmap

Bolo Line is a voice logbook for small factory floors. An operator holds a button and speaks a batch record; the app reads it back; the operator says yes; the row appears on the owner's dashboard with out-of-limit values marked.

This page lists what is built, what we plan to build next, how hard each item is, and how each one can fail. Written 27 Nov 2026. Costs are for one factory with two lines and about 200 logs a day, before GST. "Days" means working days for one developer.

## Now: languages and a better speech engine

| Item | Status |
|---|---|
| Hindi and Hinglish, with a rule-based parser, read-back and confirmation | Live |
| Sarvam speech-to-text and Sarvam voice (needs a key; the app runs without one, and the live link has one) | Live |
| Marathi | Beta: on the live link; its words have not yet been checked by a native speaker |
| Gujarati and Tamil | Next |
| Telugu, Kannada and Bengali | After that |

**Why these languages.** Tamil Nadu, Gujarat and Maharashtra have the most workers in registered factories: 16.0%, 12.8% and 11.9% of India's total in 2023-24 (Annual Survey of Industries, as published in the RBI Handbook of Statistics on Indian States, Table 122). Hindi stays the default, because many operators in those states come from Hindi-speaking states.

**How a language is added.** Each language is a data pack in `server/lang/`: keywords, number words, yes and no words, prompts and sample sentences. Number words for 0 to 999 are generated from the Unicode CLDR 49 spell-out rules, then extended with spoken forms that a native speaker confirms. The Sarvam voice is chosen per language in the server; a language without one gets the model's default voice.

**How the language is chosen.** The operator taps their language on the screen and the device remembers it. The app does not guess the language from the audio. The same sound can be a different number in two languages: "sattar" is 17 in Gujarati and 70 in Hindi. If the words arrive in a different script from the selected language, the app asks the operator to check the language instead of saving a guess.

**When a language counts as ready.** It passes a test table of at least ten utterances (number words, digits, mixed English, a missing field, an impossible number), a native speaker has checked the prompts, and real recordings have passed through each speech engine we offer. Until then the language is marked "beta".

## Built: three small features with no new dependency

| Feature | What the user gets | Cost a month | How it can fail, and the answer |
|---|---|---|---|
| First-try accuracy figure | The share of logs saved from one sentence and one "haan", with the count beside it. The dashboard shows it in total and by speech engine; `/api/stats` also gives it by language | Rs 0 | Misleading on small counts: the count is shown beside the figure |
| Record export | A CSV download and a print view of the day's log, for the factory's production and quality records | Rs 0 | Wrong time zone or missing rows: tested against a known set of rows, cell by cell |
| End-of-shift summary | One card: batches logged, out-of-limit values, rejects per machine, time of the last log | Rs 0 | Wrong day boundary: a day is the India-time calendar day, tested on both sides of midnight IST |

These came first because they work with no key, no outside account and no new package, and each one can be tested completely.

Also built: a daily limit on Sarvam spend, set by two environment variables, and an automatic switch to the browser's speech when Sarvam fails, is slow or reaches its limit.

## Later

| Feature | What the user gets | Effort | Depends on | Cost a month | Main risk | When |
|---|---|---|---|---|---|---|
| Push-to-talk tuned for noise | Fewer misheard logs on a loud floor | 0.5 day of software, then tuning on site | A real line to record on; a close-talking headset microphone per station | A few hundred rupees per headset, once | Cannot be judged at a quiet desk | Finale |
| Station set-up form | A new line or new limits without editing a file | 1.5 days | None | Rs 0 | A wrong limit hides real faults: limits are shown on the operator screen and changes are logged | Finale |
| Several stations and operators | More than one line and more than one shift | 2 days | None | Rs 0 | A row logged to the wrong station: the station name is on screen and in the read-back | Finale |
| Trend chart per machine | The owner sees a machine drifting before it leaves its limits | 1.5 days | About 20 to 25 logs per machine before limits mean anything | Rs 0 | False alarms: start with a chart, add alert rules only after real data | Finale |
| WhatsApp alert on a fault | The owner hears about an out-of-limit value within a minute | 1.5 days, plus account approval | A verified business account, an approved message template, a key | About Rs 20 at 5 alerts a day (rate to be confirmed on the provider's rate card) | A failed send goes unnoticed: every send and its delivery status is logged, and a failed alert never blocks a save | Finale as a sandbox demo; real use after |
| SMS alert | Reaches an owner with no data connection | 1 day, plus registration | Sender and template registration required in India | About Rs 0.25 a message | Template rejection | Later |
| Offline speech engine | Logging with no internet | 3 to 5 days | An open model per language; a larger server | Rs 0 to run, more for hosting | Accuracy on numbers and English loan words is unknown until tested on real recordings | Later |
| Android app with a hardware button | A gloved operator presses a physical button | 3 to 4 days | A thin app wrapper; a Bluetooth or wired button | A one-time store fee | A missed press: the on-screen button always stays | Later |
| Photo of a defect | The owner sees what the rejects looked like | 1.5 days | Storage | Small | It is not hands-free: optional, never part of the voice flow | Later |
| Accounting or ERP link | Batches reach the stock system without retyping | 4 days or more per system | A machine at the factory running that system | Rs 0 | Every set-up differs: failed posts are queued; record export covers most needs first | Later |

## Not planned

**Recognising the operator by voice, or a spoken PIN.** Published accuracy figures for speaker recognition come from clean recordings. Short clips in factory noise will be much less reliable, and a spoken PIN can be overheard. A wrong name on a quality record is worse than no name. A name button per shift does the job.

## Running cost of speech

For 200 logs a day over 30 days, that is 6,000 logs a month.

| Path | Cost a month |
|---|---|
| Browser speech and browser voice | Rs 0 |
| Sarvam speech-to-text (Rs 0.49 a minute, billed per second; a recording stops at 15 seconds, so a log costs at most about Rs 0.1225) | At most about Rs 735 |
| Sarvam voice for the read-back (Rs 2 per 1,000 characters; the Hindi read-back of a full log is about 45 characters, so about Rs 0.09) | About Rs 540 |

Prices are from Sarvam's public pricing page on 27 Nov 2026. A phrase the server has already voiced is served from its cache and costs nothing. The two daily limits in the [README](../README.md#what-needs-a-key-and-what-does-not) cap what one day can spend.

## What we have not proven yet

- Accuracy on a real factory floor in each language.
- Sarvam on real voices. [measurements.md](measurements.md) records a settings check on the five sample clips, which are a computer voice.
- How each speech engine writes spoken numbers in Marathi, Gujarati and Tamil. We accept both digits and number words and test with real recordings.
- Whether record exports meet a regulator's format. We call the feature "record export", not a compliance tool.
