from enum import Enum

DOMAIN = "deembot_atick"

ACTIVE_POLL_INTERVAL = 60 * 60 * 24
DEFAULT_PIN_DEVICE = "123456"
DEFAULT_COUNTER_RATIO = 1.0

# BLE connection settings
BLE_CONNECTION_TIMEOUT = 15
BLE_LOCK_TIMEOUT = 30
BLE_MAX_CONNECTION_FAILURES = 5
BLE_BASE_BACKOFF_DELAY = 2.0


class CounterType(Enum):
    """Enum for counter types."""

    A = "counter_a"
    B = "counter_b"

    @property
    def value_key(self) -> str:
        """Get the data key for counter value."""
        return f"{self.value}_value"

    @property
    def ratio_key(self) -> str:
        """Get the data key for counter ratio."""
        return f"{self.value}_ratio"

    @property
    def offset_key(self) -> str:
        """Get the data key for counter offset."""
        return f"{self.value}_offset"

    @classmethod
    def from_entity_id(cls, entity_id: str) -> "CounterType | None":
        """Determine counter type from entity ID."""
        if "counter_a" in entity_id:
            return cls.A
        if "counter_b" in entity_id:
            return cls.B
        return None


UUID_SERVICE_AG = "348634B0-EFE4-11E4-B80C-0800200C9A66"

UUID_ATTR_MODEL = "00002A24-0000-1000-8000-00805F9B34FB"
UUID_ATTR_MANUFACTURER = "00002A29-0000-1000-8000-00805F9B34FB"
UUID_ATTR_VERSION_FIRMWARE = "00002A26-0000-1000-8000-00805F9B34FB"

UUID_AG_ATTR_PIN = "348634B2-EFE4-11E4-B80C-0800200C9A66"
UUID_AG_ATTR_OPTIONS = "348634B3-EFE4-11E4-B80C-0800200C9A66"
UUID_AG_ATTR_COMMAND = "348634B5-EFE4-11E4-B80C-0800200C9A66"
UUID_AG_ATTR_COUNTERS = "348634B6-EFE4-11E4-B80C-0800200C9A66"
UUID_AG_ATTR_MODE = "348634B7-EFE4-11E4-B80C-0800200C9A66"
UUID_AG_ATTR_VALUES = "348634B8-EFE4-11E4-B80C-0800200C9A66"
UUID_AG_ATTR_RATIOS = "348634B9-EFE4-11E4-B80C-0800200C9A66"
