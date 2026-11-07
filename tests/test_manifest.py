"""Tests of manifest.json."""

import json
import tomllib
from pathlib import Path

from custom_components.ble_early_att.const import DOMAIN

ROOT = Path(__file__).parent.parent
MANIFEST = ROOT / "custom_components" / DOMAIN / "manifest.json"


def test_manifest_has_the_domain_of_const():
    """The manifest names the domain that const.py names."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["domain"] == DOMAIN


def test_manifest_version_is_the_version_of_pyproject():
    """The version lives in two files, and the two must agree."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert manifest["version"] == pyproject["project"]["version"]
