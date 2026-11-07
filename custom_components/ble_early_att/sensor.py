"""Diagnostic sensors on the device of each local Bluetooth adapter."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr

from .const import BLUETOOTH_DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import EarlyAttConfigEntry
    from .monitor import EarlyAttMonitor
    from .watcher import AdapterStats


@dataclass(frozen=True, kw_only=True)
class EarlyAttSensorDescription(SensorEntityDescription):
    """A count that the watcher keeps for each adapter."""

    value_fn: Callable[[AdapterStats], int]


SENSORS = (
    EarlyAttSensorDescription(
        key="early_packets_dropped",
        translation_key="early_packets_dropped",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda stats: stats.dropped.total(),
    ),
    EarlyAttSensorDescription(
        key="mtu_requests_answered",
        translation_key="mtu_requests_answered",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda stats: stats.answered,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EarlyAttConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors of each adapter that the HCI monitor reports, also later."""
    monitor = entry.runtime_data
    added: set[str] = set()

    @callback
    def add_new_adapters() -> None:
        addresses = {
            stats.address
            for stats in monitor.watcher.adapters.values()
            if stats.address is not None
        } - added
        added.update(addresses)
        async_add_entities(
            EarlyAttSensor(
                monitor, address, description, _adapter_device(hass, address)
            )
            for address in sorted(addresses)
            for description in SENSORS
        )

    add_new_adapters()
    entry.async_on_unload(monitor.add_listener(add_new_adapters))


def _adapter_device(hass: HomeAssistant, address: str) -> dr.DeviceEntry | None:
    # The Bluetooth integration keeps one entry for each adapter, with the address of
    # the adapter as its unique ID, and one device in that entry
    bluetooth_entry = hass.config_entries.async_entry_for_domain_unique_id(
        BLUETOOTH_DOMAIN, address
    )
    if bluetooth_entry is None:
        return None
    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass), bluetooth_entry.entry_id
    )
    return devices[0] if devices else None


class EarlyAttSensor(SensorEntity):
    """A count of one adapter, on the device that the Bluetooth integration made."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        monitor: EarlyAttMonitor,
        address: str,
        description: EarlyAttSensorDescription,
        adapter_device: dr.DeviceEntry | None,
    ) -> None:
        """Keep the address, because the index of an adapter can change."""
        self.entity_description = description
        self._value_fn = description.value_fn
        self._monitor = monitor
        self._address = address
        self._attr_unique_id = f"{address}_{description.key}"
        if adapter_device is not None:
            self.device_entry = adapter_device
        else:
            # The Bluetooth integration does not manage this adapter
            self._attr_device_info = dr.DeviceInfo(
                connections={(dr.CONNECTION_BLUETOOTH, address)},
                name=f"Bluetooth adapter {address}",
            )
        self._update()

    async def async_added_to_hass(self) -> None:
        """Write the state after each change that the monitor reports."""
        self.async_on_remove(self._monitor.add_listener(self._handle_change))

    @callback
    def _handle_change(self) -> None:
        self._update()
        self.async_write_ha_state()

    def _update(self) -> None:
        stats = next(
            (
                stats
                for stats in self._monitor.watcher.adapters.values()
                if stats.address == self._address
            ),
            None,
        )
        self._attr_available = self._monitor.reading and stats is not None
        self._attr_native_value = None if stats is None else self._value_fn(stats)
