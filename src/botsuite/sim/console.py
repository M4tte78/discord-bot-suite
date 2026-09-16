"""Minimal console helpers — no dependency, honours NO_COLOR, safe on Windows.

Two portability details worth naming, because both bite in practice:

* **Encoding.** The box-drawing and check-mark glyphs below cannot be encoded in
  cp1252, which is what `sys.stdout` falls back to on a Windows host when the output is
  redirected to a file or a pipe. We reconfigure stdout to UTF-8 when we can, and degrade
  to an ASCII glyph set when we cannot, rather than crashing with UnicodeEncodeError.
* **ANSI.** Windows terminals need virtual-terminal processing switched on explicitly
  before escape sequences render as colour instead of as literal `←[36m`.
"""

from __future__ import annotations

import os
import sys

# -- encoding ---------------------------------------------------------------
try:  # pragma: no cover - depends on the host stream
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError, ValueError):
    # Could not switch the stream: at least make an unencodable character print as a
    # placeholder instead of aborting the run.
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


def _encodable(sample: str) -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        sample.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


_UNICODE = {
    "tl": "┌",
    "tr": "┐",
    "bl": "└",
    "br": "┘",
    "h": "─",
    "v": "│",
    "step": "▸",
    "ok": "✔",
    "warn": "▲",
    "alert": "✖",
    "ellipsis": "…",
}
_ASCII = {
    "tl": "+",
    "tr": "+",
    "bl": "+",
    "br": "+",
    "h": "-",
    "v": "|",
    "step": ">",
    "ok": "[ok]",
    "warn": "[!]",
    "alert": "[x]",
    "ellipsis": "...",
}

G = _UNICODE if _encodable("".join(_UNICODE.values())) else _ASCII


# -- colour -----------------------------------------------------------------
def _enable_windows_ansi() -> bool:  # pragma: no cover - Windows only
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # -11 = STD_OUTPUT_HANDLE, 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


_ENABLED = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and _enable_windows_ansi()

_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "grey": "\033[90m",
}


def paint(text: str, *styles: str) -> str:
    if not _ENABLED:
        return text
    prefix = "".join(_CODES.get(s, "") for s in styles)
    return f"{prefix}{text}{_CODES['reset']}" if prefix else text


# -- output -----------------------------------------------------------------
def title(text: str) -> None:
    line = G["h"] * max(8, len(text) + 2)
    print()
    print(paint(f"{G['tl']}{line}{G['tr']}", "cyan"))
    print(paint(f"{G['v']} {text} {G['v']}", "cyan", "bold"))
    print(paint(f"{G['bl']}{line}{G['br']}", "cyan"))


def step(text: str) -> None:
    print(paint(f"\n{G['step']} {text}", "bold"))


def info(text: str) -> None:
    print(f"  {text}")


def muted(text: str) -> None:
    print(paint(f"  {text}", "grey"))


def ok(text: str) -> None:
    print(paint(f"  {G['ok']} {text}", "green"))


def warn(text: str) -> None:
    print(paint(f"  {G['warn']} {text}", "yellow"))


def alert(text: str) -> None:
    print(paint(f"  {G['alert']} {text}", "red"))


ACTION_STYLE = {
    "allow": ("green", ""),
    "flag": ("yellow", ""),
    "delete": ("yellow", ""),
    "warn": ("yellow", ""),
    "timeout": ("magenta", "bold"),
    "kick": ("red", ""),
    "ban": ("red", "bold"),
    "lockdown": ("red", "bold"),
}


def action(label: str) -> str:
    styles = ACTION_STYLE.get(label, ("", ""))
    return paint(f"{label.upper():<8}", *[s for s in styles if s])
