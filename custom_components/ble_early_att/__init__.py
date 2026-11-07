"""BLE Early ATT: answer the ATT MTU requests that a USB Bluetooth adapter delivers too early."""

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN
from .monitor import EarlyAttMonitor, open_monitor, send_to_adapter

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.SENSOR]

type EarlyAttConfigEntry = ConfigEntry[EarlyAttMonitor]


async def async_setup_entry(hass: HomeAssistant, entry: EarlyAttConfigEntry) -> bool:
    """Read the HCI monitor of the host while the entry is loaded."""
    try:
        monitor_socket = open_monitor()
    except OSError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="monitor_unavailable",
            translation_placeholders={"error": str(err)},
        ) from err
    entry.runtime_data = EarlyAttMonitor(hass.loop, monitor_socket, send_to_adapter)
    entry.runtime_data.start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EarlyAttConfigEntry) -> bool:
    """Stop the reads of the HCI monitor."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.stop()
    return unloaded
