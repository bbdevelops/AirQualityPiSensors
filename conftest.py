"""
conftest.py — loaded by pytest before any test module is imported.

Stubs out hardware-only packages (Adafruit, pms5003, RPi) and
neutralises the streamlit cache decorator so dashboard.py can be
imported on any machine without a Pi or a running Streamlit server.
"""

import sys
from unittest.mock import MagicMock

# ── Hardware stubs ─────────────────────────────────────────────────────────
# These packages only exist on a Raspberry Pi. Replace them with MagicMocks
# so Sensors.py imports cleanly on a dev machine or CI runner.
_HARDWARE_STUBS = [
    "adafruit_extended_bus",
    "adafruit_bme680",
    "board",
    "busio",
    "RPi",
    "RPi.GPIO",
]
for _mod in _HARDWARE_STUBS:
    sys.modules[_mod] = MagicMock()

# pms5003 needs a real stub so its exception classes can be raised and caught
# correctly in both production code and tests.
class _SerialTimeoutError(RuntimeError):
    pass

class _ReadTimeoutError(RuntimeError):
    pass

_pms5003_stub = MagicMock()
_pms5003_stub.SerialTimeoutError = _SerialTimeoutError
_pms5003_stub.ReadTimeoutError = _ReadTimeoutError
sys.modules["pms5003"] = _pms5003_stub

# ── Streamlit stub ─────────────────────────────────────────────────────────
# Replace st.cache_data with a transparent passthrough so load_data() in
# dashboard.py behaves as a plain function during tests (no caching).
_st = MagicMock()
_st.cache_data = lambda **kw: (lambda fn: fn)
_st.stop = MagicMock()  # no-op in tests; rendering code is guarded inside main()
sys.modules["streamlit"] = _st
