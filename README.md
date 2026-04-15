# Closet Monitor

An end-to-end IoT data pipeline for monitoring my home lab network closet — and the first node in a broader smart-home observability platform built around Home Assistant.

## The story behind this project

This project started as a single-evening exercise: wire up a microcontroller to a temperature sensor and prove I could do basic embedded work. By the time I had the firmware working and overnight data flowing, I realized the *interesting* problem wasn't the sensor — it was what to do with the telemetry it produced.

So I pivoted.

What was a one-night embedded project became a multi-stage pipeline spanning **embedded systems → networking → backend services → data persistence → exploratory analysis → dashboarding → AI insights**. Every layer is a deliberate learning surface. The goal isn't just to monitor my closet — it's to walk a complete data lifecycle with one cohesive dataset I actually understand and care about, then use it as the proving ground for a larger smart-home platform.

The closet is real. My home server lives there, running a production MCP (Model Context Protocol) server and a Meta Engagement automation pipeline. A laptop running 24/7 in an enclosed space deserves observability, and now it has it.

## Where this is headed

This repo is the foundation for a larger **smart home + home lab observability platform**:

- **Home Assistant on a Raspberry Pi 5** as the central hub, ingesting data from this sensor and other smart devices
- **Ecobee thermostat integration** via Home Assistant, with cross-correlation analysis between the wall thermostat readings and what's actually happening in the closet
- **Three wall-mounted 10-inch tablets** as monitoring and control panels around the house, running Home Assistant's Lovelace UI
- **Multiple sensor projects** feeding into the same data fabric over time

The closet monitor proves out the pipeline pattern. Future sensor projects (door reed switches, motion sensors, current monitors) will reuse this MQTT → broker → database → dashboard architecture.

## Architecture (current)

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
   ┌─────┴─────┬──────────────┐
   ▼           ▼              ▼
Jupyter    Streamlit      MCP tool
analysis   dashboard      (planned)
```

## Architecture (target)

```
┌─────────────────┐    ┌─────────────────┐
│  ESP32 + BME280 │    │ Ecobee Thermostat│
│ (closet sensor) │    │  (whole house)   │
└────────┬────────┘    └────────┬─────────┘
         │ MQTT                  │ Cloud API
         ▼                       ▼
┌─────────────────────────────────────────┐
│  Home Assistant on Raspberry Pi 5       │
│  + Mosquitto broker (production)        │
│  + SQLite/Postgres for long-term data   │
└────────┬────────────────────────────────┘
         │
   ┌─────┴──────┬──────────────┬──────────────┐
   ▼            ▼              ▼              ▼
Tablet UIs   Lovelace      Cross-source   AI insights
(3 around    dashboards    analytics      (anomaly
 the house)                (HA + closet)  detection)
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
- **Analysis:** Python with pandas, matplotlib, seaborn, scipy (Jupyter notebooks)
- **Toolchain:** `arduino-cli` for firmware, virtualenv for Python dependencies

## MQTT topics

| Topic | Payload | Frequency |
|---|---|---|
| `home/closet/status` | `online` / `offline` (retained, LWT) | On connect/disconnect |
| `home/closet/environment` | JSON (temp, humidity, pressure, RSSI, uptime) | Every 30s |
| `home/closet/alerts/temperature` | JSON alert state (retained, edge-triggered) | On threshold cross |
| `home/closet/alerts/humidity` | JSON alert state (retained, edge-triggered) | On threshold cross |

The `home/` prefix and standard payload format are intentionally Home Assistant-friendly. When the platform comes online, HA will subscribe to these topics with no firmware changes required.

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

## Findings so far

After ~16 hours of continuous operation:

- **1,917 readings collected** with **zero packet loss** (intervals ranged 27.5 - 32.5s, target 30s)
- Temperature held within a tight 5.4°F band (71.8 → 77.2°F) with std dev of just 0.91°F
- Humidity averaged 46.9% with one detected micro-event (4.4-point spike in 30 seconds, recovery within 90s)
- WiFi signal strength steady at -67 dBm average
- **15 HVAC cycles automatically detected** using rolling-mean smoothing + scipy peak detection
- Cycle lengths split into two regimes: **short cycles (16-50 min) during evening peak hours**, **long cycles (100+ min) overnight** — consistent with healthy outside-temperature-driven HVAC behavior
- Average temperature swing per cycle: 1.29°F (tight thermostat control)

The cycle-length pattern is the most actionable insight: the closet's environment is being driven by the rest of the house's thermal load, not just its own internal heat sources. Cross-referencing this with ecobee schedule data (next phase) should let me quantify the thermal lag between the wall thermostat and the closet itself.

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

- **JSON payloads** over binary — slightly more bandwidth, massively easier to debug with `mosquitto_sub -v` and to consume from any language. Also Home Assistant-friendly out of the box.
- **Edge-triggered alerts** — alert topics only publish when state changes, avoiding alert spam while still capturing every transition. Retained flag ensures late subscribers see current state.
- **Last Will & Testament** — broker auto-publishes `offline` to `home/closet/status` if the ESP32 disconnects uncleanly.
- **Non-blocking main loop** — uses `millis()` timing instead of `delay()` so the MQTT client can service keepalives and reconnections between sensor reads.
- **Separation of concerns** — credentials live in `config.h` (firmware) and `.env` (subscriber), both gitignored. Example templates are committed.
- **Server-side timestamps** — the subscriber records `received_at` independently of the device's `uptime_s`, so reading order is preserved even if the device reboots.
- **SQLite over Postgres for the first iteration** — single-file database, zero ops overhead, sufficient throughput for 30s sampling. Migration to Postgres or DuckDB happens when data volumes or query patterns demand it.
- **MQTT topic naming follows the Home Assistant convention** — `home/<location>/<metric>` — so the eventual HA migration is configuration-only, no firmware changes.

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
│   └── 01-exploratory-analysis.ipynb  # Jupyter notebook
└── README.md
```

## Roadmap

### Done
- [x] ESP32 firmware with WiFi + MQTT + BME280
- [x] Threshold-based alerting (edge-triggered)
- [x] Python subscriber with SQLite persistence
- [x] Sample overnight dataset (~955 readings, 8 hours continuous)
- [x] Exploratory analysis: descriptive stats, time-series plots, correlation
- [x] HVAC cycle detection with scipy peak detection
- [x] Cycle length analysis and time-of-day pattern identification
- [x] Detected first real-world micro-event (05:38 AM humidity spike)

### Next
- [ ] Streamlit dashboard for live + historical visualization (portable demo artifact)
- [ ] Statistical anomaly detection (rolling-window z-score)
- [ ] Ecobee API integration: pull thermostat data into the same database
- [ ] Cross-correlation analysis: closet temp vs. thermostat schedule and reported temp
- [ ] AI-generated daily summary reports

### Platform
- [ ] Migrate broker to Raspberry Pi 5 + install Home Assistant
- [ ] Connect Home Assistant to existing MQTT topics (zero firmware changes)
- [ ] Add ecobee integration through HA
- [ ] Build Lovelace dashboard combining closet sensor + ecobee data
- [ ] Deploy 3 wall-mounted tablets running HA's tablet UI
- [ ] MCP integration so Claude can query the unified data through HA

### Future sensors
- [ ] PIR motion sensor in the closet
- [ ] Door reed switch on the closet door
- [ ] Current sensor on the home server's power cable
- [ ] Additional environmental nodes in other parts of the house

## Why this lives in one repo

The temptation with a project like this is to split it into multiple repos — one for firmware, one for the subscriber service, one for analysis. I'm deliberately keeping them together because the *story* of this project is the integration. Anyone reading this repo can follow a single physical signal — temperature in a closet — through every stage of an end-to-end data system. That narrative is more valuable to me right now than the modularity. When a piece outgrows this layout (likely the dashboard, possibly the Home Assistant integration), it'll move to its own repo with proper boundaries.

## Author

Julius Moore — part of a broader home lab build, developed alongside coursework for B.S. Software Engineering at WGU.
