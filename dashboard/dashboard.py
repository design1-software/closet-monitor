"""
Closet Monitor — Operations Dashboard

A business-question-oriented dashboard for monitoring the network closet.
Every section answers a specific question a stakeholder would ask.

Questions answered:
  1. "Should I worry right now?"         → Status assessment
  2. "What are the current conditions?"   → Live metrics
  3. "What's the trend?"                  → 24-hour charts
  4. "Has anything happened recently?"    → Alert/incident log
  5. "Is the system itself healthy?"      → Sensor + WiFi health

Run: streamlit run dashboard.py
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
REFRESH_SECONDS = 30

# Thresholds (must match firmware config)
TEMP_HIGH = 82.0
TEMP_LOW = 60.0
HUMIDITY_HIGH = 65.0
HUMIDITY_LOW = 25.0

# ----- Page setup -----
st.set_page_config(
    page_title="Closet Monitor",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----- Data loading -----
@st.cache_data(ttl=REFRESH_SECONDS)
def load_readings(hours: int = 24) -> pd.DataFrame:
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
def load_alerts(limit: int = 20) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            "SELECT received_at, severity, event_type, action FROM alerts ORDER BY id DESC LIMIT ?",
            conn,
            params=(limit,),
            parse_dates=["received_at"],
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if not df.empty and "received_at" in df.columns:
        df["received_at"] = df["received_at"].dt.tz_convert("America/Chicago")
        df["received_at"] = df["received_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


@st.cache_data(ttl=REFRESH_SECONDS)
def load_total_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    conn.close()
    return count


# ----- Load data -----
df = load_readings(hours=24)
alerts_df = load_alerts(limit=20)
total_readings = load_total_count()

# ================================================================
# SECTION 1: "Should I worry right now?"
# ================================================================
st.title("🌡️ Closet Monitor")

if df.empty:
    st.error("No data in the last 24 hours. Is the subscriber running?")
    st.stop()

latest = df.iloc[-1]
last_seen = df.index[-1]
seconds_ago = (datetime.now(timezone.utc).astimezone(last_seen.tz) - last_seen).total_seconds()

# Determine overall status
issues = []

if seconds_ago > 300:
    issues.append(f"Sensor has not reported in {int(seconds_ago)}s — may be offline")
if latest["temp_f"] > TEMP_HIGH:
    issues.append(f"Temperature is {latest['temp_f']:.1f}°F — above {TEMP_HIGH}°F safe limit")
if latest["temp_f"] < TEMP_LOW:
    issues.append(f"Temperature is {latest['temp_f']:.1f}°F — below {TEMP_LOW}°F safe limit")
if latest["humidity"] > HUMIDITY_HIGH:
    issues.append(f"Humidity is {latest['humidity']:.1f}% — above {HUMIDITY_HIGH}% (condensation risk)")
if latest["humidity"] < HUMIDITY_LOW:
    issues.append(f"Humidity is {latest['humidity']:.1f}% — below {HUMIDITY_LOW}% (static risk)")

if not issues:
    st.success(
        f"✅ **Server environment is healthy.** "
        f"Temperature is {latest['temp_f']:.1f}°F and humidity is {latest['humidity']:.1f}% — "
        f"both within safe operating ranges. "
        f"Sensor last reported {int(seconds_ago)}s ago."
    )
else:
    for issue in issues:
        st.error(f"🚨 {issue}")

st.caption(
    f"Safe ranges: {TEMP_LOW}–{TEMP_HIGH}°F temperature, "
    f"{HUMIDITY_LOW}–{HUMIDITY_HIGH}% humidity • "
    f"Auto-refreshes every {REFRESH_SECONDS}s"
)

# ================================================================
# SECTION 2: "What are the current conditions?"
# ================================================================
st.divider()
st.subheader("Current Conditions")

col1, col2, col3, col4 = st.columns(4)

with col1:
    temp_delta = latest["temp_f"] - df["temp_f"].iloc[-2] if len(df) > 1 else 0
    st.metric(
        "Temperature",
        f"{latest['temp_f']:.1f}°F",
        delta=f"{temp_delta:+.2f}°F",
        help=f"{latest['temp_c']:.1f}°C • Safe range: {TEMP_LOW}–{TEMP_HIGH}°F",
    )

with col2:
    hum_delta = latest["humidity"] - df["humidity"].iloc[-2] if len(df) > 1 else 0
    st.metric(
        "Humidity",
        f"{latest['humidity']:.1f}%",
        delta=f"{hum_delta:+.2f}%",
        help=f"Safe range: {HUMIDITY_LOW}–{HUMIDITY_HIGH}%",
    )

with col3:
    st.metric(
        "Pressure",
        f"{latest['pressure_hpa']:.1f} hPa",
        help="Atmospheric pressure — useful for weather correlation",
    )

with col4:
    rssi = int(latest["rssi"])
    if rssi > -60:
        signal_label = "Excellent"
    elif rssi > -70:
        signal_label = "Good"
    elif rssi > -80:
        signal_label = "Fair"
    else:
        signal_label = "Poor"
    st.metric(
        "WiFi Signal",
        f"{rssi} dBm",
        help=f"Quality: {signal_label} • Below -80 dBm may cause data loss",
    )

# ================================================================
# SECTION 3: "What's the trend over the last 24 hours?"
# ================================================================
st.divider()
st.subheader("24-Hour Trend — Is the environment stable?")

# Summary stats that answer "is it stable?"
temp_range = df["temp_f"].max() - df["temp_f"].min()
hum_range = df["humidity"].max() - df["humidity"].min()

summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

with summary_col1:
    st.metric("Readings (24h)", f"{len(df):,}", help=f"{total_readings:,} total stored")

with summary_col2:
    stability = "Stable" if temp_range < 8 else ("Moderate" if temp_range < 12 else "Volatile")
    st.metric(
        "Temp Stability",
        stability,
        delta=f"{temp_range:.1f}°F swing",
        delta_color="off",
        help=f"Range: {df['temp_f'].min():.1f}–{df['temp_f'].max():.1f}°F",
    )

with summary_col3:
    hum_stability = "Stable" if hum_range < 15 else ("Moderate" if hum_range < 25 else "Volatile")
    st.metric(
        "Humidity Stability",
        hum_stability,
        delta=f"{hum_range:.1f}% swing",
        delta_color="off",
        help=f"Range: {df['humidity'].min():.1f}–{df['humidity'].max():.1f}%",
    )

with summary_col4:
    avg_rssi = df["rssi"].mean()
    st.metric("Avg WiFi (24h)", f"{int(avg_rssi)} dBm")

# Temperature + Humidity chart
fig = make_subplots(specs=[[{"secondary_y": True}]])

fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["temp_f"],
        name="Temperature (°F)",
        line=dict(color="#d62728", width=2),
        hovertemplate="<b>%{y:.1f}°F</b><br>%{x|%H:%M:%S}<extra></extra>",
    ),
    secondary_y=False,
)

fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["humidity"],
        name="Humidity (%)",
        line=dict(color="#1f77b4", width=2),
        hovertemplate="<b>%{y:.1f}%</b><br>%{x|%H:%M:%S}<extra></extra>",
    ),
    secondary_y=True,
)

# Add threshold reference lines
fig.add_hline(y=TEMP_HIGH, line_dash="dash", line_color="red", opacity=0.3,
              annotation_text=f"Temp alert ({TEMP_HIGH}°F)", secondary_y=False)

fig.update_xaxes(title_text="")
fig.update_yaxes(title_text="Temperature (°F)", secondary_y=False, color="#d62728")
fig.update_yaxes(title_text="Humidity (%)", secondary_y=True, color="#1f77b4")
fig.update_layout(
    height=400,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=10, b=10),
)

st.plotly_chart(fig, use_container_width=True)

# Pressure & WiFi side by side
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Atmospheric Pressure")
    pfig = go.Figure()
    pfig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["pressure_hpa"],
            line=dict(color="#9467bd", width=2),
            hovertemplate="<b>%{y:.1f} hPa</b><br>%{x|%H:%M:%S}<extra></extra>",
        )
    )
    pfig.update_layout(
        height=250,
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
        height=250,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="dBm",
        showlegend=False,
    )
    st.plotly_chart(wfig, use_container_width=True)

# ================================================================
# SECTION 4: "Has anything happened that required attention?"
# ================================================================
st.divider()
st.subheader("Recent Alerts & Events")

if alerts_df.empty:
    st.info("No alerts recorded yet. The system will log events when thresholds are crossed or the sensor goes offline.")
else:
    # Color-code severity
    def severity_badge(severity):
        colors = {
            "CRITICAL": "🔴",
            "WARNING": "🟡",
            "RESOLVED": "🟢",
            "INFO": "ℹ️",
        }
        return f"{colors.get(severity, '⚪')} {severity}"

    display_df = alerts_df.copy()
    display_df["severity"] = display_df["severity"].apply(severity_badge)
    display_df.columns = ["Time", "Severity", "Event", "Recommended Action"]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    # Quick summary
    critical_count = (alerts_df["severity"].str.contains("CRITICAL")).sum()
    warning_count = (alerts_df["severity"].str.contains("WARNING")).sum()
    resolved_count = (alerts_df["severity"].str.contains("RESOLVED")).sum()

    if critical_count > 0:
        st.warning(f"⚠️ {critical_count} critical alert(s) in the log. Review recommended actions above.")
    elif warning_count > 0 and resolved_count >= warning_count:
        st.success("All warnings have been resolved.")
    else:
        st.success("No active issues.")

# ================================================================
# SECTION 5: "Is the monitoring system itself healthy?"
# ================================================================
st.divider()
st.subheader("System Health")

health_col1, health_col2, health_col3, health_col4 = st.columns(4)

with health_col1:
    uptime_hours = latest["device_uptime_s"] / 3600
    st.metric(
        "Sensor Uptime",
        f"{uptime_hours:.1f} hrs",
        help="Time since last ESP32 reboot",
    )

with health_col2:
    if len(df) > 1:
        intervals = df.index.to_series().diff().dt.total_seconds().dropna()
        dropout_count = (intervals > 90).sum()
    else:
        dropout_count = 0
    st.metric(
        "Dropouts (24h)",
        f"{dropout_count}",
        help="Readings with >90s gap (expected: 0)",
    )

with health_col3:
    st.metric(
        "Avg Interval",
        f"{intervals.median():.1f}s" if len(df) > 1 else "N/A",
        help="Target: 30.0s",
    )

with health_col4:
    st.metric(
        "Total Stored",
        f"{total_readings:,}",
        help="All-time readings in the database",
    )

# ----- Footer -----
st.divider()
st.caption(
    f"Closet Monitor v2 • "
    f"Database: `{DB_PATH.name}` • "
    f"Last reading: {last_seen.strftime('%Y-%m-%d %H:%M:%S %Z')} • "
    f"[GitHub](https://github.com/design1-software/closet-monitor)"
)

# ----- Auto-refresh -----
st.markdown(
    f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}">',
    unsafe_allow_html=True,
)