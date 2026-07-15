# MASAGI Digital — Landing Page

Standalone static landing page (no framework, no build step), inspired by the
YCP Solidiance aesthetic: deep navy palette, Inter typography, full-screen hero
carousel, bilingual EN/ID, and dark/light mode.

## Review it

| Launcher | What it does |
|---|---|
| **`REVIEW-LANDING.bat`** | Starts a local server at http://localhost:8040 and opens your browser (recommended) |
| **`OPEN-DIRECT.bat`** | Opens `index.html` straight from the file — no server needed |

Internet is required either way (Google Fonts + the Swiper carousel library load
from CDN).

## Files

| File | Purpose |
|---|---|
| `index.html` | The whole page — 6 sections: Home (hero carousel), About Us, Our Services, Media, Location & Contact, Footer |
| `styles.css` | Design tokens (navy `#1B2A4A`, accent `#2563EB`), dark mode via `html[data-theme="dark"]`, responsive at 768/1024/1280px |
| `script.js` | Carousel, theme + language toggles (persisted), navbar scroll effect, mobile menu, scroll-reveal, contact form |
| `translations.js` | Every visible string in `en` and `id` — edit copy here |

## Editing

- **Change text / translations** → `translations.js` (both languages in one place)
- **Add a hero slide** → copy a `<div class="swiper-slide slide sX">…</div>` block in
  `index.html` and give it a background class in `styles.css`
- **Change colors** → the `:root` / `[data-theme="dark"]` token blocks at the top of `styles.css`
- **Add a language** → copy the `en` block in `translations.js`, translate it, and add a
  `<button class="lang-btn" data-lang="xx">` in the navbar

## Deploying

Everything is static — copy the five files to any web host (nginx, GitHub Pages,
or drop into the Flask app's `app/static/` and route `/` to `index.html`).
