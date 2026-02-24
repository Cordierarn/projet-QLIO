import os
from datetime import timedelta

import pandas as pd
import streamlit as st
import altair as alt
from sqlalchemy import create_engine, text


DEFAULT_DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "example_root_password"),
    "database": os.getenv("DB_NAME", "MES4"),
}


@st.cache_resource(show_spinner=False)
def get_engine():
    url = (
        f"mysql+pymysql://{DEFAULT_DB['user']}:{DEFAULT_DB['password']}"
        f"@{DEFAULT_DB['host']}:{DEFAULT_DB['port']}/{DEFAULT_DB['database']}"
    )
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=300, show_spinner=False)
def run_query(query: str, params: dict | None = None):
    try:
        with get_engine().connect() as conn:
            return pd.read_sql_query(text(query), conn, params=params or {})
    except Exception as exc:  # pragma: no cover - Streamlit friendly error
        st.error(f"Connexion BDD impossible : {exc}")
        return pd.DataFrame()


def kpi_in_progress():
    query = """
        SELECT CONCAT(ONo, '-', OPos) AS order_ref, COUNT(*) AS active_steps
        FROM tblstep
        WHERE Active = 1
        GROUP BY CONCAT(ONo, '-', OPos)
        ORDER BY active_steps DESC
    """
    df = run_query(query)
    total = int(df["active_steps"].sum()) if not df.empty else 0
    return total, df


def kpi_lead_time_delta(date_clause: str, params: dict):
    query = """
        SELECT
            CONCAT(ONo, '-', OPos) AS order_ref,
            TIMESTAMPDIFF(SECOND, PlannedStart, PlannedEnd) AS planned_secs,
            TIMESTAMPDIFF(SECOND, Start, End) AS actual_secs
        FROM tblfinorderpos
        WHERE Start IS NOT NULL AND End IS NOT NULL {date_clause}
    """
    df = run_query(query.format(date_clause=date_clause), params)
    if df.empty:
        return pd.DataFrame()
    df["delta_secs"] = df["actual_secs"] - df["planned_secs"]
    return df


def kpi_production_progress():
    planned = run_query("SELECT COUNT(*) AS n FROM tblorder")
    finished = run_query("SELECT COUNT(*) AS n FROM tblfinorder")
    active_orders = run_query(
        "SELECT COUNT(DISTINCT ONo) AS n FROM tblstep WHERE Active = 1"
    )
    planned_total = int(planned["n"].iloc[0]) if not planned.empty else 0
    finished_total = int(finished["n"].iloc[0]) if not finished.empty else 0
    active_total = int(active_orders["n"].iloc[0]) if not active_orders.empty else 0

    denom = planned_total + finished_total or 1
    ratio = active_total / denom
    return {
        "planned": planned_total,
        "finished": finished_total,
        "active": active_total,
        "ratio": ratio,
    }


def kpi_finished_per_day(date_clause: str, params: dict):
    query = """
        SELECT DATE(End) AS jour, COUNT(*) AS nb_ordres
        FROM tblfinorder
        WHERE End IS NOT NULL {date_clause}
        GROUP BY DATE(End)
        ORDER BY jour
    """
    return run_query(query.format(date_clause=date_clause), params)


def kpi_trs():
    availability = run_query(
        """
        SELECT ResourceID,
               SUM(CASE WHEN Busy = 1 THEN 1 ELSE 0 END) AS busy_ticks,
               COUNT(*) AS total_ticks
        FROM tblmachinereport
        GROUP BY ResourceID
        """
    )

    performance = run_query(
        """
        SELECT ResourceID,
               AVG(TIMESTAMPDIFF(SECOND, PlannedStart, PlannedEnd)) AS planned_secs,
               AVG(TIMESTAMPDIFF(SECOND, Start, End)) AS actual_secs
        FROM tblfinstep
        WHERE Start IS NOT NULL AND End IS NOT NULL
        GROUP BY ResourceID
        """
    )

    quality = run_query(
        """
        SELECT ResourceID,
               SUM(CASE WHEN ErrorStep = 1 OR ErrorRetVal <> 0 THEN 1 ELSE 0 END) AS errors,
               COUNT(*) AS total_steps
        FROM tblfinstep
        GROUP BY ResourceID
        """
    )

    if availability.empty and performance.empty and quality.empty:
        return pd.DataFrame()

    df = pd.merge(availability, performance, how="outer", on="ResourceID")
    df = pd.merge(df, quality, how="outer", on="ResourceID")
    df.fillna(0, inplace=True)

    df["availability"] = df.apply(
        lambda r: r.busy_ticks / r.total_ticks if r.total_ticks else 0.0, axis=1
    )
    df["performance"] = df.apply(
        lambda r: r.planned_secs / r.actual_secs if r.actual_secs else 0.0, axis=1
    )
    df["quality"] = df.apply(
        lambda r: 1 - (r.errors / r.total_steps) if r.total_steps else 1.0, axis=1
    )
    df["trs"] = df["availability"] * df["performance"] * df["quality"]
    return df[
        [
            "ResourceID",
            "availability",
            "performance",
            "quality",
            "trs",
        ]
    ]


def kpi_machine_load():
    query = """
        SELECT ResourceID,
               SUM(CASE WHEN Busy = 1 THEN 1 ELSE 0 END) AS busy_ticks,
               COUNT(*) AS total_ticks
        FROM tblmachinereport
        GROUP BY ResourceID
    """
    df = run_query(query)
    if df.empty:
        return df
    df["occupation"] = df.apply(
        lambda r: r.busy_ticks / r.total_ticks if r.total_ticks else 0.0, axis=1
    )
    return df[["ResourceID", "occupation"]]


def kpi_top_errors():
    query = """
        SELECT fs.ErrorRetVal AS error_code,
               COUNT(*) AS occurrences,
               mt.ErrorDesc AS description_mt,
               ec.Description AS description_ec
        FROM tblfinstep fs
        LEFT JOIN tblmainterror mt ON mt.ErrorNo = fs.ErrorRetVal
        LEFT JOIN tblerrorcodes ec ON ec.ErrorId = fs.ErrorRetVal
        WHERE fs.ErrorRetVal <> 0
        GROUP BY fs.ErrorRetVal, mt.ErrorDesc, ec.Description
        ORDER BY occurrences DESC
        LIMIT 10
    """
    df = run_query(query)
    if df.empty:
        return df
    df["description"] = df["description_mt"].fillna(df["description_ec"])
    return df[["error_code", "description", "occurrences"]]


def kpi_error_rate():
    query = """
        SELECT
            ResourceID,
            SUM(CASE WHEN ErrorStep = 1 OR ErrorRetVal <> 0 THEN 1 ELSE 0 END) AS errors,
            COUNT(*) AS steps
        FROM tblfinstep
        GROUP BY ResourceID
    """
    df = run_query(query)
    if df.empty:
        return df
    df["error_rate"] = df.apply(
        lambda r: r.errors / r.steps if r.steps else 0.0,
        axis=1,
    )
    return df


def kpi_first_pass_yield():
    query = """
        SELECT fs.ONo,
               SUM(CASE WHEN ErrorStep = 1 OR ErrorRetVal <> 0 THEN 1 ELSE 0 END) AS errors,
               COUNT(*) AS steps
        FROM tblfinstep fs
        GROUP BY fs.ONo
    """
    df = run_query(query)
    if df.empty:
        return 0.0
    ok_orders = (df["errors"] == 0).sum()
    total_orders = len(df)
    return ok_orders / total_orders if total_orders else 0.0


def kpi_mean_downtime():
    query = """
        SELECT ResourceID, TimeStamp, ErrorL1, ErrorL2
        FROM tblmachinereport
        ORDER BY ResourceID, TimeStamp
    """
    df = run_query(query)
    if df.empty:
        return pd.DataFrame()

    df["TimeStamp"] = pd.to_datetime(df["TimeStamp"])
    df["is_error"] = (df["ErrorL1"] == 1) | (df["ErrorL2"] == 1)

    rows = []
    for rid, group in df.groupby("ResourceID"):
        group = group.sort_values("TimeStamp")
        group["shift"] = group["is_error"].shift(1, fill_value=False)
        starts = group[(group["is_error"]) & (~group["shift"])]["TimeStamp"]
        ends = group[(~group["is_error"]) & (group["shift"])]["TimeStamp"]
        pairs = zip(starts, ends) if len(ends) >= len(starts) else zip(starts, ends)
        durations = [(e - s).total_seconds() / 60 for s, e in pairs]
        mean_minutes = sum(durations) / len(durations) if durations else 0.0
        rows.append({"ResourceID": rid, "mean_downtime_min": mean_minutes})

    return pd.DataFrame(rows)


def kpi_buffer_fill():
    query = """
        SELECT
            ResourceId,
            SUM(CASE WHEN PNo <> 0 THEN 1 ELSE 0 END) AS occupied,
            COUNT(*) AS total_slots
        FROM tblbufferpos
        GROUP BY ResourceId
    """
    df = run_query(query)
    if df.empty:
        return df
    df["fill_rate"] = df.apply(
        lambda r: r.occupied / r.total_slots if r.total_slots else 0.0,
        axis=1,
    )
    return df


def kpi_energy_per_piece():
    query = """
        SELECT
            SUM(ElectricEnergyReal) AS real_energy,
            SUM(ElectricEnergyCalc) AS calc_energy,
            COUNT(*) AS steps
        FROM tblfinstep
    """
    df = run_query(query)
    if df.empty or df.iloc[0]["steps"] == 0:
        return 0.0, 0.0
    steps = df.iloc[0]["steps"]
    return df.iloc[0]["real_energy"] / steps, df.iloc[0]["calc_energy"] / steps


@st.cache_data(ttl=600, show_spinner=False)
def load_robotino():
    path = "robotino_data.csv"
    if not os.path.exists(path):
        return pd.DataFrame()
    cols = [
        "timestamp",
        "odometry_x",
        "odometry_y",
        "odometry_phi",
        "odometry_vx",
        "odometry_vy",
        "power_voltage",
        "power_output_current",
    ]
    df = pd.read_csv(path, usecols=[c for c in cols if c], parse_dates=["timestamp"])
    df.sort_values("timestamp", inplace=True)
    return df


def robotino_metrics(df: pd.DataFrame):
    if df.empty:
        return {}
    df["dx"] = df["odometry_x"].diff()
    df["dy"] = df["odometry_y"].diff()
    df["segment_len"] = (df["dx"] ** 2 + df["dy"] ** 2) ** 0.5
    total_distance = df["segment_len"].sum()
    duration = df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]
    avg_v = df[["odometry_vx", "odometry_vy"]].pow(2).sum(axis=1).pow(0.5).mean()
    df["power_w"] = df["power_voltage"] * df["power_output_current"]
    avg_power = df["power_w"].mean()
    return {
        "distance_m": total_distance,
        "duration": duration,
        "avg_speed": avg_v,
        "avg_power": avg_power,
    }


def main():
    st.set_page_config(page_title="Pilotage Festo MES 4.0", layout="wide")
    alt.data_transformers.disable_max_rows()

    def sf_theme():
        font = "SF Pro Display, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        return {
            "config": {
                "title": {"font": font, "fontSize": 17, "color": "#111827"},
                "axis": {
                    "labelFont": font,
                    "titleFont": font,
                    "labelColor": "#1f2937",
                    "titleColor": "#111827",
                    "gridColor": "#e5e7eb",
                    "tickColor": "#e5e7eb",
                },
                "legend": {
                    "labelFont": font,
                    "titleFont": font,
                    "labelColor": "#1f2937",
                    "titleColor": "#111827",
                },
                "view": {"stroke": "transparent"},
                "background": "transparent",
            }
        }

    alt.themes.register("sf-theme", sf_theme)
    alt.themes.enable("sf-theme")

    st.sidebar.header("Filtres")

    @st.cache_data(ttl=300, show_spinner=False)
    def load_filter_values():
        dates = run_query(
            "SELECT MIN(PlannedStart) AS min_date, MAX(End) AS max_date FROM tblfinorder"
        )
        res = run_query("SELECT DISTINCT ResourceID FROM tblmachinereport ORDER BY ResourceID")
        parts = run_query("SELECT DISTINCT PNo FROM tblfinorderpos WHERE PNo IS NOT NULL AND PNo <> 0 ORDER BY PNo")
        return dates, res["ResourceID"].tolist(), parts["PNo"].tolist()

    dates_df, resources_all, parts_all = load_filter_values()
    min_date = dates_df["min_date"].iloc[0] if not dates_df.empty else None
    max_date = dates_df["max_date"].iloc[0] if not dates_df.empty else None

    date_range = st.sidebar.date_input(
        "Plage de dates (End)",
        value=(min_date, max_date) if min_date and max_date else None,
    )
    selected_resources = st.sidebar.multiselect(
        "Ressources", options=resources_all, default=resources_all[:4] if resources_all else []
    )
    selected_parts = st.sidebar.multiselect(
        "Pièces (PNo)", options=parts_all, default=parts_all[:6] if parts_all else []
    )

    def sql_filters(table_alias: str, date_field: str = "End"):
        clauses = []
        params = {}
        if date_range and len(date_range) == 2 and all(date_range):
            clauses.append(f"{table_alias}.{date_field} BETWEEN :d_start AND :d_end")
            params["d_start"] = str(date_range[0])
            params["d_end"] = str(date_range[1])
        return clauses, params

    def apply_resource_filter(base_query: str, alias: str) -> str:
        if selected_resources:
            ids = ",".join(str(r) for r in selected_resources)
            return base_query.replace("__RESOURCE_FILTER__", f"AND {alias}.ResourceID IN ({ids})")
        return base_query.replace("__RESOURCE_FILTER__", "")

    st.markdown(
        """
        <style>
        :root {
            --bg: #f5f5f7;
            --card: #ffffff;
            --muted: #6b7280;
            --accent: #007aff;
            --accent2: #34c759;
        }
        body {background: var(--bg); color: #0f172a; font-family: 'SF Pro Display','SF Pro Text','-apple-system', 'BlinkMacSystemFont', 'Segoe UI', system-ui, sans-serif;}
        .block-container {padding-top: 1.1rem; padding-bottom: 2.2rem;}
        .metric-card {padding:1rem 1.2rem;border-radius:16px;background:var(--card);border:1px solid #e5e7eb;box-shadow:0 12px 28px rgba(0,0,0,0.07);}
        .section {margin-top: 1.4rem; padding: 1.2rem; border-radius: 16px; background: var(--card); border:1px solid #e5e7eb; box-shadow:0 16px 32px rgba(15,23,42,0.08);}
        h1,h2,h3,h4 {color:#0f172a; letter-spacing:-0.02em;}
        .stDataFrame, .stDataFrame table {color: #0f172a;}
        .css-1v0mbdj, .css-1fcdlhv {background: transparent;}
        .stMarkdown p, .stMarkdown div {color: #0f172a;}
        .hero {padding: 18px 20px; border-radius: 18px; background: linear-gradient(135deg, #0f82ff, #34c8ff); color: #f7fbff; border: 1px solid rgba(255,255,255,0.55); box-shadow:0 22px 48px rgba(0,122,255,0.28);}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="hero">
            <div style="font-size: 14px; opacity: 0.9;">Dashboard MES 4.0 – Sprint 1</div>
            <div style="font-size: 28px; font-weight: 700;">Pilotage Festo / Robotino</div>
            <div style="font-size: 14px; opacity: 0.9;">Connexions : {user}@{host}:{port}/{db}</div>
        </div>
        """.format(
            user=DEFAULT_DB["user"],
            host=DEFAULT_DB["host"],
            port=DEFAULT_DB["port"],
            db=DEFAULT_DB["database"],
        ),
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.subheader("Production en cours")
    in_progress_total, in_progress_df = kpi_in_progress()
    progress = kpi_production_progress()
    col_cards = st.columns(3)
    col_cards[0].markdown(
        f'<div class="metric-card"><div>Pièces en cours</div><h2>{in_progress_total}</h2></div>',
        unsafe_allow_html=True,
    )
    col_cards[1].markdown(
        f'<div class="metric-card"><div>Taux d’avancement</div><h2>{progress["ratio"]*100:0.1f}%</h2><small>Ordres en cours / (planifiés + terminés)</small></div>',
        unsafe_allow_html=True,
    )
    col_cards[2].markdown(
        f'<div class="metric-card"><div>Ordres terminés</div><h2>{progress["finished"]}</h2></div>',
        unsafe_allow_html=True,
    )
    if not in_progress_df.empty:
        top_df = in_progress_df.head(12)
        chart = (
            alt.Chart(top_df)
            .mark_bar(color="#2563eb")
            .encode(
                x=alt.X("order_ref:N", sort="-y", axis=alt.Axis(labelAngle=-35)),
                y=alt.Y("active_steps:Q", title="Étapes actives"),
                tooltip=["order_ref", "active_steps"],
            )
            .properties(height=220)
        )
        st.altair_chart(chart, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    col_cycle, col_done = st.columns(2)
    with col_cycle:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Temps de cycle (réel vs prévu)")
        _clauses, _params = sql_filters("tblfinorderpos")
        _date_clause = ("AND " + " AND ".join(_clauses)) if _clauses else ""
        lead_time_df = kpi_lead_time_delta(_date_clause, _params)
        if lead_time_df.empty:
            st.info("Pas de données de cycle disponibles.")
        else:
            recent = lead_time_df.tail(120)
            chart = (
                alt.Chart(recent)
                .mark_line(color="#2563eb", point=True)
                .encode(
                    x=alt.X("order_ref:N", axis=alt.Axis(labelAngle=-65, labelLimit=160), title="Ordre"),
                    y=alt.Y("delta_secs:Q", title="Δ (s)"),
                    tooltip=["order_ref", "planned_secs", "actual_secs", "delta_secs"],
                )
                .properties(height=260)
            )
            st.altair_chart(chart, use_container_width=True)
            stats = recent["delta_secs"].describe()
            st.write(
                f"Δ médian : {timedelta(seconds=int(stats['50%']))} | "
                f"Δ moyen : {timedelta(seconds=int(stats['mean']))}"
            )
        st.markdown('</div>', unsafe_allow_html=True)

    with col_done:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Ordres terminés par jour")
        _clauses2, _params2 = sql_filters("tblfinorder")
        _date_clause2 = ("AND " + " AND ".join(_clauses2)) if _clauses2 else ""
        finished_df = kpi_finished_per_day(_date_clause2, _params2)
        if finished_df.empty:
            st.info("Pas d'ordres terminés.")
        else:
            chart = (
                alt.Chart(finished_df)
                .mark_bar(color="#12a4d9")
                .encode(
                    x=alt.X("jour:T", title="Jour", axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("nb_ordres:Q", title="Ordres terminés"),
                    tooltip=["jour", "nb_ordres"],
                )
                .properties(height=260)
            )
            st.altair_chart(chart, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.subheader("Performance TRS / OEE")
    trs_df = kpi_trs()
    if trs_df.empty:
        st.info("Pas de données TRS calculables.")
    else:
        st.dataframe(
            trs_df.round(3),
            hide_index=True,
            use_container_width=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.subheader("Charge et qualité machines")
    machine_load = kpi_machine_load()
    error_rate = kpi_error_rate()
    col_a, col_b = st.columns(2)
    if machine_load.empty:
        col_a.info("Pas de données de charge.")
    else:
        col_a.dataframe(
            machine_load[["ResourceID", "occupation"]].round(3),
            hide_index=True,
            use_container_width=True,
        )
    if error_rate.empty:
        col_b.info("Pas de taux d'erreur.")
    else:
        col_b.dataframe(
            error_rate[["ResourceID", "error_rate"]].round(3),
            hide_index=True,
            use_container_width=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.subheader("Qualité et incidents")
    top_errors = kpi_top_errors()
    fp_yield = kpi_first_pass_yield()
    downtime = kpi_mean_downtime()
    col1, col2 = st.columns(2)
    if top_errors.empty:
        col1.info("Pas d'erreurs enregistrées.")
    else:
        col1.dataframe(
            top_errors,
            hide_index=True,
            use_container_width=True,
        )
    col2.metric("First Pass Yield", f"{fp_yield*100:0.1f} %")
    if downtime.empty:
        col2.info("Pas de temps d'arrêt moyen calculable.")
    else:
        col2.dataframe(
            downtime.round(2),
            hide_index=True,
            use_container_width=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.subheader("Buffers & énergie")
    buf_df = kpi_buffer_fill()
    real_epp, calc_epp = kpi_energy_per_piece()
    c1, c2 = st.columns(2)
    if buf_df.empty:
        c1.info("Pas de positions de buffer.")
    else:
        c1.dataframe(
            buf_df[["ResourceId", "fill_rate"]].round(3),
            hide_index=True,
            use_container_width=True,
        )
    c2.metric(
        "Énergie par étape (réelle/calculée)",
        f"{real_epp:0.1f} / {calc_epp:0.1f} mWs",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.subheader("Robotino (CSV)")
    robotino_df = load_robotino()
    if robotino_df.empty:
        st.info("robotino_data.csv introuvable.")
    else:
        metrics = robotino_metrics(robotino_df)
        st.write(
            f"Distance : {metrics['distance_m']:.1f} m | "
            f"Durée : {metrics['duration']} | "
            f"Vitesse moyenne : {metrics['avg_speed']:.3f} m/s | "
            f"Puissance moyenne estimée : {metrics['avg_power']:.2f} W"
        )
        path_df = robotino_df[["odometry_x", "odometry_y", "timestamp"]].dropna()
        if path_df.empty:
            st.info("Pas de coordonnées exploitables pour le tracé.")
        else:
            chart = (
                alt.Chart(path_df)
                .mark_line(color="#f97316", strokeWidth=2)
                .encode(
                    x=alt.X("odometry_x:Q", title="X (m)"),
                    y=alt.Y("odometry_y:Q", title="Y (m)"),
                    color=alt.Color("timestamp:T", title="Temps", scale=alt.Scale(scheme="orangered")),
                )
                .properties(height=320, background="#edf2f7")
            )
            speed_df = robotino_df[["timestamp", "odometry_vx", "odometry_vy"]].melt(
                id_vars=["timestamp"], var_name="axis", value_name="speed"
            )
            speed_chart = (
                alt.Chart(speed_df)
                .mark_area(line={"color": "#2563eb"}, color="rgba(37,99,235,0.18)")
                .encode(
                    x=alt.X("timestamp:T", title="Temps"),
                    y=alt.Y("speed:Q", title="Vitesse (m/s)"),
                    color=alt.Color("axis:N", title="Axe", scale=alt.Scale(scheme="blues")),
                )
                .properties(height=180, width="container")
            )
            col_path, col_speed = st.columns(2)
            with col_path:
                st.altair_chart(chart, use_container_width=True)
                heatmap = (
                    alt.Chart(path_df)
                    .mark_rect()
                    .encode(
                        x=alt.X("odometry_x:Q", bin=alt.Bin(maxbins=50), title="X (m)"),
                        y=alt.Y("odometry_y:Q", bin=alt.Bin(maxbins=50), title="Y (m)"),
                        color=alt.Color("count():Q", title="Densité", scale=alt.Scale(scheme="blues")),
                    )
                    .properties(height=240, background="#f8fafc")
                )
                st.altair_chart(heatmap, use_container_width=True)
            with col_speed:
                st.altair_chart(speed_chart, use_container_width=True)
        st.caption(
            "Idées : heatmap des vitesses, détecter les arrêts (vx/vy ≈ 0), "
            "corréler les pics d'intensité aux déplacements."
        )
    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
