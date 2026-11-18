import re
import tomllib

import pytest
from conftest import PLUGINS, REPO

from ngui.manifest import load_manifest


def _need(plugin):
    if not (REPO / plugin).exists():
        pytest.skip(f"{plugin} not created yet")


@pytest.mark.parametrize("plugin", PLUGINS)
def test_locales_complete_and_equal(plugin):
    _need(plugin)
    tr = tomllib.loads((REPO / plugin / "locales" / "tr.toml").read_text())
    en = tomllib.loads((REPO / plugin / "locales" / "en.toml").read_text())
    assert tr and set(tr) == set(en)
    assert all(isinstance(v, str) for v in [*tr.values(), *en.values()])


@pytest.mark.parametrize("plugin", PLUGINS)
def test_manifest_valid(plugin):
    _need(plugin)
    m = load_manifest(REPO / plugin, expected_id=plugin)
    assert m.version == "0.1.0" and m.name.get("tr") and m.name.get("en")


def test_no_hex_colors_outside_theme():
    for p in PLUGINS:
        if p == "theme-default":
            continue
        for f in (REPO / p).rglob("*.py"):
            assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(", f.read_text()), f


def test_no_cross_plugin_imports():
    for p in PLUGINS:
        for f in (REPO / p).rglob("*.py"):
            assert not re.search(r"^\s*(from|import)\s+ngui_plugins", f.read_text(), re.M), f
