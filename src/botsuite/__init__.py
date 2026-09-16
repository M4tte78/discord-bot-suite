"""Discord bot suite: moderation, LLM chat and event management.

The business logic lives in `botsuite.security`, `botsuite.llm` and `botsuite.events`.
None of it imports `discord` — the library is only touched in `botsuite.adapters.discord`.
That separation is what makes `botsuite.sim` possible: the same engines can be driven by a
scripted, deterministic world instead of a live gateway connection.
"""

__version__ = "0.1.0"
