import struct

from dualforge.detector import PAK_MAGIC, detect_header

PAK_HEADER = struct.pack("<IIQ", PAK_MAGIC, 9, 1024) + b"\x00" * 12
UNITY_FS = b"UnityFS\x00" + struct.pack("<I", 7) + b"2021.3.16f1\x00" + b"\x00" * 16
UNITY_WEB = b"UnityWeb\x00" + struct.pack("<I", 6) + b"2019.4.40f1\x00" + b"\x00" * 16
UTOC_HEADER = b"-==--==--==--==-" + b"\x00" * 16
UNITY_SERIALIZED = b"\x00" * 8 + struct.pack("<I", 22) + b"\x00" * 16


def test_pak():
    detection = detect_header(PAK_HEADER, "pakchunk0-Windows.pak")
    assert detection.engine == "unreal"
    assert detection.kind == "pak"
    assert detection.details["pak_version"] == 9


def test_unity_fs():
    detection = detect_header(UNITY_FS, "assets.bundle")
    assert detection.engine == "unity"
    assert detection.kind == "assetbundle"
    assert detection.details["unity_version"] == "2021.3.16f1"


def test_unity_web():
    detection = detect_header(UNITY_WEB, "web.unity3d")
    assert detection.engine == "unity"
    assert detection.kind == "web-bundle"


def test_utoc():
    detection = detect_header(UTOC_HEADER, "pakchunk0-Windows.utoc")
    assert detection.engine == "unreal"
    assert detection.kind == "iostore-toc"


def test_ucas_by_extension():
    detection = detect_header(b"\x00" * 32, "pakchunk0-Windows.ucas")
    assert detection.engine == "unreal"
    assert detection.kind == "iostore-payload"


def test_pak_by_extension_fallback():
    detection = detect_header(b"\x00" * 32, "game.pak")
    assert detection.engine == "unreal"


def test_unknown_returns_none():
    assert detect_header(b"\x00" * 32, "random.bin") is None


def test_unity_serialized_by_header():
    detection = detect_header(UNITY_SERIALIZED, "sharedassets0.assets")
    assert detection.engine == "unity"
    assert detection.kind == "serialized"
    assert detection.details["serialized_version"] == 22


def test_unity_serialized_level_by_name():
    detection = detect_header(b"\x00" * 32, "level0")
    assert detection.engine == "unity"
    assert detection.kind == "serialized"


def test_unity_serialized_globalgamemanagers_by_name():
    detection = detect_header(b"\x00" * 32, "globalgamemanagers")
    assert detection.engine == "unity"
    assert detection.kind == "serialized"


def test_unity_serialized_rejects_zero_version():
    assert detect_header(b"\x00" * 32, "random.bin") is None
