"""
Tests for SensorData methods in Sensors.py.

Hardware initialisation (_init_pms5003, _init_bme680) is patched out on
every fixture so tests run without a connected sensor or Pi GPIO.
"""

import pytest
import requests as req_lib
from unittest.mock import MagicMock, patch

import Sensors
from Sensors import SensorData


# ── Shared fixture ─────────────────────────────────────────────────────────

@pytest.fixture
def sensor(monkeypatch):
    """
    Return a SensorData instance with both hardware init methods bypassed
    and both sensors replaced by configurable MagicMocks.
    """
    monkeypatch.setenv("API_ENDPOINT", "http://test-api.local")
    monkeypatch.setenv("REQUEST_TIMEOUT", "5")

    with patch.object(SensorData, "_init_pms5003"):
        with patch.object(SensorData, "_init_bme680"):
            sd = SensorData()

    # Provide mock sensors with sensible numeric attribute defaults
    sd.pms5003 = MagicMock()
    sd.bme680 = MagicMock()
    sd.bme680.temperature = 25.0
    sd.bme680.relative_humidity = 60.0
    sd.bme680.pressure = 1013.25
    sd.bme680.altitude = 100.0
    return sd


# ── _get_api_endpoint ──────────────────────────────────────────────────────

class TestGetApiEndpoint:
    def test_missing_env_returns_none(self, monkeypatch):
        monkeypatch.delenv("API_ENDPOINT", raising=False)
        with patch.object(SensorData, "_init_pms5003"):
            with patch.object(SensorData, "_init_bme680"):
                sd = SensorData()
        assert sd.api_endpoint is None

    def test_blank_env_returns_none(self, monkeypatch):
        monkeypatch.setenv("API_ENDPOINT", "   ")
        with patch.object(SensorData, "_init_pms5003"):
            with patch.object(SensorData, "_init_bme680"):
                sd = SensorData()
        assert sd.api_endpoint is None

    def test_trailing_slash_stripped(self, monkeypatch):
        monkeypatch.setenv("API_ENDPOINT", "http://api.local/")
        with patch.object(SensorData, "_init_pms5003"):
            with patch.object(SensorData, "_init_bme680"):
                sd = SensorData()
        assert sd.api_endpoint == "http://api.local"

    def test_valid_endpoint_preserved(self, monkeypatch):
        monkeypatch.setenv("API_ENDPOINT", "https://api.example.com")
        with patch.object(SensorData, "_init_pms5003"):
            with patch.object(SensorData, "_init_bme680"):
                sd = SensorData()
        assert sd.api_endpoint == "https://api.example.com"


# ── readPms ────────────────────────────────────────────────────────────────

class TestReadPms:
    def test_returns_none_when_sensor_not_initialised(self, sensor):
        sensor.pms5003 = None
        assert sensor.readPms() is None

    def test_returns_dict_with_expected_keys(self, sensor):
        mock_reading = MagicMock()
        mock_reading.pm_ug_per_m3.side_effect = lambda x: {1.0: 5, 2.5: 12, 10: 25}[x]
        sensor.pms5003.read.return_value = mock_reading

        result = sensor.readPms()

        assert result is not None
        assert set(result.keys()) == {"PM1_0", "PM2_5", "PM10"}
        assert result["PM1_0"] == 5
        assert result["PM2_5"] == 12
        assert result["PM10"] == 25

    def test_returns_none_on_sensor_exception(self, sensor):
        sensor.pms5003.read.side_effect = RuntimeError("serial timeout")
        assert sensor.readPms() is None


# ── sendPms ────────────────────────────────────────────────────────────────

class TestSendPms:
    VALID_DATA = {"PM1_0": 5.0, "PM2_5": 12.0, "PM10": 25.0}

    def test_returns_none_when_no_endpoint(self, sensor):
        sensor.api_endpoint = None
        assert sensor.sendPms(self.VALID_DATA) is None

    def test_returns_none_for_none_data(self, sensor):
        assert sensor.sendPms(None) is None

    def test_returns_none_for_incomplete_data(self, sensor):
        assert sensor.sendPms({"PM1_0": 1.0}) is None

    def test_posts_to_correct_endpoint(self, sensor):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("Sensors.requests.post", return_value=mock_response) as mock_post:
            sensor.sendPms(self.VALID_DATA)
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert call_kwargs.kwargs["url"] == "http://test-api.local/pms5003"

    def test_passes_timeout(self, sensor):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("Sensors.requests.post", return_value=mock_response) as mock_post:
            sensor.sendPms(self.VALID_DATA)
            assert mock_post.call_args.kwargs["timeout"] == sensor.request_timeout

    def test_returns_status_code_on_success(self, sensor):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("Sensors.requests.post", return_value=mock_response):
            assert sensor.sendPms(self.VALID_DATA) == 200

    def test_returns_status_code_on_non_200(self, sensor):
        mock_response = MagicMock()
        mock_response.status_code = 503
        with patch("Sensors.requests.post", return_value=mock_response):
            assert sensor.sendPms(self.VALID_DATA) == 503

    def test_returns_none_on_network_error(self, sensor):
        with patch("Sensors.requests.post", side_effect=req_lib.RequestException("timeout")):
            assert sensor.sendPms(self.VALID_DATA) is None


# ── readBme ────────────────────────────────────────────────────────────────

class TestReadBme:
    def test_returns_none_when_sensor_not_initialised(self, sensor):
        sensor.bme680 = None
        assert sensor.readBme() is None

    def test_returns_dict_with_expected_keys(self, sensor):
        with patch("Sensors.time.sleep"):
            result = sensor.readBme(num_readings=1, delay=0)

        assert result is not None
        assert set(result.keys()) == {"Temperature", "Humidity", "Pressure", "Altitude"}

    def test_values_are_formatted_strings(self, sensor):
        with patch("Sensors.time.sleep"):
            result = sensor.readBme(num_readings=1, delay=0)

        assert result["Temperature"] == "25.0"
        assert result["Humidity"] == "60.0"
        assert result["Pressure"] == "1013.250"
        assert result["Altitude"] == "100.00"

    def test_averages_multiple_readings(self, sensor):
        """Verify the loop accumulates and divides, not just keeps the last value."""
        readings = [20.0, 30.0]
        sensor.bme680.temperature = 0.0  # will be overridden by side_effect
        sensor.bme680.relative_humidity = 0.0
        sensor.bme680.pressure = 0.0
        sensor.bme680.altitude = 0.0

        call_count = {"n": 0}

        class _CyclingBme:
            """Mimics a bme680 whose readings alternate between two values."""
            def __init__(self):
                self._i = 0

            @property
            def temperature(self):
                val = readings[self._i % len(readings)]
                self._i += 1
                return val

            @property
            def relative_humidity(self): return 50.0
            @property
            def pressure(self): return 1000.0
            @property
            def altitude(self): return 0.0

        sensor.bme680 = _CyclingBme()

        with patch("Sensors.time.sleep"):
            result = sensor.readBme(num_readings=2, delay=0)

        assert result["Temperature"] == "25.0"  # (20+30)/2

    def test_num_readings_clamped_to_one(self, sensor):
        """num_readings < 1 must not raise and must return a valid dict."""
        with patch("Sensors.time.sleep"):
            result = sensor.readBme(num_readings=0, delay=0)
        assert result is not None

    def test_sleep_not_called_after_last_reading(self, sensor):
        """time.sleep should be called num_readings-1 times."""
        with patch("Sensors.time.sleep") as mock_sleep:
            sensor.readBme(num_readings=3, delay=2)
        assert mock_sleep.call_count == 2

    def test_returns_none_on_sensor_exception(self, sensor):
        sensor.bme680.temperature = property(lambda self: (_ for _ in ()).throw(OSError("i2c error")))
        # Simpler: just make the attribute access raise via side_effect on a mock
        bad_bme = MagicMock()
        type(bad_bme).temperature = property(lambda s: 1 / 0)
        sensor.bme680 = bad_bme
        with patch("Sensors.time.sleep"):
            assert sensor.readBme(num_readings=1, delay=0) is None


# ── sendBme ────────────────────────────────────────────────────────────────

class TestSendBme:
    VALID_DATA = {
        "Temperature": "25.0",
        "Humidity": "60.0",
        "Pressure": "1013.250",
        "Altitude": "100.00",
    }

    def test_returns_none_when_no_endpoint(self, sensor):
        sensor.api_endpoint = None
        assert sensor.sendBme(self.VALID_DATA) is None

    def test_returns_none_for_none_data(self, sensor):
        assert sensor.sendBme(None) is None

    def test_returns_none_for_incomplete_data(self, sensor):
        assert sensor.sendBme({"Temperature": "25.0"}) is None

    def test_posts_to_correct_endpoint(self, sensor):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("Sensors.requests.post", return_value=mock_response) as mock_post:
            sensor.sendBme(self.VALID_DATA)
            assert mock_post.call_args.kwargs["url"] == "http://test-api.local/bme680"

    def test_returns_status_code_on_success(self, sensor):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("Sensors.requests.post", return_value=mock_response):
            assert sensor.sendBme(self.VALID_DATA) == 200

    def test_returns_status_code_on_non_200(self, sensor):
        mock_response = MagicMock()
        mock_response.status_code = 429
        with patch("Sensors.requests.post", return_value=mock_response):
            assert sensor.sendBme(self.VALID_DATA) == 429

    def test_returns_none_on_network_error(self, sensor):
        with patch("Sensors.requests.post", side_effect=req_lib.RequestException("conn refused")):
            assert sensor.sendBme(self.VALID_DATA) is None
