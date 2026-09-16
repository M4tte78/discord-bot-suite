"""Storage contract.

Deliberately minimal: a namespaced key/value store of JSON documents. Everything the bots
need to survive a restart (event state, signups, leaderboards, per-guild config) fits this
shape, and a narrow contract keeps swapping SQLite for PostgreSQL a one-class change.
"""

from __future__ import annotations

from typing import Any, Protocol


class KeyValueStore(Protocol):
    def get(self, namespace: str, key: str) -> dict[str, Any] | None: ...

    def put(self, namespace: str, key: str, value: dict[str, Any]) -> None: ...

    def delete(self, namespace: str, key: str) -> None: ...

    def items(self, namespace: str) -> list[tuple[str, dict[str, Any]]]: ...

    def close(self) -> None: ...
