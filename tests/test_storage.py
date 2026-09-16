from __future__ import annotations

import pytest

from botsuite.storage import MemoryStore, SqliteStore, build_store


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        yield MemoryStore()
    else:
        s = SqliteStore(tmp_path / "test.sqlite3")
        yield s
        s.close()


def test_roundtrip(store):
    store.put("ns", "k", {"a": 1, "accents": "é"})
    assert store.get("ns", "k") == {"a": 1, "accents": "é"}


def test_missing_key_returns_none(store):
    assert store.get("ns", "nope") is None


def test_overwrite(store):
    store.put("ns", "k", {"v": 1})
    store.put("ns", "k", {"v": 2})
    assert store.get("ns", "k")["v"] == 2


def test_namespaces_are_isolated(store):
    store.put("a", "k", {"v": 1})
    assert store.get("b", "k") is None
    assert [k for k, _ in store.items("a")] == ["k"]


def test_delete(store):
    store.put("ns", "k", {"v": 1})
    store.delete("ns", "k")
    assert store.get("ns", "k") is None


def test_memory_store_returns_copies():
    store = MemoryStore()
    store.put("ns", "k", {"v": [1]})
    fetched = store.get("ns", "k")
    fetched["v"].append(2)
    assert store.get("ns", "k")["v"] == [1]


def test_sqlite_file_survives_reopen(tmp_path):
    path = tmp_path / "persist.sqlite3"
    first = SqliteStore(path)
    first.put("ns", "k", {"v": 42})
    first.close()
    second = SqliteStore(path)
    assert second.get("ns", "k") == {"v": 42}
    second.close()


def test_build_store_factory(tmp_path):
    assert isinstance(build_store("memory://"), MemoryStore)
    store = build_store(f"sqlite:///{tmp_path / 'x.sqlite3'}")
    assert isinstance(store, SqliteStore)
    store.close()
    with pytest.raises(ValueError):
        build_store("postgres://nope")
