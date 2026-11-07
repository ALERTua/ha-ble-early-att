"""
Find the ATT MTU requests that the kernel drops, in the frames of the HCI monitor.

Some controllers deliver the first ACL packet of an LE link before the event that
reports the link. The kernel drops such a packet as data for an unknown handle. The
kernel copies each frame to the monitor before it handles the frame, so a packet that
the monitor shows before the connection event of its link is a packet that the kernel
dropped. This module has no I/O: it takes monitor frames and returns what to send.
"""

import struct
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

# HCI monitor opcodes, from the Linux kernel `include/net/bluetooth/hci_mon.h`
MONITOR_NEW_INDEX = 0
MONITOR_DEL_INDEX = 1
MONITOR_EVENT = 3
MONITOR_ACL_TX = 4
MONITOR_ACL_RX = 5
MONITOR_CLOSE_INDEX = 9

_HCI_ACL_PACKET = 0x02
_ACL_START = 0x2  # packet boundary flag of the first fragment from a controller
_ACL_CONTINUATION = 0x1
_EVT_DISCONNECTION_COMPLETE = 0x05
_EVT_LE_META = 0x3E
_LE_CONNECTION_COMPLETE = 0x01
_LE_ENHANCED_CONNECTION_COMPLETE = 0x0A

_CID_ATT = 0x0004
_CID_LE_SIGNALING = 0x0005
_CID_SMP = 0x0006
_ATT_EXCHANGE_MTU_REQ = 0x02
_ATT_EXCHANGE_MTU_RSP = 0x03
# The MTU that BlueZ offers in its own request, so that both exchanges agree
SERVER_MTU = 517


class PacketKind(StrEnum):
    """Kinds of the early packets that the kernel drops."""

    ATT_MTU_REQUEST = "att_mtu_request"
    ATT_OTHER = "att_other"
    L2CAP_SIGNALING = "l2cap_signaling"
    SMP = "smp"
    OTHER = "other"


@dataclass(frozen=True)
class MtuAnswer:
    """An ATT Exchange MTU Response to send to one link."""

    adapter: int
    handle: int
    packet: bytes


@dataclass
class AdapterStats:
    """What the watcher saw on one adapter."""

    address: str | None = None
    dropped: Counter[PacketKind] = field(default_factory=Counter)
    answered: int = 0
    last_answered: datetime | None = None


@dataclass
class _EarlyLink:
    """Early packets of a handle whose connection event did not come yet."""

    kinds: Counter[PacketKind] = field(default_factory=Counter)


def _kind(cid: int, opcode: int | None) -> PacketKind:
    if cid == _CID_ATT:
        if opcode == _ATT_EXCHANGE_MTU_REQ:
            return PacketKind.ATT_MTU_REQUEST
        return PacketKind.ATT_OTHER
    if cid == _CID_LE_SIGNALING:
        return PacketKind.L2CAP_SIGNALING
    if cid == _CID_SMP:
        return PacketKind.SMP
    return PacketKind.OTHER


class EarlyAttWatcher:
    """Keep the state of the links of all adapters from the HCI monitor frames."""

    def __init__(self) -> None:
        """Start with no adapters and no links."""
        self.adapters: dict[int, AdapterStats] = {}
        # Grows with each change of the adapters or their counts
        self.revision = 0
        self._early: dict[tuple[int, int], _EarlyLink] = {}
        self._open_links: set[tuple[int, int]] = set()
        self._answered_links: set[tuple[int, int]] = set()

    def feed(self, frame: bytes) -> MtuAnswer | None:
        """Return the MTU answer that one monitor frame calls for, if any."""
        if len(frame) < 6:
            return None
        opcode, adapter, length = struct.unpack_from("<HHH", frame)
        body = frame[6 : 6 + length]
        if opcode == MONITOR_ACL_RX:
            self._on_acl_rx(adapter, body)
        elif opcode == MONITOR_ACL_TX:
            self._on_acl_tx(adapter, body)
        elif opcode == MONITOR_EVENT:
            return self._on_event(adapter, body)
        elif opcode == MONITOR_NEW_INDEX and len(body) >= 8:
            address = ":".join(f"{octet:02X}" for octet in reversed(body[2:8]))
            self.adapters.setdefault(adapter, AdapterStats()).address = address
            self.revision += 1
        elif opcode == MONITOR_CLOSE_INDEX:
            self._forget_links(adapter)
        elif opcode == MONITOR_DEL_INDEX:
            self._forget_links(adapter)
            if self.adapters.pop(adapter, None) is not None:
                self.revision += 1
        return None

    def still_needed(self, answer: MtuAnswer) -> bool:
        """Tell if nobody answered the link meanwhile and the link is still up."""
        key = (answer.adapter, answer.handle)
        return key in self._open_links and key not in self._answered_links

    def record_answer(self, answer: MtuAnswer, at: datetime) -> None:
        """Count an answer that was sent at the given time."""
        self._answered_links.add((answer.adapter, answer.handle))
        stats = self.adapters.setdefault(answer.adapter, AdapterStats())
        stats.answered += 1
        stats.last_answered = at
        self.revision += 1

    def _on_acl_rx(self, adapter: int, body: bytes) -> None:
        if len(body) < 8:
            return
        handle_flags = struct.unpack_from("<H", body)[0]
        key = (adapter, handle_flags & 0x0FFF)
        if (handle_flags >> 12) & 0x3 != _ACL_START or key in self._open_links:
            return
        cid = struct.unpack_from("<H", body, 6)[0]
        opcode = body[8] if len(body) > 8 else None
        self._early.setdefault(key, _EarlyLink()).kinds[_kind(cid, opcode)] += 1

    def _on_acl_tx(self, adapter: int, body: bytes) -> None:
        if len(body) < 2:
            return
        handle_flags = struct.unpack_from("<H", body)[0]
        key = (adapter, handle_flags & 0x0FFF)
        # The kernel sends only on a link that it knows, also on a link that was up
        # before the watcher started
        self._open_links.add(key)
        self._early.pop(key, None)
        if (
            (handle_flags >> 12) & 0x3 != _ACL_CONTINUATION
            and len(body) >= 9
            and struct.unpack_from("<H", body, 6)[0] == _CID_ATT
            and body[8] == _ATT_EXCHANGE_MTU_RSP
        ):
            # An MTU response from the host, from BlueZ or another tool
            self._answered_links.add(key)

    def _forget_links(self, adapter: int) -> None:
        # A closed adapter drops its links without a Disconnection Complete event
        self._early = {key: v for key, v in self._early.items() if key[0] != adapter}
        self._open_links = {key for key in self._open_links if key[0] != adapter}
        self._answered_links = {
            key for key in self._answered_links if key[0] != adapter
        }

    def _on_event(self, adapter: int, body: bytes) -> MtuAnswer | None:
        code = body[0] if body else None
        if code == _EVT_DISCONNECTION_COMPLETE and len(body) >= 5 and body[2] == 0:
            key = (adapter, struct.unpack_from("<H", body, 3)[0] & 0x0FFF)
            self._early.pop(key, None)
            self._open_links.discard(key)
            self._answered_links.discard(key)
            return None
        if (
            code != _EVT_LE_META
            or len(body) < 6
            or body[2]
            not in (_LE_CONNECTION_COMPLETE, _LE_ENHANCED_CONNECTION_COMPLETE)
            or body[3] != 0
        ):
            return None

        key = (adapter, struct.unpack_from("<H", body, 4)[0] & 0x0FFF)
        self._open_links.add(key)
        self._answered_links.discard(key)
        if (early := self._early.pop(key, None)) is None:
            return None
        self.adapters.setdefault(adapter, AdapterStats()).dropped.update(early.kinds)
        self.revision += 1
        if not early.kinds[PacketKind.ATT_MTU_REQUEST]:
            return None
        return MtuAnswer(adapter, key[1], _mtu_response(key[1]))


def _mtu_response(handle: int) -> bytes:
    att = struct.pack("<BH", _ATT_EXCHANGE_MTU_RSP, SERVER_MTU)
    l2cap = struct.pack("<HH", len(att), _CID_ATT) + att
    # Packet boundary flag 0b00, as the kernel sends LE data: a device ignored an
    # answer that carried 0b10
    acl = struct.pack("<HH", handle, len(l2cap)) + l2cap
    return bytes([_HCI_ACL_PACKET]) + acl
