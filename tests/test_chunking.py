from __future__ import annotations

from botsuite.llm.chunking import split_message


def test_short_message_is_untouched():
    assert split_message("court") == ["court"]


def test_long_prose_is_split_under_the_limit():
    text = "\n\n".join("phrase " * 40 for _ in range(20))
    chunks = split_message(text, limit=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)


def test_code_fence_is_never_broken():
    code = "```python\n" + "\n".join(f"line_{i} = {i}" for i in range(400)) + "\n```"
    chunks = split_message(f"Voici le code :\n\n{code}\n\nFin.", limit=600)
    assert all(len(c) <= 600 for c in chunks)
    for chunk in chunks:
        assert chunk.count("```") % 2 == 0, chunk[:80]


def test_a_single_very_long_line_is_hard_split():
    chunks = split_message("x" * 5000, limit=1000)
    assert len(chunks) == 5
    assert all(len(c) == 1000 for c in chunks)


def test_no_content_is_lost_in_prose():
    text = "\n\n".join(f"paragraphe numéro {i} " * 10 for i in range(30))
    chunks = split_message(text, limit=400)
    joined = "".join(chunks).replace("\n", "").replace(" ", "")
    assert joined == text.replace("\n", "").replace(" ", "")
