from __future__ import annotations

from dualforge import cli


def _run_handler(monkeypatch, capsys, result, argv, crack_impl=None):
    namespace = cli.build_parser().parse_args(["crack"] + argv)
    namespace.no_download = True
    namespace.path = "test"
    namespace.ghidra_home = None
    namespace.startup_timeout = 5
    namespace.title = None
    namespace.no_save = False

    def _fake_crack(*args, **kwargs):
        if crack_impl is not None:
            return crack_impl(result)
        return result

    monkeypatch.setattr("dualforge.crack.crack", _fake_crack)
    rc = cli._cmd_crack_run(namespace)
    return rc, capsys.readouterr().out


def test_crack_run_ok_prints_key_and_saved(monkeypatch, capsys):
    result = {
        "status": "ok",
        "exe": "Game.exe",
        "pak": "game.pak",
        "candidates": ["ab" * 32],
        "verified": ["ab" * 32],
        "saved": ["Game [cracked-1]"],
        "returncode": 0,
        "detail": "",
    }
    rc, out = _run_handler(monkeypatch, capsys, result, ["run", "test"])
    assert rc == 0
    assert "cracked key    : " + "ab" * 32 in out
    assert "saved to key store: Game [cracked-1]" in out


def test_crack_run_no_valid_key_returns_nonzero(monkeypatch, capsys):
    result = {
        "status": "no_valid_key",
        "exe": "Game.exe",
        "pak": "game.pak",
        "candidates": ["ab" * 32],
        "verified": [],
        "saved": [],
        "returncode": 0,
        "detail": "",
    }
    rc, out = _run_handler(monkeypatch, capsys, result, ["run", "test"])
    assert rc == 1
    assert "proprietary/obfuscated" in out


def test_crack_run_hunt_failed_returns_nonzero(monkeypatch, capsys):
    result = {
        "status": "hunt_failed",
        "exe": "Game.exe",
        "pak": "game.pak",
        "returncode": 3,
        "detail": "boom",
    }
    rc, out = _run_handler(monkeypatch, capsys, result, ["run", "test"])
    assert rc == 1
    assert "hunt failed (exit 3)" in out


def test_locres_edit_roundtrip(tmp_path, capsys):
    import struct

    from dualforge.unreal.locres import MAGIC, parse_locres

    def fstr(text: str) -> bytes:
        data = text.encode("utf-8") + b"\x00"
        return struct.pack("<i", len(data)) + data

    src = tmp_path / "en.locres"
    payload = bytearray(struct.pack("<I", MAGIC) + bytes([2]))
    payload += struct.pack("<I", 1) + fstr("Menu") + struct.pack("<I", 2)
    payload += fstr("START") + fstr("Start Game")
    payload += fstr("QUIT") + fstr("Quit")
    src.write_bytes(bytes(payload))

    out = tmp_path / "en_new.locres"
    args = cli.build_parser().parse_args(
        ["locres", "edit", str(src), "Menu.START=Begin", "-o", str(out)]
    )
    rc = cli._cmd_locres_edit(args)
    assert rc == 0
    assert "wrote 2 entries" in capsys.readouterr().out
    edited = parse_locres(out.read_bytes())
    assert edited.as_dict() == {"Menu.START": "Begin", "Menu.QUIT": "Quit"}
    assert edited.version == 2


def test_locres_edit_refuses_source_overwrite(tmp_path, capsys):
    import struct

    from dualforge.unreal.locres import MAGIC, parse_locres

    def fstr(text: str) -> bytes:
        data = text.encode("utf-8") + b"\x00"
        return struct.pack("<i", len(data)) + data

    src = tmp_path / "en.locres"
    payload = bytearray(struct.pack("<I", MAGIC) + bytes([3]))
    payload += struct.pack("<I", 1) + fstr("Menu") + struct.pack("<I", 1)
    payload += fstr("START") + fstr("Start Game")
    src.write_bytes(bytes(payload))
    assert parse_locres(src.read_bytes()).as_dict() == {"Menu.START": "Start Game"}

    args = cli.build_parser().parse_args(
        ["locres", "edit", str(src), "Menu.START=Begin", "-o", str(src)]
    )
    rc = cli._cmd_locres_edit(args)
    assert rc == 1
    assert "refusing to overwrite the source" in capsys.readouterr().err
