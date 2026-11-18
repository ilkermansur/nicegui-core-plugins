from types import SimpleNamespace

import pytest
from conftest import PLUGINS, REAL_ROLES, fetch, import_plugin, make_kernel

from ngui import NguiError
from ngui.loader import load
from ngui.manager import Manager

store = import_plugin("store")
run_action, role_options = store.run_action, store.role_options


class FakeManager:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def __getattr__(self, name):
        def f(*a):
            self.calls.append((name, a))
            if self.fail == name:
                raise NguiError("err.git", detail="offline")
        return f


def test_run_action_success_syncs_deps():
    m = FakeManager()
    assert run_action(m, "add", "notes") is None
    assert m.calls == [("add", ("notes",)), ("sync_deps", ())]


def test_run_action_error_returns_key_and_vars():
    assert run_action(FakeManager(fail="add"), "add", "x") == ("err.git", {"detail": "offline"})


def test_run_action_error_skips_sync_deps():
    m = FakeManager(fail="remove")
    run_action(m, "remove", "x")
    assert m.calls == [("remove", ("x",))]


def test_run_action_deps_error():
    assert run_action(FakeManager(fail="sync_deps"), "enable", "x")[0] == "err.git"


def test_run_action_rejects_unknown_action():
    with pytest.raises(ValueError):
        run_action(FakeManager(), "rm_rf", "/")


def test_role_options_lists_providers_only():
    ms = {"a": SimpleNamespace(provides="theme"), "b": SimpleNamespace(provides="auth")}
    assert role_options(ms, "theme", "a", str.upper) == {"a": "A"}


def test_role_options_keeps_assigned_plugin_without_manifest():
    ms = {"a": SimpleNamespace(provides="theme")}
    assert role_options(ms, "theme", "broken", str.upper) == {"a": "A", "broken": "broken"}
    assert role_options(ms, "auth", None, str.upper) == {}


def test_store_registers_page(home):
    k = make_kernel(home, PLUGINS, REAL_ROLES)
    k.manager = Manager(home)
    r = load(k)
    assert "store" in r.loaded and any(e.path == "/store" for e in k.roles["layout"].pages)


def test_store_page_renders(home, start_app):
    _, url = start_app(home, PLUGINS, REAL_ROLES)
    body = fetch(url + "/store")
    assert "Plugin Mağazası" in body and "storage-sqlite" in body and "Çalışıyor" in body
    assert "Bu alan çizilirken bir hata oluştu." not in body and "yetkiniz yok" not in body
