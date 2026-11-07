---
name: fix-design
description: "Read this file before you change `watcher.py` or `monitor.py`, the answer, the wait before it, or the HCI sockets of the integration."
metadata:
  type: reference
---

## The rules of the watcher

- Answer only an ATT Exchange MTU Request that the monitor shows before the connection event of the same handle. The connection event is LE Connection Complete (0x01) or LE Enhanced Connection Complete (0x0A), with status 0.
- Send the answer only after that event. Then the request surely comes from the new link, and not from another link of the adapter.
- Handle both connection events. The kernel turns on the enhanced event only when the controller supports LL Privacy or LE Extended Advertising (`hci_sync.c`), so older controllers send 0x01.
- Mark a link open at its connection event and at each ACL TX frame on its handle. The kernel sends only on a link that it knows, so an ACL TX also marks a link that was up before the integration started. An ACL RX on an open link is never early.
- A Disconnection Complete event with status 0 removes the state of its handle, because a new link can get the same handle. A Close Index or a Delete Index frame removes the state of all links of its adapter, because a closed adapter sends no Disconnection Complete.
- Read only the first fragment of an ACL TX packet as an MTU response. A continuation fragment (Packet Boundary flag `0b01`) has other bytes at that position.
- Mask the handle with `0x0FFF`. The upper bits of the field are the Packet Boundary and Broadcast flags.

## The answer

- Wait `ANSWER_DELAY` (0.2 s) after the connection event. Then send only when `still_needed` is true: the link is still open, and no ACL TX MTU response showed on it.
- Keep one waiting answer for each adapter and handle. A new connection event on the same handle cancels the waiting answer of the old link. `stop` cancels all waiting answers.
- A device integration that has its own fix answers at once, so its answer shows on the monitor before the wait ends. The integration then sends nothing, and the device gets exactly one answer. The ef_ble fix of rabits/ha-ef-ble#554 is such a fix. Keep both able to run together.
- Answer with MTU 517, the value that BlueZ offers in its own request.
- Send the answer through a raw HCI socket of the adapter, with the Packet Boundary flag `0b00`, as the kernel sends LE data. The DELTA Pro ignores an answer with `0b10`.
- Bind the raw socket only for the send. A bound raw socket raises `hdev->promisc` (`hci_sock_bind`), and the kernel then copies all traffic of the adapter to that socket.
- Bind each HCI socket through the libc `bind` with `ctypes`. `socket.bind((0xFFFF, 2))` fails with EBADFD for the monitor on Python 3.14 in the Home Assistant container.

## Side effects

- A raw ACL packet skips the ACL flow control of the kernel. The kernel logs `hcon ... sent 0 < count 1` once for each answer, and adds the buffer back to its count, limited to the buffer count of the controller (`hci_num_comp_pkts_evt`). No userspace path prevents this. `README.md` tells the user that the line is harmless.
- The monitor socket gets each frame of each adapter. On a host with one BLE link and passive scan, the monitor carries about 50 frames per second. The parse of one frame takes less than 1 µs.

## Monitor frames

- The header has the opcode, the adapter index and the body length, each a little-endian 16-bit value. The body follows.
- The opcodes come from `include/net/bluetooth/hci_mon.h`. The integration reads New Index 0, Delete Index 1, Event 3, ACL TX 4, ACL RX 5 and Close Index 9.
- A New Index body has the type, the bus, and then the address of the adapter in reverse octet order at bytes 2 to 7.
- The kernel sends a New Index frame for each adapter right after the bind of the monitor. Thus the integration knows all adapters at setup.

## Requirements and failures

- The monitor and the raw socket need Linux and `CAP_NET_RAW`. Without them, the config flow aborts with `monitor_unavailable`, and the setup raises `ConfigEntryError` with the same translation.
- A read error of the monitor stops the reader, logs one warning and makes the sensors unavailable until the entry reloads.
- A failed send logs one warning and records no answer.
- When the monitor loses the connection event, the integration sends no answer, because it answers only at that event.

## Rejected alternatives

- A fix inside one device integration helps only that integration, and only during its connect. This integration helps each BLE device of the host.
- An answer to other early packets: only BlueZ has the state for them.
- A limit to some adapters: the integration answers only requests that the kernel dropped, so a limit protects nothing.
- A fix in the kernel is outside this project. The kernel only logs and drops the early packet.

## Not measured

- A lower `ExchangeMTU` in the BlueZ `main.conf`: the device then takes 517 from the answer, but BlueZ uses its own lower value.
- Other peripherals and other adapters than the adapters and devices of `root-cause.md`.
