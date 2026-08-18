from __future__ import annotations

import struct
from pathlib import Path

import pytest

from dualforge.unreal.usmap import (
    USMAP_MAGIC,
    UsmapCompression,
    UsmapError,
    UsmapMappings,
    UsmapProperty,
    UsmapPropertyType,
    UsmapStruct,
    UsmapVersion,
    build_usmap,
    parse_usmap,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ue5_8"


def _sample_mappings() -> UsmapMappings:
    kind = UsmapPropertyType(kind="EnumProperty", inner=UsmapPropertyType(kind="ByteProperty"), enum_name="EDirection")
    position = UsmapPropertyType(kind="StructProperty", struct_type="Position")
    return UsmapMappings(
        names=["UnusedName"],
        enums={
            "EDirection": {0: "North", 1: "East", 2: "West"},
            "EFlag": {0: "Zero", 1: "One"},
        },
        structs={
            "Position": UsmapStruct(
                name="Position",
                property_count=3,
                properties=[
                    UsmapProperty(0, 1, "X", UsmapPropertyType(kind="FloatProperty")),
                    UsmapProperty(1, 1, "Y", UsmapPropertyType(kind="FloatProperty")),
                    UsmapProperty(2, 3, "Z", UsmapPropertyType(kind="FloatProperty")),
                ],
            ),
            "Marker": UsmapStruct(
                name="Marker",
                super_type="Position",
                property_count=6,
                properties=[
                    UsmapProperty(0, 1, "Direction", kind),
                    UsmapProperty(1, 1, "Origin", position),
                    UsmapProperty(
                        2, 1, "Layers",
                        UsmapPropertyType(kind="ArrayProperty", inner=UsmapPropertyType(kind="IntProperty")),
                    ),
                    UsmapProperty(
                        3, 1, "Tags",
                        UsmapPropertyType(kind="SetProperty", inner=UsmapPropertyType(kind="NameProperty")),
                    ),
                    UsmapProperty(
                        4, 1, "Lookup",
                        UsmapPropertyType(
                            kind="MapProperty",
                            inner=UsmapPropertyType(kind="NameProperty"),
                            value=UsmapPropertyType(kind="StructProperty", struct_type="Marker"),
                        ),
                    ),
                    UsmapProperty(
                        5, 1, "Maybe",
                        UsmapPropertyType(kind="OptionalProperty", inner=UsmapPropertyType(kind="BoolProperty")),
                    ),
                ],
            ),
        },
    )


@pytest.mark.parametrize("version", list(UsmapVersion))
@pytest.mark.parametrize("compression", [UsmapCompression.None_, UsmapCompression.ZStandard, UsmapCompression.Brotli])
def test_roundtrip_versions_and_compressions(version, compression):
    mappings = _sample_mappings()
    data = build_usmap(mappings, version=version, compression=compression)
    parsed = parse_usmap(data)
    assert parsed.structs == mappings.structs
    assert parsed.enums == mappings.enums


def test_sparse_enum_values_require_v4():
    mappings = _sample_mappings()
    mappings.enums["EDirection"] = {0: "North", 2: "East", 7: "West"}
    # ExplicitEnumValues stores real values.
    parsed = parse_usmap(build_usmap(mappings, version=UsmapVersion.ExplicitEnumValues))
    assert parsed.enums["EDirection"] == {0: "North", 2: "East", 7: "West"}
    # Older formats store names positionally: sparse keys collapse to 0..n-1.
    parsed = parse_usmap(build_usmap(mappings, version=UsmapVersion.LargeEnums))
    assert parsed.enums["EDirection"] == {0: "North", 1: "East", 2: "West"}


def test_header_layout_latest_version():
    mappings = _sample_mappings()
    data = build_usmap(mappings, version=UsmapVersion.Latest, compression=UsmapCompression.None_)
    magic, = struct.unpack_from("<H", data, 0)
    assert magic == USMAP_MAGIC
    assert data[2] == UsmapVersion.Latest
    # CUE4Parse reads the versioning flag as Read<int>() = 4 bytes.
    has_versioning, = struct.unpack_from("<i", data, 3)
    assert has_versioning == 0
    compression, = struct.unpack_from("<B", data, 7)
    assert compression == UsmapCompression.None_
    comp_size, decomp_size = struct.unpack_from("<II", data, 8)
    assert comp_size == decomp_size > 0


def test_header_layout_version_zero_has_no_versioning_flag():
    mappings = _sample_mappings()
    data = build_usmap(mappings, version=UsmapVersion.Initial, compression=UsmapCompression.None_)
    assert data[2] == UsmapVersion.Initial
    compression, = struct.unpack_from("<B", data, 3)
    assert compression == UsmapCompression.None_


def test_versioning_block_roundtrip():
    mappings = _sample_mappings()
    from dualforge.unreal.usmap import UsmapCustomVersion, UsmapPackageVersioning

    mappings.versioning = UsmapPackageVersioning(
        package_file_version=522,
        package_licensee_version=0,
        custom_versions=[
            UsmapCustomVersion(0, 0, b"\x00" * 16, 0),
            UsmapCustomVersion(42, 7, bytes(range(16)), 99),
        ],
        net_cl=0x1234,
    )
    data = build_usmap(mappings, version=UsmapVersion.Latest, compression=UsmapCompression.None_)
    parsed = parse_usmap(data)
    assert parsed.versioning == mappings.versioning


def test_rebuild_fixture_matches():
    for name in ("Mappings-Zstandard.usmap", "Mappings-Uncompressed.usmap"):
        original = parse_usmap((FIXTURES / name).read_bytes())
        for compression in (UsmapCompression.None_, UsmapCompression.ZStandard):
            rebuilt = build_usmap(original, compression=compression)
            parsed = parse_usmap(rebuilt)
            assert parsed.structs == original.structs
            assert parsed.enums == original.enums
            assert len(parsed.names) <= len(original.names)


def test_fixtures_are_equivalent():
    zstd = parse_usmap((FIXTURES / "Mappings-Zstandard.usmap").read_bytes())
    plain = parse_usmap((FIXTURES / "Mappings-Uncompressed.usmap").read_bytes())
    assert zstd.structs == plain.structs
    assert zstd.enums == plain.enums
    assert len(zstd.names) == len(plain.names) == 40567
    assert len(zstd.enums) == len(plain.enums) == 1833
    assert len(zstd.structs) == len(plain.structs) == 8991


def test_unreferenced_names_dropped():
    mappings = _sample_mappings()
    data = build_usmap(mappings, version=UsmapVersion.Latest, compression=UsmapCompression.None_)
    parsed = parse_usmap(data)
    # Caller-provided names are preserved (they may be a game's name pool).
    assert "UnusedName" in parsed.names
    assert "Marker" in parsed.names
    assert "EDirection" in parsed.names
    assert "North" in parsed.names
    # Property kinds are type bytes, not LUT names; only referenced names appear.
    assert "FloatProperty" not in parsed.names
    assert parsed.structs["Marker"].properties[1].type.struct_type == "Position"


def test_utf8_names():
    mappings = _sample_mappings()
    struct = mappings.structs["Marker"]
    struct.properties.append(
        UsmapProperty(6, 1, "Sígné", UsmapPropertyType(kind="StrProperty"))
    )
    data = build_usmap(mappings, compression=UsmapCompression.None_)
    parsed = parse_usmap(data)
    assert "Sígné" in parsed.structs["Marker"].properties[-1].name


def test_long_name_requires_longfname():
    mappings = _sample_mappings()
    struct = mappings.structs["Marker"]
    struct.properties.append(
        UsmapProperty(6, 1, "X" * 300, UsmapPropertyType(kind="StrProperty"))
    )
    with pytest.raises(UsmapError):
        build_usmap(mappings, version=UsmapVersion.Initial)
    data = build_usmap(mappings, version=UsmapVersion.LongFName)
    assert parse_usmap(data).structs == mappings.structs


def test_empty_mappings():
    data = build_usmap(UsmapMappings(), compression=UsmapCompression.None_)
    parsed = parse_usmap(data)
    assert parsed.names == []
    assert parsed.enums == {}
    assert parsed.structs == {}


@pytest.mark.parametrize("bad", [b"", b"\x00", b"\xc4\x30\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"])
def test_bad_magic_or_version(bad):
    with pytest.raises(UsmapError):
        parse_usmap(bad)


def test_invalid_versioning_flag():
    data = b"\xc4\x30\x04\x02\x00\x00\x00" + b"\x00" * 24
    with pytest.raises(UsmapError, match="versioning flag"):
        parse_usmap(data)


def test_invalid_compression_method():
    data = b"\xc4\x30\x04\x00\x00\x00\x00\xff\x10\x00\x00\x00\x10\x00\x00\x00" + b"\x00" * 16
    with pytest.raises(UsmapError, match="compression"):
        parse_usmap(data)


def test_truncated_payload():
    mappings = _sample_mappings()
    data = build_usmap(mappings, compression=UsmapCompression.None_)
    with pytest.raises(UsmapError, match="truncated"):
        parse_usmap(data[:-3])


def test_bad_compressed_payload():
    data = b"\xc4\x30\x04\x00\x00\x00\x00\x03\x04\x00\x00\x00\x04\x00\x00\x00" + b"\x00\x00\x00\x00"
    with pytest.raises(UsmapError):
        parse_usmap(data)


def test_unknown_property_type_byte():
    payload = b"\x01\x00\x00\x00" + b"\x04None" + b"\x00\x00\x00\x00" + b"\x01\x00\x00\x00"
    payload += struct.pack("<iiHH", 0, -1, 1, 1)
    payload += struct.pack("<HB", 0, 1) + struct.pack("<i", 0) + bytes([0xFF])
    data = b"\xc4\x30\x00\x00" + struct.pack("<II", len(payload), len(payload)) + payload
    with pytest.raises(UsmapError, match="property type"):
        parse_usmap(data)


def test_fixture_contains_expected_schema():
    mappings = parse_usmap((FIXTURES / "Mappings-Uncompressed.usmap").read_bytes())
    data = mappings.structs["ParserFixtureData"]
    assert data.super_type == "ParserFixtureBaseData"
    assert data.property_count == 63
    by_name = {p.name: p for p in data.properties}
    assert by_name["AnsiString"].type.kind == "AnsiStrProperty"
    assert by_name["Utf8String"].type.kind == "Utf8StrProperty"
    assert by_name["LazyObjectReference"].type.kind == "LazyObjectProperty"
    assert by_name["InterfaceReference"].type.kind == "InterfaceProperty"
    assert by_name["FieldPathReference"].type.kind == "FieldPathProperty"
    assert by_name["IntegerMap"].type.inner.kind == "NameProperty"
    assert by_name["IntegerMap"].type.value.kind == "IntProperty"
    assert by_name["NameSet"].type.inner.kind == "NameProperty"
    assert by_name["Nested"].type.struct_type == "FixtureNestedStruct"
    assert by_name["ScalarInstancedStruct"].type.struct_type == "InstancedStruct"
    assert by_name["bBoolean"].type.kind == "BoolProperty"
