import sys

from conftest import make_kernel

from ngui.loader import load

PLUGINS_ = ["storage-sqlite", "auth-local"]
ROLES_ = {"storage": "storage-sqlite", "auth": "auth-local"}


def _loaded(home):
    k = make_kernel(home, PLUGINS_, ROLES_)
    return k, load(k)


def test_local_user_and_permissions(home):
    k, r = _loaded(home)
    assert r.broken == {} and {"storage-sqlite", "auth-local"} <= set(r.loaded)
    auth = k.roles["auth"]
    user = auth.current_user()
    assert user["id"] == "local" and user["roles"] == ["admin"] and user["name"] == "Yönetici"
    assert auth.has("anything") is True


def test_user_name_translated_per_call(home):
    k, _ = _loaded(home)
    k.i18n.lang_getter = lambda: "en"
    assert k.roles["auth"].current_user()["name"] == "Administrator"
    k.i18n.lang_getter = lambda: "tr"
    assert k.roles["auth"].current_user()["name"] == "Yönetici"


def test_storage_uses_auth_user(home, monkeypatch):
    k, _ = _loaded(home)
    monkeypatch.setattr(sys.modules["ngui_plugins.storage_sqlite"], "in_request", lambda: True)
    k.roles["storage"].for_plugin("p").set("k", 1)
    assert k.roles["storage"].for_plugin("p").for_user("local").get("k") == 1


def test_lang_reader_falls_back_outside_request(home, monkeypatch):
    k, _ = _loaded(home)
    storage = k.roles["storage"]
    monkeypatch.setattr(sys.modules["ngui_plugins.storage_sqlite"], "in_request", lambda: True)
    storage.for_plugin("core").set("lang", "en")
    k.i18n.lang_getter = lambda: storage.for_plugin("core").get("lang")
    assert k.i18n.current_lang() == "en"
    monkeypatch.setattr(sys.modules["ngui_plugins.storage_sqlite"], "in_request", lambda: False)
    assert k.i18n.current_lang() == "tr"
