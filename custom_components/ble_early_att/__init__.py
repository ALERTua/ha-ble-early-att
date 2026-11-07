"""BLE Early ATT: answer the ATT MTU requests that a USB Bluetooth adapter delivers too early."""

from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryError

from .monitor import EarlyAttMonitor, open_monitor, send_to_adapter

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

type EarlyAttConfigEntry = ConfigEntry[EarlyAttMonitor]


async def async_setup_entry(hass: HomeAssistant, entry: EarlyAttConfigEntry) -> bool:
    """Read the HCI monitor of the host while the entry is loaded."""
    try:
        monitor_socket = open_monitor()
    except OSError as err:
        msg = f"Cannot open the HCI monitor: {err}"
        raise ConfigEntryError(msg) from err
    entry.runtime_data = EarlyAttMonitor(hass.loop, monitor_socket, send_to_adapter)
    entry.runtime_data.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EarlyAttConfigEntry) -> bool:
    """Stop the reads of the HCI monitor."""
    entry.runtime_data.stop()
    return True
