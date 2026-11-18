import pytest
from conftest import REAL_ROLES, REPO, make_kernel

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
