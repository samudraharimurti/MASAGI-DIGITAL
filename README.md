# MASAGI HV — Masagi Helicopter View

Custom-built ERP for small and medium enterprises in Indonesia & Southeast Asia,
with a public marketing site, a client access portal, and the product console.

**Precise by default.**

## Site scheme

| URL              | Page                                                           |
|------------------|----------------------------------------------------------------|
| `/`              | Marketing page (Bain-style, EN/ID + light/dark, CMS-driven hero carousel & insights) |
| `/blog/<slug>`   | Insight / news article (bilingual, from the CMS)               |
| `/admin/content` | Content Studio — edit hero carousel + insights (admins only)   |
| `/access`        | Client Access portal — account, databases, billing center      |
| `/product`       | Product landing (sign-in popup)                                |
| `/login`         | Standalone sign-in → lands on `/access`                        |
| `/databases`     | Database picker                                                |
| `/app`           | MASAGI HV console (the ERP)                                    |
| `/sitemap.xml` · `/robots.txt` | SEO endpoints, generated from CMS content        |
| `/store`         | Digital products storefront (templates, ebook, course)        |
| `/store/pay/<order>` | Checkout (DOKU sandbox simulator; swap for live DOKU)      |
| `/store/thanks`  | Post-payment page (polls webhook-confirmed status)             |
| `/downloads`     | My Downloads — customer dashboard, signed download links       |

Site content (hero video/pictures + articles) lives in `data/site_content.json` —
editable in the browser at `/admin/content`, no deploy needed.

## Store pipeline (app/store.py)

Buy → email capture → pending order → DOKU checkout → **signed webhook**
(`POST /api/store/webhook/doku`, HMAC-verified — the only place access is granted)
→ account auto-created → receipt + magic-link email → `/downloads`.
Customer data in `data/store/store.db`; private files in `data/store/files/`
(served only via signed links: 24 h / 5 uses, regenerable); mock emails in
`data/store/outbox/`. Plug in real keys via `DOKU_CLIENT_ID` / `DOKU_SECRET_KEY`
env vars — integration points are marked `# DOKU:` and `# EMAIL:` in store.py.

## Run

```powershell
cd app
pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:8010  (or double-click `start_masagi_hv.bat`)

| user    | password   | role           | access                            |
|---------|------------|----------------|-----------------------------------|
| admin   | admin123   | Admin          | full access incl. users/settings  |
| finance | finance123 | Accountant     | bookkeeping, budgets, bank import |
| viewer  | viewer123  | Viewer/Auditor | read-only                         |

Demo passwords are seed data — change them in Settings → Users before any real use.

## Data

Databases are self-contained SQLite files in `data/` (auto-created and seeded on
first start: `MASAGI-GROUP` live demo + `TEST-SERVER` sandbox). Override the
location with the `MASAGI_HV_DATA_DIR` environment variable.

## Structure

| path                    | purpose                                          |
|-------------------------|--------------------------------------------------|
| `app/server.py`         | Flask app: pages, auth, REST API, Excel endpoints|
| `app/database.py`       | schema, standard COA template, seed data         |
| `app/reports.py`        | P&L, balance sheet, trial balance, budgets, HV   |
| `app/excel_io.py`       | Excel exports / imports / templates              |
| `app/pdf_export.py`     | PDF statements                                   |
| `app/bank_import.py`    | BCA receipt / mutasi CSV / e-statement import    |
| `app/static/marketing.html` | marketing page (`/`)                        |
| `app/static/access.html`    | client access portal (`/access`)            |
| `app/static/`           | product SPA (no build step)                      |
