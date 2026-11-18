import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest

from ngui import LOCALES_DIR
from ngui.bus import Bus, Services
from ngui.config import Config, Home
from ngui.context import Kernel
from ngui.i18n import I18n

REPO = Path(__file__).resolve().parent.parent
PLUGINS = ["storage-sqlite", "auth-local", "theme-default", "layout-sidebar", "store"]
REAL_ROLES = {"storage": "storage-sqlite", "auth": "auth-local",
              "theme": "theme-default", "layout": "layout-sidebar"}


@pytest.fixture
def home(tmp_path):
    return Home(tmp_path / "home")


def _write_config(home: Home, plugins: list[str], roles: dict[str, str]) -> Config:
    cfg = Config(core_repo="", enabled=list(plugins), roles=dict(roles),
                 links={p: str(REPO / p) for p in plugins})
    home.save_config(cfg)
    return cfg


def make_kernel(home: Home, plugins: list[str], roles: dict[str, str]) -> Kernel:
    cfg = _write_config(home, plugins, roles)
    i18n = I18n("tr")
    i18n.load("core", LOCALES_DIR)
    return Kernel(home, cfg, Bus(), Services(), i18n)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _is_up(url: str) -> bool:
    try:
        urlopen(url + "/", timeout=1).close()
        return True
    except HTTPError:
        return True
    except (URLError, OSError):
        return False


def fetch(url: str) -> str:
    """HTTP body as text (NiceGUI 4 embeds its JSON payload in the page body)."""
    try:
        with urlopen(url, timeout=5) as r:
            return r.read().decode()
    except HTTPError as e:
        return e.read().decode()


@pytest.fixture
def start_app(tmp_path):
    procs = []
    log_path = tmp_path / "app.log"

    def start(home: Home, plugins: list[str], roles: dict[str, str], env: dict[str, str] | None = None):
        _write_config(home, plugins, roles)
        port = _free_port()
        full = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
        full.update(env or {}, NGUI_HOME=str(home.root), NGUI_PORT=str(port), NGUI_CORE_REPO="")
        with log_path.open("ab") as log:
            proc = subprocess.Popen([sys.executable, "-m", "ngui", "run"], cwd=REPO, env=full,
                                    stdout=log, stderr=subprocess.STDOUT)
        procs.append(proc)
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 20
        while proc.poll() is None and not _is_up(url) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert proc.poll() is None and _is_up(url), (
            f"app failed to start; output:\n{log_path.read_text(errors='replace')}")
        return proc, url

    yield start
    for proc in procs:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
