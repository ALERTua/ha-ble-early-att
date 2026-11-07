"""Pytest configuration and fixtures."""

import socket
from collections.abc import Iterator

import pytest


@pytest.fixture
def monitor_pair(socket_enabled: None) -> Iterator[tuple[socket.socket, socket.socket]]:
    """Give a datagram socket in place of the HCI monitor, and a socket that feeds it."""
    reader = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    reader.bind(("127.0.0.1", 0))
    reader.setblocking(False)
    writer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    writer.connect(reader.getsockname())
    yield reader, writer
    reader.close()
    writer.close()
