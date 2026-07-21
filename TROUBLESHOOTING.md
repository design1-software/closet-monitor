# Closet Monitor — Troubleshooting Runbook

A step-by-step guide for diagnosing and recovering from common issues. Work through the sections in order — each step builds on the previous one.

## System overview

| Component | Where it runs | Address |
|---|---|---|
| ESP32 + BME280 sensor | Closet, VLAN 31 (Gorgeous-Auto) | — |
| Mosquitto MQTT broker | Raspberry Pi, VLAN 10 | 192.168.10.16 |
| Subscriber + Alert Listener + Dashboard | Acer (jmg-server), VLAN 10 | 192.168.10.11 |
| Dashboard URL | Any device on the network | http://192.168.10.11:8501 |

---

## Quick health check (run this first)

Open PowerShell on the Acer and run all four commands. The output tells you exactly what's broken.

```powershell
# 1. Are the Python services running?
Get-Process -Name python | Select-Object Id

# 2. Is the dashboard port listening?
netstat -ano | findstr ":8501"

# 3. Is the Pi's broker reachable?
$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect("192.168.10.16", 1883); Write-Output "Broker REACHABLE"; $c.Close() } catch { Write-Output "Broker UNREACHABLE" }

# 4. Are new readings arriving? (run after waiting 30 seconds)
& "C:\Users\jbm06\closet-monitor\subscriber\venv\Scripts\python.exe" -c "import sqlite3; c = sqlite3.connect('C:/Users/jbm06/closet-monitor/data/closet.db'); print(c.execute('SELECT received_at FROM readings ORDER BY id DESC LIMIT 1').fetchone())"
```

### Reading the results

| Check | Healthy | Broken |
|---|---|---|
| Python processes | Shows 3+ PIDs | No output |
| Dashboard port | Shows a LISTENING line with port 8501 | No output |
| Broker | `Broker REACHABLE` | `Broker UNREACHABLE` |
| Latest reading | Timestamp within the last minute | Old timestamp or error |

---

## Problem: Acer rebooted — what needs restarting?

The Windows Scheduled Task (ClosetMonitorServices) handles this automatically at boot. If services didn't come up:

```powershell
# Check task status
Get-ScheduledTask -TaskName "ClosetMonitorServices" | Select-Object TaskName, State
Get-ScheduledTaskInfo -TaskName "ClosetMonitorServices" | Select-Object LastRunTime, LastTaskResult

# Run it manually if needed
Start-ScheduledTask -TaskName "ClosetMonitorServices"

# Or launch directly
& "C:\Users\jbm06\closet-monitor\start-services.ps1"
```

**Note:** Mosquitto on the Pi auto-starts via `systemctl` and survives Pi reboots independently.

---

## Problem: Dashboard shows sensor is offline / stale data

**Most common cause:** the subscriber stopped running.

```powershell
# Check if subscriber is running
Get-Process -Name python | Select-Object Id

# Check the subscriber log for errors
Get-Content "C:\Users\jbm06\closet-monitor\data\logs\subscriber-error.log" -Tail 30

# Restart all services
& "C:\Users\jbm06\closet-monitor\start-services.ps1"

# Tail the log to confirm readings are flowing
Get-Content "C:\Users\jbm06\closet-monitor\data\logs\subscriber-error.log" -Wait
# You should see "Stored reading" lines every ~30 seconds
```

---

## Problem: Subscriber won't connect ("Not authorized")

**Cause:** MQTT credentials in `.env` don't match what's in the Pi's Mosquitto password file.

```powershell
# Check .env credentials
Get-Content "C:\Users\jbm06\closet-monitor\subscriber\.env"
```

If credentials look wrong, edit the file and restart services:

```powershell
notepad "C:\Users\jbm06\closet-monitor\subscriber\.env"
& "C:\Users\jbm06\closet-monitor\start-services.ps1"
```

To reset the password on the Pi, SSH in and run:

```bash
ssh <pi-user>@192.168.10.16
mosquitto_passwd /etc/mosquitto/passwordfile closet-subscriber
sudo systemctl restart mosquitto
# Then update MQTT_PASSWORD in .env on the Acer and restart services
```

---

## Problem: Mosquitto broker is not running

Mosquitto lives on the Pi, not the Acer. SSH in to manage it:

```bash
ssh <pi-user>@192.168.10.16

# Check status
sudo systemctl status mosquitto

# Start if stopped
sudo systemctl start mosquitto

# Enable auto-start on boot (if not already set)
sudo systemctl enable mosquitto

# Verify it's listening
sudo ss -tlnp | grep 1883
```

### If Mosquitto won't start on the Pi

```bash
# Run manually to see config errors
sudo systemctl stop mosquitto
mosquitto -c /etc/mosquitto/mosquitto.conf -v

# Common errors:
# "Unable to open password file" → path wrong in mosquitto.conf
# "Unable to open acl file"     → path wrong in mosquitto.conf
# "Address already in use"      → another process on port 1883
```

---

## Problem: ESP32 is not publishing

The subscriber is connected to the broker but no readings are arriving.

### Step 1: Physical check

Go to the closet and look at the ESP32:

- **Red power LED on?** If no → USB cable is loose or charger isn't working. Reseat or swap.
- **Powered but stuck?** Press the **EN button** (small button near the USB port) to reboot. Wait 30 seconds and watch the subscriber log.

### Step 2: Confirm via live log

```powershell
Get-Content "C:\Users\jbm06\closet-monitor\data\logs\subscriber-error.log" -Wait
# Press EN on the ESP32 — you should see "Stored event [home/closet/status]: online"
# followed by "Stored reading" lines within 30 seconds
```

### Step 3: WiFi check

If rebooting doesn't help, the ESP32 may have lost WiFi:

- **Router rebooted and ESP32 hasn't reconnected** → press EN again
- **WiFi password changed** → need to reflash firmware with new credentials
- **SSID changed** → need to reflash firmware

### Step 4: Broker IP check

The ESP32 has the broker IP hardcoded in `config.h` (`MQTT_HOST = "192.168.10.16"`). If the Pi's IP changed, the ESP32 is publishing to the wrong address. Reflash if needed:

```powershell
# Update config.h with the correct Pi IP
notepad "C:\Users\jbm06\closet-monitor\config.h"

# Bring ESP32 to the Acer, plug in via USB-C, then flash:
arduino-cli compile --fqbn esp32:esp32:esp32 "C:\Users\jbm06\closet-monitor"
arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32 "C:\Users\jbm06\closet-monitor"
# Hold BOOT button when you see "Connecting......"
# Check Device Manager for the correct COM port if COM3 doesn't work
```

---

## Problem: Acer's IP changed

**Cause:** DHCP assigned a different IP after a reboot or update. This breaks dashboard access from other devices (they're using the old IP).

**Fix:** assign a static IP directly on the Acer's NIC so it never changes:

1. Open **Settings → Network & Internet → Ethernet → your adapter → Edit**
2. Switch from Automatic (DHCP) to **Manual**
3. Set: IP address, subnet mask (255.255.255.0), gateway (your VLAN 10 gateway), DNS (192.168.10.16 for Pi-hole)

Alternatively, configure a static DHCP binding on the Cisco 1111:

```
ip dhcp pool ACER-SERVER
  host 192.168.10.11 255.255.255.0
  hardware-address <acer-mac-address>
```

---

## Problem: Dashboard unreachable from other devices

```powershell
# Confirm Streamlit is listening
netstat -ano | findstr ":8501"
# Should show: TCP 0.0.0.0:8501 ... LISTENING

# Confirm Acer's current IP
ipconfig | findstr "IPv4"

# If the IP changed, use the new IP in the browser:
# http://<new-ip>:8501
```

If the port is listening but devices can't reach it, check the Windows Firewall:

```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "Closet Monitor Dashboard" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow
```

---

## Problem: Alert notifications not arriving

### Windows toast not showing

Toasts only appear when a user is logged into the Acer. If the session is locked or no one is logged in, toasts are silently dropped. Use ntfy for reliable push notifications.

### ntfy not sending

Check that `NTFY_TOPIC` is set in `.env`:

```powershell
Get-Content "C:\Users\jbm06\closet-monitor\subscriber\.env" | findstr "NTFY"
```

If `NTFY_TOPIC` is blank, add your topic:

```powershell
notepad "C:\Users\jbm06\closet-monitor\subscriber\.env"
# Set NTFY_TOPIC=your-topic-name
```

Then restart services and check the alert listener log:

```powershell
& "C:\Users\jbm06\closet-monitor\start-services.ps1"
Get-Content "C:\Users\jbm06\closet-monitor\data\logs\alert-listener-error.log" -Wait
```

### Test with a simulated alert

SSH into the Pi and publish a test alert:

```bash
ssh <pi-user>@192.168.10.16
mosquitto_pub -h 192.168.10.16 -u closet-sensor -P '<your-mqtt-password>' \
  -t "home/closet/alerts/temperature" \
  -m '{"alert":true,"temp_f":86.0,"threshold_high":85.0,"threshold_low":50.0}'
```

You should see a Windows toast on the Acer and a push notification in the ntfy app.

---

## Full system restart (nuclear option)

If everything seems broken and you want a clean start:

```powershell
# 1. Kill all Python processes
Get-Process -Name python | Stop-Process -Force

# 2. Verify broker is still up on the Pi
$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect("192.168.10.16", 1883); Write-Output "Broker OK"; $c.Close() } catch { Write-Output "Broker DOWN — SSH into Pi and restart mosquitto" }

# 3. Physically reboot the ESP32 (press EN button in the closet)

# 4. Start all services
& "C:\Users\jbm06\closet-monitor\start-services.ps1"

# 5. Tail the log and wait for readings
Get-Content "C:\Users\jbm06\closet-monitor\data\logs\subscriber-error.log" -Wait

# 6. Verify dashboard
# Open http://192.168.10.11:8501 — should show green status
```

---

## Reference: key file locations

| File | Path | Purpose |
|---|---|---|
| ESP32 firmware | `C:\Users\jbm06\closet-monitor\closet-monitor.ino` | Sensor code |
| ESP32 config (secrets) | `C:\Users\jbm06\closet-monitor\config.h` | WiFi + MQTT credentials (gitignored) |
| Startup script | `C:\Users\jbm06\closet-monitor\start-services.ps1` | Launches all services |
| Subscriber | `C:\Users\jbm06\closet-monitor\subscriber\subscriber.py` | MQTT → SQLite |
| Alert listener | `C:\Users\jbm06\closet-monitor\subscriber\alert_listener.py` | Alerts + notifications |
| Python config (secrets) | `C:\Users\jbm06\closet-monitor\subscriber\.env` | MQTT + ntfy credentials (gitignored) |
| Virtual environment | `C:\Users\jbm06\closet-monitor\subscriber\venv\` | Python dependencies |
| SQLite database | `C:\Users\jbm06\closet-monitor\data\closet.db` | All readings + alerts |
| Alert log (flat file) | `C:\Users\jbm06\closet-monitor\data\alerts.log` | Alert history |
| Service logs | `C:\Users\jbm06\closet-monitor\data\logs\` | stdout/stderr for each service |
| Dashboard | `C:\Users\jbm06\closet-monitor\dashboard\dashboard.py` | Streamlit UI |
| Mosquitto config (Pi) | `/etc/mosquitto/mosquitto.conf` | Broker settings |
| Mosquitto passwords (Pi) | `/etc/mosquitto/passwordfile` | Hashed MQTT credentials |
| Mosquitto ACLs (Pi) | `/etc/mosquitto/aclfile` | Topic permissions |

## Reference: key commands

| Task | Command |
|---|---|
| Check Acer IP | `ipconfig \| findstr "IPv4"` |
| Check services running | `Get-Process -Name python \| Select-Object Id` |
| Tail subscriber log | `Get-Content "C:\Users\jbm06\closet-monitor\data\logs\subscriber-error.log" -Wait` |
| Restart all services | `& "C:\Users\jbm06\closet-monitor\start-services.ps1"` |
| Kill all services | `Get-Process -Name python \| Stop-Process -Force` |
| Count total readings | `& "...\venv\Scripts\python.exe" -c "import sqlite3; c=sqlite3.connect('../data/closet.db'); print(c.execute('SELECT COUNT(*) FROM readings').fetchone())"` |
| Check scheduled task | `Get-ScheduledTask -TaskName "ClosetMonitorServices"` |
| Broker reachability | `Test-NetConnection -ComputerName 192.168.10.16 -Port 1883` |
| SSH into Pi | `ssh <pi-user>@192.168.10.16` |
| Restart Mosquitto (Pi) | `sudo systemctl restart mosquitto` |
| Flash firmware | `arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32 "C:\Users\jbm06\closet-monitor"` |
