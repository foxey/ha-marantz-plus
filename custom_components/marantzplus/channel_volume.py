"""Channel volume management for Marantz+ integration.

This module provides the ChannelVolumeManager class for managing individual
speaker channel volume controls through Home Assistant number entities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant

from .const import CHANNEL_MAP

if TYPE_CHECKING:
    from denonavr import DenonAVR

_LOGGER = logging.getLogger(__name__)


class ChannelVolumeManager:
    """Manages channel volume entities and communication with the receiver.
    
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
    ) -> None:
        """Initialize the channel volume manager.
        
        Args:
            receiver: DenonAVR instance for communication with the receiver
            zone: Zone name (Main, Zone2, or Zone3)
            hass: Home Assistant instance
        """
        self.receiver = receiver
        self.zone = zone
        self.hass = hass
        
        # Initialize pending counters for all channels to 0
        # Tracks expected CV events to prevent feedback loops
        self.pending_counters: dict[str, int] = {
            channel: 0 for channel in CHANNEL_MAP
        }
        
        # Initialize channel volumes for state tracking
        # None indicates value not yet received from receiver
        self.channel_volumes: dict[str, float | None] = {
            channel: None for channel in CHANNEL_MAP
        }
        
        # Store entity references for updates
        # Populated during async_setup
        self.entities: dict[str, object] = {}

    async def async_send_cv_command(
        self,
        channel: str,
        value: float,
    ) -> None:
        """Send a channel volume command to the receiver.
        
        Args:
            channel: Channel code (FL, FR, C, SL, SR, SW)
            value: Volume in dB (-12.0 to +12.0)
        """
        import asyncio
        from .const import ZONE_PREFIXES, CV_TELNET_TIMEOUT, CV_TELNET_PORT
        
        # Increment pending counter before sending
        self.pending_counters[channel] += 1
        
        # Format CV command with zone prefix
        zone_prefix = ZONE_PREFIXES.get(self.zone, "")
        protocol_value = db_to_protocol(value)
        command = f"{zone_prefix}CV{channel} {protocol_value}\r"
        
        reader = None
        writer = None
        try:
            # Create short-lived telnet connection using asyncio streams
            reader, writer = await asyncio.wait_for(
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
            
        except (asyncio.TimeoutError, OSError, ConnectionError) as err:
            _LOGGER.error(
                "Failed to send CV command to %s for channel %s: %s",
                self.receiver.host,
                channel,
                err,
            )
            # Decrement counter on error
            self.pending_counters[channel] -= 1
            
        finally:
            # Close connection if it was established
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    def _cv_callback(
        self,
        zone: str,
        event: str,
        parameter: str,
    ) -> None:
        """Handle CV events from the persistent telnet connection.
        
        Args:
            zone: Zone identifier (Main, Zone2, Zone3, or ALL_ZONES)
            event: Event type (should be "CV")
            parameter: Event parameter (e.g., "FL 50")
        """
        from .const import CHANNEL_MAP
        
        # Validate this is for our zone
        if zone != self.zone and zone != "ALL_ZONES":
            return
        
        # Ignore telnet protocol messages
        if parameter.strip() in ("END", ""):
            return
        
        # Parse CV event parameter: "FL 50" or "FR 535"
        try:
            parts = parameter.strip().split()
            if len(parts) != 2:
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

    async def _get_supported_channels(self) -> list[str]:
        """Query receiver for supported channels.
        
        Returns:
            List of supported channel codes (FL, FR, C, SL, SR, SW)
        """
        from .const import CHANNEL_MAP
        
        # For now, return all standard channels as fallback
        # In the future, we could query the receiver to determine
        # which channels are actually supported
        _LOGGER.debug(
            "Using all standard channels for %s zone %s",
            self.receiver.host,
            self.zone,
        )
        return list(CHANNEL_MAP.keys())

    async def async_setup(
        self,
        device_info: dict,
        unique_id_base: str,
    ) -> list:
        """Set up channel volume entities.
        
        Args:
            device_info: Device information for entity registration
            unique_id_base: Base unique ID for entity generation
            
        Returns:
            List of ChannelVolumeNumber entities to add to Home Assistant
        """
        from .const import CHANNEL_MAP
        
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
            )
            entities.append(entity)
            self.entities[channel] = entity
        
        # Register CV callback with receiver's telnet callback system
        try:
            if hasattr(self.receiver, "register_callback"):
                self.receiver.register_callback("CV", self._cv_callback)
                _LOGGER.debug(
                    "Registered CV callback for %s zone %s",
                    self.receiver.host,
                    self.zone,
                )
        except Exception as err:
            _LOGGER.warning(
                "Failed to register CV callback for %s zone %s: %s",
                self.receiver.host,
                self.zone,
                err,
            )
        
        return entities


def protocol_to_db(protocol_value: str, offset: int = 50) -> float:
    """Convert protocol value to dB.
    
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
    protocol_value = protocol_value.strip()
    raw = int(protocol_value)
    if len(protocol_value) == 3:
        # 3-digit: half dB step
        return raw / 10 - offset
    # 2-digit: whole dB step
    return float(raw - offset)


def db_to_protocol(db_value: float, offset: int = 50) -> str:
    """Convert dB to protocol value.
    
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
    """Home Assistant number entity for individual channel volume control.
    
    Represents a single channel's volume as a number entity with proper
    bounds, step size, and unit of measurement.
    """

    def __init__(
        self,
        manager: ChannelVolumeManager,
        channel: str,
        zone: str,
        device_info: dict,
        unique_id_base: str,
    ) -> None:
        """Initialize the channel volume number entity.
        
        Args:
            manager: ChannelVolumeManager instance for command sending
            channel: Channel code (FL, FR, C, SL, SR, SW)
            zone: Zone name (Main, Zone2, or Zone3)
            device_info: Device information for entity registration
            unique_id_base: Base unique ID for entity generation
        """
        super().__init__()
        
        self._manager = manager
        self._channel = channel
        self._zone = zone
        
        # Generate entity name and ID
        channel_name = CHANNEL_MAP[channel].lower().replace(" ", "_")
        zone_suffix = "" if zone == "Main" else f"_{zone.lower()}"
        
        # Entity attributes
        self._attr_name = f"{zone if zone != 'Main' else ''} Channel {CHANNEL_MAP[channel]} Volume".strip()
        self._attr_unique_id = f"{unique_id_base}{zone_suffix}_channel_{channel_name}_volume"
        self._attr_device_info = device_info

    async def async_set_native_value(self, value: float) -> None:
        """Set the channel volume.
        
        Args:
            value: Volume in dB (-12.0 to +12.0)
        """
        try:
            await self._manager.async_send_cv_command(self._channel, value)
        except Exception as err:
            _LOGGER.error(
                "Failed to set channel %s volume to %.1f dB: %s",
                self._channel,
                value,
                err,
            )

    @property
    def native_value(self) -> float | None:
        """Return the current channel volume in dB."""
        return self._manager.channel_volumes.get(self._channel)

    @property
    def native_min_value(self) -> float:
        """Return minimum volume (-12.0 dB)."""
        from .const import MIN_CHANNEL_VOLUME_DB
        return MIN_CHANNEL_VOLUME_DB

    @property
    def native_max_value(self) -> float:
        """Return maximum volume (+12.0 dB)."""
        from .const import MAX_CHANNEL_VOLUME_DB
        return MAX_CHANNEL_VOLUME_DB

    @property
    def native_step(self) -> float:
        """Return volume step size (0.5 dB)."""
        from .const import CHANNEL_VOLUME_STEP_DB
        return CHANNEL_VOLUME_STEP_DB

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of measurement (dB)."""
        return "dB"
