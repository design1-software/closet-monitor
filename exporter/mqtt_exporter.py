#!/usr/bin/env python3
"""
closet-exporter — bridges the closet-monitor MQTT feed into Prometheus.

Subscribes to home/closet/environment on the Pi's Mosquitto broker and exposes
the latest reading as Prometheus gauges on :9110/metrics. Lets the environmental
data (Tier 1) show in Grafana alongside the infrastructure metrics — without
touching the closet-monitor's own Streamlit dashboard.
"""
import json
import os
import time
import paho.mqtt.client as mqtt
from prometheus_client import start_http_server, Gauge

HOST        = os.getenv("MQTT_HOST", "192.168.10.16")
PORT        = int(os.getenv("MQTT_PORT", "1883"))
USER        = os.getenv("MQTT_USER", "")
PASSWORD    = os.getenv("MQTT_PASSWORD", "")
TOPIC       = os.getenv("MQTT_TOPIC", "home/closet/environment")
HTTP_PORT   = int(os.getenv("EXPORTER_PORT", "9110"))

G = {
    "temp_f":       Gauge("closet_temperature_fahrenheit", "Closet temperature (F)"),
    "temp_c":       Gauge("closet_temperature_celsius", "Closet temperature (C)"),
    "humidity":     Gauge("closet_humidity_percent", "Closet relative humidity (%)"),
    "pressure_hpa": Gauge("closet_pressure_hpa", "Closet barometric pressure (hPa)"),
    "rssi":         Gauge("closet_sensor_rssi_dbm", "Sensor Wi-Fi RSSI (dBm)"),
    "uptime_s":     Gauge("closet_sensor_uptime_seconds", "Sensor uptime (s)"),
}
G_LAST = Gauge("closet_last_reading_timestamp_seconds", "Unix time of the last reading received")


def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[closet-exporter] connected rc={rc}, subscribing {TOPIC}", flush=True)
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception as e:
        print(f"[closet-exporter] bad payload: {e}", flush=True)
        return
    for key, gauge in G.items():
        v = data.get(key)
        if v is not None:
            try:
                gauge.set(float(v))
            except (TypeError, ValueError):
                pass
    G_LAST.set(time.time())


def main():
    start_http_server(HTTP_PORT)
    print(f"[closet-exporter] /metrics on :{HTTP_PORT}", flush=True)
    # paho-mqtt 2.x requires an explicit callback API version
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if USER:
        client.username_pw_set(USER, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    while True:
        try:
            client.connect(HOST, PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            print(f"[closet-exporter] connection error: {e}; retrying in 10s", flush=True)
            time.sleep(10)


if __name__ == "__main__":
    main()
