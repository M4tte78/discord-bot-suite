"""Content filtering, with normalisation first.

Naive keyword filters are trivially bypassed on Discord: Cyrillic look-alikes
(`ѕсаm`), zero-width joiners (`s​cam`), leetspeak (`5c4m`), letter spacing
(`s c a m`) and character repetition (`scaaaam`) all defeat a plain `in` check.

`normalize()` folds those variants back to a canonical form *before* any rule is applied,
and `collapsed()` additionally removes whitespace so that spaced-out payloads are caught.
Rules therefore stay short and readable.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..models import Action, Verdict

ZERO_WIDTH = "​‌‍⁠﻿­"

#: Small confusables table — the subset actually seen in the wild on community servers.
HOMOGLYPHS = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ѕ": "s",
        "ԁ": "d",
        "ɡ": "g",
        "ⅼ": "l",
        "ᴏ": "o",
        "ʀ": "r",
        "α": "a",
        "ε": "e",
        "ο": "o",
        "ρ": "p",
        "τ": "t",
        "ν": "v",
    }
)

LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)

_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")
_REPEATS = re.compile(r"(.)\1{2,}")
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Canonical lowercase form used for rule matching."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.translate({ord(ch): None for ch in ZERO_WIDTH})
    text = text.lower()
    text = text.translate(HOMOGLYPHS)
    text = text.translate(LEET)
    text = _NON_ALNUM.sub(" ", text)
    text = _REPEATS.sub(r"\1\1", text)
    return _SPACES.sub(" ", text).strip()


def collapsed(text: str) -> str:
    """`normalize()` without any whitespace — defeats `f r e e   n i t r o`."""
    return normalize(text).replace(" ", "")


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: str
    action: Action = Action.DELETE
    reason: str = ""
    #: Match against the whitespace-free form as well as the normalised one.
    match_collapsed: bool = True


DEFAULT_RULES: tuple[Rule, ...] = (
    Rule(
        name="scam.free_nitro",
        pattern=r"free ?nitro|nitro ?gratuit|steam ?gift",
        action=Action.DELETE,
        reason="arnaque au cadeau (pattern nitro/steam)",
    ),
    Rule(
        name="scam.credentials",
        pattern=r"(login|connecte[rz]? ?vous|verify) ?(your)? ?(account|compte)",
        action=Action.DELETE,
        reason="tentative d'hameçonnage de compte",
    ),
    Rule(
        name="scam.crypto_airdrop",
        pattern=r"airdrop|double ?your ?(btc|eth)|x2 ?crypto",
        action=Action.DELETE,
        reason="arnaque crypto",
    ),
)


class ContentFilter:
    def __init__(self, rules: tuple[Rule, ...] | list[Rule] = DEFAULT_RULES) -> None:
        self.rules = tuple(rules)
        self._compiled = [(r, re.compile(r.pattern, re.IGNORECASE)) for r in self.rules]

    def check(self, text: str) -> list[Verdict]:
        norm = normalize(text)
        flat = collapsed(text)
        verdicts: list[Verdict] = []
        for rule, regex in self._compiled:
            hit = regex.search(norm)
            surface = "normalized"
            if hit is None and rule.match_collapsed:
                hit = regex.search(flat)
                surface = "collapsed"
            if hit:
                verdicts.append(
                    Verdict(
                        action=rule.action,
                        rule=f"content.{rule.name}",
                        reason=rule.reason or f"règle {rule.name}",
                        score=1.0,
                        details={"match": hit.group(0), "surface": surface},
                    )
                )
        return verdicts
