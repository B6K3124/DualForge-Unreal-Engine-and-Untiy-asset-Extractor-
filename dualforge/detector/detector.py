from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dualforge.compression import sniff

PAK_MAGIC = 0x5A6F12E1
UTOC_MAGIC = b"-==--==--==--==-"
UNITY_SIGNATURES = (b"UnityFS", b"UnityWeb", b"UnityRaw")


@dataclass
class Detection:
    engine: str
    kind: str
    path: str
    details: Dict[str, object] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [f"Engine : {self.engine}", f"Kind   : {self.kind}"]
        for key, value in self.details.items():
            lines.append(f"{key:8s}: {value}")
        return "\n".join(lines)


def detect(path: str) -> Optional[Detection]:
    header = _read_header(path)
    if header is None:
        return None
    return detect_header(header, Path(path).name, path)


def detect_header(header: bytes, filename: str, path: str = "") -> Optional[Detection]:
    if len(header) >= 4 and struct.unpack_from("<I", header, 0)[0] == PAK_MAGIC:
        version = struct.unpack_from("<I", header, 4)[0] if len(header) >= 8 else None
        return Detection(
            engine="unreal",
            kind="pak",
            path=path,
            details={"pak_version": version, "encrypted_index": False},
        )
    if header.startswith(UTOC_MAGIC):
        return Detection(engine="unreal", kind="iostore-toc", path=path)
    lower = filename.lower()
    if lower.endswith(".ucas"):
        return Detection(engine="unreal", kind="iostore-payload", path=path)
    if lower.endswith(".utoc"):
        return Detection(engine="unreal", kind="iostore-toc", path=path)
    if lower.endswith(".pak"):
        return Detection(engine="unreal", kind="pak", path=path, details={"magic_checked": False})
    for sig in UNITY_SIGNATURES:
        if header.startswith(sig):
            return _detect_unity(header, sig, filename, path)
    if lower.endswith(".unity3d") or lower.endswith(".bundle") or lower.endswith(".assetbundle"):
        return Detection(engine="unity", kind="bundle", path=path)
    compressed = sniff(header)
    if compressed:
        return Detection(engine="container", kind=compressed, path=path)
    return None


def _detect_unity(header: bytes, sig: bytes, filename: str, path: str) -> Detection:
    version, unity_version = _parse_unityfs_header(header, len(sig))
    kind = "assetbundle" if sig == b"UnityFS" else "web-bundle"
    details = {
        "signature": sig.decode("ascii", "replace"),
        "bundle_version": version,
    }
    if unity_version:
        details["unity_version"] = unity_version
    return Detection(engine="unity", kind=kind, path=path, details=details)


def _parse_unityfs_header(header: bytes, sig_len: int) -> tuple:
    pos = sig_len
    if pos >= len(header):
        return (None, None)
    end = header.find(b"\x00", pos)
    if end == -1:
        return (None, None)
    pos = end + 1
    if pos + 4 > len(header):
        return (None, None)
    version = struct.unpack_from("<I", header, pos)[0]
    pos += 4
    end = header.find(b"\x00", pos)
    if end == -1:
        return (version, None)
    return (version, header[pos:end].decode("utf-8", "replace"))


def _read_header(path: str, size: int = 32) -> Optional[bytes]:
    try:
        with open(path, "rb") as fh:
            return fh.read(size)
    except OSError:
        return None


__all__ = ["Detection", "detect", "detect_header", "PAK_MAGIC", "UTOC_MAGIC"]
