import os
import json

from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import db

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "telefan-mes-4-secret-2026")


@app.template_filter("sep")
def sep_filter(value):
    """Séparateur de milliers (espace fine) pour l'affichage français."""
    try:
        n = float(value)
        if n == int(n):
            return f"{int(n):,}".replace(",", "\u202f")
        return f"{n:,.1f}".replace(",", "\u202f")
    except (ValueError, TypeError):
        return value

USERS = {
    os.getenv("ADMIN_EMAIL", "admin@telefan.fr"): {
        "password_hash": generate_password_hash(os.getenv("ADMIN_PASSWORD", "Admin@MES4_2026!")),
        "role":          "Administrateur",
    },
    os.getenv("OPER_EMAIL", "operateur@telefan.fr"): {
        "password_hash": generate_password_hash(os.getenv("OPER_PASSWORD", "Oper@Prod_2026")),
        "role":          "Opérateur",
    },
}

NAV = [
    ("dashboard",    "Accueil",     "home",         "Vue générale"),
    ("production",   "Production",  "settings-2",   "KPI 1–4"),
    ("qualite",      "Qualité",     "check-circle", "KPI 5–9"),
    ("machines",     "Machines",    "cpu",          "KPI 10"),
    ("maintenance",  "Maintenance", "wrench",       "KPI 11–12"),
    ("geographie",   "Géographie",  "map-pin",      "Site & Capteurs"),
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
        u = USERS.get(email)
        if u and check_password_hash(u["password_hash"], password):
            session["user"] = email
            session["role"] = u["role"]
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
        "nav":      NAV,
        "active":   active,
        "user":     session.get("user", "admin@telefan.fr"),
        "role":     session.get("role", ""),
        "db_info":  db.DEFAULT_DB,
    }


# ──────────────────────────────────────────────
# Pages
# ──────────────────────────────────────────────

@app.route("/")
def dashboard():
    date_from = request.args.get("from", "").strip()
    date_to   = request.args.get("to",   "").strip()
    db_min, db_max = db.get_finstep_date_range()

    in_prog_total, in_prog_df = db.kpi_in_progress()
    progress     = db.kpi_production_progress()
    trs_df       = db.kpi_trs(date_from or None, date_to or None)
    total_errors = db.kpi_total_errors(date_from or None, date_to or None)
    buf_df       = db.kpi_buffer_fill()
    lead_df      = db.kpi_lead_time_delta(date_from or None, date_to or None)

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
        date_from=date_from,
        date_to=date_to,
        db_min=db_min or "",
        db_max=db_max or "",
    )


@app.route("/production")
def production():
    date_from = request.args.get("from", "").strip()
    date_to   = request.args.get("to",   "").strip()
    db_min, db_max = db.get_finstep_date_range()

    in_prog_total, in_prog_df = db.kpi_in_progress()
    progress       = db.kpi_production_progress()
    lead_df        = db.kpi_lead_time_delta(date_from or None, date_to or None)
    finished_df    = db.kpi_finished_per_day(date_from or None, date_to or None)
    orders_df      = db.kpi_orders_table()
    advancement_df = db.kpi_order_advancement()

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
        advancement=db.to_records(advancement_df),
        orders=db.to_records(orders_df),
        date_from=date_from,
        date_to=date_to,
        db_min=db_min or "",
        db_max=db_max or "",
    )


@app.route("/qualite")
def qualite():
    date_from = request.args.get("from", "").strip()
    date_to   = request.args.get("to",   "").strip()
    db_min, db_max = db.get_finstep_date_range()

    trs_df       = db.kpi_trs(date_from or None, date_to or None)
    ml_df        = db.kpi_machine_load(date_from or None, date_to or None)
    top_errors   = db.kpi_top_errors()
    step_errors  = db.kpi_errors_by_step(date_from or None, date_to or None)
    total_errors = db.kpi_total_errors(date_from or None, date_to or None)
    fp_yield, ok_orders, total_orders = db.kpi_first_pass_yield(date_from or None, date_to or None)

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
        step_errors_data=json.dumps(db.to_records(step_errors) if not step_errors.empty else []),
        qual_by_resource=json.dumps(trs_table),
        date_from=date_from,
        date_to=date_to,
        db_min=db_min or "",
        db_max=db_max or "",
    )


@app.route("/machines")
def machines():
    date_from = request.args.get("from", "").strip()
    date_to   = request.args.get("to",   "").strip()
    db_min, db_max = db.get_machine_date_range()

    dt_df = db.kpi_mean_downtime(date_from or None, date_to or None)
    ml_df = db.kpi_machine_load()

    total_dt = avg_mtbf = avg_mttr = 0.0
    t_h = t_m = 0
    if not dt_df.empty:
        total_dt  = float(dt_df["total_downtime_min"].sum())
        with_fail = dt_df[dt_df["n_failures"] > 0]
        avg_mtbf  = float(with_fail["mtbf_min"].median()) if not with_fail.empty else 0.0
        avg_mttr  = float(with_fail["mttr_min"].median()) if not with_fail.empty else 0.0
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
        date_from=date_from,
        date_to=date_to,
        db_min=db_min or "",
        db_max=db_max or "",
    )


@app.route("/maintenance")
def maintenance():
    date_from = request.args.get("from", "").strip()
    date_to   = request.args.get("to",   "").strip()
    db_min, db_max = db.get_machine_date_range()

    buf_df          = db.kpi_buffer_fill()
    real_epp, calc_epp = db.kpi_energy_per_piece()
    dt_df           = db.kpi_mean_downtime(date_from or None, date_to or None)
    ml_df           = db.kpi_machine_load()
    energy_df       = db.kpi_energy_by_resource()

    # CSV sensor data
    power_df        = db.kpi_sensor_power()
    pneumatics_df   = db.kpi_sensor_pneumatics()
    energy_stats, energy_sample = db.kpi_sensor_energy_stats()

    fill_global = float(buf_df["fill_rate"].mean()) if not buf_df.empty else 0.0
    if not dt_df.empty:
        with_fail = dt_df[dt_df["n_failures"] > 0]
        avg_mtbf  = float(with_fail["mtbf_min"].median()) if not with_fail.empty else 0.0
        avg_mttr  = float(with_fail["mttr_min"].median()) if not with_fail.empty else 0.0
    else:
        avg_mtbf = avg_mttr = 0.0

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
        date_from=date_from,
        date_to=date_to,
        db_min=db_min or "",
        db_max=db_max or "",
        power_data=json.dumps(db.to_records(power_df) if not power_df.empty else []),
        pneumatics_data=json.dumps(db.to_records(pneumatics_df) if not pneumatics_df.empty else []),
        energy_stats=energy_stats,
        energy_sample=json.dumps(energy_sample),
    )


@app.route("/geographie")
def geographie():
    in_prog_total, _ = db.kpi_in_progress()
    progress         = db.kpi_production_progress()
    trs_df           = db.kpi_trs()
    trs_g            = float(trs_df["trs"].mean()) if not trs_df.empty else 0.0
    buf_df           = db.kpi_buffer_fill()
    fill_global      = float(buf_df["fill_rate"].mean()) if not buf_df.empty else 0.0

    return render_template(
        "geographie.html",
        **_base_ctx("geographie"),
        in_prog_total=in_prog_total,
        finished=progress["finished"],
        trs_pct=round(trs_g * 100, 1),
        fill_pct=round(fill_global * 100, 1),
    )


# ──────────────────────────────────────────────
# Error handlers
# ──────────────────────────────────────────────

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html", **_base_ctx(""), error=str(e)), 404


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print(f"[T'Elefan MES 4.0] http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
