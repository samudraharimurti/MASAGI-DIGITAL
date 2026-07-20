"""MASAGI Account — unified sign-in portal (account.masagi.io).

One account per person; each account carries grants that map it to a local
identity inside each system:

    hv    -> a MASAGI-HV username (+ which database to open)
    crom  -> a MASAGI-CROM user email

Flow:  login here -> chooser -> /launch/<system> mints a 60-second
HMAC-signed token -> redirect to <system>/sso?token=... -> that app verifies
the token with the shared secret (data/portal/sso_secret) and opens its own
normal session. The portal never shares its cookie with the systems.

Run:   python server.py                     (PORT env, default 8015)
Users: python server.py add-user <email> "<Name>" <password> [hv:user@DB] [crom:email]
       python server.py list-users
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timedelta

from flask import (Flask, jsonify, redirect, request, send_from_directory,
                   session)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
PORTAL_DIR = os.path.join(BASE_DIR, os.pardir, "data", "portal")
DB_PATH = os.path.join(PORTAL_DIR, "portal.db")
SSO_SECRET_FILE = os.environ.get("SSO_SECRET_FILE") or os.path.join(PORTAL_DIR, "sso_secret")
FLASK_SECRET_FILE = os.path.join(PORTAL_DIR, ".flask_secret")
FIRST_LOGIN_FILE = os.path.join(PORTAL_DIR, "FIRST-LOGIN.txt")

# Where each system lives. On the server these are set by systemd to the
# public subdomains; locally they default to the dev ports.
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
TOKEN_TTL_SECONDS = 60
LOGIN_ATTEMPTS = {}  # email -> [timestamps of failures]

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
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS grants(
      user_id INTEGER NOT NULL, system TEXT NOT NULL,
      identity TEXT NOT NULL, extra TEXT DEFAULT '',
      UNIQUE(user_id, system));
    """)
    # shared SSO secret for HV + CROM (they read the same file)
    if not os.path.exists(SSO_SECRET_FILE):
        with open(SSO_SECRET_FILE, "w") as f:
            f.write(secrets.token_hex(32))
    # first-run seed: one admin account with a generated password, written to
    # FIRST-LOGIN.txt — read it, sign in, then delete the file. Wrapped
    # against the UNIQUE(email) constraint because gunicorn boots multiple
    # workers, each importing (and so seeding) this module independently.
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        pw = secrets.token_urlsafe(10)
        try:
            conn.execute(
                "INSERT INTO users(email,name,password_hash,created_at) VALUES(?,?,?,?)",
                ("samudra@masagi.io", "Samudra",
                 generate_password_hash(pw), datetime.utcnow().isoformat()))
            uid = conn.execute("SELECT id FROM users WHERE email='samudra@masagi.io'").fetchone()["id"]
            conn.execute("INSERT INTO grants VALUES(?,?,?,?)", (uid, "hv", "admin", "MASAGI-GROUP"))
            conn.execute("INSERT INTO grants VALUES(?,?,?,?)", (uid, "crom", "admin@masagicrom.local", ""))
            with open(FIRST_LOGIN_FILE, "w") as f:
                f.write("MASAGI Account — first sign-in\n"
                        "  email:    samudra@masagi.io\n"
                        "  password: %s\n"
                        "Sign in, then delete this file.\n" % pw)
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
    return jsonify({"email": u["email"], "name": u["name"], "systems": systems})


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


# ----------------------------------------------------------------------- cli

def _cli(argv):
    init_db()
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "add-user":
        # add-user email "Name" password [hv:username@DB] [crom:email]
        email, name, pw = argv[2].lower(), argv[3], argv[4]
        conn = db()
        conn.execute("INSERT OR REPLACE INTO users(email,name,password_hash,created_at)"
                     " VALUES(?,?,?,?)",
                     (email, name, generate_password_hash(pw), datetime.utcnow().isoformat()))
        uid = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
        for spec in argv[5:]:
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
        print("user saved:", email)
    elif cmd == "list-users":
        conn = db()
        for u in conn.execute("SELECT * FROM users"):
            grants = conn.execute("SELECT system, identity, extra FROM grants WHERE user_id=?",
                                  (u["id"],)).fetchall()
            print(u["email"], "-", u["name"],
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
