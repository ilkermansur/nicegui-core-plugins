import pytest
from conftest import REAL_ROLES, fetch, make_kernel

from ngui.loader import load

PLUGINS_ = ["storage-sqlite", "auth-local", "theme-default", "layout-sidebar"]


@pytest.fixture
def loaded(home):
    k = make_kernel(home, PLUGINS_, REAL_ROLES)
    load(k)
    return k


def test_layout_loads_with_all_roles(home):
    k = make_kernel(home, PLUGINS_, REAL_ROLES)
    r = load(k)
    assert r.missing_roles == [] and r.broken == {}


def test_unknown_slot_is_ignored(loaded):
    loaded.roles["layout"].add("sidebar", lambda: None)
    assert "sidebar" not in loaded.roles["layout"].slots


def test_known_slot_keeps_builder(loaded):
    builder = lambda: None  # noqa: E731
    loaded.roles["layout"].add("nav", builder)
    assert loaded.roles["layout"].slots["nav"] == [builder]


def test_page_registers_entry_and_returns_fn(loaded):
    fn = lambda: None  # noqa: E731
    assert loaded.roles["layout"].page("/x", lambda: "X", icon="star", permission="p")(fn) is fn
    e = loaded.roles["layout"].pages[-1]
    assert (e.path, e.icon, e.permission) == ("/x", "star", "p")


def test_home_page_renders_shell(home, start_app):
    _, url = start_app(home, PLUGINS_, REAL_ROLES)
    body = fetch(url + "/")
    assert "ngui-app-name" in body and "ngui-rail" in body and "Ana sayfa" in body
