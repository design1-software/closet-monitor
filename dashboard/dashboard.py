"""
Closet Monitor — Live Dashboard

A Streamlit dashboard showing the current state of the network closet
plus the last 24 hours of telemetry.

Run: streamlit run dashboard.py
Stop: Ctrl+C
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ----- Config -----
DB_PATH = Path(__file__).parent.parent / "data" / "closet.db"
REFRESH_SECONDS = 30  # auto-refresh interval

# ----- Page setup -----
st.set_page_config(
    page_title="Closet Monitor",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----- Data loading -----
@st.cache_data(ttl=REFRESH_SECONDS)
def load_data(hours: int = 24) -> pd.DataFrame:
    """Load the last N hours of readings from SQLite."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM readings WHERE received_at >= ? ORDER BY received_at",
        conn,
        params=(cutoff,),
        parse_dates=["received_at"],
    )
    conn.close()
    if not df.empty:
        df["received_at"] = df["received_at"].dt.tz_convert("America/Chicago")
        df = df.set_index("received_at")
    return df


@st.cache_data(ttl=REFRESH_SECONDS)
def load_total_count() -> int:
    """Total readings ever stored."""
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    conn.close()
    return count


# ----- Header -----
st.title("🌡️ Closet Monitor")
st.caption(
    "Live environmental telemetry from the network closet • "
    f"auto-refreshes every {REFRESH_SECONDS}s"
)

# ----- Load data -----
df = load_data(hours=24)
total_readings = load_total_count()

if df.empty:
    st.error("No data in the last 24 hours. Is the subscriber running?")
    st.stop()

latest = df.iloc[-1]
last_seen = df.index[-1]
seconds_ago = (datetime.now(timezone.utc).astimezone(last_seen.tz) - last_seen).total_seconds()

# ----- Status banner -----
if seconds_ago < 90:
    st.success(f"✅ Online — last reading {int(seconds_ago)}s ago")
else:
    st.warning(f"⚠️ Last reading was {int(seconds_ago)}s ago — sensor may be offline")

# ----- Current readings (big numbers) -----
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Temperature",
        f"{latest['temp_f']:.1f}°F",
        delta=f"{latest['temp_f'] - df['temp_f'].iloc[-2]:.2f}°F",
        help=f"{latest['temp_c']:.2f}°C",
    )

with col2:
    st.metric(
        "Humidity",
        f"{latest['humidity']:.1f}%",
        delta=f"{latest['humidity'] - df['humidity'].iloc[-2]:.2f}%",
    )

with col3:
    st.metric(
        "Pressure",
        f"{latest['pressure_hpa']:.1f} hPa",
        delta=f"{latest['pressure_hpa'] - df['pressure_hpa'].iloc[-2]:.2f} hPa",
    )

with col4:
    st.metric(
        "WiFi Signal",
        f"{int(latest['rssi'])} dBm",
        help="-60 or higher = excellent, -70 or lower = degraded",
    )

# ----- 24-hour summary stats -----
st.divider()
st.subheader("Last 24 hours at a glance")

stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

with stat_col1:
    st.metric("Readings", f"{len(df):,}", help=f"{total_readings:,} total ever stored")

with stat_col2:
    st.metric(
        "Temp range",
        f"{df['temp_f'].min():.1f}° → {df['temp_f'].max():.1f}°F",
        delta=f"swing of {df['temp_f'].max() - df['temp_f'].min():.1f}°F",
        delta_color="off",
    )

with stat_col3:
    st.metric(
        "Humidity range",
        f"{df['humidity'].min():.1f}% → {df['humidity'].max():.1f}%",
        delta=f"swing of {df['humidity'].max() - df['humidity'].min():.1f}%",
        delta_color="off",
    )

with stat_col4:
    avg_rssi = df["rssi"].mean()
    st.metric("Avg WiFi", f"{int(avg_rssi)} dBm")

# ----- Combined temperature + humidity chart -----
st.divider()
st.subheader("Temperature & Humidity — Last 24 Hours")

fig = make_subplots(specs=[[{"secondary_y": True}]])

fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["temp_f"],
        name="Temperature (°F)",
        line=dict(color="#d62728", width=2),
        hovertemplate="<b>%{y:.2f}°F</b><br>%{x|%H:%M:%S}<extra></extra>",
    ),
    secondary_y=False,
)

fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["humidity"],
        name="Humidity (%)",
        line=dict(color="#1f77b4", width=2),
        hovertemplate="<b>%{y:.2f}%</b><br>%{x|%H:%M:%S}<extra></extra>",
    ),
    secondary_y=True,
)

fig.update_xaxes(title_text="")
fig.update_yaxes(title_text="Temperature (°F)", secondary_y=False, color="#d62728")
fig.update_yaxes(title_text="Humidity (%)", secondary_y=True, color="#1f77b4")
fig.update_layout(
    height=450,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=10, b=10),
)

st.plotly_chart(fig, use_container_width=True)

# ----- Pressure & WiFi (smaller, side by side) -----
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Atmospheric Pressure")
    pfig = go.Figure()
    pfig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["pressure_hpa"],
            line=dict(color="#9467bd", width=2),
            hovertemplate="<b>%{y:.2f} hPa</b><br>%{x|%H:%M:%S}<extra></extra>",
        )
    )
    pfig.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="hPa",
        showlegend=False,
    )
    st.plotly_chart(pfig, use_container_width=True)

with chart_col2:
    st.subheader("WiFi Signal Strength")
    wfig = go.Figure()
    wfig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["rssi"],
            line=dict(color="#2ca02c", width=2),
            hovertemplate="<b>%{y} dBm</b><br>%{x|%H:%M:%S}<extra></extra>",
        )
    )
    wfig.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="dBm",
        showlegend=False,
    )
    st.plotly_chart(wfig, use_container_width=True)

# ----- Footer -----
st.divider()
st.caption(
    f"Database: `{DB_PATH}` • "
    f"Newest reading: {last_seen.strftime('%Y-%m-%d %H:%M:%S %Z')} • "
    f"Project: [closet-monitor on GitHub](https://github.com/design1-software/closet-monitor)"
)

# ----- Auto-refresh -----
# Streamlit re-runs the whole script on a timer when this is set
st.markdown(
    f"""
    <meta http-equiv="refresh" content="{REFRESH_SECONDS}">
    """,
    unsafe_allow_html=True,
)
