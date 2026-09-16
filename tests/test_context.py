from __future__ import annotations

from botsuite.llm.context import ContextWindow, Conversation, estimate_tokens


def test_system_prompt_is_always_first():
    window = ContextWindow("système", budget_tokens=1000)
    conversation = Conversation(key="c")
    conversation.add("user", "bonjour")
    messages = window.build(conversation)
    assert messages[0] == {"role": "system", "content": "système"}


def test_oldest_turns_are_dropped_first():
    window = ContextWindow("sys", budget_tokens=40)  # ~160 characters
    conversation = Conversation(key="c")
    for i in range(20):
        conversation.add("user", f"message numéro {i} " * 3)
    messages = window.build(conversation)
    kept = [m["content"] for m in messages[1:]]
    assert kept, "au moins un tour doit survivre"
    assert "19" in kept[-1]
    assert not any("0 " in c and "numéro 0" in c for c in kept)


def test_budget_is_respected():
    budget = 60
    window = ContextWindow("sys", budget_tokens=budget)
    conversation = Conversation(key="c")
    for i in range(40):
        conversation.add("assistant", f"réponse {i} " * 5)
    total = sum(estimate_tokens(m["content"]) for m in window.build(conversation))
    assert total <= budget


def test_reset_clears_history():
    conversation = Conversation(key="c")
    conversation.add("user", "a")
    conversation.reset()
    assert conversation.turns == []
