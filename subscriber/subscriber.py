"""
Closet Monitor — MQTT to SQLite subscriber.

Listens on the home/closet/# topic tree, parses incoming JSON readings
from the ESP32, and persists them to a local SQLite database for later
analysis and dashboarding.

Run: python subscriber.py
Stop: Ctrl+C (graceful shutdown — final reading is committed)
"""

import json
import logging
import os
import signal
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# ----- Setup -----
load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "home/closet/#")
DB_PATH = Path(os.getenv("DB_PATH", "../data/closet.db")).resolve()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("closet-subscriber")


# ----- Database -----
def init_db(path: Path) -> sqlite3.Connection:
    """Create the database and tables if they don't exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at     TEXT NOT NULL,
            device_uptime_s INTEGER,
            temp_f          REAL,
            temp_c          REAL,
            humidity        REAL,
            pressure_hpa    REAL,
            rssi            INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            topic       TEXT NOT NULL,
            payload     TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_readings_received_at
        ON readings(received_at)
    """)
    conn.commit()
    log.info(f"Database ready at {path}")
    return conn


def insert_reading(conn: sqlite3.Connection, payload: dict) -> None:
    """Persist a single environment reading."""
    conn.execute("""
        INSERT INTO readings
            (received_at, device_uptime_s, temp_f, temp_c, humidity, pressure_hpa, rssi)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        payload.get("uptime_s"),
        payload.get("temp_f"),
        payload.get("temp_c"),
        payload.get("humidity"),
        payload.get("pressure_hpa"),
        payload.get("rssi"),
    ))
    conn.commit()


def insert_event(conn: sqlite3.Connection, topic: str, payload: str) -> None:
    """Persist a status or alert event."""
    conn.execute("""
        INSERT INTO events (received_at, topic, payload)
        VALUES (?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        topic,
        payload,
    ))
    conn.commit()


# ----- MQTT callbacks -----
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        log.info(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        log.info(f"Subscribed to {MQTT_TOPIC}")
    else:
        log.error(f"MQTT connection failed with code {rc}")


def on_message(client, userdata, msg):
    conn: sqlite3.Connection = userdata["conn"]
    topic = msg.topic
    raw = msg.payload.decode("utf-8", errors="replace")

    try:
        if topic == "home/closet/environment":
            payload = json.loads(raw)
            insert_reading(conn, payload)
            log.info(
                f"Stored reading: "
                f"{payload.get('temp_f')}°F  "
                f"{payload.get('humidity')}%  "
                f"{payload.get('pressure_hpa')} hPa"
            )
        else:
            insert_event(conn, topic, raw)
            log.info(f"Stored event [{topic}]: {raw}")
    except json.JSONDecodeError:
        log.warning(f"Non-JSON payload on {topic}: {raw}")
        insert_event(conn, topic, raw)
    except Exception as e:
        log.exception(f"Error processing message on {topic}: {e}")


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

    # Graceful shutdown on Ctrl+C
    def shutdown(signum, frame):
        log.info("Shutdown signal received. Disconnecting cleanly...")
        client.loop_stop()
        client.disconnect()
        conn.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    log.info(f"Connecting to {MQTT_HOST}:{MQTT_PORT}...")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
