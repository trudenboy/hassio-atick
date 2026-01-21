# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration for the Deembot aTick BLE water meter device. Supports automatic BLE device discovery, encrypted/unencrypted counter readings, configurable polling, and counter offset calibration.

**Language:** Python 3.11+
**Framework:** Home Assistant custom component
**Min HA Version:** 2024.2.0

## Development Commands

```bash
# Install test dependencies
pip install -r requirements_test.txt

# Run tests
pytest tests/
pytest tests/ --cov=custom_components/deembot_atick --cov-report=term-missing

# Linting (run before committing)
black custom_components/ tests/
isort custom_components/ tests/
flake8 custom_components/ --max-line-length=120 --ignore=E203,W503
```

## Architecture

### Data Flow

```
BLE Advertisement → ATickDataUpdateCoordinator → ATickBTDevice → Sensor Entities
```

### Core Components

- **`const.py`**: Constants and `CounterType` enum. Use `CounterType.A` / `CounterType.B` instead of magic strings.

- **`device.py`**: Core BLE device handling with `ATickDeviceData` TypedDict. Key features:
  - `_parse_adv_values_counters()` - decryption of counter values
  - Exponential backoff on connection failures (`_check_backoff`, `_record_failure`, `_reset_backoff`)
  - `set_counter_value(counter_type, value)` - thread-safe counter updates with lock
  - `cleanup()` - proper resource cleanup including AsyncExitStack

- **`coordinator.py`**: Extends `ActiveBluetoothDataUpdateCoordinator`. Handles BLE events and triggers updates based on `poll_interval`.

- **`config_flow.py`**: User/options/reconfigure flows. Device discovery uses service UUID.

- **`__init__.py`**: Integration setup with proper service lifecycle (register on setup, unload on last entry removal). Uses `_get_counter_context()` helper for service handlers.

- **`sensor.py`**: Counter sensors using `CounterType` enum for keys. RSSI sensor disabled by default.

### Data Model

Device data uses `ATickDeviceData` TypedDict. Raw values stored, ratios/offsets applied on display:
```python
displayed_value = raw_value * ratio + offset
```

Use `CounterType` enum for type-safe counter access:
```python
from .const import CounterType

device.get_counter_value_with_ratio(CounterType.A)
await device.set_counter_value(CounterType.B, 15.0)
```

### Configuration Entry

```python
entry.data = {'address': 'MAC', 'pin': 'PIN', 'device_info': {...}}
entry.options = {'poll_interval': int, 'counter_a_offset': float, 'counter_b_offset': float}
```

## Key Constants

Located in `const.py`:
- BLE Service UUID: `UUID_SERVICE_AG`
- Connection settings: `BLE_CONNECTION_TIMEOUT`, `BLE_LOCK_TIMEOUT`, `BLE_MAX_CONNECTION_FAILURES`, `BLE_BASE_BACKOFF_DELAY`
- Poll interval range: 60-86400 seconds (default 86400)

## Debug Logging

Add to Home Assistant `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.deembot_atick: debug
```
