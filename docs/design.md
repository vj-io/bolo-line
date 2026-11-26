# Design contract: Sketchnote as the product UI

The user asked for the opuscar `sketchnote` style (brag-styles library) as the product's look. That style is written for a film; this file is its translation into a web app UI. Every build session uses these tokens and rules; nobody invents colours, fonts or radii.

Source: `~/.claude/plugins/cache/brag-scaled/brag-scaled/0.9.1-plus/skills/brag-styles/opuscar/styles/sketchnote/STYLE.md` (read it for the feel; the film rules about frames, 24 fps, camera moves, subtitles and sound do not apply to the app).

## What carries over
- **The screen is a page of visual notes**: warm white paper with a faint dot grid, black fineliner lines, grey marker for volume and shadow, and one yellow marker for the single thing that matters.
- **Hand lettering is the typography**: a bold casual hand for titles, banners, buttons and key values; a thin upright hand for notes and body text.
- **The signature move, "the page writes itself"**, becomes interaction feedback: when something new arrives (a transcript, a parsed record, a confirmation), its box outline draws on, then the marker fill, then the words. Order inside one element: outline, paper fill, marker, shadow, label.
- **One yellow thread**: yellow marks the user's voice and what it produced (the mic button, the live transcript highlight, the value just captured), plus banners and fat arrows. Everything else is black and grey.

## Tokens (CSS custom properties; contrast measured on paper #FBFAF6)
| Token | Value | Use | Text contrast |
|---|---|---|---|
| `--paper` | `#FBFAF6` | page background | |
| `--dot` | `#D6D2C8` | dot grid only (26 px pitch, 1.3 px dots) | decorative |
| `--ink` | `#1E1E22` | lines, titles, body text | 15.9:1 |
| `--notes` | `#5B5852` | secondary notes, captions, placeholders | 6.8:1 (5.1:1 on yellow) |
| `--marker-1` | `#E3E2E0` | grey marker light: card fill, volume | ink 12.8:1, notes 5.5:1 |
| `--marker-2` | `#CBCACB` | grey marker middle: drop shadows, banner tails | not for text backgrounds |
| `--marker-3` | `#A1A1A4` | grey marker dark: folds, small dark parts | never text (2.5:1) |
| `--yellow` | `#FED651` | the one accent: mic, highlight swash, banners, fat arrows | ink on yellow 11.8:1 |
| `--yellow-deep` | `#F5AA00` | strokes only (loops, sparks) | never text (1.9:1) |
| `--amber-ink` | `#8A5A00` | warning text ("check this value") | 5.7:1 |
| `--red-pen` | `#C8331F` | error strokes, crossed-out misheard words | 5.1:1 |
| `--red-pen-ink` | `#B3261A` | error text | 6.3:1 |
| `--green-tick` | `#2E7D32` | the saved tick and "saved" word only | 4.9:1 |

| `--red-tint` | `#FBE4DF` | background tint of a flagged dashboard row (temperature fault) | red-pen-ink 5.4:1, ink 13.7:1 |
| `--amber-tint` | `#FCEFC9` | background tint of a flagged dashboard row (rejects high) | amber-ink 5.2:1, ink 14.5:1 |

Semantic extension (the film has no states; a UI needs them): red correction pen = error or misheard, amber ink = needs checking, green tick = saved. Each colour is always paired with a word or icon, never colour alone. Keep yellow off error and success states.

**Status colours sit on paper or their own tint only.** Measured on the grey card fill `--marker-1`, green-tick is 3.96:1 (fails) and amber-ink 4.58:1 (marginal), so status words, ticks and flags never sit on `--marker-1`.

Marker fills are translucent in the film; in the UI use the solid tokens above (they are the film's marker colours composited on paper), so text contrast stays measurable.

## Type
- Titles, banners, buttons, key values: **Kalam Bold** (Indian Type Foundry, OFL). Kalam also covers Devanagari, so Hindi text renders in the same hand.
- Notes and body: **Patrick Hand** (OFL), Latin only; Devanagari body text falls back to Kalam Regular.
- Self-host the fonts (Fontsource packages or files in the repo). No Google Fonts link at runtime: the judges start the app from `docker compose up` and it must not depend on a CDN.
- Body text at least 18 px; at most four sizes on a screen. Letters may get a fixed small tilt per element (seeded, never random per render), but never digits: numbers are read at a glance.
- The four operator values (batch, machine, temperature, rejects) are Kalam Bold at 56 px or more (`--fs-hero`). Where a value does not fit a 375 px box at that size (the machine), show its number large and its type ("Oven") as the label; never shrink a value below 56 px and never scroll sideways.
- If the PRD needs another Indian script (Tamil, Bengali and so on), pick a hand-style OFL face that covers it and record the choice in the PRD.

## Shapes and components
- **Lines** are hand-drawn: wobbly fineliner borders (rough.js, or an SVG path with a small seeded jitter), closed shapes overshooting their start a little. One stroke weight family: 2 px main, 1.2 px secondary. Wobble is for borders and marks only: the dashboard's table rules are plain, light (`--marker-2`, 1 px) and straight, so rows scan.
- **Cards** are rounded boxes (radius 14 px) with a paper fill, a fineliner border, and a grey-marker drop shadow offset down-right by 8 to 10 px. Shadows always fall down-right.
- **Banners** (section titles) are ribbons with a yellow marker fill and grey tails; a number on a banner gets a yellow swash.
- **Fat arrows** with a yellow fill link steps in a flow.
- **The mic button** is the largest element on the voice screen: a yellow marker disc with a fineliner outline and a hand-drawn mic icon; while listening, a pen scribble ring boils around it.
- **Captured values** sit in boxes; the value just captured gets a yellow swash under it; a confirmed value gets a yellow loop drawn around it and a green tick.
- **Misheard input** is crossed out in red pen with the correction written next to it, never silently replaced.
- Icons are drawn in the same fineliner style (simple outline icons with a grey marker volume), not an icon font.

## Motion
- Resting CSS is always the final drawn state; all keyframes live inside `@media (prefers-reduced-motion: no-preference)`, so reduced motion needs no overrides and nothing can stay invisible.
- Draw-on uses `stroke-dasharray`/`stroke-dashoffset` with `pathLength="1"` on paths drawn at their measured pixel size. Never combine `pathLength` dash animation with `vector-effect: non-scaling-stroke` (it renders with gaps in Chromium).
- Speed is a pen's speed: an outline in 0.25 to 0.5 s, words written left to right in about 0.3 s per word, never a fade or slide-in for content. Nothing bounces or slides once drawn.
- The only continuous motion is the listening scribble ring and a slight line boil (at most every 2 frames, 1 to 2 px).

## Accessibility and layout
- Works at 375 px wide first (phone in a factory, a clinic, a field), then scales up to a laptop for the demo video.
- Visible focus ring: a yellow marker loop around the focused control plus a 2 px ink outline.
- Every voice action also has a visible text fallback (a tap target and an editable field) so the app is testable without a microphone.
- Text contrast at least 4.5:1, using the pairs in the token table only.

## Tailwind (if the stack uses Tailwind v4)
Reset the default namespaces in `@theme` (`--color-*: initial; --radius-*: initial; --shadow-*: initial;`) and define only the tokens above, so a stray `bg-blue-500` or `rounded-lg` renders nothing and parallel sessions cannot drift.

## Who owns this
The integrating session owns the token file (for example `app/styles/tokens.css`) and lands it before any UI session starts. UI sessions consume the tokens by name and never write hex literals; at hand-back, grep the diff for `#[0-9a-fA-F]{6}` and arbitrary Tailwind values outside the token file.
