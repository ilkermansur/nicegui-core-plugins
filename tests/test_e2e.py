from types import SimpleNamespace

import pytest

from conftest import PLUGINS, REAL_ROLES, fetch

AUTH_PLUGIN = '''
class DenyingAuth:
    def current_user(self):
        return {"id": "t", "name": "Tester", "roles": []}

    def has(self, permission):
        return permission != "secret.view"


def setup(ctx):
    return DenyingAuth()
'''

PAGES_PLUGIN = '''
from nicegui import ui


def setup(ctx):
    layout = ctx.role("layout")

    @layout.page("/secret", title="Secret", permission="secret.view")
    def secret():
        ui.label("SECRET-CONTENT")

    @layout.page("/boom", title="Boom")
    def boom():
        ui.label("PARTIAL-CONTENT")
        raise RuntimeError("kaboom")
'''


def _plugin(root, pid, code, provides=""):
    d = root / pid
    d.mkdir(parents=True)
    d.joinpath("plugin.toml").write_text(
        f'id = "{pid}"\nversion = "0.1.0"\ncore = ">=1,<2"\n' + (f'provides = "{provides}"\n' if provides else ""))
    d.joinpath("__init__.py").write_text(code)
    return str(d)


@pytest.fixture
def app(home, start_app):
    proc, url = start_app(home, PLUGINS, REAL_ROLES)
    return SimpleNamespace(url=url, proc=proc, log=start_app.log)


def test_home_renders_in_layout(app):
    html = fetch(app.url + "/")
    assert "Ana sayfa" in html and "ngui" in html


def test_store_page_renders(app):
    html = fetch(app.url + "/store")
    assert "Plugin Mağazası" in html and "storage-sqlite" in html


def test_unknown_path_is_404_not_recovery(app):
    assert "Eksik rol" not in fetch(app.url + "/nope", ok_statuses=(404,))


def test_english_default_lang(home, start_app):
    _, url = start_app(home, PLUGINS, REAL_ROLES, default_lang="en")
    assert "Home" in fetch(url + "/") and "Plugin Store" in fetch(url + "/store")


def test_no_broken_plugins_logged(app):
    fetch(app.url + "/")
    fetch(app.url + "/store")
    assert "setup failed" not in app.log() and "Traceback" not in app.log()


def test_forbidden_and_failing_pages_keep_the_frame(home, start_app, tmp_path):
    links = {"test-auth": _plugin(tmp_path / "extra", "test-auth", AUTH_PLUGIN, "auth"),
             "test-pages": _plugin(tmp_path / "extra", "test-pages", PAGES_PLUGIN)}
    roles = REAL_ROLES | {"auth": "test-auth"}
    _, url = start_app(home, [*PLUGINS, "test-pages"], roles, links=links)

    forbidden = fetch(url + "/secret")
    assert "Bu sayfayı görüntüleme yetkiniz yok." in forbidden
    assert "SECRET-CONTENT" not in forbidden and "Traceback" not in forbidden

    boom = fetch(url + "/boom")
    assert "Bu alan çizilirken bir hata oluştu." in boom and "kaboom" not in boom
    assert "ngui" in boom and "Ana sayfa" in boom  # frame intact
