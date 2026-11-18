from types import SimpleNamespace

import pytest
from conftest import PLUGINS, REAL_ROLES, REPO, fetch, import_plugin, make_kernel

from ngui import NguiError
from ngui.loader import load
from ngui.manager import Manager, PluginStatus

store = import_plugin("store")
run_action, role_options, row_actions = store.run_action, store.role_options, store.row_actions


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


def _row(pid="x", source="repo", enabled=True, role=""):
    return PluginStatus(pid, source, enabled, role, "", "")


def test_row_actions_repo_plugin():
    assert row_actions(_row(), "store") == ["disable", "update", "rollback", "remove", "purge"]
    assert row_actions(_row(enabled=False), "store")[0] == "enable"


def test_row_actions_role_core_and_link():
    assert row_actions(_row(role="theme"), "store") == ["update", "rollback", "purge"]
    assert row_actions(_row(source="core"), "store") == ["disable", "purge"]
    assert row_actions(_row(source="link", role="auth"), "store") == ["purge"]


def test_row_actions_never_disable_or_remove_the_store_itself():
    assert row_actions(_row("store"), "store") == ["update", "rollback", "purge"]
    assert row_actions(_row("store", source="core"), "store") == ["purge"]


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


class FakeControl:
    enabled = True

    def set_enabled(self, value):
        self.enabled = value


def _page():
    ctx = SimpleNamespace(t=lambda k, **v: k, role=lambda r: None, kernel=SimpleNamespace(manager=None))
    return store.StorePage(ctx)


def test_lock_without_spinner_and_late_controls_reenable():
    page = _page()
    early, off = FakeControl(), FakeControl()
    page.controls = [early]
    page._lock(True)  # no spinner rendered: must not raise
    assert not early.enabled and page.locked
    late = FakeControl()  # a catalog button created while the action runs
    late.set_enabled(False)
    page.controls += [late, off]
    page.off.append(off)
    page._lock(False)
    assert early.enabled and late.enabled and not off.enabled and not page.locked


def test_url_install_confirms_with_the_url():
    import asyncio
    page, calls = _page(), []

    async def act(*args, **kw):
        calls.append((args, kw))
    page.act = act
    asyncio.run(page.install("  "))
    asyncio.run(page.install(" https://x/nicegui-plugin-a "))
    assert calls == [(("add", "https://x/nicegui-plugin-a"), {"confirm": "confirm.install"})]


def test_core_actions_include_rollback_with_confirm():
    assert store.CORE_ACTIONS == {"update.core": ("update", None), "rollback.core": ("rollback", "confirm.rollback")}


def test_core_store_shows_core_commit_rollback_and_description(home, start_app):
    import shutil
    import subprocess

    from ngui.config import CORE_KEY, LockEntry
    core = home.repos_dir / CORE_KEY
    for p in PLUGINS:
        shutil.copytree(REPO / p, core / p)
    for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"]):
        subprocess.run(["git", *cmd], cwd=core, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=core, check=True, capture_output=True, text=True).stdout
    home.save_lock({CORE_KEY: LockEntry("file:///core", sha.strip())})
    _, url = start_app(home, PLUGINS, REAL_ROLES, linked=False)
    body = fetch(url + "/store")
    assert "Core'u geri al" in body and "Core'u güncelle" in body and sha[:7] in body
    assert "SQLite depolama" in body and "Eklenti verisini SQLite dosyasında saklar." in body
