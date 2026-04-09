"""Shared fixtures for ha-marantz-plus tests."""

from unittest.mock import MagicMock

import pytest

from custom_components.marantzplus.channel_volume import (
    ChannelVolumeManager,
    ChannelVolumeNumber,
)
from custom_components.marantzplus.const import CHANNEL_MAP

try:
    from denonavr.const import POWER_ON
except ImportError:
    POWER_ON = "ON"


@pytest.fixture
def mock_receiver():
    """Return a mock DenonAVR receiver."""
    receiver = MagicMock()
    receiver.host = "192.168.1.100"
    receiver.power = POWER_ON
    receiver.telnet_connected = True
    receiver.telnet_healthy = True
    return receiver


@pytest.fixture
def manager(mock_receiver):
    """Return a ChannelVolumeManager for the Main zone."""
    return ChannelVolumeManager(
        receiver=mock_receiver,
        zone="Main",
        hass=MagicMock(),
        unique_id_base="test-serial",
    )


@pytest.fixture
def manager_zone2(mock_receiver):
    """Return a ChannelVolumeManager for Zone2."""
    return ChannelVolumeManager(
        receiver=mock_receiver,
        zone="Zone2",
        hass=MagicMock(),
        unique_id_base="test-serial",
    )


@pytest.fixture
def manager_with_entities(manager):
    """Return a manager with mock entities attached."""
    entities = {}
    for channel in CHANNEL_MAP:
        entity = MagicMock()
        entity.async_write_ha_state = MagicMock()
        entity.async_schedule_update_ha_state = MagicMock()
        entities[channel] = entity
    manager.entities = entities
    return manager, entities


@pytest.fixture
def channel_entity(manager):
    """Return a ChannelVolumeNumber entity for the FL channel."""
    return ChannelVolumeNumber(
        manager=manager,
        channel="FL",
        zone="Main",
        device_info={},
        unique_id_base="test-serial",
        device_name="Test Device",
    )
