"""Tests of the setup and the unload of the integration."""

import errno
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ble_early_att.const import DOMAIN
from custom_components.ble_early_att.monitor import EarlyAttMonitor
from tests.common import wait_until
from tests.hci import ADAPTER, connection_complete, mtu_request


async def test_loaded_entry_answers_and_unload_closes_the_monitor(
    hass, enable_custom_integrations, monitor_pair
):
    """The entry reads the monitor while it is loaded and closes it at unload."""
    reader, writer = monitor_pair
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    sent: list[tuple[int, bytes]] = []

    with (
        patch("custom_components.ble_early_att.open_monitor", return_value=reader),
        patch(
            "custom_components.ble_early_att.send_to_adapter",
            side_effect=lambda adapter, packet: sent.append((adapter, packet)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        writer.send(mtu_request())
        writer.send(connection_complete())
        await wait_until(lambda: sent)

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, EarlyAttMonitor)
    assert [adapter for adapter, _ in sent] == [ADAPTER]

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert reader.fileno() == -1


async def test_entry_without_the_monitor_fails_with_the_reason(
    hass, enable_custom_integrations, caplog
):
    """Without Linux or CAP_NET_RAW the entry shows a setup error with the cause."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ble_early_att.open_monitor",
        side_effect=PermissionError(errno.EPERM, "Operation not permitted"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert "Operation not permitted" in caplog.text
