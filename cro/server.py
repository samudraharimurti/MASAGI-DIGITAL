# MASAGI CROM - customer pipeline management for SNI certification & NPT lubricant registration.
# Flask + SQLite, bilingual (EN/ID), light/dark theme. Run: python server.py  ->  http://localhost:8030

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import uuid
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import reports
from database import (BASE, DATA_DIR, DB_PATH, POST_CERT, UPLOAD_DIR, add_months,
                      connect, create_stages, init_db, invoice_total)
from i18n import MONTHS, translate

PORT = int(os.environ.get("CROM_PORT", "8016"))
ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg", "xlsx", "xls", "docx", "doc", "zip", "csv"}
LOGIN_ATTEMPTS = {}  # email -> [timestamps of failures]

init_db()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

_secret_file = os.path.join(DATA_DIR, ".secret_key")
if not os.path.exists(_secret_file):
    with open(_secret_file, "w") as f:
        f.write(secrets.token_hex(32))
with open(_secret_file) as f:
    app.secret_key = f.read().strip()


# ------------------------------------------------------------------ helpers

def db():
    if "db" not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def q(sql, args=()):
    return db().execute(sql, args).fetchall()


def q1(sql, args=()):
    return db().execute(sql, args).fetchone()


def commit():
    db().commit()


def get_lang():
    lang = request.cookies.get("lang", "en")
    return lang if lang in ("en", "id") else "en"


def t(key):
    return translate(get_lang(), key)


def fmt_money(v):
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        v = 0
    return "Rp " + f"{v:,.0f}".replace(",", ".")


def fmt_date(iso):
    if not iso:
        return "-"
    s = str(iso)[:10]
    try:
        d = date.fromisoformat(s)
    except ValueError:
        return s
    return f"{d.day} {MONTHS[get_lang()][d.month - 1]} {d.year}"


def fmt_dt(iso):
    if not iso:
        return "-"
    s = str(iso)
    return fmt_date(s[:10]) + (" " + s[11:16] if len(s) >= 16 else "")


def days_until(iso):
    if not iso:
        return None
    try:
        return (date.fromisoformat(str(iso)[:10]) - date.today()).days
    except ValueError:
        return None


def stage_name(row):
    return row["name_id"] if get_lang() == "id" else row["name_en"]


def stage_note(row):
    return row["note_id"] if get_lang() == "id" else row["note_en"]


def get_settings():
    return {r["key"]: r["value"] for r in q("SELECT key, value FROM settings")}


def current_user():
    if "user" not in g:
        g.user = None
        uid = session.get("uid")
        if uid:
            row = q1("SELECT * FROM users WHERE id=? AND active=1", (uid,))
            g.user = row
    return g.user


def log(action, details, sub=None, inv=None):
    u = current_user()
    db().execute(
        "INSERT INTO activity(user_id, submission_id, invoice_id, action, details) VALUES(?,?,?,?,?)",
        (u["id"] if u else None, sub, inv, action, details))


def notify(uid, ten, tid, ben, bid, link=""):
    db().execute(
        "INSERT INTO notifications(user_id, title_en, title_id, body_en, body_id, link) VALUES(?,?,?,?,?,?)",
        (uid, ten, tid, ben, bid, link))


def notify_staff(ten, tid, ben, bid, link="", admins_only=False):
    roles = ("admin",) if admins_only else ("admin", "inputter")
    for r in q(f"SELECT id FROM users WHERE active=1 AND role IN ({','.join('?' * len(roles))})", roles):
        notify(r["id"], ten, tid, ben, bid, link)


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapper


def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                return redirect(url_for("login"))
            if u["role"] not in roles:
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


@app.before_request
def before():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST":
        if request.form.get("csrf") != session["csrf"]:
            abort(400)


# Helper *functions* are registered as Jinja globals (not context vars) so that
# macros imported via {% from %} can see them too.
app.jinja_env.globals.update(t=t, fmt_money=fmt_money, fmt_date=fmt_date, fmt_dt=fmt_dt,
                             days_until=days_until, stage_name=stage_name, stage_note=stage_note)


@app.context_processor
def inject():
    u = current_user()
    unread = 0
    if u:
        unread = q1("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", (u["id"],))["c"]
    return dict(lang=get_lang(), user=u, csrf=session.get("csrf", ""), unread=unread,
                settings=get_settings(), today=date.today().isoformat())


def invoice_paid(iid):
    return q1("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE invoice_id=? AND confirmed=1", (iid,))["s"]


def recompute_invoice(iid):
    inv = q1("SELECT * FROM invoices WHERE id=?", (iid,))
    if not inv or inv["status"] in ("DRAFT", "CANCELLED"):
        return
    paid = invoice_paid(iid)
    if paid >= inv["total"] - 1:
        pd = q1("SELECT MAX(pay_date) m FROM payments WHERE invoice_id=? AND confirmed=1", (iid,))["m"]
        db().execute("UPDATE invoices SET status='PAID', paid_date=? WHERE id=?", (pd, iid))
    elif paid > 0:
        db().execute("UPDATE invoices SET status='PARTIAL', paid_date=NULL WHERE id=?", (iid,))
    else:
        db().execute("UPDATE invoices SET status='SENT', paid_date=NULL WHERE id=?", (iid,))


def invoice_rows(where="", args=()):
    rows = q(f"""SELECT i.*, u.company, u.name AS client_name,
                        (SELECT code FROM submissions s WHERE s.id = i.submission_id) AS sub_code,
                        COALESCE((SELECT SUM(p.amount) FROM payments p
                                  WHERE p.invoice_id = i.id AND p.confirmed = 1), 0) AS paid
                 FROM invoices i JOIN users u ON u.id = i.client_id {where}
                 ORDER BY i.id DESC""", args)
    out = []
    today = date.today().isoformat()
    for r in rows:
        d = dict(r)
        d["disp"] = "OVERDUE" if (d["status"] in ("SENT", "PARTIAL") and (d["due_date"] or "9999") < today) \
            else d["status"]
        out.append(d)
    return out


def submission_rows(where="", args=()):
    return q(f"""SELECT s.*, u.company, u.name AS client_name,
                        (SELECT st.name_en FROM stages st WHERE st.submission_id = s.id
                          AND st.status IN ('IN_PROGRESS','ACTION') ORDER BY st.ord LIMIT 1) AS cur_en,
                        (SELECT st.name_id FROM stages st WHERE st.submission_id = s.id
                          AND st.status IN ('IN_PROGRESS','ACTION') ORDER BY st.ord LIMIT 1) AS cur_id,
                        (SELECT COUNT(*) FROM stages st WHERE st.submission_id = s.id
                          AND st.status = 'COMPLETED') AS done_n,
                        (SELECT COUNT(*) FROM stages st WHERE st.submission_id = s.id) AS total_n
                 FROM submissions s JOIN users u ON u.id = s.client_id {where}
                 ORDER BY s.id DESC""", args)


# --------------------------------------------------------------------- auth

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("home"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        now = time.time()
        attempts = [ts for ts in LOGIN_ATTEMPTS.get(email, []) if now - ts < 600]
        if len(attempts) >= 5:
            flash(t("locked_out"), "error")
            return render_template("login.html")
        row = q1("SELECT * FROM users WHERE lower(email)=? AND active=1", (email,))
        if row and check_password_hash(row["password_hash"], pw):
            LOGIN_ATTEMPTS.pop(email, None)
            session["uid"] = row["id"]
            session["csrf"] = secrets.token_hex(16)
            return redirect(url_for("home"))
        attempts.append(now)
        LOGIN_ATTEMPTS[email] = attempts
        flash(t("bad_login"), "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- MASAGI Account SSO -----------------------------------------------------
# account.masagi.io signs a short-lived token; this endpoint verifies it and
# opens a normal session for the mapped local user. Shared secret lives in
# <repo>/data/portal/sso_secret (created by the portal app on first run).

SSO_SECRET_FILE = os.environ.get("SSO_SECRET_FILE") or os.path.join(
    BASE, os.pardir, "data", "portal", "sso_secret")


def _sso_secret():
    try:
        with open(SSO_SECRET_FILE) as f:
            return f.read().strip()
    except OSError:
        return None


@app.route("/sso")
def sso_login():
    secret = _sso_secret()
    token = request.args.get("token", "")
    if not secret or "." not in token:
        abort(403)
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        abort(403)
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, TypeError):
        abort(400)
    if payload.get("sys") != "crom" or payload.get("exp", 0) < time.time():
        abort(403)
    row = q1("SELECT * FROM users WHERE lower(email)=? AND active=1",
             ((payload.get("email") or "").strip().lower(),))
    if not row:
        abort(403)
    session.clear()
    session["uid"] = row["id"]
    session["csrf"] = secrets.token_hex(16)
    return redirect(url_for("home"))


@app.route("/")
def home():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    return redirect(url_for("portal") if u["role"] == "client" else url_for("dashboard"))


@app.route("/lang/<code>")
def set_lang(code):
    resp = redirect(request.referrer or url_for("home"))
    if code in ("en", "id"):
        resp.set_cookie("lang", code, max_age=365 * 24 * 3600)
    return resp


# ---------------------------------------------------------------- dashboard

@app.route("/dashboard")
@role_required("admin", "inputter")
def dashboard():
    today = date.today().isoformat()
    kpis = {
        "active": q1("SELECT COUNT(*) c FROM submissions WHERE status='ACTIVE'")["c"],
        "certified": q1("SELECT COUNT(*) c FROM submissions WHERE status='CERTIFIED'")["c"],
        "overdue": q1("""SELECT COUNT(*) c FROM stages st JOIN submissions s ON s.id=st.submission_id
                         WHERE st.status IN ('IN_PROGRESS','ACTION') AND s.status='ACTIVE'
                           AND COALESCE(st.action_due, st.est_end) < ?""", (today,))["c"],
        "outstanding": q1("""SELECT COALESCE(SUM(i.total - COALESCE((SELECT SUM(p.amount) FROM payments p
                                 WHERE p.invoice_id=i.id AND p.confirmed=1),0)),0) s
                             FROM invoices i WHERE i.status IN ('SENT','PARTIAL')""")["s"],
    }

    def pipeline(stype):
        return q("""SELECT tpl.ord, tpl.name_en, tpl.name_id,
                           (SELECT COUNT(*) FROM stages st JOIN submissions s ON s.id=st.submission_id
                             WHERE s.status='ACTIVE' AND s.service_type=tpl.service_type
                               AND st.key=tpl.key AND st.status IN ('IN_PROGRESS','ACTION')) c
                    FROM stage_templates tpl WHERE tpl.service_type=? ORDER BY tpl.ord""", (stype,))

    pipe_sni, pipe_npt = pipeline("SNI"), pipeline("NPT")
    pipe_max = max([r["c"] for r in pipe_sni] + [r["c"] for r in pipe_npt] + [1])
    dist = {r["service_type"]: r["c"] for r in
            q("SELECT service_type, COUNT(*) c FROM submissions WHERE status='ACTIVE' GROUP BY service_type")}
    dist_total = max(sum(dist.values()), 1)

    deadlines = q("""SELECT s.id sid, s.code, u.company, st.name_en, st.name_id, st.status st_status,
                            COALESCE(st.action_due, st.est_end) due
                     FROM stages st JOIN submissions s ON s.id=st.submission_id
                     JOIN users u ON u.id = s.client_id
                     WHERE st.status IN ('IN_PROGRESS','ACTION') AND s.status='ACTIVE'
                       AND COALESCE(st.action_due, st.est_end) <= date(?, '+14 day')
                     ORDER BY due""", (today,))

    compliance = []
    for r in q("""SELECT id, code, product_name, service_type, next_surveillance, cert_expiry
                  FROM submissions WHERE status='CERTIFIED'"""):
        if r["next_surveillance"] and r["next_surveillance"] <= add_months(today, 3):
            compliance.append({"sid": r["id"], "code": r["code"], "kind": "cycle",
                               "service_type": r["service_type"], "due": r["next_surveillance"]})
        if r["cert_expiry"] and r["cert_expiry"] <= add_months(today, 6):
            compliance.append({"sid": r["id"], "code": r["code"], "kind": "expiry",
                               "service_type": r["service_type"], "due": r["cert_expiry"]})
    compliance.sort(key=lambda x: x["due"])

    month_start = today[:8] + "01"
    revenue = {
        "invoiced": q1("""SELECT COALESCE(SUM(total),0) s FROM invoices
                          WHERE issue_date >= ? AND status NOT IN ('DRAFT','CANCELLED')""", (month_start,))["s"],
        "collected": q1("""SELECT COALESCE(SUM(amount),0) s FROM payments
                           WHERE confirmed=1 AND pay_date >= ?""", (month_start,))["s"],
        "outstanding": kpis["outstanding"],
    }
    activity = q("""SELECT a.*, u.name uname FROM activity a LEFT JOIN users u ON u.id=a.user_id
                    ORDER BY a.id DESC LIMIT 12""")
    return render_template("dashboard.html", kpis=kpis, pipe_sni=pipe_sni, pipe_npt=pipe_npt,
                           pipe_max=pipe_max, dist=dist, dist_total=dist_total, deadlines=deadlines,
                           compliance=compliance, revenue=revenue, activity=activity)


# -------------------------------------------------------------- submissions

@app.route("/submissions")
@role_required("admin", "inputter")
def submissions():
    stype = request.args.get("type", "")
    status = request.args.get("status", "")
    term = (request.args.get("q") or "").strip()
    where, args = [], []
    if stype in ("SNI", "NPT"):
        where.append("s.service_type=?"); args.append(stype)
    if status:
        where.append("s.status=?"); args.append(status)
    if term:
        where.append("(s.code LIKE ? OR s.product_name LIKE ? OR u.company LIKE ?)")
        args += [f"%{term}%"] * 3
    rows = submission_rows(("WHERE " + " AND ".join(where)) if where else "", tuple(args))
    return render_template("submissions.html", rows=rows, f_type=stype, f_status=status, f_q=term)


@app.route("/submissions/new", methods=["GET", "POST"])
@role_required("admin")
def submission_new():
    clients = q("SELECT id, name, company FROM users WHERE role='client' AND active=1 ORDER BY company")
    if request.method == "POST":
        client_id = request.form.get("client_id")
        stype = request.form.get("service_type")
        product = (request.form.get("product_name") or "").strip()
        if not (client_id and stype in ("SNI", "NPT") and product):
            flash(t("err_required"), "error")
            return render_template("submission_new.html", clients=clients)
        year = date.today().year
        seq = q1("SELECT COUNT(*) c FROM submissions WHERE service_type=? AND code LIKE ?",
                 (stype, f"{stype}-{year}-%"))["c"] + 1
        code = f"{stype}-{year}-{seq:04d}"
        today = date.today().isoformat()
        cur = db().execute(
            """INSERT INTO submissions(code, client_id, service_type, product_name, brand, standard_ref,
                                       product_desc, status, submitted_at, created_by)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (code, client_id, stype, product, request.form.get("brand", "").strip(),
             request.form.get("standard_ref", "").strip(), request.form.get("product_desc", "").strip(),
             "ACTIVE", today, current_user()["id"]))
        sid = cur.lastrowid
        create_stages(db(), sid, stype, today)
        log("create", f"{code} created ({product})", sub=sid)
        notify(int(client_id),
               "New submission registered", "Pengajuan baru terdaftar",
               f"{code} - {product} has been registered and the pipeline has started.",
               f"{code} - {product} telah terdaftar dan pipeline telah dimulai.",
               f"/portal/submissions/{sid}")
        commit()
        flash(t("flash_submission_created"), "ok")
        return redirect(url_for("submission_detail", sid=sid))
    return render_template("submission_new.html", clients=clients)


def _get_submission(sid, allow_client=False):
    s = q1("""SELECT s.*, u.name client_name, u.company, u.email client_email
              FROM submissions s JOIN users u ON u.id=s.client_id WHERE s.id=?""", (sid,))
    if not s:
        abort(404)
    u = current_user()
    if u["role"] == "client":
        if not allow_client or s["client_id"] != u["id"]:
            abort(403)
    return s


def _detail_ctx(sid):
    stages = q("SELECT * FROM stages WHERE submission_id=? ORDER BY ord", (sid,))
    docs = q("""SELECT d.*, u.name uname FROM documents d LEFT JOIN users u ON u.id=d.uploaded_by
                WHERE d.submission_id=? ORDER BY d.id DESC""", (sid,))
    comments = q("""SELECT c.*, u.name uname, u.role urole FROM comments c
                    LEFT JOIN users u ON u.id=c.user_id
                    WHERE c.submission_id=? ORDER BY c.id""", (sid,))
    invoices = invoice_rows("WHERE i.submission_id=?", (sid,))
    return stages, docs, comments, invoices


@app.route("/submissions/<int:sid>")
@role_required("admin", "inputter")
def submission_detail(sid):
    s = _get_submission(sid)
    stages, docs, comments, invoices = _detail_ctx(sid)
    current = next((x for x in stages if x["status"] in ("IN_PROGRESS", "ACTION")), None)
    reg_days = {r["key"]: r["days"] for r in
                q("SELECT key, days FROM stage_templates WHERE service_type=?", (s["service_type"],))}
    activity = q("""SELECT a.*, u.name uname FROM activity a LEFT JOIN users u ON u.id=a.user_id
                    WHERE a.submission_id=? ORDER BY a.id DESC LIMIT 10""", (sid,))
    return render_template("submission_detail.html", s=s, stages=stages, current=current,
                           reg_days=reg_days, docs=docs, comments=comments, invoices=invoices,
                           activity=activity)


def _get_stage_for_update(st_id):
    st = q1("SELECT * FROM stages WHERE id=?", (st_id,))
    if not st:
        abort(404)
    s = q1("SELECT * FROM submissions WHERE id=?", (st["submission_id"],))
    return st, s


@app.route("/stages/<int:st_id>/complete", methods=["POST"])
@role_required("admin", "inputter")
def stage_complete(st_id):
    st, s = _get_stage_for_update(st_id)
    if s["status"] != "ACTIVE" or st["status"] not in ("IN_PROGRESS", "ACTION"):
        abort(400)
    today = date.today().isoformat()
    db().execute("UPDATE stages SET status='COMPLETED', completed_at=?, action_due=NULL WHERE id=?",
                 (today, st_id))
    nxt = q1("SELECT * FROM stages WHERE submission_id=? AND ord=?", (s["id"], st["ord"] + 1))
    if nxt:
        est = (date.today() + timedelta(days=nxt["days"] or 7)).isoformat()
        db().execute("UPDATE stages SET status='IN_PROGRESS', entered_at=?, est_end=? WHERE id=?",
                     (today, est, nxt["id"]))
        log("stage", f"{s['code']}: {st['name_en']} completed -> {nxt['name_en']}", sub=s["id"])
        notify(s["client_id"], "Stage update", "Pembaruan tahap",
               f"{s['code']} moved to: {nxt['name_en']}.",
               f"{s['code']} memasuki tahap: {nxt['name_id']}.",
               f"/portal/submissions/{s['id']}")
        flash(t("flash_stage_completed"), "ok")
    else:
        cert_no = (request.form.get("cert_number") or "").strip()
        pc = POST_CERT[s["service_type"]]
        db().execute("""UPDATE submissions SET status='CERTIFIED', cert_number=?, certified_at=?,
                        cert_expiry=?, next_surveillance=? WHERE id=?""",
                     (cert_no, today, add_months(today, pc["validity_months"]),
                      add_months(today, pc["cycle_months"]), s["id"]))
        log("certified", f"{s['code']} certified ({cert_no or 'no number'})", sub=s["id"])
        notify(s["client_id"], "Certificate issued!", "Sertifikat terbit!",
               f"{s['code']} - {s['product_name']} is now certified. Number: {cert_no or '-'}.",
               f"{s['code']} - {s['product_name']} telah tersertifikasi. Nomor: {cert_no or '-'}.",
               f"/portal/submissions/{s['id']}")
        flash(t("flash_certified"), "ok")
    commit()
    return redirect(url_for("submission_detail", sid=s["id"]))


@app.route("/stages/<int:st_id>/corrective", methods=["POST"])
@role_required("admin", "inputter")
def stage_corrective(st_id):
    st, s = _get_stage_for_update(st_id)
    if s["status"] != "ACTIVE" or st["status"] != "IN_PROGRESS":
        abort(400)
    try:
        days = max(1, min(180, int(request.form.get("days") or 30)))
    except ValueError:
        days = 30
    due = (date.today() + timedelta(days=days)).isoformat()
    note = (request.form.get("note") or "").strip()
    db().execute("UPDATE stages SET status='ACTION', action_due=? WHERE id=?", (due, st_id))
    if note:
        db().execute("UPDATE stages SET client_notes = client_notes || ? WHERE id=?",
                     (("\n" if st["client_notes"] else "") + note, st_id))
    log("corrective", f"{s['code']}: corrective action on {st['name_en']} ({days}d)", sub=s["id"])
    notify(s["client_id"], "Corrective action required", "Tindakan koreksi diperlukan",
           f"{s['code']}: corrective action required at stage {st['name_en']} (deadline {due}).",
           f"{s['code']}: tindakan koreksi diperlukan pada tahap {st['name_id']} (batas {due}).",
           f"/portal/submissions/{s['id']}")
    commit()
    flash(t("flash_corrective"), "ok")
    return redirect(url_for("submission_detail", sid=s["id"]))


@app.route("/stages/<int:st_id>/resume", methods=["POST"])
@role_required("admin", "inputter")
def stage_resume(st_id):
    st, s = _get_stage_for_update(st_id)
    if st["status"] != "ACTION":
        abort(400)
    db().execute("UPDATE stages SET status='IN_PROGRESS', action_due=NULL WHERE id=?", (st_id,))
    log("stage", f"{s['code']}: {st['name_en']} resumed after corrective action", sub=s["id"])
    commit()
    flash(t("flash_resumed"), "ok")
    return redirect(url_for("submission_detail", sid=s["id"]))


@app.route("/stages/<int:st_id>/revert", methods=["POST"])
@role_required("admin", "inputter")
def stage_revert(st_id):
    st, s = _get_stage_for_update(st_id)
    if s["status"] != "ACTIVE":
        abort(400)
    today = date.today().isoformat()
    est = (date.today() + timedelta(days=st["days"] or 7)).isoformat()
    db().execute("""UPDATE stages SET status='PENDING', entered_at=NULL, est_end=NULL,
                    completed_at=NULL, action_due=NULL WHERE submission_id=? AND ord>?""",
                 (s["id"], st["ord"]))
    db().execute("""UPDATE stages SET status='IN_PROGRESS', entered_at=?, est_end=?, completed_at=NULL,
                    action_due=NULL, cycle=cycle+1 WHERE id=?""", (today, est, st_id))
    log("revert", f"{s['code']}: pipeline restarted from {st['name_en']} (cycle {st['cycle'] + 1})", sub=s["id"])
    notify(s["client_id"], "Stage repeated", "Tahap diulang",
           f"{s['code']}: the process returned to stage {st['name_en']}.",
           f"{s['code']}: proses kembali ke tahap {st['name_id']}.",
           f"/portal/submissions/{s['id']}")
    commit()
    flash(t("flash_reverted"), "ok")
    return redirect(url_for("submission_detail", sid=s["id"]))


@app.route("/stages/<int:st_id>/fail", methods=["POST"])
@role_required("admin")
def stage_fail(st_id):
    st, s = _get_stage_for_update(st_id)
    if s["status"] != "ACTIVE":
        abort(400)
    db().execute("UPDATE stages SET status='FAILED' WHERE id=?", (st_id,))
    db().execute("UPDATE submissions SET status='REJECTED' WHERE id=?", (s["id"],))
    log("rejected", f"{s['code']} rejected at {st['name_en']}", sub=s["id"])
    notify(s["client_id"], "Submission rejected", "Pengajuan ditolak",
           f"{s['code']} was rejected at stage {st['name_en']}. Contact us for the next steps.",
           f"{s['code']} ditolak pada tahap {st['name_id']}. Hubungi kami untuk langkah selanjutnya.",
           f"/portal/submissions/{s['id']}")
    commit()
    flash(t("flash_failed"), "ok")
    return redirect(url_for("submission_detail", sid=s["id"]))


@app.route("/stages/<int:st_id>/notes", methods=["POST"])
@role_required("admin", "inputter")
def stage_notes(st_id):
    st, s = _get_stage_for_update(st_id)
    db().execute("UPDATE stages SET internal_notes=?, client_notes=? WHERE id=?",
                 ((request.form.get("internal_notes") or "").strip(),
                  (request.form.get("client_notes") or "").strip(), st_id))
    commit()
    flash(t("flash_notes"), "ok")
    return redirect(url_for("submission_detail", sid=s["id"]))


@app.route("/stages/<int:st_id>/plandays", methods=["POST"])
@role_required("admin", "inputter")
def stage_plandays(st_id):
    """Admin/inputter can adjust the planned duration of a stage (vs the regulatory default)."""
    st, s = _get_stage_for_update(st_id)
    try:
        days = max(1, min(365, int(request.form.get("days") or st["days"])))
    except (ValueError, TypeError):
        days = st["days"]
    # A running stage recalculates its estimated end from the entry date; others just store the plan.
    if st["entered_at"] and st["status"] in ("IN_PROGRESS", "ACTION"):
        est = (date.fromisoformat(st["entered_at"][:10]) + timedelta(days=days)).isoformat()
        db().execute("UPDATE stages SET days=?, est_end=? WHERE id=?", (days, est, st_id))
    else:
        db().execute("UPDATE stages SET days=? WHERE id=?", (days, st_id))
    log("plandays", f"{s['code']}: {st['name_en']} plan set to {days} days", sub=s["id"])
    commit()
    flash(t("flash_plandays"), "ok")
    return redirect(url_for("submission_detail", sid=s["id"]))


@app.route("/submissions/<int:sid>/hold", methods=["POST"])
@role_required("admin")
def submission_hold(sid):
    s = _get_submission(sid)
    if s["status"] == "ACTIVE":
        db().execute("UPDATE submissions SET status='ON_HOLD' WHERE id=?", (sid,))
        log("hold", f"{s['code']} put on hold", sub=sid)
        commit()
        flash(t("flash_hold"), "ok")
    elif s["status"] == "ON_HOLD":
        db().execute("UPDATE submissions SET status='ACTIVE' WHERE id=?", (sid,))
        log("hold", f"{s['code']} resumed from hold", sub=sid)
        commit()
        flash(t("flash_unhold"), "ok")
    return redirect(url_for("submission_detail", sid=sid))


@app.route("/submissions/<int:sid>/surveillance", methods=["POST"])
@role_required("admin", "inputter")
def surveillance_done(sid):
    s = _get_submission(sid)
    if s["status"] != "CERTIFIED" or not s["next_surveillance"]:
        abort(400)
    pc = POST_CERT[s["service_type"]]
    nxt = add_months(s["next_surveillance"], pc["cycle_months"])
    db().execute("UPDATE submissions SET next_surveillance=? WHERE id=?", (nxt, sid))
    kind = "annual surveillance" if s["service_type"] == "SNI" else "quarterly report"
    log("compliance", f"{s['code']}: {kind} cycle completed, next due {nxt}", sub=sid)
    commit()
    flash(t("flash_surv"), "ok")
    return redirect(url_for("submission_detail", sid=sid))


@app.route("/submissions/<int:sid>/comment", methods=["POST"])
@login_required
def submission_comment(sid):
    s = _get_submission(sid, allow_client=True)
    u = current_user()
    body = (request.form.get("body") or "").strip()
    if not body:
        return redirect(request.referrer or url_for("home"))
    internal = 1 if (u["role"] in ("admin", "inputter") and request.form.get("internal")) else 0
    db().execute("INSERT INTO comments(submission_id, user_id, body, internal) VALUES(?,?,?,?)",
                 (sid, u["id"], body, internal))
    if u["role"] == "client":
        notify_staff("Client comment", "Komentar klien",
                     f"{s['code']}: {u['name']} wrote: {body[:120]}",
                     f"{s['code']}: {u['name']} menulis: {body[:120]}",
                     f"/submissions/{sid}")
    elif not internal:
        notify(s["client_id"], "New message", "Pesan baru",
               f"{s['code']}: {body[:120]}", f"{s['code']}: {body[:120]}",
               f"/portal/submissions/{sid}")
    commit()
    flash(t("flash_comment"), "ok")
    return redirect(request.referrer or url_for("home"))


@app.route("/submissions/<int:sid>/upload", methods=["POST"])
@login_required
def submission_upload(sid):
    s = _get_submission(sid, allow_client=True)
    u = current_user()
    f = request.files.get("file")
    if not f or not f.filename:
        flash(t("err_file_missing"), "error")
        return redirect(request.referrer or url_for("home"))
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        flash(t("err_file_type"), "error")
        return redirect(request.referrer or url_for("home"))
    sub_dir = os.path.join(UPLOAD_DIR, f"sub_{sid}")
    os.makedirs(sub_dir, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(sub_dir, stored))
    category = "CLIENT_UPLOAD" if u["role"] == "client" else \
        (request.form.get("category") if request.form.get("category") in ("INTERNAL", "CERTIFICATE") else "INTERNAL")
    fname = secure_filename(f.filename) or stored
    db().execute("""INSERT INTO documents(submission_id, uploaded_by, file_name, stored_name, category)
                    VALUES(?,?,?,?,?)""", (sid, u["id"], fname, stored, category))
    log("document", f"{s['code']}: uploaded {fname}", sub=sid)
    if u["role"] == "client":
        notify_staff("Client document", "Dokumen klien",
                     f"{s['code']}: {u['name']} uploaded {fname}",
                     f"{s['code']}: {u['name']} mengunggah {fname}",
                     f"/submissions/{sid}")
    else:
        notify(s["client_id"], "New document", "Dokumen baru",
               f"{s['code']}: document {fname} is available.",
               f"{s['code']}: dokumen {fname} telah tersedia.",
               f"/portal/submissions/{sid}")
    commit()
    flash(t("flash_doc"), "ok")
    return redirect(request.referrer or url_for("home"))


@app.route("/files/<int:doc_id>")
@login_required
def download_doc(doc_id):
    d = q1("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not d:
        abort(404)
    u = current_user()
    if u["role"] == "client":
        s = q1("SELECT client_id FROM submissions WHERE id=?", (d["submission_id"],))
        if not s or s["client_id"] != u["id"] or d["category"] == "INTERNAL":
            abort(403)
    return send_from_directory(os.path.join(UPLOAD_DIR, f"sub_{d['submission_id']}"),
                               d["stored_name"], as_attachment=True, download_name=d["file_name"])


# ------------------------------------------------------------------ portal

@app.route("/portal")
@role_required("client")
def portal():
    u = current_user()
    subs = submission_rows("WHERE s.client_id=?", (u["id"],))
    invoices = invoice_rows("WHERE i.client_id=? AND i.status != 'DRAFT'", (u["id"],))
    notes = q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 6", (u["id"],))
    return render_template("portal.html", subs=subs, invoices=invoices, notes=notes)


@app.route("/portal/submissions/<int:sid>")
@role_required("client")
def portal_submission(sid):
    s = _get_submission(sid, allow_client=True)
    stages, docs, comments, invoices = _detail_ctx(sid)
    docs = [d for d in docs if d["category"] != "INTERNAL"]
    comments = [c for c in comments if not c["internal"]]
    current = next((x for x in stages if x["status"] in ("IN_PROGRESS", "ACTION")), None)
    return render_template("portal_submission.html", s=s, stages=stages, current=current,
                           docs=docs, comments=comments, invoices=invoices)


# ---------------------------------------------------------------- invoices

@app.route("/invoices")
@login_required
def invoices_list():
    u = current_user()
    if u["role"] == "client":
        rows = invoice_rows("WHERE i.client_id=? AND i.status != 'DRAFT'", (u["id"],))
    elif u["role"] == "admin":
        rows = invoice_rows()
    else:
        abort(403)
    return render_template("invoices.html", rows=rows)


@app.route("/invoices/new", methods=["GET", "POST"])
@role_required("admin")
def invoice_new():
    clients = q("SELECT id, name, company FROM users WHERE role='client' AND active=1 ORDER BY company")
    subs = q("""SELECT s.id, s.code, s.client_id, s.product_name FROM submissions s
                WHERE s.status IN ('ACTIVE','CERTIFIED') ORDER BY s.id DESC""")
    st = get_settings()
    if request.method == "POST":
        client_id = request.form.get("client_id")
        descs = request.form.getlist("item_desc")
        qtys = request.form.getlist("item_qty")
        prices = request.form.getlist("item_price")
        items = []
        for d_, qv, pv in zip(descs, qtys, prices):
            d_ = (d_ or "").strip()
            try:
                qf, pf = float(qv or 0), float(pv or 0)
            except ValueError:
                qf = pf = 0
            if d_ and qf > 0 and pf > 0:
                items.append((d_, qf, pf))
        if not client_id or not items:
            flash(t("err_invoice_items"), "error")
            return render_template("invoice_new.html", clients=clients, subs=subs, st=st)
        tax_mode = request.form.get("tax_mode") or st.get("tax_mode") or "PPh"
        if tax_mode not in ("PPh", "PPN", "NONE"):
            tax_mode = "PPh"
        default_pct = st.get("pph_percent" if tax_mode == "PPh" else "ppn_percent") or "0"
        try:
            tax_pct = float(request.form.get("tax_percent") or default_pct)
        except ValueError:
            tax_pct = float(default_pct or 0)
        if tax_mode == "NONE":
            tax_pct = 0
        subtotal = sum(qf * pf for _, qf, pf in items)
        tax, total = invoice_total(subtotal, tax_mode, tax_pct)
        year = date.today().year
        seq = q1("SELECT COUNT(*) c FROM invoices WHERE number LIKE ?", (f"INV-{year}-%",))["c"] + 1
        number = f"INV-{year}-{seq:04d}"
        sub_id = request.form.get("submission_id") or None
        if sub_id:
            owner = q1("SELECT client_id FROM submissions WHERE id=?", (sub_id,))
            if not owner or str(owner["client_id"]) != str(client_id):
                sub_id = None
        cur = db().execute(
            """INSERT INTO invoices(number, client_id, submission_id, status, issue_date, due_date,
                                    subtotal, tax_mode, tax_percent, tax_amount, total, notes, created_by)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (number, client_id, sub_id, "DRAFT",
             request.form.get("issue_date") or date.today().isoformat(),
             request.form.get("due_date") or (date.today() + timedelta(days=30)).isoformat(),
             subtotal, tax_mode, tax_pct, tax, total,
             (request.form.get("notes") or "").strip(), current_user()["id"]))
        inv_id = cur.lastrowid
        for d_, qf, pf in items:
            db().execute("INSERT INTO invoice_items(invoice_id, description, qty, unit_price, total) "
                         "VALUES(?,?,?,?,?)", (inv_id, d_, qf, pf, qf * pf))
        log("invoice", f"{number} created", inv=inv_id)
        commit()
        flash(t("flash_invoice_created"), "ok")
        return redirect(url_for("invoice_detail", iid=inv_id))
    return render_template("invoice_new.html", clients=clients, subs=subs, st=st)


def _get_invoice(iid):
    inv = q1("""SELECT i.*, u.name client_name, u.company, u.email client_email, u.phone client_phone
                FROM invoices i JOIN users u ON u.id=i.client_id WHERE i.id=?""", (iid,))
    if not inv:
        abort(404)
    u = current_user()
    if u["role"] == "client" and (inv["client_id"] != u["id"] or inv["status"] == "DRAFT"):
        abort(403)
    if u["role"] == "inputter":
        abort(403)
    return inv


@app.route("/invoices/<int:iid>")
@login_required
def invoice_detail(iid):
    inv = _get_invoice(iid)
    items = q("SELECT * FROM invoice_items WHERE invoice_id=?", (iid,))
    pays = q("""SELECT p.*, u.name uname FROM payments p LEFT JOIN users u ON u.id=p.created_by
                WHERE p.invoice_id=? ORDER BY p.id""", (iid,))
    paid = invoice_paid(iid)
    sub = q1("SELECT id, code, product_name FROM submissions WHERE id=?", (inv["submission_id"],)) \
        if inv["submission_id"] else None
    overdue = inv["status"] in ("SENT", "PARTIAL") and (inv["due_date"] or "9999") < date.today().isoformat()
    return render_template("invoice_detail.html", inv=inv, items=items, pays=pays, paid=paid,
                           balance=inv["total"] - paid, sub=sub, overdue=overdue)


@app.route("/invoices/<int:iid>/print")
@login_required
def invoice_print(iid):
    inv = _get_invoice(iid)
    items = q("SELECT * FROM invoice_items WHERE invoice_id=?", (iid,))
    paid = invoice_paid(iid)
    return render_template("invoice_print.html", inv=inv, items=items, paid=paid,
                           balance=inv["total"] - paid)


@app.route("/invoices/<int:iid>/send", methods=["POST"])
@role_required("admin")
def invoice_send(iid):
    inv = _get_invoice(iid)
    if inv["status"] != "DRAFT":
        abort(400)
    db().execute("UPDATE invoices SET status='SENT' WHERE id=?", (iid,))
    log("invoice", f"{inv['number']} sent to {inv['company']}", inv=iid)
    notify(inv["client_id"], "Invoice issued", "Faktur diterbitkan",
           f"Invoice {inv['number']} ({fmt_money(inv['total'])}) is due {inv['due_date']}.",
           f"Faktur {inv['number']} ({fmt_money(inv['total'])}) jatuh tempo {inv['due_date']}.",
           f"/invoices/{iid}")
    commit()
    flash(t("flash_invoice_sent"), "ok")
    return redirect(url_for("invoice_detail", iid=iid))


@app.route("/invoices/<int:iid>/cancel", methods=["POST"])
@role_required("admin")
def invoice_cancel(iid):
    inv = _get_invoice(iid)
    if inv["status"] in ("PAID", "CANCELLED"):
        abort(400)
    db().execute("UPDATE invoices SET status='CANCELLED' WHERE id=?", (iid,))
    log("invoice", f"{inv['number']} cancelled", inv=iid)
    commit()
    flash(t("flash_invoice_cancelled"), "ok")
    return redirect(url_for("invoice_detail", iid=iid))


@app.route("/invoices/<int:iid>/payment", methods=["POST"])
@role_required("admin")
def invoice_payment(iid):
    inv = _get_invoice(iid)
    try:
        amount = float(request.form.get("amount") or 0)
    except ValueError:
        amount = 0
    if amount <= 0 or inv["status"] not in ("SENT", "PARTIAL"):
        abort(400)
    u = current_user()
    db().execute("""INSERT INTO payments(invoice_id, amount, pay_date, method, reference, confirmed,
                    confirmed_by, confirmed_at, created_by)
                    VALUES(?,?,?,?,?,1,?,datetime('now'),?)""",
                 (iid, amount, request.form.get("pay_date") or date.today().isoformat(),
                  (request.form.get("method") or "").strip(),
                  (request.form.get("reference") or "").strip(), u["id"], u["id"]))
    recompute_invoice(iid)
    log("payment", f"{inv['number']}: payment {fmt_money(amount)} recorded", inv=iid)
    notify(inv["client_id"], "Payment received", "Pembayaran diterima",
           f"We recorded {fmt_money(amount)} for invoice {inv['number']}. Thank you.",
           f"Kami mencatat {fmt_money(amount)} untuk faktur {inv['number']}. Terima kasih.",
           f"/invoices/{iid}")
    commit()
    flash(t("flash_payment"), "ok")
    return redirect(url_for("invoice_detail", iid=iid))


@app.route("/invoices/<int:iid>/proof", methods=["POST"])
@role_required("client")
def invoice_proof(iid):
    inv = _get_invoice(iid)
    f = request.files.get("file")
    try:
        amount = float(request.form.get("amount") or 0)
    except ValueError:
        amount = 0
    if not f or not f.filename or amount <= 0:
        flash(t("err_required"), "error")
        return redirect(url_for("invoice_detail", iid=iid))
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        flash(t("err_file_type"), "error")
        return redirect(url_for("invoice_detail", iid=iid))
    proof_dir = os.path.join(UPLOAD_DIR, "proofs")
    os.makedirs(proof_dir, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(proof_dir, stored))
    u = current_user()
    db().execute("""INSERT INTO payments(invoice_id, amount, pay_date, method, proof_stored, proof_name,
                    confirmed, created_by) VALUES(?,?,?,?,?,?,0,?)""",
                 (iid, amount, request.form.get("pay_date") or date.today().isoformat(),
                  "Transfer", stored, secure_filename(f.filename) or stored, u["id"]))
    log("payment", f"{inv['number']}: client uploaded payment proof ({fmt_money(amount)})", inv=iid)
    notify_staff("Payment proof uploaded", "Bukti bayar diunggah",
                 f"{inv['company']} uploaded proof for {inv['number']} ({fmt_money(amount)}).",
                 f"{inv['company']} mengunggah bukti untuk {inv['number']} ({fmt_money(amount)}).",
                 f"/invoices/{iid}", admins_only=True)
    commit()
    flash(t("flash_proof"), "ok")
    return redirect(url_for("invoice_detail", iid=iid))


@app.route("/payments/<int:pid>/confirm", methods=["POST"])
@role_required("admin")
def payment_confirm(pid):
    p = q1("SELECT * FROM payments WHERE id=?", (pid,))
    if not p or p["confirmed"]:
        abort(400)
    u = current_user()
    db().execute("UPDATE payments SET confirmed=1, confirmed_by=?, confirmed_at=datetime('now') WHERE id=?",
                 (u["id"], pid))
    recompute_invoice(p["invoice_id"])
    inv = q1("SELECT * FROM invoices WHERE id=?", (p["invoice_id"],))
    log("payment", f"{inv['number']}: payment {fmt_money(p['amount'])} confirmed", inv=inv["id"])
    notify(inv["client_id"], "Payment confirmed", "Pembayaran dikonfirmasi",
           f"Your payment of {fmt_money(p['amount'])} for {inv['number']} has been confirmed.",
           f"Pembayaran Anda sebesar {fmt_money(p['amount'])} untuk {inv['number']} telah dikonfirmasi.",
           f"/invoices/{inv['id']}")
    commit()
    flash(t("flash_payment_confirmed"), "ok")
    return redirect(url_for("invoice_detail", iid=p["invoice_id"]))


@app.route("/proofs/<int:pid>")
@login_required
def download_proof(pid):
    p = q1("SELECT p.*, i.client_id FROM payments p JOIN invoices i ON i.id=p.invoice_id WHERE p.id=?", (pid,))
    if not p or not p["proof_stored"]:
        abort(404)
    u = current_user()
    if u["role"] == "inputter" or (u["role"] == "client" and p["client_id"] != u["id"]):
        abort(403)
    return send_from_directory(os.path.join(UPLOAD_DIR, "proofs"), p["proof_stored"],
                               as_attachment=True, download_name=p["proof_name"])


# ----------------------------------------------------------------- reports

@app.route("/reports")
@role_required("admin", "inputter")
def reports_list():
    rows = q("SELECT * FROM weekly_reports ORDER BY id DESC")
    return render_template("reports.html", rows=rows, llm_on=reports.llm_available())


@app.route("/reports/generate", methods=["POST"])
@role_required("admin")
def reports_generate():
    rid = reports.generate(db(), current_user()["id"])
    log("report", "Weekly report generated")
    commit()
    flash(t("flash_report"), "ok")
    return redirect(url_for("report_detail", rid=rid))


@app.route("/reports/<int:rid>")
@role_required("admin", "inputter")
def report_detail(rid):
    r = q1("SELECT * FROM weekly_reports WHERE id=?", (rid,))
    if not r:
        abort(404)
    import json as _json
    data = _json.loads(r["raw_json"] or "{}")
    return render_template("report_detail.html", r=r, data=data)


# ------------------------------------------------------------------- users

@app.route("/users")
@role_required("admin")
def users_list():
    rows = q("SELECT * FROM users ORDER BY role, company, name")
    return render_template("users.html", rows=rows)


@app.route("/users/new", methods=["GET", "POST"])
@app.route("/users/<int:uid>/edit", methods=["GET", "POST"])
@role_required("admin")
def user_form(uid=None):
    row = q1("SELECT * FROM users WHERE id=?", (uid,)) if uid else None
    if uid and not row:
        abort(404)
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        name = (request.form.get("name") or "").strip()
        role = request.form.get("role")
        pw = request.form.get("password") or ""
        active = 1 if request.form.get("active") else 0
        if not (email and name and role in ("admin", "inputter", "client")):
            flash(t("err_required"), "error")
            return render_template("user_form.html", row=row)
        dupe = q1("SELECT id FROM users WHERE lower(email)=? AND id != ?", (email, uid or 0))
        if dupe:
            flash(t("err_email_taken"), "error")
            return render_template("user_form.html", row=row)
        if uid:
            if uid == current_user()["id"] and not active:
                flash(t("err_self_disable"), "error")
                return render_template("user_form.html", row=row)
            db().execute("""UPDATE users SET email=?, name=?, role=?, company=?, phone=?, active=? WHERE id=?""",
                         (email, name, role, request.form.get("company", "").strip(),
                          request.form.get("phone", "").strip(), active, uid))
            if pw:
                db().execute("UPDATE users SET password_hash=? WHERE id=?",
                             (generate_password_hash(pw), uid))
        else:
            if not pw:
                flash(t("err_required"), "error")
                return render_template("user_form.html", row=row)
            db().execute("""INSERT INTO users(email, password_hash, name, role, company, phone, active)
                            VALUES(?,?,?,?,?,?,?)""",
                         (email, generate_password_hash(pw), name, role,
                          request.form.get("company", "").strip(),
                          request.form.get("phone", "").strip(), active))
        commit()
        flash(t("flash_user_saved"), "ok")
        return redirect(url_for("users_list"))
    return render_template("user_form.html", row=row)


# ---------------------------------------------------------------- settings

@app.route("/settings", methods=["GET", "POST"])
@role_required("admin")
def settings_page():
    if request.method == "POST":
        for key in ("company_name", "company_address", "company_email", "company_phone",
                    "tax_mode", "ppn_percent", "pph_percent", "invoice_footer"):
            if key in request.form:
                db().execute("INSERT INTO settings(key, value) VALUES(?,?) "
                             "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                             (key, request.form.get(key, "").strip()))
        commit()
        flash(t("flash_settings"), "ok")
        return redirect(url_for("settings_page"))
    return render_template("settings.html", llm_on=reports.llm_available())


# ------------------------------------------------------------ notifications

@app.route("/notifications")
@login_required
def notifications_page():
    u = current_user()
    rows = q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100", (u["id"],))
    return render_template("notifications.html", rows=rows)


@app.route("/notifications/read", methods=["POST"])
@login_required
def notifications_read():
    db().execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (current_user()["id"],))
    commit()
    return redirect(url_for("notifications_page"))


@app.errorhandler(403)
def err403(e):
    return render_template("error.html", code=403, message=t("forbidden")), 403


@app.errorhandler(404)
def err404(e):
    return render_template("error.html", code=404, message=t("not_found")), 404


if __name__ == "__main__":
    if "--weekly-report" in sys.argv:
        conn = connect()
        rid = reports.generate(conn, None)
        conn.close()
        print(f"Weekly report #{rid} generated.")
        sys.exit(0)
    print(f"MASAGI CROM running on http://127.0.0.1:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False)
