# Closet Monitor

An end-to-end IoT data pipeline for monitoring my home lab network closet. An ESP32 microcontroller reads environmental conditions, publishes them over WiFi to an MQTT broker, and a Python service persists them to a local database for analysis, dashboarding, and AI-assisted insights.

## The story behind this project

This project started as a single-evening exercise: wire up a microcontroller to a temperature sensor and prove I could do basic embedded work. By the time I had the firmware working and overnight data flowing, I realized the *interesting* problem wasn't the sensor — it was what to do with the telemetry it produced.

So I pivoted.

What was a one-night embedded project became a multi-stage pipeline spanning **embedded systems → networking → backend services → data persistence → exploratory analysis → (next) dashboarding and AI insights.** Every layer is a deliberate learning surface. The goal isn't just to monitor my closet — it's to walk a complete data lifecycle with one cohesive dataset I actually understand and care about.

The closet is real. My home server lives there, running a production MCP (Model Context Protocol) server and a Meta Engagement automation pipeline. A laptop running 24/7 in an enclosed space deserves observability, and now it has it.

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
- **Analysis:** Python with pandas, matplotlib, seaborn (Jupyter notebooks)
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
    received_at     TEXT NOT NULL,
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
    topic       TEXT NOT NULL,
    payload     TEXT NOT NULL
);
```

## Early findings

After ~16 hours of continuous operation:

- **1,917 readings collected** with **zero packet loss** (every interval between 27.5s and 32.5s, target was 30s)
- Temperature held within a tight 5.4°F band (71.8 → 77.2°F) with std dev of just 0.91°F — evidence of healthy HVAC behavior
- Humidity averaged 46.9% with occasional brief spikes that don't correlate with temperature changes
- WiFi signal strength held steady at -67 dBm average across the entire run
- **Detected a brief humidity event at 05:38 AM:** humidity jumped 4.4 points in 30 seconds while temperature stayed flat, then recovered within 90 seconds. Signature suggests a brief introduction of moist air (door opening, nearby shower, or air movement) — too fast for HVAC, too localized for weather.

The fact that the sensor caught and recorded a 90-second event without intervention is exactly the value proposition of continuous monitoring versus point-in-time checks.

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
mosquitto_sub -h <broker-ip> -t "home/closet/#" -v
sqlite3 data/closet.db "SELECT COUNT(*) FROM readings;"
```

### Analysis

```bash
cd analysis
jupyter lab
# Open 01-exploratory-analysis.ipynb
```

## Design decisions

- **JSON payloads** over binary — slightly more bandwidth, massively easier to debug with `mosquitto_sub -v` and to consume from any language.
- **Edge-triggered alerts** — alert topics only publish when state changes, avoiding alert spam while still capturing every transition. Retained flag ensures late subscribers see current state.
- **Last Will & Testament** — broker auto-publishes `offline` to `home/closet/status` if the ESP32 disconnects uncleanly.
- **Non-blocking main loop** — uses `millis()` timing instead of `delay()` so the MQTT client can service keepalives and reconnections between sensor reads.
- **Separation of concerns** — credentials live in `config.h` (firmware) and `.env` (subscriber), both gitignored. Example templates are committed.
- **Server-side timestamps** — the subscriber records `received_at` independently of the device's `uptime_s`, so reading order is preserved even if the device reboots.
- **SQLite over Postgres for the first iteration** — single-file database, zero ops overhead, sufficient throughput for 30s sampling. When this moves to the production server with longer retention, migration to Postgres or DuckDB becomes a discrete decision rather than premature optimization.

## Repository layout

```
closet-monitor/
├── closet-monitor.ino                 # ESP32 firmware
├── config.example.h                   # Firmware config template
├── data/
│   ├── sample-overnight-*.log         # Sample dataset for reference
│   └── closet.db                      # Live SQLite database (gitignored)
├── subscriber/
│   ├── subscriber.py                  # Python MQTT → SQLite service
│   ├── requirements.txt               # Python dependencies
│   └── .env.example                   # Subscriber config template
├── analysis/
│   └── 01-exploratory-analysis.ipynb  # Jupyter notebook (in progress)
└── README.md
```

## Roadmap

- [x] ESP32 firmware with WiFi + MQTT + BME280
- [x] Threshold-based alerting (edge-triggered)
- [x] Python subscriber with SQLite persistence
- [x] Sample overnight dataset (~955 readings, 8 hours continuous)
- [x] Initial exploratory analysis: descriptive stats, time-series plots, correlation
- [x] Detected first real-world micro-event (05:38 AM humidity spike)
- [ ] HVAC cycle detection (programmatic identification of cooling cycles)
- [ ] Statistical anomaly detection (rolling-window z-score)
- [ ] Streamlit dashboard for live + historical visualization
- [ ] AI-generated daily summary reports
- [ ] MCP integration so Claude can query closet status conversationally
- [ ] Migration from Mac dev broker to Acer production broker
- [ ] Additional sensors (PIR motion, door reed switch, current sensor)

## Why this lives in one repo

The temptation with a project like this is to split it into multiple repos — one for firmware, one for the subscriber service, one for analysis. I'm deliberately keeping them together because the *story* of this project is the integration. Anyone reading this repo can follow a single physical signal — temperature in a closet — through every stage of an end-to-end data system. That narrative is more valuable to me right now than the modularity. When a piece outgrows this layout (likely the dashboard), it'll move to its own repo with proper boundaries.

## Author

Julius Moore — part of a broader home lab build, developed alongside coursework for B.S. Software Engineering at WGU.
