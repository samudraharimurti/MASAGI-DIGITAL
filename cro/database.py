# MASAGI CROM - schema, regulation-derived stage templates, and demo seed.
#
# Regulatory sources for the pipeline definitions:
#   SNI : Skema Sertifikasi SNI Pelumas Wajib Tipe 5, LSPro Migas LEMIGAS doc D.P.09 rev I.3 (17-03-2023)
#   NPT : Peraturan Menteri ESDM No. 053 Tahun 2006 (Wajib Daftar Pelumas)

import os
import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "crom.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','inputter','client')),
  company TEXT DEFAULT '',
  phone TEXT DEFAULT '',
  active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS stage_templates(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  service_type TEXT NOT NULL,
  ord INTEGER NOT NULL,
  key TEXT NOT NULL,
  name_en TEXT, name_id TEXT,
  days INTEGER,
  note_en TEXT, note_id TEXT
);
CREATE TABLE IF NOT EXISTS submissions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  client_id INTEGER NOT NULL REFERENCES users(id),
  service_type TEXT NOT NULL CHECK(service_type IN ('SNI','NPT')),
  product_name TEXT NOT NULL,
  brand TEXT DEFAULT '',
  standard_ref TEXT DEFAULT '',
  product_desc TEXT DEFAULT '',
  status TEXT DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','CERTIFIED','REJECTED','ON_HOLD')),
  submitted_at TEXT,
  cert_number TEXT DEFAULT '',
  certified_at TEXT,
  cert_expiry TEXT,
  next_surveillance TEXT,
  created_by INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS stages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  ord INTEGER, key TEXT,
  name_en TEXT, name_id TEXT,
  days INTEGER,
  note_en TEXT, note_id TEXT,
  status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING','IN_PROGRESS','COMPLETED','ACTION','FAILED','SKIPPED')),
  entered_at TEXT, est_end TEXT, completed_at TEXT,
  action_due TEXT,
  internal_notes TEXT DEFAULT '',
  client_notes TEXT DEFAULT '',
  cycle INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS invoices(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  number TEXT UNIQUE NOT NULL,
  client_id INTEGER NOT NULL REFERENCES users(id),
  submission_id INTEGER REFERENCES submissions(id),
  status TEXT DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','SENT','PAID','PARTIAL','CANCELLED')),
  issue_date TEXT, due_date TEXT, paid_date TEXT,
  subtotal REAL DEFAULT 0,
  tax_mode TEXT DEFAULT 'PPh' CHECK(tax_mode IN ('PPh','PPN','NONE')),
  tax_percent REAL DEFAULT 2,
  tax_amount REAL DEFAULT 0, total REAL DEFAULT 0,
  notes TEXT DEFAULT '',
  created_by INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS invoice_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  description TEXT, qty REAL DEFAULT 1, unit_price REAL DEFAULT 0, total REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  amount REAL NOT NULL,
  pay_date TEXT, method TEXT DEFAULT '', reference TEXT DEFAULT '',
  proof_stored TEXT DEFAULT '', proof_name TEXT DEFAULT '',
  confirmed INTEGER DEFAULT 0, confirmed_by INTEGER, confirmed_at TEXT,
  created_by INTEGER, created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  uploaded_by INTEGER,
  file_name TEXT, stored_name TEXT,
  category TEXT DEFAULT 'INTERNAL' CHECK(category IN ('CLIENT_UPLOAD','INTERNAL','CERTIFICATE')),
  uploaded_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS comments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  user_id INTEGER,
  body TEXT,
  internal INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS activity(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER, submission_id INTEGER, invoice_id INTEGER,
  action TEXT, details TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title_en TEXT, title_id TEXT, body_en TEXT, body_id TEXT,
  link TEXT DEFAULT '',
  is_read INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS weekly_reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  week_start TEXT, week_end TEXT,
  raw_json TEXT,
  summary_en TEXT, summary_id TEXT,
  llm_used INTEGER DEFAULT 0,
  generated_by INTEGER,
  generated_at TEXT DEFAULT (datetime('now'))
);
"""

# (service, ord, key, name_en, name_id, planned_days, note_en, note_id)
STAGE_TEMPLATES = [
    # --- SNI Type 5 (LSPro LEMIGAS D.P.09): Seleksi > Determinasi > Tinjauan & Keputusan > Lisensi ---
    ("SNI", 1, "seleksi",
     "Application & Document Selection",
     "Permohonan & Seleksi Dokumen", 10,
     "Tahap I Seleksi: 18 requirement items (deed, IUI, trademark/licence, NPWP, ISO 9001:2015 QMS documents, "
     "process map, equipment list, product info & photos, statement letter). One production site per SPPT-SNI.",
     "Tahap I Seleksi: 18 butir persyaratan (akta, IUI, merek/lisensi, NPWP, dokumen SMM ISO 9001:2015, peta proses, "
     "daftar peralatan, informasi & foto produk, surat pernyataan bermeterai). Satu lokasi produksi per SPPT-SNI."),
    ("SNI", 2, "audit_kecukupan",
     "Adequacy Audit (Stage 1)",
     "Audit Kecukupan (Tahap 1)", 7,
     "Document review of the production process & management system by the audit team to determine readiness "
     "for the field audit.",
     "Tinjauan dokumen proses produksi & sistem manajemen oleh Tim Audit untuk menentukan kesiapan penilaian lapangan."),
    ("SNI", 3, "audit_kesesuaian",
     "Conformity Audit (Stage 2, factory)",
     "Audit Kesesuaian (Tahap 2, pabrik)", 14,
     "On-site audit while production is running: full QMS elements, production process assessment, QC equipment "
     "(viscometer, titrator, AAS, water content). Min 4 man-days domestic / 6 abroad. NC: major fixed within 1 month, "
     "minor within 2 months.",
     "Audit lapangan saat produksi berjalan: seluruh elemen SMM, asesmen proses produksi, peralatan QC (viskometer, "
     "titrator, AAS, water content). Min 4 orang-hari DN / 6 LN. KTS: mayor maks 1 bulan, minor maks 2 bulan."),
    ("SNI", 4, "pengambilan_contoh",
     "Product Sampling by PPC",
     "Pengambilan Contoh oleh PPC", 7,
     "Registered PPC samples randomly from the production line or warehouse with sampling report (BAPC) and test "
     "label (LCU); at least 4 litres per sample (2 for test, 2 archived); per SNI number, brand, API service and SAE.",
     "PPC terdaftar mengambil contoh acak di lini produksi/gudang dengan BAPC dan Label Contoh Uji; minimal 4 liter "
     "per contoh (2 uji, 2 arsip); per nomor SNI, merek, API service, dan SAE."),
    ("SNI", 5, "pengujian",
     "Laboratory Testing",
     "Pengujian Laboratorium", 30,
     "KAN-accredited laboratory appointed by the Minister, per SNI 7069.x parameters. Engine test once per "
     "certification period per performance spec (unless the formula is unchanged and documented).",
     "Laboratorium terakreditasi KAN dan ditunjuk Menteri, sesuai parameter SNI 7069.x. Uji unjuk kerja mesin 1x per "
     "periode sertifikasi per spesifikasi (kecuali formula tidak berubah dan terdokumentasi)."),
    ("SNI", 6, "tinjauan_keputusan",
     "Technical Review & Certification Decision",
     "Tinjauan Teknis & Keputusan Sertifikasi", 14,
     "Technical team/evaluator reviews the audit report, BAPC and test report; decision through the panel / technical "
     "review committee. Failed parameter: retest of archive sample or full resampling; second failure = application fails.",
     "Tim Teknis/Evaluator meninjau Laporan Audit, BAPC, dan LHU; keputusan melalui rapat Panel/Komite Tinjauan "
     "Teknis. Parameter gagal: uji ulang arsip atau contoh ulang; gagal kedua = permohonan gugur."),
    ("SNI", 7, "registrasi_penerbitan",
     "Kemenperin Registration & SPPT-SNI Issuance",
     "Registrasi Kemenperin & Penerbitan SPPT-SNI", 7,
     "Online registration to the Industrial Standardization Center (BPPI, Ministry of Industry) before issuance. "
     "SPPT-SNI is valid 4 years for one production site; SNI mark printed on every package.",
     "Registrasi online ke Pusat Standardisasi Industri (BPPI, Kemenperin) sebelum penerbitan. SPPT-SNI berlaku 4 "
     "tahun untuk satu lokasi produksi; tanda SNI dicetak pada setiap kemasan."),

    # --- NPT (Permen ESDM 53/2006) ---
    ("NPT", 1, "permohonan",
     "Application Preparation & Filing",
     "Penyiapan & Pengajuan Permohonan", 7,
     "Application to the Director General of Oil & Gas with administrative data (deed, company profile, NPWP, SIUP, "
     "TDP, domicile, principal appointment, HAKI trademark, statement letter) and technical data (source, spec, "
     "composition, packaging, performance report/API-JASO certificate) - Art. 5-6.",
     "Permohonan kepada Dirjen Migas dengan data administratif (akte, company profile, NPWP, SIUP, TDP, domisili, "
     "penunjukan prinsipal, merek HAKI, surat pernyataan) dan data teknis (sumber perolehan, spesifikasi, komposisi, "
     "kemasan, laporan unjuk kerja/sertifikat API-JASO) - Pasal 5-6."),
    ("NPT", 2, "evaluasi",
     "Document Research & Evaluation",
     "Penelitian & Evaluasi Dokumen", 14,
     "Research & Evaluation Team formed by the Director General; clarifications may be requested. Regulatory limit: "
     "10 working days after documents are complete and correct - Art. 7(4).",
     "Tim Penelitian & Evaluasi bentukan Dirjen; klarifikasi dapat diminta. Batas regulasi: 10 hari kerja setelah "
     "persyaratan lengkap dan benar - Pasal 7(4)."),
    ("NPT", 3, "pengambilan_percontoh",
     "Sample Collection by DG Officer",
     "Pengambilan Percontoh oleh Petugas Ditjen", 7,
     "Directorate General officer takes lubricant samples at the factory/warehouse (domestic production) or the "
     "importer/distributor warehouse (imported), then ships them to the test laboratory - Art. 8(1-2).",
     "Petugas Ditjen mengambil percontoh pelumas di pabrik/gudang (produksi dalam negeri) atau gudang importir/"
     "distributor (impor), lalu mengirim ke Laboratorium Uji - Pasal 8(1-2)."),
    ("NPT", 4, "uji_lab",
     "Laboratory Testing (LEMIGAS)",
     "Uji Laboratorium (LEMIGAS)", 30,
     "LEMIGAS test laboratory and/or another accredited lab appointed by the DG. Regulatory limit: 21 working days "
     "from sample receipt to the Analysis Result Report - Art. 8(5).",
     "Laboratorium Uji LEMIGAS dan/atau lab terakreditasi lain yang ditunjuk Dirjen. Batas regulasi: 21 hari kerja "
     "sejak percontoh diterima hingga Laporan Hasil Analisa - Pasal 8(5)."),
    ("NPT", 5, "keputusan_penerbitan",
     "Decision & NPT Issuance",
     "Keputusan & Penerbitan NPT", 14,
     "Approval (NPT granted and recorded in the General Lubricants Register) or rejection with reasons, max 10 "
     "working days after the Analysis Report. NPT is valid 5 years and renewable - Art. 8(6-8).",
     "Persetujuan (NPT diberikan dan dicatat dalam Daftar Umum Pelumas) atau penolakan disertai alasan, maks 10 hari "
     "kerja setelah Laporan Hasil Analisa. NPT berlaku 5 tahun dan dapat diperpanjang - Pasal 8(6-8)."),
]

# Post-certification lifecycle per regulation:
#   SNI : certificate valid 4 years, surveillance (audit + sampling + testing) once per year.
#   NPT : registration valid 5 years, quarterly marketing-realisation report to the DG (Art. 14),
#         government market sampling every 6 months (Art. 12).
POST_CERT = {
    "SNI": {"validity_months": 48, "cycle_months": 12},
    "NPT": {"validity_months": 60, "cycle_months": 3},
}

DEFAULT_SETTINGS = {
    "company_name": "MASAGI CROM",
    "company_address": "Jakarta, Indonesia",
    "company_email": "admin@masagicrom.local",
    "company_phone": "+62 21 0000 0000",
    # The company is NOT a PKP, so it does not charge PPN. Services are subject to
    # PPh Pasal 23 (2%), withheld by the client. tax_mode: PPh | PPN | NONE.
    "tax_mode": "PPh",
    "ppn_percent": "11",
    "pph_percent": "2",
    "invoice_footer": "Payment to BCA 000-000-0000 a.n. MASAGI Digital. / Pembayaran ke BCA 000-000-0000 a.n. MASAGI Digital.",
}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def add_months(iso_date, months):
    """Naive month arithmetic on an ISO date string."""
    d = date.fromisoformat(iso_date[:10])
    y, m = d.year, d.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day).isoformat()


def create_stages(conn, submission_id, service_type, start_iso):
    """Instantiate the pipeline for a new submission; first stage starts immediately."""
    rows = conn.execute(
        "SELECT * FROM stage_templates WHERE service_type=? ORDER BY ord", (service_type,)
    ).fetchall()
    for tpl in rows:
        first = tpl["ord"] == 1
        conn.execute(
            """INSERT INTO stages(submission_id, ord, key, name_en, name_id, days, note_en, note_id,
                                  status, entered_at, est_end)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (submission_id, tpl["ord"], tpl["key"], tpl["name_en"], tpl["name_id"], tpl["days"],
             tpl["note_en"], tpl["note_id"],
             "IN_PROGRESS" if first else "PENDING",
             start_iso if first else None,
             (date.fromisoformat(start_iso) + timedelta(days=tpl["days"])).isoformat() if first else None),
        )


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = connect()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) c FROM stage_templates").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO stage_templates(service_type, ord, key, name_en, name_id, days, note_en, note_id) "
            "VALUES(?,?,?,?,?,?,?,?)", STAGE_TEMPLATES)
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?,?)", (k, v))
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        seed_demo(conn)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- demo seed

def _seed_submission(conn, code, client_id, stype, product, brand, std, created_by,
                     started_days_ago, stages_done, overdue_current=False):
    """Create a submission whose first `stages_done` stages are completed and the next one is running."""
    start = (date.today() - timedelta(days=started_days_ago)).isoformat()
    cur = conn.execute(
        """INSERT INTO submissions(code, client_id, service_type, product_name, brand, standard_ref,
                                   status, submitted_at, created_by)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (code, client_id, stype, product, brand, std, "ACTIVE", start, created_by))
    sid = cur.lastrowid
    create_stages(conn, sid, stype, start)
    stages = conn.execute("SELECT * FROM stages WHERE submission_id=? ORDER BY ord", (sid,)).fetchall()
    cursor_day = date.fromisoformat(start)
    for i, st in enumerate(stages):
        if i < stages_done:
            entered = cursor_day
            dur = max(2, st["days"] // 2)
            done = entered + timedelta(days=dur)
            conn.execute(
                "UPDATE stages SET status='COMPLETED', entered_at=?, est_end=?, completed_at=? WHERE id=?",
                (entered.isoformat(), (entered + timedelta(days=st["days"])).isoformat(), done.isoformat(), st["id"]))
            cursor_day = done
        elif i == stages_done:
            entered = cursor_day
            est = entered + timedelta(days=st["days"])
            if overdue_current:
                est = date.today() - timedelta(days=6)
            conn.execute(
                "UPDATE stages SET status='IN_PROGRESS', entered_at=?, est_end=? WHERE id=?",
                (entered.isoformat(), est.isoformat(), st["id"]))
            break
    return sid


def _seed_certified(conn, code, client_id, stype, product, brand, std, created_by,
                    certified_days_ago, cert_number):
    start = (date.today() - timedelta(days=certified_days_ago + 90)).isoformat()
    certified = (date.today() - timedelta(days=certified_days_ago)).isoformat()
    pc = POST_CERT[stype]
    nxt = add_months(certified, pc["cycle_months"])
    cur = conn.execute(
        """INSERT INTO submissions(code, client_id, service_type, product_name, brand, standard_ref, status,
                                   submitted_at, cert_number, certified_at, cert_expiry, next_surveillance, created_by)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (code, client_id, stype, product, brand, std, "CERTIFIED", start, cert_number, certified,
         add_months(certified, pc["validity_months"]), nxt, created_by))
    sid = cur.lastrowid
    create_stages(conn, sid, stype, start)
    stages = conn.execute("SELECT * FROM stages WHERE submission_id=? ORDER BY ord", (sid,)).fetchall()
    cursor_day = date.fromisoformat(start)
    for st in stages:
        entered = cursor_day
        done = entered + timedelta(days=max(2, st["days"] // 2))
        conn.execute(
            "UPDATE stages SET status='COMPLETED', entered_at=?, est_end=?, completed_at=? WHERE id=?",
            (entered.isoformat(), (entered + timedelta(days=st["days"])).isoformat(), done.isoformat(), st["id"]))
        cursor_day = done
    return sid


def invoice_total(subtotal, tax_mode, tax_percent):
    """PPh is withheld (reduces the amount payable); PPN is added; NONE leaves it unchanged."""
    tax = round(subtotal * tax_percent / 100)
    if tax_mode == "PPN":
        return tax, subtotal + tax
    if tax_mode == "PPh":
        return tax, subtotal - tax
    return 0, subtotal


def _seed_invoice(conn, number, client_id, submission_id, created_by, status, issued_days_ago,
                  due_in_days, items, tax_mode="PPh", tax_percent=2.0):
    issue = (date.today() - timedelta(days=issued_days_ago)).isoformat()
    due = (date.fromisoformat(issue) + timedelta(days=due_in_days)).isoformat()
    subtotal = sum(q * p for _, q, p in items)
    tax, total = invoice_total(subtotal, tax_mode, tax_percent)
    cur = conn.execute(
        """INSERT INTO invoices(number, client_id, submission_id, status, issue_date, due_date,
                                subtotal, tax_mode, tax_percent, tax_amount, total, created_by)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (number, client_id, submission_id, status, issue, due, subtotal, tax_mode, tax_percent, tax,
         total, created_by))
    inv_id = cur.lastrowid
    for desc, q, p in items:
        conn.execute(
            "INSERT INTO invoice_items(invoice_id, description, qty, unit_price, total) VALUES(?,?,?,?,?)",
            (inv_id, desc, q, p, q * p))
    return inv_id, total


def seed_demo(conn):
    def mk_user(email, pw, name, role, company="", phone=""):
        return conn.execute(
            "INSERT INTO users(email, password_hash, name, role, company, phone) VALUES(?,?,?,?,?,?)",
            (email, generate_password_hash(pw), name, role, company, phone)).lastrowid

    admin = mk_user("admin@masagicrom.local", "admin123", "CROM Admin", "admin", "MASAGI Digital")
    inputter = mk_user("inputter@masagicrom.local", "inputter123", "Rina Inputter", "inputter", "MASAGI Digital")
    c1 = mk_user("client@pelumasnusantara.co.id", "client123", "Budi Santoso", "client",
                 "PT Pelumas Nusantara", "+62 811 111 111")
    c2 = mk_user("client@lubrindo.co.id", "client123", "Sari Wijaya", "client",
                 "PT Lubrindo Jaya", "+62 812 222 222")

    y = date.today().year
    s1 = _seed_submission(conn, f"SNI-{y}-0001", c1, "SNI", "Oli Mesin X-Pro 10W-40",
                          "X-Pro", "SNI 7069.1:2020", admin, 45, 2)                      # factory audit running
    s2 = _seed_submission(conn, f"SNI-{y}-0002", c1, "SNI", "Oli Motor Matic Z-Glide 10W-30",
                          "Z-Glide", "SNI 7069.2:2021", admin, 70, 4, overdue_current=True)  # lab test overdue
    s3 = _seed_submission(conn, f"NPT-{y}-0001", c1, "NPT", "Gear Oil GX-90",
                          "GearMax", "SAE 90, API GL-5", admin, 12, 1)                   # DG evaluation running
    s4 = _seed_submission(conn, f"NPT-{y}-0002", c2, "NPT", "Hydraulic Oil HV-68",
                          "HydraPro", "ISO VG 68", admin, 3, 0)                          # new this week
    s5 = _seed_certified(conn, f"SNI-{y-1}-0007", c2, "SNI", "Diesel Engine Oil D-Force 15W-40",
                         "D-Force", "SNI 7069.5:2021", admin, 340, f"SPPT-SNI 007/LSPro/{y-1}")
    s6 = _seed_certified(conn, f"NPT-{y-1}-0011", c2, "NPT", "Motorcycle Oil M-Sport 10W-30",
                         "M-Sport", "SAE 10W-30, API SL", admin, 80, f"NPT 0111/{y-1}")

    i1, i1_total = _seed_invoice(conn, f"INV-{y}-0001", c1, s1, admin, "SENT", 40, 30, [
        ("SNI Type 5 certification service - Oli Mesin X-Pro 10W-40 (SNI 7069.1:2020)", 1, 28_000_000),
        ("Laboratory testing fee (physico-chemical parameters)", 1, 9_500_000)])
    conn.execute("INSERT INTO payments(invoice_id, amount, pay_date, method, confirmed, confirmed_by, confirmed_at, created_by) "
                 "VALUES(?,?,?,?,1,?,datetime('now'),?)",
                 (i1, i1_total, (date.today() - timedelta(days=20)).isoformat(), "Bank transfer", admin, admin))
    conn.execute("UPDATE invoices SET status='PAID', paid_date=? WHERE id=?",
                 ((date.today() - timedelta(days=20)).isoformat(), i1))

    i2, _ = _seed_invoice(conn, f"INV-{y}-0002", c1, s2, admin, "SENT", 10, 30, [
        ("SNI Type 5 certification service - Z-Glide 10W-30 (SNI 7069.2:2021)", 1, 28_000_000)])
    conn.execute("INSERT INTO payments(invoice_id, amount, pay_date, method, confirmed, confirmed_by, confirmed_at, created_by) "
                 "VALUES(?,?,?,?,1,?,datetime('now'),?)",
                 (i2, 15_000_000, (date.today() - timedelta(days=2)).isoformat(), "Bank transfer", admin, admin))
    conn.execute("UPDATE invoices SET status='PARTIAL' WHERE id=?", (i2,))

    _seed_invoice(conn, f"INV-{y}-0003", c2, s4, admin, "SENT", 45, 14, [
        ("NPT registration service - Hydraulic Oil HV-68", 1, 12_500_000),
        ("LEMIGAS laboratory analysis fee", 1, 6_000_000)])                              # overdue
    _seed_invoice(conn, f"INV-{y}-0004", c1, s3, admin, "DRAFT", 1, 30, [
        ("NPT registration service - Gear Oil GX-90", 1, 12_500_000)])

    conn.executemany(
        "INSERT INTO activity(user_id, submission_id, action, details) VALUES(?,?,?,?)",
        [(admin, s1, "stage", f"SNI-{y}-0001: Adequacy Audit completed, Conformity Audit (factory) started"),
         (inputter, s2, "stage", f"SNI-{y}-0002: sample delivered to laboratory"),
         (admin, s4, "create", f"NPT-{y}-0002 created for PT Lubrindo Jaya"),
         (admin, None, "invoice", f"INV-{y}-0002 sent to PT Pelumas Nusantara")])

    conn.executemany(
        """INSERT INTO notifications(user_id, title_en, title_id, body_en, body_id, link)
           VALUES(?,?,?,?,?,?)""",
        [(c1, "Stage update", "Pembaruan tahap",
          f"SNI-{y}-0001 moved to: Conformity Audit (Stage 2, factory).",
          f"SNI-{y}-0001 memasuki tahap: Audit Kesesuaian (Tahap 2, pabrik).", f"/portal/submissions/{s1}"),
         (c1, "Invoice sent", "Faktur terkirim",
          f"Invoice INV-{y}-0002 has been issued.", f"Faktur INV-{y}-0002 telah diterbitkan.", "/invoices"),
         (c2, "Surveillance reminder", "Pengingat surveilan",
          "Annual surveillance for D-Force 15W-40 is approaching.",
          "Surveilan tahunan untuk D-Force 15W-40 akan segera jatuh tempo.", f"/portal/submissions/{s5}")])
