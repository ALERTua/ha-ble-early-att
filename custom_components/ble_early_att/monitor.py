"""Read the HCI monitor of the host, and send the answers that the watcher finds."""

import asyncio
import ctypes
import errno
import functools
import logging
import os
import socket
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from .watcher import EarlyAttWatcher, MtuAnswer

_LOGGER = logging.getLogger(__name__)

_AF_BLUETOOTH = 31
_BTPROTO_HCI = 1
_HCI_DEV_NONE = 0xFFFF
_HCI_CHANNEL_RAW = 0
_HCI_CHANNEL_MONITOR = 2
# Larger than each frame that the watcher reads: the kernel cuts a longer frame
_MONITOR_FRAME_MAX = 4096

# A device integration that answers the request itself answers at once, so its answer
# shows on the monitor before this delay ends
ANSWER_DELAY = 0.2


class _SockaddrHci(ctypes.Structure):
    _fields_ = (
        ("family", ctypes.c_ushort),
        ("dev", ctypes.c_ushort),
        ("channel", ctypes.c_ushort),
    )


@functools.cache
def _libc() -> ctypes.CDLL:
    return ctypes.CDLL(None, use_errno=True)


def _hci_socket(dev: int, channel: int) -> socket.socket:
    if sys.platform != "linux":
        raise OSError(errno.EAFNOSUPPORT, "HCI sockets need Linux")
    sock = socket.socket(_AF_BLUETOOTH, socket.SOCK_RAW, _BTPROTO_HCI)
    # `socket.bind((dev, channel))` fails with EBADFD for the monitor on Python 3.14
    addr = _SockaddrHci(_AF_BLUETOOTH, dev, channel)
    if _libc().bind(sock.fileno(), ctypes.byref(addr), ctypes.sizeof(addr)) != 0:
        code = ctypes.get_errno()
        sock.close()
        raise OSError(code, os.strerror(code))
    sock.setblocking(False)
    return sock


def open_monitor() -> socket.socket:
    """Open the HCI monitor channel, which needs Linux and CAP_NET_RAW."""
    return _hci_socket(_HCI_DEV_NONE, _HCI_CHANNEL_MONITOR)


def send_to_adapter(adapter: int, packet: bytes) -> None:
    """Send an HCI packet to one adapter through a raw socket."""
    # Bound only for the send: the kernel copies all traffic of the adapter to a bound
    # raw socket
    with _hci_socket(adapter, _HCI_CHANNEL_RAW) as raw:
        raw.send(packet)


class EarlyAttMonitor:
    """Feed the frames of the HCI monitor to the watcher, and send its answers."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        monitor: socket.socket,
        send: Callable[[int, bytes], None],
    ) -> None:
        """Take an open monitor socket, which `stop` closes, and a send to an adapter."""
        self.watcher = EarlyAttWatcher()
        self.reading = False
        self._loop = loop
        self._monitor = monitor
        self._send = send
        self._timers: dict[tuple[int, int], asyncio.TimerHandle] = {}
        self._listeners: list[Callable[[], None]] = []
        self._reported_adapters: set[int] = set()

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call the listener after each change of the adapters or their counts."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def start(self) -> None:
        """Read the monitor while the event loop runs."""
        self._loop.add_reader(self._monitor.fileno(), self._read)
        self.reading = True

    def stop(self) -> None:
        """Stop the reads, drop the waiting answers and close the monitor."""
        if self._monitor.fileno() != -1:
            self._loop.remove_reader(self._monitor.fileno())
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
        self._monitor.close()
        self.reading = False

    def _read(self) -> None:
        revision = self.watcher.revision
        while (frame := self._recv()) is not None:
            if (answer := self.watcher.feed(frame)) is not None:
                key = (answer.adapter, answer.handle)
                # A new link on the handle replaces the answer to a link that closed
                if (old := self._timers.pop(key, None)) is not None:
                    old.cancel()
                self._timers[key] = self._loop.call_later(
                    ANSWER_DELAY, self._answer, answer
                )
        if self.watcher.revision != revision or not self.reading:
            self._changed()

    def _recv(self) -> bytes | None:
        try:
            return self._monitor.recv(_MONITOR_FRAME_MAX)
        except BlockingIOError:
            return None
        except OSError as err:
            _LOGGER.warning(
                "Reading the HCI monitor failed, so early ATT MTU requests stay "
                "unanswered until the integration reloads: %s",
                err,
            )
            self._loop.remove_reader(self._monitor.fileno())
            self.reading = False
            return None

    def _answer(self, answer: MtuAnswer) -> None:
        del self._timers[answer.adapter, answer.handle]
        if not self.watcher.still_needed(answer):
            _LOGGER.debug(
                "Handle %d on hci%d needs no answer: another tool answered, or the "
                "link closed",
                answer.handle,
                answer.adapter,
            )
            return
        try:
            self._send(answer.adapter, answer.packet)
        except OSError as err:
            _LOGGER.warning(
                "Could not answer the ATT MTU request that the kernel dropped on "
                "hci%d: %s",
                answer.adapter,
                err,
            )
            return
        self.watcher.record_answer(answer, datetime.now(UTC))
        _LOGGER.info(
            "Answered the ATT MTU request that the kernel dropped on hci%d",
            answer.adapter,
        )
        self._changed()

    def _changed(self) -> None:
        for index, stats in self.watcher.adapters.items():
            if index not in self._reported_adapters and stats.dropped.total():
                self._reported_adapters.add(index)
                _LOGGER.info(
                    "hci%d delivers the first packet of a new link too early, and the "
                    "kernel drops it. The integration answers such packets when they "
                    "are ATT MTU requests",
                    index,
                )
        for listener in list(self._listeners):
            listener()
