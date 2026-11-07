---
name: release-ci
description: "Read this file before you publish a release, change a workflow, or act on a Dependabot alert or PR."
metadata:
  type: reference
---

## CI

- `checks.yml` and `validate.yml` skip a push that changes only `**.md` or `**.png` files. Such a push runs only the release drafter.
- `checks.yml` runs pre-commit on all files, and pre-commit runs the full test suite on Linux.

## Releases

- The release drafter names the draft and its tag `$NEXT_PATCH_VERSION`. Each push to `main` updates the draft.
- Its template has sample sections, for example "Breaking 1: Description of breaking change 1."
- Just before you publish, set the tag and the title of the draft to the version of `manifest.json`. Then replace the sample sections with the real changes.

## Dependabot

- Dependabot security updates are on for this repository.
- The integration has no runtime requirements (`"requirements": []` in `manifest.json`). Each package of `uv.lock` serves only the tests and the tools, so an alert for it does not reach a user.
- `pytest-homeassistant-custom-component` pins one `homeassistant` release, and `homeassistant` pins packages such as `pillow`. A Dependabot PR that raises such a pin makes uv lower the whole test stack, for example to pytest 6.2.2, and the Checks workflow fails.
- Close such a PR, and dismiss its alerts with the reason `tolerable_risk`. The pin moves with the next release of `pytest-homeassistant-custom-component`. Then run `just upgrade`.
