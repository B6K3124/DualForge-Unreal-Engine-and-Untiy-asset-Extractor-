from __future__ import annotations

from dualforge.unreal.autodetect import (
    _score_exe,
    find_game_executable,
    find_install_root,
)


def _make_tree(tmp_path, names_with_scores):
    """Build a fake install tree and return root."""
    files = []
    for name, size_mb in names_with_scores:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x00" * (size_mb * 1024 * 1024))
        files.append(p)
    return tmp_path


def test_find_game_executable_prefers_shipping_win64(tmp_path):
    root = tmp_path / "TheGame"
    (root / "TheGame" / "Binaries" / "Win64").mkdir(parents=True)
    game = root / "TheGame" / "Binaries" / "Win64" / "TheGame-Win64-Shipping.exe"
    launcher = root / "TheGame" / "Binaries" / "Win64" / "TheGameLauncher.exe"
    game.write_bytes(b"\x00" * (60 * 1024 * 1024))
    launcher.write_bytes(b"\x00" * (2 * 1024 * 1024))
    best, _ = find_game_executable(str(root.parent / "TheGame"))
    assert best == str(game)


def test_find_game_executable_excludes_runtime_installers(tmp_path):
    root = tmp_path / "GameX"
    (root / "GameX" / "Binaries" / "Win64").mkdir(parents=True)
    game = root / "GameX" / "Binaries" / "Win64" / "GameX.exe"
    uninst = root / "GameX" / "Binaries" / "Win64" / "Uninstall_x64.exe"
    redist_dir = root / "GameX" / "Engine" / "Redist"
    redist = redist_dir / "UE4PrereqSetup_x64.exe"
    redist_dir.mkdir(parents=True)
    game.write_bytes(b"\x00" * (40 * 1024 * 1024))
    uninst.write_bytes(b"\x00" * (10 * 1024 * 1024))
    redist.write_bytes(b"\x00" * (10 * 1024 * 1024))
    best, ranked = find_game_executable(str(root / "GameX"))
    assert best == str(game)
    names = [p.split("\\")[-1] for p, _ in ranked]
    assert "Uninstall_x64.exe" not in names
    assert "UE4PrereqSetup_x64.exe" not in names


def test_find_install_root_from_pak_path(tmp_path):
    pak = tmp_path / "Content" / "Paks" / "pakchunk0-WindowsNoEditor.pak"
    pak.parent.mkdir(parents=True)
    pak.write_bytes(b"X" * 16)
    root = find_install_root(str(pak))
    assert root == tmp_path


def test_score_exe_ignored_binary_returns_negative(tmp_path):
    exe = tmp_path / "SGuard64.exe"
    exe.write_bytes(b"\x00" * 1000)
    assert _score_exe(exe, tmp_path) < 0