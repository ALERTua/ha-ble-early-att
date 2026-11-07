# Project memory index

The index that follows comes from `.claude/memory/MEMORY.md` of this repository, and each link is relative to that folder.

- This repository is public. Keep private values out of it, also out of this memory. Examples are device addresses, serial numbers, user IDs, local IP addresses, config entry IDs and machine paths.
- The ef_ble integration has its own fix for the same problem, proposed in https://github.com/rabits/ha-ef-ble/issues/554. This integration must keep working next to that fix.
- [Root cause](root-cause.md) — why a BLE device stays silent, the early ACL packet, the kernel drop, the HCI monitor order, the known adapters and devices
- [Fix design](fix-design.md) — the watcher rules, the answer and its wait, coexistence with another fix, the HCI sockets, side effects, monitor frames, rejected alternatives
- [Home Assistant traps](home-assistant.md) — the sensor device, the config flow, a reload of changed code, the config entry API, the log level, `ty` and entity attributes
- [Tests](tests.md) — the mutation check, errors in loop callbacks, `caplog` in a teardown, frames in one read, the socket pair, the test event loop on Windows
- [Live check](live-check.md) — a smoke test on a real host, an HCI monitor capture, the four scenarios, the kernel log
- [Release and CI](release-ci.md) — the path filters of CI, the release draft, Dependabot alerts and PRs for pinned test packages
