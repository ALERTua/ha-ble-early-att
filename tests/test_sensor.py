"""Tests of the diagnostic sensors of each adapter."""

import socket
from unittest.mock import MagicMock

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ble_early_att.const import DOMAIN
from custom_components.ble_early_att.monitor import EarlyAttMonitor
from custom_components.ble_early_att.sensor import SENSORS, EarlyAttSensor
from tests.common import wait_until
from tests.hci import (
    ADAPTER_ADDRESS,
    connection_complete,
    monitor_frame,
    mtu_request,
    new_index,
)


def _entity_id(hass, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{ADAPTER_ADDRESS}_{key}"
    )


def _state(hass, key: str) -> str | None:
    if (entity_id := _entity_id(hass, key)) is None:
        return None
    if (state := hass.states.get(entity_id)) is None:
        return None
    return state.state


async def test_sensors_join_the_device_of_the_adapter(hass, loaded_entry, feed_monitor):
    """The counts appear on the device that the Bluetooth integration made."""
    # The Bluetooth integration keeps one entry for each adapter, keyed by its address
    bluetooth_entry = MockConfigEntry(domain="bluetooth", unique_id=ADAPTER_ADDRESS)
    bluetooth_entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    adapter_device = devices.async_get_or_create(
        config_entry_id=bluetooth_entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, ADAPTER_ADDRESS)},
        name="Realtek Bluetooth Radio",
    )

    feed_monitor(new_index())
    await wait_until(lambda: _state(hass, "mtu_requests_answered") == "0")

    registry = er.async_get(hass)
    for key in ("early_packets_dropped", "mtu_requests_answered"):
        entry = registry.async_get(_entity_id(hass, key))
        assert entry.device_id == adapter_device.id
        assert entry.entity_category is er.EntityCategory.DIAGNOSTIC
    assert _state(hass, "early_packets_dropped") == "0"
    assert (
        hass.states.get(_entity_id(hass, "early_packets_dropped")).name
        == "Realtek Bluetooth Radio Early packets dropped"
    )
    # The integration made no device of its own
    assert dr.async_entries_for_config_entry(devices, loaded_entry.entry_id) == []


async def test_adapter_outside_the_bluetooth_integration_gets_its_own_device(
    hass, loaded_entry, feed_monitor
):
    """An adapter without a Bluetooth entry still shows its counts, under its address."""
    feed_monitor(new_index())
    await wait_until(lambda: _state(hass, "mtu_requests_answered") == "0")

    entry = er.async_get(hass).async_get(_entity_id(hass, "early_packets_dropped"))
    device = dr.async_get(hass).async_get(entry.device_id)
    assert device.name == f"Bluetooth adapter {ADAPTER_ADDRESS}"
    assert device.connections == {(dr.CONNECTION_BLUETOOTH, ADAPTER_ADDRESS)}


async def test_sensors_count_the_dropped_and_the_answered_requests(
    hass, loaded_entry, feed_monitor
):
    """A dropped MTU request counts at once, its answer after the wait."""
    feed_monitor(new_index())
    await wait_until(lambda: _state(hass, "early_packets_dropped") == "0")

    feed_monitor(mtu_request(), connection_complete())

    await wait_until(lambda: _state(hass, "early_packets_dropped") == "1")
    await wait_until(lambda: _state(hass, "mtu_requests_answered") == "1")


async def test_sensors_of_a_removed_adapter_are_unavailable(
    hass, loaded_entry, feed_monitor
):
    """An adapter that goes away keeps its sensors, without a value."""
    feed_monitor(new_index())
    await wait_until(lambda: _state(hass, "early_packets_dropped") == "0")

    feed_monitor(monitor_frame(1, b""))

    await wait_until(lambda: _state(hass, "early_packets_dropped") == STATE_UNAVAILABLE)
    assert _state(hass, "mtu_requests_answered") == STATE_UNAVAILABLE


async def test_sensors_are_unavailable_when_the_monitor_stops_reading(hass):
    """A monitor that failed to read gives no count, also for a known adapter."""
    hci = EarlyAttMonitor(hass.loop, MagicMock(spec=socket.socket), MagicMock())
    hci.watcher.feed(new_index())

    sensor = EarlyAttSensor(hci, ADAPTER_ADDRESS, SENSORS[0], None)

    assert hci.reading is False
    assert sensor.available is False
    assert sensor.native_value == 0
