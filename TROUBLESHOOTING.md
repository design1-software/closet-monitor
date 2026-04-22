# Closet Monitor — Troubleshooting Runbook

A step-by-step guide for diagnosing and recovering from common issues. Work through the sections in order — each step builds on the previous one.

---

## Quick health check (run this first)

Open a terminal and run all five commands. The output tells you exactly what's broken.

```bash
# 1. Is Mosquitto broker running?
brew services list | grep mosquitto

# 2. Is the Python subscriber running?
ps aux | grep subscriber.py | grep -v grep

# 3. Is the alert listener running?
ps aux | grep alert_listener.py | grep -v grep

# 4. What is my Mac's current IP?
ipconfig getifaddr en0

# 5. Is the ESP32 publishing? (waits 15 seconds for one message)
mosquitto_sub -h $(ipconfig getifaddr en0) -u closet-subscriber -P 'YOUR_PASSWORD' -t "home/closet/#" -C 1 -W 15
```

### Reading the results

| Check | Healthy | Broken |
|---|---|---|
| Mosquitto | `started` | `none` or `stopped` |
| Subscriber | Shows a python process with PID | No output |
| Alert listener | Shows a python process with PID | No output |
| Mac IP | Shows an IP like `192.168.20.25` | No output (not connected to WiFi) |
| ESP32 publishing | Prints a JSON reading within 15s | Times out with no output |

---

## Problem: Dashboard says sensor is offline

**Most common cause:** the subscriber stopped running. The dashboard reads from the SQLite database, and the subscriber is what writes to it. If the subscriber isn't running, no new data arrives, and the dashboard shows the sensor as offline.

### Fix

```bash
# Check if subscriber is running
ps aux | grep subscriber.py | grep -v grep

# If nothing shows up, restart it
cd ~/Documents/closet-monitor/subscriber
source venv/bin/activate
python subscriber.py &

# Verify it connected
# (wait 5 seconds, you should see "Connected to MQTT broker" and "Stored reading" lines)
```

---

## Problem: Subscriber won't connect ("Not authorized")

**Cause:** MQTT credentials are wrong or the password has special characters not properly quoted.

### Fix

```bash
# Check .env file
cat ~/Documents/closet-monitor/subscriber/.env | grep MQTT

# Verify the password is in single quotes if it contains ! $ # or other special chars
# CORRECT:   MQTT_PASSWORD='MyPassword!!'
# WRONG:     MQTT_PASSWORD=MyPassword!!

# Edit if needed
nano ~/Documents/closet-monitor/subscriber/.env

# Restart subscriber
kill %1 2>/dev/null
python subscriber.py &
```

### Test credentials manually

```bash
mosquitto_sub -h $(ipconfig getifaddr en0) -u closet-subscriber -P 'YOUR_PASSWORD' -t "home/closet/#" -C 1 -W 10
```

If this returns "not authorised", the password doesn't match what's in Mosquitto's password file. Recreate it:

```bash
cd /opt/homebrew/etc/mosquitto
mosquitto_passwd passwordfile closet-subscriber
# Enter new password when prompted
brew services restart mosquitto
# Then update .env with the new password
```

---

## Problem: Mosquitto broker is not running

### Fix

```bash
# Check status
brew services list | grep mosquitto

# If stopped, start it
brew services start mosquitto

# If it was already "started" but not actually listening, restart
brew services restart mosquitto

# Verify it's listening on port 1883
sudo lsof -i :1883
# Should show: mosquitto ... *:1883 (LISTEN)
```

### If Mosquitto won't start

```bash
# Check for config errors by running manually with verbose output
brew services stop mosquitto
/opt/homebrew/opt/mosquitto/sbin/mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf -v

# Look for error messages — common issues:
# - "Error: Unable to open password file" → path is wrong in mosquitto.conf
# - "Error: Unable to open acl file" → path is wrong in mosquitto.conf
# - "Error: Address already in use" → another process is on port 1883

# Fix the issue, then restart normally
brew services start mosquitto
```

---

## Problem: ESP32 is not publishing (mosquitto_sub times out)

The ESP32 is either powered off, not connected to WiFi, or trying to reach the wrong broker IP.

### Step 1: Physical check

Go to the closet and look at the ESP32:

- **Red power LED on?** If no → USB cable is loose or wall charger isn't working. Reseat the cable or try a different charger.
- **Red LED on but no blue LED activity?** The ESP32 is powered but may be stuck. Press the **EN button** (small button near the USB port) to reboot it. Wait 10 seconds, then check `mosquitto_sub` again.

### Step 2: WiFi check

If the ESP32 is powered and rebooted but still not publishing, it may have lost WiFi.

**Common causes:**
- WiFi password changed → need to reflash firmware with new password
- Router rebooted and ESP32 hasn't reconnected → press EN to reboot ESP32
- WiFi SSID changed → need to reflash firmware
- ESP32 is too far from the access point → check RSSI in recent readings, should be above -85 dBm

### Step 3: Broker IP check

If your Mac's IP changed (check with `ipconfig getifaddr en0`), the ESP32 is trying to publish to the old IP.

**Fix:** reflash the ESP32 with the new broker IP:

```bash
# Update config.h with new MQTT_HOST IP
nano ~/Documents/closet-monitor/config.h

# Bring ESP32 to the Mac, plug in via USB-C
cd ~/Documents/closet-monitor
arduino-cli compile --fqbn esp32:esp32:esp32 .
arduino-cli upload -p /dev/cu.usbserial-0001 --fqbn esp32:esp32:esp32 .
# Hold BOOT button when you see "Connecting......"

# Verify it reconnects
mosquitto_sub -h $(ipconfig getifaddr en0) -u closet-subscriber -P 'YOUR_PASSWORD' -t "home/closet/#" -C 1

# Move ESP32 back to closet wall charger
```

**Prevention:** set a static IP reservation for your Mac in your router's DHCP settings so the IP never changes.

---

## Problem: Mac's IP address changed

**Cause:** DHCP assigned a different IP after a reboot, network switch, or lease expiration.

**What breaks:** the ESP32 firmware has the broker IP hardcoded. If the Mac's IP changes, the ESP32 publishes to the old IP and nothing arrives.

### Fix

```bash
# Check current IP
ipconfig getifaddr en0

# If different from what's in config.h, you need to:
# 1. Update config.h with the new IP
# 2. Reflash the ESP32 (see "Broker IP check" above)
# 3. Update .env with the new MQTT_HOST
# 4. Restart subscriber and alert listener
```

### Prevention

Set a static DHCP reservation in your router for your Mac's MAC address. This ensures the same IP is assigned every time.

---

## Problem: Dashboard won't start ("command not found: streamlit")

**Cause:** the Python virtual environment isn't activated.

### Fix

```bash
cd ~/Documents/closet-monitor/subscriber
source venv/bin/activate
cd ~/Documents/closet-monitor/dashboard
streamlit run dashboard.py
```

Always activate the venv first — Streamlit is installed there, not globally.

---

## Problem: Dashboard shows stale data (no new readings)

**Cause:** subscriber crashed or disconnected silently.

### Fix

```bash
# Kill any existing subscriber
ps aux | grep subscriber.py | grep -v grep
# Note the PID, then:
kill <PID>

# Restart
cd ~/Documents/closet-monitor/subscriber
source venv/bin/activate
python subscriber.py &

# Watch for "Stored reading" lines to confirm data is flowing
```

---

## Problem: Alert listener not sending notifications

### Fix

```bash
# Check if alert listener is running
ps aux | grep alert_listener.py | grep -v grep

# If not running, start it
cd ~/Documents/closet-monitor/subscriber
source venv/bin/activate
python alert_listener.py &

# Test with a simulated alert
mosquitto_pub -h $(ipconfig getifaddr en0) -u closet-sensor -P 'SENSOR_PASSWORD' -t "home/closet/alerts/temperature" -m '{"alert":true,"temp_f":86.0,"threshold_high":85.0,"threshold_low":50.0}'

# You should see a macOS notification banner appear
```

---

## Problem: Mac rebooted — what needs restarting?

After a Mac reboot, this is the recovery sequence:

```bash
# Step 1: Mosquitto auto-starts via brew services — verify
brew services list | grep mosquitto
# If not started: brew services start mosquitto

# Step 2: Start the subscriber
cd ~/Documents/closet-monitor/subscriber
source venv/bin/activate
python subscriber.py &

# Step 3: Start the alert listener
python alert_listener.py &

# Step 4: Verify ESP32 is publishing
mosquitto_sub -h $(ipconfig getifaddr en0) -u closet-subscriber -P 'YOUR_PASSWORD' -t "home/closet/#" -C 1

# Step 5: Keep Mac awake (if needed)
caffeinate -dims &

# Step 6: Launch dashboard (optional — only when you want to view it)
cd ~/Documents/closet-monitor/dashboard
streamlit run dashboard.py
```

**Note:** Mosquitto auto-starts on reboot (brew service). The subscriber and alert listener do NOT — they must be started manually each time. This will be resolved when services migrate to the Acer or Pi with proper service management.

---

## Problem: Serial port locked ("screen is terminating" or "resource busy")

**Cause:** a previous `screen` session or Arduino upload is holding the serial port.

### Fix

```bash
# Find what's holding the port
sudo lsof /dev/cu.usbserial-0001

# Kill the process
sudo kill -9 <PID>

# Clean up orphaned screen sessions
screen -wipe
pkill screen

# Verify port is free (should return nothing)
sudo lsof /dev/cu.usbserial-0001
```

---

## Full system restart (nuclear option)

If everything seems broken and you want a clean start:

```bash
# 1. Kill everything
pkill -f subscriber.py
pkill -f alert_listener.py
pkill -f streamlit
brew services stop mosquitto

# 2. Restart Mosquitto
brew services start mosquitto

# 3. Verify broker is listening
sudo lsof -i :1883

# 4. Physically reboot the ESP32 (press EN button or unplug/replug power)

# 5. Verify ESP32 is publishing
mosquitto_sub -h $(ipconfig getifaddr en0) -u closet-subscriber -P 'YOUR_PASSWORD' -t "home/closet/#" -C 1 -W 30

# 6. Start subscriber
cd ~/Documents/closet-monitor/subscriber
source venv/bin/activate
python subscriber.py &

# 7. Start alert listener
python alert_listener.py &

# 8. Keep Mac awake
caffeinate -dims &

# 9. Launch dashboard
cd ~/Documents/closet-monitor/dashboard
streamlit run dashboard.py

# 10. Verify dashboard shows green status at http://localhost:8501
```

---

## Reference: key file locations

| File | Path | Purpose |
|---|---|---|
| ESP32 firmware | `~/Documents/closet-monitor/closet-monitor.ino` | Sensor code |
| ESP32 config (secrets) | `~/Documents/closet-monitor/config.h` | WiFi + MQTT credentials |
| Mosquitto config | `/opt/homebrew/etc/mosquitto/mosquitto.conf` | Broker settings |
| Mosquitto passwords | `/opt/homebrew/etc/mosquitto/passwordfile` | Hashed MQTT credentials |
| Mosquitto ACLs | `/opt/homebrew/etc/mosquitto/aclfile` | Topic permissions |
| Python subscriber | `~/Documents/closet-monitor/subscriber/subscriber.py` | MQTT → SQLite |
| Alert listener | `~/Documents/closet-monitor/subscriber/alert_listener.py` | Alerts + notifications |
| Python config (secrets) | `~/Documents/closet-monitor/subscriber/.env` | MQTT credentials |
| SQLite database | `~/Documents/closet-monitor/data/closet.db` | All readings + alerts |
| Alert log | `~/Documents/closet-monitor/data/alerts.log` | Flat-file alert history |
| Dashboard | `~/Documents/closet-monitor/dashboard/dashboard.py` | Streamlit UI |
| Virtual environment | `~/Documents/closet-monitor/subscriber/venv/` | Python dependencies |

## Reference: key commands

| Task | Command |
|---|---|
| Check Mac IP | `ipconfig getifaddr en0` |
| Check broker status | `brew services list \| grep mosquitto` |
| Check subscriber | `ps aux \| grep subscriber.py \| grep -v grep` |
| Grab one reading | `mosquitto_sub -h $(ipconfig getifaddr en0) -u closet-subscriber -P 'PWD' -t "home/closet/#" -C 1` |
| Count total readings | `sqlite3 ~/Documents/closet-monitor/data/closet.db "SELECT COUNT(*) FROM readings;"` |
| Recent readings | `sqlite3 ~/Documents/closet-monitor/data/closet.db "SELECT * FROM readings ORDER BY id DESC LIMIT 5;"` |
| Recent alerts | `sqlite3 ~/Documents/closet-monitor/data/closet.db "SELECT * FROM alerts ORDER BY id DESC LIMIT 5;"` |
| Compile firmware | `cd ~/Documents/closet-monitor && arduino-cli compile --fqbn esp32:esp32:esp32 .` |
| Flash firmware | `arduino-cli upload -p /dev/cu.usbserial-0001 --fqbn esp32:esp32:esp32 .` |
| Start dashboard | `cd ~/Documents/closet-monitor/subscriber && source venv/bin/activate && cd ../dashboard && streamlit run dashboard.py` |
