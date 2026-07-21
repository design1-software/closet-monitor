FROM python:3.12-slim
RUN pip install --no-cache-dir "paho-mqtt>=2.0,<3.0" "prometheus_client>=0.20,<1.0"
COPY mqtt_exporter.py /app/mqtt_exporter.py
WORKDIR /app
CMD ["python", "mqtt_exporter.py"]
