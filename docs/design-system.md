# MASAGI Digital — Design System

**Status:** implementation contract · **Target:** WCAG 2.2 AA · **Default theme:** light
**Authority:** `.claude/skills/design-system/SKILL.md` (mission and rules) → `landing/tokens.css` (values)
**Surfaces:** masagi.io (`landing/`) · blog.masagi.io (`cms/templates/`) · cms.masagi.io · hv.masagi.io · cro.masagi.io

Every rule below is anchored to a selector that exists today. Where the shipped code
disagrees with this document, the deviation is listed in §6.9 with a migration path —
this document is the target, the code is the current position.

Every contrast figure in this document was computed by sRGB linearisation and
`(L1 + 0.05) / (L2 + 0.05)`, not estimated. Figures that disagree with the comments in
`tokens.css` are flagged in §6.9.1.

---

## 1. Context and goals

### 1.1 What this system is for

MASAGI Digital sells finance software to Indonesian finance directors and owner-operators.
The buyer's existing trust artefacts — bank statements, audited accounts, the board pack
MASAGI-HV exports — are black on white. The design system's job is to make the marketing
site, the blog and the product consoles look like they were produced by the same discipline
that produces those documents: quiet surfaces, numbers that hold their weight, nothing that
looks like a template.

### 1.2 Design intent, in one sentence

*A quiet, hairline-separated, light-first surface where the only saturated colour is the
MASAGI green, and where the numbers are the loudest thing on the page.*

### 1.3 Non-negotiable goals

| Goal | How it is verified |
|---|---|
| One token file, one palette | `grep -rn '^\s*--[a-z]' landing/*.css cms/templates/*.html` returns hits only in `tokens.css` |
| Both themes complete | Every component in §3 has a light and a dark row; neither is a filter of the other |
| WCAG 2.2 AA, computed | §4 acceptance criteria, each with the measured pair |
| Bilingual at parity | Every `data-i18n` / `data-en` key resolves in both `en` and `id` |
| No horizontal page scroll at 320 / 375 / 768 px | §7 gate G-7 |
| Figures never weigh less than the prose around them | §3.5, §2.4 |

### 1.4 Out of scope

Product-console *application* chrome inside hv.masagi.io and cro.masagi.io (sidebars,
data grids, modals) is not specified here. Those apps consume the same `tokens.css` and
MUST follow §2 and §4; their component inventory is a separate document.

---

## 2. Design tokens and foundations

### 2.1 The token contract

`landing/tokens.css` is the single source of truth. It is served as `/tokens.css` on
masagi.io and `/static/tokens.css` on blog.masagi.io — the same bytes to both origins.

**Rules**

1. A component stylesheet MUST NOT declare a custom property. Tokens are declared once,
   in `tokens.css`, under `:root, html[data-theme="light"]` and `html[data-theme="dark"]`.
2. Component CSS MUST consume semantic tokens. A raw hex value in component CSS is a bug,
   with exactly two exemptions: the brand mark's own `<polygon fill>` attributes, and
   decorative cover gradients that are explicitly listed in §6.5.
3. `tokens.css` MUST be linked **first**, before any component sheet, on every surface.
4. Every surface MUST carry the anti-FOUC boot script *before* the first paint, in `<head>`,
   setting `data-theme` from `localStorage["masagi-theme"]` and falling back to
   `prefers-color-scheme`, then to `"light"`. This ships on all three surfaces today
   (`landing/index.html:21`, `landing/pricing.html:124`, `cms/templates/base.html:20`) and
   MUST be copied verbatim to any new surface.
5. Asset URLs MUST carry a version stamp written into the source file
   (`tokens.css?v=202608091212`), never patched after deploy. The blog currently stamps
   `?v=1` — see §6.9.

### 2.2 Colour

Light is the default and dark is a complete equal. Every value is from `tokens.css`.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--bg` | `#FFFFFF` | `#0A0A0A` | page canvas |
| `--bg-2` | `#F6F7F8` | `#141417` | alternating section band |
| `--surface` | `#FFFFFF` | `#101012` | cards, panels, console |
| `--surface-2` | `#F2F4F4` | `#18181B` | hover, nested, console bar, table row hover |
| `--surface-3` | `#F6F7F8` | `#1E1E21` | input fills, raised chips |
| `--border` | `#E3E6E6` | `#2C2C30` | decorative hairline **only** |
| `--border-soft` | `rgba(10,10,10,.08)` | `rgba(255,255,255,.07)` | band edges |
| `--field-border` | `#8E9294` | `#83838A` | **control boundaries** — the only border token that may carry SC 1.4.11 |
| `--text` | `#0A0A0A` | `#F2F2F2` | headings, ledger totals, input values |
| `--text-2` | `#5F6165` | `#8F8F94` | body prose |
| `--text-3` | `#6E7276` | `#828289` | metadata, captions, placeholders |
| `--accent` | `#1E7A4C` | `#57D496` | links, chips, focus ring, primary fill |
| `--accent-2` | `#31A96A` | `#31A96A` | gradients and marks **only** — never text, never a fill under white ink |
| `--accent-ink` | `#FFFFFF` | `#05140B` | the only legal ink on an `--accent` fill |
| `--accent-soft` | `rgba(30,122,76,.09)` | `rgba(87,212,150,.10)` | chip fills |
| `--accent-line` | `rgba(30,122,76,.26)` | `rgba(87,212,150,.28)` | hover borders — decorative, never load-bearing |

**Colour rules**

- The light theme MUST use the deep green `#1E7A4C`. `#57D496` on `#FFFFFF` is **1.86:1**
  and is prohibited as light-theme ink or as a fill under white ink.
- `--accent-ink` is theme-flipped and MUST be used for any text on an `--accent` fill.
  Hard-coding `#fff` on an accent fill produces **1.86:1** in dark (`#FFFFFF` on `#57D496`)
  and is prohibited. This defect ships today — see §6.9.2.
- `--accent-2` (`#31A96A`) MUST NOT be used as text on a light surface: `#31A96A` on
  `#FFFFFF` is **2.99:1**. It is also illegal as a fill under `--accent-ink` in light:
  `#FFFFFF` on `#31A96A` is **2.99:1**.
- `--border` is decorative. `#E3E6E6` on `#FFFFFF` is **1.26:1** and `#2C2C30` on `#0A0A0A`
  is **1.42:1** — it cannot satisfy SC 1.4.11 for any control. Controls whose identity
  depends on their outline MUST use `--field-border` or supply a ≥3:1 glyph (§3.1, §3.2).

### 2.3 Surface separation

Adjacent MASAGI surfaces separate by luminance ratios between **1.07:1 and 1.14:1** —
by design, and far below any perceptual guarantee. Nothing structural may depend on a
fill delta alone.

| Pair | Light | Dark |
|---|---|---|
| `--bg-2` band vs `--bg` canvas | 1.07:1 | 1.08:1 |
| `--surface-3` field fill vs `--surface` card | 1.07:1 | 1.14:1 |
| `--surface-2` row hover vs `--surface` | 1.10:1 | 1.07:1 |

**Rule:** every boundary that a user must perceive — section band, card edge, field edge,
table foot — MUST be drawn with a border token, never left to the fill delta.
`theme-swiper.css:135` (`.section.alt` hairlines) and `theme-swiper.css:307` (`tfoot`
border-top) are the pattern to copy.

### 2.4 Type

Family: `"Inter", "Helvetica Neue", Arial, sans-serif`. Weights loaded: 400 · 500 · 600 · 700 · 800.

**Ramp (contract).** Every step is a decision. Values not on this ramp MUST NOT be introduced.

| Step | px | Use |
|---|---|---|
| `t-12` | 12 | eyebrow, table head, meta, legal, footer base |
| `t-14` | 14 | dense UI: nav links, chips, table body, card body |
| `t-16` | 16 | body prose default |
| `t-18` | 18 | lead paragraph, hero sub at desktop |
| `t-20` | 20 | card headings, `h3` |
| `t-24` | 24 | `pcard h2`, small section heads |
| `t-30` | 30 | `h2` minimum, hero `h1` minimum |
| `t-38` | 38 | `h2` maximum, stat figure |
| `t-50` | 50 | hero `h1` maximum |

- **12px is the floor.** No text below 12px on any public surface. `table.pl thead th`
  at 10.5px, `.p-tag` at 11px, `.eyebrow` at 11.5px and `.console-note` at 11.5px all
  violate this today (§6.9.3).
- Headings MUST be weight **600**, letter-spacing **-0.022em**, line-height 1.04–1.10;
  the hero `h1` uses **-0.026em**.
- Body MUST be `--text-2`, line-height 1.6–1.65.
- **Numerals:** every stat and every ledger figure MUST be weight **700** with
  `font-variant-numeric: tabular-nums`. In a finance product a figure MUST NOT weigh less
  than the prose beside it. `table.pl` (`theme-swiper.css:298`) and `table.pl tfoot td`
  (`:308`) are correct; `table.pl tbody td` inherits regular weight and that is deliberate —
  only the total is bold, so the eye lands on it.
- Half-pixel and quarter-step sizes (`13.5px`, `14.5px`, `15.5px`, `17.5px`) are prohibited
  in new code. Existing ones are mapped in §6.9.3.

### 2.5 Spacing

4px rhythm: `4 · 8 · 12 · 16 · 20 · 24 · 32 · 44 · 64 · 80`.

- Component padding, gaps and margins MUST come from this scale.
- Section vertical padding MUST be `64` (mobile) → `80` (≥768px) → `104` (≥1024px).
- The page gutter MUST be `20px` at every width. It is `22px` today across all three
  surfaces (§6.9.3); when it changes it MUST change in all three at once, because the
  landing and blog wrappers are visually aligned across a subdomain hop.
- Off-scale values (`9px`, `11px`, `13px`, `18px`, `22px`, `26px`, `34px`, `46px`, `74px`,
  `88px`) MUST NOT be introduced. Existing ones are mapped in §6.9.3.

### 2.6 Geometry

| Token | Value | Applies to |
|---|---|---|
| `--r-sm` | 12px | inputs, textareas, small marks, inline chips that are not pills |
| `--r-md` | 20px | cards, panels, mobile menu sheet, logo tiles |
| `--r-lg` | 32px | feature blocks, the console, `.product`, `.case-inner`, hero media |
| `--pill` | 999px | buttons, tags, language group, theme button, category chips |

Raw radii (`5px`, `6px`, `7px`, `10px`, `11px`, `12px`, `14px`, `16px`) MUST NOT be
introduced. Existing ones are mapped in §6.9.3.

### 2.7 Motion

| Duration | Use |
|---|---|
| 120ms | press feedback (`transform: translateY(1px)`) |
| 180ms | hover, colour, border-colour, background |
| 250–300ms | theme swap, navbar scrolled transition, hamburger glyph |
| 600ms | scroll-reveal and carousel |

All motion MUST be inside `@media (prefers-reduced-motion: no-preference)` or be neutralised
by a `reduce` block. `styles.css:299-302` neutralises `.reveal` and `scroll-behavior` and
MUST be extended to cover any new animation. Swiper autoplay MUST be disabled under
`prefers-reduced-motion: reduce` — it is not today (§6.9.4).

### 2.8 Breakpoints

Canonical set. New CSS MUST use only these.

| Name | Query | Layout change |
|---|---|---|
| base | — | single column, mobile-first |
| `sm` | `min-width: 480px` | reserved; no current use |
| `md` | `min-width: 768px` | 3-up about grid, 4-up stats, 3-up media, 3-up steps, 2-up form row, 4-up footer |
| `lg` | `min-width: 1024px` | desktop menu replaces hamburger, 2-up products, split contact grid, 104px sections |
| `xl` | `min-width: 1280px` | max container reached; no further structural change |

Three component-scoped max-width queries are permitted because they track a *content*
threshold rather than a device class, and each MUST carry a comment saying what overflows:

- `max-width: 940px` — hero and console grids collapse to one column.
- `max-width: 860px` — blog `.cats` becomes a scroll strip.
- `max-width: 620px` — console table sheds its COGS column.

`900px`, `820px`, `560px`, `400px` and `1224px` queries are strays and MUST be folded into
the canonical set or one of the three above (§6.9.3).

### 2.9 Measured contrast reference

Every ratio cited in §3 and §4 comes from this table. Computed, not estimated.

**Light** — canvas `#FFFFFF`, band/field `#F6F7F8`, hover `#F2F4F4`

| Foreground | on `#FFFFFF` | on `#F6F7F8` | on `#F2F4F4` |
|---|---|---|---|
| `--text` `#0A0A0A` | 19.80 | 18.46 | 17.93 |
| `--text-2` `#5F6165` | 6.20 | 5.78 | 5.62 |
| `--text-3` `#6E7276` | 4.85 | 4.52 | **4.39** |
| `--accent` `#1E7A4C` | 5.33 | 4.96 | 4.82 |
| `--accent-2` `#31A96A` | **2.99** | — | — |
| `--field-border` `#8E9294` | 3.14 | **2.93** | — |
| `--border` `#E3E6E6` | **1.26** | **1.17** | — |

Light composites: `--accent-soft` over `#FFFFFF` = `#EBF3EF`, `--accent` on it = **4.72**;
over `#F6F7F8` = `#E3ECE9`, `--accent` on it = **4.42**. `--accent-line` over `#FFFFFF` =
`#C4DCD0`, **1.45** against the card. `--accent-ink` `#FFFFFF` on `--accent` `#1E7A4C` = **5.33**.

**Dark** — canvas `#0A0A0A`, band `#141417`, surface `#101012`, hover `#18181B`, field `#1E1E21`

| Foreground | on `#0A0A0A` | on `#101012` | on `#141417` | on `#18181B` | on `#1E1E21` |
|---|---|---|---|---|---|
| `--text` `#F2F2F2` | 17.68 | 16.98 | 16.42 | — | 14.85 |
| `--text-2` `#8F8F94` | 6.15 | 5.91 | 5.71 | 5.50 | — |
| `--text-3` `#828289` | 5.19 | 4.98 | 4.82 | 4.64 | **4.36** |
| `--accent` `#57D496` | 10.62 | 10.19 | 9.86 | 9.50 | 8.92 |
| `--accent-2` `#31A96A` | 6.61 | 6.35 | — | — | — |
| `--field-border` `#83838A` | 5.26 | 5.05 | 4.88 | — | 4.42 |
| `--border` `#2C2C30` | **1.42** | **1.37** | **1.32** | — | — |

Dark composites: `--accent-soft` over `#101012` = `#17241F`, `--accent` on it = **8.61**;
over `#0A0A0A` = `#121E18`, **9.20**. `--accent-line` over `#101012` = `#244737`, **1.84**
against the surface. `--accent-ink` `#05140B` on `--accent` `#57D496` = **10.13**.

Bolded figures fail the threshold for their intended use and are handled in §3 and §6.

---

## 3. Component-level rules

Each family below states anatomy, variants, all seven states, the tokens it consumes,
behaviour at 320 / 375 / 768 / 1024 / 1280, long-content and overflow handling, empty
state, keyboard / pointer / touch behaviour, and both themes.

**State vocabulary.** The seven states are `default`, `hover`, `focus-visible`, `active`,
`disabled`, `loading`, `error`. Where a state is not applicable, the row MUST say so and
say why — "N/A" without a reason is not acceptable in this document or in a review.

**Global focus rule.** `theme-swiper.css:268-270` defines the ring:

```
a:focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px;
}
```

The `outline-offset: 2px` is load-bearing, not cosmetic: on an `--accent`-filled control
the ring would otherwise sit accent-on-accent at 1:1. The 2px gap puts page background
between ring and fill, so the measured pair becomes ring-vs-canvas — **5.33:1** light
(`#1E7A4C` on `#FFFFFF`) and **10.62:1** dark (`#57D496` on `#0A0A0A`). Any component that
suppresses the offset MUST supply its own ≥3:1 indicator.

This rule ships on `landing/index.html` only. `landing/pricing.html` and
`cms/templates/base.html` do not load `theme-swiper.css` and therefore have no
`:focus-visible` rule at all (§6.9.5). It MUST be added to both.

---

### 3.1 Buttons

**Selectors:** `.btn` · `.btn-accent` · `.btn-line` · `.menu-cta` · `.menu-cta.ghost` ·
`.btn-a` · `.pcard .cta` · `.btn-solid` · `.btn-ghost` · `.scoping button` · `.mobile-login`

#### 3.1.1 Anatomy

```
┌──────────────────────────────────┐
│  [pad-x 24]  Label  [pad-x 24]   │  ← --pill, 1px border, no icon slot today
└──────────────────────────────────┘
   ▲ pad-y 12   ▲ 14px / 600 / -0.01em
```

A button is: a pill container, a 1px border (present on every variant, transparent or
coloured), a single text label. There is no icon slot, no badge and no split control in
this system. Minimum target 44×44px including padding — 12px vertical padding on a
14px/1.6 label gives 46px, which satisfies it. Any variant that reduces vertical padding
MUST restore the 44px floor with `min-height`.

#### 3.1.2 Variants

| Variant | Fill | Ink | Border | Where |
|---|---|---|---|---|
| `.btn-accent` (primary) | `--accent` | `--accent-ink` | `--accent` | hero CTAs, product CTAs, form submit |
| `.btn-line` (secondary) | transparent | `--text` | `--field-border` *(target; ships `--border`)* | "See both products" |
| `.menu-cta` (nav primary) | `--accent` | `--accent-ink` | none | nav Login |
| `.menu-cta.ghost` (nav secondary) | transparent | `--text` | `--field-border` *(target; ships `--border`)* | nav "Talk to us" |
| `.pcard .cta` (card primary) | `--accent` | `--accent-ink` | `--accent` | pricing card "Get a quote" |
| `.mobile-login` (compact nav primary) | `--accent` | `--accent-ink` *(target; ships `#fff`)* | none | <1024px Login |

There MUST be exactly one `.btn-accent` per view region. Two primaries in one card,
or a primary that repeats an adjacent primary's label, is a review failure.

#### 3.1.3 States

| State | Primary (`.btn-accent`, `.menu-cta`, `.pcard .cta`) | Secondary (`.btn-line`, `.menu-cta.ghost`) |
|---|---|---|
| **default** | `--accent` fill, `--accent-ink` label | transparent, `--text` label, `--field-border` outline |
| **hover** | `filter: brightness(1.07)`, 180ms. MUST NOT change the label token | `background: --glass`, `border-color: --accent-line`, label stays `--text` |
| **focus-visible** | 2px `--accent` outline at 2px offset (§3 global rule) | same |
| **active** | `transform: translateY(1px)`, 120ms | same |
| **disabled** | `opacity: .45`, `pointer-events: none`, `aria-disabled="true"`. MUST NOT be conveyed by opacity alone — the label MUST also change (e.g. "Sending…"). **No button on the public site uses this today**; the rule exists so the first one is right | same |
| **loading** | **Not applicable on the marketing surfaces.** Both forms resolve by setting `window.location.href` to a `mailto:` URI (`script.js:328`, `pricing.html:312`) — there is no async round trip, so there is no interval to represent. If a real endpoint replaces `mailto:`, the submit button MUST take `aria-busy="true"`, swap the label to the ID/EN "Sending…" string, keep its width fixed with `min-width` measured against the *Indonesian* label, and stay focusable | Not applicable — secondary buttons are navigational only |
| **error** | **Not applicable to the button itself.** Validation errors belong on the field (§3.4). The button MUST NOT turn red, MUST NOT be disabled to express an error, and MUST NOT be the only thing that announces failure | Not applicable — same reason |

#### 3.1.4 Tokens consumed

`--accent` · `--accent-ink` · `--accent-line` · `--field-border` · `--glass` · `--text` ·
`--pill` · type `t-14` weight 600 letter-spacing -0.01em · padding `12px 24px` · motion 120/180ms.

#### 3.1.5 Responsive

| Width | Behaviour |
|---|---|
| 320px | `.cta-row` wraps; buttons go full-width via `flex: 1 1 100%` so a wrapped ID label never leaves an orphan 40px button. Padding tightens to `12px 20px` |
| 375px | Two short buttons may sit side by side; the row MUST still be `flex-wrap: wrap` |
| 768px | Buttons return to intrinsic width, `12px 24px` |
| 1024px | `.menu-cta` and `.menu-cta.ghost` become visible with the desktop menu; `.mobile-login` hides |
| 1280px | No change |

#### 3.1.6 Long content, overflow, empty

- Labels MUST be one line. `white-space: nowrap` is prohibited on buttons — a nowrap
  Indonesian label is what pushes a row past the viewport. Let the *row* wrap instead.
- A button MUST NOT be sized by a fixed `width`. Where two buttons must match, use the
  grid/flex track, not a pixel width.
- A button with no label MUST NOT be rendered. If a CMS-driven CTA arrives with a label
  but no `href`, or an `href` but no label, the button MUST be omitted entirely —
  `script.js:225-227` already gates on both and is the pattern to copy.

#### 3.1.7 Keyboard, pointer, touch

- **Keyboard:** every button is a native `<button>` or `<a href>`. Enter activates links
  and buttons; Space activates buttons. No `div` with a click handler, no `tabindex="0"`
  substitutes. Tab order MUST follow visual order.
- **Pointer:** hover is 180ms; `:hover` MUST NOT be the only channel for information.
- **Touch:** 44×44px minimum (SC 2.5.8). `:hover` styles are unreachable on touch, so no
  affordance may live only in hover. `.btn:active { transform: translateY(1px) }` gives
  touch users press feedback and MUST be retained.

#### 3.1.8 Themes

| | Light | Dark |
|---|---|---|
| Primary label on fill | `#FFFFFF` on `#1E7A4C` = **5.33:1** | `#05140B` on `#57D496` = **10.13:1** |
| Secondary label on canvas | `#0A0A0A` on `#FFFFFF` = **19.80:1** | `#F2F2F2` on `#0A0A0A` = **17.68:1** |
| Secondary outline vs canvas | `#8E9294` on `#FFFFFF` = **3.14:1** ✓ *(ships `#E3E6E6` = 1.26:1 ✗)* | `#83838A` on `#0A0A0A` = **5.26:1** ✓ *(ships `#2C2C30` = 1.42:1 ✗)* |
| Focus ring vs canvas | **5.33:1** | **10.62:1** |

`.btn-accent`'s glow is `0 10px 30px rgba(87,212,150,.16)` in both themes — a light-green
shadow under a deep-green light-theme button. It MUST be tokenised per theme or removed.
The pricing page's `rgba(37,99,235,.30)` blue glow under a green button
(`pricing.html:52, 81, 103`) MUST be removed (§6.9.6).

---

### 3.2 Navigation

**Selectors:** `.navbar` · `.navbar.scrolled` · `.menu` · `.menu.mobile-open` ·
`.hamburger` · `.lang-group` / `.lang-btn` · `.theme-btn` · `.mobile-login` ·
blog `.cats` / `.cats a` / `.cats a.on`

#### 3.2.1 Anatomy

```
┌───────────────────────────────────────────────────────────────┐
│ [mark + wordmark]   [ menu links … CTA CTA ]   [EN|ID] [☾] [≡] │  72px
└───────────────────────────────────────────────────────────────┘
     brand              .menu (≥1024px)            .nav-controls
```

Blog header: brand · `.cats` chip strip · `.tools` (EN | ID | ☾), 64px.

Three regions, fixed order: brand (home link), navigation, controls. The controls cluster
MUST NOT wrap under the brand — it is `flex-shrink: 0`.

#### 3.2.2 Variants

| Variant | Trigger | Treatment |
|---|---|---|
| `.navbar` at rest | `scrollY ≤ 40` | transparent, transparent bottom border |
| `.navbar.scrolled` | `scrollY > 40`, or the mobile menu opening | `--nav-bg` + `blur(16px) saturate(140%)` + `--border-soft` hairline |
| `.menu` desktop | `≥1024px` | horizontal row |
| `.menu.mobile-open` | hamburger toggled | opaque `--surface` sheet below the bar, `--r-md`, full-width rows |
| blog `.cats` | `>860px` | wrapping pill row |
| blog `.cats` strip | `≤860px` | full-width, `flex-wrap: nowrap`, `overflow-x: auto`, scrollbar hidden |

Opening the mobile menu MUST force `.scrolled` on. The sheet is `--surface` (opaque) but
the bar above it is not, and translucent nav over live page content has no measurable
contrast. `script.js:80` does this and MUST be preserved.

#### 3.2.3 States

| State | Menu link | `.lang-btn` | `.theme-btn` | `.hamburger` | blog `.cats a` |
|---|---|---|---|---|---|
| **default** | `--text-2`, 2px transparent bottom border | `--text-2`, `--pill` group with `--field-border` | `--text-2` glyph, `--field-border` ring | 3 bars in `--text` | `--text-2` pill |
| **hover** | `--text` + `--accent` bottom border | `--text` | `--text`, `border-color: --accent-line` | `border-color: --accent-line` | `--text` on `--surface-2` |
| **focus-visible** | global ring | global ring | global ring | global ring | global ring |
| **active** | no transform (the border is the feedback) | pressed state = selected state | `translateY(1px)` | bars animate to ✕ over 250ms | `translateY(1px)` |
| **selected** | `aria-current="page"` + `--text` + persistent `--accent` border | `.on` → `--accent` fill, `--accent-ink` label, `aria-pressed="true"` | `aria-pressed` reflects dark on/off | `aria-expanded="true"` + `.open` glyph | `.on` → `--accent` fill + `aria-current="page"` |
| **disabled** | **Not applicable.** A destination that does not exist MUST be removed from the nav, not greyed out — a disabled nav item is an unexplained dead end | Not applicable — both languages always exist | Not applicable — both themes always exist | Not applicable | Not applicable |
| **loading** | **Not applicable.** The nav is static markup; it never waits on a fetch | Not applicable — language swap is a synchronous DOM pass (`script.js:27-44`) | Not applicable — theme swap is a synchronous attribute write | Not applicable | Not applicable |
| **error** | **Not applicable.** Navigation cannot fail locally; a 404 is the destination's problem | If `localStorage` throws, the swap still applies and only persistence is lost (`script.js:43`) — silent by design, no error UI | Same as `.lang-btn` | Not applicable | Not applicable |

#### 3.2.4 Tokens consumed

`--nav-bg` · `--border-soft` · `--field-border` · `--text` / `--text-2` · `--accent` ·
`--accent-ink` · `--surface` · `--surface-2` · `--accent-line` · `--glass` · `--pill` ·
`--r-md` · type `t-14` weight 500 · motion 180/250ms.

#### 3.2.5 Responsive

| Width | Behaviour |
|---|---|
| 320px | Bar 72px. Controls gap 4px, `.lang-btn` padding `4px 6px`, `.theme-btn` 28×28, `.hamburger` 32×32, brand mark capped at 116px. Every control MUST still hit 44px of *touch target* via padding on its hit area even where the painted box is 28px |
| 375px | Controls gap 6px, `.theme-btn` 30×30, `.hamburger` 34×34. This is the width at which brand + EN/ID + theme + hamburger overflowed by ~36px before the compaction rules landed; it MUST be re-measured on every nav change |
| 768px | Still hamburger. `.mobile-login` visible so Login is reachable without opening the sheet |
| 1024px | `.menu` becomes `flex`, `.hamburger` and `.mobile-login` hide. Sheet state MUST be cleared on the same tick so a resize past 1024px cannot leave `aria-expanded="true"` |
| 1280px | Container capped at 1180px; gutters grow |

Blog `.cats`: ≤860px the header wraps to two rows and the strip becomes horizontally
scrollable. It MUST NOT be hidden — it is the blog's only navigation
(`cms/templates/base.html:48-56`).

#### 3.2.6 Long content, overflow, empty

- Nav labels MUST NOT be truncated with an ellipsis. "Location & Contact" → "Lokasi &
  Kontak" is shorter in ID, but "Book a scoping call" → "Jadwalkan sesi konsultasi"
  (**+32%**) is not: the nav CTA MUST be allowed to set the bar's intrinsic width at
  ≥1024px, and MUST NOT appear at all below it (the sheet carries it instead).
- The `.cats` strip MUST keep `flex: 0 0 auto` on children so a long category name scrolls
  rather than compressing its neighbours, and the scroll container MUST NOT hide its
  overflow without also being scrollable.
- **Empty:** the blog renders whatever `types` yields; with zero categories the strip
  degrades to the single "All" chip, which is correct and MUST NOT be special-cased.
- The mobile sheet MUST scroll internally (`max-height: calc(100dvh - 72px); overflow-y: auto`)
  once its item count exceeds the viewport. It does not today and MUST be fixed before any
  nav item is added.

#### 3.2.7 Keyboard, pointer, touch

Required behaviour, all testable:

1. `.hamburger` MUST carry `aria-expanded` (ships, `script.js:79`) **and**
   `aria-controls="menu"` (missing — MUST be added).
2. **Escape MUST close the open sheet and return focus to `.hamburger`.** Not implemented —
   a keyboard user who opens the sheet today cannot close it without tabbing through it.
   This is the single highest-priority nav fix.
3. While the sheet is open, Tab MUST cycle within it; background content MUST be
   `inert` or `aria-hidden="true"`.
4. `.lang-btn` and `.theme-btn` MUST expose their state programmatically: `aria-pressed`
   on both, and the theme button's `aria-label` MUST describe the *action* and update with
   state ("Switch to dark theme" / "Switch to light theme"). Today the glyph changes
   (`script.js:13`) but the label is a static "Toggle dark mode", and on `pricing.html:148`
   and `base.html:98` there is no `aria-label` at all — only a `title`.
5. The current page MUST be marked with `aria-current="page"`, not by class alone.
   `.cats a.on` and `.menu a.on` are visual-only today.
6. Touch: every control ≥44×44px of hit area. Tapping a sheet link closes the sheet
   (`script.js:84-91`) — correct, and MUST be preserved.

#### 3.2.8 Themes

| | Light | Dark |
|---|---|---|
| Menu link on canvas | `#5F6165` on `#FFFFFF` = **6.20:1** | `#8F8F94` on `#0A0A0A` = **6.15:1** |
| Sheet link on `--surface` | `#0A0A0A` on `#FFFFFF` = **19.80:1** | `#F2F2F2` on `#101012` = **16.98:1** |
| `.lang-btn.on` | `#FFFFFF` on `#1E7A4C` = **5.33:1** | `#05140B` on `#57D496` = **10.13:1** |
| `.theme-btn` glyph | `#5F6165` on `#FFFFFF` = **6.20:1** | `#8F8F94` on `#0A0A0A` = **6.15:1** |
| `.hamburger` bars | `#0A0A0A` on `#FFFFFF` = **19.80:1** | `#F2F2F2` on `#0A0A0A` = **17.68:1** |
| `.mobile-login` | `#FFFFFF` on `#1E7A4C` = **5.33:1** ✓ | `#FFFFFF` on `#57D496` = **1.86:1** ✗ |

`.mobile-login` is a live AA failure. `styles.css:89-92` sets `color: #fff !important` and
`theme-swiper.css` never reclaims it, so below 1024px in dark theme the Login button's label
sits at **1.86:1**. It MUST use `--accent-ink`. See §6.9.2.

The `.theme-btn` and `.hamburger` outlines are `--border` — **1.26:1** light, **1.42:1**
dark — and cannot carry SC 1.4.11. These are icon-only controls, so the *glyph* is the
identifying feature and it measures 6.15–19.80:1, which satisfies the SC. That is the
justification, and it MUST be recorded rather than assumed: any icon-only control whose
glyph drops below 3:1 fails, outline or no outline.

`--nav-bg` is translucent (`rgba(255,255,255,.82)` / `rgba(12,12,14,.72)`), so nav-link
contrast over scrolling content is *not* the value above. The 6.20 / 6.15 figures are the
worst case measured against the pure canvas. Any content that scrolls beneath the bar MUST
stay within `--bg` ± the band tokens; a photograph or a saturated gradient MUST NOT pass
under the navbar.

---

### 3.3 Cards

**Selectors:** `.card` · `.product.glass` · `.step-card` · `.stat` · `.m-card` ·
`.c-block` · `.case-inner` · `.pcard` · blog `.card`

#### 3.3.1 Anatomy

```
┌─ 1px --border, --r-md ────────────┐
│  [ media / icon / number ]        │  optional
│  [ eyebrow or tag ]               │  optional, --accent on --accent-soft
│  Heading            t-20 / 600    │
│  Body               t-14 / --text-2
│  [ action ]                       │  optional
└───────────────────────────────────┘
   --surface fill · box-shadow: none
```

One family, one treatment: `--surface` fill, 1px `--border`, `--r-md` (`--r-lg` for
`.product` and `.case-inner`), **no shadow at rest**. `theme-swiper.css:140-146` unifies
them and is the canonical rule.

#### 3.3.2 Variants

| Variant | Radius | Extra anatomy |
|---|---|---|
| `.card` (about) | `--r-md` | 46px gradient icon tile |
| `.product.glass` (service) | `--r-lg` | `.p-tag` chip, feature list, primary CTA, `::before` accent-soft bloom |
| `.step-card` (how) | `--r-md` | `.step-n` numeral chip |
| `.stat` | `--r-md` | `t-38` / 700 accent figure + `t-14` `--text-2` caption |
| `.m-card` (media) | `--r-md` | 150px cover, meta row, `overflow: hidden` — whole card is one `<a>` |
| `.c-block` (contact) | `--r-md` | `t-12` accent label + value |
| `.case-inner` | `--r-lg` | centred, `max-width: 900px` |
| `.pcard` (pricing) | `--r-md` | 46px mark, price, feature list, CTA |
| blog `.card` | `--r-md` | 172px cover, `display: flex; flex-direction: column`, `.card-b { flex: 1 }` so CTAs bottom-align |

`.product.glass` MUST NOT actually be glass. `styles.css:218-223` gives it
`background: var(--glass)` + `backdrop-filter: blur(12px)`; `theme-swiper.css:233-239`
reclaims it to `--card-bg` with `backdrop-filter: none`. The reclaim is the intended
state — a blurred translucent card over a near-white canvas has no measurable boundary.
The class name is now a lie and SHOULD be renamed `.product` in a follow-up.

#### 3.3.3 States

| State | Interactive card (`.m-card`, blog `.card`) | Static card (`.card`, `.step-card`, `.stat`, `.c-block`, `.case-inner`, `.pcard`) |
|---|---|---|
| **default** | `--surface`, `--border`, no shadow | identical |
| **hover** | `border-color: --accent-line`, `background: --surface-2`, `translateY(-2px)`, 180ms | `.card`/`.step-card` share the hover today. They SHOULD NOT: a static card that lifts under the cursor promises a click it does not deliver. Static cards MUST drop the transform and the border change |
| **focus-visible** | global ring on the wrapping `<a>`; ring MUST surround the whole card, so the card MUST NOT set `overflow: hidden` on the focusable element itself. `.m-card` and blog `.card` both set `overflow: hidden` — the ring is drawn outside the box so it survives, but any inner focus styling would be clipped | **Not applicable** — a static card is not focusable and MUST NOT be given `tabindex` |
| **active** | `translateY(0)`, 120ms — the lift collapses under the press | Not applicable |
| **disabled** | **Not applicable.** An unavailable article is not listed. A card MUST NOT be rendered greyed-out and unclickable | Not applicable |
| **loading** | **Applicable, and already solved by fallback rather than skeleton.** `.media-grid` ships three real static cards; `script.js:302-316` replaces them once the CMS answers and `renderMediaCards` returns early on an empty result (`:265`), so a slow or dead CMS leaves real content on screen. Skeleton placeholders MUST NOT be introduced — a marketing page must never render an empty rectangle. The same pattern governs the hero (`script.js:249`) | Not applicable — static cards are authored in markup |
| **error** | **Applicable.** A failed fetch MUST be silent to the user and MUST leave the fallback markup intact (`script.js:299, 316`). An error message in place of content is prohibited on a marketing surface | Not applicable |

#### 3.3.4 Tokens consumed

`--surface` · `--surface-2` · `--border` · `--accent-line` · `--accent` · `--accent-soft` ·
`--text` / `--text-2` / `--text-3` · `--r-md` / `--r-lg` / `--pill` · type `t-20` heading /
`t-14` body / `t-38` stat · padding `24px` (mobile) → `32px` (≥768px) · gap `20px` · motion 180ms.

#### 3.3.5 Responsive

| Width | About | Products | Steps | Media / blog | Stats | Pricing |
|---|---|---|---|---|---|---|
| 320px | 1-up | 1-up | 1-up | 1-up | 2-up | 1-up |
| 375px | 1-up | 1-up | 1-up | 1-up | 2-up | 1-up |
| 768px | 3-up | 1-up | 3-up | 3-up (blog 2-up ≤900px) | 4-up | 2-up |
| 1024px | 3-up | 2-up | 3-up | 3-up | 4-up | 2-up |
| 1280px | 3-up, container capped | 2-up | 3-up | 3-up | 4-up | 2-up |

**Every grid child that can contain wide content MUST set `min-width: 0`.** Grid items
default to `min-width: auto`, which refuses to shrink below their content — that is
exactly how the console's ~416px table forced its hero column, and the whole page, wider
than a 375px viewport. `theme-swiper.css:409` fixes `.hero-grid > *` and `.console-grid > *`;
`.about-grid`, `.products`, `.steps`, `.media-grid`, `.stats`, `.contact-grid`,
`.foot-grid`, `.inc-grid` and blog `.grid` MUST get the same treatment before any of them
receives a table, a `<pre>`, a long URL or an untruncated Indonesian entity name.

#### 3.3.6 Long content, overflow, empty

- Card headings MUST wrap, never truncate. Two-line headings are normal; the grid row
  stretches, so cards in a row MUST be equal-height by grid default, not by fixed `height`.
- Bodies SHOULD be capped at `48ch` so an ID paragraph 12–20% longer than its EN source
  does not produce a card twice the height of its neighbours.
- Where a card has a bottom-aligned action, the body MUST take `flex: 1` — blog
  `.card-b p { flex: 1 }` is the pattern. Without it, a short ID excerpt lifts its
  "Baca selengkapnya →" out of alignment with the card beside it.
- Covers MUST have an explicit height (150px landing, 172px blog) so a card has a stable
  box before its background image resolves.
- **Empty state:** the blog index ships the correct one — `.empty`, 70px vertical padding,
  centred `--text-2`, bilingual via `data-en` / `data-id`
  (`cms/templates/index.html:65-66`). Any new collection MUST provide the same: a
  sentence, both languages, no illustration, no retry button.
- A card MUST NOT render with an empty heading. `renderMediaCards` writes `title_en || ""`
  (`script.js:270`) — a post with no EN title produces a headless card. The renderer MUST
  fall back to the other language before falling back to an empty string.

#### 3.3.7 Keyboard, pointer, touch

- An interactive card MUST be a single `<a>` wrapping its content (`.m-card`, blog
  `.card`) so there is one tab stop, one accessible name and one target. Nested links
  inside a card link are prohibited.
- A static card MUST NOT be focusable.
- The accessible name of a card link is its heading. `.m-read` / `.read` ("Read more →")
  is decorative repetition and SHOULD carry `aria-hidden="true"` so the link is not
  announced as "…Read more" on every card.
- Touch: the whole card is the target, which comfortably exceeds 44×44px. The `-2px` hover
  lift is pointer-only and MUST NOT be the only affordance.

#### 3.3.8 Themes

| | Light | Dark |
|---|---|---|
| Heading on card | `#0A0A0A` on `#FFFFFF` = **19.80:1** | `#F2F2F2` on `#101012` = **16.98:1** |
| Body on card | `#5F6165` on `#FFFFFF` = **6.20:1** | `#8F8F94` on `#101012` = **5.91:1** |
| Meta on card | `#6E7276` on `#FFFFFF` = **4.85:1** | `#828289` on `#101012` = **4.98:1** |
| Body on hovered card | `#5F6165` on `#F2F4F4` = **5.62:1** | `#8F8F94` on `#18181B` = **5.50:1** |
| Meta on hovered card | `#6E7276` on `#F2F4F4` = **4.39:1** ✗ | `#828289` on `#18181B` = **4.64:1** ✓ |
| Chip (`.p-tag`, `.tag`, `.step-n`) on card | `#1E7A4C` on `#EBF3EF` = **4.72:1** | `#57D496` on `#17241F` = **8.61:1** |
| Chip on `--bg-2` band | `#1E7A4C` on `#E3ECE9` = **4.42:1** ✗ | — |

Two rules follow directly:

1. `--text-3` MUST NOT be used on `--surface-2`. In light it measures **4.39:1** against
   `#F2F4F4`, below the 4.5:1 that SC 1.4.3 requires for text under 18.66px. Meta rows that
   survive a row/card hover MUST use `--text-2` (**5.62:1**).
2. An accent chip MUST sit on `--surface`, never directly on `--bg-2`. On the band the
   composite is `#E3ECE9` and the label measures **4.42:1**. Every shipped chip currently
   sits on a card and passes at **4.72:1**; the rule prevents the next one from not.

---

### 3.4 Forms

**Selectors:** `.f-field label` · `.f-field input` · `.f-field textarea` · `.f-row` ·
`.c-form` · `.f-note` · pricing `.scoping form` · `.fld` · `.f2` · `.scoping button`

#### 3.4.1 Anatomy

```
LABEL                      t-12 / 600 / .06em / uppercase / --text-2
┌─ 1px --field-border, --r-sm ─────────────────┐
│  value / placeholder    t-14 / --text        │  --surface-3 fill
└──────────────────────────────────────────────┘
  helper or error         t-12 / --text-3 or --danger
```

Label above field, never a floating label, never placeholder-as-label. The placeholder is
an *example*, not a name — `placeholder="you@company.co.id"` beside a real `<label>Email</label>`
is the correct pattern and ships.

#### 3.4.2 Variants

| Variant | Where | Notes |
|---|---|---|
| Single-column field | both forms | default |
| Paired row | `.f-row` (≥768px), `.f2` (all widths) | `.f2` on pricing is 2-up even at 320px and MUST be made responsive |
| Textarea | both forms | `resize: vertical` only; horizontal resize would break the card |
| Submit | `.btn-accent` / `.scoping button` | §3.1 |
| Note | `.f-note` / `.note` | sets expectation of what submit does |

#### 3.4.3 States

| State | Treatment |
|---|---|
| **default** | fill `--surface-3`, border `--field-border`, value `--text`, placeholder `--text-3`, radius `--r-sm` |
| **hover** | `border-color: --text-3`, 180ms. Cosmetic only — the field is already delimited at rest |
| **focus-visible** | `border-color: --accent` **and** `box-shadow: 0 0 0 3px var(--accent-soft)`. The **border change** is the indicator that satisfies SC 1.4.11 — the 3px halo is 9–10% alpha and measures **1.13:1** against white, so it is decorative and MUST NOT be relied on alone. `outline: none` is therefore permitted here **only because** the border carries the indicator; removing the border change without restoring an outline is a regression |
| **active** | Not distinguished from focus. A text input has no meaningful pressed state — the caret is the feedback |
| **disabled** | `opacity: .55`, `cursor: not-allowed`, `--surface-2` fill, and the `disabled` attribute so it leaves the tab order. **Not used on either shipped form**; specified so the first use is correct. A disabled field MUST be accompanied by text explaining why |
| **loading** | **Not applicable to fields.** Neither form performs an async round trip — both build a `mailto:` URI and set `window.location.href` (`script.js:328`, `pricing.html:312`). If a real endpoint lands, fields MUST become `readonly` (not `disabled`, which would drop them from the accessibility tree and lose the values) and the form MUST take `aria-busy="true"` |
| **error** | **Applicable and entirely unimplemented — the highest-priority form gap.** Required: `aria-invalid="true"` on the field; `aria-describedby` pointing at a message element; the message rendered below the field in `t-12`, prefixed with a `⚠` glyph so colour is not the only channel (SC 1.4.1); `border-color` set to a danger token; focus moved to the first invalid field on submit. Both forms today `return` silently when a required value is missing (`script.js:325`, `pricing.html:309`) — the user presses submit and nothing whatsoever happens. That is a failure of SC 3.3.1 (Error Identification) and SC 3.3.3 (Error Suggestion) |

**Token gap.** There is no danger token. `tokens.css` MUST gain `--danger` and
`--danger-soft` in both themes before error states are implemented, and the light value
MUST be dark enough to clear 4.5:1 on `#FFFFFF` — a mid-red such as `#B3261E` (5.51:1 on
white) rather than a saturated `#EF4444` (3.76:1). Do not add it to a component sheet.

#### 3.4.4 Tokens consumed

`--surface-3` · `--field-border` · `--accent` · `--accent-soft` · `--text` / `--text-2` /
`--text-3` · `--r-sm` · type `t-12` label / `t-14` value · padding `12px` · motion 180ms.

#### 3.4.5 Responsive

| Width | Behaviour |
|---|---|
| 320px | All fields 1-up. `.f2` MUST collapse to one column here — it does not today and its two 12px-padded inputs plus a 14px gap leave ~130px per field |
| 375px | 1-up |
| 768px | `.f-row` becomes `1fr 1fr` |
| 1024px | `.contact-grid` becomes `.8fr 1.2fr`; the form takes the wider track |
| 1280px | Form capped by the 1180px container; fields MUST NOT exceed `640px` measure |

Inputs MUST be `width: 100%` with `box-sizing: border-box` (both ship). A field MUST NOT
carry a fixed pixel width.

#### 3.4.6 Long content, overflow, empty

- `<textarea>` MUST allow vertical resize and MUST NOT allow horizontal.
- Long unbroken input (a pasted URL) MUST scroll inside the field, never widen it. This is
  automatic for `input`; a `textarea` MUST also carry `overflow-wrap: anywhere`.
- Labels MUST wrap to two lines rather than truncate. "What would you like to fix?" →
  "Apa yang ingin Anda perbaiki?" needs the room.
- **Empty:** an empty optional field is a valid resting state and MUST NOT be styled as an
  error. `#fCompany` and `#sCompany` are optional and MUST NOT carry `required`.
- Submitting an empty required form MUST produce field-level errors, never silence.

#### 3.4.7 Keyboard, pointer, touch

- Every field MUST have a programmatically associated label. `landing/index.html` uses
  `<label for>` correctly. **`landing/pricing.html:219-224` uses bare `<label>` elements
  with no `for` and inputs with no `aria-label`** — the scoping form's fields are
  effectively unlabelled to a screen reader. This MUST be fixed; it is a straight
  SC 1.3.1 / SC 4.1.2 failure on the page whose entire purpose is lead capture.
- Tab order MUST be DOM order. No `tabindex` above 0.
- Enter in a single-line input MUST submit the form (native behaviour; do not intercept).
- Inputs MUST carry correct `type` and `autocomplete`: `type="email"` +
  `autocomplete="email"`, `autocomplete="name"`, `autocomplete="organization"`. Only
  `type` is set today; `autocomplete` MUST be added (SC 1.3.5).
- Touch: field height MUST be ≥44px (12px padding + 14px/1.6 line = 46px ✓). Font-size
  MUST be ≥16px on iOS to prevent focus zoom — **14.5px today, so iOS Safari zooms on
  focus**; this MUST be raised to `t-16` on the input, which also puts it back on the ramp.

#### 3.4.8 Themes

| | Light | Dark |
|---|---|---|
| Value on fill | `#0A0A0A` on `#F6F7F8` = **18.46:1** | `#F2F2F2` on `#1E1E21` = **14.85:1** |
| Placeholder on fill | `#6E7276` on `#F6F7F8` = **4.52:1** ✓ | `#828289` on `#1E1E21` = **4.36:1** ✗ |
| Label on card | `#5F6165` on `#FFFFFF` = **6.20:1** | `#8F8F94` on `#101012` = **5.91:1** |
| Border vs card (outer edge) | `#8E9294` on `#FFFFFF` = **3.14:1** ✓ | `#83838A` on `#101012` = **5.05:1** ✓ |
| Border vs own fill (inner edge) | `#8E9294` on `#F6F7F8` = **2.93:1** | `#83838A` on `#1E1E21` = **4.42:1** |
| Focus border vs card | `#1E7A4C` on `#FFFFFF` = **5.33:1** | `#57D496` on `#101012` = **10.19:1** |
| Focus border vs own fill | `#1E7A4C` on `#F6F7F8` = **4.96:1** | `#57D496` on `#1E1E21` = **8.92:1** |

Three consequences, all testable:

1. **Dark placeholders fail.** `--text-3` on `--surface-3` measures **4.36:1**; SC 1.4.3
   requires 4.5:1. Placeholders MUST use `--text-2` in dark (`#8F8F94` on `#1E1E21`), or
   `--text-3` dark MUST be lightened. Do not lighten it in a component sheet.
2. **Fields MUST sit on `--surface`, never on `--bg-2`.** The light field border clears
   3:1 on its *outer* edge against the white card (**3.14:1**) but not on its inner edge
   against its own `#F6F7F8` fill (**2.93:1**). Because `--surface-3` and `--bg-2` are the
   same colour in light, a field placed directly on an `.alt` band would measure **2.93:1**
   on *both* edges and fail SC 1.4.11 outright. Both shipped forms sit on a `--surface`
   card and pass — with 0.14 of margin. Any redesign that removes the card removes the
   pass.
3. **`--border` is not a field border.** `landing/pricing.html:27` styles its inputs with
   `border: 1px solid var(--border)` — **1.26:1** on the white card. The scoping form's
   fields therefore fail SC 1.4.11 today while the landing contact form passes. Pricing
   MUST switch to `--field-border`.

---

### 3.5 Product console

**Selectors:** `.console` · `.console-bar` · `.console-body` · `table.pl` ·
`table.pl thead th` · `table.pl tbody td` · `td.ent` · `td.elim` · `tfoot td` ·
`.console-note` · `.console-pill` · `.console-band` · `.console-grid` · `.hero-console`

This is the site's only depiction of the software. It is rendered in markup, not as a
screenshot, so it stays sharp at any size, follows the theme, costs no image weight and
cannot go stale. That decision is load-bearing and MUST NOT be reversed to "just use a PNG".

#### 3.5.1 Anatomy

```
┌─ --r-lg, 1px --border, overflow:hidden, --shadow ──────────────┐
│ ● ● ●  MASAGI-HV — Consolidated P&L · FY2026    ← --surface-2  │ chrome bar
├────────────────────────────────────────────────────────────────┤
│ ENTITY            REVENUE      COGS   GROSS PROFIT  ← thead     │
│ PT …                18.4 M    11.2 M        7.2 M              │ tbody
│ Intercompany elim  (5.2 M)   (5.2 M)            —  ← --accent  │
├────────────────────────────────────────────────────────────────┤
│ Group               46.1 M    28.9 M       17.2 M  ← tfoot 700 │
├────────────────────────────────────────────────────────────────┤
│ [Illustration]  Representative figures in IDR…                 │ note
└────────────────────────────────────────────────────────────────┘
```

**The `Illustration` pill and the disclaimer are not decoration and MUST NOT be removed.**
The figures are invented. A finance product showing invented numbers without saying so is
fabricated evidence, which the system prohibits outright (§6.2).

#### 3.5.2 Variants

| Variant | Where | Difference |
|---|---|---|
| Hero console | `.hero-console` inside `.hero-grid` | carries `--shadow`; the page's first paint |
| Band console | `.console` inside `.console-band` | on `--bg-2` with hairline band edges |
| ≤620px console | both | COGS column removed, entity names wrap, type steps down |

#### 3.5.3 States

| State | Treatment |
|---|---|
| **default** | `--surface` panel, `--border`, `--r-lg`; chrome bar `--surface-2`; thead `--text-3` uppercase over a `--border` rule; tbody `--text-2` over `--border-soft` rules; `td.ent` `--text` weight 500; `td.elim` `--accent`; tfoot `--text` weight 700 over a `--border` rule |
| **hover** | `table.pl tbody tr:hover td { background: var(--surface-2) }` — a row-reading aid only. It MUST NOT imply the row is clickable, so no cursor change, no border change, no lift |
| **focus-visible** | **Applicable to the scroll container only.** When `.console-body` scrolls horizontally it MUST be keyboard-reachable — `tabindex="0"` plus `role="group"` and an `aria-label`, per SC 2.1.1: a scrollable region that only a mouse or finger can pan is a keyboard trap by omission. Below 620px the current design removes the overflow entirely, so this applies only in the 620–940px window. **Not implemented** |
| **active** | **Not applicable.** No cell, row or header is actionable. The console is a picture of the product, not the product |
| **disabled** | **Not applicable.** Nothing here can be turned off |
| **loading** | **Not applicable.** The console is static markup in the initial HTML — that is the point. It MUST NOT be made to depend on a fetch. `script.js:249-254` may hide it in favour of a CMS carousel, but only when that carousel actually carries media, and the console remains in the DOM |
| **error** | **Not applicable.** Static markup cannot fail. If the console is ever wired to live data, a failed load MUST fall back to these illustrative figures with the pill intact, never to an empty table |

#### 3.5.4 Tokens consumed

`--surface` · `--surface-2` · `--border` · `--border-soft` · `--accent` · `--accent-soft` ·
`--accent-line` · `--text` / `--text-2` / `--text-3` · `--r-lg` · `--pill` · `--shadow` ·
`font-variant-numeric: tabular-nums` · monospace stack for the chrome-bar caption only.

Type: thead `t-12` (currently 10.5px — must move to the ramp), tbody `t-14`, tfoot `t-14`
weight 700, note `t-12`, pill `t-12`.

#### 3.5.5 Responsive

The consolidated P&L is the one place where responsive behaviour is a *content* decision,
not a layout one. The section headline promises "one number you can defend"; if the Group
total is off-screen, the section is broken regardless of how the table looks.

| Width | Behaviour |
|---|---|
| 320px | 3 columns (Entity / Revenue / Gross profit). Entity names wrap, `max-width: 46%`, line-height 1.3. Type `t-12`, cell padding `8px`. Group total MUST be visible without scrolling |
| 375px | Identical. This is the width where sticky-first-column plus reduced type still left the Group total ~86px past the edge — dropping the COGS column is what fixed it, and the fix MUST be re-verified on any table change |
| 768px | Still 3 columns below 620px is passed, so at 768px all 4 columns show; `.console-grid` still 1 column |
| 1024px | `.console-grid` is `.82fr 1.18fr`, copy left, console right (`>940px`) |
| 1280px | Container capped; console keeps `max-width: 100%` |

Two structural rules that this component paid for in defects:

- `.hero-grid > *` and `.console-grid > *` MUST keep `min-width: 0`. Without it the grid
  child refuses to shrink below the table's ~416px intrinsic width and drags the whole
  page wider than the viewport.
- `html, body { overflow-x: hidden }` is a **safety net, not the fix.** It masks overflow
  instead of resolving it, and it silently hides content that has escaped the viewport.
  The `min-width: 0` rules are the fix. Any new overflow MUST be resolved at its source,
  and the presence of `overflow-x: hidden` MUST NOT be treated as evidence that a layout
  is correct.

#### 3.5.6 Long content, overflow, empty

- **`white-space: nowrap` MUST NOT be applied to the entity column.** Indonesian entity
  names run long — "PT Bahtera Logistik Nusantara" is 29 characters — and holding them on
  one line pushed the table 36px past its box and took the Group total with it. Figures
  keep `nowrap`; names wrap. This is the general rule: **nowrap belongs on numbers, never
  on names.**
- Where horizontal scroll survives (620–940px), `.console-body` MUST keep `overflow-x: auto`,
  the first column MUST be `position: sticky; left: 0` with an opaque `--surface`
  background (including on `tfoot`, or the total scrolls out from under its own label),
  and a 26px gradient scroll affordance MUST be visible at the right edge. All three ship.
- The gradient affordance MUST be `pointer-events: none` or it eats taps on the last column.
- Currency and scale MUST be stated once, in the note ("Representative figures in IDR"),
  never repeated per cell.
- **Empty:** not applicable — the table is authored, never empty. If it is ever wired to
  live data, a zero-entity group MUST render the header row plus a single full-width cell
  carrying a bilingual "No entities configured" string, and MUST NOT render a bare `tfoot`.

#### 3.5.7 Keyboard, pointer, touch

- The console wrapper carries `role="img"` with an `aria-label`. That is a deliberate,
  defensible choice: it presents the illustration as a single object rather than making a
  screen-reader user walk a fake table. **But `role="img"` removes the table semantics
  entirely, so the label is the only thing assistive tech receives, and the current label
  does not contain the group figure** — the one number the section promises. The label
  MUST be rewritten to carry the claim, in both languages, e.g. *"Illustration: MASAGI-HV
  consolidated profit and loss. Five entities, intercompany eliminations of 5.2 M, group
  revenue 46.1 M and group gross profit 17.2 M. Representative figures in IDR, not a
  client's accounts."*
- If the `role="img"` approach is ever abandoned in favour of a real table, the table MUST
  gain `<caption>`, `scope="col"` on every `th`, and `scope="row"` on the entity cells.
- `td.elim` uses `--accent` green for the elimination row. Colour MUST NOT be the only
  signal (SC 1.4.1) — the accounting parentheses `(5.2 M)` are the non-colour cue and MUST
  be retained.
- Touch: horizontal panning must not fight vertical page scroll. `.console-body` uses
  native `overflow-x` and MUST NOT intercept touch events.

#### 3.5.8 Themes

| | Light | Dark |
|---|---|---|
| Chrome-bar caption | `#6E7276` on `#F2F4F4` = **4.39:1** ✗ | `#828289` on `#18181B` = **4.64:1** ✓ |
| Column header | `#6E7276` on `#FFFFFF` = **4.85:1** | `#828289` on `#101012` = **4.98:1** |
| Body figure | `#5F6165` on `#FFFFFF` = **6.20:1** | `#8F8F94` on `#101012` = **5.91:1** |
| Body figure, row hovered | `#5F6165` on `#F2F4F4` = **5.62:1** | `#8F8F94` on `#18181B` = **5.50:1** |
| Entity name | `#0A0A0A` on `#FFFFFF` = **19.80:1** | `#F2F2F2` on `#101012` = **16.98:1** |
| Elimination row | `#1E7A4C` on `#FFFFFF` = **5.33:1** | `#57D496` on `#101012` = **10.19:1** |
| Elimination, row hovered | `#1E7A4C` on `#F2F4F4` = **4.82:1** | `#57D496` on `#18181B` = **9.50:1** |
| Group total | `#0A0A0A` on `#FFFFFF` = **19.80:1** | `#F2F2F2` on `#101012` = **16.98:1** |
| `.console-note` | `#6E7276` on `#FFFFFF` = **4.85:1** | `#828289` on `#101012` = **4.98:1** |
| `.console-pill` | `#1E7A4C` on `#EBF3EF` = **4.72:1** | `#57D496` on `#17241F` = **8.61:1** |

The chrome-bar caption is a live failure: `--text-3` on `--surface-2` measures **4.39:1**
in light at 12px. It MUST move to `--text-2` (**5.62:1** on `#F2F4F4`).

---

### 3.6 Trust strip

**Selectors:** `.trust` · `.trust-label` · `.trust-logos` · `.logo-tile` · `.logo-tile img`

#### 3.6.1 Anatomy

```
        TRUSTED BY COMPANIES ACROSS SOUTHEAST ASIA     ← t-12 / .16em / --text-3
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │ [logo] │ │ [logo] │ │ [logo] │ │ [logo] │ │ [logo] │ │ [logo] │  62px min
   └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
   --surface fill, --border, --r-md · img height:30px, max-width:128px
```

The strip sits between the hero and the first section with `--border-soft` edges on both
sides. It is a claim about customers and is governed by §6.2.

#### 3.6.2 Variants

Two, and only two — by theme, not by content:

| Theme | Rest | Hover |
|---|---|---|
| Light | `filter: grayscale(1); opacity: .68` | `grayscale(0); opacity: 1` |
| Dark | `filter: brightness(0) invert(1); opacity: .62` | `filter: none; opacity: 1` |

Six third-party marks in six palettes rendered raw make the strip louder than the headline,
and the dark-inked ones (United Oil, Evalube) disappear on a dark canvas. Neutral at rest,
true colour on hover. The dark treatment is a *knockout to white*, not a grayscale — a
grayscale dark logo stays dark.

#### 3.6.3 States

| State | Treatment |
|---|---|
| **default** | tile `--surface` + `--border` + `--r-md`; image neutralised per theme |
| **hover** | tile `border-color: --accent-line`, image returns to true colour at full opacity, 200ms |
| **focus-visible** | **Not applicable today** — the tiles are `<span>`s, not links, and MUST stay that way unless there is a real destination. If they ever link to a case study, each MUST become an `<a>` with the global focus ring and an accessible name naming the *company*, not the file |
| **active** | **Not applicable** — not interactive |
| **disabled** | **Not applicable** — a customer is either shown or not shown; there is no "off" logo |
| **loading** | **Applicable.** `.logo-tile img` MUST keep an explicit `height: 30px` and a `min-width: 40px`. This is not styling: with `height: auto` these images have no intrinsic size before they load, collapse to 0×0, and **a 0×0 lazily-loaded image never enters the viewport and therefore never loads at all**. If `loading="lazy"` is added (it is not present today; the images carry `decoding="async"` only), the explicit height becomes mandatory rather than merely correct |
| **error** | **Applicable, and the handling is a prohibition.** A logo that 404s MUST fail silently — broken-image glyph or nothing. There MUST NOT be an `onerror` handler that substitutes a text wordmark. A generated wordmark is a fabricated customer mark; it also renders identically whether the company is a customer or the file simply moved, which destroys the strip's evidentiary value. `.logo-word` in `styles.css:314-316` and `theme-swiper.css:249` is dead CSS from exactly that defect and MUST be deleted |

#### 3.6.4 Tokens consumed

`--bg` · `--border-soft` · `--surface` · `--border` · `--accent-line` · `--text-3` ·
`--r-md` · type `t-12` weight 600 letter-spacing .16em uppercase · motion 200ms.

#### 3.6.5 Responsive

| Width | Behaviour |
|---|---|
| 320px | `flex-wrap: wrap`, `justify-content: center`, gap 16px. Tiles MUST shrink — `width: 150px` from `styles.css:309` gives 2-up with 22px gutters and no room; tiles MUST become `flex: 0 1 auto` with `min-width: 120px` |
| 375px | 2-up |
| 768px | 3-up |
| 1024px | 6-up single row |
| 1280px | 6-up, wider gaps |

The strip MUST NOT become a marquee or an auto-scrolling carousel. Motion under a trust
claim reads as concealment, and it fails SC 2.2.2 unless paused.

#### 3.6.6 Long content, overflow, empty

- `max-width: 128px` plus `object-fit: contain` means a wide wordmark scales down rather
  than stretching its tile. `min-width: 40px` stops a narrow square mark from collapsing.
- **Empty:** with fewer than three logos the strip MUST NOT render at all. Two tiles under
  "Trusted by companies across Southeast Asia" reads worse than no strip. The label and
  the tiles MUST be shown or hidden together.
- The `alt` text MUST be the company name exactly (`alt="Shell"`), never "logo",
  "client logo" or a filename.

#### 3.6.7 Keyboard, pointer, touch

- Not interactive: no tab stops, no `tabindex`, no cursor change.
- The colour-on-hover reveal is pointer-only. On touch the logos stay neutralised, which
  is acceptable **because the `alt` text carries the identity** — the reveal is decoration,
  not information. Any future strip that carries information in hover fails on touch.

#### 3.6.8 Themes

| | Light | Dark |
|---|---|---|
| Strip label | `#6E7276` on `#FFFFFF` = **4.85:1** ✓ (12px) | `#828289` on `#0A0A0A` = **5.19:1** ✓ |
| Tile border | `#E3E6E6` on `#FFFFFF` = **1.26:1** | `#2C2C30` on `#0A0A0A` = **1.42:1** |
| Logo mark | grayscale at .68 opacity | knocked out to white at .62 opacity |

Tile borders are decorative and the low ratios are acceptable: the tiles are not controls,
and SC 1.4.11 exempts them. Logotypes are exempt from SC 1.4.3 and SC 1.4.11 by the
success criteria themselves, so the neutralised marks do not need to clear a ratio — but
they MUST remain *identifiable*, which is why the dark theme inverts rather than dims.

---

### 3.7 Section rhythm

**Selectors:** `.section` · `.section.alt` · `.sec-head` · `.sec-head h2` · `.sec-head .lead` ·
`.eyebrow` · `.eyebrow::before` · `.eyebrow-green` · `.wrap`

#### 3.7.1 Anatomy

```
╔═ --border-soft hairline (alt only) ═══════════════════╗
║                                                        ║
║   ▬▬▬ EYEBROW           t-12 / 600 / .14em / --accent  ║
║   Section heading       t-30…t-38 / 600 / -0.022em     ║
║   Lead paragraph        t-18 / --text-2 / max 62ch     ║
║                                                        ║
║   [ content grid ]                                     ║
║                                                        ║
╚═ --border-soft hairline (alt only) ═══════════════════╝
```

Sections alternate `--bg` and `--bg-2`. Because those separate by only **1.07:1** (light)
and **1.08:1** (dark), the band alone is not perceivable — the `--border-soft` hairlines on
`.section.alt` are what actually create the rhythm and MUST NOT be removed as "redundant
with the background". This is the specific thing that broke when the palette moved from
navy to near-black: banding that a saturated palette got for free had to be drawn.

#### 3.7.2 Variants

| Variant | Background | Edges |
|---|---|---|
| `.section` | `--bg` | none |
| `.section.alt` | `--bg-2` | `--border-soft` top and bottom |
| `.console-band` | `--bg-2` | `--border-soft` top and bottom |
| `.case` | `--bg-2` + a `--accent-soft` radial at 50% 0% | inherits |
| `.trust` | `--bg` | `--border-soft` top and bottom |

Two `.alt` sections MUST NOT be adjacent — the alternation is the rhythm. The current
order (hero → trust → about → **alt** services → how → case → media → **alt** contact) is
correct.

#### 3.7.3 States

| State | Treatment |
|---|---|
| **default** | padding 64/80/104px by breakpoint, `.sec-head` margin-bottom 44px |
| **hover** | **Not applicable.** A section is a layout container, not a control |
| **focus-visible** | **Not applicable to the section itself**, but each `<section>` with an `id` is a same-page navigation target and MUST have an accessible name — `aria-labelledby` pointing at its `h2` (or `aria-label`), so a screen-reader user landing via `#services` hears where they are. Not implemented on any section today |
| **active** | Not applicable |
| **disabled** | Not applicable |
| **loading** | **Applicable in one form only:** `.reveal` starts at `opacity: 0; translateY(26px)` and an IntersectionObserver adds `.visible`. If the observer is unavailable the fallback MUST add `.visible` to everything immediately (`script.js:104-107`) and `prefers-reduced-motion: reduce` MUST neutralise the whole mechanism (`styles.css:299-302`). **A content section MUST NOT depend on JavaScript to become visible.** Both escape hatches ship and MUST NOT be removed |
| **error** | Not applicable — sections are authored markup |

#### 3.7.4 Tokens consumed

`--bg` · `--bg-2` · `--border-soft` · `--accent` · `--text` · `--text-2` · type `t-12`
eyebrow / `t-30`–`t-38` heading / `t-18` lead · spacing 64/80/104 section, 44 head,
20 gutter · motion 600ms reveal.

The eyebrow rule (`.eyebrow::before`) is a `30×3px` `--accent` bar. It MUST be
`aria-hidden` by construction (it is a `::before`, so it already is) and MUST NOT be the
only marker of a section start.

#### 3.7.5 Responsive

| Width | Section padding | `.sec-head` margin | Gutter | `h2` |
|---|---|---|---|---|
| 320px | 64px | 32px | 20px | 30px |
| 375px | 64px | 32px | 20px | 30px |
| 768px | 80px | 44px | 20px | clamp → ~34px |
| 1024px | 104px | 44px | 20px | 38px |
| 1280px | 104px | 44px | 20px (container capped at 1180px) | 38px |

`.wrap` MUST be `max-width: 1180px; margin: 0 auto; padding: 0 20px`. The blog uses 1120px
and the landing 1180px; that 60px difference is visible across a subdomain hop and SHOULD
be unified on 1180px.

#### 3.7.6 Long content, overflow, empty

- `.lead` MUST cap at `62ch`. An ID lead runs 8–12% longer than its EN source
  ("Dibangun di Indonesia…" +7.7%, hero sub +11.7%), and an uncapped measure at 1280px
  produces a 120-character line.
- Headings MUST wrap. `h2` MUST NOT use `text-overflow: ellipsis`.
- A section MUST NOT set a fixed `height`. `.hero` was `height: 100svh; min-height: 560px`
  and that forced the product below the fold; it is now `height: auto; min-height: 0` and
  MUST stay that way.
- **Empty:** a section whose content collection is empty MUST NOT render its `.sec-head`
  alone. Head and content are shown or hidden together — an eyebrow, a heading and a lead
  above nothing reads as a broken page.
- Every section MUST use `.wrap`; content MUST NOT touch the viewport edge at any width.

#### 3.7.7 Keyboard, pointer, touch

- `html { scroll-behavior: smooth }` MUST be disabled under `prefers-reduced-motion: reduce`
  (`styles.css:301`).
- Same-page anchors MUST land with the target's heading visible under the 72px fixed
  navbar. `scroll-margin-top: 88px` MUST be set on every `section[id]` — it is not today,
  so `#about`, `#services`, `#how`, `#media` and `#contact` all land with their heading
  under the navbar. This is a straight SC 2.4.11 (Focus Not Obscured) risk as soon as those
  anchors receive focus.
- Sections are not interactive; no tab stops, no pointer states.

#### 3.7.8 Themes

| | Light | Dark |
|---|---|---|
| `h2` | `#0A0A0A` on `#FFFFFF` = **19.80:1** / on `#F6F7F8` = **18.46:1** | `#F2F2F2` on `#0A0A0A` = **17.68:1** / on `#141417` = **16.42:1** |
| `.lead` | `#5F6165` on `#FFFFFF` = **6.20:1** / on `#F6F7F8` = **5.78:1** | `#8F8F94` on `#0A0A0A` = **6.15:1** / on `#141417` = **5.71:1** |
| `.eyebrow` (12px) | `#1E7A4C` on `#FFFFFF` = **5.33:1** / on `#F6F7F8` = **4.96:1** | `#57D496` on `#0A0A0A` = **10.62:1** / on `#141417` = **9.86:1** |
| Band hairline | composite `#EBEBEB` vs `#FFFFFF` = **1.19:1** | composite `#1B1B1B` vs `#0A0A0A` = **1.15:1** |

The hairline ratios are low by design — a section divider is decorative structure, not a
UI component boundary, and SC 1.4.11 does not apply. It is nonetheless the *only* thing
separating the bands, so it MUST NOT be softened further.

`.eyebrow-green` hardcodes `#1E7A4C` in `styles.css:327-328` and is only saved by
`theme-swiper.css:24` winning on load order at equal specificity. In dark, `#1E7A4C` on
`#0A0A0A` is **3.72:1** — a fail for 12px text. The hardcoded rule MUST be deleted rather
than left to load order (§6.1).

---

## 4. Accessibility requirements and testable acceptance criteria

Target: **WCAG 2.2 Level AA**. Every criterion below names the SC by number, states the
exact colour pair where contrast is involved, and can be checked by a developer without
judgement calls.

### 4.1 Contrast

| ID | Criterion | SC | Test |
|---|---|---|---|
| A-1 | Body prose ≥4.5:1 | 1.4.3 | `--text-2` on `--bg`: **6.20:1** light, **6.15:1** dark. On `--bg-2`: **5.78:1** / **5.71:1**. Pass |
| A-2 | Metadata ≥4.5:1 | 1.4.3 | `--text-3` on `--bg`: **4.85:1** / **5.19:1**. Pass. On `--surface-2`: **4.39:1** light — **FAIL**, must move to `--text-2` (5.62:1) |
| A-3 | Placeholders ≥4.5:1 | 1.4.3 | `--text-3` on `--surface-3`: **4.52:1** light pass, **4.36:1** dark **FAIL** — dark must use `--text-2` |
| A-4 | Accent text ≥4.5:1 | 1.4.3 | `--accent` on `--bg`: **5.33:1** / **10.62:1**. On `--accent-soft` over `--surface`: **4.72:1** / **8.61:1**. Over `--bg-2`: **4.42:1** — **FAIL**, chips must sit on `--surface` |
| A-5 | Ink on accent fill ≥4.5:1 | 1.4.3 | `--accent-ink` on `--accent`: **5.33:1** / **10.13:1**. Any literal `#fff` on `--accent` is **1.86:1** in dark — **FAIL** (`.mobile-login`) |
| A-6 | `--accent-2` never used as text on light | 1.4.3 | `#31A96A` on `#FFFFFF` = **2.99:1**. `grep -n '31A96A' landing/*.css landing/*.html` must return no rule setting `color` on a light surface — `pricing.html:79` currently does |
| A-7 | Large text ≥3:1 | 1.4.3 | `.stat .n` at 38px/700: `--accent` on `--bg` = **5.33:1** / **10.62:1**. Pass with margin |
| A-8 | Control boundaries ≥3:1 | 1.4.11 | `--field-border` on `--bg`: **3.14:1** / **5.26:1**. `--border` is **1.26:1** / **1.42:1** and must never bound a control. Ghost buttons and pricing inputs currently use `--border` — **FAIL** |
| A-9 | Focus indicator ≥3:1 | 1.4.11 | Ring `--accent` at 2px offset against canvas: **5.33:1** / **10.62:1**. The offset is required; without it the ring on `.btn-accent` is accent-on-accent |
| A-10 | Icon-only control glyph ≥3:1 | 1.4.11 | `.theme-btn` glyph `--text-2` on `--bg`: **6.20:1** / **6.15:1**. `.hamburger` bars `--text`: **19.80:1** / **17.68:1**. Pass |
| A-11 | No text under 12px | — (ramp) | `grep -nE 'font-size:\s*(1[01](\.\d)?|[0-9](\.\d)?)px' landing/*.css` returns nothing |

### 4.2 Keyboard and focus

| ID | Criterion | SC | Test |
|---|---|---|---|
| A-12 | Every interactive element reachable by Tab | 2.1.1 | Tab from the top of each page; every button, link, field and the console scroll region receives focus |
| A-13 | No keyboard trap | 2.1.2 | Tab forward and backward through the open mobile sheet and out |
| A-14 | Visible focus on every focusable element | 2.4.7 | The global `:focus-visible` rule must be present on all three surfaces. **Currently landing only** — FAIL on pricing and blog |
| A-15 | Focus not obscured by the fixed navbar | 2.4.11 | Tab to the first control inside each `section[id]` after following its anchor; the focused element must be fully visible. Requires `scroll-margin-top: 88px` — **not present, FAIL** |
| A-16 | Escape closes the mobile sheet and restores focus | 2.1.1 / 2.4.3 | Open sheet, press Escape, sheet closes and focus returns to `.hamburger` — **not implemented, FAIL** |
| A-17 | Focus order matches visual order | 2.4.3 | No positive `tabindex` anywhere: `grep -n 'tabindex="[1-9]' ` returns nothing |
| A-18 | Scrollable regions are keyboard-operable | 2.1.1 | `.console-body` between 620px and 940px must have `tabindex="0"`, `role="group"` and an `aria-label` — **not implemented, FAIL** |

### 4.3 Names, roles, values

| ID | Criterion | SC | Test |
|---|---|---|---|
| A-19 | Every field has a programmatic label | 1.3.1 / 4.1.2 | Every `input`/`textarea` has a `<label for>` or `aria-label`. `pricing.html:219-224` — **FAIL** |
| A-20 | Toggle state is exposed | 4.1.2 | `.lang-btn` and `.theme-btn` carry `aria-pressed` reflecting `.on` / current theme — **not implemented, FAIL** |
| A-21 | Current page/category is exposed | 4.1.2 | `.cats a.on` and the active nav link carry `aria-current="page"` — **not implemented, FAIL** |
| A-22 | Disclosure state is exposed and wired | 4.1.2 | `.hamburger` has `aria-expanded` (pass) **and** `aria-controls="menu"` (FAIL) |
| A-23 | Section landmarks are named | 1.3.1 | Every `section[id]` has `aria-labelledby` pointing at its heading — **not implemented, FAIL** |
| A-24 | Decorative graphics are hidden | 1.1.1 | Brand SVGs carry `aria-hidden="true"` (pass); `::before` glyphs are inherently hidden (pass) |
| A-25 | The console's accessible name carries its claim | 1.1.1 | The `role="img"` label names the entity count, the elimination and the group total, in EN and ID — **currently incomplete, FAIL** |

### 4.4 Forms and errors

| ID | Criterion | SC | Test |
|---|---|---|---|
| A-26 | Errors are identified in text | 3.3.1 | Submit both forms empty; each invalid field shows a text message and `aria-invalid="true"` — **currently silent, FAIL** |
| A-27 | Errors suggest a correction | 3.3.3 | The message says what is expected ("Enter an email address like you@company.co.id"), not "Invalid" |
| A-28 | Error is not colour-only | 1.4.1 | The message carries a glyph and text; removing all colour still identifies the field |
| A-29 | Field purpose is programmatic | 1.3.5 | `autocomplete` on name, email, organization — **not present, FAIL** |
| A-30 | Redundant entry avoided | 3.3.7 | No field asks for information already provided in the same flow. Pass — both forms are single-step |
| A-31 | Submit does not trigger an unexpected context change | 3.2.2 | The `.f-note` / `.note` text states that submit opens the user's mail client, in both languages. Pass |

### 4.5 Motion, targets, colour independence

| ID | Criterion | SC | Test |
|---|---|---|---|
| A-32 | Reduced motion respected | 2.3.3 | With `prefers-reduced-motion: reduce`: `.reveal` is visible and untransitioned, smooth scroll is off (pass), **Swiper autoplay is stopped (FAIL — not implemented)** |
| A-33 | Auto-advancing content is pausable | 2.2.2 | The hero carousel autoplays every 5s with no pause control — **FAIL whenever the CMS supplies media slides.** It must gain a pause control or drop autoplay |
| A-34 | Touch targets ≥24×24px (AA) | 2.5.8 | Every control measured at 320px. `.theme-btn` paints 28×28 and `.hamburger` 32×32 at that width — both clear 24px; 44px remains the internal standard |
| A-35 | Colour is never the only channel | 1.4.1 | `td.elim` green is accompanied by accounting parentheses (pass); `.lang-btn.on` fill is accompanied by `aria-pressed` once A-20 lands; `.cats a.on` by `aria-current` once A-21 lands |
| A-36 | No horizontal page scroll | 1.4.10 | At 320 / 375 / 768px, `document.documentElement.scrollWidth <= window.innerWidth` **with `overflow-x: hidden` temporarily disabled** — the hidden overflow must not be what makes this pass |

### 4.6 Language

| ID | Criterion | SC | Test |
|---|---|---|---|
| A-37 | Page language is declared and updated | 3.1.1 | `document.documentElement.lang` is `en` or `id` and changes with the toggle (pass — `script.js:31`) |
| A-38 | Inline foreign-language phrases are marked | 3.1.2 | Product names (MASAGI-HV, MASAGI-CROM) are proper nouns and exempt. English terms retained inside ID copy ("Custom", "Onboarding", "go-live") MUST carry `lang="en"` — **not marked, FAIL** |

---

## 5. Content and tone standards

### 5.1 Voice

Concise, confident, implementation-focused. Plain English and plain Bahasa. No enterprise
filler. Every claim must be backed by something on the page.

| Do | Don't |
|---|---|
| "Five companies. One number you can defend." | "Unlock synergies across your organisation" |
| "Closing the books went from seven days to two." | "Dramatically accelerate your close" |
| "Representative figures in IDR — not a client's accounts." | *(omitting the disclaimer)* |
| "Book a scoping call" | "Get started free" |
| "Priced to your business, not a plan tier." | "Plans from $99/mo*" |

### 5.2 CTA honesty

**A CTA MUST NOT promise something the destination does not deliver.** This is the rule
that produced the most damaging copy defect this codebase has shipped: a "Start free"
button on a page whose only offer is a custom quote. There is no free tier, no self-serve
signup and no trial — a visitor who clicks "Start free" lands on a contact form and learns
the label was false.

Checklist for any new CTA:

1. Name the next action, not the outcome. "Book a scoping call", "Get a quote",
   "Request an HV demo", "Read the case study →".
2. If the destination is a form, the label must imply a conversation.
3. If the destination is an anchor on the same page, the label must name the section.
4. Two CTAs on the same page with the same label must point at the same destination.
   `pricing.html` has two "Get a quote" links both pointing at `#scoping` — permitted, but
   each SHOULD carry an `aria-label` naming its product ("Get a quote for MASAGI-HV") so
   they are distinguishable out of context.

### 5.3 Evidence

- No invented logos. No placeholder wordmarks dressed as customers. No figure attributed
  to a real company that the company has not agreed to.
- Illustrative data MUST be labelled illustrative, in both languages, adjacent to the data
  and not in a footnote elsewhere on the page.
- The client story runs unattributed by role and city ("Finance Director · Multi-entity
  group · Jakarta"). That is acceptable; naming a company that has not consented is not.

### 5.4 Bilingual handling

Every string on a public surface MUST exist in both `en` and `id`. The landing and pricing
pages key off `data-i18n` / `data-i18n-ph`; the blog keys off `data-en` / `data-id`. Both
mechanisms MUST resolve every key — a missing key leaves the English in place, which is a
silent failure the QA gate has to catch (§7, G-11).

**Indonesian runs longer.** Measured against the shipped dictionaries:

| Key | EN | chars | ID | chars | Δ |
|---|---|---|---|---|---|
| `media.read` | Read more → | 11 | Baca selengkapnya → | 19 | **+73%** |
| `hero.title` | Five companies. One number you can defend. | 42 | Lima perusahaan. Satu angka yang bisa kamu pertahankan. | 63 | **+50%** |
| `console.th.rev` | Revenue | 7 | Pendapatan | 10 | **+43%** |
| `contact.form.company` | Company | 7 | Perusahaan | 10 | **+43%** |
| `getquote` (pricing) | Get a quote | 11 | Minta penawaran | 15 | **+36%** |
| `hero.cta1` | Book a scoping call | 19 | Jadwalkan sesi konsultasi | 25 | **+32%** |
| `how.s2t` | We tailor the system | 20 | Kami sesuaikan sistemnya | 24 | **+20%** |
| `console.th.entity` | Entity | 6 | Entitas | 7 | **+17%** |
| `hero.sub` | *(154 chars)* | 154 | *(172 chars)* | 172 | **+12%** |
| `about.title` | Built in Indonesia. Precise by default. | 39 | Dibangun di Indonesia. Precise by default. | 42 | **+8%** |

The system-wide ~15–20% average hides the cases that actually break layout: **short UI
strings expand the most.** A 73% expansion on an 11-character link label, and 43% on a
7-character table header, are what push a nav bar or a table past the viewport — not the
paragraphs.

**Rules**

1. Layout MUST be measured with the **Indonesian** strings, not the English. Any width,
   `min-width`, `max-width` or `ch` cap MUST be chosen against the ID string.
2. `white-space: nowrap` MUST NOT be applied to any translated string. It is permitted only
   on numerals and on the `.cats` chips, which live in a scroll container built for it.
3. Buttons and nav items MUST NOT have fixed widths. Where two must match, the grid track
   sets the width.
4. Table headers MUST be allowed to wrap. "Pendapatan" and "Laba kotor" do not fit the
   column widths that "Revenue" and "Gross profit" imply at 375px.
5. Untranslated technical terms retained inside ID copy ("Custom", "Onboarding", "go-live",
   "scoping") MUST carry `lang="en"` (SC 3.1.2).
6. Placeholders MUST be localised too, including the email example
   (`you@company.co.id` → `anda@perusahaan.co.id`). Both forms do this correctly.
7. The two dictionaries MUST have identical key sets. A key present in `en` and absent in
   `id` renders English inside an Indonesian page with no visible warning.

### 5.5 Numbers and currency

- Figures use `tabular-nums`, weight 700, and MUST be right-aligned in tables.
- Negative and contra amounts use accounting parentheses `(5.2 M)`, never a minus sign
  alone and never colour alone.
- Currency and scale are stated once per table, in its note.
- Indonesian decimal and thousands separators differ from English. Where a figure is
  rendered from data rather than authored, it MUST be formatted with
  `Intl.NumberFormat(lang === 'id' ? 'id-ID' : 'en-US')`. The console's authored figures
  are identical in both locales and are exempt.

---

## 6. Anti-patterns and prohibited implementations

Each of these is grounded in a defect this codebase actually shipped, and each carries a
detection command.

### 6.1 Declaring tokens in more than one file

`styles.css` and `tokens.css` both declared the palette, and both scoped dark as
`html[data-theme="dark"]` — equal specificity, so **load order chose the palette** and the
old navy/blue values came back on the dark theme. `styles.css:9-13` records the removal.

The same failure mode is still live at the rule level: `.section.alt` is
`background: var(--surface)` in `styles.css:191` and `background: var(--bg-2)` in
`theme-swiper.css:135`, both at specificity (0,2,0). The band exists only because
`theme-swiper.css` is linked second. Reorder the two `<link>` tags and the alternating
rhythm disappears. `.trust`, `.logo-tile`, `.logo-tile img`, `.eyebrow-green` and the
`.menu-cta` `!important` pair are in the same position.

- **Prohibited:** declaring a custom property outside `tokens.css`; relying on load order
  to resolve two equal-specificity rules for the same property.
- **Detect:** `grep -rn '^\s*--[a-z-]*:' landing/ cms/templates/ | grep -v tokens.css`
- **Fix:** delete the losing rule outright. Do not add `!important`; do not reorder links.

### 6.2 Fabricating evidence

An `onerror` handler on the trust-strip logos substituted a generated text wordmark when
an image 404'd. It rendered a plausible "customer mark" for a company whose file had simply
moved — and would have rendered one for a company that was never a customer. `.logo-word`
in `styles.css:314` and `theme-swiper.css:249` is the dead CSS left behind.

- **Prohibited:** `onerror` fallbacks that synthesise brand marks; placeholder logos;
  figures attributed to a named company; unlabelled illustrative data.
- **Detect:** `grep -rn 'onerror' landing/ cms/templates/` returns nothing.
- **Fix:** let a missing logo be missing; delete `.logo-word`.

### 6.3 Grid children without `min-width: 0`

Grid and flex items default to `min-width: auto` and refuse to shrink below their content.
The console's ~416px table therefore forced its hero column — and the entire page — wider
than a 375px viewport, and the Group total went off-screen. `theme-swiper.css:409` is the
fix; `theme-swiper.css:395` (`html, body { overflow-x: hidden }`) is the net that was
**masking** the overflow rather than resolving it.

- **Prohibited:** treating `overflow-x: hidden` as a fix; adding a table, `<pre>`, long URL
  or untruncated entity name to a grid child that has not set `min-width: 0`.
- **Detect:** in DevTools, disable `html, body { overflow-x: hidden }` and re-check
  `scrollWidth` at 320 / 375 / 768px.
- **Fix:** `min-width: 0` on the child; `max-width: 100%` on the wide element.

### 6.4 Lazy images with `height: auto`

`.logo-tile img` with `height: auto` has no intrinsic size before it loads, so it lays out
at 0×0 — and **a 0×0 image never intersects the viewport, so a lazily-loaded one never
loads at all.** The strip rendered as six empty tiles. `theme-swiper.css:320-323` fixes it
with an explicit `height: 30px` and `min-width: 40px`.

- **Prohibited:** `loading="lazy"` (or any deferred load) on an image without an explicit
  height or `aspect-ratio`.
- **Detect:** `grep -n 'loading="lazy"' landing/*.html landing/*.js cms/templates/*.html`,
  then confirm each match's CSS sets a height.
- **Fix:** explicit `height` + `object-fit: contain`, or `aspect-ratio` + `width: 100%`.

### 6.5 Raw hex in component CSS

Every hex in a component sheet is a value that will not follow the theme. Current
offenders, and their status:

| Location | Value | Status |
|---|---|---|
| `pricing.html:79` `.pcard li::before` | `#31A96A` | **Must fix** — 2.99:1 on the white card, fails SC 1.4.3 |
| `styles.css:92` `.mobile-login` | `#fff` | **Must fix** — 1.86:1 in dark, fails SC 1.4.3 |
| `styles.css:327-328` `.eyebrow-green` | `#1E7A4C` | **Must delete** — 3.72:1 in dark; survives only on load order |
| `pricing.html:52, 81, 103` | `rgba(37,99,235,.30)` | **Must delete** — a blue glow under a green button, left from the pre-MASAGI palette |
| `theme-swiper.css:78` `.btn-accent` | `rgba(87,212,150,.16)` | **Must tokenise** — light-green glow under a deep-green light-theme button |
| `pricing.html:107-116` `footer` | `#C7D2E4`, `#0A1222` | **Must tokenise** — see §6.9.7 |
| `theme-swiper.css:194-196`, `styles.css:248-250`, `cms/templates/index.html:23-26` cover gradients | brand greens | **Exempt** — decorative covers, listed here so the exemption is explicit |
| Brand SVG `<polygon fill>` | brand greens | **Exempt** — the mark is fixed in both themes by design |

- **Detect:** `grep -nE '#[0-9A-Fa-f]{3,6}|rgba?\(' landing/*.css landing/*.html cms/templates/*.html | grep -v tokens.css`

### 6.6 `white-space: nowrap` on translated strings

The entity column was held on one line by `nowrap`. Indonesian PT names are long; that
alone pushed the table 36px past its box and carried the Group total off-screen. Fixed at
`theme-swiper.css:415-419` by letting names wrap while figures keep `nowrap`.

- **Prohibited:** `nowrap` on any element carrying a `data-i18n`, `data-i18n-ph`, `data-en`
  or `data-id` attribute.
- **Detect:** `grep -n 'nowrap' landing/*.css cms/templates/*.html` and confirm each match
  is on numerals or on the `.cats` scroll strip.

### 6.7 Overriding half of a compound selector

`styles.css:288` scopes `.footer a, .footer span { color: #C7D2E4 }`. That was fine over the
old navy footer; on the light `--surface` footer it is **1.53:1**. A fix that reclaimed only
`.footer a` would have left every `<span>` in the footer illegible — including the copyright
line and the Jakarta address. `theme-swiper.css:224` reclaims **both** selectors, and
`:335-337` reclaims three more base rules (`.foot-brand .tagline`, `.footer`,
`.foot-copy, .foot-base`) that were scoped tightly enough to outrank the theme's
single-class overrides.

- **Prohibited:** reclaiming one selector out of a comma-separated group; assuming a
  single-class override outranks `.parent .child`.
- **Detect:** when overriding, `grep` the base sheet for the property and reclaim **every**
  selector in the group at matching-or-higher specificity. Then check the rendered element
  in DevTools, not the stylesheet.

### 6.8 CTAs that overpromise

Covered in §5.2. Detection is manual: for every `.btn`, `.menu-cta`, `.cta` and `.m-read`,
follow the `href` and confirm the destination delivers the label.

### 6.9 Conflicts between the skill, `tokens.css` and the shipped code

These are open discrepancies, not opinions. Each needs a decision.

**6.9.1 Recorded contrast figures that do not match computation.** Four comments in
`tokens.css` state ratios that recomputation does not reproduce. The colours are fine; the
comments are wrong and must be corrected, because they are the numbers this document and
every future review cite.

| Location | Recorded | Computed | Note |
|---|---|---|---|
| `tokens.css:32` `--text-2` light | 5.83:1 | **6.205:1** | Understated; also repeated in `SKILL.md` |
| `tokens.css:69` `--field-border` dark on `#1E1E21` | 4.02:1 | **4.417:1** | Understated |
| `tokens.css:69` `--field-border` dark on canvas | 5.28:1 | **5.259:1** | Rounding only |
| `theme-swiper.css:208` field fill vs canvas | 1.19:1 | **1.07:1** light, **1.14:1** dark | The conclusion — that the border must delimit the field — is still correct |

Note also that `tokens.css:29` records `--field-border` light as 3.14:1 "on white", which is
accurate, but the field's own fill is `#F6F7F8`, not white, and against that fill it is
**2.93:1** (§3.4.8). The comment should record both edges.

**6.9.2 `.mobile-login` is a live AA failure.** `styles.css:89-92` sets
`background: var(--accent); color: #fff !important` and nothing reclaims it. Below 1024px in
dark theme the Login label measures **1.86:1** (`#FFFFFF` on `#57D496`). This is the
compact login control — the primary conversion path on mobile. Fix: `color: var(--accent-ink)`.

**6.9.3 The declared ramp, spacing scale, geometry set and breakpoints are not what ships.**
The skill declares them; the code predates them. Migration map:

| Declared | Shipped values to migrate |
|---|---|
| Type `12·14·16·18·20·24·30·38·50` | 10.5 → 12 · 11 → 12 · 11.5 → 12 · 12.5 → 12 · 13 → 14 · 13.5 → 14 · 14.5 → 14 · 15 → 16 · 15.5 → 16 · 16.5 → 16 · 17.5 → 18 · 19 → 20 · 21 → 20 · 24 ✓ · 25 → 24 · 27 → 24 · 30 ✓ · 32 → 30 · 34 → 38 · 40 → 38 · 42 → 38 · 46 → 50 · 50 ✓ · 62 → 50 |
| Space `4·8·12·16·20·24·32·44·64·80` | 5 → 4 · 6 → 8 · 7 → 8 · 9 → 8 · 10 → 12 · 11 → 12 · 13 → 12 · 14 → 16 · 18 → 20 · 22 → 20 · 26 → 24 · 28 → 32 · 30 → 32 · 34 → 32 · 36 → 32 · 38 → 44 · 42 → 44 · 46 → 44 · 48 → 44 · 58 → 64 · 62 → 64 · 70 → 64 · 72 → 64 · 74 → 80 · 88 → 80 · 90 → 80 · 96 → 80 · 104 ✓ |
| Radius `12·20·32·999` | 2 → 12 · 5 → 12 · 6 → 12 · 7 → 12 · 10 → 12 · 11 → 12 · 12 ✓ · 14 → 20 · 16 → 20 · 50% (only for the console-bar dots, exempt) |
| Breakpoints `768·1024·1280` + three content queries | 400 → fold into 480/base · 560 → fold into the nav content query · 820 / 860 / 900 → consolidate on 860 · 940 ✓ · 1023.5 → 1024 · 1224 → 1280 |

This is a large mechanical change and MUST be done as one commit per surface, with a
visual diff at 320 / 375 / 768 / 1024 / 1280 before and after. Do not do it piecemeal —
half-migrated scales are worse than either endpoint.

**6.9.4 Carousel autoplay has no pause control.** `SWIPER_OPTS` (`script.js:55-62`) sets
`autoplay: { delay: 5000, disableOnInteraction: false }` and no `prefers-reduced-motion`
guard. When the CMS supplies slides with media the carousel replaces the static hero and
begins auto-advancing indefinitely — SC 2.2.2 and SC 2.3.3. Fix: disable autoplay entirely
under `prefers-reduced-motion: reduce`, and add a visible pause control otherwise.

**6.9.5 Two of three surfaces have no focus-visible rule.** `theme-swiper.css:268-270` is
loaded only by `landing/index.html`. `landing/pricing.html` and `cms/templates/base.html`
inherit only the UA default — and `pricing.html:26-28` sets `outline: none` on inputs and
textareas globally, restoring only a `--accent` border and a 9%-alpha halo on focus. The
focus rule MUST be moved into `tokens.css` (it is theme-level, not component-level) or
duplicated into both inline sheets.

**6.9.6 `pricing.html` is a second design system.** It reimplements buttons, nav, cards and
forms in an inline `<style>` block rather than sharing `styles.css` + `theme-swiper.css`.
Consequences already visible: form fields bounded by `--border` instead of `--field-border`
(§3.4.8), `#31A96A` checkmarks at 2.99:1 (§6.5), blue glows under green buttons,
`.f2` fixed at two columns down to 320px, unlabelled fields (A-19), no focus rule (A-14),
and `.pcard h2` used as the product name while the page's real `h1` is the pricing headline.
It SHOULD be migrated onto the shared sheets. Until then, every rule in this document
applies to it and every fix must be made twice.

**6.9.7 The pricing footer breaks in both themes.** `pricing.html:107-116` sets
`footer { background: var(--navy); color: #C7D2E4 }`, where `--navy` is aliased to
`var(--text)`. In light that yields `#C7D2E4` on `#0A0A0A` = 12.98:1 (fine) but
`.foot-copy { color: var(--text-3) }` = `#6E7276` on `#0A0A0A` = **4.08:1** at 12.5px —
below 4.5:1, SC 1.4.3. In dark, the footer background is hardcoded `#0A1222` and
`.foot-brand span { color: var(--accent-ink) }` = `#05140B` on `#0A1222` = **1.01:1** —
the MASAGI wordmark in the pricing footer is invisible in dark theme. `.foot-links a:hover`
has the same value and the same result. Fix: adopt the landing footer's treatment
(`--surface` in light, `#141417` in dark, `--text-2` body, `--text-3` base line).

**6.9.8 The hero markup is malformed.** `landing/index.html:111` is `</section` with no
closing `>`. The parser consumes the following `</div>` on line 112 as part of that end
tag, closes the hero `<section>` early, and leaves line 113's `</div>` and line 121's
`</section>` unmatched. The result is that `#heroCarousel` is a sibling of the hero section
rather than a child, and `.hero-grid` is never explicitly closed. It renders by accident.
Fix before touching hero layout, and add HTML validation to the QA gate (G-1).

---

## 7. QA checklist

Run before shipping any component. Every item is pass/fail — no judgement calls.

### Structure and tokens

- [ ] **G-1** HTML validates. No unclosed or malformed tags. *(`landing/index.html:111` currently fails.)*
- [ ] **G-2** No custom property is declared outside `tokens.css`.
      `grep -rn '^\s*--[a-z-]*:' landing/ cms/templates/ | grep -v tokens.css` → empty.
- [ ] **G-3** No raw hex or `rgba()` in component CSS except the §6.5 exemptions.
- [ ] **G-4** Every font-size is on the ramp; nothing below 12px.
- [ ] **G-5** Every padding, margin and gap is on the 4px scale.
- [ ] **G-6** Every radius is `--r-sm`, `--r-md`, `--r-lg` or `--pill`.
- [ ] **G-7** No rule wins by load order alone: for every property you overrode, the base
      sheet has no equal-specificity competitor left. Reclaim **all** selectors in a
      comma-separated group, not one.

### Layout

- [ ] **G-8** No horizontal page scroll at **320 / 375 / 768px**, verified with
      `html, body { overflow-x: hidden }` temporarily disabled.
- [ ] **G-9** Every grid and flex child that can contain wide content sets `min-width: 0`.
- [ ] **G-10** Checked at 320 / 375 / 768 / 1024 / 1280px, in **both** themes — ten screens.
- [ ] **G-11** Every image has an explicit height or `aspect-ratio`; no deferred-load image
      can lay out at 0×0.
- [ ] **G-12** No fixed `height` on a text-bearing container; no fixed `width` on a button
      or nav item.

### Language

- [ ] **G-13** Every string has an `en` and an `id` value; the two dictionaries have
      identical key sets.
- [ ] **G-14** Layout re-checked at all five widths **with Indonesian active**. Short labels
      expand most — "Read more →" → "Baca selengkapnya →" is +73%.
- [ ] **G-15** No `white-space: nowrap` on any translated string.
- [ ] **G-16** Placeholders localised, including the email example.
- [ ] **G-17** English terms retained inside ID copy carry `lang="en"`.

### States

- [ ] **G-18** All seven states specified — default, hover, focus-visible, active,
      disabled, loading, error — with a written reason for each that is not applicable.
- [ ] **G-19** No state is conveyed by colour alone.
- [ ] **G-20** No affordance lives only in `:hover` (unreachable on touch).
- [ ] **G-21** Empty state defined, bilingual, and shown/hidden together with its heading.
- [ ] **G-22** Async content has a real fallback in the initial HTML, not a skeleton;
      a failed fetch leaves the fallback intact and says nothing.

### Accessibility

- [ ] **G-23** Every text/background pair computed, not eyeballed, and recorded in the PR
      as *ratio + exact pair* — e.g. "`--text-2` `#5F6165` on `--surface` `#FFFFFF` = 6.20:1".
- [ ] **G-24** Body and metadata ≥4.5:1; large text ≥3:1 (SC 1.4.3).
- [ ] **G-25** Control boundaries and focus indicators ≥3:1 (SC 1.4.11). `--border` never
      bounds a control.
- [ ] **G-26** Tab through the whole component: every interactive element reachable, visible
      ring on each, order matches visual order (SC 2.1.1, 2.4.3, 2.4.7).
- [ ] **G-27** Escape closes anything that opens; focus returns to the trigger (SC 2.1.2).
- [ ] **G-28** Focused elements are not obscured by the fixed navbar (SC 2.4.11);
      `section[id]` carries `scroll-margin-top: 88px`.
- [ ] **G-29** Every field has a programmatic label and an `autocomplete` value
      (SC 1.3.1, 1.3.5).
- [ ] **G-30** Submitting invalid input produces a text error, `aria-invalid`, an
      `aria-describedby` link and focus on the first invalid field (SC 3.3.1, 3.3.3).
- [ ] **G-31** Toggles expose `aria-pressed`; current page/category exposes
      `aria-current="page"`; disclosures expose `aria-expanded` **and** `aria-controls`
      (SC 4.1.2).
- [ ] **G-32** Touch targets ≥24×24px, internal standard 44×44px (SC 2.5.8).
- [ ] **G-33** With `prefers-reduced-motion: reduce`: no transitions, no autoplay, no smooth
      scroll (SC 2.3.3). Auto-advancing content has a pause control (SC 2.2.2).
- [ ] **G-34** Screen-reader pass: every landmark named, every image either described or
      `aria-hidden`, no `role="img"` label that omits the claim its content makes.

### Content

- [ ] **G-35** Every CTA's destination delivers what the label promises.
- [ ] **G-36** No invented logo, wordmark, testimonial or attributed figure.
- [ ] **G-37** Illustrative data labelled illustrative, adjacent to the data, in both
      languages.
- [ ] **G-38** Asset version stamps written into the source file, not patched after deploy.

---

## Appendix — file map

| Path | Role |
|---|---|
| `landing/tokens.css` | **Single source of truth.** Served to masagi.io and blog.masagi.io |
| `landing/styles.css` | Base layout, grid, breakpoints. Pre-dates the current palette; several rules survive only because `theme-swiper.css` reclaims them |
| `landing/theme-swiper.css` | Surface treatments and reclaims. Removable by design — removing it must degrade to a plain, legible page, not a broken one |
| `landing/index.html` | Landing markup. Anti-FOUC boot at `:21` |
| `landing/pricing.html` | Pricing. Self-contained inline styles — a parallel system (§6.9.6) |
| `landing/script.js` | Theme, language, carousel, navbar, reveal, CMS fetches with fallbacks |
| `landing/translations.js` | EN/ID dictionaries for the landing |
| `cms/templates/base.html` | Blog shell. Consumes `/static/tokens.css`; own inline component styles |
| `cms/templates/index.html` | Blog index — the reference empty state (`:65-66`) |
| `docs/design-system.md` | This document |
