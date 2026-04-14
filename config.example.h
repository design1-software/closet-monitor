cat > config.example.h << 'EOF'
#ifndef CONFIG_H
#define CONFIG_H

// Copy this file to config.h and fill in your values.
// config.h is gitignored — never commit real credentials.

#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"

#define MQTT_HOST       "192.168.1.XXX"
#define MQTT_PORT       1883
#define MQTT_CLIENT_ID  "closet-monitor-01"

#define PUBLISH_INTERVAL_MS  30000

#define TEMP_HIGH_F          85.0
#define TEMP_LOW_F           50.0
#define HUMIDITY_HIGH_PCT    60.0
#define HUMIDITY_LOW_PCT     25.0

#endif
EOF