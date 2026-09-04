"""Auto-detect a game's main executable inside an opened folder.

Helps the Tools menu (Ghidra Key Hunt etc.) start with the right binary and
lets DualForge identify which game a folder belongs to so the matching driver
can be applied automatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from dualforge.drivers import registry

_SKIP_DIRS = {"steamapps", "common", "node_modules", ".git", "support", "redist", "unins"}
_BINARY_DIRS = {"binaries", "win64", "win32", "bin", "win", "windows"}


def find_game_executable(folder: str, depth: int = 5) -> Optional[str]:
    """Return the most likely game executable path in ``folder`` (or None)."""
    root = Path(folder)
    if not root.is_dir():
        return None
    candidates: List[tuple] = []
    _walk(root, root, depth, candidates)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _walk(root: Path, directory: Path, depth: int, out: List[tuple]) -> None:
    if depth <= 0:
        return
    try:
        entries = sorted(directory.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_dir():
                if entry.name.lower() in _SKIP_DIRS:
                    continue
                _walk(root, entry, depth - 1, out)
            elif entry.suffix.lower() == ".exe":
                score = _score(root, entry)
                if score > 0:
                    out.append((score, str(entry)))
        except OSError:
            continue


def _score(root: Path, exe: Path) -> float:
    stem = exe.stem.lower()
    if any(noise in stem for noise in (
        "unins", "redist", "vcredist", "dxsetup", "vc_redist",
        "installer", "setup", "dotnet", "launcher",
    )):
        return 0.0
    score = 1.0
    rel = exe.relative_to(root)
    parts = [p.lower() for p in rel.parts]
    for part in parts[:-1]:
        if part in _BINARY_DIRS:
            score += 15.0
    root_name = root.name.lower()
    if stem == root_name:
        score += 40.0
    elif root_name and (root_name in stem or stem in root_name):
        score += 20.0
    if len(parts) <= 2:
        score += 5.0
    return score


def identify_game(exe_path: str, folder: str = "") -> Optional[object]:
    """Match an executable (or folder) against the driver registry.

    Returns the best-scoring ``GameDriver`` or None.
    """
    candidates = [
        p
        for p in (exe_path, folder)
        if p
    ]
    text = " ".join(candidates).lower()
    best = None
    best_score = 0.0
    for driver in registry.list():
        for frag in driver.game_fragments:
            if frag.lower() in text:
                score = len(frag)
                if score > best_score:
                    best_score = score
                    best = driver
                break
    return best


def find_usmap_output(exe_path: str) -> Optional[str]:
    """Suggest a .usmap output path for the given game executable."""
    if not exe_path:
        return None
    base = Path(exe_path).stem
    return str(Path.home() / ".dualforge" / f"{base}.usmap")


__all__ = ["find_game_executable", "identify_game", "find_usmap_output"]
