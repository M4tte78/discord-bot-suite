from __future__ import annotations

from .base import KeyValueStore
from .memory import MemoryStore
from .sqlite import SqliteStore


def build_store(url: str) -> KeyValueStore:
    """`memory://` or `sqlite:///relative/path.sqlite3`."""
    if url in ("", "memory://"):
        return MemoryStore()
    if url.startswith("sqlite:///"):
        return SqliteStore(url[len("sqlite:///") :])
    if url.startswith("sqlite://:memory:"):
        return SqliteStore(":memory:")
    raise ValueError(f"STORAGE_URL non supporté : {url!r}")
