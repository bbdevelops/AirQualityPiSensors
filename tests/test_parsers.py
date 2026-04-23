"""
Tests for the three env-parsing helpers in Sensors.py:
  _parse_int_env, _parse_float_env, _parse_i2c_addr
"""

import pytest
import Sensors
from Sensors import _parse_int_env, _parse_float_env, _parse_i2c_addr


class TestParseIntEnv:
    def test_missing_key_returns_default(self, monkeypatch):
        monkeypatch.delenv("MY_INT", raising=False)
        assert _parse_int_env("MY_INT", 42) == 42

    def test_blank_value_returns_default(self, monkeypatch):
        monkeypatch.setenv("MY_INT", "   ")
        assert _parse_int_env("MY_INT", 42) == 42

    def test_valid_decimal(self, monkeypatch):
        monkeypatch.setenv("MY_INT", "27")
        assert _parse_int_env("MY_INT", 0) == 27

    def test_valid_hex(self, monkeypatch):
        monkeypatch.setenv("MY_INT", "0x1B")
        assert _parse_int_env("MY_INT", 0) == 27

    def test_invalid_string_returns_default(self, monkeypatch):
        monkeypatch.setenv("MY_INT", "not-a-number")
        assert _parse_int_env("MY_INT", 99) == 99

    def test_negative_decimal(self, monkeypatch):
        monkeypatch.setenv("MY_INT", "-5")
        assert _parse_int_env("MY_INT", 0) == -5


class TestParseFloatEnv:
    def test_missing_key_returns_default(self, monkeypatch):
        monkeypatch.delenv("MY_FLOAT", raising=False)
        assert _parse_float_env("MY_FLOAT", 1.5) == 1.5

    def test_blank_value_returns_default(self, monkeypatch):
        monkeypatch.setenv("MY_FLOAT", "")
        assert _parse_float_env("MY_FLOAT", 1.5) == 1.5

    def test_valid_integer_string(self, monkeypatch):
        monkeypatch.setenv("MY_FLOAT", "10")
        assert _parse_float_env("MY_FLOAT", 0.0) == 10.0

    def test_valid_float_string(self, monkeypatch):
        monkeypatch.setenv("MY_FLOAT", "1002.25")
        assert _parse_float_env("MY_FLOAT", 0.0) == pytest.approx(1002.25)

    def test_invalid_string_returns_default(self, monkeypatch):
        monkeypatch.setenv("MY_FLOAT", "abc")
        assert _parse_float_env("MY_FLOAT", 3.14) == 3.14


class TestParseI2cAddr:
    def test_none_returns_default(self):
        assert _parse_i2c_addr(None) == 0x77

    def test_blank_returns_default(self):
        assert _parse_i2c_addr("   ") == 0x77

    def test_valid_0x76(self):
        assert _parse_i2c_addr("0x76") == 0x76

    def test_valid_0x77(self):
        assert _parse_i2c_addr("0x77") == 0x77

    def test_valid_decimal_118(self):
        # 118 decimal == 0x76
        assert _parse_i2c_addr("118") == 0x76

    def test_unsupported_address_returns_default(self):
        # 0x78 is not a valid BME680 address
        assert _parse_i2c_addr("0x78") == 0x77

    def test_non_numeric_returns_default(self):
        assert _parse_i2c_addr("bad-addr") == 0x77

    def test_custom_default(self):
        assert _parse_i2c_addr(None, default=0x76) == 0x76
