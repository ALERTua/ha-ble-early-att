# BLE Early ATT

A Home Assistant integration that helps Bluetooth devices talk through some USB Bluetooth adapters.

## Do you need it?

You probably need it when all of these are true:

- A Bluetooth device connects in Home Assistant, but its integration then waits and gives up. You get no data, the login of the device fails, or its entities stay unavailable.
- The same device works with its phone app, through an ESPHome Bluetooth proxy, or through another Bluetooth adapter.
- At the moment of the connection, the host log shows a line like `Bluetooth: hci0: ACL packet for unknown connection handle 16`.

An example: the [EcoFlow BLE](https://github.com/rabits/ha-ef-ble) integration connects to an EcoFlow DELTA Pro and then stops after `Init completed, starting auth routine...`.

Not sure? Install the integration and open the page of your Bluetooth adapter (Settings → Devices & services → Bluetooth). The sensor "Early packets dropped" counts the packets that your adapter lost. If it stays at 0 while your devices connect, you do not need this integration.

## What goes wrong

When some devices connect, the first thing that they do is ask: "How large can my messages be?" Some USB Bluetooth adapters give that question to Linux a moment too early, before they tell Linux that the connection exists. Linux does not know the connection yet, so it throws the question away. The device waits for an answer that never comes, and some devices then send no data at all.

Which devices ask at once: for example, many devices that are built on the Nordic Semiconductor nRF5 SDK, which can send this question as soon as the device connects.

Which adapters lose the question: the Realtek RTL8852BU (a Wi-Fi 6 and Bluetooth chip in many mini PCs) does it on every connection. Other users see the same Linux log line with Realtek RTL8761 dongles. Other adapters can have the same problem.

## What the integration does

It watches the Bluetooth traffic of the host. When it sees that Linux threw such a question away, it sends the answer that Linux would have sent.

- It answers only the questions that Linux lost. Linux still answers all other questions.
- It does not change any other traffic, and it keeps no connection open.
- It does nothing for devices behind an ESPHome Bluetooth proxy, because a proxy does not lose these questions.

## What it does not fix

- A weak signal, interference, or a pairing problem.
- A device whose lost first packet is something other than this question. The integration counts such packets in its diagnostics, so that you can report them.

## Requirements

- Home Assistant 2026.9 or later, on Linux.
- A Bluetooth adapter that is connected to the Home Assistant host. Adapters behind ESPHome proxies do not need this integration.
- Permission to read the Bluetooth traffic of the host. Home Assistant OS gives it. If your installation does not, the setup tells you so.

## Installation

1. In HACS, add `https://github.com/ALERTua/ha-ble-early-att` as a custom repository of the type Integration.
2. Install "BLE Early ATT" and restart Home Assistant.
3. Go to Settings → Devices & services → Add integration, and select "BLE Early ATT".

The integration has no settings. It works for all Bluetooth adapters of the host.

## Side effect

Each time the integration answers, the host log shows one line like `Bluetooth: hci0: hcon ... sent 0 < count 1`. Linux writes it because it sees the confirmation of a message that it did not send itself. The line is harmless.

## How it works

For developers: the integration reads the HCI monitor channel. The kernel copies each received frame to the monitor before it handles the frame (`hci_rx_work`), so an ATT Exchange MTU Request that shows up before the LE Connection Complete event of its link is a request that `hci_acldata_packet` dropped. When that event arrives with status success and the same handle, the integration sends an ATT Exchange MTU Response (MTU 517, as BlueZ offers) through a raw HCI socket, with the packet boundary flag `0b00`.
