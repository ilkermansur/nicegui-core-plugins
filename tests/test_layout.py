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


def test_title_that_raises_falls_back_to_path(loaded):
    layout = loaded.roles["layout"]

    def boom():
        raise RuntimeError("bad title")

    layout.page("/bad", boom)(lambda: None)
    assert layout._text(layout.pages[-1]) == "/bad"


def test_permission_check_that_raises_is_not_allowed(loaded):
    layout = loaded.roles["layout"]
    layout.page("/p", "P", permission="x")(lambda: None)
    loaded.roles["auth"].has = lambda p: 1 / 0
    assert layout._allowed(layout.pages[-1]) is False


DEMO_INIT = '''import asyncio

from nicegui import ui


def setup(ctx):
    @ctx.role("layout").page("/async", "Async", icon="bolt")
    async def page():
        await asyncio.sleep(0)
        ui.label("async-page-rendered")
'''


def test_async_page_is_awaited(home, tmp_path, start_app, monkeypatch):
    import conftest
    demo = tmp_path / "demo"
    (demo / "locales").mkdir(parents=True)
    names = '{ tr = "demo", en = "demo" }'
    (demo / "plugin.toml").write_text(f'id = "demo"\nversion = "0.1.0"\ncore = ">=1,<2"\n'
                                      f'name = {names}\ndescription = {names}\n')
    (demo / "__init__.py").write_text(DEMO_INIT)
    orig = conftest._write_config

    def write(h, plugins, roles):
        cfg = orig(h, plugins, roles)
        cfg.links["demo"] = str(demo)
        h.save_config(cfg)
        return cfg

    monkeypatch.setattr(conftest, "_write_config", write)
    _, url = start_app(home, [*PLUGINS_, "demo"], REAL_ROLES)
    body = fetch(url + "/async")
    assert "async-page-rendered" in body and "ngui-rail" in body
