"""MASAGI CMS — the content system behind masagi.io.

One Flask app serves two hosts (nginx routes both to this process):

  blog.masagi.io  public, server-rendered blog: news, insights, use cases and
                  field notes, bilingual EN/ID, plus the read-only JSON feeds
                  the landing page consumes (carousel + latest posts).
  cms.masagi.io   the admin panel (/admin) — WordPress-style: dashboard, post
                  lists per type, EN/ID editor, media library, carousel editor.

Content lives in SQLite at data/cms/cms.db; uploads in data/cms/uploads.
Public reads are CORS-open (non-sensitive); every write is session-gated.
"""
import functools
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone

from flask import (Flask, abort, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir, "data", "cms"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "cms.db")
SECRET_FILE = os.path.join(DATA_DIR, ".flask_secret")

os.makedirs(UPLOAD_DIR, exist_ok=True)

# Public base URL of the blog — used for canonical links, sitemap and feed.
BLOG_BASE = os.environ.get("CMS_BLOG_BASE", "https://blog.masagi.io").rstrip("/")

MAX_UPLOAD_MB = int(os.environ.get("CMS_MAX_UPLOAD_MB", "64"))
IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "svg", "avif"}
VIDEO_EXT = {"mp4", "webm", "ogg", "mov"}
ALLOWED_EXT = IMAGE_EXT | VIDEO_EXT

# The four content types the site publishes. Order drives the admin sidebar
# and the blog's category nav.
POST_TYPES = [
    ("news",       "News",       "Berita"),
    ("insight",    "Insights",   "Wawasan"),
    ("use_case",   "Use Cases",  "Studi Kasus"),
    ("field_note", "Field Notes", "Catatan Lapangan"),
]
TYPE_KEYS = [t[0] for t in POST_TYPES]
TYPE_LABEL_EN = {t[0]: t[1] for t in POST_TYPES}
TYPE_LABEL_ID = {t[0]: t[2] for t in POST_TYPES}
# URL segment per type (/category/<slug>)
TYPE_SLUG = {"news": "news", "insight": "insights",
             "use_case": "use-cases", "field_note": "field-notes"}
SLUG_TO_TYPE = {v: k for k, v in TYPE_SLUG.items()}

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"),
            template_folder=os.path.join(BASE_DIR, "templates"))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

if os.path.exists(SECRET_FILE):
    app.secret_key = open(SECRET_FILE).read().strip()
else:
    app.secret_key = secrets.token_hex(32)
    with open(SECRET_FILE, "w") as f:
        f.write(app.secret_key)
    os.chmod(SECRET_FILE, 0o600)


# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  name TEXT DEFAULT '',
  password_hash TEXT NOT NULL,
  is_active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  type TEXT NOT NULL DEFAULT 'insight',
  status TEXT NOT NULL DEFAULT 'draft',
  title_en TEXT DEFAULT '', title_id TEXT DEFAULT '',
  excerpt_en TEXT DEFAULT '', excerpt_id TEXT DEFAULT '',
  body_en TEXT DEFAULT '', body_id TEXT DEFAULT '',
  cover_image TEXT DEFAULT '',
  author TEXT DEFAULT 'MASAGI Team',
  published_at TEXT DEFAULT '',
  created_at TEXT DEFAULT '', updated_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS slides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  position INTEGER DEFAULT 0,
  is_active INTEGER DEFAULT 1,
  media_type TEXT DEFAULT 'image',      -- image | video | none
  media_url TEXT DEFAULT '',            -- upload path, or YouTube/Vimeo/.mp4 URL
  media_side TEXT DEFAULT 'right',      -- right | left  (which side the media sits on)
  poster TEXT DEFAULT '',               -- still shown before a video plays
  eyebrow_en TEXT DEFAULT '', eyebrow_id TEXT DEFAULT '',
  title_en TEXT DEFAULT '', title_id TEXT DEFAULT '',
  sub_en TEXT DEFAULT '', sub_id TEXT DEFAULT '',
  cta_label_en TEXT DEFAULT '', cta_label_id TEXT DEFAULT '',
  cta_href TEXT DEFAULT '',
  updated_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS media (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT UNIQUE NOT NULL,
  original_name TEXT DEFAULT '',
  kind TEXT DEFAULT 'image',
  size INTEGER DEFAULT 0,
  uploaded_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT DEFAULT ''
);
"""

DEFAULT_SETTINGS = {
    "blog_title_en": "News, insights and field notes.",
    "blog_title_id": "Berita, wawasan, dan catatan lapangan.",
    "blog_lead_en": "Thinking out loud from our client work — what growing "
                    "companies in Indonesia are fixing, and how.",
    "blog_lead_id": "Berpikir bersama dari pekerjaan klien kami — apa yang sedang "
                    "dibenahi perusahaan-perusahaan yang tumbuh di Indonesia, dan "
                    "bagaimana caranya.",
}


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def _close_db(exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def today():
    return datetime.now(timezone.utc).date().isoformat()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (k, v))
    if not conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        # first-run admin; the password is meant to be changed immediately
        pw = os.environ.get("CMS_ADMIN_PASSWORD", "masagi-cms")
        conn.execute(
            "INSERT INTO users (username, name, password_hash, is_active, created_at)"
            " VALUES (?,?,?,1,?)",
            ("admin", "MASAGI Admin", generate_password_hash(pw), now()))
    if not conn.execute("SELECT 1 FROM posts LIMIT 1").fetchone():
        _seed_posts(conn)
    if not conn.execute("SELECT 1 FROM slides LIMIT 1").fetchone():
        _seed_slides(conn)
    conn.commit()
    conn.close()


def _p(text):
    """Plain paragraphs -> HTML, so seeded copy renders like editor output."""
    return "".join("<p>%s</p>" % b.strip().replace("\n", " ")
                   for b in text.split("\n\n") if b.strip())


def _seed_posts(conn):
    """The four bilingual articles migrated from the HV content studio, so
    blog.masagi.io launches with the same content the old /blog served."""
    seed = [
        {
            "slug": "introducing-masagi-hv", "type": "news",
            "title_en": "Introducing MASAGI HV: a helicopter view for growing SMEs",
            "title_id": "Memperkenalkan MASAGI HV: helicopter view untuk UKM yang tumbuh",
            "excerpt_en": "Built with Indonesian SME finance teams, MASAGI HV puts the whole "
                          "business in one live view — and takes the busywork off your people.",
            "excerpt_id": "Dibangun bersama tim keuangan UKM Indonesia, MASAGI HV menyatukan "
                          "seluruh bisnis dalam satu tampilan hidup — dan mengangkat pekerjaan "
                          "berulang dari pundak timmu.",
            "published_at": "2026-07-01",
            "body_en": "Every founder we sat with told us a version of the same story: the "
                       "business grew, and somewhere along the way they stopped being able to "
                       "see it. Sales were in one app, the bank in another, the real numbers in "
                       "someone's spreadsheet — and the truth arrived weeks after month-end.\n\n"
                       "MASAGI HV is our answer. One helicopter view of every account, entity "
                       "and rupiah, built around how Indonesian SMEs actually work: rupiah-"
                       "native, fluent in a BCA statement, comfortable with the way a real "
                       "month actually closes.\n\n"
                       "We are opening three pilot slots for growing businesses that want the "
                       "view from above. Write to hello@masagi.id and tell us how your back "
                       "office runs today — we'll show you what it looks like from up here.",
            "body_id": "Setiap founder yang kami temui menceritakan versi cerita yang sama: "
                       "bisnisnya tumbuh, dan di suatu titik mereka berhenti bisa melihatnya. "
                       "Penjualan di satu aplikasi, bank di aplikasi lain, angka sebenarnya di "
                       "spreadsheet seseorang — dan kebenaran baru tiba berminggu-minggu "
                       "setelah tutup bulan.\n\n"
                       "MASAGI HV adalah jawaban kami. Satu helicopter view untuk setiap akun, "
                       "entitas, dan rupiah, dibangun mengikuti cara UKM Indonesia benar-benar "
                       "bekerja: rupiah-native, fasih membaca mutasi BCA, dan paham bagaimana "
                       "sebuah bulan benar-benar ditutup.\n\n"
                       "Kami membuka tiga slot pilot untuk bisnis yang ingin melihat dari "
                       "atas. Tulis ke hello@masagi.id dan ceritakan bagaimana back office-mu "
                       "berjalan hari ini — kami tunjukkan seperti apa kelihatannya dari sini.",
        },
        {
            "slug": "month-end-close-seven-days-to-two", "type": "use_case",
            "title_en": "How one Jakarta group cut its month-end close from seven days to two",
            "title_id": "Bagaimana satu grup di Jakarta memangkas tutup buku dari tujuh hari jadi dua",
            "excerpt_en": "Their finance team wasn't slow — their tools were. Here's what changed "
                          "when consolidation stopped being a copy-paste job.",
            "excerpt_id": "Tim keuangannya tidak lambat — alatnya yang lambat. Ini yang berubah "
                          "saat konsolidasi berhenti jadi pekerjaan salin-tempel.",
            "published_at": "2026-06-18",
            "body_en": "When we first sat down with the group's finance manager, she wasn't "
                       "asking for software. She was asking for her evenings back.\n\n"
                       "Every month-end looked the same: five companies, five workbooks, one "
                       "very long night stitching them together by hand. Intercompany sales were "
                       "reconciled from memory. A single mistyped bank reference could throw the "
                       "whole consolidation out.\n\n"
                       "We didn't rebuild how they work — we removed the manual steps. Books "
                       "stayed per company; the group view assembled itself. Bank statements "
                       "were pasted in and booked in a couple of clicks. By the second close, "
                       "the number the board needed was ready before lunch, not after midnight.",
            "body_id": "Saat pertama kali duduk bersama manajer keuangan grup itu, dia tidak "
                       "sedang minta software. Dia minta malam-malamnya kembali.\n\n"
                       "Setiap tutup bulan sama saja: lima perusahaan, lima workbook, satu "
                       "malam panjang menjahitnya jadi satu secara manual. Penjualan antar-"
                       "perusahaan direkonsiliasi dari ingatan. Satu nomor referensi bank yang "
                       "salah ketik bisa membuat seluruh konsolidasi meleset.\n\n"
                       "Kami tidak mengubah cara mereka bekerja — kami menghapus langkah "
                       "manualnya. Pembukuan tetap per perusahaan; tampilan grup terangkai "
                       "sendiri. Mutasi bank ditempel dan terbukukan dalam beberapa klik. Di "
                       "tutup buku kedua, angka yang dibutuhkan direksi siap sebelum makan "
                       "siang — bukan lewat tengah malam.",
        },
        {
            "slug": "hidden-cost-of-spreadsheets", "type": "insight",
            "title_en": "The hidden cost of running a growing business on spreadsheets",
            "title_id": "Biaya tersembunyi menjalankan bisnis yang tumbuh di atas spreadsheet",
            "excerpt_en": "Spreadsheets feel free. The real bill arrives at month-end — in hours "
                          "lost and decisions delayed.",
            "excerpt_id": "Spreadsheet terasa gratis. Tagihan sebenarnya datang di akhir bulan "
                          "— dalam jam yang hilang dan keputusan yang tertunda.",
            "published_at": "2026-05-30",
            "body_en": "Every growing business reaches the same fork in the road. The "
                       "spreadsheet that carried you from one shop to three quietly becomes the "
                       "thing holding you back at five.\n\n"
                       "It isn't dramatic. There's no outage. Just a slow tax — a day here "
                       "reconciling the bank, an afternoon there hunting a duplicate transfer, a "
                       "number for the owner that lands a week late and half-trusted.\n\n"
                       "Knowing where the business stands should be a byproduct of doing the "
                       "books, not a second job after them. That is the whole idea behind the "
                       "helicopter view.",
            "body_id": "Setiap bisnis yang tumbuh sampai di persimpangan yang sama. "
                       "Spreadsheet yang mengantarmu dari satu toko ke tiga toko, diam-diam "
                       "menjadi penghambat di toko kelima.\n\n"
                       "Tidak ada drama. Tidak ada sistem yang tumbang. Hanya pajak pelan-"
                       "pelan — sehari di sini merekonsiliasi bank, sesore di sana memburu "
                       "transfer ganda, angka untuk pemilik yang datang terlambat seminggu "
                       "dan cuma setengah dipercaya.\n\n"
                       "Tahu posisi bisnismu seharusnya efek samping dari membukukan, bukan "
                       "pekerjaan kedua setelahnya. Itulah inti dari helicopter view.",
        },
        {
            "slug": "hiring-more-admins-wont-fix-it", "type": "field_note",
            "title_en": "Hiring another admin won't fix your back office",
            "title_id": "Menambah admin tidak akan membereskan back office-mu",
            "excerpt_en": "When the typing piles up, the instinct is to add people. There's a "
                          "better use for the people you already have.",
            "excerpt_id": "Saat pekerjaan input menumpuk, naluri kita menambah orang. Ada "
                          "kegunaan yang lebih baik untuk orang yang sudah ada.",
            "published_at": "2026-05-12",
            "body_en": "When the back office falls behind, the first instinct is always the "
                       "same: hire another admin. Six months later the typing has grown to fill "
                       "the new hands, and the owner still can't see last month's profit.\n\n"
                       "The problem was never the people. It's that good people were spending "
                       "their days on work a system should do — re-typing bank lines, chasing "
                       "duplicates, assembling the same report the same way every month.\n\n"
                       "The businesses that get ahead don't have bigger admin teams. They have "
                       "the same people doing different work: chasing receivables, talking to "
                       "customers, watching the numbers instead of typing them.",
            "body_id": "Saat back office mulai keteteran, naluri pertama selalu sama: rekrut "
                       "admin lagi. Enam bulan kemudian pekerjaan input tumbuh memenuhi "
                       "tangan yang baru, dan pemilik tetap tidak tahu untung bulan lalu.\n\n"
                       "Masalahnya tidak pernah di orangnya. Masalahnya, orang-orang baik itu "
                       "menghabiskan hari untuk pekerjaan yang seharusnya dikerjakan sistem — "
                       "mengetik ulang baris bank, memburu duplikat, menyusun laporan yang "
                       "sama dengan cara yang sama setiap bulan.\n\n"
                       "Bisnis yang melaju bukan yang tim adminnya paling besar. Mereka punya "
                       "orang yang sama mengerjakan hal berbeda: menagih piutang, berbicara "
                       "dengan pelanggan, mengawasi angka — bukan mengetiknya.",
        },
    ]
    for s in seed:
        conn.execute(
            "INSERT INTO posts (slug, type, status, title_en, title_id, excerpt_en,"
            " excerpt_id, body_en, body_id, cover_image, author, published_at,"
            " created_at, updated_at)"
            " VALUES (?,?, 'published', ?,?,?,?,?,?,'','MASAGI Team',?,?,?)",
            (s["slug"], s["type"], s["title_en"], s["title_id"], s["excerpt_en"],
             s["excerpt_id"], _p(s["body_en"]), _p(s["body_id"]),
             s["published_at"], now(), now()))


def _seed_slides(conn):
    """Carousel seeded from the landing page's current three hero slides, so
    the live hero is unchanged until someone edits or adds media."""
    seed = [
        ("MASAGI Digital", "MASAGI Digital",
         "Systems that let you see your business clearly.",
         "Sistem yang membuat bisnismu terlihat jernih.",
         "We build precise operational software for growing companies in Indonesia "
         "and Southeast Asia — so decisions start from what is actually true today.",
         "Kami membangun perangkat lunak operasional yang presisi untuk perusahaan "
         "yang sedang tumbuh di Indonesia dan Asia Tenggara — supaya setiap keputusan "
         "berangkat dari yang benar-benar terjadi hari ini.",
         "Explore our services", "Lihat layanan kami", "#services"),
        ("MASAGI-HV · Helicopter View ERP", "MASAGI-HV · ERP Helicopter View",
         "Every entity, account and rupiah — one live view.",
         "Setiap entitas, akun, dan rupiah — satu tampilan hidup.",
         "Consolidated finance for multi-entity groups: double-entry at the core, "
         "smart bank import, budgets and board-ready reports.",
         "Keuangan terkonsolidasi untuk grup multi-entitas: double-entry di intinya, "
         "impor bank pintar, anggaran, dan laporan siap rapat direksi.",
         "See MASAGI-HV", "Lihat MASAGI-HV", "#services"),
        ("MASAGI-CROM · Certification Ops", "MASAGI-CROM · Operasional Sertifikasi",
         "Regulatory work, run like clockwork.",
         "Urusan regulasi, berjalan seperti jarum jam.",
         "Run every client's certification as a staged pipeline — from submission "
         "to audit to issued certificate, nothing slips.",
         "Jalankan sertifikasi setiap klien sebagai pipeline bertahap — dari "
         "pengajuan, audit, sampai sertifikat terbit, tidak ada yang terlewat.",
         "See MASAGI-CROM", "Lihat MASAGI-CROM", "#services"),
    ]
    for i, s in enumerate(seed):
        conn.execute(
            "INSERT INTO slides (position, is_active, media_type, media_url, media_side,"
            " eyebrow_en, eyebrow_id, title_en, title_id, sub_en, sub_id,"
            " cta_label_en, cta_label_id, cta_href, updated_at)"
            " VALUES (?,1,'none','','right',?,?,?,?,?,?,?,?,?,?)",
            (i, s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8], now()))


init_db()


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def slugify(text, fallback="post"):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return s or fallback


def unique_slug(slug, post_id=None):
    """Keep slugs unique — append -2, -3 … when the base is taken."""
    base, n = slug, 2
    while True:
        row = db().execute("SELECT id FROM posts WHERE slug=?", (slug,)).fetchone()
        if row is None or (post_id and row["id"] == int(post_id)):
            return slug
        slug = "%s-%d" % (base, n)
        n += 1


def current_user():
    uid = session.get("cms_user")
    if not uid:
        return None
    return db().execute(
        "SELECT * FROM users WHERE id=? AND is_active=1", (uid,)).fetchone()


def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        user = current_user()
        if user is None:
            return jsonify({"error": "Sign in required"}), 401
        g.user = user
        return fn(*a, **kw)
    return wrapper


def cors(resp):
    """Public feeds are read-only and non-sensitive; the landing page reads
    them cross-origin from masagi.io."""
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "public, max-age=60"
    return resp


def safe_href(v):
    """Only benign link targets survive (no javascript:/data:)."""
    s = (v or "").strip()
    return s if s.lower().startswith(("http://", "https://", "mailto:", "tel:", "/", "#")) else ""


def media_kind(name):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return "video" if ext in VIDEO_EXT else "image"


def post_dict(r, lang=None):
    d = dict(r)
    d["type_label_en"] = TYPE_LABEL_EN.get(d["type"], d["type"])
    d["type_label_id"] = TYPE_LABEL_ID.get(d["type"], d["type"])
    d["url"] = "%s/%s" % (BLOG_BASE, d["slug"])
    d["type_slug"] = TYPE_SLUG.get(d["type"], d["type"])
    return d


def get_settings():
    rows = db().execute("SELECT key, value FROM settings").fetchall()
    out = dict(DEFAULT_SETTINGS)
    out.update({r["key"]: r["value"] for r in rows})
    return out


# --------------------------------------------------------------------------
# public blog
# --------------------------------------------------------------------------

def _published(where="", params=()):
    sql = ("SELECT * FROM posts WHERE status='published' %s"
           " ORDER BY (published_at='') ASC, published_at DESC, id DESC" % where)
    return db().execute(sql, params).fetchall()


@app.get("/")
def blog_index():
    posts = _published()
    return render_template("index.html", posts=[post_dict(p) for p in posts],
                           types=POST_TYPES, type_slug=TYPE_SLUG, active=None,
                           settings=get_settings(), blog_base=BLOG_BASE)


@app.get("/category/<cat>")
def blog_category(cat):
    key = SLUG_TO_TYPE.get(cat)
    if not key:
        abort(404)
    posts = _published("AND type=?", (key,))
    return render_template("index.html", posts=[post_dict(p) for p in posts],
                           types=POST_TYPES, type_slug=TYPE_SLUG, active=key,
                           type_label=TYPE_LABEL_EN[key],
                           settings=get_settings(), blog_base=BLOG_BASE)


@app.get("/<slug>")
def blog_post(slug):
    row = db().execute(
        "SELECT * FROM posts WHERE slug=? AND status='published'", (slug,)).fetchone()
    if row is None:
        abort(404)
    post = post_dict(row)
    more = [post_dict(p) for p in _published("AND slug<>?", (slug,))][:3]
    return render_template("post.html", post=post, more=more, types=POST_TYPES,
                           type_slug=TYPE_SLUG, active=post["type"],
                           settings=get_settings(), blog_base=BLOG_BASE)


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith(("/api/", "/admin")):
        return jsonify({"error": "Not found"}), 404
    return render_template("404.html", types=POST_TYPES, type_slug=TYPE_SLUG,
                           settings=get_settings(), blog_base=BLOG_BASE), 404


@app.get("/uploads/<path:name>")
def uploaded_file(name):
    return send_from_directory(UPLOAD_DIR, name)


@app.get("/robots.txt")
def robots():
    body = "User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: %s/sitemap.xml\n" % BLOG_BASE
    return app.response_class(body, mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap():
    urls = [BLOG_BASE + "/"]
    urls += ["%s/category/%s" % (BLOG_BASE, s) for s in TYPE_SLUG.values()]
    urls += ["%s/%s" % (BLOG_BASE, r["slug"]) for r in _published()]
    items = "".join("<url><loc>%s</loc></url>" % u for u in urls)
    return app.response_class(
        '<?xml version="1.0" encoding="UTF-8"?><urlset '
        'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % items,
        mimetype="application/xml")


# --------------------------------------------------------------------------
# public JSON feeds (consumed by the masagi.io landing page)
# --------------------------------------------------------------------------

@app.get("/api/public/posts")
def api_public_posts():
    try:
        limit = max(1, min(50, int(request.args.get("limit", 12))))
    except ValueError:
        limit = 12
    t = request.args.get("type")
    rows = _published("AND type=?", (t,)) if t in TYPE_KEYS else _published()
    return cors(jsonify({"posts": [post_dict(r) for r in rows[:limit]]}))


@app.get("/api/public/carousel")
def api_public_carousel():
    rows = db().execute(
        "SELECT * FROM slides WHERE is_active=1 ORDER BY position, id").fetchall()
    return cors(jsonify({"slides": [dict(r) for r in rows]}))


# --------------------------------------------------------------------------
# admin panel
# --------------------------------------------------------------------------

@app.get("/admin")
def admin_page():
    return send_from_directory(app.static_folder, "admin.html")


@app.post("/api/admin/login")
def admin_login():
    d = request.get_json(silent=True) or {}
    row = db().execute("SELECT * FROM users WHERE username=? AND is_active=1",
                       (str(d.get("username", "")).strip(),)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], d.get("password", "")):
        return jsonify({"error": "Wrong username or password"}), 401
    session["cms_user"] = row["id"]
    session.permanent = True
    return jsonify({"ok": True, "user": {"username": row["username"], "name": row["name"]}})


@app.post("/api/admin/logout")
def admin_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/admin/me")
@login_required
def admin_me():
    return jsonify({"username": g.user["username"], "name": g.user["name"],
                    "types": [{"key": k, "label": l} for k, l, _ in POST_TYPES],
                    "blog_base": BLOG_BASE})


@app.post("/api/admin/password")
@login_required
def admin_password():
    d = request.get_json(force=True)
    new = d.get("new_password") or ""
    if len(new) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400
    if not check_password_hash(g.user["password_hash"], d.get("current_password", "")):
        return jsonify({"error": "Current password is incorrect"}), 400
    db().execute("UPDATE users SET password_hash=? WHERE id=?",
                 (generate_password_hash(new), g.user["id"]))
    db().commit()
    return jsonify({"ok": True})


@app.get("/api/admin/stats")
@login_required
def admin_stats():
    counts = {}
    for k in TYPE_KEYS:
        counts[k] = db().execute(
            "SELECT COUNT(*) n FROM posts WHERE type=?", (k,)).fetchone()["n"]
    return jsonify({
        "counts": counts,
        "published": db().execute("SELECT COUNT(*) n FROM posts WHERE status='published'").fetchone()["n"],
        "drafts": db().execute("SELECT COUNT(*) n FROM posts WHERE status='draft'").fetchone()["n"],
        "slides": db().execute("SELECT COUNT(*) n FROM slides WHERE is_active=1").fetchone()["n"],
        "media": db().execute("SELECT COUNT(*) n FROM media").fetchone()["n"],
    })


# ---- posts ----

POST_FIELDS = ("title_en", "title_id", "excerpt_en", "excerpt_id",
               "body_en", "body_id", "cover_image", "author", "published_at")


@app.get("/api/admin/posts")
@login_required
def admin_posts():
    t = request.args.get("type")
    if t in TYPE_KEYS:
        rows = db().execute(
            "SELECT * FROM posts WHERE type=? ORDER BY (published_at='') ASC,"
            " published_at DESC, id DESC", (t,)).fetchall()
    else:
        rows = db().execute(
            "SELECT * FROM posts ORDER BY (published_at='') ASC,"
            " published_at DESC, id DESC").fetchall()
    return jsonify({"posts": [post_dict(r) for r in rows]})


@app.get("/api/admin/posts/<int:pid>")
@login_required
def admin_post_get(pid):
    row = db().execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
    if row is None:
        return jsonify({"error": "Post not found"}), 404
    return jsonify(post_dict(row))


def _post_payload(d):
    vals = {k: str(d.get(k) or "").strip() for k in POST_FIELDS}
    vals["author"] = vals["author"] or "MASAGI Team"
    vals["cover_image"] = safe_href(vals["cover_image"])
    ptype = d.get("type") if d.get("type") in TYPE_KEYS else "insight"
    status = "published" if d.get("status") == "published" else "draft"
    return vals, ptype, status


@app.post("/api/admin/posts")
@login_required
def admin_post_create():
    d = request.get_json(force=True)
    vals, ptype, status = _post_payload(d)
    if not vals["title_en"] and not vals["title_id"]:
        return jsonify({"error": "Give the post a title first"}), 400
    slug = unique_slug(slugify(d.get("slug") or vals["title_en"] or vals["title_id"]))
    if status == "published" and not vals["published_at"]:
        vals["published_at"] = today()
    cur = db().execute(
        "INSERT INTO posts (slug, type, status, title_en, title_id, excerpt_en,"
        " excerpt_id, body_en, body_id, cover_image, author, published_at,"
        " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (slug, ptype, status, vals["title_en"], vals["title_id"], vals["excerpt_en"],
         vals["excerpt_id"], vals["body_en"], vals["body_id"], vals["cover_image"],
         vals["author"], vals["published_at"], now(), now()))
    db().commit()
    return jsonify({"ok": True, "id": cur.lastrowid, "slug": slug}), 201


@app.put("/api/admin/posts/<int:pid>")
@login_required
def admin_post_update(pid):
    row = db().execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
    if row is None:
        return jsonify({"error": "Post not found"}), 404
    d = request.get_json(force=True)
    vals, ptype, status = _post_payload(d)
    if not vals["title_en"] and not vals["title_id"]:
        return jsonify({"error": "Give the post a title first"}), 400
    slug = unique_slug(slugify(d.get("slug") or vals["title_en"] or vals["title_id"]), pid)
    if status == "published" and not vals["published_at"]:
        vals["published_at"] = today()
    db().execute(
        "UPDATE posts SET slug=?, type=?, status=?, title_en=?, title_id=?,"
        " excerpt_en=?, excerpt_id=?, body_en=?, body_id=?, cover_image=?,"
        " author=?, published_at=?, updated_at=? WHERE id=?",
        (slug, ptype, status, vals["title_en"], vals["title_id"], vals["excerpt_en"],
         vals["excerpt_id"], vals["body_en"], vals["body_id"], vals["cover_image"],
         vals["author"], vals["published_at"], now(), pid))
    db().commit()
    return jsonify({"ok": True, "slug": slug})


@app.delete("/api/admin/posts/<int:pid>")
@login_required
def admin_post_delete(pid):
    db().execute("DELETE FROM posts WHERE id=?", (pid,))
    db().commit()
    return jsonify({"ok": True})


# ---- carousel ----

SLIDE_TEXT = ("eyebrow_en", "eyebrow_id", "title_en", "title_id", "sub_en", "sub_id",
              "cta_label_en", "cta_label_id")


@app.get("/api/admin/carousel")
@login_required
def admin_carousel_get():
    rows = db().execute("SELECT * FROM slides ORDER BY position, id").fetchall()
    return jsonify({"slides": [dict(r) for r in rows]})


@app.put("/api/admin/carousel")
@login_required
def admin_carousel_save():
    """Whole-list save: the editor sends every slide in display order."""
    d = request.get_json(force=True)
    slides = d.get("slides")
    if not isinstance(slides, list):
        return jsonify({"error": "slides must be a list"}), 400
    db().execute("DELETE FROM slides")
    for i, s in enumerate(slides[:12]):
        if not isinstance(s, dict):
            continue
        vals = {k: str(s.get(k) or "").strip() for k in SLIDE_TEXT}
        if not vals["title_en"] and not vals["title_id"] and not s.get("media_url"):
            continue  # a slide needs at least a headline or media
        mtype = s.get("media_type") if s.get("media_type") in ("image", "video", "none") else "none"
        side = s.get("media_side") if s.get("media_side") in ("right", "left") else "right"
        db().execute(
            "INSERT INTO slides (position, is_active, media_type, media_url, media_side,"
            " poster, eyebrow_en, eyebrow_id, title_en, title_id, sub_en, sub_id,"
            " cta_label_en, cta_label_id, cta_href, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (i, 0 if s.get("is_active") in (0, False, "0", "false") else 1,
             mtype, safe_href(s.get("media_url")), side, safe_href(s.get("poster")),
             vals["eyebrow_en"], vals["eyebrow_id"], vals["title_en"], vals["title_id"],
             vals["sub_en"], vals["sub_id"], vals["cta_label_en"], vals["cta_label_id"],
             safe_href(s.get("cta_href")), now()))
    db().commit()
    rows = db().execute("SELECT * FROM slides ORDER BY position, id").fetchall()
    return jsonify({"ok": True, "slides": [dict(r) for r in rows]})


# ---- media library ----

@app.get("/api/admin/media")
@login_required
def admin_media_list():
    rows = db().execute("SELECT * FROM media ORDER BY id DESC").fetchall()
    return jsonify({"media": [dict(r) for r in rows]})


@app.post("/api/admin/media")
@login_required
def admin_media_upload():
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"error": "No file received"}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "Unsupported file type (.%s). Images and MP4/WebM video only." % ext}), 400
    base = secure_filename(f.filename.rsplit(".", 1)[0])[:60] or "file"
    name = "%s-%s.%s" % (base, secrets.token_hex(4), ext)
    f.save(os.path.join(UPLOAD_DIR, name))
    size = os.path.getsize(os.path.join(UPLOAD_DIR, name))
    db().execute(
        "INSERT INTO media (filename, original_name, kind, size, uploaded_at)"
        " VALUES (?,?,?,?,?)", (name, f.filename, media_kind(name), size, now()))
    db().commit()
    return jsonify({"ok": True, "url": "/uploads/" + name,
                    "filename": name, "kind": media_kind(name)}), 201


@app.delete("/api/admin/media/<int:mid>")
@login_required
def admin_media_delete(mid):
    row = db().execute("SELECT * FROM media WHERE id=?", (mid,)).fetchone()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    try:
        os.remove(os.path.join(UPLOAD_DIR, row["filename"]))
    except OSError:
        pass  # already gone from disk — still drop the row
    db().execute("DELETE FROM media WHERE id=?", (mid,))
    db().commit()
    return jsonify({"ok": True})


# ---- settings ----

@app.get("/api/admin/settings")
@login_required
def admin_settings_get():
    return jsonify(get_settings())


@app.post("/api/admin/settings")
@login_required
def admin_settings_save():
    d = request.get_json(force=True)
    for k in DEFAULT_SETTINGS:
        if k in d:
            db().execute(
                "INSERT INTO settings (key, value) VALUES (?,?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, str(d[k] or "").strip()))
    db().commit()
    return jsonify({"ok": True, "settings": get_settings()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8020))
    print("MASAGI CMS on http://127.0.0.1:%d  (admin at /admin)" % port)
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=False)
