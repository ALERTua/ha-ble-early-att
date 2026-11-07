---
name: live-check
description: "Read this file before you run a smoke test on a real Home Assistant host, capture the HCI monitor, or release a change of the answer logic."
metadata:
  type: reference
---

## Principles

- Before you release a change of the watcher or of the answer, do a live check. Use a host with an adapter that drops the early packet. The unit tests cannot show the real order of the kernel.
- On Home Assistant OS, run a capture script in the Core container with `docker exec homeassistant python3 <script>`. That container can open monitor and raw HCI sockets. A Bluetooth device accepts one BLE connection at a time in many cases, so a script that connects needs the device integration disabled first.
- A capture script binds a raw `BTPROTO_HCI` socket to `HCI_DEV_NONE` (0xFFFF) and `HCI_CHANNEL_MONITOR` (2) through the libc `bind`. It prints each ACL frame with the handle and the L2CAP bytes, and each LE meta event except the advertising reports (subevents 0x02 and 0x0D).
- `ha host logs --identifier kernel --verbose` shows the kernel log with times.

## The signs in a capture

```
ACL RX h=0x010 0300040002f700      MTU Request of the device, before the event: the kernel dropped it
EVT 3e1f0a00100000...              LE Enhanced Connection Complete, status 0, handle 0x0010
ACL TX h=0x010 03000400030502      the answer, MTU 517, 0.2 s after the event
ACL TX h=0x010 03000400020502      the MTU Request of BlueZ
ACL RX h=0x010 0300040003f700      the device answers BlueZ
```

## The four scenarios

1. A device integration with its own fix, and this integration. The capture shows exactly one ACL TX MTU response on the link, which the other fix sends at once. "Early packets dropped" grows, and "MTU requests answered" stays the same.
2. The same device integration without its fix: the answer goes 0.2 s after the event, "MTU requests answered" grows, and the device integration gets data.
3. Control: disable the config entry of BLE Early ATT and reload the device integration. The request gets no answer, and the device stays silent. Enable the entry again.
4. Other BLE devices. Count the LE extended advertising reports (subevent 0x0D) of the adapter for 20 s with the entry enabled, then disabled. The two rates are the same. The kernel log has only two known lines: `ACL packet for unknown connection handle` once for each link, and `hcon ... sent 0 < count 1` once for each answer.

## A host where the four scenarios pass

- The host: Home Assistant 2026.11.0, Home Assistant OS 18.4, kernel 6.18.58-haos, BlueZ 5.86, a Realtek RTL8852BU, an EcoFlow DELTA Pro (V1) with ef_ble 1.3.1.
- Without the integration, ef_ble stops after `Init completed, starting auth routine...`. With it, `Auth completed, everything is fine` comes about 0.9 s after the connection.
- The advertising reports come at about 1.1 per second, with the entry on and off.
