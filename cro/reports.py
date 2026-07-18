# MASAGI CROM - weekly report aggregation and narrative generation.
#
# The narrative is rule-based by default so the app has zero external dependencies.
# If ANTHROPIC_API_KEY is set (and the `anthropic` package is installed), the summary is
# written by Claude instead. The spec (system_analysis.md #5) asks for a lightweight,
# cost-efficient model and names Claude Haiku, so the default is claude-haiku-4-5;
# override with CROM_LLM_MODEL (e.g. claude-opus-4-8 for the highest quality).

import json
import os
from datetime import date, timedelta

LLM_DEFAULT_MODEL = "claude-haiku-4-5"


def llm_available():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def week_bounds(ref=None):
    ref = ref or date.today()
    monday = ref - timedelta(days=ref.weekday())
    return monday.isoformat(), (monday + timedelta(days=6)).isoformat()


def aggregate(conn, ws, we):
    today = date.today().isoformat()

    def n(sql, args=()):
        return conn.execute(sql, args).fetchone()[0] or 0

    new_subs = conn.execute(
        """SELECT s.code, s.product_name, u.company FROM submissions s JOIN users u ON u.id = s.client_id
           WHERE date(s.created_at) BETWEEN ? AND ?""", (ws, we)).fetchall()
    stages_done = conn.execute(
        """SELECT st.completed_at, st.name_en, s.code FROM stages st
           JOIN submissions s ON s.id = st.submission_id
           WHERE st.completed_at BETWEEN ? AND ?""", (ws, we)).fetchall()
    certified = conn.execute(
        """SELECT s.code, s.product_name, s.cert_number FROM submissions s
           WHERE s.certified_at BETWEEN ? AND ?""", (ws, we)).fetchall()
    overdue = conn.execute(
        """SELECT s.code, st.name_en, st.name_id,
                  CAST(julianday(?) - julianday(st.est_end) AS INTEGER) AS days_late
           FROM stages st JOIN submissions s ON s.id = st.submission_id
           WHERE st.status IN ('IN_PROGRESS','ACTION') AND s.status = 'ACTIVE'
             AND st.est_end IS NOT NULL AND st.est_end < ?
           ORDER BY days_late DESC""", (today, today)).fetchall()

    invoiced = n("""SELECT SUM(total) FROM invoices
                    WHERE issue_date BETWEEN ? AND ? AND status NOT IN ('DRAFT','CANCELLED')""", (ws, we))
    collected = n("""SELECT SUM(amount) FROM payments
                     WHERE confirmed = 1 AND pay_date BETWEEN ? AND ?""", (ws, we))
    outstanding = n("""SELECT SUM(i.total - COALESCE((SELECT SUM(p.amount) FROM payments p
                                                      WHERE p.invoice_id = i.id AND p.confirmed = 1), 0))
                       FROM invoices i WHERE i.status IN ('SENT','PARTIAL')""")

    bottleneck = conn.execute(
        """SELECT st.name_en, st.name_id, COUNT(*) c
           FROM stages st JOIN submissions s ON s.id = st.submission_id
           WHERE st.status IN ('IN_PROGRESS','ACTION') AND s.status = 'ACTIVE'
             AND st.est_end IS NOT NULL AND st.est_end < ?
           GROUP BY st.key ORDER BY c DESC LIMIT 1""", (today,)).fetchone()

    active_by_type = {r["service_type"]: r["c"] for r in conn.execute(
        "SELECT service_type, COUNT(*) c FROM submissions WHERE status='ACTIVE' GROUP BY service_type")}

    # Per-client, per-submission progress (with the client-visible note of the current stage).
    progress = conn.execute(
        """SELECT s.id, s.code, s.product_name, s.service_type, s.status,
                  u.name AS client_name, u.company,
                  (SELECT COUNT(*) FROM stages st WHERE st.submission_id = s.id AND st.status='COMPLETED') AS done_n,
                  (SELECT COUNT(*) FROM stages st WHERE st.submission_id = s.id) AS total_n,
                  (SELECT st.name_en FROM stages st WHERE st.submission_id = s.id
                     AND st.status IN ('IN_PROGRESS','ACTION') ORDER BY st.ord LIMIT 1) AS cur_en,
                  (SELECT st.name_id FROM stages st WHERE st.submission_id = s.id
                     AND st.status IN ('IN_PROGRESS','ACTION') ORDER BY st.ord LIMIT 1) AS cur_id,
                  (SELECT st.client_notes FROM stages st WHERE st.submission_id = s.id
                     AND st.status IN ('IN_PROGRESS','ACTION') ORDER BY st.ord LIMIT 1) AS cur_note
           FROM submissions s JOIN users u ON u.id = s.client_id
           WHERE s.status IN ('ACTIVE','CERTIFIED','ON_HOLD')
           ORDER BY u.company, s.code""").fetchall()
    by_client = {}
    for r in progress:
        grp = by_client.setdefault(r["company"], {"company": r["company"],
                                                   "client_name": r["client_name"], "submissions": []})
        grp["submissions"].append(dict(r))
    progress_by_client = list(by_client.values())

    return {
        "week_start": ws,
        "week_end": we,
        "new_submissions": [dict(r) for r in new_subs],
        "stages_completed": [dict(r) for r in stages_done],
        "certified": [dict(r) for r in certified],
        "overdue": [dict(r) for r in overdue],
        "active_by_type": active_by_type,
        "revenue": {"invoiced": invoiced, "collected": collected, "outstanding": outstanding},
        "bottleneck": dict(bottleneck) if bottleneck else None,
        "progress_by_client": progress_by_client,
    }


def _rp(v):
    return "Rp " + f"{v:,.0f}".replace(",", ".")


def rule_summary(d, lang):
    en = lang == "en"
    L = []
    n_new, n_done = len(d["new_submissions"]), len(d["stages_completed"])
    n_cert, n_over = len(d["certified"]), len(d["overdue"])
    rev = d["revenue"]

    L.append("== " + ("EXECUTIVE SUMMARY" if en else "RINGKASAN EKSEKUTIF") + " ==")
    if en:
        L.append(f"This week the agency registered {n_new} new submission(s), completed {n_done} pipeline "
                 f"stage(s) and issued {n_cert} certificate(s). {_rp(rev['collected'])} was collected against "
                 f"{_rp(rev['invoiced'])} newly invoiced, leaving {_rp(rev['outstanding'])} outstanding. "
                 f"{n_over} stage(s) are currently running late.")
    else:
        L.append(f"Minggu ini tercatat {n_new} pengajuan baru, {n_done} tahap pipeline selesai, dan {n_cert} "
                 f"sertifikat terbit. Pembayaran diterima {_rp(rev['collected'])} dari faktur baru senilai "
                 f"{_rp(rev['invoiced'])}, dengan piutang berjalan {_rp(rev['outstanding'])}. "
                 f"{n_over} tahap saat ini terlambat.")

    L.append("")
    L.append("== " + ("KEY HIGHLIGHTS" if en else "SOROTAN UTAMA") + " ==")
    for s in d["new_submissions"] or []:
        L.append(("- New submission: " if en else "- Pengajuan baru: ") + f"{s['code']} - {s['product_name']} ({s['company']})")
    for c in d["certified"] or []:
        L.append(("- Certificate issued: " if en else "- Sertifikat terbit: ") + f"{c['code']} ({c['cert_number'] or '-'})")
    if not d["new_submissions"] and not d["certified"]:
        L.append("- " + ("No new submissions or certificates this week." if en
                         else "Tidak ada pengajuan baru maupun sertifikat minggu ini."))

    L.append("")
    L.append("== " + ("RISK ALERTS" if en else "PERINGATAN RISIKO") + " ==")
    if d["overdue"]:
        for o in d["overdue"][:8]:
            name = o["name_en"] if en else o["name_id"]
            L.append(f"- {o['code']}: {name} " + (f"is {o['days_late']} day(s) late." if en
                                                  else f"terlambat {o['days_late']} hari."))
        if d["bottleneck"]:
            b = d["bottleneck"]
            bn = b["name_en"] if en else b["name_id"]
            L.append(("- Bottleneck: " if en else "- Titik hambat: ") + f"{bn} ({b['c']} " +
                     ("submissions stalled)." if en else "pengajuan tertahan)."))
    else:
        L.append("- " + ("No overdue stages - pipeline is healthy." if en
                         else "Tidak ada tahap terlambat - pipeline sehat."))

    L.append("")
    L.append("== " + ("RECOMMENDATIONS" if en else "REKOMENDASI") + " ==")
    if d["overdue"]:
        L.append("- " + ("Chase the overdue stages above; labs and auditors should confirm revised dates."
                         if en else "Tindak lanjuti tahap terlambat di atas; minta lab dan auditor mengonfirmasi jadwal baru."))
    if rev["outstanding"] > 0:
        L.append("- " + (f"Follow up outstanding invoices totalling {_rp(rev['outstanding'])}."
                         if en else f"Tagih piutang berjalan sebesar {_rp(rev['outstanding'])}."))
    L.append("- " + ("Review the compliance calendar for upcoming surveillance and quarterly NPT reports."
                     if en else "Periksa kalender kepatuhan untuk surveilan dan laporan triwulanan NPT yang akan datang."))
    return "\n".join(L)


def llm_summary(data):
    """Ask Claude for the bilingual summary. Returns (en, id) or None on any failure."""
    if not llm_available():
        return None
    try:
        from anthropic import Anthropic
        client = Anthropic()
        model = os.environ.get("CROM_LLM_MODEL", LLM_DEFAULT_MODEL)
        prompt = (
            "You are an operations analyst for an Indonesian certification agency that manages SNI product "
            "certification (Type 5 scheme) and NPT lubricant registration (Permen ESDM 53/2006) pipelines for "
            "clients. Write this week's management report from the JSON below.\n\n"
            "Structure (plain text, no markdown symbols other than '-' bullets):\n"
            "== EXECUTIVE SUMMARY == (3-4 sentences)\n== KEY HIGHLIGHTS == (bullets)\n"
            "== RISK ALERTS == (bullets: overdue stages, bottlenecks, unpaid invoices)\n"
            "== RECOMMENDATIONS == (bullets)\n\n"
            "Amounts are Indonesian Rupiah. Return ONLY a JSON object, no code fences: "
            '{"en": "<report in English>", "id": "<laporan dalam Bahasa Indonesia>"}\n\n'
            "DATA:\n" + json.dumps(data, ensure_ascii=False)
        )
        resp = client.messages.create(
            model=model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("{"):]
        obj = json.loads(text[text.find("{"): text.rfind("}") + 1])
        if obj.get("en") and obj.get("id"):
            return obj["en"], obj["id"]
    except Exception:
        pass
    return None


def generate(conn, user_id, ref_date=None):
    ws, we = week_bounds(ref_date)
    data = aggregate(conn, ws, we)
    pair = llm_summary(data)
    llm_used = 1 if pair else 0
    if not pair:
        pair = (rule_summary(data, "en"), rule_summary(data, "id"))
    cur = conn.execute(
        """INSERT INTO weekly_reports(week_start, week_end, raw_json, summary_en, summary_id, llm_used, generated_by)
           VALUES(?,?,?,?,?,?,?)""",
        (ws, we, json.dumps(data, ensure_ascii=False), pair[0], pair[1], llm_used, user_id))
    conn.commit()
    return cur.lastrowid
