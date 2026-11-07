"""Add BLE Early ATT from the UI: one entry for the host, with no fields."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class EarlyAttConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add the one entry of the integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a confirmation, then add the entry."""
        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(title="BLE Early ATT", data={})
