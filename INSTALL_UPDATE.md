# Installation Guide (Updated)

This guide walks through setting up AirQualityPiSensors on a **Raspberry Pi 3 B+** running **Raspberry Pi OS Trixie (Debian 13)**. Every command is shown in full — no Linux experience is assumed.

> **About this guide:** This is a corrected and updated replacement for the original INSTALL.md. The original contained two hardware wiring errors that would prevent the PMS5003 sensor from working, and was missing several steps required on Trixie. All corrections are noted where they appear.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Wire the sensors](#2-wire-the-sensors)
3. [Configure the Pi](#3-configure-the-pi)
4. [Install OS packages](#4-install-os-packages)
5. [Add your user to the required groups](#5-add-your-user-to-the-required-groups)
6. [Download the code](#6-download-the-code)
7. [Create the Python environment](#7-create-the-python-environment)
8. [Configure your settings](#8-configure-your-settings)
9. [Run manually to test](#9-run-manually-to-test)
10. [Run the dashboard](#10-run-the-dashboard)
11. [Run automatically on a schedule](#11-run-automatically-on-a-schedule)
12. [Access the database](#12-access-the-database)
13. [Shutting down safely](#13-shutting-down-safely)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. What you need

| Item | Notes |
|---|---|
| Raspberry Pi 3 B+ | With Raspberry Pi OS Trixie installed via Raspberry Pi Imager |
| PMS5003 sensor | Particle matter (PM1.0 / PM2.5 / PM10) |
| BME680 sensor | Temperature, humidity, pressure, altitude |
| Jumper wires | To connect sensors to the Pi's GPIO header |
| Breadboard | Optional but recommended for organising wires |
| Internet connection on the Pi | For downloading packages |
| A running AirQualityPiAPI instance | Optional — see [Kingy/AirQualityPiAPI](https://github.com/Kingy/AirQualityPiAPI). If you don't have one, readings are saved locally and the dashboard still works. |

> **Tip:** You can use a keyboard, mouse, and monitor connected directly to the Pi, or SSH into it over your local network. To find the Pi's IP address, log in to your router admin page and look for a device named `raspberrypi`.

---

## 2. Wire the sensors

**Connect the sensors before powering the Pi on.**

### A note on TX and RX

TX means *transmit* and RX means *receive* — from the perspective of the device the label is printed on. This means:

- The **sensor's TX** pin (it transmits data) must connect to the **Pi's RX** pin (the Pi receives it)
- The **sensor's RX** pin (it receives commands) must connect to the **Pi's TX** pin (the Pi transmits)

**Do not connect TX to TX or RX to RX.** The original INSTALL.md had this wrong — it is the most common wiring mistake with UART sensors and will result in no data being received.

---

### PMS5003 (particle sensor) — UART

The PMS5003 communicates over a serial UART connection and runs on 5 V.

| PMS5003 pin | Pi physical pin | Pi label | Notes |
|---|---|---|---|
| Pin 1 — VCC | Pin 2 | 5V | Power — sensor requires 5 V |
| Pin 2 — GND | Pin 6 | GND | Ground |
| Pin 3 — **TX** | Pin **10** | GPIO 15 (**RXD**) | Sensor transmits → Pi receives |
| Pin 4 — **RX** | Pin **8** | GPIO 14 (**TXD**) | Sensor receives ← Pi transmits |
| Pin 5 — RESET | Pin **13** | GPIO **27** | Hardware reset — required for error recovery |
| Pin 6 — SET/EN | Pin 15 | GPIO 22 | Enable/sleep control |

> **Correction from original guide:** The original had TX wired to Pin 8 and RX to Pin 10 — this is backwards and the sensor will not transmit. TX must go to Pin 10 (Pi RXD) and RX must go to Pin 8 (Pi TXD).

> **Correction from original guide:** The original listed RESET as Pin 11 (GPIO 17). This does not match the software configuration. The correct pin is Pin 13 (GPIO 27).

> **Power note:** The 5 V pins (Pin 2 and Pin 4) can be connected to the positive (+) rail of a breadboard to power the PMS5003. Connect the negative (−) rail to any Pi ground pin (e.g. Pin 6). The BME680 runs on 3.3 V — do not connect it to the 5 V rail.

---

### BME680 (environmental sensor) — I2C

The BME680 measures temperature, humidity, pressure, and altitude. It runs on **3.3 V** — do not connect it to 5 V.

| BME680 pin | Pi physical pin | Pi label |
|---|---|---|
| VIN | Pin 1 | 3.3V |
| GND | Pin 9 | GND |
| SDA | Pin 3 | GPIO 2 (SDA) |
| SCL | Pin 5 | GPIO 3 (SCL) |

---

### Pi GPIO pin reference

Pin 1 is at the end of the header nearest the SD card slot. Odd-numbered pins run along the inner edge, even-numbered pins along the outer edge.

```
        3V3 [ 1] [ 2] 5V
  GPIO2/SDA [ 3] [ 4] 5V
  GPIO3/SCL [ 5] [ 6] GND
      GPIO4 [ 7] [ 8] GPIO14/TXD  ← PMS5003 RX
        GND [ 9] [10] GPIO15/RXD  ← PMS5003 TX
     GPIO17 [11] [12] GPIO18
     GPIO27 [13] [14] GND          ← PMS5003 RESET
     GPIO22 [15] [16] GPIO23       ← PMS5003 SET/EN
        3V3 [17] [18] GPIO24
     GPIO10 [19] [20] GND
      GPIO9 [21] [22] GPIO25
     GPIO11 [23] [24] GPIO8
        GND [25] [26] GPIO7
      GPIO0 [27] [28] GPIO1
      GPIO5 [29] [30] GND
      GPIO6 [31] [32] GPIO12
     GPIO13 [33] [34] GND
     GPIO19 [35] [36] GPIO16
     GPIO26 [37] [38] GPIO20
        GND [39] [40] GPIO21
```

---

## 3. Configure the Pi

The Pi 3 B+ uses its main UART for Bluetooth by default. These steps disable Bluetooth and free that UART for the PMS5003.

### 3a. Enable I2C and serial hardware

Open the configuration tool:

```bash
sudo raspi-config
```

> **Sudo prompt:** Trixie requires a password for `sudo` commands. Enter the password you set during first-boot setup.

Use the **arrow keys** to navigate and **Enter** to select:

1. **Interface Options** → **I2C** → **Yes** (enable I2C)
2. **Interface Options** → **Serial Port**
   - "Would you like a login shell to be accessible over serial?" → **No**
   - "Would you like the serial port hardware to be enabled?" → **Yes**
3. Arrow back to **Finish** and press Enter — choose **No** when asked to reboot (we will reboot after the next step).

### 3b. Edit the boot configuration file

Open the file:

```bash
sudo nano /boot/firmware/config.txt
```

> **About nano:** Nano is a simple terminal text editor. The cursor moves with the arrow keys. To save: press **Ctrl + O** (hold Ctrl and press the letter O), then press **Enter** to confirm. To exit: press **Ctrl + X**.

> **Trixie note:** On Trixie the boot partition is at `/boot/firmware/`. The old path `/boot/config.txt` no longer exists.

Scroll to the bottom using the **Down arrow key** and add these three lines (only if they are not already present):

```ini
enable_uart=1
dtoverlay=disable-bt
dtparam=i2c_arm=on
```

Save with **Ctrl + O**, press **Enter**, then exit with **Ctrl + X**.

> **What these lines do:**
> - `enable_uart=1` — activates the hardware UART on GPIO pins 14 and 15
> - `dtoverlay=disable-bt` — disables Bluetooth, which was occupying the hardware UART on the Pi 3 B+, freeing it for the PMS5003
> - `dtparam=i2c_arm=on` — enables the I2C bus used by the BME680

> **Correction from original guide:** The original used `dtoverlay=miniuart-bt` which keeps Bluetooth active on a reduced UART. This was found to be unreliable for the PMS5003. Using `dtoverlay=disable-bt` instead (disabling Bluetooth entirely) is the confirmed working approach on this hardware.

### 3c. Reboot

```bash
sudo reboot
```

The Pi will disconnect. Wait about 30 seconds, then reconnect.

### 3d. Verify the devices

Check that the serial port is mapped correctly:

```bash
ls -l /dev/serial0
```

You should see a line ending in `-> ttyAMA0`:

```
lrwxrwxrwx 1 root root 7 ... /dev/serial0 -> ttyAMA0
```

If it shows `-> ttyS0` instead, the `disable-bt` overlay did not apply — double-check you edited `/boot/firmware/config.txt` (not `/boot/config.txt`) and reboot again.

Check the I2C bus for the BME680:

```bash
sudo i2cdetect -y 1
```

A grid of dashes is printed with detected device addresses shown as numbers. Look for `76` or `77` somewhere in the grid — that is the BME680. Note which address appears — you will need it in step 8.

---

## 4. Install OS packages

These packages are needed to compile Python extensions and to provide the GPIO library that the PMS5003 sensor driver requires:

```bash
sudo apt update
sudo apt install -y build-essential git i2c-tools python3-dev python3-setuptools python3-venv python3-serial libgpiod3 libgpiod-dev gpiod
```

> **Trixie note:** `libgpiod3` (not `libgpiod2`) is the correct package name on Trixie. Both `libgpiod3` and `libgpiod-dev` are required so the Python `gpiod` package can compile and link against the system library. Without these, the PMS5003 sensor driver will fail to import.

This may take a few minutes. You will see a lot of output scrolling past — this is normal.

---

## 5. Add your user to the required groups

The sensor script accesses the serial port and GPIO pins. Your user account needs permission for both:

```bash
sudo usermod -a -G dialout pi
sudo usermod -a -G gpio pi
```

> **What this does:** Adds the user `pi` to the `dialout` group (serial port access) and the `gpio` group (GPIO pin access). Without these, the script will fail with "permission denied" errors when trying to open `/dev/ttyAMA0` or control the enable/reset pins.

The group changes take effect on the next login. Reboot now:

```bash
sudo reboot
```

After reconnecting, confirm the groups were added:

```bash
groups
```

You should see both `dialout` and `gpio` in the output.

---

## 6. Download the code

Navigate to your home directory and clone the repository:

```bash
cd ~
git clone https://github.com/bbdevelops/AirQualityPiSensors.git
cd AirQualityPiSensors
```

> **All following commands assume you are inside the `AirQualityPiSensors` folder.** If you open a new terminal window, run `cd ~/AirQualityPiSensors` first. (`~` is shorthand for your home directory, `/home/pi`.)

---

## 7. Create the Python environment

A virtual environment is a self-contained folder of Python packages for this project, keeping everything separate from the rest of the system.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **What `source .venv/bin/activate` does:** Activates the virtual environment for the current terminal session. Your prompt will change to start with `(.venv)` to show it is active. You need this active whenever you run the project manually.
>
> To deactivate it later: type `deactivate` and press Enter.  
> To reactivate it in a new terminal: run `source ~/AirQualityPiSensors/.venv/bin/activate`.

The install step may take **5–10 minutes** on a Pi 3 B+. This is normal.

### Verify gpiod installed correctly

Once the install finishes, run:

```bash
.venv/bin/python3 -c "import gpiod; print(gpiod.__version__)"
```

You should see a version number such as `2.4.2`. If you see an error about a missing `_gpiod` module, confirm step 4 completed successfully, then run:

```bash
.venv/bin/pip install gpiod --force-reinstall
```

---

## 8. Configure your settings

Copy the example configuration file:

```bash
cp .env.example .env
```

Open it for editing:

```bash
nano .env
```

The file contains:

```dotenv
API_ENDPOINT=https://your-api-url-here
REQUEST_TIMEOUT=10
PMS_DEVICE=/dev/serial0
PMS_PIN_ENABLE=22
PMS_PIN_RESET=27
I2C_ADDR=0x76
BME_I2C_BUS=1
SEA_LEVEL_PRESSURE=1002.25
```

**Settings to review:**

| Setting | What to set |
|---|---|
| `API_ENDPOINT` | Your AirQualityPiAPI URL, or leave blank to skip API posting and save locally only |
| `PMS_DEVICE` | Leave as `/dev/serial0` — confirmed correct for this setup |
| `PMS_PIN_ENABLE` | Leave as `22` — matches the wiring in step 2 |
| `PMS_PIN_RESET` | Leave as `27` — matches the wiring in step 2 |
| `I2C_ADDR` | Set to `0x76` or `0x77` — whichever appeared in the `i2cdetect` output in step 3d |
| `SEA_LEVEL_PRESSURE` | Look up your local weather station's current mean sea-level pressure in hPa for accurate altitude readings. The default is a reasonable approximation. |

Save and exit: **Ctrl + O**, **Enter**, **Ctrl + X**.

> **Important:** Do not wrap values in quotes. Write `API_ENDPOINT=https://example.com`, not `API_ENDPOINT="https://example.com"`. The systemd service reads this file directly and quotes will be treated as part of the value.

> **Important:** Check path values carefully — a missing `/` causes "No such file or directory" errors. For example, `PMS_DEVICE=/dev/serial0` is correct; `PMS_DEVICE=/devserial0` is not.

---

## 9. Run manually to test

Make sure the virtual environment is active (prompt starts with `(.venv)`):

```bash
source .venv/bin/activate
```

Run the sensor script:

```bash
python Sensors.py
```

Then check the log file:

```bash
cat error.log
```

A successful run produces lines like:

```
2026-05-02 12:00:00,000 INFO PMS5003 initialized on /dev/serial0.
2026-05-02 12:00:05,000 INFO BME680 initialized on i2c bus 1 at address 0x77.
2026-05-02 12:00:10,000 INFO Reading stored at 2026-05-02T12:00:10+00:00.
```

If you see `Unable to initialize PMS5003` or timeout errors, work through the [Troubleshooting](#14-troubleshooting) section.

---

## 10. Run the dashboard

The dashboard shows a live chart of all readings stored in the local database.

### Install and start the dashboard service

```bash
sudo cp deploy/systemd/airqualitypi-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now airqualitypi-dashboard.service
```

Check it started successfully:

```bash
sudo systemctl status airqualitypi-dashboard.service
```

The output should include `active (running)`. Press **Q** to exit the status view.

### Open the dashboard

Find the Pi's IP address:

```bash
hostname -I
```

Then open a browser on any device on the same network and go to:

```
http://<pi-ip-address>:8501
```

Replace `<pi-ip-address>` with the address shown by `hostname -I`. If more than one address is listed, use the first one.

The dashboard will start automatically on every boot.

---

## 11. Run automatically on a schedule

The sensor script runs every 15 minutes via a systemd timer. It fires 2 minutes after boot, then repeats every 15 minutes.

### 11a. Copy the service and timer files

```bash
sudo cp deploy/systemd/airqualitypi-sensors.service /etc/systemd/system/
sudo cp deploy/systemd/airqualitypi-sensors.timer /etc/systemd/system/
```

### 11b. Check the paths in the service file

```bash
sudo nano /etc/systemd/system/airqualitypi-sensors.service
```

Confirm these three lines match your setup:

```ini
WorkingDirectory=/home/pi/AirQualityPiSensors
EnvironmentFile=/home/pi/AirQualityPiSensors/.env
ExecStart=/home/pi/AirQualityPiSensors/.venv/bin/python /home/pi/AirQualityPiSensors/Sensors.py
```

If your username is `pi` and you cloned into `~/AirQualityPiSensors`, these are correct as-is. Save and exit: **Ctrl + O**, **Enter**, **Ctrl + X**.

### 11c. Enable and start the timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now airqualitypi-sensors.timer
```

Check the timer is active:

```bash
sudo systemctl status airqualitypi-sensors.timer
```

You should see `active (waiting)`. Press **Q** to exit.

To see when the next scheduled run is:

```bash
systemctl list-timers airqualitypi-sensors.timer
```

### 11d. Trigger a manual test run

Run the service once immediately to confirm everything works:

```bash
sudo systemctl start airqualitypi-sensors.service
```

Then watch the log:

```bash
tail -f /home/pi/AirQualityPiSensors/error.log
```

Press **Ctrl + C** to stop watching the log.

### 11e. View systemd logs

```bash
journalctl -u airqualitypi-sensors.service -n 50 --no-pager
```

---

## 12. Access the database

All sensor readings are stored in a SQLite database file at `/home/pi/AirQualityPiSensors/readings.db`. You can query it directly on the Pi, export it to a spreadsheet, or open it with a GUI tool on another computer.

### Install the SQLite command-line tool

```bash
sudo apt install sqlite3
```

### Query the database on the Pi

Open the database:

```bash
sqlite3 ~/AirQualityPiSensors/readings.db
```

Your prompt will change to `sqlite>`. You can now run SQL queries:

```sql
-- Show the 20 most recent readings
SELECT * FROM readings ORDER BY timestamp DESC LIMIT 20;

-- Show only PM2.5 and temperature from the last 20 readings
SELECT timestamp, pm2_5, temp FROM readings ORDER BY timestamp DESC LIMIT 20;

-- Show readings where PM2.5 exceeded 10 µg/m³
SELECT timestamp, pm2_5 FROM readings WHERE pm2_5 > 10 ORDER BY timestamp;

-- Count total readings stored
SELECT COUNT(*) FROM readings;
```

To exit the SQLite prompt:

```sql
.quit
```

### The readings table

All readings are stored in a single table with these columns:

| Column | Type | Description |
|---|---|---|
| `id` | integer | Auto-incrementing row ID |
| `timestamp` | text | UTC timestamp in ISO 8601 format |
| `pm1_0` | real | PM1.0 concentration (µg/m³) |
| `pm2_5` | real | PM2.5 concentration (µg/m³) |
| `pm10` | real | PM10 concentration (µg/m³) |
| `temp` | real | Temperature (°C) |
| `humidity` | real | Relative humidity (%) |
| `pressure` | real | Barometric pressure (hPa) |
| `altitude` | real | Altitude (m) |

### Export to CSV for spreadsheet software

This command exports all readings to a CSV file you can open in Excel or Google Sheets:

```bash
sqlite3 -csv -header ~/AirQualityPiSensors/readings.db \
  "SELECT * FROM readings ORDER BY timestamp;" > ~/readings.csv
```

The file is saved to `/home/pi/readings.csv`. To copy it to a USB drive, find where the drive is mounted:

```bash
lsblk
```

USB drives typically appear at `/media/pi/<drivename>/`. Then copy:

```bash
cp ~/readings.csv /media/pi/<drivename>/
```

Replace `<drivename>` with the name shown by `lsblk`.

### Open the database on a Windows or Mac computer

Copy `readings.db` to your computer via USB, then open it with [DB Browser for SQLite](https://sqlitebrowser.org/dl/) — a free GUI app. It lets you browse the table, run SQL queries, and export to CSV, with no configuration required.

---

## 13. Shutting down safely

**Do not pull the power cable without shutting down first.** Cutting power mid-write can corrupt the SD card.

Shut down cleanly:

```bash
sudo shutdown -h now
```

Wait about 10 seconds for the green activity LED to stop blinking before disconnecting power.

### Check services are set to auto-start

After any reboot, both services restart automatically. To verify:

```bash
systemctl is-enabled airqualitypi-sensors.timer
systemctl is-enabled airqualitypi-dashboard.service
```

Both should return `enabled`.

### Stop services without shutting down

```bash
sudo systemctl stop airqualitypi-sensors.timer
sudo systemctl stop airqualitypi-dashboard.service
```

### Disable auto-start permanently

```bash
sudo systemctl disable airqualitypi-sensors.timer
sudo systemctl disable airqualitypi-dashboard.service
```

---

## 14. Troubleshooting

### No PMS5003 readings / "Failed to read start of frame byte"

Work through these in order:

**1. Confirm `/dev/serial0` points to `ttyAMA0`:**
```bash
ls -la /dev/serial0
```
Must end with `-> ttyAMA0`. If it shows `-> ttyS0`, the `disable-bt` overlay did not apply — re-check `/boot/firmware/config.txt` and reboot.

**2. Confirm wiring:**

| PMS5003 pin | Must connect to |
|---|---|
| Pin 3 — TX | Pi Pin **10** (GPIO 15 RXD) |
| Pin 4 — RX | Pi Pin **8** (GPIO 14 TXD) |
| Pin 5 — RESET | Pi Pin **13** (GPIO 27) |
| Pin 6 — SET/EN | Pi Pin **15** (GPIO 22) |
| Pin 1 — VCC | Pi Pin 2 or 4 (5 V) |
| Pin 2 — GND | Any GND pin (e.g. Pin 6) |

**3. Check the fan is spinning:**
The PMS5003 has a small internal fan. If it is not spinning when the Pi is powered on, the sensor has no 5 V.

**4. Test the serial port directly:**
```bash
.venv/bin/python3 -c "
import gpiod, serial, time
from gpiod.line import Direction, Value

with gpiod.request_lines('/dev/gpiochip0', consumer='pms-test',
        config={22: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE)}) as req:
    print('Waiting 5 seconds for sensor to wake...')
    time.sleep(5)
    s = serial.Serial('/dev/ttyAMA0', 9600, timeout=5)
    data = s.read(64)
    print('bytes received:', len(data))
    print('hex:', data.hex())
    s.close()
"
```
- `bytes received: 64` with hex starting with `424d` — sensor is working
- `bytes received: 0` — wiring or power problem

---

### "Unable to open port /dev/ttyAMA0: No such file or directory"

Check the exact value in your `.env`:

```bash
grep PMS_DEVICE .env
```

It must read exactly:
```
PMS_DEVICE=/dev/serial0
```

A missing `/` (e.g. `/devserial0`) causes this error. Open `nano .env` to fix it.

---

### "Permission denied" on `/dev/ttyAMA0` or GPIO pins

Your user is not in the required groups:

```bash
sudo usermod -a -G dialout pi
sudo usermod -a -G gpio pi
sudo reboot
```

---

### No BME680 readings

- Run `sudo i2cdetect -y 1` and confirm an address (`76` or `77`) appears
- Check `I2C_ADDR` in `.env` matches the detected address
- Confirm I2C is enabled: `sudo raspi-config` → Interface Options → I2C → Yes

---

### `import gpiod` fails / missing `_gpiod` module

The system library is missing or the pip package could not link against it:

```bash
sudo apt install libgpiod3 libgpiod-dev
.venv/bin/pip install gpiod --force-reinstall
```

---

### API errors

- Confirm `API_ENDPOINT` in `.env` has no trailing slash and no surrounding quotes
- Test connectivity from the Pi: `curl <your-api-endpoint>`
- Increase `REQUEST_TIMEOUT` in `.env` if your network is slow

---

### Virtual environment not active

If you see `ModuleNotFoundError` when running manually, activate the environment first:

```bash
source ~/AirQualityPiSensors/.venv/bin/activate
```

The prompt will change to start with `(.venv)`.
