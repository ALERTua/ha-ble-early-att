"""Tests of the monitor that reads HCI frames and sends the answers."""

import asyncio
import ctypes
import errno
import logging
import socket
import sys
from collections.abc import Callable, Iterator
from typing import ClassVar, Self

import pytest

from custom_components.ble_early_att import monitor
from custom_components.ble_early_att.monitor import ANSWER_DELAY, EarlyAttMonitor
from tests.common import wait_until
from tests.hci import (
    ADAPTER,
    HANDLE,
    connection_complete,
    disconnection_complete,
    mtu_request,
    mtu_response_from_host,
)


class _Sent:
    """Record each packet that the monitor sends, with the loop time of the send."""

    def __init__(self) -> None:
        self.packets: list[tuple[int, bytes, float]] = []

    def __call__(self, adapter: int, packet: bytes) -> None:
        self.packets.append((adapter, packet, asyncio.get_running_loop().time()))


@pytest.fixture(autouse=True)
def no_errors_in_callbacks(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    """Fail a test when a callback of the monitor raises inside the event loop."""
    yield
    records = caplog.get_records("call")
    errors = [r.getMessage() for r in records if r.levelno >= logging.ERROR]
    assert errors == []


def _logged(caplog: pytest.LogCaptureFixture, text: str) -> Callable[[], bool]:
    return lambda: any(text in record.getMessage() for record in caplog.records)


async def test_dropped_request_is_answered_after_the_delay(monitor_pair):
    """The answer goes to the adapter of the link, after the wait for other tools."""
    reader, writer = monitor_pair
    sent = _Sent()
    hci = EarlyAttMonitor(asyncio.get_running_loop(), reader, sent)
    hci.start()

    writer.send(mtu_request())
    writer.send(connection_complete())
    connected_at = asyncio.get_running_loop().time()
    await wait_until(lambda: sent.packets)

    [(adapter, packet, sent_at)] = sent.packets
    assert adapter == ADAPTER
    assert packet[:3] == bytes([0x02]) + HANDLE.to_bytes(2, "little")
    assert sent_at - connected_at >= ANSWER_DELAY
    assert hci.watcher.adapters[ADAPTER].answered == 1
    hci.stop()


@pytest.mark.parametrize(
    "late_frame",
    [mtu_response_from_host(), disconnection_complete()],
    ids=["another_tool_answered", "link_closed"],
)
async def test_link_that_needs_no_answer_gets_none(monitor_pair, caplog, late_frame):
    """An answer from another tool, or a closed link, during the wait stops the send."""
    reader, writer = monitor_pair
    sent = _Sent()
    hci = EarlyAttMonitor(asyncio.get_running_loop(), reader, sent)
    hci.start()
    caplog.set_level(logging.DEBUG, logger=monitor.__name__)

    for frame in (mtu_request(), connection_complete(), late_frame):
        writer.send(frame)
    await wait_until(_logged(caplog, "needs no answer"))

    assert sent.packets == []
    assert (
        ADAPTER not in hci.watcher.adapters
        or not hci.watcher.adapters[ADAPTER].answered
    )
    hci.stop()


async def test_new_link_on_the_handle_gets_one_answer(monitor_pair):
    """A link that closes and opens again during the wait gets one answer only."""
    reader, writer = monitor_pair
    sent = _Sent()
    hci = EarlyAttMonitor(asyncio.get_running_loop(), reader, sent)
    hci.start()

    for frame in (
        mtu_request(),
        connection_complete(),
        disconnection_complete(),
        mtu_request(),
        connection_complete(),
    ):
        writer.send(frame)
    await wait_until(lambda: sent.packets)
    await asyncio.sleep(ANSWER_DELAY)

    assert len(sent.packets) == 1
    hci.stop()


async def test_failed_send_is_logged_and_not_counted(monitor_pair, caplog):
    """A send that the kernel refuses leaves a warning and no count."""
    reader, writer = monitor_pair

    def refuse(_adapter: int, _packet: bytes) -> None:
        raise OSError(errno.ENODEV, "No such device")

    hci = EarlyAttMonitor(asyncio.get_running_loop(), reader, refuse)
    hci.start()

    writer.send(mtu_request())
    writer.send(connection_complete())
    await wait_until(_logged(caplog, "Could not answer"))

    assert hci.watcher.adapters[ADAPTER].answered == 0
    hci.stop()


async def test_stop_drops_the_waiting_answers_and_closes_the_monitor(monitor_pair):
    """Nothing goes out after the integration stops."""
    reader, writer = monitor_pair
    sent = _Sent()
    hci = EarlyAttMonitor(asyncio.get_running_loop(), reader, sent)
    hci.start()

    writer.send(mtu_request())
    writer.send(connection_complete())
    # The watcher counts the dropped request when it reads the connection event
    await wait_until(lambda: ADAPTER in hci.watcher.adapters)
    hci.stop()
    await asyncio.sleep(ANSWER_DELAY * 2)

    assert sent.packets == []
    assert reader.fileno() == -1


class _BrokenMonitor:
    """A monitor socket that becomes readable and then fails to read."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock

    def fileno(self) -> int:
        return self._sock.fileno()

    def recv(self, _size: int) -> bytes:
        raise OSError(errno.ENETDOWN, "Network is down")

    def close(self) -> None:
        self._sock.close()


async def test_read_error_stops_the_reads(monitor_pair, caplog):
    """A monitor that fails leaves a warning, and the loop stops to watch it."""
    reader, writer = monitor_pair
    loop = asyncio.get_running_loop()
    hci = EarlyAttMonitor(loop, _BrokenMonitor(reader), _Sent())
    hci.start()

    writer.send(mtu_request())
    await wait_until(_logged(caplog, "Reading the HCI monitor failed"))

    assert loop.remove_reader(reader.fileno()) is False
    hci.stop()


def test_hci_sockets_need_linux(monkeypatch):
    """Other systems have no HCI sockets, and the error tells so."""
    monkeypatch.setattr(sys, "platform", "win32")

    with pytest.raises(OSError, match="need Linux") as err:
        monitor.open_monitor()

    assert err.value.errno == errno.EAFNOSUPPORT


class _FakeHciSocket:
    """Stand in for a Bluetooth socket, which the test machine cannot open."""

    instances: ClassVar[list[_FakeHciSocket]] = []

    def __init__(self, family: int, kind: int, proto: int) -> None:
        self.args = (family, kind, proto)
        self.blocking = True
        self.closed = False
        self.sent: list[bytes] = []
        _FakeHciSocket.instances.append(self)

    def fileno(self) -> int:
        return 42

    def setblocking(self, flag: bool) -> None:
        self.blocking = flag

    def send(self, data: bytes) -> int:
        self.sent.append(data)
        return len(data)

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class _FakeLibc:
    """Record each bind, and return the result that the test gives."""

    def __init__(self, result: int) -> None:
        self.result = result
        self.binds: list[tuple[int, tuple[int, int, int]]] = []

    def bind(self, fd: int, addr: ctypes._CArgObject, _size: int) -> int:
        sockaddr = addr._obj
        self.binds.append((fd, (sockaddr.family, sockaddr.dev, sockaddr.channel)))
        return self.result


@pytest.fixture
def fake_linux(monkeypatch) -> Callable[[int], _FakeLibc]:
    """Make the module act as on Linux, with fake sockets and a fake libc."""
    _FakeHciSocket.instances = []
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(socket, "socket", _FakeHciSocket)

    def install(result: int) -> _FakeLibc:
        libc = _FakeLibc(result)
        monkeypatch.setattr(monitor, "_libc", lambda: libc)
        return libc

    return install


def test_open_monitor_binds_the_monitor_channel(fake_linux):
    """The monitor socket binds to no adapter on channel 2, and does not block."""
    libc = fake_linux(0)

    sock = monitor.open_monitor()

    [created] = _FakeHciSocket.instances
    assert sock is created
    assert created.args == (31, socket.SOCK_RAW, 1)
    assert libc.binds == [(42, (31, 0xFFFF, 2))]
    assert created.blocking is False


def test_failed_bind_closes_the_socket(fake_linux, monkeypatch):
    """A bind that the kernel refuses raises its error and leaks no socket."""
    fake_linux(-1)
    monkeypatch.setattr(ctypes, "get_errno", lambda: errno.EPERM)

    with pytest.raises(PermissionError):
        monitor.open_monitor()

    assert _FakeHciSocket.instances[0].closed


def test_send_to_adapter_binds_only_for_the_send(fake_linux):
    """The raw socket of the adapter carries the packet and closes at once."""
    libc = fake_linux(0)

    monitor.send_to_adapter(ADAPTER, b"\x02packet")

    [raw] = _FakeHciSocket.instances
    assert libc.binds == [(42, (31, ADAPTER, 0))]
    assert raw.sent == [b"\x02packet"]
    assert raw.closed
