"""Tests of the diagnostics download."""

from custom_components.ble_early_att.diagnostics import (
    async_get_config_entry_diagnostics,
)
from tests.common import wait_until
from tests.hci import ADAPTER_ADDRESS, connection_complete, mtu_request, new_index


async def test_diagnostics_show_the_counts_without_addresses(
    hass, loaded_entry, feed_monitor, sent_packets
):
    """The download names each adapter by its index and never by its address."""
    feed_monitor(new_index(), mtu_request(), connection_complete())
    await wait_until(lambda: sent_packets)

    diagnostics = await async_get_config_entry_diagnostics(hass, loaded_entry)

    assert diagnostics["reading"] is True
    [(name, adapter)] = diagnostics["adapters"].items()
    assert name == "hci1"
    assert adapter["dropped"] == {"att_mtu_request": 1}
    assert adapter["answered"] == 1
    assert adapter["last_answered"] is not None
    assert ADAPTER_ADDRESS not in str(diagnostics)


async def test_diagnostics_before_any_answer(hass, loaded_entry, feed_monitor):
    """An adapter without answers has no time of the last answer."""
    feed_monitor(new_index())
    await wait_until(lambda: loaded_entry.runtime_data.watcher.adapters)

    diagnostics = await async_get_config_entry_diagnostics(hass, loaded_entry)

    assert diagnostics["adapters"]["hci1"] == {
        "dropped": {},
        "answered": 0,
        "last_answered": None,
    }
