# Achilles UI — token contract

Everything below is defined in `app/globals.css` (light under `:root`, dark
under `@media (prefers-color-scheme: dark)`). Components are CSS Modules that
consume these tokens. **There is no Tailwind in this project** — any reference
snippet with utility class names must be translated into module rules.

The metaphor: a marked-up paper back from your editor. Paper and ink. A resume
is black and white, so the UI is near-monochrome — the screen is honest about
what the exported PDF looks like. Colour is only ever a proof mark.

## Colour

| Token | Light | Dark | Use it for |
|---|---|---|---|
| `--paper` | `#FBFAF7` | `#12110E` | Page background. The default ground. |
| `--paper-2` | `#F4F2ED` | `#1A1815` | Inset / well — something pressed *into* the page (scroll areas, code wells, table header bands). |
| `--surface` | `#FFFFFF` | `#191713` | Raised card — something laid *on* the page. The only place pure white is allowed. |
| `--ink` | `#14130F` | `#ECE8DF` | Primary text, headings, the focus ring. |
| `--ink-2` | `#4B4840` | `#B2AC9E` | Secondary text — supporting prose, field labels. |
| `--ink-3` | `#6E6A60` | `#8B8679` | Muted / meta — counts, dates, hints. Weakest ink allowed; `--paper-2` is the darkest ground it may sit on, and it clears AA there (4.82:1 light / 4.88:1 dark). |
| `--rule` | `#E3DFD5` | `#2C2A25` | Default hairline: card edges, table row lines, dividers. |
| `--rule-strong` | `#C8C2B4` | `#413E36` | Emphasised border: header underline, active edge, pressable control, scrollbar thumb. **Borders only** — as type it measures under 2:1 in both themes. |
| `--del` | `#9E2F26` | `#D4796A` | Deletion mark — the struck text and its `−` glyph. |
| `--del-wash` | `#F7EDEB` | `#241A18` | Deletion row/block tint, *behind* text. |
| `--del-wash-2` | `#EBD4D1` | `#3B2623` | One step deeper: the words inside a struck row that actually moved. |
| `--ins` | `#2C6349` | `#77A98C` | Insertion mark — the added text and its `+` glyph. |
| `--ins-wash` | `#EBF2ED` | `#17201A` | Insertion row/block tint. |
| `--ins-wash-2` | `#D2DFD8` | `#233229` | One step deeper, as `--del-wash-2`. |
| `--flag` | `#7F611C` | `#C6A45C` | Needs-review mark — a flagged query, a failing gate. |
| `--flag-wash` | `#F7F1E3` | `#231E14` | Needs-review tint. |
| `--hover` | `#F4F2ED` | `#201E1A` | Row / control hover. A paper tint, never a hue. The **only** hover ground; never `--surface`, which is pure white in light and punches a hole in a tinted row. |
| `--scrim` | `rgba(20,19,15,.24)` | `rgba(0,0,0,.66)` | The wash a modal lays over the page. Per-theme by necessity — see below. |

Why the marks are ink + **wash** pairs and not coloured borders: a mark has to
cover a whole diff row and stay readable under body text. A coloured border
fights the hairline grid that carries the layout and reads as UI chrome — a
brand accent — which this system forbids. A wash sits behind the text like a
highlighter pass and leaves the grid intact. The one exception is a **change
bar**: a 1px `--flag` edge beside a quoted offending line, which is an
editorial mark rather than chrome. Hairline weight, never 2px.

**`--del` and `--flag` are not interchangeable.** `--del` means an operation was
struck — the pipeline broke, the service is offline, a value was rejected.
`--flag` means the *document* needs a human look — a gate did not pass, a
required term is missing, the resume is not ready. So "step failed" is `--del`
while "gate fail" is `--flag`, and that is the correct reading rather than an
inconsistency. `--ins` is the third: something we would add ourselves.

**Never mix a scrim off `--ink`.** `--ink` inverts between themes, so an
ink-derived scrim dims the page in light and *brightens* it in dark — a pale
veil over the whole viewport, which is the glassmorphism rule 3 forbids. Any
derived colour belongs in `globals.css` as a per-theme token, which is also why
no module calls `color-mix()`.

## Shape, elevation, motion

| Token | Value | Use it for |
|---|---|---|
| `--r-card` | `4px` | Cards, panels, wells. Paper has a cut edge, not a moulded one. |
| `--r-ctl` | `3px` | Buttons, inputs, small controls. |
| `--r-mark` | `1px` | Objects 3-5px across: a meter bar, a pixel-grid cell, a highlighted run of words. `--r-ctl` on a 4px bar is a circle. Nothing smaller exists — do not write a literal. |
| `--r-pill` | `999px` | Genuine pills only — status chip, keyword tag. |
| `--shadow-card` | `0 1px 2px rgba(20,19,15,.05), 0 0 0 1px var(--rule)` | The **only** shadow. Contact shade plus a hairline ring. Dark theme swaps the shade to black alpha so it never reads as a glow. |
| `--ease` | `cubic-bezier(0.23, 1, 0.32, 1)` | Every transition and animation. |
| `--dur-1` | `120ms` | State flip: hover, press, checkbox. |
| `--dur-2` | `180ms` | Element enter/exit: row, chip, tooltip. |
| `--dur-3` | `300ms` | Layout change: panel open, list reflow. The ceiling for a state change. |
| `--dur-spin` | `900ms` | Ambient: one turn of a spinner. |
| `--dur-loop` | `1600ms` | Ambient: one breath of `shimmer-text`. |

Ambient loops are the only thing allowed past the 300ms ceiling — a loop is not
a state change, and at 300ms it flickers. There are exactly two ambient values,
so every spinner in the app turns at one speed and every shimmer breathes at one
period. `LoadingState` is the single documented exception: its label pulses at
`calc(var(--cycle) * 2)`, twice its own grid cycle, which is what makes the
cells and the label read as one mechanism rather than two.

## Type

| Token | Stack | Use it for |
|---|---|---|
| `--font-mono` | `"JetBrains Mono Variable", ui-monospace, SFMono-Regular, monospace` | Figures, scores, keywords, file names, dates, anything tabular. The default on `<body>`. |
| `--font-serif` | `"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif` | Section headings and running prose. This is what creates the manuscript feel. |

`@fontsource-variable/jetbrains-mono@5.3.0` is self-hosted (woff2, weights
100–800, `font-display: swap`) and imported at the top of `globals.css`. The
serif half is a **system stack on purpose** — nothing to download, zero
external requests. Do not add a font package or a `<link>` to a font CDN.

`h1`–`h6` are already serif globally; opt a heading back to mono with `.mono`
when it has to line up with tabular data.

## Shared keyframes

Defined once in `globals.css` — do not redeclare them in a module. Pair each
with `var(--ease)` and one of the duration tokens.

| Keyframe | What it does | Use it for |
|---|---|---|
| `fade-in` | opacity 0 → 1 | Content arriving in place. |
| `fade-up` | opacity 0 + `translateY(6px)` → 0 | A row being laid onto the page. |
| `pop-in` | scale `0.94` → `1.01` → `1` with fade | A mark being stamped: chip, badge, gate flipping to passed. |
| `spin` | `rotate(360deg)` | Indeterminate work. Needs `infinite linear`. |
| `shimmer-text` | pulses `color` `--ink-3`↔`--ink-2` and opacity | Pending text waiting on the server. **Not** a gradient sweep — gradients are banned, and a moving highlight over text hurts readability. Apply straight to the text element; no background or extra markup needed. |
| `pixel-on` | scale `0.6` → `1.08` → `1` with fade | One cell switching on: meter segment, coverage grid. |

Every animation and transition is already killed under
`@media (prefers-reduced-motion: reduce)` globally, so a module does not need
its own block — but do not rely on a *hover-only* animation to convey state.

## Utilities

Four, and no more. `.sr-only` (visually hidden, still spoken), `.tabular`
(tabular figures — already on `<body>`, so columns never jitter mid-poll),
`.serif`, `.mono`. Everything else belongs in a CSS Module.

`.sr-only` is `position: absolute`. **Never put it on a `<th>` or `<td>`** — that
takes the cell out of the table box, so the header row lays out fewer cells than
the body has columns and the header band stops short of the edge. Keep the cell
in flow and wrap only its text: `<th><span class="sr-only">…</span></th>`.

## Controls

There are exactly two sizes of button.

- **Form scale** is the shared `components/Button.tsx` — `primary` (solid ink),
  `ghost` (hairline), `subtle` (bare type), 34px min-height. Anything at the
  scale of a form or a card footer uses it. Do not restate its ground, border,
  padding or hover in a module; pass a `className` for what is genuinely local.
- **Compact scale** is 11px type, 24px min-height, `2px 8px` padding, for a
  control seated inside a table row or a card header, where 34px would push the
  row taller than its own text. `DiffPanel`'s `.btn`/`.segBtn` and `GateTable`'s
  `.expandBtn` share those metrics.

Two controls are deliberately neither: `AdvancedSection`'s `.showBtn` is welded
to the side of an input and has to match its height exactly, and `Stepper`'s
`.btn` is fixed geometry inside a bordered group.

## Non-negotiables

1. **No raw hex/rgb/hsl in a component CSS file.** Tokens only. `globals.css`
   is the single place a literal colour may appear.
2. **Colour is never the only signal.** A deletion also gets `line-through`
   and a leading `−`; an insertion gets a leading `+`; a flag gets its own
   glyph and a text label. Accessibility requirement, and it survives being
   printed in greyscale.
3. **Hairlines over shadows.** At most `--shadow-card`. No glows, no gradients,
   no glassmorphism, no coloured drop shadows.
4. **Motion is short and functional.** 120 / 180 / 300ms with `--ease`, and
   disabled under reduced motion.
5. **No emoji anywhere.** Inline SVG for icons, no icon packages. The global
   reset sets `fill: none; stroke: currentColor` on `svg`, so a glyph inherits
   `--del` / `--ins` / `--flag` from its row.
6. **Real semantic HTML.** `<table>` for tabular data, `<button>` for actions,
   a `<label>` tied to every input, keyboard reachable. The focus ring is
   global (`2px solid var(--ink)`, `2px` offset) — never remove it.
7. **Check both themes.** Especially `--ink-3` on `--paper-2`.
8. **One live region per thing being reported.** A live region only announces a
   *mutation* to a region already in the DOM, so a `role="status"` on a node that
   mounts with its text inside it announces nothing — and five of them on rows
   that all re-render together announce noise. The page owns one region for "a
   result landed"; `TaskRows` owns one for "which stage is in hand". That is all.
9. **`aria-controls` must resolve.** Disclosures keep their panel mounted and
   collapse it with `grid-template-rows: 0fr → 1fr` (plus `inert`/`aria-hidden`),
   which is also why no disclosure animates a hardcoded height.

## Where things live

- `app/globals.css` — tokens, reset, focus ring, keyframes, utilities.
- `app/layout.tsx` — `<html suppressHydrationWarning>` (a browser extension
  mutates `<html>` before hydration — leave it), `<body className="mono tabular">`,
  and a `MotionConfig` whose default tween mirrors `--ease` / `--dur-2`.
- `docs/API.md` + `lib/types.ts` — the data contract. Read, never edit.
