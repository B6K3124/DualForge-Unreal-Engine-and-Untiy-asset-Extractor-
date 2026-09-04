from __future__ import annotations

import json
from pathlib import Path

from dualforge.crack import (
    crack_all,
    extract_candidate_keys,
    find_validation_pak,
    validate_keys_against_pak,
)


def test_find_validation_pak_picks_largest(tmp_path):
    small = tmp_path / "pakchunk0-WindowsNoEditor.pak"
    big = tmp_path / "pakchunk5-WindowsNoEditor.pak"
    small.write_bytes(b"\x00" * 100)
    big.write_bytes(b"\x00" * 500)
    assert find_validation_pak(str(tmp_path)) == str(big)


def test_find_validation_pak_accepts_file_directly(tmp_path):
    pak = tmp_path / "direct.pak"
    pak.write_bytes(b"\x00" * 32)
    assert find_validation_pak(str(pak)) == str(pak)


def test_extract_candidate_keys_filters_64_hex(tmp_path):
    out = tmp_path / "candidates.json"
    out.write_text(
        json.dumps(
            {
                "matches": [
                    {
                        "candidates": [
                            {"hex": "aabb" * 16},
                            {"hex": "0x" + "cc" * 32},
                            {"hex": "deadbeef"},
                        ]
                    }
                ]
            }
        )
    )
    keys = extract_candidate_keys(str(out))
    assert keys == ["aabb" * 16, "cc" * 32]


def test_extract_candidate_keys_missing_or_invalid(tmp_path):
    assert extract_candidate_keys(None) == []
    assert extract_candidate_keys(str(tmp_path / "none.json")) == []
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json")
    assert extract_candidate_keys(str(bad)) == []


def test_validate_keys_against_pak_dedupes_and_uses_validate(monkeypatch, tmp_path):
    pak = tmp_path / "game.pak"
    pak.write_bytes(b"\x00" * 2048)
    calls = {}

    def fake_probe(raw, count=16):
        calls["probe"] = raw
        return [b"A" * 16, b"B" * 16]

    def fake_validate(block, scheme, key, archive_name="", guid="", parameters=None):
        calls.setdefault("keys", []).append(key)
        return key == "11" * 32

    monkeypatch.setattr("dualforge.crack.probe_pak_blocks", fake_probe)
    monkeypatch.setattr("dualforge.crack.validate_key", fake_validate)

    verified = validate_keys_against_pak(
        str(pak), ["11" * 32, "22" * 32, "11" * 32]
    )
    assert verified == ["11" * 32]
    # 2 unique keys validated, each against 2 blocks
    assert sorted(set(calls["keys"])) == ["11" * 32, "22" * 32]
    assert len(calls["keys"]) == 4


def test_validate_keys_against_pak_no_blocks(monkeypatch, tmp_path):
    pak = tmp_path / "game.pak"
    pak.write_bytes(b"\x00" * 100)

    def fake_probe(raw, count=16):
        return []

    monkeypatch.setattr("dualforge.crack.probe_pak_blocks", fake_probe)
    assert validate_keys_against_pak(str(pak), ["11" * 32]) == []


class _FakeJsonResult:
    def __init__(self, keys):
        self._keys = keys

    def write_text(self, *args, **kwargs):
        pass


def test_crack_all_scans_every_binary_and_dedupes(monkeypatch, tmp_path):
    class FakeHeadless:
        parents = ("", "")
        name = "analyzeHeadless.bat"

    monkeypatch.setattr(
        "dualforge.crack.find_game_executable",
        lambda folder: (
            "game.exe",
            [("game.exe", 200.0), ("GameClient.exe", 150.0), ("launcher.exe", -1.0)],
        ),
    )
    monkeypatch.setattr(
        "dualforge.crack.find_validation_pak",
        lambda folder: str(tmp_path / "g.pak"),
    )

    import dualforge.crack as crack_module

    monkeypatch.setattr(
        "dualforge.ghidra.manager.ensure_ghidra",
        lambda download=True, ghidra_home=None: FakeHeadless(),
    )
    monkeypatch.setattr("dualforge.ghidra.manager.ensure_java", lambda download=True: None)

    hunts = {}

    def fake_hunt(binary, ghidra_home, startup_timeout=300):
        hunts[binary] = True
        return 0, "ok", str(tmp_path / f"{Path(binary).stem}.json")

    monkeypatch.setattr(crack_module, "run_ghidra_hunt", fake_hunt)

    def fake_extract(json_path):
        if "game" in json_path:
            return ["11" * 32, "22" * 32]
        return ["22" * 32, "33" * 32]

    monkeypatch.setattr(crack_module, "extract_candidate_keys", fake_extract)
    monkeypatch.setattr(
        crack_module,
        "validate_keys_against_pak",
        lambda pak, keys, block_count=16: ["22" * 32],
    )

    class FakeStore:
        def __init__(self):
            self.entries = []

        def add(self, title, key, engine="", notes=""):
            self.entries.append(title)

    monkeypatch.setattr(crack_module, "KeyStore", FakeStore)

    result = crack_all(str(tmp_path))
    # Only the two positively-scored binaries were scanned (launcher filtered out).
    assert hunts == {"game.exe": True, "GameClient.exe": True}
    assert result["candidates"] == ["11" * 32, "22" * 32, "33" * 32]
    assert result["verified"] == ["22" * 32]
    assert result["saved"] == [f"{Path(str(tmp_path)).stem} [cracked-1]"]
    assert result["status"] == "ok"


def test_crack_all_skips_failed_hunts_and_reports_no_key(monkeypatch, tmp_path):
    class FakeHeadless:
        parents = ("", "")
        name = "analyzeHeadless.bat"

    monkeypatch.setattr(
        "dualforge.crack.find_game_executable",
        lambda folder: ("game.exe", [("game.exe", 200.0)]),
    )
    monkeypatch.setattr(
        "dualforge.crack.find_validation_pak",
        lambda folder: str(tmp_path / "g.pak"),
    )

    import dualforge.crack as crack_module

    monkeypatch.setattr(
        "dualforge.ghidra.manager.ensure_ghidra",
        lambda download=True, ghidra_home=None: FakeHeadless(),
    )
    monkeypatch.setattr("dualforge.ghidra.manager.ensure_java", lambda download=True: None)
    monkeypatch.setattr(
        crack_module,
        "run_ghidra_hunt",
        lambda binary, ghidra_home, startup_timeout=300: (20, "boom", ""),
    )
    monkeypatch.setattr(crack_module, "extract_candidate_keys", lambda path: [])
    monkeypatch.setattr(
        crack_module,
        "validate_keys_against_pak",
        lambda pak, keys, block_count=16: [],
    )

    result = crack_all(str(tmp_path), save_keys=False)
    assert result["status"] == "no_valid_key"
    assert result["hunt_results"][0]["status"] == "hunt_failed"
    assert result["candidates"] == []
