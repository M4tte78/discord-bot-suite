from __future__ import annotations

import copy
from typing import Any


class MemoryStore:
    """Volatile store — development and tests."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {}

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        value = self._data.get(namespace, {}).get(key)
        return copy.deepcopy(value) if value is not None else None

    def put(self, namespace: str, key: str, value: dict[str, Any]) -> None:
        self._data.setdefault(namespace, {})[key] = copy.deepcopy(value)

    def delete(self, namespace: str, key: str) -> None:
        self._data.get(namespace, {}).pop(key, None)

    def items(self, namespace: str) -> list[tuple[str, dict[str, Any]]]:
        return [(k, copy.deepcopy(v)) for k, v in sorted(self._data.get(namespace, {}).items())]

    def close(self) -> None:
        return None
