from __future__ import annotations

import struct

import pytest

from dualforge.unreal.locres import (
    MAGIC,
    LocresFile,
    parse_locres,
    parse_locres_file,
)


def _fstr(text: str) -> bytes:
    data = text.encode("utf-8") + b"\x00"
    return struct.pack("<i", len(data)) + data


def _fstr16(text: str) -> bytes:
    data = text.encode("utf-16-le") + b"\x00\x00"
    return struct.pack("<i", -len(data) // 2) + data


def _build_locres(version: int = 2) -> bytes:
    payload = bytearray(struct.pack("<I", MAGIC))
    payload += bytes([version])
    payload += struct.pack("<I", 2)
    payload += _fstr("Menu")
    payload += struct.pack("<I", 2)
    payload += _fstr("START")
    payload += _fstr("Start Game")
    payload += _fstr("QUIT")
    payload += _fstr("Quit")
    payload += _fstr("Items")
    payload += struct.pack("<I", 1)
    payload += _fstr("SWORD_DESC")
    payload += _fstr("A sharp blade.")
    return bytes(payload)


def test_parse_legacy():
    locres = parse_locres(_build_locres(2))
    assert locres.magic_ok
    assert locres.version == 2
    entries = locres.as_dict()
    assert entries == {
        "Menu.START": "Start Game",
        "Menu.QUIT": "Quit",
        "Items.SWORD_DESC": "A sharp blade.",
    }


def test_parse_utf16():
    payload = bytearray(struct.pack("<I", MAGIC))
    payload += bytes([3])
    payload += struct.pack("<I", 1)
    payload += _fstr16("Localization")
    payload += struct.pack("<I", 1)
    payload += _fstr16("KEY_A")
    payload += _fstr16("日本語テキスト")
    locres = parse_locres(bytes(payload))
    assert locres.as_dict() == {"Localization.KEY_A": "日本語テキスト"}


def test_to_json_and_csv():
    locres = parse_locres(_build_locres(2))
    doc = locres.to_json()
    assert '"value": "Start Game"' in doc
    csv = locres.to_csv()
    assert csv.splitlines()[0] == "namespace,key,source,value"
    assert "Menu,START,,Start Game" in csv


def test_csv_escaping():
    payload = bytearray(struct.pack("<I", MAGIC))
    payload += bytes([2])
    payload += struct.pack("<I", 1)
    payload += _fstr("Dialogs")
    payload += struct.pack("<I", 1)
    payload += _fstr("GREETING")
    payload += _fstr('Hello, "world"!')
    locres = parse_locres(bytes(payload))
    assert '"Hello, ""world""!"' in locres.to_csv()


def test_parse_empty_raises():
    with pytest.raises(ValueError):
        parse_locres(b"")


def test_parse_garbage_raises():
    with pytest.raises(ValueError):
        parse_locres(b"not a locres payload at all")


def test_parse_file(tmp_path):
    target = tmp_path / "en.locres"
    target.write_bytes(_build_locres(2))
    locres = parse_locres_file(str(target))
    assert "Menu.START" in locres.as_dict()


def test_locres_file_dataclass():
    locres = LocresFile(version=2, magic_ok=True)
    from dualforge.unreal.locres import LocresEntry

    locres.entries.append(LocresEntry(namespace="A", key="B", value="C"))
    assert locres.as_dict() == {"A.B": "C"}
    assert locres.to_json()