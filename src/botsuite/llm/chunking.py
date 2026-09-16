"""Splitting a model answer into Discord-sized messages.

Discord rejects any message over 2000 characters. Cutting blindly every 2000 characters
breaks code fences in half, which renders as garbage. This splitter walks the text as an
alternating sequence of fenced blocks and prose, and re-opens the fence on every chunk of
a long block.
"""

from __future__ import annotations

import re

LIMIT = 2000
_FENCE = re.compile(r"(```[\w+-]*\n.*?(?:```|\Z))", re.DOTALL)


def _hard_split(text: str, limit: int) -> list[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _split_prose(text: str, limit: int) -> list[str]:
    chunks: list[str] = []
    buffer = ""
    for paragraph in text.split("\n\n"):
        candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        if len(candidate) <= limit:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
            buffer = ""
        if len(paragraph) <= limit:
            buffer = paragraph
            continue
        # Paragraph alone is too long: fall back to lines, then to a hard cut.
        line_buffer = ""
        for line in paragraph.split("\n"):
            candidate = f"{line_buffer}\n{line}" if line_buffer else line
            if len(candidate) <= limit:
                line_buffer = candidate
            else:
                if line_buffer:
                    chunks.append(line_buffer)
                line_buffer = ""
                if len(line) <= limit:
                    line_buffer = line
                else:
                    chunks.extend(_hard_split(line, limit))
        if line_buffer:
            buffer = line_buffer
    if buffer:
        chunks.append(buffer)
    return chunks


def _split_code(block: str, limit: int) -> list[str]:
    first_newline = block.find("\n")
    header = block[:first_newline]  # ```python
    body = block[first_newline + 1 :]
    if body.endswith("```"):
        body = body[:-3].rstrip("\n")

    # Room for the fence markers we re-add on every chunk.
    inner_limit = limit - len(header) - len("\n") - len("\n```")
    if inner_limit <= 0:  # pragma: no cover - pathological fence header
        return _hard_split(block, limit)

    chunks: list[str] = []
    buffer = ""
    for line in body.split("\n"):
        candidate = f"{buffer}\n{line}" if buffer else line
        if len(candidate) <= inner_limit:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
        if len(line) <= inner_limit:
            buffer = line
        else:
            pieces = _hard_split(line, inner_limit)
            chunks.extend(pieces[:-1])
            buffer = pieces[-1]
    if buffer:
        chunks.append(buffer)

    return [f"{header}\n{c}\n```" for c in chunks]


def split_message(text: str, limit: int = LIMIT) -> list[str]:
    """Split `text` into chunks of at most `limit` characters, never breaking a code fence."""
    if len(text) <= limit:
        return [text]

    out: list[str] = []
    for segment in _FENCE.split(text):
        if not segment:
            continue
        if segment.startswith("```"):
            out.extend(_split_code(segment, limit) if len(segment) > limit else [segment])
        else:
            out.extend(_split_prose(segment, limit) if len(segment) > limit else [segment])

    # Merge adjacent small chunks back together when they still fit.
    merged: list[str] = []
    for chunk in out:
        if merged and len(merged[-1]) + len(chunk) + 1 <= limit and not chunk.startswith("```"):
            merged[-1] = f"{merged[-1]}\n{chunk}"
        else:
            merged.append(chunk)
    return [c for c in merged if c.strip()]
