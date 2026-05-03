import sqlite3
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "readings.db"

AQI_BANDS = [
    (0,   12,   "Good",            "#00e400"),
    (12,  35.4, "Moderate",        "#ffff00"),
    (35.4,55.4, "Unhealthy (Sensitive)", "#ff7e00"),
    (55.4,150.4,"Unhealthy",       "#ff0000"),
    (150.4,250.4,"Very Unhealthy", "#8f3f97"),
    (250.4,float("inf"),"Hazardous","#7e0023"),
]


def pm25_label(value):
    if value is None:
        return "No data", "#888"
    for lo, hi, label, colour in AQI_BANDS:
        if lo <= value < hi:
            return label, colour
    return "Hazardous", "#7e0023"


@st.cache_data(ttl=10)
def load_data(limit: int = 2000) -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql(
            "SELECT * FROM readings ORDER BY timestamp DESC LIMIT ?",
            conn,
            params=(limit,),
        )
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp")
    return df


def main() -> None:  # noqa: C901
    """Run the Streamlit dashboard app."""
    # ── Page config ───────────────────────────────────────────────────────────
    st.set_page_config(
        page_title="AirQualityPi",
        page_icon="🌿",
        layout="wide",
    )

    st.title("🌿 AirQualityPi Dashboard")

    # ── Sidebar controls ──────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Settings")
        hours = st.slider("Show last N hours", min_value=1, max_value=168, value=24)
        refresh_interval = st.slider("Auto-refresh every (seconds)", min_value=10, max_value=300, value=60, step=5)
        st.caption(f"Dashboard will refresh every {refresh_interval} seconds.")

    df = load_data()

    if df.empty:
        st.warning(
            "No readings found in the database yet. "
            "Run `Sensors.py` at least once to populate data."
        )
        st.stop()
        return

    # Filter to selected time window
    cutoff = df["timestamp"].max() - pd.Timedelta(hours=hours)
    df = df[df["timestamp"] >= cutoff]

    if df.empty:
        st.warning("No readings in the selected time window. Try increasing the hours slider.")
        st.stop()
        return

    latest = df.iloc[-1]

    # ── KPI row ───────────────────────────────────────────────────────────────
    st.subheader("Latest Reading")

    pm25_val = latest.get("pm2_5")
    aqi_label, aqi_colour = pm25_label(pm25_val)

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "PM2.5",
        f"{pm25_val:.1f} µg/m³" if pm25_val is not None else "—",
        help="Fine particulate matter (≤ 2.5 µm)",
    )
    col2.metric(
        "PM10",
        f"{latest['pm10']:.1f} µg/m³" if latest.get("pm10") is not None else "—",
        help="Coarse particulate matter (≤ 10 µm)",
    )
    col3.metric(
        "Temperature",
        f"{latest['temp']:.1f} °C" if latest.get("temp") is not None else "—",
    )
    col4.metric(
        "Humidity",
        f"{latest['humidity']:.1f} %" if latest.get("humidity") is not None else "—",
    )
    col5.metric(
        "Pressure",
        f"{latest['pressure']:.1f} hPa" if latest.get("pressure") is not None else "—",
    )

    st.markdown(
        f"**Air Quality:** "
        f"<span style='background:{aqi_colour};padding:2px 10px;border-radius:4px;"
        f"color:{'#000' if aqi_colour in ('#00e400','#ffff00') else '#fff'}'>"  
        f"{aqi_label}</span>",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Particulate matter chart ──────────────────────────────────────────────
    st.subheader("Particulate Matter Over Time")

    fig_pm = go.Figure()
    for col, label, colour in [
        ("pm1_0", "PM1.0", "#4c78a8"),
        ("pm2_5", "PM2.5", "#f58518"),
        ("pm10",  "PM10",  "#e45756"),
    ]:
        mask = df[col].notna()
        fig_pm.add_scatter(
            x=df.loc[mask, "timestamp"],
            y=df.loc[mask, col],
            name=label,
            line=dict(color=colour),
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>" + label + ": %{y:.1f} µg/m³<extra></extra>",
        )

    # Add WHO PM2.5 guideline line at 15 µg/m³
    fig_pm.add_hline(
        y=15,
        line_dash="dot",
        line_color="gray",
        annotation_text="WHO PM2.5 guideline (15 µg/m³)",
        annotation_position="bottom right",
    )

    fig_pm.update_layout(
        yaxis_title="µg/m³",
        legend=dict(orientation="h"),
        margin=dict(t=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig_pm, use_container_width=True)

    # ── Temperature & humidity chart ──────────────────────────────────────────
    st.subheader("Temperature & Humidity Over Time")

    fig_env = go.Figure()

    mask_temp = df["temp"].notna()
    fig_env.add_scatter(
        x=df.loc[mask_temp, "timestamp"],
        y=df.loc[mask_temp, "temp"],
        name="Temperature (°C)",
        line=dict(color="#e45756"),
        hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Temp: %{y:.1f} °C<extra></extra>",
    )

    mask_hum = df["humidity"].notna()
    fig_env.add_scatter(
        x=df.loc[mask_hum, "timestamp"],
        y=df.loc[mask_hum, "humidity"],
        name="Humidity (%)",
        line=dict(color="#4c78a8"),
        yaxis="y2",
        hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Humidity: %{y:.1f} %<extra></extra>",
    )

    fig_env.update_layout(
        yaxis=dict(title=dict(text="Temperature (°C)", font=dict(color="#e45756"))),
        yaxis2=dict(
            title=dict(text="Humidity (%)", font=dict(color="#4c78a8")),
            overlaying="y",
            side="right",
            range=[0, 100],
        ),
        legend=dict(orientation="h"),
        margin=dict(t=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig_env, use_container_width=True)

    # ── Pressure chart ────────────────────────────────────────────────────────
    st.subheader("Barometric Pressure Over Time")

    mask_pres = df["pressure"].notna()
    fig_pres = go.Figure()
    fig_pres.add_scatter(
        x=df.loc[mask_pres, "timestamp"],
        y=df.loc[mask_pres, "pressure"],
        name="Pressure (hPa)",
        line=dict(color="#72b7b2"),
        fill="tozeroy",
        fillcolor="rgba(114,183,178,0.15)",
        hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Pressure: %{y:.1f} hPa<extra></extra>",
    )
    fig_pres.update_layout(
        yaxis_title="hPa",
        margin=dict(t=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig_pres, use_container_width=True)

    # ── Raw data table ────────────────────────────────────────────────────────
    with st.expander("Raw readings table"):
        display = df.copy()
        display["timestamp"] = display["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        st.dataframe(
            display[["timestamp", "pm1_0", "pm2_5", "pm10", "temp", "humidity", "pressure", "altitude"]]
            .rename(columns={
                "timestamp": "Timestamp",
                "pm1_0": "PM1.0",
                "pm2_5": "PM2.5",
                "pm10": "PM10",
                "temp": "Temp (°C)",
                "humidity": "Humidity (%)",
                "pressure": "Pressure (hPa)",
                "altitude": "Altitude (m)",
            })
            .reset_index(drop=True),
            use_container_width=True,
        )

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    time.sleep(refresh_interval)
    load_data.clear()
    st.rerun()


if __name__ == "__main__":
    main()
