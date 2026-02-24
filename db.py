import os
import json
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text

DEFAULT_DB = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", "example_root_password"),
    "database": os.getenv("DB_NAME",     "MES4"),
}

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = (
            f"mysql+pymysql://{DEFAULT_DB['user']}:{DEFAULT_DB['password']}"
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
    df = run_query("""
        SELECT CONCAT(ONo, '-', OPos) AS order_ref,
               COUNT(*) AS active_steps
        FROM tblstep
        WHERE Active = 1
        GROUP BY CONCAT(ONo, '-', OPos)
        ORDER BY active_steps DESC
    """)
    total = int(df["active_steps"].sum()) if not df.empty else 0
    return total, df


def kpi_production_progress():
    planned  = run_query("SELECT COUNT(*) AS n FROM tblorder")
    finished = run_query("SELECT COUNT(*) AS n FROM tblfinorder")
    active   = run_query("SELECT COUNT(DISTINCT ONo) AS n FROM tblstep WHERE Active = 1")
    p = int(planned["n"].iloc[0])  if not planned.empty  else 0
    f = int(finished["n"].iloc[0]) if not finished.empty else 0
    a = int(active["n"].iloc[0])   if not active.empty   else 0
    return {"planned": p, "finished": f, "active": a, "ratio": round(a / (p + f or 1), 4)}


def kpi_lead_time_delta(date_clause: str = "", params: dict | None = None):
    df = run_query(f"""
        SELECT CONCAT(ONo, '-', OPos)                          AS order_ref,
               TIMESTAMPDIFF(SECOND, PlannedStart, PlannedEnd) AS planned_secs,
               TIMESTAMPDIFF(SECOND, Start, End)               AS actual_secs
        FROM tblfinorderpos
        WHERE Start IS NOT NULL AND End IS NOT NULL {date_clause}
    """, params or {})
    if df.empty:
        return df
    df["delta_secs"] = df["actual_secs"] - df["planned_secs"]
    return df


def kpi_finished_per_day(date_clause: str = "", params: dict | None = None):
    return run_query(f"""
        SELECT DATE(End) AS jour, COUNT(*) AS nb_ordres
        FROM tblfinorder
        WHERE End IS NOT NULL {date_clause}
        GROUP BY DATE(End)
        ORDER BY jour
    """, params or {})


def kpi_trs():
    avail = run_query("""
        SELECT ResourceID,
               SUM(CASE WHEN Busy = 1 THEN 1 ELSE 0 END) AS busy_ticks,
               COUNT(*)                                   AS total_ticks
        FROM tblmachinereport
        GROUP BY ResourceID
    """)
    perf = run_query("""
        SELECT ResourceID,
               AVG(TIMESTAMPDIFF(SECOND, PlannedStart, PlannedEnd)) AS planned_secs,
               AVG(TIMESTAMPDIFF(SECOND, Start, End))               AS actual_secs
        FROM tblfinstep
        WHERE Start IS NOT NULL AND End IS NOT NULL
        GROUP BY ResourceID
    """)
    qual = run_query("""
        SELECT ResourceID,
               SUM(CASE WHEN ErrorStep=1 OR ErrorRetVal<>0 THEN 1 ELSE 0 END) AS errors,
               COUNT(*)                                                         AS total_steps
        FROM tblfinstep
        GROUP BY ResourceID
    """)
    if avail.empty and perf.empty and qual.empty:
        return pd.DataFrame()
    df = pd.merge(avail, perf, how="outer", on="ResourceID")
    df = pd.merge(df,    qual, how="outer", on="ResourceID")
    df.fillna(0, inplace=True)
    df["availability"] = df.apply(lambda r: r.busy_ticks  / r.total_ticks  if r.total_ticks  else 0.0, axis=1)
    df["performance"]  = df.apply(lambda r: r.planned_secs / r.actual_secs if r.actual_secs  else 0.0, axis=1)
    df["quality"]      = df.apply(lambda r: 1 - r.errors  / r.total_steps  if r.total_steps  else 1.0, axis=1)
    df["trs"]          = df["availability"] * df["performance"] * df["quality"]
    return df[["ResourceID", "availability", "performance", "quality", "trs"]]


def kpi_machine_load():
    df = run_query("""
        SELECT ResourceID,
               SUM(CASE WHEN Busy = 1 THEN 1 ELSE 0 END) AS busy_ticks,
               COUNT(*)                                   AS total_ticks
        FROM tblmachinereport
        GROUP BY ResourceID
    """)
    if df.empty:
        return df
    df["occupation"] = df.apply(lambda r: r.busy_ticks / r.total_ticks if r.total_ticks else 0.0, axis=1)
    return df[["ResourceID", "occupation"]]


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


def kpi_total_errors() -> int:
    df = run_query("""
        SELECT SUM(CASE WHEN ErrorStep=1 OR ErrorRetVal<>0 THEN 1 ELSE 0 END) AS n
        FROM tblfinstep
    """)
    val = df.iloc[0]["n"] if not df.empty else 0
    return int(val) if val else 0


def kpi_first_pass_yield():
    df = run_query("""
        SELECT ONo,
               SUM(CASE WHEN ErrorStep=1 OR ErrorRetVal<>0 THEN 1 ELSE 0 END) AS errors
        FROM tblfinstep
        GROUP BY ONo
    """)
    if df.empty:
        return 0.0, 0, 0
    ok    = int((df["errors"] == 0).sum())
    total = len(df)
    return (ok / total if total else 0.0), ok, total


def kpi_mean_downtime():
    df = run_query("""
        SELECT ResourceID, TimeStamp, Busy, ErrorL1, ErrorL2
        FROM tblmachinereport
        ORDER BY ResourceID, TimeStamp
    """)
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
    df = run_query("""
        SELECT SUM(ElectricEnergyReal) AS real_energy,
               SUM(ElectricEnergyCalc) AS calc_energy,
               COUNT(*)                AS steps
        FROM tblfinstep
    """)
    if df.empty or df.iloc[0]["steps"] == 0:
        return 0.0, 0.0
    steps = df.iloc[0]["steps"]
    return float(df.iloc[0]["real_energy"] / steps), float(df.iloc[0]["calc_energy"] / steps)


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
