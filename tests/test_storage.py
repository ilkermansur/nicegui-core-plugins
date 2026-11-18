import pytest
from conftest import import_plugin

mod = import_plugin("storage-sqlite")
SqliteStorage = mod.SqliteStorage


@pytest.fixture(autouse=True)
def _in_request(monkeypatch):
    monkeypatch.setattr(mod, "in_request", lambda: True)


@pytest.fixture
def current():
    return {"id": "u1"}


@pytest.fixture
def storage(tmp_path, current):
    return SqliteStorage(tmp_path / "s.db", lambda: current["id"])


@pytest.fixture
def store(storage):
    return storage.for_plugin("p")


def test_roundtrip_and_types(store):
    store.set("a", {"x": [1, "ğ"]})
    assert store.get("a") == {"x": [1, "ğ"]}
    assert store.get("missing", 7) == 7


def test_list_prefix_sorted(store):
    for k in ["b2", "a", "b1"]:
        store.set(k, 1)
    assert store.list("b") == ["b1", "b2"] and store.list() == ["a", "b1", "b2"]


def test_delete(store):
    store.set("a", 1)
    store.delete("a")
    assert store.get("a") is None


def test_scopes_isolated(storage):
    p = storage.for_plugin("p")
    p.set("k", "u1")
    p.shared.set("k", "shared")
    p.for_user("u2").set("k", "u2")
    assert p.get("k") == "u1" and p.shared.get("k") == "shared" and p.for_user("u2").get("k") == "u2"
    assert storage.for_plugin("other").get("k") is None


def test_user_resolved_per_call(storage, current):
    p = storage.for_plugin("p")
    p.set("k", 1)
    current["id"] = "u2"
    assert p.get("k") is None


def test_outside_request_raises(storage, monkeypatch):
    monkeypatch.setattr(mod, "in_request", lambda: False)
    with pytest.raises(RuntimeError):
        storage.for_plugin("p").get("k")
    storage.for_plugin("p").shared.set("k", 1)
    storage.for_plugin("p").for_user("u1").set("k", 1)


def test_real_in_request_check_false_outside_page():
    fresh = import_plugin("storage-sqlite")
    assert fresh.in_request() is False


def test_purge(storage):
    storage.for_plugin("p").shared.set("k", 1)
    storage.for_plugin("q").shared.set("k", 1)
    storage.purge("p")
    assert storage.for_plugin("p").shared.get("k") is None and storage.for_plugin("q").shared.get("k") == 1


def test_persists_across_instances(tmp_path):
    SqliteStorage(tmp_path / "s.db", lambda: "u").for_plugin("p").shared.set("k", 1)
    assert SqliteStorage(tmp_path / "s.db", lambda: "u").for_plugin("p").shared.get("k") == 1
