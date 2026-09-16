from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    namespace TEXT NOT NULL,
    key       TEXT NOT NULL,
    payload   TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
);
"""


class SqliteStore:
    """File-backed store. Same contract as MemoryStore, so scenarios can swap one for the
    other to demonstrate that state survives a process restart."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload FROM documents WHERE namespace = ? AND key = ?", (namespace, key)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, namespace: str, key: str, value: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO documents (namespace, key, payload) VALUES (?, ?, ?) "
            "ON CONFLICT(namespace, key) DO UPDATE SET payload = excluded.payload",
            (namespace, key, json.dumps(value, ensure_ascii=False)),
        )
        self._conn.commit()

    def delete(self, namespace: str, key: str) -> None:
        self._conn.execute(
            "DELETE FROM documents WHERE namespace = ? AND key = ?", (namespace, key)
        )
        self._conn.commit()

    def items(self, namespace: str) -> list[tuple[str, dict[str, Any]]]:
        rows = self._conn.execute(
            "SELECT key, payload FROM documents WHERE namespace = ? ORDER BY key", (namespace,)
        ).fetchall()
        return [(key, json.loads(payload)) for key, payload in rows]

    def close(self) -> None:
        self._conn.close()
