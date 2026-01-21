"""aTick BLE device handler."""

from __future__ import annotations

import array
import asyncio
import dataclasses
import logging
import struct
import time
from contextlib import AsyncExitStack
from textwrap import wrap
from typing import TypedDict

from bleak import AdvertisementData, BleakClient, BLEDevice
from bleak.exc import BleakError

from .const import (ACTIVE_POLL_INTERVAL, BLE_BASE_BACKOFF_DELAY,
                    BLE_CONNECTION_TIMEOUT, BLE_LOCK_TIMEOUT,
                    BLE_MAX_CONNECTION_FAILURES, DEFAULT_PIN_DEVICE,
                    UUID_AG_ATTR_RATIOS, UUID_AG_ATTR_VALUES,
                    UUID_ATTR_MANUFACTURER, UUID_ATTR_MODEL,
                    UUID_ATTR_VERSION_FIRMWARE, UUID_SERVICE_AG, CounterType)

_LOGGER = logging.getLogger(__name__)


class ATickDeviceData(TypedDict, total=False):
    """Typed dictionary for device data."""

    model: str | None
    manufacturer: str | None
    firmware_version: str | None
    counter_a_value: float | None
    counter_b_value: float | None
    counter_a_ratio: float
    counter_b_ratio: float
    counter_a_offset: float
    counter_b_offset: float


@dataclasses.dataclass
class ATickParsedAdvertisementData:
    """Parsed advertisement data from aTick device."""

    counter_a_value: float | None = None
    counter_b_value: float | None = None


class ATickBTDevice:
    """aTick Bluetooth Low Energy device handler."""

    def __init__(
        self, ble_device: BLEDevice, poll_interval: int = ACTIVE_POLL_INTERVAL
    ) -> None:
        """Initialize aTick BLE device.

        Args:
            ble_device: BLE device object
            poll_interval: Active polling interval in seconds (default: 24 hours)
        """
        self._poll_interval = poll_interval
        self._last_active_update = -self._poll_interval
        self._ble_device = ble_device
        self.base_unique_id: str = self._ble_device.address
        self._client: BleakClient | None = None
        self._client_stack = AsyncExitStack()
        self._lock = asyncio.Lock()

        # Exponential backoff state
        self._connection_failures: int = 0
        self._last_connection_failure: float = 0.0

        self.data: ATickDeviceData = {
            "model": None,
            "manufacturer": None,
            "firmware_version": None,
            "counter_a_value": None,
            "counter_b_value": None,
            "counter_a_ratio": 0.01,
            "counter_b_ratio": 0.01,
            "counter_a_offset": 0.0,
            "counter_b_offset": 0.0,
        }

    def active_poll_needed(self, seconds_since_last_poll: float | None) -> bool:
        """Check if active polling is needed based on configured interval."""
        if (
            seconds_since_last_poll is not None
            and seconds_since_last_poll < self._poll_interval
        ):
            return False

        return (time.monotonic() - self._last_active_update) > self._poll_interval

    def update_ble_device(self, ble_device: BLEDevice) -> None:
        """Update the BLE device reference.

        This is needed because BlueZ can invalidate old device references
        when scanning stops and restarts. Updating ensures we always have
        a fresh reference before connecting.

        Args:
            ble_device: Fresh BLEDevice reference from Home Assistant
        """
        self._ble_device = ble_device
        _LOGGER.debug("Updated BLE device reference for %s", ble_device.address)

    async def active_full_update(self) -> None:
        """Perform full active update of device information and ratios."""
        try:
            await self.device_info_update()

            # Update counter ratios (multipliers) from device
            try:
                await self.update_counters_ratio()
                _LOGGER.debug(
                    "Updated ratios: A=%s, B=%s",
                    self.data.get("counter_a_ratio"),
                    self.data.get("counter_b_ratio"),
                )
            except Exception as err:
                _LOGGER.debug("Could not update ratios: %s", err)
        finally:
            await self.stop()

        self._last_active_update = time.monotonic()
        _LOGGER.debug("Active update completed for device %s", self._ble_device.address)

    async def device_info_update(self) -> None:
        """Update device information (model, manufacturer, firmware)."""
        await self.update_model_name()
        await self.update_manufacturer()
        await self.update_firmware_version()
        _LOGGER.debug("Device info updated for %s", self._ble_device.address)

    def parse_advertisement_data(
        self, pin: str | None, adv: AdvertisementData
    ) -> ATickParsedAdvertisementData | None:
        """Parse counter values from BLE advertisement data."""
        if not adv.manufacturer_data:
            return None

        new_values = (0.0, 0.0)

        try:
            new_values = self._parse_adv_values_counters(
                adv.manufacturer_data.get(list(adv.manufacturer_data.keys())[-1]),
                pin or DEFAULT_PIN_DEVICE,
                self._ble_device.address,
            )
        except (IndexError, ValueError, KeyError) as err:
            _LOGGER.debug("Failed to parse advertisement data: %s", err)
        except Exception as err:
            _LOGGER.warning(
                "Unexpected error parsing advertisement data: %s", err, exc_info=True
            )

        return ATickParsedAdvertisementData(
            counter_a_value=new_values[0],
            counter_b_value=new_values[1],
        )

    def is_advertisement_changed(
        self, parsed_advertisement: ATickParsedAdvertisementData
    ) -> bool:
        """Check if advertisement data has changed from current values."""
        a_val = parsed_advertisement.counter_a_value or 0.0
        b_val = parsed_advertisement.counter_b_value or 0.0
        return (a_val + b_val) > 0 and (
            parsed_advertisement.counter_a_value != self.data.get("counter_a_value")
            or parsed_advertisement.counter_b_value != self.data.get("counter_b_value")
        )

    def update_from_advertisement(
        self, parsed_advertisement: ATickParsedAdvertisementData
    ) -> None:
        """Update device data from parsed advertisement."""
        self.data["counter_a_value"] = parsed_advertisement.counter_a_value
        self.data["counter_b_value"] = parsed_advertisement.counter_b_value
        _LOGGER.debug(
            "Updated from advertisement: A=%s, B=%s",
            parsed_advertisement.counter_a_value,
            parsed_advertisement.counter_b_value,
        )

    async def stop(self) -> None:
        """Disconnect from BLE device."""
        if self._client is not None:
            try:
                await self._client.disconnect()
                _LOGGER.debug("Successfully disconnected from device")
            except BleakError as err:
                _LOGGER.debug("BleakError during disconnect: %s", err)
            except Exception as err:
                _LOGGER.warning(
                    "Unexpected error during disconnect: %s", err, exc_info=True
                )

        self._client = None

    async def cleanup(self) -> None:
        """Cleanup all resources including AsyncExitStack."""
        await self.stop()
        await self._client_stack.aclose()

    @property
    def connected(self) -> bool:
        """Check if device is connected."""
        return self._client is not None and self._client.is_connected

    def _check_backoff(self) -> None:
        """Check if we should wait due to connection backoff.

        Raises:
            BleakError: If backoff is active and we should wait.
        """
        if self._connection_failures >= BLE_MAX_CONNECTION_FAILURES:
            time_since_failure = time.monotonic() - self._last_connection_failure
            backoff_delay = BLE_BASE_BACKOFF_DELAY * (
                2 ** min(self._connection_failures, 8)
            )
            if time_since_failure < backoff_delay:
                remaining = backoff_delay - time_since_failure
                raise BleakError(
                    f"Connection backoff active, retry in {remaining:.1f}s "
                    f"(failures: {self._connection_failures})"
                )

    def _reset_backoff(self) -> None:
        """Reset connection backoff state after successful connection."""
        self._connection_failures = 0
        self._last_connection_failure = 0.0

    def _record_failure(self) -> None:
        """Record a connection failure for backoff calculation."""
        self._connection_failures += 1
        self._last_connection_failure = time.monotonic()

    async def get_client(self) -> BleakClient:
        """Get or create BLE client with exponential backoff."""
        self._check_backoff()

        try:
            async with asyncio.timeout(BLE_LOCK_TIMEOUT):
                async with self._lock:
                    if not self.connected:
                        _LOGGER.debug("Connecting to %s", self._ble_device.address)

                        try:
                            self._client = await self._client_stack.enter_async_context(
                                BleakClient(
                                    self._ble_device, timeout=BLE_CONNECTION_TIMEOUT
                                )
                            )
                            self._reset_backoff()
                            _LOGGER.debug("Connected successfully")
                        except asyncio.TimeoutError as exc:
                            self._record_failure()
                            _LOGGER.debug(
                                "Timeout on connect (failures: %d)",
                                self._connection_failures,
                            )
                            raise asyncio.TimeoutError("Timeout on connect") from exc
                        except BleakError as exc:
                            self._record_failure()
                            _LOGGER.debug(
                                "BleakError on connect (failures: %d): %s",
                                self._connection_failures,
                                exc,
                            )
                            raise BleakError(f"Error on connect: {exc}") from exc
                    else:
                        _LOGGER.debug("Connection reused")

        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                f"Lock acquisition timed out after {BLE_LOCK_TIMEOUT}s"
            )

        return self._client  # type: ignore[return-value]

    async def write_gatt(self, uuid: str, data: str) -> None:
        """Write data to GATT characteristic.

        Args:
            uuid: Characteristic UUID
            data: Hex string to write

        Raises:
            ValueError: If data is not valid hex
            BleakError: If write fails
        """
        try:
            data_bytes = bytearray.fromhex(data)
        except ValueError as err:
            _LOGGER.error("Invalid hex data for GATT write: %s", data)
            raise ValueError(f"Invalid hex data: {data}") from err

        client = await self.get_client()
        await client.write_gatt_char(uuid, data_bytes, True)
        _LOGGER.debug("GATT write to %s: %s", uuid, data)

    async def read_gatt(self, uuid: str) -> bytes | None:
        """Read data from GATT characteristic.

        Args:
            uuid: Characteristic UUID

        Returns:
            Read data or None if service/characteristic not found
        """
        client = await self.get_client()

        service = client.services.get_service(UUID_SERVICE_AG)
        if service is None:
            _LOGGER.warning("Service %s not found", UUID_SERVICE_AG)
            return None

        characteristic = service.get_characteristic(uuid)
        if characteristic is None:
            _LOGGER.warning(
                "Characteristic %s not found in service %s", uuid, UUID_SERVICE_AG
            )
            return None

        data = await client.read_gatt_char(characteristic)
        _LOGGER.debug("GATT read from %s: %s", uuid, data)
        return data

    async def update_firmware_version(self) -> None:
        """Read and update firmware version from device."""
        if data := await self.read_gatt(UUID_ATTR_VERSION_FIRMWARE):
            self.data["firmware_version"] = data.decode("utf-8")

    async def update_manufacturer(self) -> None:
        """Read and update manufacturer from device."""
        if data := await self.read_gatt(UUID_ATTR_MANUFACTURER):
            self.data["manufacturer"] = data.decode("utf-8")

    async def update_counters_value(self) -> None:
        """Read and update counter values from device via GATT."""
        if data := await self.read_gatt(UUID_AG_ATTR_VALUES):
            values = array.array("f", data).tolist()
            self.data["counter_a_value"] = self._truncate_float(values[0], 2)
            self.data["counter_b_value"] = self._truncate_float(values[1], 2)

    async def update_counters_ratio(self) -> None:
        """Read and update counter ratios (multipliers) from device."""
        if data := await self.read_gatt(UUID_AG_ATTR_RATIOS):
            values = array.array("f", data).tolist()
            self.data["counter_a_ratio"] = self._truncate_float(values[0], 2)
            self.data["counter_b_ratio"] = self._truncate_float(values[1], 2)

    async def update_model_name(self) -> None:
        """Read and update model name from device."""
        if data := await self.read_gatt(UUID_ATTR_MODEL):
            self.data["model"] = data.decode("utf-8")

    @staticmethod
    def is_encrypted(data: bytes) -> bool:
        """Check if advertisement data is encrypted."""
        if len(data) < 8:
            _LOGGER.debug("Data too short to check encryption: %d bytes", len(data))
            return False
        return (int.from_bytes(data[7:8]) & 16) != 0

    @staticmethod
    def _dec_to_hex(num: int) -> str:
        """Convert decimal to hex string in little-endian format."""
        return num.to_bytes((num.bit_length() + 7) // 8, "little").hex() or "00"

    @staticmethod
    def _truncate_float(n: float, places: int) -> float:
        """Truncate float to specified decimal places."""
        return int(n * (10**places)) / 10**places

    @staticmethod
    def _mid_little_endian(value_hex: str) -> str:
        """Reorder hex bytes in mid-little-endian format."""
        arr = wrap(value_hex, 2)
        return arr[2] + arr[3] + arr[0] + arr[1]

    def _parse_adv_values_counters(
        self, data: bytes | None, key: str, mac: str
    ) -> list[float]:
        """Parse and decrypt counter values from advertisement data.

        Args:
            data: Raw advertisement data bytes
            key: PIN code for decryption
            mac: Device MAC address (format: XX:XX:XX:XX:XX:XX)

        Returns:
            List of two float values [counter_a, counter_b]
        """
        if not data or len(data) < 9:
            _LOGGER.debug(
                "Advertisement data too short: %s bytes", len(data) if data else 0
            )
            return [0.0, 0.0]

        try:
            if self.is_encrypted(data):
                res = ""
                i4 = 0

                # Calculate seed from MAC address
                for i in range(6):
                    i2 = i * 3
                    i4 += int(mac[i2 : i2 + 2], 16)

                # Add PIN to seed
                for i3 in range(4):
                    i4 += (int(key) >> (i3 * 8)) & 255

                i8 = ((i4 ^ 255) + 1) & 255

                # XOR decrypt data
                for i5 in range(1, 9):
                    res += self._dec_to_hex((data[i5] ^ i8) & 255)

                float_values = array.array(
                    "f",
                    bytes.fromhex(
                        self._mid_little_endian(res[0:8])
                        + self._mid_little_endian(res[8:16])
                    ),
                ).tolist()
            else:
                float_values = array.array("f", data[1:9]).tolist()

            return [
                self._truncate_float(float_values[0], 2),
                self._truncate_float(float_values[1], 2),
            ]
        except (IndexError, ValueError, struct.error) as err:
            _LOGGER.error("Failed to parse counter values: %s", err)
            return [0.0, 0.0]
        except Exception as err:
            _LOGGER.exception("Unexpected error parsing counter values: %s", err)
            return [0.0, 0.0]

    @property
    def name(self) -> str | None:
        """Get device name."""
        return self._ble_device.name

    @property
    def model(self) -> str | None:
        """Get device model."""
        return self.data.get("model")

    @property
    def manufacturer(self) -> str | None:
        """Get device manufacturer."""
        return self.data.get("manufacturer")

    @property
    def firmware_version(self) -> str | None:
        """Get device firmware version."""
        return self.data.get("firmware_version")

    @property
    def counter_a_value(self) -> float | None:
        """Get counter A value (raw, without ratio applied)."""
        return self.data.get("counter_a_value")

    @property
    def counter_b_value(self) -> float | None:
        """Get counter B value (raw, without ratio applied)."""
        return self.data.get("counter_b_value")

    def get_counter_value_with_ratio(
        self, counter_type: CounterType | str
    ) -> float | None:
        """Get counter value with ratio (multiplier) and offset applied.

        Args:
            counter_type: CounterType enum or string key (e.g., 'counter_a_value')

        Returns:
            Counter value multiplied by ratio and with offset added, or None if value is None
        """
        if isinstance(counter_type, CounterType):
            value_key = counter_type.value_key
            ratio_key = counter_type.ratio_key
            offset_key = counter_type.offset_key
        else:
            # Legacy string support
            value_key = counter_type
            ratio_key = counter_type.replace("_value", "_ratio")
            offset_key = counter_type.replace("_value", "_offset")

        value = self.data.get(value_key)  # type: ignore[arg-type]
        if value is None:
            return None

        ratio = self.data.get(ratio_key, 1.0)  # type: ignore[arg-type]
        offset = self.data.get(offset_key, 0.0)  # type: ignore[arg-type]

        # Apply ratio and offset, then round to 3 decimal places
        result = (value * ratio) + offset  # type: ignore[operator]
        return round(result, 3)

    async def set_counter_value(
        self, counter_type: CounterType, displayed_value: float
    ) -> None:
        """Set counter value (converting from displayed value to raw).

        Args:
            counter_type: Which counter to set (A or B)
            displayed_value: The displayed value (with ratio and offset applied)
        """
        ratio = self.data.get(counter_type.ratio_key, 1.0)  # type: ignore[arg-type]
        offset = self.data.get(counter_type.offset_key, 0.0)  # type: ignore[arg-type]

        # Convert from displayed value to raw value
        if ratio != 0:
            raw_value = (displayed_value - offset) / ratio  # type: ignore[operator]
        else:
            raw_value = displayed_value - offset  # type: ignore[operator]

        async with self._lock:
            self.data[counter_type.value_key] = raw_value  # type: ignore[literal-required]

        _LOGGER.info(
            "Set %s to %s m³ (raw: %s, ratio: %s, offset: %s)",
            counter_type.value_key,
            displayed_value,
            raw_value,
            ratio,
            offset,
        )
