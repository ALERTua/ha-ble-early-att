---
name: home-assistant
description: "Read this file before you change the sensors, the device of an entity, the config flow or the setup of the integration, or before you call the Home Assistant API for a config entry."
metadata:
  type: reference
---

## The device of the sensors

- Home Assistant 2026.9 and later keep the devices of each config entry apart: identifiers and connections are unique only inside one config entry. Thus `DeviceInfo` with the connection of an adapter makes a new device in the entry of this integration.
- To put an entity on the device of another integration, set `entity.device_entry` and give no device info (`helpers/entity_platform.py`).
- The Bluetooth integration keeps one config entry for each local adapter. The unique ID of that entry is the address of the adapter in uppercase, and the entry has one device. `_adapter_device` in `sensor.py` finds the device this way.
- When the Bluetooth integration does not manage an adapter, the sensors make their own device "Bluetooth adapter <address>".
- The name of an adapter device is `hci<N> (<address>)`, so the entity IDs start with `sensor.hci<N>_` and the address.
- Key each sensor by the address of the adapter, not by its index. The index of an adapter can change.
- The diagnostics give the counts by adapter index and by packet kind, with no address, so that a user can post them in an issue.

## Setup and config flow

- Home Assistant does not set up a config entry of an integration without a `config_flow` module, also in a test.
- The integration has one config entry (`single_config_entry`), because one monitor serves all adapters of the host.
- The config flow has one step without fields. It opens and closes the monitor first, so that a host without the permission gets the abort reason at once.
- Home Assistant loads the code of a custom integration only when it starts. A reload of the config entry does not load changed files.
- Home Assistant runs a selector event loop on Linux, so `loop.add_reader` works.

## The API of config entries

- The REST API adds the integration with `POST /api/config/config_entries/flow` and the body `{"handler": "ble_early_att"}`, then `POST /api/config/config_entries/flow/<flow_id>` with the body `{}`.
- The REST API reloads an entry with `POST /api/config/config_entries/entry/<entry_id>/reload`. It has no call that disables or unloads an entry. Use the UI or the websocket command `config_entries/disable` for that.

## Logs

- The `info` lines of the integration tell the first early packet of each adapter and each answer. A Home Assistant installation with a default log level of `warning` hides them. To see them, set the level of `custom_components.ble_early_att` to `info` with the action `logger.set_level`.

## Types

- `ty` refuses a property that overrides `available` or `native_value`, and a narrower annotation of `entity_description`. Set `_attr_available` and `_attr_native_value` in `_update()` instead.
