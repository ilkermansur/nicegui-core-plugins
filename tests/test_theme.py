from types import SimpleNamespace

import pytest
from conftest import REAL_ROLES, REPO, import_plugin, make_kernel

from ngui.loader import load

PLUGINS_ = ["storage-sqlite", "auth-local", "theme-default"]
ROLES_ = {r: REAL_ROLES[r] for r in ("storage", "auth", "theme")}


def test_theme_loads_as_role(home):
    k = make_kernel(home, PLUGINS_, ROLES_)
    r = load(k)
    assert r.broken == {} and "theme-default" in r.loaded
    assert k.roles["theme"].mode == "auto"  # outside a request: storage raises, falls back


def test_set_mode_validates(home):
    k = make_kernel(home, PLUGINS_, ROLES_)
    load(k)
    with pytest.raises(ValueError):
        k.roles["theme"].set_mode("blue")


def test_css_tokens_light_and_dark():
    css = (REPO / "theme-default" / "theme.css").read_text()
    for var in ["--ngui-bg", "--ngui-surface", "--ngui-border", "--ngui-text", "--ngui-muted",
                "--ngui-primary", "--ngui-success", "--ngui-warning", "--ngui-danger", "--ngui-neutral"]:
        assert css.count(var + ":") >= 2, var
    assert "body.body--dark" in css


class _Store(dict):
    writes = 0

    def set(self, key, value):
        self.writes += 1
        self[key] = value


def _theme(monkeypatch, **stored):
    mod = import_plugin("theme-default")
    monkeypatch.setattr(mod.ui, "dark_mode", lambda value: applied.append(value))
    applied = []
    store = _Store(stored)
    return mod.DefaultTheme(SimpleNamespace(storage=store)), store, applied


def test_primary_tone():
    mod = import_plugin("theme-default")
    css = (REPO / "theme-default" / "theme.css").read_text()
    assert "primary" in mod.TONES and ".ngui-tone-primary { color: var(--ngui-primary); }" in css


def test_unknown_stored_mode_falls_back_to_auto(monkeypatch):
    theme, _, _ = _theme(monkeypatch, mode="blue")
    assert theme.mode == "auto"


def test_set_mode_writes_only_on_change(monkeypatch):
    theme, store, applied = _theme(monkeypatch, mode="dark")
    theme.set_mode("dark")
    assert store.writes == 0 and applied == [True]
    theme.set_mode("light")
    assert store.writes == 1 and store["mode"] == "light" and applied == [True, False]


def test_no_unused_mode_keys():
    for lang in ("tr", "en"):
        assert "mode." not in (REPO / "theme-default" / "locales" / f"{lang}.toml").read_text()
