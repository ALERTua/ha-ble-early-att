# AGENTS.md

Guidance for AI coding agents working in this repository. Keep changes minimal, verify against the actual code, and follow the boundaries below.

## Project overview

BLE Early ATT is a [Home Assistant](https://www.home-assistant.io/) custom integration (HACS). Some Bluetooth adapters on USB, built-in ones too, deliver the first data packet of a new LE link before the event that reports the link. The Linux kernel drops that packet. When the packet is an ATT Exchange MTU Request, nobody answers it, and some devices then stay silent. This integration reads the HCI monitor channel of the host and sends the missing ATT Exchange MTU Response through a raw HCI socket. It needs Linux and the `CAP_NET_RAW` capability.

Read `.claude/memory/MEMORY.md` before you start. It links the facts behind the design. Examples are the root cause, the rules of the fix, the traps of Home Assistant and of the tests, and the live check. When your work touches a topic of a line, read the file of that line. `README.md` explains the problem to a user.

This is a HACS integration, **not** a standalone Python library.

## Repository layout

- `custom_components/ble_early_att/` — the integration package (domain: `ble_early_att`): `watcher.py` (pure logic, no I/O), `monitor.py` (sockets and timers), `config_flow.py`, `diagnostics.py`, `sensor.py`.
- `tests/` — pytest suite (`pytest-asyncio`, `pytest-homeassistant-custom-component`).
- `conftest.py` — loads the Home Assistant test plugin, also on Windows (see "Testing").
- `script/update_version.py` — bumps the version (see gotcha below).
- `plans/` — the plans. Git ignores this folder.
- `.claude/memory/` — the project memory. Git tracks it, and `CLAUDE.md` imports its index.
- `justfile` — canonical task runner. `.ruff.toml`, `.pre-commit-config.yaml`, `pyproject.toml` — tooling config.
- `.github/workflows/` — `validate.yml` (hassfest and HACS), `checks.yml` (pre-commit) and `release_draft.yml` (release drafter).

## Dev environment & commands

The project uses **[uv](https://docs.astral.sh/uv/)**. Run everything through `uv run` so the project virtualenv is used. Do **not** `cd` into subdirectories before running commands — run them from the repo root.

Use the `just` recipes. The `justfile` shows what each recipe runs.

- `just install`: after a clone, and after a change of the dependencies.
- `just upgrade`: when you upgrade all dependencies.
- `just lint`: after each code change.
- `just test`: after each change.
- `just cov`: when you add or change tests, to see the lines of each module that no test runs. Keep each module above 95%. The recipe fails when the total is below 95%, but it does not check each module, so read the table. `[tool.coverage.report]` in `pyproject.toml` excludes the same lines as Home Assistant core, for example `raise NotImplementedError`.
- `just pre`: before you finish a change.
- `just pre-update`: when you update the versions of the pre-commit hooks.
- `just version X.Y.Z`: when you change the version.

Run any ad-hoc Python via `uv run python ...`.

The pre-commit hooks also run the full test suite, so each commit runs it. They also run the `ty` type checker on the files of `[tool.ty.src]` in `pyproject.toml`, which is `custom_components` only, because the tests use mocks and wrong values on purpose. Fix a type error instead of adding a `ty:ignore` comment.

## Code style & conventions

- **Python 3.14+ only.** `requires-python = ">=3.14.2"` (tracking Home Assistant core), and ruff `target-version = "py314"`. You may freely use the newest idioms.
- **No `from __future__ import annotations`.** Annotations are deferred by default on 3.14; the import is redundant and must not be added.
- **Modern typing:** use PEP 604 unions (`str | None`) and PEP 585 builtins (`list[...]`, `dict[...]`) — not `Optional`, `Union`, `List`, `Dict`.
- **`TYPE_CHECKING` guards:** import types used only in annotations under `if TYPE_CHECKING:`. Deferred annotations make this safe.
- **Ruff with its default rule set.** Ignore a rule only with a narrowly-scoped `# noqa: RULE  # reason`. A method that overrides a method of Home Assistant gets `@override` from `typing`.
- **No reference to a plan in code.** A comment, a docstring or a name states the rule itself. It never cites a plan item, a step number or a path of `plans/`.

## Testing

- The tests run with [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component). It gives the fixtures of the Home Assistant core tests, for example `hass`. For a test that sets up the integration, use the `hass` fixture.
- Put the shared fixtures into `tests/conftest.py`. A test module never imports another test module.
- The plugin blocks sockets and DNS in each test. A test of the monitor uses a socket pair and no real Bluetooth.
- Home Assistant does not run on Windows, and the plugin does not load there on its own. The root `conftest.py` makes it load. Its docstring tells why `addopts` in `pyproject.toml` has `-p no:homeassistant`, and a comment in `pyproject.toml` tells why each test gets a new event loop. Read both before you change these settings.
- **Tests work around the code, not the reverse.** Do **not** compromise or add logic to production code merely to satisfy tests. When the test/non-production environment differs, absorb that difference inside the test code.
- Async tests use `asyncio_mode = "auto"` with a new event loop for each test.

## Agent workflow & boundaries

- **Raise open questions before implementing.** If requirements are ambiguous or a change risks the design that `.claude/memory/` describes, ask first.
- **Use a markdown checklist for multi-step work.** For any multi-stage implementation, write a checklist, tick items off as you complete them, and return the updated list.
- **Never touch git history or the index.** You are **not** allowed to run `git add`, `git commit`, `git rm`, or anything that stages or commits. Producing a diff or a commit message does not imply permission to commit.
- **Version-sync gotcha:** the version lives in **both** `pyproject.toml` (`version = "..."`) and `custom_components/ble_early_att/manifest.json` (`"version"`). They must match. Use `just version X.Y.Z` rather than editing either by hand. `tests/test_manifest.py` checks that they match.
