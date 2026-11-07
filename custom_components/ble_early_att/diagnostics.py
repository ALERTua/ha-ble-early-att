"""Diagnostics of BLE Early ATT: the counts of each adapter, without addresses."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import EarlyAttConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: EarlyAttConfigEntry,
) -> dict[str, Any]:
    """Return the state of the monitor and the counts of each adapter."""
    monitor = entry.runtime_data
    return {
        "reading": monitor.reading,
        "adapters": {
            f"hci{index}": {
                "dropped": dict(sorted(stats.dropped.items())),
                "answered": stats.answered,
                "last_answered": stats.last_answered.isoformat()
                if stats.last_answered
                else None,
            }
            for index, stats in sorted(monitor.watcher.adapters.items())
        },
    }
