"""Build-time stand-in for pyuepak's ``oodle.py``.

This file is swapped in during PyInstaller analysis (see scripts/build.ps1) so
that neither the module graph nor the frozen app ever downloads or bundles the
Oodle DLL. It mirrors pyuepak's public surface (``oodle``, ``Oodle``,
``fetch_oodle``, error classes) but resolves the DLL from the game instead.
"""

import ctypes
import glob
import os
from pathlib import Path


class OodleError(Exception):
    pass


class InitializationFailed(OodleError):
    pass


class CompressionFailed(OodleError):
    pass


def fetch_oodle():
    raise InitializationFailed(
        "DualForge never bundles or downloads the Oodle DLL - "
        "supply the game's oo2core_*.dll instead"
    )


def _find_game_oodle():
    dirs = [os.getcwd(), str(Path.home() / ".dualforge")]
    dirs += [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    for d in dirs:
        for pattern in (
            "oo2core_*_win64.dll",
            "oo2core_*_linux64.so",
            "oo2core_*_mac64.dylib",
        ):
            for path in glob.glob(os.path.join(d, pattern)):
                if Path(path).is_file():
                    return Path(path)
    return None


class Oodle:
    def decompress(self, data: bytes, output_size: int) -> bytes:
        path = _find_game_oodle()
        if path is None:
            raise InitializationFailed(
                "this pak uses Oodle compression and requires the game's "
                "oo2core_*.dll (copy it into ~/.dualforge or the working dir)"
            )
        lib = ctypes.CDLL(str(path))
        fn = lib.OodleLZ_Decompress
        fn.restype = ctypes.c_longlong
        out_buffer = (ctypes.c_ubyte * output_size)()
        written = fn(
            data,
            len(data),
            out_buffer,
            output_size,
            1,
            1,
            0,
            None,
            0,
            None,
            None,
            None,
            0,
            3,
        )
        if written <= 0:
            raise CompressionFailed("Oodle decompression failed")
        return bytes(out_buffer[:written])


_oodle_singleton = None


def oodle():
    global _oodle_singleton
    if _oodle_singleton is None:
        _oodle_singleton = Oodle()
    return _oodle_singleton