from __future__ import annotations

from botsuite.sim import console


def test_glyph_set_is_complete():
    assert set(console._UNICODE) == set(console._ASCII)
    assert set(console.G) == set(console._UNICODE)


def test_ascii_fallback_is_encodable_everywhere():
    """The fallback must survive cp1252 — that is the whole point of having one."""
    "".join(console._ASCII.values()).encode("cp1252")


def test_paint_returns_the_text_when_colour_is_off(monkeypatch):
    monkeypatch.setattr(console, "_ENABLED", False)
    assert console.paint("hello", "red") == "hello"


def test_output_helpers_do_not_raise(capsys):
    console.title("titre")
    console.step("étape")
    console.info("info")
    console.muted("discret")
    console.ok("ok")
    console.warn("attention")
    console.alert("alerte")
    assert capsys.readouterr().out
