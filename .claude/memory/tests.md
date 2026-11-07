---
name: tests
description: "Read this file before you write or change a test, a fixture or `conftest.py`, or when a test passes or fails for an unclear reason."
metadata:
  type: reference
---

## Principles

- For each rule of `watcher.py`, `monitor.py` and `sensor.py`, a test must fail when the rule is removed. Remove the rule, run the narrow test file, and make sure that a test fails. Then put the rule back.
- An exception in an event loop callback, for example a timer, goes to the exception handler of the loop and does not fail the test. The autouse fixture `no_errors_in_callbacks` in `tests/test_monitor.py` fails a test that logged an ERROR record.
- In a fixture teardown, `caplog.records` holds only the records of the teardown. Use `caplog.get_records("call")` for the records of the test itself.
- When a test sends all frames before one read, a rule that needs two separate reads stays untested. Examples are the one-time log and the filter of the listeners. Wait for a state between the frames with `wait_until` of `tests/common.py`.
- The frame builders of `tests/hci.py` use their own values: adapter 1, handle `0x0123` and the address `AA:BB:CC:DD:EE:FF`. The handle is above `0xFF`, so a wrong mask of the handle fails a test.

## Sockets and the event loop

- The test plugin blocks sockets in each test. The fixture `monitor_pair` of `tests/conftest.py` asks for `socket_enabled` and gives a UDP socket pair on 127.0.0.1 as the monitor. No test uses real Bluetooth.
- The fixture `fake_linux` of `tests/test_monitor.py` sets `sys.platform` to `linux` and replaces `socket.socket` and the libc `bind`. Thus the Linux branch of the socket code runs on each system.
- The default event loop of Windows has no `add_reader`. The hook `pytest_asyncio_loop_factories` of the root `conftest.py` gives each test on Windows a selector loop, as Home Assistant has on Linux.
- The line `ctypes.CDLL(None, use_errno=True)` in `monitor.py` runs only on Linux, so `just cov` on Windows shows it as not run. The CI runs the tests on Linux.
