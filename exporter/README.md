# closet-exporter — MQTT → Prometheus bridge

Exposes the closet-monitor sensor feed as Prometheus metrics so the
environmental data can appear in Grafana **alongside** infrastructure metrics —
without replacing the Streamlit dashboard, which remains the primary UI.

It subscribes to `home/closet/environment` on the same Mosquitto broker the
subscriber uses, and serves gauges on `:9110/metrics`:

| Metric | Source field |
|---|---|
| `closet_temperature_fahrenheit` | `temp_f` |
| `closet_temperature_celsius` | `temp_c` |
| `closet_humidity_percent` | `humidity` |
| `closet_pressure_hpa` | `pressure_hpa` |
| `closet_sensor_rssi_dbm` | `rssi` |
| `closet_sensor_uptime_seconds` | `uptime_s` |
| `closet_last_reading_timestamp_seconds` | (time message received) |

## Configuration (env vars)

| Var | Default |
|---|---|
| `MQTT_HOST` | `192.168.10.16` |
| `MQTT_PORT` | `1883` |
| `MQTT_USER` | (empty) |
| `MQTT_PASSWORD` | (empty) — keep in a gitignored `.env`, never commit |
| `MQTT_TOPIC` | `home/closet/environment` |
| `EXPORTER_PORT` | `9110` |

## Run (Docker)

```yaml
services:
  closet-exporter:
    build: ./exporter
    restart: unless-stopped
    environment:
      - MQTT_HOST=192.168.10.16
      - MQTT_USER=closet-subscriber
      - MQTT_PASSWORD=${MQTT_PASSWORD}   # from a gitignored .env
      - MQTT_TOPIC=home/closet/environment
    ports:
      - "9110:9110"
```

## Run (standalone)

```bash
pip install "paho-mqtt>=2.0" prometheus_client
MQTT_USER=closet-subscriber MQTT_PASSWORD=... python exporter/mqtt_exporter.py
```

## Prometheus scrape

```yaml
scrape_configs:
  - job_name: closet
    static_configs:
      - targets: ['closet-exporter:9110']
```

Then add a Grafana time-series/stat dashboard on `closet_temperature_fahrenheit`,
`closet_humidity_percent`, `closet_pressure_hpa`, `closet_sensor_rssi_dbm`.
