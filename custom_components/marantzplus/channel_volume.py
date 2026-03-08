"""
Channel volume management for Marantz+ integration.

This module provides the ChannelVolumeManager class for managing individual
speaker channel volume controls through Home Assistant number entities.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from denonavr.const import POWER_ON
from homeassistant.components.number import NumberEntity

from .const import (
    CHANNEL_MAP,
    CHANNEL_VOLUME_STEP_DB,
    CV_TELNET_PORT,
    CV_TELNET_TIMEOUT,
    MAX_CHANNEL_VOLUME_DB,
    MIN_CHANNEL_VOLUME_DB,
    ZONE_PREFIXES,
)

if TYPE_CHECKING:
    from denonavr import DenonAVR
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ChannelVolumeManager:
    """
    Manages channel volume entities and communication with the receiver.

    This class coordinates channel volume functionality by:
    - Creating and managing ChannelVolumeNumber entities
    - Sending CV commands via short-lived telnet connections
    - Receiving CV events via the library's persistent telnet connection
    - Preventing feedback loops using pending counters
    """

    def __init__(
        self,
        receiver: DenonAVR,
        zone: str,
        hass: HomeAssistant,
        unique_id_base: str,
    ) -> None:
        """
        Initialize the channel volume manager.

        Args:
            receiver: DenonAVR instance for communication with the receiver
            zone: Zone name (Main, Zone2, or Zone3)
            hass: Home Assistant instance
            unique_id_base: Base unique ID (not used, kept for compatibility)

        """
        self.receiver = receiver
        self.zone = zone
        self.hass = hass

        # Initialize pending counters for all channels to 0
        # Tracks expected CV events to prevent feedback loops
        self.pending_counters: dict[str, int] = dict.fromkeys(CHANNEL_MAP, 0)

        # Initialize channel volumes for state tracking
        # None indicates value not yet received from receiver
        self.channel_volumes: dict[str, float | None] = dict.fromkeys(CHANNEL_MAP)

        # Store entity references for updates
        # Populated during async_setup
        self.entities: dict[str, object] = {}

        # Track last known power state to detect changes
        self._last_power_state: str | None = None

    @property
    def is_receiver_available(self) -> bool:
        """Return True if the receiver is available (responding to network requests)."""
        # Check if receiver state is not None (None means unavailable/network error)
        return self.receiver.state is not None

    @property
    def is_receiver_powered_on(self) -> bool:
        """Return True if the receiver is powered on."""
        # Check if receiver power is ON
        return self.receiver.power == POWER_ON

    async def async_send_cv_command(
        self,
        channel: str,
        value: float,
    ) -> None:
        """
        Send a channel volume command to the receiver.

        Args:
            channel: Channel code (FL, FR, C, SL, SR, SW)
            value: Volume in dB (-12.0 to +12.0)

        """
        # Increment pending counter before sending
        self.pending_counters[channel] += 1

        # Format CV command with zone prefix
        zone_prefix = ZONE_PREFIXES.get(self.zone, "")
        protocol_value = db_to_protocol(value)
        command = f"{zone_prefix}CV{channel} {protocol_value}\r"

        _reader = None
        writer = None
        try:
            # Create short-lived telnet connection using asyncio streams
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.receiver.host,
                    CV_TELNET_PORT,
                ),
                timeout=CV_TELNET_TIMEOUT,
            )

            # Send CV command
            writer.write(command.encode("ascii"))
            await writer.drain()

            _LOGGER.debug(
                "Sent CV command to %s: %s",
                self.receiver.host,
                command.strip(),
            )

        except (TimeoutError, OSError, ConnectionError):
            _LOGGER.exception(
                "Failed to send CV command to %s for channel %s",
                self.receiver.host,
                channel,
            )
            # Decrement counter on error
            self.pending_counters[channel] -= 1

        finally:
            # Close connection if it was established
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except OSError:
                    _LOGGER.debug("Error closing telnet connection")
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("Unexpected error closing telnet connection")

    def _cv_callback(
        self,
        zone: str,
        event: str,
        parameter: str,
    ) -> None:
        """
        Handle CV events from the persistent telnet connection.

        Args:
            zone: Zone identifier (Main, Zone2, Zone3, or ALL_ZONES)
            event: Event type (should be "CV")
            parameter: Event parameter (e.g., "FL 50")

        """
        # Expected parts count for CV event parameter
        expected_parts = 2

        try:
            # Validate this is for our zone
            if zone not in (self.zone, "ALL_ZONES"):
                return

            # Ignore telnet protocol messages
            if parameter.strip() in ("END", ""):
                return

            # Parse CV event parameter: "FL 50" or "FR 535"
            parts = parameter.strip().split()
            if len(parts) != expected_parts:
                _LOGGER.debug(
                    "Ignoring CV event with unexpected format: %s",
                    parameter,
                )
                return

            channel_code = parts[0]
            protocol_value = parts[1]

            # Validate channel code
            if channel_code not in CHANNEL_MAP:
                _LOGGER.warning(
                    "Unknown channel code in CV event: %s",
                    channel_code,
                )
                return

            # Check pending counter
            if self.pending_counters[channel_code] > 0:
                # Decrement counter and skip entity update (feedback prevention)
                self.pending_counters[channel_code] -= 1
                _LOGGER.debug(
                    "Skipping CV event for %s (pending counter: %d)",
                    channel_code,
                    self.pending_counters[channel_code],
                )
                return

            # Convert protocol value to dB
            db_value = protocol_to_db(protocol_value)

            # Update channel volume state
            self.channel_volumes[channel_code] = db_value

            # Update entity if it exists
            if channel_code in self.entities:
                entity = self.entities[channel_code]
                if hasattr(entity, "async_write_ha_state"):
                    entity.async_write_ha_state()
                    _LOGGER.debug(
                        "Updated %s channel %s to %.1f dB",
                        self.zone,
                        channel_code,
                        db_value,
                    )

        except (ValueError, IndexError) as err:
            _LOGGER.warning(
                "Failed to parse CV event parameter '%s': %s",
                parameter,
                err,
            )
        except Exception:
            _LOGGER.exception(
                "Unexpected error in CV callback for zone %s, event %s, parameter '%s'",
                zone,
                event,
                parameter,
            )

    def _power_callback(
        self,
        zone: str,
        event: str,
        parameter: str,
    ) -> None:
        """
        Handle power state change events.

        Args:
            zone: Zone identifier (Main, Zone2, Zone3, or ALL_ZONES)
            event: Event type (ZM for Main, Z2 for Zone2, Z3 for Zone3)
            parameter: Power state parameter

        """
        try:
            # Validate this is for our zone
            if zone not in (self.zone, "ALL_ZONES"):
                return

            # Check if power state changed
            current_power = self.receiver.power
            if current_power != self._last_power_state:
                _LOGGER.debug(
                    "Power state changed for %s zone %s: %s -> %s",
                    self.receiver.host,
                    self.zone,
                    self._last_power_state,
                    current_power,
                )
                self._last_power_state = current_power

                # Update all channel entities to reflect new availability
                for entity in self.entities.values():
                    if hasattr(entity, "async_write_ha_state"):
                        entity.async_write_ha_state()

        except Exception:
            _LOGGER.exception(
                "Error in power callback: zone=%s event=%s param=%s",
                zone,
                event,
                parameter,
            )

    async def _get_supported_channels(self) -> list[str]:
        """
        Get all standard channels.

        Returns all standard channels. Entity availability will be managed
        dynamically based on whether the receiver actually reports values
        for each channel.

        Returns:
            List of all standard channel codes (FL, FR, C, SL, SR, SW)

        """
        _LOGGER.debug(
            "Creating entities for all standard channels for %s zone %s",
            self.receiver.host,
            self.zone,
        )
        return list(CHANNEL_MAP.keys())

    async def _query_initial_values(self) -> None:  # noqa: PLR0912
        """Query receiver for initial channel values to determine availability."""
        # Expected parts count for CV response
        expected_parts = 2

        # Build CV? query command with zone prefix
        zone_prefix = ZONE_PREFIXES.get(self.zone, "")
        query_command = f"{zone_prefix}CV?\r"

        _reader = None
        writer = None
        try:
            # Create short-lived telnet connection
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.receiver.host,
                    CV_TELNET_PORT,
                ),
                timeout=CV_TELNET_TIMEOUT,
            )

            # Send CV? query
            writer.write(query_command.encode("ascii"))
            await writer.drain()

            # Read response with timeout
            response_data = await asyncio.wait_for(
                _reader.read(4096),
                timeout=CV_TELNET_TIMEOUT,
            )
            response = response_data.decode("ascii", errors="replace")

            # Parse response and update channel values
            # Response format: "CVFL 50\rCVFR 50\rCVC 48\r"
            for raw_line in response.split("\r"):
                parsed_line = raw_line.strip()
                if not parsed_line:
                    continue

                # Remove zone prefix if present
                if parsed_line.startswith(zone_prefix + "CV"):
                    # Remove zone prefix and "CV"
                    parsed_line = parsed_line[len(zone_prefix) + 2 :]
                elif parsed_line.startswith("CV"):
                    parsed_line = parsed_line[2:]  # Remove "CV"
                else:
                    continue

                # Parse "FL 50" or "FR 535"
                parts = parsed_line.split()
                if len(parts) >= expected_parts:
                    channel_code = parts[0]
                    protocol_value = parts[1]

                    if channel_code in self.channel_volumes:
                        try:
                            db_value = protocol_to_db(protocol_value)
                            self.channel_volumes[channel_code] = db_value
                            _LOGGER.debug(
                                "Initial value for %s channel %s: %.1f dB",
                                self.zone,
                                channel_code,
                                db_value,
                            )
                        except (ValueError, IndexError) as err:
                            _LOGGER.warning(
                                "Failed to parse initial CV value '%s' for "
                                "channel %s: %s",
                                protocol_value,
                                channel_code,
                                err,
                            )

            # Log which channels are available
            available_channels = [
                ch for ch, val in self.channel_volumes.items() if val is not None
            ]
            if available_channels:
                _LOGGER.info(
                    "Active channels for %s zone %s: %s",
                    self.receiver.host,
                    self.zone,
                    ", ".join(available_channels),
                )
            else:
                _LOGGER.warning(
                    "No active channels detected for %s zone %s",
                    self.receiver.host,
                    self.zone,
                )

        except (TimeoutError, OSError, ConnectionError) as err:
            _LOGGER.warning(
                "Failed to query initial channel values for %s zone %s: %s",
                self.receiver.host,
                self.zone,
                err,
            )

        finally:
            # Close connection if it was established
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except OSError:
                    _LOGGER.debug("Error closing telnet connection")
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("Unexpected error closing telnet connection")

    async def async_setup(
        self,
        device_info: dict,
        unique_id_base: str,
        device_name: str,
    ) -> list:
        """
        Set up channel volume entities.

        Args:
            device_info: Device information for entity registration
            unique_id_base: Base unique ID for entity generation
            device_name: Device name for entity naming

        Returns:
            List of ChannelVolumeNumber entities to add to Home Assistant

        """
        # Get supported channels
        supported_channels = await self._get_supported_channels()

        # Create entities for each supported channel
        entities = []
        for channel in supported_channels:
            entity = ChannelVolumeNumber(
                manager=self,
                channel=channel,
                zone=self.zone,
                device_info=device_info,
                unique_id_base=unique_id_base,
                device_name=device_name,
            )
            entities.append(entity)
            self.entities[channel] = entity

        return entities

    async def async_initialize(self) -> None:
        """
        Initialize channel volume manager after entities are added to HA.

        This must be called after entities are added to Home Assistant to ensure
        the hass attribute is set before any callbacks are triggered.
        """
        # Register CV callback with receiver's telnet callback system
        try:
            if hasattr(self.receiver, "register_callback"):
                self.receiver.register_callback("CV", self._cv_callback)
                _LOGGER.debug(
                    "Registered CV callback for %s zone %s",
                    self.receiver.host,
                    self.zone,
                )
        except Exception:
            _LOGGER.exception(
                "Failed to register CV callback for %s zone %s",
                self.receiver.host,
                self.zone,
            )

        # Register power state callback
        try:
            if hasattr(self.receiver, "register_callback"):
                # Register for zone-specific power events
                if self.zone == "Main":
                    power_event = "ZM"
                elif self.zone == "Zone2":
                    power_event = "Z2"
                elif self.zone == "Zone3":
                    power_event = "Z3"
                else:
                    power_event = "ZM"  # Default to main zone

                self.receiver.register_callback(power_event, self._power_callback)
                _LOGGER.debug(
                    "Registered power callback (%s) for %s zone %s",
                    power_event,
                    self.receiver.host,
                    self.zone,
                )

                # Initialize last power state
                self._last_power_state = self.receiver.power
        except Exception:
            _LOGGER.exception(
                "Failed to register power callback for %s zone %s",
                self.receiver.host,
                self.zone,
            )

        # Query initial channel values to determine availability
        await self._query_initial_values()


def protocol_to_db(protocol_value: str, offset: int = 50) -> float:
    """
    Convert protocol value to dB.

    Args:
        protocol_value: String from receiver (2-digit or 3-digit)
        offset: Protocol offset (default 50, so 50 = 0.0 dB)

    Returns:
        Volume in dB

    Examples:
        "53" → +3.0 dB (53 - 50)
        "535" → +3.5 dB (535 / 10 - 50)
        "50" → 0.0 dB
        "38" → -12.0 dB

    """
    # Length for 3-digit half-dB step values
    half_db_length = 3

    protocol_value = protocol_value.strip()
    raw = int(protocol_value)
    if len(protocol_value) == half_db_length:
        # 3-digit: half dB step
        return raw / 10 - offset
    # 2-digit: whole dB step
    return float(raw - offset)


def db_to_protocol(db_value: float, offset: int = 50) -> str:
    """
    Convert dB to protocol value.

    Args:
        db_value: Volume in dB (-12.0 to +12.0)
        offset: Protocol offset (default 50, so 0.0 dB = 50)

    Returns:
        Protocol string (2-digit for whole dB, 3-digit for half dB)

    Examples:
        +3.0 → "53" (whole dB)
        +3.5 → "535" (half dB)
        0.0 → "50"
        -12.0 → "38"

    """
    if db_value % 1 == 0:
        # Whole dB: 2-digit string
        return str(int(db_value) + offset)
    # Half dB: 3-digit string
    return str(int((db_value + offset) * 10))


class ChannelVolumeNumber(NumberEntity):
    """
    Home Assistant number entity for individual channel volume control.

    Represents a single channel's volume as a number entity with proper
    bounds, step size, and unit of measurement.
    """

    # Enable periodic updates
    _attr_should_poll = True

    def __init__(  # noqa: PLR0913
        self,
        manager: ChannelVolumeManager,
        channel: str,
        zone: str,
        device_info: dict,
        *,
        unique_id_base: str,
        device_name: str,
    ) -> None:
        """
        Initialize the channel volume number entity.

        Args:
            manager: ChannelVolumeManager instance for command sending
            channel: Channel code (FL, FR, C, SL, SR, SW)
            zone: Zone name (Main, Zone2, or Zone3)
            device_info: Device information for entity registration
            unique_id_base: Base unique ID for entity generation
            device_name: Device name for entity naming

        """
        super().__init__()

        self._manager = manager
        self._channel = channel
        self._zone = zone

        # Generate entity name and ID
        channel_name = CHANNEL_MAP[channel].lower().replace(" ", "_")

        # Build entity name with device and zone context
        if zone == "Main":
            # Main zone: "Device Front Left Volume"
            self._attr_name = f"{device_name} {CHANNEL_MAP[channel]} Volume"
        else:
            # Other zones: "Device Zone2 Front Left Volume"
            self._attr_name = f"{device_name} {zone} {CHANNEL_MAP[channel]} Volume"

        # Build unique_id
        zone_suffix = "" if zone == "Main" else f"_{zone.lower()}"
        self._attr_unique_id = f"{unique_id_base}{zone_suffix}_{channel_name}_volume"
        self._attr_device_info = device_info

        # Set icon based on channel type
        if channel == "SW":
            self._attr_icon = "mdi:smoke-detector"
        else:
            self._attr_icon = "mdi:speaker"

    async def async_set_native_value(self, value: float) -> None:
        """
        Set the channel volume.

        Args:
            value: Volume in dB (-12.0 to +12.0)

        """
        try:
            await self._manager.async_send_cv_command(self._channel, value)
        except Exception:
            _LOGGER.exception(
                "Failed to set channel %s volume to %.1f dB",
                self._channel,
                value,
            )

    async def async_update(self) -> None:
        """
        Update entity state.

        This is called periodically by Home Assistant. We use it to check
        if the receiver availability has changed and trigger a state update.
        """
        # The availability property will be re-evaluated when this completes
        # No need to do anything here - just having this method enables polling

    @property
    def native_value(self) -> float | None:
        """Return the current channel volume in dB."""
        return self._manager.channel_volumes.get(self._channel)

    @property
    def available(self) -> bool:
        """
        Return True if entity is available.

        A channel is considered available if:
        1. The receiver is available (responding to network requests)
        2. The receiver is powered on
        3. We've received at least one CV event for it from the receiver
        """
        return (
            self._manager.is_receiver_available
            and self._manager.is_receiver_powered_on
            and self._manager.channel_volumes.get(self._channel) is not None
        )

    @property
    def native_min_value(self) -> float:
        """Return minimum volume (-12.0 dB)."""
        return MIN_CHANNEL_VOLUME_DB

    @property
    def native_max_value(self) -> float:
        """Return maximum volume (+12.0 dB)."""
        return MAX_CHANNEL_VOLUME_DB

    @property
    def native_step(self) -> float:
        """Return volume step size (0.5 dB)."""
        return CHANNEL_VOLUME_STEP_DB

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of measurement (dB)."""
        return "dB"
