"""Tests of the flow that adds the integration from the UI."""

import errno
from unittest.mock import MagicMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ble_early_att.const import DOMAIN

OPEN_MONITOR = "custom_components.ble_early_att.config_flow.open_monitor"


async def test_user_confirms_and_gets_one_entry(hass, enable_custom_integrations):
    """The flow opens and closes the monitor, asks to confirm and adds the entry."""
    monitor_socket = MagicMock(spec=["close"])
    with patch(OPEN_MONITOR, return_value=monitor_socket):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    monitor_socket.close.assert_called_once_with()

    with (
        patch(OPEN_MONITOR, return_value=monitor_socket),
        patch("custom_components.ble_early_att.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}


async def test_host_without_the_monitor_gets_the_reason(
    hass, enable_custom_integrations
):
    """Without Linux or CAP_NET_RAW the flow stops and names the error."""
    with patch(
        OPEN_MONITOR,
        side_effect=PermissionError(errno.EPERM, "Operation not permitted"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "monitor_unavailable"
    assert "Operation not permitted" in result["description_placeholders"]["error"]


async def test_second_entry_is_refused(hass, enable_custom_integrations):
    """The host has one HCI monitor, so the integration has one entry."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
