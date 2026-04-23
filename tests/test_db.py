"""
Tests for the SQLite database helpers in Sensors.py:
  init_db, store_reading
"""

import sqlite3

import pytest
import Sensors
from Sensors import init_db, store_reading


@pytest.fixture(autouse=True)
def isolate_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file for every test in this module."""
    db_file = str(tmp_path / "test_readings.db")
    monkeypatch.setattr(Sensors, "DB_PATH", db_file)
    return db_file


def _row_count(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]


def _fetch_all(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM readings").fetchall()]


class TestInitDb:
    def test_creates_readings_table(self):
        init_db()
        with sqlite3.connect(Sensors.DB_PATH) as conn:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
        assert "readings" in tables

    def test_idempotent(self):
        """Calling init_db twice must not raise."""
        init_db()
        init_db()

    def test_schema_columns(self):
        init_db()
        with sqlite3.connect(Sensors.DB_PATH) as conn:
            cols = [
                row[1]
                for row in conn.execute("PRAGMA table_info(readings)").fetchall()
            ]
        assert cols == [
            "id", "timestamp", "pm1_0", "pm2_5", "pm10",
            "temp", "humidity", "pressure", "altitude",
        ]


class TestStoreReading:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        init_db()

    def test_both_sensors_stores_all_columns(self):
        pms = {"PM1_0": 5.0, "PM2_5": 12.0, "PM10": 25.0}
        bme = {"Temperature": "23.4", "Humidity": "55.0",
               "Pressure": "1013.250", "Altitude": "45.00"}
        store_reading(pms, bme)

        rows = _fetch_all(Sensors.DB_PATH)
        assert len(rows) == 1
        row = rows[0]
        assert row["pm1_0"] == pytest.approx(5.0)
        assert row["pm2_5"] == pytest.approx(12.0)
        assert row["pm10"] == pytest.approx(25.0)
        assert row["temp"] == pytest.approx(23.4)
        assert row["humidity"] == pytest.approx(55.0)
        assert row["pressure"] == pytest.approx(1013.25)
        assert row["altitude"] == pytest.approx(45.0)

    def test_pms_none_stores_null_pm_columns(self):
        bme = {"Temperature": "20.0", "Humidity": "50.0",
               "Pressure": "1000.000", "Altitude": "10.00"}
        store_reading(None, bme)

        row = _fetch_all(Sensors.DB_PATH)[0]
        assert row["pm1_0"] is None
        assert row["pm2_5"] is None
        assert row["pm10"] is None
        assert row["temp"] == pytest.approx(20.0)

    def test_bme_none_stores_null_env_columns(self):
        pms = {"PM1_0": 3.0, "PM2_5": 8.0, "PM10": 15.0}
        store_reading(pms, None)

        row = _fetch_all(Sensors.DB_PATH)[0]
        assert row["pm1_0"] == pytest.approx(3.0)
        assert row["temp"] is None
        assert row["humidity"] is None
        assert row["pressure"] is None
        assert row["altitude"] is None

    def test_both_none_stores_all_null_sensor_columns(self):
        store_reading(None, None)

        row = _fetch_all(Sensors.DB_PATH)[0]
        assert row["pm1_0"] is None
        assert row["temp"] is None

    def test_timestamp_is_iso_utc(self):
        store_reading(None, None)
        row = _fetch_all(Sensors.DB_PATH)[0]
        # UTC ISO timestamps end with +00:00
        assert "+00:00" in row["timestamp"]

    def test_multiple_readings_accumulate(self):
        for _ in range(3):
            store_reading(None, None)
        assert _row_count(Sensors.DB_PATH) == 3

    def test_db_error_does_not_raise(self, monkeypatch):
        """A bad DB path must log the error but not crash the caller."""
        monkeypatch.setattr(Sensors, "DB_PATH", "/nonexistent/path/readings.db")
        store_reading(None, None)  # should not raise
