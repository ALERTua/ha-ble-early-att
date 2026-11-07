"""Tests of the watcher that finds the MTU requests the kernel dropped."""

import struct

import pytest

from custom_components.ble_early_att.watcher import (
    EarlyAttWatcher,
    MtuAnswer,
    PacketKind,
)
from tests.hci import (
    ADAPTER,
    ADAPTER_ADDRESS,
    HANDLE,
    acl_rx,
    connection_complete,
    disconnection_complete,
    monitor_frame,
    mtu_request,
    mtu_response_from_host,
)


def _feed(watcher: EarlyAttWatcher, *frames: bytes) -> list[MtuAnswer | None]:
    return [watcher.feed(frame) for frame in frames]


@pytest.mark.parametrize("subevent", [0x01, 0x0A], ids=["legacy", "enhanced"])
def test_mtu_request_before_connection_complete_is_answered(subevent: int):
    """A request that the kernel dropped gets an answer once its link is up."""
    watcher = EarlyAttWatcher()

    *_, answer = _feed(watcher, mtu_request(), connection_complete(subevent))

    assert answer is not None
    assert (answer.adapter, answer.handle) == (ADAPTER, HANDLE)
    packet_type, handle_flags, _, _, cid, opcode = struct.unpack_from(
        "<BHHHHB", answer.packet
    )
    assert packet_type == 0x02
    assert handle_flags == HANDLE  # packet boundary flag 0b00
    assert cid == 0x0004
    assert opcode == 0x03
    assert watcher.adapters[ADAPTER].dropped[PacketKind.ATT_MTU_REQUEST] == 1


@pytest.mark.parametrize(
    "frames",
    [
        pytest.param([connection_complete(), mtu_request()], id="kernel_saw_it"),
        pytest.param(
            [mtu_request(), connection_complete(status=0x3E)], id="connect_failed"
        ),
        pytest.param(
            [
                mtu_request(),
                disconnection_complete(),
                connection_complete(),
                mtu_request(),
            ],
            id="handle_of_a_closed_link_reused",
        ),
    ],
)
def test_other_mtu_requests_are_not_answered(frames: list[bytes]):
    """Only a request that the kernel dropped on a link that came up is answered."""
    watcher = EarlyAttWatcher()

    assert _feed(watcher, *frames) == [None] * len(frames)


def test_answer_is_not_needed_after_the_host_answered():
    """An answer that another tool already sent on the link is not sent again."""
    watcher = EarlyAttWatcher()
    *_, answer = _feed(watcher, mtu_request(), connection_complete())
    assert answer is not None
    assert watcher.still_needed(answer)

    watcher.feed(mtu_response_from_host())

    assert not watcher.still_needed(answer)


def test_answer_is_not_needed_after_the_link_closed():
    """A link that closed before the answer went out needs no answer."""
    watcher = EarlyAttWatcher()
    *_, answer = _feed(watcher, mtu_request(), connection_complete())
    assert answer is not None

    watcher.feed(disconnection_complete())

    assert not watcher.still_needed(answer)


def test_recorded_answers_are_counted_once_per_link():
    """A sent answer counts, and the link needs no second one."""
    watcher = EarlyAttWatcher()
    *_, answer = _feed(watcher, mtu_request(), connection_complete())
    assert answer is not None

    watcher.record_answer(answer)

    assert watcher.adapters[ADAPTER].answered == 1
    assert not watcher.still_needed(answer)


@pytest.mark.parametrize(
    ("cid", "payload", "kind"),
    [
        (0x0004, b"\x10\x01\x00\xff\xff\x00\x28", PacketKind.ATT_OTHER),
        (0x0005, b"\x12\x01\x08\x00", PacketKind.L2CAP_SIGNALING),
        (0x0006, b"\x0b\x01", PacketKind.SMP),
        (0x0040, b"\x00", PacketKind.OTHER),
    ],
)
def test_other_dropped_packets_are_counted_without_an_answer(
    cid: int, payload: bytes, kind: PacketKind
):
    """Early packets that only BlueZ can answer are counted by kind."""
    watcher = EarlyAttWatcher()

    answers = _feed(watcher, acl_rx(cid, payload), connection_complete())

    assert answers == [None, None]
    assert watcher.adapters[ADAPTER].dropped == {kind: 1}


def test_link_that_was_up_before_the_watcher_started_is_not_counted():
    """Packets of an old link wait for its end, and a new link on the handle counts."""
    watcher = EarlyAttWatcher()
    old_link_packet = acl_rx(0x0004, b"\x1b\x10\x00\x01")

    *_, answer = _feed(
        watcher,
        old_link_packet,
        disconnection_complete(),
        mtu_request(),
        connection_complete(),
    )

    assert answer is not None
    assert watcher.adapters[ADAPTER].dropped == {PacketKind.ATT_MTU_REQUEST: 1}


def test_link_where_the_host_sends_is_open():
    """The kernel sends only on a link that it knows, so nothing there is early."""
    watcher = EarlyAttWatcher()
    write = struct.pack("<HH", 3, 0x0004) + b"\x12\x2a\x00"
    host_write = monitor_frame(4, struct.pack("<HH", HANDLE, len(write)) + write)

    answers = _feed(watcher, host_write, mtu_request(), connection_complete())

    assert answers == [None, None, None]
    assert watcher.adapters == {}


@pytest.mark.parametrize("opcode", [1, 9], ids=["removed", "closed"])
def test_adapter_that_goes_away_forgets_its_links(opcode: int):
    """A handle of a closed adapter is free for a new link that the kernel drops."""
    watcher = EarlyAttWatcher()

    *_, answer = _feed(
        watcher,
        connection_complete(),
        monitor_frame(opcode, b""),
        mtu_request(),
        connection_complete(),
    )

    assert answer is not None


def test_continuation_fragment_is_not_an_mtu_response():
    """Bytes in the middle of a long packet do not mark the link as answered."""
    watcher = EarlyAttWatcher()
    *_, answer = _feed(watcher, mtu_request(), connection_complete())
    assert answer is not None
    # Read as the start of a packet, these bytes are an ATT MTU response
    looks_like_a_response = b"\x03\x00\x04\x00\x03\x05\x02"
    continuation = struct.pack("<HH", HANDLE | 0x1000, len(looks_like_a_response))

    watcher.feed(monitor_frame(4, continuation + looks_like_a_response))

    assert watcher.still_needed(answer)


def test_new_index_names_the_adapter():
    """The monitor reports the address of each adapter when it opens."""
    watcher = EarlyAttWatcher()
    address = bytes.fromhex(ADAPTER_ADDRESS.replace(":", ""))[::-1]

    watcher.feed(monitor_frame(0, b"\x00\x01" + address + b"hci1\x00\x00\x00\x00"))

    assert watcher.adapters[ADAPTER].address == ADAPTER_ADDRESS


@pytest.mark.parametrize(
    "frame",
    [
        b"",
        b"\x05\x00",
        monitor_frame(5, b"\x10"),
        monitor_frame(4, b"\x10"),
        monitor_frame(3, b""),
    ],
)
def test_short_frames_are_ignored(frame: bytes):
    """A truncated frame changes nothing and raises nothing."""
    watcher = EarlyAttWatcher()

    assert watcher.feed(frame) is None
    assert watcher.adapters == {}
