"""
Tests for pure-logic functions in dashboard.py:
  pm25_label, load_data
"""

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

import dashboard
from dashboard import pm25_label, load_data


# ── pm25_label ─────────────────────────────────────────────────────────────

class TestPm25Label:
    def test_none_returns_no_data(self):
        label, colour = pm25_label(None)
        assert label == "No data"
        assert colour == "#888"

    @pytest.mark.parametrize("value, expected_label", [
        (0,     "Good"),
        (6.0,   "Good"),
        (11.9,  "Good"),
        (12.0,  "Moderate"),
        (20.0,  "Moderate"),
        (35.4,  "Unhealthy (Sensitive)"),
        (50.0,  "Unhealthy (Sensitive)"),
        (55.4,  "Unhealthy"),
        (100.0, "Unhealthy"),
        (150.4, "Very Unhealthy"),
        (200.0, "Very Unhealthy"),
        (250.4, "Hazardous"),
        (999.9, "Hazardous"),
    ])
    def test_aqi_bands(self, value, expected_label):
        label, _ = pm25_label(value)
        assert label == expected_label

    @pytest.mark.parametrize("value, expected_colour", [
        (0,     "#00e400"),
        (12.0,  "#ffff00"),
        (35.4,  "#ff7e00"),
        (55.4,  "#ff0000"),
        (150.4, "#8f3f97"),
        (250.4, "#7e0023"),
    ])
    def test_aqi_colours(self, value, expected_colour):
        _, colour = pm25_label(value)
        assert colour == expected_colour


# ── load_data ──────────────────────────────────────────────────────────────

def _create_db(path: Path, rows: list[dict]) -> None:
    """Helper: create a readings.db at *path* and insert *rows*."""
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pm1_0 REAL, pm2_5 REAL, pm10 REAL,
                temp REAL, humidity REAL, pressure REAL, altitude REAL
            )
        """)
        for row in rows:
            conn.execute(
                "INSERT INTO readings (timestamp, pm1_0, pm2_5, pm10, temp, humidity, pressure, altitude) "
                "VALUES (:timestamp, :pm1_0, :pm2_5, :pm10, :temp, :humidity, :pressure, :altitude)",
                row,
            )


@pytest.fixture
def patch_db_path(tmp_path, monkeypatch):
    """Redirect dashboard.DB_PATH to a temp directory path."""
    db_file = tmp_path / "readings.db"
    monkeypatch.setattr(dashboard, "DB_PATH", db_file)
    return db_file


class TestLoadData:
    def test_missing_db_returns_empty_dataframe(self, patch_db_path):
        # DB file does not exist yet
        result = load_data()
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_empty_table_returns_empty_dataframe(self, patch_db_path):
        _create_db(patch_db_path, rows=[])
        result = load_data()
        assert result.empty

    def test_returns_dataframe_with_rows(self, patch_db_path):
        rows = [
            {
                "timestamp": "2026-04-22T10:00:00+00:00",
                "pm1_0": 3.0, "pm2_5": 8.0, "pm10": 15.0,
                "temp": 24.5, "humidity": 58.0, "pressure": 1010.0, "altitude": 50.0,
            },
            {
                "timestamp": "2026-04-22T10:15:00+00:00",
                "pm1_0": 4.0, "pm2_5": 9.0, "pm10": 17.0,
                "temp": 25.0, "humidity": 57.0, "pressure": 1011.0, "altitude": 51.0,
            },
        ]
        _create_db(patch_db_path, rows)
        result = load_data()

        assert len(result) == 2
        assert {"timestamp", "pm1_0", "pm2_5", "pm10",
                "temp", "humidity", "pressure", "altitude"}.issubset(result.columns)

    def test_timestamp_column_is_datetime(self, patch_db_path):
        rows = [{
            "timestamp": "2026-04-22T10:00:00+00:00",
            "pm1_0": 1.0, "pm2_5": 2.0, "pm10": 3.0,
            "temp": 20.0, "humidity": 50.0, "pressure": 1000.0, "altitude": 0.0,
        }]
        _create_db(patch_db_path, rows)
        result = load_data()

        assert pd.api.types.is_datetime64_any_dtype(result["timestamp"])

    def test_rows_sorted_ascending_by_timestamp(self, patch_db_path):
        rows = [
            {
                "timestamp": "2026-04-22T10:30:00+00:00",
                "pm1_0": 2.0, "pm2_5": 4.0, "pm10": 8.0,
                "temp": 22.0, "humidity": 52.0, "pressure": 1005.0, "altitude": 10.0,
            },
            {
                "timestamp": "2026-04-22T10:00:00+00:00",
                "pm1_0": 1.0, "pm2_5": 2.0, "pm10": 4.0,
                "temp": 21.0, "humidity": 51.0, "pressure": 1004.0, "altitude": 9.0,
            },
        ]
        _create_db(patch_db_path, rows)
        result = load_data()

        timestamps = result["timestamp"].tolist()
        assert timestamps == sorted(timestamps)

    def test_respects_limit_parameter(self, patch_db_path):
        rows = [
            {
                "timestamp": f"2026-04-22T{h:02d}:00:00+00:00",
                "pm1_0": 1.0, "pm2_5": 2.0, "pm10": 3.0,
                "temp": 20.0, "humidity": 50.0, "pressure": 1000.0, "altitude": 0.0,
            }
            for h in range(10)
        ]
        _create_db(patch_db_path, rows)
        result = load_data(limit=5)

        assert len(result) == 5
