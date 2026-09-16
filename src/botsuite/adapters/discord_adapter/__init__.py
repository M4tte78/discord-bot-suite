"""Discord adapter.

This is the only package that imports `discord`. It converts gateway objects into the
platform-neutral snapshots the engines expect, and applies the decisions they return.
"""

from .convert import to_member_snapshot, to_message_snapshot

__all__ = ["to_member_snapshot", "to_message_snapshot"]
