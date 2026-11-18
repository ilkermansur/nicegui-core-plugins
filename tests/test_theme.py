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
                "--ngui-primary", "--ngui-success", "--ngui-warning", "--ngui-danger", "--ngui-neutral",
                "--ngui-chart-1", "--ngui-chart-6", "--ngui-chart-grid"]:
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
    monkeypatch.setattr(mod.ui, "add_body_html", lambda code: early.append(code))
    applied, early = [], []
    _theme.early = early
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


def test_dark_primary_beats_the_inline_light_value():
    # app.colors() writes the light --q-primary inline; dark mode must still win, and primary
    # buttons need dark text on the light primary
    css = (REPO / "theme-default" / "theme.css").read_text()
    assert "--q-primary: var(--ngui-primary) !important" in css
    assert "body.body--dark .q-btn.bg-primary .q-btn__content" in css


@pytest.mark.parametrize("mode,condition", [
    ("dark", "true"), ("light", "false"), ("auto", "matchMedia('(prefers-color-scheme: dark)').matches")])
def test_dark_class_is_set_before_the_first_paint(monkeypatch, mode, condition):
    # Quasar adds body--dark only after its JavaScript runs; without this the page paints light first
    theme, _, _ = _theme(monkeypatch, mode=mode)
    theme.set_mode(mode)
    assert _theme.early == [f"<script>if ({condition}) document.body.classList.add('body--dark')</script>"]


def _rendered_texts(monkeypatch, build):
    # a tiny fake ui that records labels, icons and classes
    mod = import_plugin("theme-default")
    texts, classes = [], []

    class El:
        def __init__(self, text=""):
            texts.append(text)

        def classes(self, c):
            classes.append(c)
            return self

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(mod.ui, "label", lambda text="": El(text))
    monkeypatch.setattr(mod.ui, "icon", lambda name: El(name))
    monkeypatch.setattr(mod.ui, "card", lambda: El())
    monkeypatch.setattr(mod.ui, "row", lambda: El())
    monkeypatch.setattr(mod.ui, "column", lambda: El())
    build(mod.DefaultTheme(SimpleNamespace(storage={})))
    return texts, " ".join(classes)


def test_kpi_delta_and_trend(monkeypatch):
    texts, classes = _rendered_texts(monkeypatch, lambda th: th.kpi("Orders", 332, delta="16 vs yesterday", trend="up"))
    assert "16 vs yesterday" in texts and "arrow_drop_up" in texts and "ngui-trend-up" in classes


def test_kpi_without_delta_has_no_delta_row(monkeypatch):
    texts, classes = _rendered_texts(monkeypatch, lambda th: th.kpi("Orders", 332))
    assert "ngui-kpi-delta" not in classes


def test_card_meta_and_header_actions(monkeypatch):
    called = []
    texts, _ = _rendered_texts(monkeypatch, lambda th: (th.card("Revenue", meta="Last 30 days"),
                                                        th.page_header("Dashboard", "Overview", actions=lambda: called.append(1))))
    assert "Last 30 days" in texts and called == [1]
