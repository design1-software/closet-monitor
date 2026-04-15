# Closet Monitor

An end-to-end IoT data pipeline for monitoring my home lab network closet. An ESP32 microcontroller reads environmental conditions, publishes them over WiFi to an MQTT broker, and a Python service persists them to a local database for analysis, dashboarding, and AI-assisted insights.

## Why

My home server — which runs a production MCP (Model Context Protocol) server and a Meta Engagement automation pipeline — lives in a network closet without active cooling or monitoring. A laptop running 24/7 in an enclosed space needs observability. This project adds eyes and ears to that closet, then turns the resulting telemetry into something I can actually learn from.

## Architecture

```
┌─────────────────┐
│  ESP32 + BME280 │  Edge device — embedded C++
└────────┬────────┘
         │ WiFi · MQTT
         ▼
┌─────────────────┐
│ Mosquitto Broker│  Message broker
└────────┬────────┘
         │ subscribe
         ▼
┌──────────────────┐
│ Python Subscriber│  paho-mqtt → SQLite
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  SQLite Database │  Time-series persistence
└────────┬─────────┘
         │
   ┌─────┴─────┬──────────────┬──────────────┐
   ▼           ▼              ▼              ▼
Jupyter    Streamlit      MCP tool      AI insights
analysis   dashboard      (planned)     (planned)
```

## Hardware

- **ESP32-WROOM-32** (Teyleten 38-pin, USB-C) — dual-core 240 MHz microcontroller with WiFi + Bluetooth
- **BME280 sensor** (SHILLEHTEK pre-soldered, 3.3V, I²C at 0x76) — temperature, humidity, pressure
- **4 female-to-female Dupont jumper wires** — direct ESP32-to-sensor connection (no breadboard)

### Wiring

| BME280 Pin | ESP32 Pin |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SCL | GPIO 22 |
| SDA | GPIO 21 |

## Software stack

- **Firmware:** Arduino C++ using PubSubClient (MQTT) and Adafruit BME280 libraries
- **Broker:** Eclipse Mosquitto 2.x
- **Subscriber:** Python 3 with paho-mqtt and python-dotenv
- **Database:** SQLite 3
- **Toolchain:** `arduino-cli` for firmware, virtualenv for Python dependencies

## MQTT topics

| Topic | Payload | Frequency |
|---|---|---|
| `home/closet/status` | `online` / `offline` (retained, LWT) | On connect/disconnect |
| `home/closet/environment` | JSON (temp, humidity, pressure, RSSI, uptime) | Every 30s |
| `home/closet/alerts/temperature` | JSON alert state (retained, edge-triggered) | On threshold cross |
| `home/closet/alerts/humidity` | JSON alert state (retained, edge-triggered) | On threshold cross |

### Example payload

```json
{
  "temp_f": 76.71,
  "temp_c": 24.84,
  "humidity": 41.44,
  "pressure_hpa": 1009.71,
  "rssi": -72,
  "uptime_s": 60
}
```

## Database schema

```sql
CREATE TABLE readings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at     TEXT NOT NULL,         -- ISO 8601, server-side timestamp
    device_uptime_s INTEGER,
    temp_f          REAL,
    temp_c          REAL,
    humidity        REAL,
    pressure_hpa    REAL,
    rssi            INTEGER
);

CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    topic       TEXT NOT NULL,             -- status, alerts/*, etc.
    payload     TEXT NOT NULL
);
```

## Setup

### Firmware

1. Copy `config.example.h` to `config.h` and fill in WiFi credentials and MQTT broker IP
2. Install toolchain:
   ```bash
   brew install arduino-cli mosquitto
   arduino-cli core install esp32:esp32
   arduino-cli lib install "PubSubClient" "Adafruit BME280 Library" "Adafruit Unified Sensor"
   ```
3. Compile and upload (hold BOOT button on ESP32 during upload):
   ```bash
   arduino-cli compile --fqbn esp32:esp32:esp32 .
   arduino-cli upload -p /dev/cu.usbserial-0001 --fqbn esp32:esp32:esp32 .
   ```

### Subscriber

```bash
cd subscriber
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # edit with your broker IP
python subscriber.py
```

### Verify the pipeline

In a separate terminal:
```bash
mosquitto_sub -h <broker-ip> -t "home/closet/#" -v       # see live MQTT traffic
sqlite3 data/closet.db "SELECT COUNT(*) FROM readings;"  # confirm rows accumulating
```

## Design decisions

- **JSON payloads** over binary — slightly more bandwidth, massively easier to debug with `mosquitto_sub -v` and to consume from any language.
- **Edge-triggered alerts** — alert topics only publish when state changes, avoiding alert spam while still capturing every transition. Retained flag ensures late subscribers see current state.
- **Last Will & Testament** — broker auto-publishes `offline` to `home/closet/status` if the ESP32 disconnects uncleanly.
- **Non-blocking main loop** — uses `millis()` timing instead of `delay()` so the MQTT client can service keepalives and reconnections between sensor reads.
- **Separation of concerns** — credentials live in `config.h` (firmware) and `.env` (subscriber), both gitignored. Example templates are committed.
- **Server-side timestamps** — the subscriber records `received_at` independently of the device's `uptime_s`, so reading order is preserved even if the device reboots.

## Repository layout

```
closet-monitor/
├── closet-monitor.ino          # ESP32 firmware (compiled with arduino-cli)
├── config.example.h            # Firmware config template
├── data/
│   └── sample-overnight-*.log  # Sample dataset for reference
├── subscriber/
│   ├── subscriber.py           # Python MQTT → SQLite service
│   ├── requirements.txt        # Python dependencies
│   └── .env.example            # Subscriber config template
└── README.md
```

## Roadmap

- [x] ESP32 firmware with WiFi + MQTT + BME280
- [x] Threshold-based alerting (edge-triggered)
- [x] Python subscriber with SQLite persistence
- [x] Sample overnight dataset (~955 readings, 8 hours continuous)
- [ ] Jupyter notebook: exploratory data analysis (HVAC cycle detection, trend analysis, anomalies)
- [ ] Streamlit dashboard for live + historical visualization
- [ ] Statistical anomaly detection
- [ ] AI-generated daily summary reports
- [ ] MCP integration so Claude can query closet status conversationally
- [ ] Migration from Mac dev broker to Acer production broker
- [ ] Additional sensors (PIR motion, door reed switch, current sensor)

## Author

Julius Moore — part of a broader home lab build, developed alongside coursework for B.S. Software Engineering at WGU.
