"""Build the HCI monitor frames that the tests feed to the integration."""

import struct

ADAPTER = 1
HANDLE = 0x0123
ADAPTER_ADDRESS = "AA:BB:CC:DD:EE:FF"


def monitor_frame(opcode: int, body: bytes) -> bytes:
    """Wrap a body in the header of the HCI monitor."""
    return struct.pack("<HHH", opcode, ADAPTER, len(body)) + body


def new_index(address: str = ADAPTER_ADDRESS) -> bytes:
    """Build the frame that reports an adapter, as the monitor sends after its bind."""
    octets = bytes.fromhex(address.replace(":", ""))[::-1]
    return monitor_frame(0, b"\x00\x01" + octets + b"hci1\x00\x00\x00\x00")


def acl_rx(cid: int, payload: bytes, handle: int = HANDLE) -> bytes:
    """Build the first fragment of a packet that the controller delivers."""
    l2cap = struct.pack("<HH", len(payload), cid) + payload
    # Packet boundary flag 0b10, as a controller marks the first fragment
    return monitor_frame(5, struct.pack("<HH", handle | 0x2000, len(l2cap)) + l2cap)


def mtu_request(handle: int = HANDLE) -> bytes:
    """Build the ATT Exchange MTU Request of a device."""
    return acl_rx(0x0004, struct.pack("<BH", 0x02, 247), handle)


def mtu_response_from_host(handle: int = HANDLE) -> bytes:
    """Build an ATT Exchange MTU Response that the host sends."""
    att = struct.pack("<BH", 0x03, 517)
    l2cap = struct.pack("<HH", len(att), 0x0004) + att
    return monitor_frame(4, struct.pack("<HH", handle, len(l2cap)) + l2cap)


def connection_complete(
    subevent: int = 0x0A, status: int = 0, handle: int = HANDLE
) -> bytes:
    """Build an LE Connection Complete event, legacy (0x01) or enhanced (0x0A)."""
    params = bytes([subevent, status]) + struct.pack("<H", handle) + bytes(27)
    return monitor_frame(3, bytes([0x3E, len(params)]) + params)


def disconnection_complete(handle: int = HANDLE) -> bytes:
    """Build a Disconnection Complete event."""
    params = b"\x00" + struct.pack("<H", handle) + b"\x13"
    return monitor_frame(3, bytes([0x05, len(params)]) + params)
