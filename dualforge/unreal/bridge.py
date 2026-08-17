from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class UnrealError(Exception):
    pass


class UnrealBridge:
    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = cli_path or _find_cli()

    def available(self) -> bool:
        return self.cli_path is not None

    def _cmd(self, args: List[str]) -> List[str]:
        return [self.cli_path] + args

    def list_files(self, pak: str, aes_key: Optional[str] = None) -> List[Dict[str, object]]:
        self._require()
        args = ["list", "--json", pak]
        if aes_key:
            args += ["--aes", aes_key]
        result = self._run(args)
        return _parse_list_output(result)

    def extract(
        self,
        pak: str,
        out_dir: str,
        aes_key: Optional[str] = None,
        files: Optional[List[str]] = None,
    ) -> int:
        self._require()
        args = ["extract", pak, "-o", out_dir]
        if aes_key:
            args += ["--aes", aes_key]
        if files:
            args += ["--files"] + files
        result = self._run(args)
        return _parse_extract_output(result)

    def _require(self) -> None:
        if not self.available():
            raise UnrealError(
                "No CUE4Parse-based CLI found. Point DUALFORGE_CUE4PARSE (or Settings) "
                "at one - e.g. the maintained 'uex' CLI (https://github.com/arkive-games/uex, "
                "Apache-2.0, requires the .NET runtime). The PyPI package 'cue4parse' is broken; "
                "do not install it."
            )

    def _run(self, args: List[str]) -> str:
        try:
            completed = subprocess.run(
                self._cmd(args),
                capture_output=True,
                text=True,
                timeout=600,
            )
        except FileNotFoundError as exc:
            raise UnrealError(f"could not run CUE4ParseCLI: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise UnrealError("CUE4ParseCLI timed out") from exc
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise UnrealError(
                f"CUE4ParseCLI failed (exit {completed.returncode}): {stderr or 'no output'}"
            )
        return completed.stdout or ""


def _find_cli() -> Optional[str]:
    env = os.environ.get("DUALFORGE_CUE4PARSE")
    if env and Path(env).is_file():
        return env
    for name in ("CUE4ParseCLI", "CUE4ParseCLI.exe", "cue4parse", "uex", "uex.exe"):
        found = shutil.which(name)
        if found:
            return found
    for base in (Path.home() / ".dualforge", Path.cwd()):
        for candidate in (*base.glob("CUE4ParseCLI*"), *base.glob("uex*")):
            if candidate.is_file():
                return str(candidate)
    return None


def _parse_list_output(output: str) -> List[Dict[str, object]]:
    output = output.strip()
    if not output:
        return []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return [{"path": line.strip()} for line in output.splitlines() if line.strip()]
    if isinstance(payload, list):
        return list(payload)
    if isinstance(payload, dict):
        for key in ("files", "entries", "data", "result"):
            if key in payload and isinstance(payload[key], list):
                return list(payload[key])
    return [{"path": line.strip()} for line in output.splitlines() if line.strip()]


def _parse_extract_output(output: str) -> int:
    import re

    match = re.search(r"(\d+)\s+file", output, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


__all__ = ["UnrealBridge", "UnrealError"]
