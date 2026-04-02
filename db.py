import os
import json
from datetime import datetime
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

DEFAULT_DB = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER",     "qlio_user"),
    "password": os.getenv("DB_PASSWORD", "Qlio_MES4@2026"),
    "database": os.getenv("DB_NAME",     "mes4"),
}

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = (
            f"mysql+pymysql://{quote_plus(DEFAULT_DB['user'])}:{quote_plus(DEFAULT_DB['password'])}"
            f"@{DEFAULT_DB['host']}:{DEFAULT_DB['port']}/{DEFAULT_DB['database']}"
        )
        _engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)
    return _engine


def run_query(query: str, params: dict | None = None) -> pd.DataFrame:
    try:
        with get_engine().connect() as conn:
            return pd.read_sql_query(text(query), conn, params=params or {})
    except Exception as exc:
        print(f"[DB ERROR] {exc}")
        return pd.DataFrame()


def to_records(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


# ──────────────────────────────────────────────
# KPI FUNCTIONS
# ──────────────────────────────────────────────

def kpi_in_progress():
    """KPI 1 – nombre de produits distincts en cours (Active=1, par ONo/OPos)."""
    df = run_query("""
        SELECT ONo AS order_ref,
               COUNT(DISTINCT OPos) AS products_in_progress
        FROM tblstep
        WHERE Active = 1
        GROUP BY ONo
        ORDER BY products_in_progress DESC
    """)
    total = int(df["products_in_progress"].sum()) if not df.empty else 0
    return total, df


def kpi_order_advancement():
    """KPI 3 – top 3 OF les plus avancés (FIFO) : produits terminés / total produits."""
    df = run_query("""
        SELECT ONo,
               SUM(CASE WHEN End IS NOT NULL THEN 1 ELSE 0 END) AS finished_products,
               COUNT(*) AS total_products
        FROM tblorderpos
        GROUP BY ONo
        HAVING total_products > 0
        ORDER BY (SUM(CASE WHEN End IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*)) DESC
        LIMIT 3
    """)
    if df.empty:
        return df
    df["pct"] = (df["finished_products"] / df["total_products"] * 100).round(1).clip(upper=100)
    return df


def kpi_production_progress():
    planned  = run_query("SELECT COUNT(*) AS n FROM tblorder")
    finished = run_query("SELECT COUNT(*) AS n FROM tblfinorder")
    active   = run_query("SELECT COUNT(DISTINCT ONo) AS n FROM tblstep WHERE Active = 1")
    p = int(planned["n"].iloc[0])  if not planned.empty  else 0
    f = int(finished["n"].iloc[0]) if not finished.empty else 0
    a = int(active["n"].iloc[0])   if not active.empty   else 0
    return {"planned": p, "finished": f, "active": a, "ratio": round(a / (p + f or 1), 4)}


def kpi_lead_time_delta(date_from=None, date_to=None):
    cond, params = [], {}
    if date_from:
        cond.append("End >= :date_from")
        params["date_from"] = date_from
    if date_to:
        cond.append("End < DATE_ADD(:date_to, INTERVAL 1 DAY)")
        params["date_to"] = date_to
    extra = (" AND " + " AND ".join(cond)) if cond else ""
    df = run_query(f"""
        SELECT CONCAT(ONo, '-', OPos)                          AS order_ref,
               TIMESTAMPDIFF(SECOND, PlannedStart, PlannedEnd) AS planned_secs,
               TIMESTAMPDIFF(SECOND, Start, End)               AS actual_secs
        FROM tblfinorderpos
        WHERE Start IS NOT NULL AND End IS NOT NULL{extra}
    """, params)
    if df.empty:
        return df
    df["delta_secs"] = df["actual_secs"] - df["planned_secs"]
    return df


def kpi_finished_per_day(date_from=None, date_to=None):
    cond, params = [], {}
    if date_from:
        cond.append("End >= :date_from")
        params["date_from"] = date_from
    if date_to:
        cond.append("End < DATE_ADD(:date_to, INTERVAL 1 DAY)")
        params["date_to"] = date_to
    extra = (" AND " + " AND ".join(cond)) if cond else ""
    return run_query(f"""
        SELECT DATE(End) AS jour, COUNT(*) AS nb_ordres
        FROM tblfinorder
        WHERE End IS NOT NULL{extra}
        GROUP BY DATE(End)
        ORDER BY jour
    """, params)


def kpi_trs(date_from=None, date_to=None):
    cond_mr, p_mr = [], {}
    cond_fs, p_fs = [], {}
    if date_from:
        cond_mr.append("TimeStamp >= :date_from")
        p_mr["date_from"] = date_from
        cond_fs.append("End >= :date_from")
        p_fs["date_from"] = date_from
    if date_to:
        cond_mr.append("TimeStamp < DATE_ADD(:date_to, INTERVAL 1 DAY)")
        p_mr["date_to"] = date_to
        cond_fs.append("End < DATE_ADD(:date_to, INTERVAL 1 DAY)")
        p_fs["date_to"] = date_to
    where_mr  = ("WHERE " + " AND ".join(cond_mr)) if cond_mr else ""
    extra_fs  = (" AND " + " AND ".join(cond_fs)) if cond_fs else ""
    where_fs  = ("WHERE " + " AND ".join(cond_fs)) if cond_fs else ""

    avail = run_query(f"""
        SELECT ResourceID,
               SUM(CASE WHEN Busy = 1 THEN 1 ELSE 0 END) AS busy_ticks,
               COUNT(*)                                   AS total_ticks
        FROM tblmachinereport
        {where_mr}
        GROUP BY ResourceID
    """, p_mr)
    perf = run_query(f"""
        SELECT ResourceID,
               AVG(TIMESTAMPDIFF(SECOND, PlannedStart, PlannedEnd)) AS planned_secs,
               AVG(TIMESTAMPDIFF(SECOND, Start, End))               AS actual_secs
        FROM tblfinstep
        WHERE Start IS NOT NULL AND End IS NOT NULL{extra_fs}
        GROUP BY ResourceID
    """, p_fs)
    qual = run_query(f"""
        SELECT ResourceID,
               SUM(CASE WHEN ErrorStep=1 OR ErrorRetVal<>0 THEN 1 ELSE 0 END) AS errors,
               COUNT(*)                                                         AS total_steps
        FROM tblfinstep
        {where_fs}
        GROUP BY ResourceID
    """, p_fs)
    if avail.empty and perf.empty and qual.empty:
        return pd.DataFrame()
    df = pd.merge(avail, perf, how="outer", on="ResourceID")
    df = pd.merge(df,    qual, how="outer", on="ResourceID")
    df.fillna(0, inplace=True)
    df["availability"] = df.apply(lambda r: r.busy_ticks  / r.total_ticks  if r.total_ticks  else 0.0, axis=1)
    df["performance"]  = df.apply(lambda r: min(r.planned_secs / r.actual_secs, 1.0) if r.actual_secs else 0.0, axis=1)
    df["quality"]      = df.apply(lambda r: 1 - r.errors  / r.total_steps  if r.total_steps  else 1.0, axis=1)
    df["trs"]          = df["availability"] * df["performance"] * df["quality"]
    return df[["ResourceID", "availability", "performance", "quality", "trs"]]


def kpi_machine_load(date_from=None, date_to=None):
    cond, params = [], {}
    if date_from:
        cond.append("TimeStamp >= :date_from")
        params["date_from"] = date_from
    if date_to:
        cond.append("TimeStamp < DATE_ADD(:date_to, INTERVAL 1 DAY)")
        params["date_to"] = date_to
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    df = run_query(f"""
        SELECT ResourceID,
               SUM(CASE WHEN Busy = 1 THEN 1 ELSE 0 END) AS busy_ticks,
               COUNT(*)                                   AS total_ticks
        FROM tblmachinereport
        {where}
        GROUP BY ResourceID
    """, params)
    if df.empty:
        return df
    df["occupation"] = df.apply(lambda r: r.busy_ticks / r.total_ticks if r.total_ticks else 0.0, axis=1)
    return df[["ResourceID", "occupation"]]


def kpi_errors_by_step(date_from=None, date_to=None):
    """KPI 8 – taux d'erreur (%) par numéro d'étape, trié Pareto."""
    cond, params = [], {}
    if date_from:
        cond.append("End >= :date_from")
        params["date_from"] = date_from
    if date_to:
        cond.append("End < DATE_ADD(:date_to, INTERVAL 1 DAY)")
        params["date_to"] = date_to
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    return run_query(f"""
        SELECT StepNo,
               COUNT(*) AS total,
               SUM(CASE WHEN ErrorStep=1 OR ErrorRetVal<>0 THEN 1 ELSE 0 END) AS errors,
               ROUND(
                 100.0 * SUM(CASE WHEN ErrorStep=1 OR ErrorRetVal<>0 THEN 1 ELSE 0 END) / COUNT(*),
                 2
               ) AS error_rate
        FROM tblfinstep
        {where}
        GROUP BY StepNo
        HAVING total > 0
        ORDER BY error_rate DESC
        LIMIT 25
    """, params)


def kpi_top_errors():
    df = run_query("""
        SELECT fs.ErrorRetVal   AS error_code,
               COUNT(*)         AS occurrences,
               mt.ErrorDesc     AS description_mt,
               ec.Description   AS description_ec
        FROM tblfinstep fs
        LEFT JOIN tblmainterror mt ON mt.ErrorNo  = fs.ErrorRetVal
        LEFT JOIN tblerrorcodes ec ON ec.ErrorId  = fs.ErrorRetVal
        WHERE fs.ErrorRetVal <> 0
        GROUP BY fs.ErrorRetVal, mt.ErrorDesc, ec.Description
        ORDER BY occurrences DESC
        LIMIT 10
    """)
    if df.empty:
        return df
    df["description"] = df["description_mt"].fillna(df["description_ec"]).fillna(df["error_code"].astype(str))
    return df[["error_code", "description", "occurrences"]]


def kpi_total_errors(date_from=None, date_to=None) -> int:
    cond, params = [], {}
    if date_from:
        cond.append("End >= :date_from")
        params["date_from"] = date_from
    if date_to:
        cond.append("End < DATE_ADD(:date_to, INTERVAL 1 DAY)")
        params["date_to"] = date_to
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    df = run_query(f"""
        SELECT SUM(CASE WHEN ErrorStep=1 OR ErrorRetVal<>0 THEN 1 ELSE 0 END) AS n
        FROM tblfinstep
        {where}
    """, params)
    val = df.iloc[0]["n"] if not df.empty else 0
    return int(val) if val else 0


def kpi_first_pass_yield(date_from=None, date_to=None):
    cond, params = [], {}
    if date_from:
        cond.append("End >= :date_from")
        params["date_from"] = date_from
    if date_to:
        cond.append("End < DATE_ADD(:date_to, INTERVAL 1 DAY)")
        params["date_to"] = date_to
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    df = run_query(f"""
        SELECT ONo,
               SUM(CASE WHEN ErrorStep=1 OR ErrorRetVal<>0 THEN 1 ELSE 0 END) AS errors
        FROM tblfinstep
        {where}
        GROUP BY ONo
    """, params)
    if df.empty:
        return 0.0, 0, 0
    ok    = int((df["errors"] == 0).sum())
    total = len(df)
    return (ok / total if total else 0.0), ok, total


def get_machine_date_range():
    """Retourne (min_date, max_date) sous forme de str ISO depuis tblmachinereport."""
    df = run_query("""
        SELECT MIN(TimeStamp) AS min_ts, MAX(TimeStamp) AS max_ts
        FROM tblmachinereport
    """)
    if df.empty or df.iloc[0]["min_ts"] is None:
        return None, None
    min_ts = pd.to_datetime(df.iloc[0]["min_ts"])
    max_ts = pd.to_datetime(df.iloc[0]["max_ts"])
    return min_ts.strftime("%Y-%m-%d"), max_ts.strftime("%Y-%m-%d")


def get_finstep_date_range():
    """Retourne (min_date, max_date) depuis tblfinstep.End."""
    df = run_query("""
        SELECT MIN(End) AS min_ts, MAX(End) AS max_ts
        FROM tblfinstep
        WHERE End IS NOT NULL
    """)
    if df.empty or df.iloc[0]["min_ts"] is None:
        return None, None
    min_ts = pd.to_datetime(df.iloc[0]["min_ts"])
    max_ts = pd.to_datetime(df.iloc[0]["max_ts"])
    return min_ts.strftime("%Y-%m-%d"), max_ts.strftime("%Y-%m-%d")


def kpi_mean_downtime(date_from=None, date_to=None):
    conditions = []
    params: dict = {}
    if date_from:
        conditions.append("TimeStamp >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("TimeStamp < DATE_ADD(:date_to, INTERVAL 1 DAY)")
        params["date_to"] = date_to
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    df = run_query(f"""
        SELECT ResourceID, TimeStamp, Busy, ErrorL1, ErrorL2
        FROM tblmachinereport
        {where}
        ORDER BY ResourceID, TimeStamp
    """, params)
    if df.empty:
        return pd.DataFrame()
    df["TimeStamp"] = pd.to_datetime(df["TimeStamp"])
    df["is_error"]  = (df["ErrorL1"] == 1) | (df["ErrorL2"] == 1)
    rows = []
    for rid, grp in df.groupby("ResourceID"):
        grp = grp.sort_values("TimeStamp").reset_index(drop=True)
        grp["shift"] = grp["is_error"].shift(1, fill_value=False)
        starts = grp[(grp["is_error"]) & (~grp["shift"])]["TimeStamp"]
        ends   = grp[(~grp["is_error"]) & (grp["shift"])]["TimeStamp"]
        durs   = [(e - s).total_seconds() / 60 for s, e in zip(starts, ends)]
        total_t = (grp["TimeStamp"].iloc[-1] - grp["TimeStamp"].iloc[0]).total_seconds() / 60 if len(grp) > 1 else 0
        n       = len(durs)
        total_d = sum(durs)
        occ     = (grp["Busy"] == 1).mean()
        rows.append({
            "ResourceID":         rid,
            "occupation":         round(float(occ), 4),
            "total_downtime_min": round(total_d, 2),
            "n_failures":         n,
            "mtbf_min":           round((total_t - total_d) / n if n else total_t, 2),
            "mttr_min":           round(total_d / n if n else 0.0, 2),
        })
    return pd.DataFrame(rows)


def kpi_buffer_fill():
    df = run_query("""
        SELECT ResourceId,
               SUM(CASE WHEN PNo <> 0 THEN 1 ELSE 0 END) AS occupied,
               COUNT(*)                                   AS total_slots
        FROM tblbufferpos
        GROUP BY ResourceId
    """)
    if df.empty:
        return df
    df["fill_rate"] = df.apply(lambda r: r.occupied / r.total_slots if r.total_slots else 0.0, axis=1)
    return df


def kpi_energy_per_piece():
    """KPI 12 – énergie moyenne par OF (divisée par COUNT DISTINCT ONo)."""
    df = run_query("""
        SELECT SUM(ElectricEnergyReal) AS real_energy,
               SUM(ElectricEnergyCalc) AS calc_energy,
               COUNT(DISTINCT ONo)     AS n_orders
        FROM tblfinstep
    """)
    if df.empty or not df.iloc[0]["n_orders"]:
        return 0.0, 0.0
    n = int(df.iloc[0]["n_orders"])
    return float(df.iloc[0]["real_energy"] / n), float(df.iloc[0]["calc_energy"] / n)


def kpi_energy_by_resource():
    return run_query("""
        SELECT ResourceID,
               AVG(ElectricEnergyReal) AS avg_real,
               AVG(ElectricEnergyCalc) AS avg_calc
        FROM tblfinstep
        WHERE ElectricEnergyReal IS NOT NULL
        GROUP BY ResourceID
        ORDER BY avg_real DESC
    """)


def kpi_orders_table():
    return run_query("""
        SELECT fo.ONo          AS ono,
               fo.PlannedStart AS planned_start,
               fo.PlannedEnd   AS planned_end,
               fo.Start        AS actual_start,
               fo.End          AS actual_end,
               fo.State        AS state
        FROM tblfinorder fo
        ORDER BY fo.End DESC
        LIMIT 25
    """)


# ──────────────────────────────────────────────
# CSV SENSOR DATA (data_all.csv / dataEnergy.csv)
# ──────────────────────────────────────────────

_CSV_DIR = os.path.dirname(os.path.abspath(__file__))


def kpi_sensor_power():
    """Charge data_all.csv et retourne une série temporelle de puissance (échantillonnée)."""
    path = os.path.join(_CSV_DIR, "data_all.csv")
    try:
        df = pd.read_csv(path, sep=",")
        df.columns = [c.strip() for c in df.columns]
        cols = ["Timestamp", "ActivePowerL1", "ActivePowerL2", "ActivePowerL3", "ActivePowerTotal"]
        df = df[[c for c in cols if c in df.columns]].copy()
        df.replace("null", pd.NA, inplace=True)
        for c in df.columns[1:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        # Échantillonnage : max 200 points
        step = max(1, len(df) // 200)
        df = df.iloc[::step].reset_index(drop=True)
        return df
    except Exception as exc:
        print(f"[CSV POWER ERROR] {exc}")
        return pd.DataFrame()


def kpi_sensor_pneumatics():
    """Charge data_all.csv et retourne pression + débit (échantillonnés)."""
    path = os.path.join(_CSV_DIR, "data_all.csv")
    try:
        df = pd.read_csv(path, sep=",")
        df.columns = [c.strip() for c in df.columns]
        cols = ["Timestamp", "Pressure", "Flow"]
        df = df[[c for c in cols if c in df.columns]].copy()
        df.replace("null", pd.NA, inplace=True)
        for c in df.columns[1:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        step = max(1, len(df) // 200)
        df = df.iloc[::step].reset_index(drop=True)
        return df
    except Exception as exc:
        print(f"[CSV PNEUMATICS ERROR] {exc}")
        return pd.DataFrame()


def kpi_sensor_energy_stats():
    """Calcule des statistiques globales depuis dataEnergy.csv (min/max/moy)."""
    path = os.path.join(_CSV_DIR, "dataEnergy.csv")
    try:
        df = pd.read_csv(path, sep=";", header=0)
        df.columns = [c.strip() for c in df.columns]
        # Renommage pour accès simple
        rename = {
            "Time [s]": "time_s",
            "Pressure [bar]": "pressure_bar",
            "Flow Rate [l/min]": "flow_lmin",
            "Active Power L1 [W]": "pwr_l1",
            "Active Power L2 [W]": "pwr_l2",
            "Active Power L3 [W]": "pwr_l3",
        }
        df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)
        for c in df.columns[1:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        stats = {}
        for col in ["pressure_bar", "flow_lmin", "pwr_l1", "pwr_l2", "pwr_l3"]:
            if col in df.columns:
                stats[col] = {
                    "min":  round(float(df[col].min()), 3),
                    "max":  round(float(df[col].max()), 3),
                    "mean": round(float(df[col].mean()), 3),
                }
        # Série temporelle échantillonnée pour graphique (max 300 pts)
        step = max(1, len(df) // 300)
        sample = df[["time_s"] + [c for c in ["pwr_l1", "pwr_l2", "pwr_l3"] if c in df.columns]].iloc[::step]
        return stats, json.loads(sample.to_json(orient="records"))
    except Exception as exc:
        print(f"[CSV ENERGY STATS ERROR] {exc}")
        return {}, []
