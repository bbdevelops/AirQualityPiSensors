# Installation Guide

This guide walks through setting up AirQualityPiSensors on a **Raspberry Pi 3 B+** running Raspberry Pi OS (installed via Raspberry Pi Imager). Every command is shown in full — no Linux experience is assumed.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Wire the sensors](#2-wire-the-sensors)
3. [Configure the Pi](#3-configure-the-pi)
4. [Install OS packages](#4-install-os-packages)
5. [Download the code](#5-download-the-code)
6. [Create the Python environment](#6-create-the-python-environment)
7. [Configure your settings](#7-configure-your-settings)
8. [Run manually to test](#8-run-manually-to-test)
9. [Run the dashboard](#9-run-the-dashboard)
10. [Run automatically on a schedule](#10-run-automatically-on-a-schedule)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. What you need

| Item | Notes |
|---|---|
| Raspberry Pi 3 B+ | With Raspberry Pi OS installed via Raspberry Pi Imager |
| PMS5003 sensor | Particle matter (PM1.0 / PM2.5 / PM10) |
| BME680 sensor | Temperature, humidity, pressure, altitude |
| Internet connection on the Pi | For downloading packages |
| A running AirQualityPiAPI instance | See [Kingy/AirQualityPiAPI](https://github.com/Kingy/AirQualityPiAPI) |

> **Tip:** You can use a keyboard, mouse, and monitor connected directly to the Pi, or SSH into it over your local network. To find the Pi's IP address, log in to your router admin page and look for a device named `raspberrypi`.

---

## 2. Wire the sensors

Connect the sensors before powering the Pi on.

### PMS5003 (particle sensor) — UART

| PMS5003 pin | Pi pin | Pi label |
|---|---|---|
| Pin 1 — 5V | Pin 2 | 5V |
| Pin 2 — GND | Pin 6 | GND |
| Pin 3 — TX | Pin 8 | GPIO 14 (TXD) |
| Pin 4 — RX | Pin 10 | GPIO 15 (RXD) |
| Pin 5 — RESET | Pin 11 | GPIO 17 |
| Pin 6 — EN | Pin 15 | GPIO 22 (optional) |

### BME680 (environmental sensor) — I2C

| BME680 pin | Pi pin | Pi label |
|---|---|---|
| VIN | Pin 1 | 3.3V |
| SDA | Pin 3 | GPIO 2 (SDA) |
| SCL | Pin 5 | GPIO 3 (SCL) |
| GND | Pin 9 | GND |

---

## 3. Configure the Pi

The Pi 3 B+ uses its main UART for Bluetooth by default. These steps redirect it back to the GPIO pins so the PMS5003 can communicate.

### 3a. Enable I2C and serial hardware

Open the configuration tool:

```bash
sudo raspi-config
```

Navigate the menus:

1. **Interface Options** → **I2C** → **Yes** (enable)
2. **Interface Options** → **Serial Port**
   - "Would you like a login shell to be accessible over serial?" → **No**
   - "Would you like the serial port hardware to be enabled?" → **Yes**
3. Select **Finish** — do **not** reboot yet.

### 3b. Edit the boot configuration file

Open the file in the nano text editor:

```bash
sudo nano /boot/firmware/config.txt
```

> **Trixie note:** On Raspberry Pi OS Bookworm and later (including Trixie), the boot partition is mounted at `/boot/firmware/`. The old path `/boot/config.txt` no longer exists.

Scroll to the bottom and add these three lines (if they are not already present):

```ini
enable_uart=1
dtoverlay=miniuart-bt
dtparam=i2c_arm=on
```

Save and exit: press **Ctrl + O**, then **Enter**, then **Ctrl + X**.

> **Why `miniuart-bt`?** On the Pi 3 B+, Bluetooth occupies the full UART. This overlay swaps Bluetooth to the mini-UART, freeing the full UART for the PMS5003 sensor.

### 3c. Reboot

```bash
sudo reboot
```

### 3d. Verify the devices

After rebooting, check the serial port exists:

```bash
ls -l /dev/serial0
```

You should see a line like `/dev/serial0 -> ttyAMA0`.

Check the I2C bus for the BME680 (it will appear at address `0x76` or `0x77`):

```bash
sudo i2cdetect -y 1
```

A grid is printed. Look for `76` or `77` in the output. If you see one of those, the sensor is wired and detected correctly.

---

## 4. Install OS packages

> **Trixie note:** Raspberry Pi OS Trixie requires a password for `sudo` commands. If prompted, enter the password you set during first-boot setup.

These packages are needed to compile Python extensions and run the diagnostic tools above:

```bash
sudo apt update
sudo apt install -y build-essential git i2c-tools python3-dev python3-setuptools python3-venv python3-serial
```

This may take a few minutes depending on your internet speed.

---

## 5. Download the code

Clone this repository into your home directory:

```bash
cd ~
git clone https://github.com/bbdevelops/AirQualityPiSensors.git
cd AirQualityPiSensors
```

> All following commands assume you are inside the `AirQualityPiSensors` folder. If you open a new terminal window, run `cd ~/AirQualityPiSensors` first.

---

## 6. Create the Python environment

A virtual environment keeps this project's dependencies separate from the rest of the system.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

You will see lots of output as packages download and install — this is normal. It may take 5–10 minutes on a Pi 3 B+.

> **Tip:** After this step, your terminal prompt will start with `(.venv)`. This tells you the virtual environment is active. To deactivate it later, type `deactivate`. To reactivate it, run `source ~/AirQualityPiSensors/.venv/bin/activate`.

---

## 7. Configure your settings

Copy the example configuration file:

```bash
cp .env.example .env
```

Open it for editing:

```bash
nano .env
```

The file looks like this:

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

The most important setting is **`API_ENDPOINT`**. If you have a running AirQualityPiAPI instance, set it to that URL. If you don't have one yet, **leave it blank** — the script will still collect readings and save them locally to the SQLite database, and the dashboard will work normally. API posting is simply skipped when the endpoint is not set.

```dotenv
# If you have an API:
API_ENDPOINT=https://your-api-url-here

# If you don't have an API yet, leave it empty or omit the line entirely:
API_ENDPOINT=
```

Also check **`I2C_ADDR`**: use whichever address (`0x76` or `0x77`) appeared in the `i2cdetect` output in step 3d.

For **`SEA_LEVEL_PRESSURE`**, look up your local weather station's current mean sea-level pressure (in hPa) for accurate altitude readings. The default is a reasonable approximation.

Save and exit: **Ctrl + O**, **Enter**, **Ctrl + X**.

> **Note:** Do not wrap values in quotes. Write `API_ENDPOINT=https://example.com`, not `API_ENDPOINT="https://example.com"`. The systemd service reads the file directly and quotes will be included literally.

---

## 8. Run manually to test

Make sure the virtual environment is active (`(.venv)` at the start of the prompt), then run:

```bash
python Sensors.py
```

You should see log output in the terminal. Any errors are also written to `error.log` in the project folder.

If both sensors are wired correctly and `API_ENDPOINT` is set, you will see readings posted to the API.

---

## 9. Run the dashboard

The dashboard shows a live chart of all readings stored in the local database.

Start it manually:

```bash
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
```

Then open a browser on any device connected to the same network and go to:

```
http://<pi-ip-address>:8501
```

Replace `<pi-ip-address>` with your Pi's IP address (the same one you use for SSH). To find it on the Pi itself, run `hostname -I`.

### Run the dashboard automatically at startup

Copy the systemd service file:

```bash
sudo cp deploy/systemd/airqualitypi-dashboard.service /etc/systemd/system/
```

Open it to check the paths are correct for your install:

```bash
sudo nano /etc/systemd/system/airqualitypi-dashboard.service
```

If you cloned into `~/AirQualityPiSensors` and your username is `pi`, the defaults should be correct. Save and exit, then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now airqualitypi-dashboard.service
sudo systemctl status airqualitypi-dashboard.service
```

The status output should show `active (running)`. The dashboard will now start automatically every time the Pi boots.

---

## 10. Run automatically on a schedule

The sensor script is designed to run every 15 minutes via a systemd timer.

### 10a. Copy the service and timer files

```bash
sudo cp deploy/systemd/airqualitypi-sensors.service /etc/systemd/system/
sudo cp deploy/systemd/airqualitypi-sensors.timer /etc/systemd/system/
```

### 10b. Check the paths

```bash
sudo nano /etc/systemd/system/airqualitypi-sensors.service
```

Look for `WorkingDirectory`, `EnvironmentFile`, and `ExecStart`. If you cloned into `/home/pi/AirQualityPiSensors` and your username is `pi`, the defaults are correct. If your username is different, update the paths. Save and exit.

### 10c. Enable and start the timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now airqualitypi-sensors.timer
sudo systemctl status airqualitypi-sensors.timer
```

You should see `active (waiting)` — the script will run 2 minutes after boot, then every 15 minutes after that.

### 10d. View logs

```bash
journalctl -u airqualitypi-sensors.service -n 50 --no-pager
```

### Optional: cron fallback

If you prefer cron over systemd, add this line with `crontab -e`:

```cron
*/15 * * * * cd /home/pi/AirQualityPiSensors && /home/pi/AirQualityPiSensors/.venv/bin/python Sensors.py >> /home/pi/AirQualityPiSensors/error.log 2>&1
```

---

## 11. Troubleshooting

### No PMS5003 readings

- Confirm `/dev/serial0` exists: `ls -l /dev/serial0`
- Confirm the serial login shell is **disabled** in `raspi-config` (Interface Options → Serial Port → first question → No)
- Double-check wiring — TX on the sensor goes to RXD (Pin 10) on the Pi, and RX on the sensor goes to TXD (Pin 8)

### No BME680 readings

- Run `sudo i2cdetect -y 1` and confirm an address appears
- Check that `I2C_ADDR` in `.env` matches the detected address (`0x76` or `0x77`)
- Confirm I2C is enabled in `raspi-config` (Interface Options → I2C → Yes)

### API errors

- Make sure `API_ENDPOINT` in `.env` has no trailing slash and no surrounding quotes
- Test network access: `curl <your-api-endpoint>`
- Increase `REQUEST_TIMEOUT` in `.env` if the network is slow

### Virtual environment not active

If you see `ModuleNotFoundError`, the virtual environment is probably not active:

```bash
source ~/AirQualityPiSensors/.venv/bin/activate
```

### Permission denied on `/dev/serial0`

Add your user to the `dialout` group, then log out and back in:

```bash
sudo usermod -aG dialout $USER
```
