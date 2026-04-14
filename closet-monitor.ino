/*
 * Closet Environmental Monitor
 * ----------------------------
 * ESP32 + BME280 sensor publishing environmental data to an MQTT broker.
 * Part of a home lab infrastructure monitoring system.
 *
 * Publishes:
 *   home/closet/environment        - Regular readings every PUBLISH_INTERVAL_MS
 *   home/closet/alerts/temperature - When temp crosses configured thresholds
 *   home/closet/alerts/humidity    - When humidity crosses configured thresholds
 *   home/closet/status             - Online/offline status (LWT)
 *
 * Author: Julius Moore
 * Hardware: ESP32-WROOM-32 (Teyleten 38-pin) + BME280 (I2C, 0x76)
 */

 #include <WiFi.h>
 #include <PubSubClient.h>
 #include <Wire.h>
 #include <Adafruit_Sensor.h>
 #include <Adafruit_BME280.h>
 #include "config.h"
 
 // ----- Globals -----
 WiFiClient   espClient;
 PubSubClient mqtt(espClient);
 Adafruit_BME280 bme;
 
 unsigned long lastPublish = 0;
 bool lastTempAlertState = false;
 bool lastHumidityAlertState = false;
 
 // ----- WiFi -----
 void connectWiFi() {
   Serial.printf("Connecting to WiFi: %s ", WIFI_SSID);
   WiFi.mode(WIFI_STA);
   WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
 
   unsigned long start = millis();
   while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
     delay(500);
     Serial.print(".");
   }
 
   if (WiFi.status() == WL_CONNECTED) {
     Serial.printf("\nConnected. IP: %s, RSSI: %d dBm\n",
                   WiFi.localIP().toString().c_str(), WiFi.RSSI());
   } else {
     Serial.println("\nWiFi connection failed. Will retry in main loop.");
   }
 }
 
 // ----- MQTT -----
 void connectMQTT() {
   mqtt.setServer(MQTT_HOST, MQTT_PORT);
 
   while (!mqtt.connected()) {
     Serial.printf("Connecting to MQTT %s:%d ... ", MQTT_HOST, MQTT_PORT);
 
     // Last Will & Testament: broker publishes "offline" if we disconnect uncleanly
     if (mqtt.connect(MQTT_CLIENT_ID,
                      "home/closet/status", 1, true, "offline")) {
       Serial.println("connected.");
       mqtt.publish("home/closet/status", "online", true);
     } else {
       Serial.printf("failed, rc=%d. Retrying in 5s\n", mqtt.state());
       delay(5000);
     }
   }
 }
 
 // ----- Sensor reading + publish -----
 void readAndPublish() {
   float tempC = bme.readTemperature();
   float tempF = tempC * 9.0 / 5.0 + 32.0;
   float humidity = bme.readHumidity();
   float pressure = bme.readPressure() / 100.0;  // hPa
 
   // Build JSON payload
   char payload[200];
   snprintf(payload, sizeof(payload),
            "{\"temp_f\":%.2f,\"temp_c\":%.2f,\"humidity\":%.2f,"
            "\"pressure_hpa\":%.2f,\"rssi\":%d,\"uptime_s\":%lu}",
            tempF, tempC, humidity, pressure, WiFi.RSSI(), millis() / 1000);
 
   if (mqtt.publish("home/closet/environment", payload)) {
     Serial.printf("Published: %s\n", payload);
   } else {
     Serial.println("Publish failed.");
   }
 
   // ----- Threshold alerts (edge-triggered: only publish on state change) -----
   bool tempAlert = (tempF > TEMP_HIGH_F) || (tempF < TEMP_LOW_F);
   if (tempAlert != lastTempAlertState) {
     char alertMsg[150];
     snprintf(alertMsg, sizeof(alertMsg),
              "{\"alert\":%s,\"temp_f\":%.2f,\"threshold_high\":%.2f,\"threshold_low\":%.2f}",
              tempAlert ? "true" : "false", tempF, TEMP_HIGH_F, TEMP_LOW_F);
     mqtt.publish("home/closet/alerts/temperature", alertMsg, true);
     Serial.printf("TEMP ALERT: %s\n", alertMsg);
     lastTempAlertState = tempAlert;
   }
 
   bool humidityAlert = (humidity > HUMIDITY_HIGH_PCT) || (humidity < HUMIDITY_LOW_PCT);
   if (humidityAlert != lastHumidityAlertState) {
     char alertMsg[150];
     snprintf(alertMsg, sizeof(alertMsg),
              "{\"alert\":%s,\"humidity\":%.2f,\"threshold_high\":%.2f,\"threshold_low\":%.2f}",
              humidityAlert ? "true" : "false", humidity, HUMIDITY_HIGH_PCT, HUMIDITY_LOW_PCT);
     mqtt.publish("home/closet/alerts/humidity", alertMsg, true);
     Serial.printf("HUMIDITY ALERT: %s\n", alertMsg);
     lastHumidityAlertState = humidityAlert;
   }
 }
 
 // ----- Setup -----
 void setup() {
   Serial.begin(115200);
   delay(1000);
   Serial.println("\n=== Closet Monitor starting ===");
 
   Wire.begin(21, 22);  // SDA=21, SCL=22
   if (!bme.begin(0x76) && !bme.begin(0x77)) {
     Serial.println("BME280 not found! Halting.");
     while (1) delay(1000);
   }
   Serial.println("BME280 initialized.");
 
   connectWiFi();
   connectMQTT();
 }
 
 // ----- Main loop -----
 void loop() {
   if (WiFi.status() != WL_CONNECTED) connectWiFi();
   if (!mqtt.connected()) connectMQTT();
   mqtt.loop();
 
   if (millis() - lastPublish >= PUBLISH_INTERVAL_MS) {
     readAndPublish();
     lastPublish = millis();
   }
 }