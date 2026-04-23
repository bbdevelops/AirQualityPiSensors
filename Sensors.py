
import os
import sqlite3
import requests
import time
import logging
from datetime import datetime, timezone

from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_bme680

from pms5003 import PMS5003
from dotenv import load_dotenv

load_dotenv()
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file_path = os.path.join(script_dir, 'error.log')
DB_PATH = os.path.join(script_dir, 'readings.db')

logging.basicConfig(filename=log_file_path, level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s')


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pm1_0     REAL,
                pm2_5     REAL,
                pm10      REAL,
                temp      REAL,
                humidity  REAL,
                pressure  REAL,
                altitude  REAL
            )
        """)


def store_reading(pms_data, bme_data):
    ts = datetime.now(timezone.utc).isoformat()
    row = (
        ts,
        pms_data.get("PM1_0") if pms_data else None,
        pms_data.get("PM2_5") if pms_data else None,
        pms_data.get("PM10")  if pms_data else None,
        float(bme_data["Temperature"]) if bme_data else None,
        float(bme_data["Humidity"])    if bme_data else None,
        float(bme_data["Pressure"])    if bme_data else None,
        float(bme_data["Altitude"])    if bme_data else None,
    )
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO readings "
                "(timestamp, pm1_0, pm2_5, pm10, temp, humidity, pressure, altitude) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row
            )
        logging.info("Reading stored at %s.", ts)
    except sqlite3.Error as e:
        logging.error("Failed to store reading in database: %s", e)


def _parse_int_env(name, default):
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        return int(value, 0)
    except ValueError:
        logging.warning("Invalid value for %s=%r. Using default %s.", name, value, default)
        return default


def _parse_float_env(name, default):
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        return float(value)
    except ValueError:
        logging.warning("Invalid value for %s=%r. Using default %s.", name, value, default)
        return default


def _parse_i2c_addr(value, default=0x77):
    if value is None or not str(value).strip():
        return default

    try:
        parsed = int(str(value).strip(), 0)
    except ValueError:
        logging.warning("Invalid I2C_ADDR=%r. Using default %s.", value, hex(default))
        return default

    if parsed not in (0x76, 0x77):
        logging.warning("I2C_ADDR %s is not supported for BME680. Using default %s.", hex(parsed), hex(default))
        return default

    return parsed


class SensorData:
    def __init__(self):
        self.api_endpoint = self._get_api_endpoint()
        self.request_timeout = _parse_float_env("REQUEST_TIMEOUT", 10.0)
        self.pms5003 = None
        self.bme680 = None

        self._init_pms5003()
        self._init_bme680()

        if self.pms5003 is None and self.bme680 is None:
            logging.error("No sensors were initialized. Check wiring and environment configuration.")

    def _get_api_endpoint(self):
        endpoint = os.getenv("API_ENDPOINT", "").strip()

        if not endpoint:
            logging.warning("API_ENDPOINT is not configured. Sensor reads will run but API sends are skipped.")
            return None

        return endpoint.rstrip("/")

    def _init_pms5003(self):
        device = os.getenv("PMS_DEVICE", "/dev/serial0")
        pin_enable = _parse_int_env("PMS_PIN_ENABLE", 22)
        pin_reset = _parse_int_env("PMS_PIN_RESET", 27)

        try:
            self.pms5003 = PMS5003(
                    device=device,
                    baudrate=9600,
                    pin_enable=pin_enable,
                    pin_reset=pin_reset
                    )
            logging.info("PMS5003 initialized on %s.", device)
        except Exception as e:
            logging.error("Unable to initialize PMS5003: %s", e)
            self.pms5003 = None

    def _init_bme680(self):
        i2c_bus = _parse_int_env("BME_I2C_BUS", 1)
        i2c_addr = _parse_i2c_addr(os.getenv("I2C_ADDR"), default=0x77)
        sea_level_pressure = _parse_float_env("SEA_LEVEL_PRESSURE", 1002.25)

        try:
            i2c = I2C(i2c_bus)
            self.bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, i2c_addr)
            self.bme680.sea_level_pressure = sea_level_pressure
            logging.info("BME680 initialized on i2c bus %s at address %s.", i2c_bus, hex(i2c_addr))
        except Exception as e:
            logging.error("Unable to initialize BME680: %s", e)
            self.bme680 = None

    def readPms(self):
        if self.pms5003 is None:
            logging.warning("Skipping PMS5003 read because sensor is not initialized.")
            return None

        try:
            pms_data = self.pms5003.read()

            pm1_0 = pms_data.pm_ug_per_m3(1.0)
            pm2_5 = pms_data.pm_ug_per_m3(2.5)
            pm10 = pms_data.pm_ug_per_m3(10)

            data = {
                    "PM1_0": pm1_0,
                    "PM2_5": pm2_5,
                    "PM10": pm10
                    }

            return data
        except Exception as e:
            logging.error(f"An error occurred when reading PMS data: {e}")
            return None

    def sendPms(self, data):
        if not self.api_endpoint:
            logging.warning("Skipping PMS5003 send because API_ENDPOINT is not configured.")
            return None

        try:
            if not data or not all(k in data for k in ("PM1_0", "PM2_5", "PM10")):
                logging.error("PMS data is missing or incomplete.")
                return None

            endpoint = self.api_endpoint + "/pms5003"

            response = requests.post(url=endpoint, data=data, timeout=self.request_timeout)

            if response.status_code != 200:
                logging.error(f"Failed to send PMS data, status code: {response.status_code}")

            return response.status_code
        except requests.RequestException as e:
            logging.error(f"Network error when sending PMS data: {e}")
        except Exception as e:
            logging.error(f"An error occurred when sending PMS data: {e}")
        return None

    def readBme(self, num_readings=5, delay=2):
        if self.bme680 is None:
            logging.warning("Skipping BME680 read because sensor is not initialized.")
            return None

        if num_readings < 1:
            num_readings = 1

        try:
            temp_total, humidity_total, pressure_total, altitude_total = 0.0, 0.0, 0.0, 0.0

            for idx in range(num_readings):
                temp_total += float(self.bme680.temperature)
                humidity_total += float(self.bme680.relative_humidity)
                pressure_total += float(self.bme680.pressure)
                altitude_total += float(self.bme680.altitude)

                if idx < num_readings - 1:
                    time.sleep(delay)

            temp = temp_total / num_readings
            humidity = humidity_total / num_readings
            pressure = pressure_total / num_readings
            altitude = altitude_total / num_readings

            data = {
                'Temperature': f"{temp:0.1f}",
                'Pressure': f"{pressure:0.3f}",
                'Humidity': f"{humidity:0.1f}",
                'Altitude': f"{altitude:0.2f}"
            }

            return data
        except Exception as e:
            logging.error(f"An error occurred when reading BME data: {e}")
            return None

    def sendBme(self, data):
        if not self.api_endpoint:
            logging.warning("Skipping BME680 send because API_ENDPOINT is not configured.")
            return None

        try:
            if not data or not all(k in data for k in ("Temperature", "Pressure", "Humidity", "Altitude")):
                logging.error("BME data is missing or incomplete.")
                return None

            endpoint = self.api_endpoint + "/bme680"

            response = requests.post(url=endpoint, data=data, timeout=self.request_timeout)

            if response.status_code != 200:
                logging.error(f"Failed to send BME data, status code: {response.status_code}")

            return response.status_code
        except requests.RequestException as e:
            logging.error(f"Network error when sending BME data: {e}")
        except Exception as e:
            logging.error(f"An error occurred when sending BME data: {e}")
        return None


def main():
    init_db()

    sensor_data = SensorData()

    pms_data = sensor_data.readPms()
    sensor_data.sendPms(pms_data)

    bme_data = sensor_data.readBme()
    sensor_data.sendBme(bme_data)

    store_reading(pms_data, bme_data)


if __name__ == "__main__":
    main()
