import json
import sqlite3
import threading
from pathlib import Path
from typing import Callable

from nicegui.slot import Slot


class StorageContextError(RuntimeError):
    pass


def in_request() -> bool:
    return bool(Slot.get_stack())


class Store:
    def __init__(self, storage: "SqliteStorage", plugin: str, scope: Callable[[], str] | str):
        self._s, self._plugin, self._scope = storage, plugin, scope
        self.shared = self if scope == "shared" else Store(storage, plugin, "shared")

    def _sc(self) -> str:
        return self._scope() if callable(self._scope) else self._scope

    def _run(self, sql: str, args: tuple = (), write: bool = False) -> list:
        with self._s._lock:
            rows = self._s._db.execute(sql, args).fetchall()
            if write:
                self._s._db.commit()
            return rows

    def get(self, key, default=None):
        rows = self._run("SELECT value FROM kv WHERE plugin=? AND scope=? AND key=?",
                         (self._plugin, self._sc(), key))
        return json.loads(rows[0][0]) if rows else default

    def set(self, key, value):
        self._run("INSERT OR REPLACE INTO kv VALUES (?,?,?,?)",
                  (self._plugin, self._sc(), key, json.dumps(value, ensure_ascii=False)), write=True)

    def delete(self, key):
        self._run("DELETE FROM kv WHERE plugin=? AND scope=? AND key=?",
                  (self._plugin, self._sc(), key), write=True)

    def list(self, prefix=""):
        rows = self._run("SELECT key FROM kv WHERE plugin=? AND scope=?", (self._plugin, self._sc()))
        return sorted(r[0] for r in rows if r[0].startswith(prefix))

    def for_user(self, user_id):
        return Store(self._s, self._plugin, f"user:{user_id}")


class SqliteStorage:
    def __init__(self, db_path: Path, user_id: Callable[[], str],
                 no_request_msg: Callable[[], str] = lambda: "no request context"):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._user_id, self._msg = user_id, no_request_msg
        self._lock = threading.Lock()
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS kv(plugin TEXT, scope TEXT, key TEXT, value TEXT, "
                         "PRIMARY KEY(plugin, scope, key))")
        self._db.commit()

    def _current_scope(self) -> str:
        if not in_request():
            raise StorageContextError(self._msg())
        return f"user:{self._user_id()}"

    def for_plugin(self, plugin_id: str) -> Store:
        return Store(self, plugin_id, self._current_scope)

    def purge(self, plugin_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM kv WHERE plugin=?", (plugin_id,))
            self._db.commit()


def setup(ctx) -> SqliteStorage:
    return SqliteStorage(ctx.kernel.home.data_dir / "storage.sqlite3",
                         lambda: ctx.role("auth").current_user()["id"],
                         lambda: ctx.t("err.no_request"))
