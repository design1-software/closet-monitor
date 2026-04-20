"""
Closet Monitor — Alert Listener

Subscribes to MQTT alert topics and sensor status.
Logs all events to SQLite and delivers macOS desktop
notifications for conditions that require human action.

Each alert includes:
  1. What happened
  2. Why it matters
  3. What to do about it

Run:  python alert_listener.py
Stop: Ctrl+C
"""

import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# ----- Setup -----
load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DB_PATH = Path(os.getenv("DB_PATH", "../data/closet.db")).resolve()
ALERT_LOG = Path(os.getenv("ALERT_LOG", "../data/alerts.log")).resolve()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("closet-alerts")

# Track offline duration
last_online_time = None
offline_since = None

# ----- Action runbooks (what to do for each alert) -----
RUNBOOKS = {
    "temp_high": {
        "title": "🔴 Closet Temperature High",
        "message": "Temperature has exceeded 82°F.\n\nAction: Check if AC is running. If yes, check for airflow blockage near the server. If no, check thermostat settings.",
    },
    "temp_low": {
        "title": "🔵 Closet Temperature Low",
        "message": "Temperature has dropped below 60°F.\n\nAction: Check if heating is running. Possible HVAC failure or thermostat issue.",
    },
    "humidity_high": {
        "title": "🔴 Closet Humidity High",
        "message": "Humidity has exceeded 65%. Risk of condensation and corrosion on electronics.\n\nAction: Check for water intrusion, AC drain issues, or unusual moisture source. Inspect server and network equipment for visible condensation.",
    },
    "humidity_low": {
        "title": "⚡ Closet Humidity Low",
        "message": "Humidity has dropped below 25%. Risk of static discharge damaging electronics.\n\nAction: Consider a small humidifier near the closet. Avoid touching server components without grounding yourself.",
    },
    "sensor_offline": {
        "title": "⚠️ Closet Sensor Offline",
        "message": "No data received for 5+ minutes.\n\nAction: Check USB power to the ESP32. Check WiFi connectivity. Press the EN (reset) button on the ESP32 if power is confirmed.",
    },
    "sensor_online": {
        "title": "✅ Closet Sensor Back Online",
        "message": "Sensor has reconnected and is publishing normally.",
    },
}


# ----- macOS Desktop Notification -----
def notify_macos(title: str, message: str, sound: str = "Ping"):
    """Send a native macOS notification banner."""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}" sound name "{sound}"'
        ], check=True, timeout=5)
        log.info(f"Desktop notification sent: {title}")
    except Exception as e:
        log.warning(f"Failed to send desktop notification: {e}")


# ----- Alert Log File -----
def log_to_file(severity: str, event_type: str, details: str):
    """Append a structured line to the alert log file."""
    timestamp = datetime.now(timezone.utc).isoformat()
    line = f"{timestamp} | {severity:8s} | {event_type:20s} | {details}\n"
    with open(ALERT_LOG, "a") as f:
        f.write(line)


# ----- Database -----
def init_db(path: Path) -> sqlite3.Connection:
    """Ensure the alerts table exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            severity    TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            topic       TEXT NOT NULL,
            payload     TEXT NOT NULL,
            action      TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_received_at
        ON alerts(received_at)
    """)
    conn.commit()
    log.info(f"Alert database ready at {path}")
    return conn


def insert_alert(conn, severity, event_type, topic, payload, action=""):
    """Persist an alert to the database."""
    conn.execute("""
        INSERT INTO alerts (received_at, severity, event_type, topic, payload, action)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        severity,
        event_type,
        topic,
        payload,
        action,
    ))
    conn.commit()


# ----- Alert Processing -----
def process_threshold_alert(conn, topic, payload_str):
    """Handle temperature/humidity threshold alerts from the ESP32 firmware."""
    try:
        data = json.loads(payload_str)
    except json.JSONDecodeError:
        log.warning(f"Non-JSON alert payload: {payload_str}")
        return

    is_alert = data.get("alert", False)

    if "temperature" in topic:
        if is_alert:
            temp = data.get("temp_f", "?")
            high = data.get("threshold_high", 82)
            low = data.get("threshold_low", 60)

            if isinstance(temp, (int, float)):
                if temp > high:
                    runbook = RUNBOOKS["temp_high"]
                    severity = "CRITICAL"
                    event_type = "temp_high"
                else:
                    runbook = RUNBOOKS["temp_low"]
                    severity = "WARNING"
                    event_type = "temp_low"
            else:
                runbook = RUNBOOKS["temp_high"]
                severity = "WARNING"
                event_type = "temp_unknown"

            notify_macos(runbook["title"], f"Current: {temp}°F\n{runbook['message']}")
            log_to_file(severity, event_type, f"temp={temp}°F threshold_high={high} threshold_low={low}")
            insert_alert(conn, severity, event_type, topic, payload_str, runbook["message"])
        else:
            log_to_file("RESOLVED", "temp_normal", "Temperature returned to safe range")
            insert_alert(conn, "RESOLVED", "temp_normal", topic, payload_str, "Temperature back in safe range. No action needed.")

    elif "humidity" in topic:
        if is_alert:
            hum = data.get("humidity", "?")
            high = data.get("threshold_high", 65)
            low = data.get("threshold_low", 25)

            if isinstance(hum, (int, float)):
                if hum > high:
                    runbook = RUNBOOKS["humidity_high"]
                    severity = "CRITICAL"
                    event_type = "humidity_high"
                else:
                    runbook = RUNBOOKS["humidity_low"]
                    severity = "WARNING"
                    event_type = "humidity_low"
            else:
                runbook = RUNBOOKS["humidity_high"]
                severity = "WARNING"
                event_type = "humidity_unknown"

            notify_macos(runbook["title"], f"Current: {hum}%\n{runbook['message']}")
            log_to_file(severity, event_type, f"humidity={hum}% threshold_high={high} threshold_low={low}")
            insert_alert(conn, severity, event_type, topic, payload_str, runbook["message"])
        else:
            log_to_file("RESOLVED", "humidity_normal", "Humidity returned to safe range")
            insert_alert(conn, "RESOLVED", "humidity_normal", topic, payload_str, "Humidity back in safe range. No action needed.")


def process_status(conn, payload_str):
    """Handle online/offline status messages."""
    global last_online_time, offline_since

    now = datetime.now(timezone.utc)

    if payload_str == "online":
        if offline_since:
            offline_duration = (now - offline_since).total_seconds()
            runbook = RUNBOOKS["sensor_online"]
            notify_macos(runbook["title"], f"Was offline for {int(offline_duration)}s.\n{runbook['message']}")
            log_to_file("RESOLVED", "sensor_online", f"Back online after {int(offline_duration)}s")
            insert_alert(conn, "RESOLVED", "sensor_online", "home/closet/status", payload_str,
                         f"Sensor recovered after {int(offline_duration)}s offline")
            offline_since = None
        else:
            log_to_file("INFO", "sensor_online", "Sensor connected")
            insert_alert(conn, "INFO", "sensor_online", "home/closet/status", payload_str, "Initial connection")

        last_online_time = now

    elif payload_str == "offline":
        offline_since = now
        log.warning("Sensor went OFFLINE — LWT received")
        log_to_file("WARNING", "sensor_offline", "LWT received — sensor disconnected")
        insert_alert(conn, "WARNING", "sensor_offline", "home/closet/status", payload_str,
                     RUNBOOKS["sensor_offline"]["message"])

        # Delayed notification — only notify if still offline after 5 minutes
        # (For now, log immediately. The 5-min delay would need async/threading.)
        notify_macos(RUNBOOKS["sensor_offline"]["title"], RUNBOOKS["sensor_offline"]["message"])


# ----- MQTT Callbacks -----
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        log.info(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
        # Subscribe to alert topics and status
        topics = [
            ("home/closet/alerts/#", 1),
            ("home/closet/status", 1),
        ]
        client.subscribe(topics)
        log.info("Subscribed to alert and status topics")
    else:
        log.error(f"MQTT connection failed with code {rc}")


def on_message(client, userdata, msg):
    conn = userdata["conn"]
    topic = msg.topic
    payload = msg.payload.decode("utf-8", errors="replace")

    log.info(f"Received [{topic}]: {payload}")

    if topic == "home/closet/status":
        process_status(conn, payload)
    elif "alerts" in topic:
        process_threshold_alert(conn, topic, payload)


def on_disconnect(client, userdata, *args):
    log.warning("Disconnected from MQTT broker. Auto-reconnect will retry.")


# ----- Main -----
def main():
    conn = init_db(DB_PATH)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        userdata={"conn": conn},
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    def shutdown(signum, frame):
        log.info("Shutdown signal received.")
        client.loop_stop()
        client.disconnect()
        conn.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    log.info(f"Alert listener starting — connecting to {MQTT_HOST}:{MQTT_PORT}")
    mqtt_user = os.getenv("MQTT_USER")
    mqtt_pass = os.getenv("MQTT_PASSWORD")
    if mqtt_user:
        client.username_pw_set(mqtt_user, mqtt_pass)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
