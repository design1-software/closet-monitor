Here's the README — copy and paste this entire block into ~/Documents/closet-monitor/README.md:
markdown# Closet Monitor

An ESP32-based environmental monitoring system for a home lab network closet. Publishes real-time temperature, humidity, and atmospheric pressure readings to an MQTT broker, enabling alerting and historical tracking for the infrastructure running my self-hosted services.

## Why

My home server — which runs a production MCP (Model Context Protocol) server and a Meta Engagement automation pipeline — lives in a network closet without active cooling or monitoring. A laptop running 24/7 in an enclosed space needs observability. This project adds eyes and ears to that closet.

## Architecture
ESP32 + BME280 ──WiFi──> Mosquitto MQTT Broker ──> Subscribers
(closet)             (Mac for dev,              (logs, alerts,
Acer for prod)             MCP integration)

## Hardware

- **ESP32-WROOM-32** (Teyleten 38-pin, USB-C) — dual-core 240 MHz microcontroller with WiFi + Bluetooth
- **BME280 sensor** (SHILLEHTEK pre-soldered, 3.3V, I²C at address 0x76) — temperature, humidity, pressure
- **4 female-to-female Dupont jumper wires** — direct ESP32-to-sensor connection (no breadboard)

### Wiring

| BME280 Pin | ESP32 Pin |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SCL | GPIO 22 |
| SDA | GPIO 21 |

## Software

- **Firmware:** Arduino C++ using PubSubClient (MQTT) and Adafruit BME280 libraries
- **Broker:** Eclipse Mosquitto 2.x
- **Toolchain:** `arduino-cli` (compile, upload, serial monitor) — no IDE required

## MQTT Topics

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

## Setup

1. Copy `config.example.h` to `config.h`
2. Fill in your WiFi credentials and MQTT broker IP in `config.h`
3. Install toolchain:
```bash
   brew install arduino-cli mosquitto
   arduino-cli core install esp32:esp32
   arduino-cli lib install "PubSubClient" "Adafruit BME280 Library" "Adafruit Unified Sensor"
```
4. Compile and upload (hold BOOT button on ESP32 during upload):
```bash
   arduino-cli compile --fqbn esp32:esp32:esp32 .
   arduino-cli upload -p /dev/cu.usbserial-0001 --fqbn esp32:esp32:esp32 .
```
5. Subscribe to verify:
```bash
   mosquitto_sub -h <broker-ip> -t "home/closet/#" -v
```

## Design decisions

- **JSON payloads** over binary — slightly more bandwidth, massively easier to debug with `mosquitto_sub -v` and to consume from any language.
- **Edge-triggered alerts** — alert topics only publish when state changes (normal → alert or alert → normal), avoiding alert spam while still capturing every transition. Retained flag ensures late subscribers see current state.
- **Last Will & Testament** — broker automatically publishes `offline` to `home/closet/status` if the ESP32 loses connection uncleanly, so subscribers know when the sensor is actually down.
- **Non-blocking main loop** — uses `millis()` timing instead of `delay()` so the MQTT client can service keepalives and reconnections between sensor reads.
- **Config separated from code** — credentials live in `config.h` which is gitignored; `config.example.h` documents what's needed without exposing secrets.

## Roadmap

- [x] ESP32 firmware with WiFi + MQTT + BME280
- [x] Threshold-based alerting (edge-triggered)
- [ ] Node.js subscriber with SQLite persistence
- [ ] Integration with home MCP server (queryable via Claude)
- [ ] Migration from Mac dev broker to Acer production broker
- [ ] Grafana dashboard for historical trends
- [ ] Additional sensors (PIR motion, door reed switch, current sensor)

## Author

Julius Moore — part of a broader home lab build documented as coursework for B.S. Software Engineering at WGU.