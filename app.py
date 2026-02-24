import os
import json

from flask import Flask, render_template, redirect, url_for, session, request, jsonify
import db

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "telefan-mes-4-secret-2026")

VALID_USERS = {
    os.getenv("ADMIN_EMAIL", "admin@telefan.fr"): os.getenv("ADMIN_PASSWORD", "telefan2026"),
}

NAV = [
    ("dashboard",    "Accueil",     "home",        "Vue générale"),
    ("production",   "Production",  "settings-2",  "KPI 1–4"),
    ("qualite",      "Qualité",     "check-circle","KPI 5–9"),
    ("machines",     "Machines",    "cpu",         "KPI 10"),
    ("maintenance",  "Maintenance", "wrench",      "KPI 11–12"),
]


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

@app.before_request
def require_login():
    public = {"login", "static"}
    if request.endpoint not in public and not session.get("user"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if VALID_USERS.get(email) == password:
            session["user"] = email
            return redirect(url_for("dashboard"))
        error = "Identifiants incorrects."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ──────────────────────────────────────────────
# Page helpers
# ──────────────────────────────────────────────

def _base_ctx(active: str) -> dict:
    return {
        "nav":    NAV,
        "active": active,
        "user":   session.get("user", "Admin"),
        "db_info": db.DEFAULT_DB,
    }


# ──────────────────────────────────────────────
# Pages
# ──────────────────────────────────────────────

@app.route("/")
def dashboard():
    in_prog_total, in_prog_df = db.kpi_in_progress()
    progress     = db.kpi_production_progress()
    trs_df       = db.kpi_trs()
    total_errors = db.kpi_total_errors()
    buf_df       = db.kpi_buffer_fill()
    lead_df      = db.kpi_lead_time_delta()

    trs_g  = float(trs_df["trs"].mean())          if not trs_df.empty else 0.0
    dispo  = float(trs_df["availability"].mean()) if not trs_df.empty else 0.0
    perf   = float(trs_df["performance"].mean())  if not trs_df.empty else 0.0
    qual   = float(trs_df["quality"].mean())      if not trs_df.empty else 0.0

    # Alerts
    alerts = []
    if trs_g < 0.80:
        alerts.append(("warn", f"TRS global < 80 % ({trs_g*100:.0f} %)"))
    if not buf_df.empty:
        for _, r in buf_df[buf_df["fill_rate"] > 0.90].head(2).iterrows():
            alerts.append(("danger", f"Buffer {r['ResourceId']} saturé à {r['fill_rate']*100:.0f} %"))
    if total_errors > 0:
        alerts.append(("warn", f"{total_errors} erreur(s) détectée(s)"))
    if progress["finished"] > 0:
        alerts.append(("info", f"{progress['finished']} OF terminés au total"))
    if not alerts:
        alerts.append(("ok", "Aucune alerte active"))

    # Chart data
    in_prog_chart = {
        "labels": db.to_records(in_prog_df.head(15)),
    }
    lead_chart = db.to_records(lead_df.tail(40)) if not lead_df.empty else []

    return render_template(
        "dashboard.html",
        **_base_ctx("dashboard"),
        in_prog_total=in_prog_total,
        finished=progress["finished"],
        trs_pct=round(trs_g * 100, 1),
        dispo_pct=round(dispo * 100, 1),
        perf_pct=round(perf * 100, 1),
        qual_pct=round(qual * 100, 1),
        total_errors=total_errors,
        alerts=alerts,
        in_prog_data=json.dumps(db.to_records(in_prog_df.head(15))),
        lead_data=json.dumps(lead_chart),
        top3=db.to_records(in_prog_df.head(3)),
    )


@app.route("/production")
def production():
    in_prog_total, in_prog_df = db.kpi_in_progress()
    progress     = db.kpi_production_progress()
    lead_df      = db.kpi_lead_time_delta()
    finished_df  = db.kpi_finished_per_day()
    orders_df    = db.kpi_orders_table()

    ecart_avg = 0
    if not lead_df.empty:
        ecart_avg = int(lead_df["delta_secs"].mean())

    return render_template(
        "production.html",
        **_base_ctx("production"),
        in_prog_total=in_prog_total,
        finished=progress["finished"],
        ratio_pct=round(progress["ratio"] * 100, 1),
        ecart_avg_min=round(ecart_avg / 60, 1),
        in_prog_data=json.dumps(db.to_records(in_prog_df.head(15))),
        lead_data=json.dumps(db.to_records(lead_df.tail(60)) if not lead_df.empty else []),
        finished_data=json.dumps(db.to_records(finished_df) if not finished_df.empty else []),
        advancement=db.to_records(in_prog_df.head(8)),
        orders=db.to_records(orders_df),
    )


@app.route("/qualite")
def qualite():
    trs_df       = db.kpi_trs()
    ml_df        = db.kpi_machine_load()
    top_errors   = db.kpi_top_errors()
    total_errors = db.kpi_total_errors()
    fp_yield, ok_orders, total_orders = db.kpi_first_pass_yield()

    trs_g = float(trs_df["trs"].mean())          if not trs_df.empty else 0.0
    dispo = float(trs_df["availability"].mean()) if not trs_df.empty else 0.0
    perf  = float(trs_df["performance"].mean())  if not trs_df.empty else 0.0
    qual  = float(trs_df["quality"].mean())      if not trs_df.empty else 0.0
    occ   = float(ml_df["occupation"].mean())    if not ml_df.empty  else 0.0

    trs_table = []
    if not trs_df.empty:
        for _, r in trs_df.iterrows():
            trs_table.append({
                "resource":     r["ResourceID"],
                "availability": round(r["availability"] * 100, 1),
                "performance":  round(r["performance"]  * 100, 1),
                "quality":      round(r["quality"]      * 100, 1),
                "trs":          round(r["trs"]          * 100, 1),
            })

    return render_template(
        "qualite.html",
        **_base_ctx("qualite"),
        trs_pct=round(trs_g * 100, 1),
        dispo_pct=round(dispo * 100, 1),
        perf_pct=round(perf * 100, 1),
        qual_pct=round(qual * 100, 1),
        occ_pct=round(occ * 100, 1),
        total_errors=total_errors,
        ok_orders=ok_orders,
        total_orders=total_orders,
        fp_yield_pct=round(fp_yield * 100, 1),
        trs_table=trs_table,
        errors_data=json.dumps(db.to_records(top_errors) if not top_errors.empty else []),
        qual_by_resource=json.dumps(trs_table),
    )


@app.route("/machines")
def machines():
    dt_df = db.kpi_mean_downtime()
    ml_df = db.kpi_machine_load()

    total_dt = avg_mtbf = avg_mttr = 0.0
    t_h = t_m = 0
    if not dt_df.empty:
        total_dt  = float(dt_df["total_downtime_min"].sum())
        avg_mtbf  = float(dt_df["mtbf_min"].mean())
        avg_mttr  = float(dt_df["mttr_min"].mean())
        t_h, t_m  = int(total_dt // 60), int(total_dt % 60)

    detail = []
    if not dt_df.empty:
        occ_map = {}
        if not ml_df.empty:
            occ_map = dict(zip(ml_df["ResourceID"], ml_df["occupation"]))
        for _, r in dt_df.iterrows():
            occ = occ_map.get(r["ResourceID"], r.get("occupation", 0))
            detail.append({
                "resource":    r["ResourceID"],
                "busy_pct":    round(float(occ) * 100, 1),
                "pannes":      int(r["n_failures"]),
                "mttr":        round(r["mttr_min"], 1),
                "mtbf":        round(r["mtbf_min"], 1),
                "downtime":    round(r["total_downtime_min"], 1),
            })

    return render_template(
        "machines.html",
        **_base_ctx("machines"),
        total_h=t_h,
        total_m=t_m,
        avg_mtbf=round(avg_mtbf, 1),
        avg_mttr=round(avg_mttr, 1),
        detail=detail,
        pareto_data=json.dumps(detail),
        occ_data=json.dumps(db.to_records(ml_df) if not ml_df.empty else []),
    )


@app.route("/maintenance")
def maintenance():
    buf_df          = db.kpi_buffer_fill()
    real_epp, calc_epp = db.kpi_energy_per_piece()
    dt_df           = db.kpi_mean_downtime()
    ml_df           = db.kpi_machine_load()
    energy_df       = db.kpi_energy_by_resource()

    fill_global = float(buf_df["fill_rate"].mean()) if not buf_df.empty else 0.0
    avg_mtbf    = float(dt_df["mtbf_min"].mean())   if not dt_df.empty else 0.0
    avg_mttr    = float(dt_df["mttr_min"].mean())   if not dt_df.empty else 0.0

    buffers = []
    if not buf_df.empty:
        for _, r in buf_df.iterrows():
            pct = round(float(r["fill_rate"]) * 100, 1)
            buffers.append({
                "id":      r["ResourceId"],
                "pct":     pct,
                "occupied": int(r["occupied"]),
                "total":    int(r["total_slots"]),
                "status":  "danger" if pct > 90 else ("warn" if pct > 70 else "ok"),
            })

    occ_global = float(ml_df["occupation"].mean()) if not ml_df.empty else 0.0
    total_machines = len(ml_df) if not ml_df.empty else 0

    return render_template(
        "maintenance.html",
        **_base_ctx("maintenance"),
        fill_pct=round(fill_global * 100, 1),
        real_epp=round(real_epp, 3),
        calc_epp=round(calc_epp, 3),
        avg_mtbf=round(avg_mtbf, 1),
        avg_mttr=round(avg_mttr, 1),
        buffers=buffers,
        buf_chart_data=json.dumps(buffers),
        energy_data=json.dumps(db.to_records(energy_df) if not energy_df.empty else []),
        total_machines=total_machines,
        occ_pct=round(occ_global * 100, 1),
    )


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print(f"[T'Elefan MES 4.0] http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
