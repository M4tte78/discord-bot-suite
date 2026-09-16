from __future__ import annotations

import pytest

from botsuite.security.content import ContentFilter, Rule, collapsed, normalize

FILTER = ContentFilter()

BYPASS_ATTEMPTS = [
    "free nitro",
    "FREE NITRO",
    "fr3e n1tro",
    "f r e e   n i t r o",
    "freeee nitrooo",
    "fr​ee nit​ro",  # zero-width spaces
    "frее nitrо",  # Cyrillic е and о
    "frée nitrö",  # combining accents
]


@pytest.mark.parametrize("text", BYPASS_ATTEMPTS)
def test_obfuscated_scam_is_caught(text):
    verdicts = FILTER.check(text)
    assert verdicts, f"non détecté : {text!r}"
    assert verdicts[0].rule == "content.scam.free_nitro"


@pytest.mark.parametrize(
    "text",
    [
        "je viens de finir le niveau",
        "quelqu'un a un lien vers la doc ?",
        "le nitro coûte cher",  # mentions nitro but is not the scam pattern
    ],
)
def test_normal_messages_are_not_flagged(text):
    assert FILTER.check(text) == []


def test_normalize_is_idempotent():
    once = normalize("Fr3e  N1TRO!!!")
    assert normalize(once) == once


def test_collapsed_removes_spacing():
    assert collapsed("f r e e") == "free"


def test_custom_rules():
    custom = ContentFilter([Rule(name="test", pattern=r"interdit", reason="mot interdit")])
    assert custom.check("mot InTeRdIt ici")[0].rule == "content.test"
    assert custom.check("rien") == []
