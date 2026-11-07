"""Pytest configuration and fixtures."""

import socket
from collections.abc import AsyncIterator, Callable, Iterator
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ble_early_att.const import DOMAIN


@pytest.fixture
def monitor_pair(socket_enabled: None) -> Iterator[tuple[socket.socket, socket.socket]]:
    """Give a datagram socket in place of the HCI monitor, and a socket that feeds it."""
    reader = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    reader.bind(("127.0.0.1", 0))
    reader.setblocking(False)
    writer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    writer.connect(reader.getsockname())
    yield reader, writer
    reader.close()
    writer.close()


@pytest.fixture
def sent_packets() -> list[tuple[int, bytes]]:
    """Collect the packets that the loaded entry sends to the adapters."""
    return []


@pytest.fixture
async def loaded_entry(
    hass, enable_custom_integrations, monitor_pair, sent_packets
) -> AsyncIterator[MockConfigEntry]:
    """Load the entry on the fake monitor, and record its sends."""
    reader, _writer = monitor_pair
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    def send(adapter: int, packet: bytes) -> None:
        sent_packets.append((adapter, packet))

    with (
        patch("custom_components.ble_early_att.open_monitor", return_value=reader),
        patch("custom_components.ble_early_att.send_to_adapter", side_effect=send),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry
        if entry.state is ConfigEntryState.LOADED:
            assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.fixture
def feed_monitor(monitor_pair) -> Callable[..., None]:
    """Send frames to the fake monitor of the loaded entry."""
    _reader, writer = monitor_pair

    def feed(*frames: bytes) -> None:
        for frame in frames:
            writer.send(frame)

    return feed
