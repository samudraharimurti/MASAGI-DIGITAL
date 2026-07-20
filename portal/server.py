"""MASAGI Account — unified sign-in portal (account.masagi.io).

One account per person; each account carries grants that map it to a local
identity inside each system:

    hv    -> a MASAGI-HV username (+ which database to open)
    crom  -> a MASAGI-CROM user email

Flow:  login here -> chooser -> /launch/<system> mints a 60-second
HMAC-signed token -> redirect to <system>/sso?token=... -> that app verifies
the token with the shared secret (data/portal/sso_secret) and opens its own
normal session. The portal never shares its cookie with the systems.

Admins (users.is_admin=1) additionally get:
  - trial MASAGI-HV databases, created/listed by having the portal mint an
    SSO token for the ADMIN'S OWN hv grant and call HV's existing
    /api/databases endpoints server-to-server (HV_INTERNAL_URL) — HV's own
    role check is the real authority here, the portal never duplicates it.
  - full CRUD over portal users and their grants.
  - an editor for the landing page's own headline/description copy, served
    publicly (CORS *) at GET /api/public/landing-content for the static
    landing page to fetch at load. Blog/news stays on MASAGI HV's existing
    CMS (/admin/content there) — linked from here, not rebuilt.

Run:   python server.py                     (PORT env, default 8015)
Users: python server.py add-user <email> "<Name>" <password> [admin] [hv:user@DB] [crom:email]
       python server.py list-users
"""
import base64
import functools
import hashlib
import hmac
import http.client
import json
import os
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import (Flask, g, jsonify, redirect, request, send_from_directory,
                   session)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
PORTAL_DIR = os.path.join(BASE_DIR, os.pardir, "data", "portal")
DB_PATH = os.path.join(PORTAL_DIR, "portal.db")
SSO_SECRET_FILE = os.environ.get("SSO_SECRET_FILE") or os.path.join(PORTAL_DIR, "sso_secret")
FLASK_SECRET_FILE = os.path.join(PORTAL_DIR, ".flask_secret")
LANDING_CONTENT_FILE = os.path.join(PORTAL_DIR, "landing_content.json")

# Where each system lives for BROWSER redirects (public URL the user's own
# tab is sent to). HV_INTERNAL_URL is separate: where the portal's own
# backend reaches HV directly (same box -> localhost, no TLS/DNS needed).
SYSTEMS = {
    "hv": {
        "name": "MASAGI HV",
        "desc_en": "Helicopter View ERP — consolidated finance",
        "desc_id": "ERP Helicopter View — keuangan terkonsolidasi",
        "url": os.environ.get("HV_URL", "http://127.0.0.1:8010"),
    },
    "crom": {
        "name": "MASAGI CROM",
        "desc_en": "Certification & regulatory operations",
        "desc_id": "Operasional sertifikasi & regulasi",
        "url": os.environ.get("CROM_URL", "http://127.0.0.1:8016"),
    },
}
HV_INTERNAL_URL = os.environ.get("HV_INTERNAL_URL") or SYSTEMS["hv"]["url"]
TOKEN_TTL_SECONDS = 60
LOGIN_ATTEMPTS = {}  # email -> [timestamps of failures]
SEED_EMAIL = "samudra@masagi.io"
SEED_PASSWORD = "masagi123"

os.makedirs(PORTAL_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)
if not os.path.exists(FLASK_SECRET_FILE):
    with open(FLASK_SECRET_FILE, "w") as f:
        f.write(secrets.token_hex(32))
with open(FLASK_SECRET_FILE) as f:
    app.secret_key = f.read().strip()
app.permanent_session_lifetime = timedelta(days=14)


# ---------------------------------------------------------------- db / seed

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT DEFAULT '',
      password_hash TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1,
      is_admin INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS grants(
      user_id INTEGER NOT NULL, system TEXT NOT NULL,
      identity TEXT NOT NULL, extra TEXT DEFAULT '',
      UNIQUE(user_id, system));
    """)
    try:  # migration for databases created before is_admin existed
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # shared SSO secret for HV + CROM (they read the same file)
    if not os.path.exists(SSO_SECRET_FILE):
        with open(SSO_SECRET_FILE, "w") as f:
            f.write(secrets.token_hex(32))

    # first-run seed: fixed super-admin credentials. Wrapped against the
    # UNIQUE(email) constraint because gunicorn boots multiple workers, each
    # importing (and so seeding) this module independently.
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        try:
            conn.execute(
                "INSERT INTO users(email,name,password_hash,is_admin,created_at) VALUES(?,?,?,1,?)",
                (SEED_EMAIL, "Samudra", generate_password_hash(SEED_PASSWORD),
                 datetime.utcnow().isoformat()))
            uid = conn.execute("SELECT id FROM users WHERE email=?", (SEED_EMAIL,)).fetchone()["id"]
            conn.execute("INSERT INTO grants VALUES(?,?,?,?)", (uid, "hv", "admin", "MASAGI-GROUP"))
            conn.execute("INSERT INTO grants VALUES(?,?,?,?)", (uid, "crom", "admin@masagicrom.local", ""))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # another worker won the race and seeded it first
    conn.close()


# Runs unconditionally at import time (not just under `python server.py`) so
# the database, seed user, and shared SSO secret all exist before gunicorn
# serves the first request — gunicorn imports this module, it never executes
# the `if __name__ == "__main__"` block below.
init_db()


# ------------------------------------------------------------------- tokens

def _sso_secret():
    with open(SSO_SECRET_FILE) as f:
        return f.read().strip()


def mint_token(payload: dict) -> str:
    payload = dict(payload, exp=int(time.time()) + TOKEN_TTL_SECONDS,
                   n=secrets.token_hex(4))
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_sso_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + sig


# -------------------------------------------------------------------- pages

@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/admin")
def admin_page():
    return send_from_directory(STATIC_DIR, "admin.html")


@app.get("/static/<path:path>")
def static_files(path):
    return send_from_directory(STATIC_DIR, path)


# ---------------------------------------------------------------------- api

def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    conn = db()
    try:
        return conn.execute("SELECT * FROM users WHERE id=? AND is_active=1",
                            (uid,)).fetchone()
    finally:
        conn.close()


def admin_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u:
            return jsonify({"error": "Not signed in"}), 401
        if not u["is_admin"]:
            return jsonify({"error": "Admin access required"}), 403
        g.admin = u
        return fn(*args, **kwargs)
    return wrapper


@app.post("/api/login")
def api_login():
    d = request.get_json(force=True)
    email = (d.get("email") or "").strip().lower()
    now = time.time()
    attempts = [ts for ts in LOGIN_ATTEMPTS.get(email, []) if now - ts < 600]
    if len(attempts) >= 5:
        return jsonify({"error": "Too many attempts — try again in 10 minutes."}), 429
    conn = db()
    try:
        row = conn.execute("SELECT * FROM users WHERE lower(email)=? AND is_active=1",
                           (email,)).fetchone()
    finally:
        conn.close()
    if not row or not check_password_hash(row["password_hash"], d.get("password") or ""):
        attempts.append(now)
        LOGIN_ATTEMPTS[email] = attempts
        return jsonify({"error": "Wrong email or password."}), 401
    LOGIN_ATTEMPTS.pop(email, None)
    session.clear()
    session["uid"] = row["id"]
    session.permanent = True
    return jsonify({"ok": True})


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/me")
def api_me():
    u = current_user()
    if not u:
        return jsonify({"error": "Not signed in"}), 401
    conn = db()
    try:
        grants = conn.execute("SELECT system, identity, extra FROM grants WHERE user_id=?",
                              (u["id"],)).fetchall()
    finally:
        conn.close()
    systems = []
    for g_ in grants:
        meta = SYSTEMS.get(g_["system"])
        if meta:
            systems.append({"key": g_["system"], "name": meta["name"],
                            "desc_en": meta["desc_en"], "desc_id": meta["desc_id"]})
    return jsonify({"email": u["email"], "name": u["name"], "is_admin": bool(u["is_admin"]),
                    "systems": systems})


@app.post("/api/me/password")
def change_my_password():
    u = current_user()
    if not u:
        return jsonify({"error": "Not signed in"}), 401
    d = request.get_json(force=True)
    if not check_password_hash(u["password_hash"], d.get("current_password") or ""):
        return jsonify({"error": "Current password is incorrect."}), 400
    new = d.get("new_password") or ""
    if len(new) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400
    conn = db()
    try:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                     (generate_password_hash(new), u["id"]))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.get("/launch/<system>")
def launch(system):
    u = current_user()
    if not u:
        return redirect("/")
    meta = SYSTEMS.get(system)
    conn = db()
    try:
        g_ = conn.execute("SELECT * FROM grants WHERE user_id=? AND system=?",
                          (u["id"], system)).fetchone()
    finally:
        conn.close()
    if not meta or not g_:
        return redirect("/?denied=1")
    if system == "hv":
        payload = {"sys": "hv", "u": g_["identity"], "db": g_["extra"] or None}
    else:
        payload = {"sys": "crom", "email": g_["identity"]}
    return redirect(meta["url"].rstrip("/") + "/sso?token=" + mint_token(payload))


# ------------------------------------------------------- internal HV calls
# Server-to-server: mint a fresh SSO token for the ADMIN'S OWN hv grant,
# trade it for an HV session cookie, then call HV's existing admin API with
# that cookie. HV's own @role_required("admin") is what actually authorizes
# this — the portal never duplicates or bypasses that check.

def _hv_call(hv_identity, method, path, body=None):
    parsed = urlparse(HV_INTERNAL_URL)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.hostname, port, timeout=10)
    try:
        token = mint_token({"sys": "hv", "u": hv_identity})
        conn.request("GET", "/sso?token=" + token)
        r = conn.getresponse()
        r.read()
        cookie = r.getheader("Set-Cookie")
        if r.status not in (301, 302, 303, 307, 308) or not cookie:
            return None, "HV did not accept the internal sign-in (status %s) — is the account's " \
                         "HV grant valid and active?" % r.status
        headers = {"Cookie": cookie.split(";")[0]}
        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body)
        conn.request(method, path, body=payload, headers=headers)
        r2 = conn.getresponse()
        raw = r2.read()
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {"raw": raw.decode(errors="replace")}
        return r2.status, data
    except OSError as e:
        return None, "Could not reach MASAGI HV internally: %s" % e
    finally:
        conn.close()


def _admin_hv_identity(admin_row):
    conn = db()
    try:
        g_ = conn.execute("SELECT identity FROM grants WHERE user_id=? AND system='hv'",
                          (admin_row["id"],)).fetchone()
    finally:
        conn.close()
    return g_["identity"] if g_ else None


@app.get("/api/admin/hv-databases")
@admin_required
def admin_list_hv_databases():
    identity = _admin_hv_identity(g.admin)
    if not identity:
        return jsonify({"error": "Your account has no MASAGI HV identity — add an hv grant "
                                 "to your own user first."}), 400
    status, data = _hv_call(identity, "GET", "/api/databases")
    if status is None:
        return jsonify({"error": data}), 502
    if status != 200:
        return jsonify({"error": data.get("error", "HV returned status %s" % status)}), 502
    return jsonify({"databases": [d["name"] for d in data.get("databases", [])]})


@app.post("/api/admin/hv-databases")
@admin_required
def admin_create_hv_database():
    identity = _admin_hv_identity(g.admin)
    if not identity:
        return jsonify({"error": "Your account has no MASAGI HV identity — add an hv grant "
                                 "to your own user first."}), 400
    d = request.get_json(force=True)
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Database name is required."}), 400
    status, data = _hv_call(identity, "POST", "/api/databases",
                            {"name": name, "seed_demo": bool(d.get("seed_demo", True))})
    if status is None:
        return jsonify({"error": data}), 502
    if status not in (200, 201):
        return jsonify({"error": data.get("error", "HV returned status %s" % status)}), 502
    return jsonify({"ok": True, "name": data.get("name", name)})


# ------------------------------------------------------------ user/grant CRUD

def _serialize_user(row, conn):
    grants = conn.execute("SELECT system, identity, extra FROM grants WHERE user_id=?",
                          (row["id"],)).fetchall()
    out = {"id": row["id"], "email": row["email"], "name": row["name"],
           "is_admin": bool(row["is_admin"]), "is_active": bool(row["is_active"]),
           "hv_username": "", "hv_db": "", "crom_email": ""}
    for g_ in grants:
        if g_["system"] == "hv":
            out["hv_username"] = g_["identity"]
            out["hv_db"] = g_["extra"] or ""
        elif g_["system"] == "crom":
            out["crom_email"] = g_["identity"]
    return out


@app.get("/api/admin/users")
@admin_required
def admin_list_users():
    conn = db()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return jsonify({"users": [_serialize_user(r, conn) for r in rows]})
    finally:
        conn.close()


def _apply_grants(conn, uid, d):
    hv_user = (d.get("hv_username") or "").strip()
    hv_db = (d.get("hv_db") or "").strip()
    crom_email = (d.get("crom_email") or "").strip().lower()
    if hv_user:
        conn.execute("INSERT OR REPLACE INTO grants VALUES(?,?,?,?)", (uid, "hv", hv_user, hv_db))
    else:
        conn.execute("DELETE FROM grants WHERE user_id=? AND system='hv'", (uid,))
    if crom_email:
        conn.execute("INSERT OR REPLACE INTO grants VALUES(?,?,?,?)", (uid, "crom", crom_email, ""))
    else:
        conn.execute("DELETE FROM grants WHERE user_id=? AND system='crom'", (uid,))


@app.post("/api/admin/users")
@admin_required
def admin_create_user():
    d = request.get_json(force=True)
    email = (d.get("email") or "").strip().lower()
    name = (d.get("name") or "").strip()
    pw = d.get("password") or ""
    if "@" not in email or len(pw) < 6:
        return jsonify({"error": "Valid email and a password of at least 6 characters are required."}), 400
    conn = db()
    try:
        try:
            conn.execute(
                "INSERT INTO users(email,name,password_hash,is_admin,created_at) VALUES(?,?,?,?,?)",
                (email, name, generate_password_hash(pw), 1 if d.get("is_admin") else 0,
                 datetime.utcnow().isoformat()))
        except sqlite3.IntegrityError:
            return jsonify({"error": "An account with that email already exists."}), 409
        uid = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
        _apply_grants(conn, uid, d)
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return jsonify({"ok": True, "user": _serialize_user(row, conn)}), 201
    finally:
        conn.close()


@app.put("/api/admin/users/<int:uid>")
@admin_required
def admin_update_user(uid):
    d = request.get_json(force=True)
    conn = db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            return jsonify({"error": "User not found."}), 404
        name = d.get("name", row["name"])
        is_admin = 1 if d.get("is_admin") else 0
        is_active = 1 if d.get("is_active", row["is_active"]) else 0
        if row["id"] == g.admin["id"] and not is_admin:
            return jsonify({"error": "You can't remove your own admin access."}), 400
        if row["id"] == g.admin["id"] and not is_active:
            return jsonify({"error": "You can't deactivate your own account."}), 400
        conn.execute("UPDATE users SET name=?, is_admin=?, is_active=? WHERE id=?",
                     (name, is_admin, is_active, uid))
        new_pw = d.get("password") or ""
        if new_pw:
            if len(new_pw) < 6:
                return jsonify({"error": "New password must be at least 6 characters."}), 400
            conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                         (generate_password_hash(new_pw), uid))
        _apply_grants(conn, uid, d)
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return jsonify({"ok": True, "user": _serialize_user(row, conn)})
    finally:
        conn.close()


@app.delete("/api/admin/users/<int:uid>")
@admin_required
def admin_delete_user(uid):
    if uid == g.admin["id"]:
        return jsonify({"error": "You can't delete your own account."}), 400
    conn = db()
    try:
        conn.execute("DELETE FROM grants WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# --------------------------------------------------------- landing page CMS

DEFAULT_LANDING_CONTENT = {
    "hero": [
        {"eyebrow_en": "MASAGI Digital", "eyebrow_id": "MASAGI Digital",
         "title_en": "Systems that let you see your business clearly.",
         "title_id": "Sistem yang membuat bisnismu terlihat jernih.",
         "sub_en": "We build precise operational software for growing companies in Indonesia "
                   "and Southeast Asia — so decisions start from what is actually true today.",
         "sub_id": "Kami membangun perangkat lunak operasional yang presisi untuk perusahaan "
                   "yang sedang tumbuh di Indonesia dan Asia Tenggara — supaya setiap keputusan "
                   "berangkat dari yang benar-benar terjadi hari ini."},
        {"eyebrow_en": "MASAGI-HV · Helicopter View ERP", "eyebrow_id": "MASAGI-HV · ERP Helicopter View",
         "title_en": "Every entity, account and rupiah — one live view.",
         "title_id": "Setiap entitas, akun, dan rupiah — satu tampilan hidup.",
         "sub_en": "Consolidated finance for multi-entity groups: double-entry at the core, "
                   "smart bank import, budgets and board-ready reports.",
         "sub_id": "Keuangan terkonsolidasi untuk grup multi-entitas: double-entry di intinya, "
                   "impor bank pintar, anggaran, dan laporan siap rapat direksi."},
        {"eyebrow_en": "MASAGI-CROM · Certification Ops", "eyebrow_id": "MASAGI-CROM · Operasional Sertifikasi",
         "title_en": "Regulatory work, run like clockwork.",
         "title_id": "Urusan regulasi, berjalan seperti jarum jam.",
         "sub_en": "Run every client's certification as a staged pipeline — from submission "
                   "to audit to issued certificate, nothing slips.",
         "sub_id": "Jalankan sertifikasi setiap klien sebagai pipeline bertahap — dari "
                   "pengajuan, audit, sampai sertifikat terbit, tidak ada yang terlewat."},
    ],
    "about": {
        "lead_en": "MASAGI Digital is a software company from Jakarta. We sit with operating "
                  "teams, learn how their month really runs, and build systems that remove "
                  "the busywork — so people can do the work only people can do.",
        "lead_id": "MASAGI Digital adalah perusahaan perangkat lunak dari Jakarta. Kami duduk "
                  "bersama tim operasional, memahami bagaimana bulan mereka benar-benar "
                  "berjalan, lalu membangun sistem yang menghapus pekerjaan berulang.",
        "mission_en": "To give growing companies in Southeast Asia the same operational "
                     "clarity as the region's largest groups — without the enterprise price "
                     "tag or the enterprise bureaucracy.",
        "mission_id": "Memberi perusahaan yang sedang tumbuh di Asia Tenggara kejernihan "
                     "operasional yang sama dengan grup terbesar di kawasan — tanpa harga "
                     "dan birokrasi enterprise.",
        "vision_en": "A region where every serious business runs on numbers it can trust, "
                    "updated live, understood by everyone at the table.",
        "vision_id": "Kawasan tempat setiap bisnis yang serius berjalan di atas angka yang "
                    "bisa dipercaya, diperbarui langsung, dan dipahami semua orang.",
    },
    "services": {
        "hv_desc_en": "The Helicopter View ERP — consolidated finance for growing SMEs and "
                     "multi-entity groups.",
        "hv_desc_id": "ERP Helicopter View — keuangan terkonsolidasi untuk UKM yang tumbuh "
                     "dan grup multi-entitas.",
        "crom_desc_en": "Certification & Regulatory Operations Management — every client's "
                        "certification runs as a clear, staged pipeline.",
        "crom_desc_id": "Certification & Regulatory Operations Management — sertifikasi "
                        "setiap klien berjalan sebagai pipeline bertahap yang jelas.",
    },
    "contact": {
        "hq_en": "Jakarta, Indonesia — Serving clients across ID · SG · MY · VN · TH",
        "hq_id": "Jakarta, Indonesia — Melayani klien di ID · SG · MY · VN · TH",
        "email": "samudra@masagi.io",
        "hours_en": "Monday – Friday · 09.00 – 18.00 WIB",
        "hours_id": "Senin – Jumat · 09.00 – 18.00 WIB",
    },
}


def _read_landing_content():
    try:
        with open(LANDING_CONTENT_FILE, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return dict(DEFAULT_LANDING_CONTENT)
    merged = json.loads(json.dumps(DEFAULT_LANDING_CONTENT))  # deep copy
    if isinstance(saved.get("hero"), list):
        for i, slide in enumerate(saved["hero"][:3]):
            if i < len(merged["hero"]) and isinstance(slide, dict):
                merged["hero"][i].update(slide)
    for key in ("about", "services", "contact"):
        if isinstance(saved.get(key), dict):
            merged[key].update(saved[key])
    return merged


@app.get("/api/public/landing-content")
def public_landing_content():
    resp = jsonify(_read_landing_content())
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "public, max-age=60"
    return resp


@app.post("/api/admin/landing-content")
@admin_required
def admin_save_landing_content():
    d = request.get_json(force=True)
    current = _read_landing_content()
    if isinstance(d.get("hero"), list):
        for i, slide in enumerate(d["hero"][:3]):
            if i < len(current["hero"]) and isinstance(slide, dict):
                current["hero"][i].update({k: str(v) for k, v in slide.items()})
    for key in ("about", "services", "contact"):
        if isinstance(d.get(key), dict):
            current[key].update({k: str(v) for k, v in d[key].items()})
    with open(LANDING_CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "content": current})


# ----------------------------------------------------------------------- cli

def _cli(argv):
    init_db()
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "add-user":
        # add-user email "Name" password [admin] [hv:username@DB] [crom:email]
        email, name, pw = argv[2].lower(), argv[3], argv[4]
        is_admin = 0
        specs = []
        for arg in argv[5:]:
            if arg.lower() == "admin":
                is_admin = 1
            else:
                specs.append(arg)
        conn = db()
        conn.execute("INSERT OR REPLACE INTO users(id,email,name,password_hash,is_admin,created_at)"
                     " VALUES((SELECT id FROM users WHERE email=?),?,?,?,?,?)",
                     (email, email, name, generate_password_hash(pw), is_admin,
                      datetime.utcnow().isoformat()))
        uid = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
        for spec in specs:
            system, _, ident = spec.partition(":")
            if system == "hv":
                user_part, _, db_part = ident.partition("@")
                conn.execute("INSERT OR REPLACE INTO grants VALUES(?,?,?,?)",
                             (uid, "hv", user_part, db_part))
            elif system == "crom":
                conn.execute("INSERT OR REPLACE INTO grants VALUES(?,?,?,?)",
                             (uid, "crom", ident, ""))
        conn.commit()
        conn.close()
        print("user saved:", email, "(admin)" if is_admin else "")
    elif cmd == "list-users":
        conn = db()
        for u in conn.execute("SELECT * FROM users"):
            grants = conn.execute("SELECT system, identity, extra FROM grants WHERE user_id=?",
                                  (u["id"],)).fetchall()
            print(u["email"], "-", u["name"], "[admin]" if u["is_admin"] else "",
                  ["%s:%s%s" % (g_["system"], g_["identity"],
                                "@" + g_["extra"] if g_["extra"] else "") for g_ in grants])
        conn.close()
    else:
        print(__doc__)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _cli(sys.argv)
    else:
        port = int(os.environ.get("PORT", 8015))
        print("MASAGI Account portal running at http://127.0.0.1:%d" % port)
        app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=False)
