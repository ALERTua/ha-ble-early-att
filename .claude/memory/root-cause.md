---
name: root-cause
description: "Read this file before you change how the integration finds a dropped packet, or before you explain why a BLE device stays silent through a USB Bluetooth adapter."
metadata:
  type: reference
---

## Principles

- Some Bluetooth controllers on USB send the first ACL packet of a new LE link before the LE Connection Complete event of that link. Events and ACL data come through different USB endpoints, so the host can get them in either order. The RFC patch "handle USB endpoint race condition" on the linux-bluetooth list describes this race.
- A built-in adapter can connect over USB too. Say "built-in or USB dongle" to users, because "USB adapter" makes them think only of a dongle.
- The kernel drops an ACL packet for a handle that it does not know. It logs `ACL packet for unknown connection handle <n>` and does not keep the packet for later (`hci_acldata_packet` in `net/bluetooth/hci_core.c`).
- The kernel copies each received frame to the HCI monitor channel before it handles the frame (`hci_rx_work`). It handles the frames one at a time, in queue order. Thus a packet that the monitor shows before the connection event of its link is a packet that the kernel dropped.
- The kernel also copies each frame that the host sends to the monitor, also a frame from a raw HCI socket (`hci_send_frame`).
- When the dropped packet is an ATT Exchange MTU Request, BlueZ never sees it, and nobody answers it. Some peripherals then keep the link up but send no notification.
- The Nordic nRF5 SDK module `nrf_ble_gatt` sends an MTU request when a link comes up, also in the peripheral role (`nrf_ble_gatt.c`, SDK 17.1). It does this when `NRF_BLE_GATT_MTU_EXCHANGE_INITIATION_ENABLED` is 1. Many firmware projects on GitHub set this flag to 1.
- Zephyr sends no MTU request when a link comes up, because `BT_GATT_AUTO_UPDATE_MTU` has no default (`Kconfig.gatt`).
- Only BlueZ can answer an early packet of another kind, for example SMP or L2CAP signaling, because the answer needs the state of BlueZ. Thus the integration answers only the MTU request and counts the other kinds.

## Realtek RTL8852BU

- This adapter is built into a mini PC. It connects over the internal USB bus of the computer, with the driver `btusb` and the USB ID `0bda:b85b`.
- With firmware `0x127cfd78`, it sends the first ACL packet before the LE Enhanced Connection Complete event on each LE link. It does this on Home Assistant OS 18.4, kernel 6.18.58-haos, BlueZ 5.86.
- Users of Realtek RTL8761 dongles report the same kernel log line (home-assistant/operating-system#3758). Nobody captured their traffic.

## EcoFlow DELTA Pro (V1)

- The first packet of each link is its ATT Exchange MTU Request `02 f7 00` (MTU 247).
- Without an answer, the device acknowledges each write but sends no notification. ef_ble then stops after `Init completed, starting auth routine...` and times out after 30 s.
- An Android phone answers the request within 4 ms, and the device then answers the key exchange of the app.
- An answer 0.2 s after the connection event works too: the auth of ef_ble completes about 0.9 s after the connection.
- The device works through an ESPHome Bluetooth proxy. The HCI monitor of the host shows no frame of a link through a proxy.
