import struct

from dualforge.detector import (
    IL2CPP_METADATA_MAGIC,
    LOCRES_MAGIC,
    PAK_MAGIC,
    detect_header,
)

PAK_HEADER = struct.pack("<IIQ", PAK_MAGIC, 9, 1024) + b"\x00" * 12
UNITY_FS = b"UnityFS\x00" + struct.pack("<I", 7) + b"2021.3.16f1\x00" + b"\x00" * 16
UNITY_WEB = b"UnityWeb\x00" + struct.pack("<I", 6) + b"2019.4.40f1\x00" + b"\x00" * 16
UTOC_HEADER = b"-==--==--==--==-" + b"\x00" * 16
UNITY_SERIALIZED = b"\x00" * 8 + struct.pack("<I", 22) + b"\x00" * 16
LOCRES_HEADER = struct.pack("<I", LOCRES_MAGIC) + b"\x00" * 16
IL2CPP_METADATA = struct.pack("<Ii", IL2CPP_METADATA_MAGIC, 31) + b"\x00" * 16


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


def test_locres_detection():
    detection = detect_header(LOCRES_HEADER, "Game.locres")
    assert detection.engine == "unreal"
    assert detection.kind == "locres"


def test_il2cpp_metadata_detection():
    detection = detect_header(IL2CPP_METADATA, "global-metadata.dat")
    assert detection.engine == "unity"
    assert detection.kind == "il2cpp-metadata"
    assert detection.details["metadata_version"] == 31


def test_dds_detection():
    import struct as _s

    header = b"DDS " + _s.pack("<I", 124) + b"\x00" * 4 + _s.pack("<II", 64, 32) + b"\x00" * 12
    detection = detect_header(header, "tex.dds")
    assert detection.engine == "container"
    assert detection.kind == "dds"
    assert detection.details == {"width": 64, "height": 32}


def test_ktx_detection():
    header = b"\xABKTX 11\xBB\r\n\x1a\n" + b"\x00" * 16
    detection = detect_header(header, "tex.ktx")
    assert detection.engine == "container"
    assert detection.kind == "ktx"
