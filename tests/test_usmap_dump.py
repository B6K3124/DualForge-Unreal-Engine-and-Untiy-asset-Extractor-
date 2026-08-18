from __future__ import annotations

import struct

import pytest

from dualforge.unreal import usmap_dump as dump


def _pool():
    table, blocks = dump._build_test_pool()
    pool = dump._walk_pool_table(
        table,
        pool_base=0x100000,
        read_block=lambda addr: blocks[addr - 0x100000],
        layout=dump._LAYOUT_LSB,
    )
    return pool, blocks


def test_detect_layout_lsb():
    _, blocks = dump._build_test_pool()
    assert dump._detect_layout(blocks[dump.FNAME_CHUNK_TABLE_SIZE]) == dump._LAYOUT_LSB


def test_detect_layout_msb():
    entries = [(name, False) for name in ("None", "ByteProperty", "IntProperty", "BoolProperty")]
    block = bytearray()
    for name, wide in entries:
        raw = name.encode("utf-8")
        block += struct.pack("<H", (len(name) + 1) | (0x8000 if wide else 0))
        block += raw + b"\x00"
    block += b"\x00\x00"
    block = bytes(block[:dump.FNAME_BLOCK_SIZE]).ljust(dump.FNAME_BLOCK_SIZE, b"\x00")
    assert dump._detect_layout(block) == dump._LAYOUT_MSB


def test_detect_layout_none():
    assert dump._detect_layout(b"\xff" * 64) is None


def test_walk_pool_table_lsb():
    pool, _ = _pool()
    assert pool.names == [
        "None", "ByteProperty", "IntProperty", "BoolProperty",
        "日本語テスト", "A" * 300, "SecondBlockName",
    ]
    assert pool.block_count == 2
    assert pool.pool_base == 0x100000


def test_walk_block_wide_and_nul_termination():
    block = bytearray()
    for name, wide in [("日本語テスト", True), ("short", False)]:
        raw = name.encode("utf-16-le") if wide else name.encode("utf-8")
        length = len(name) + 1
        block += struct.pack("<H", (length << 1) | (1 if wide else 0))
        block += raw + (b"\x00\x00" if wide else b"\x00")
    names: list[str] = []
    count = dump._walk_block(bytes(block), names, dump._LAYOUT_LSB)
    assert count == 2
    assert names == ["日本語テスト", "short"]


def test_walk_block_stops_at_zero_header():
    block = struct.pack("<H", (5 << 1)) + b"None\x00" + b"\x00\x00" + b"garbage"
    names: list[str] = []
    assert dump._walk_block(block, names, dump._LAYOUT_LSB) == 1
    assert names == ["None"]


def test_walk_block_truncated_entry():
    block = struct.pack("<H", (100 << 1)) + b"short"
    names: list[str] = []
    assert dump._walk_block(block, names, dump._LAYOUT_LSB) == 0


def test_usmap_from_names():
    mappings = dump.usmap_from_names(["None", "ByteProperty"])
    assert mappings.names == ["None", "ByteProperty"]
    assert mappings.enums == {}
    assert mappings.structs == {}


def test_usmap_roundtrip_with_dumped_names():
    from dualforge.unreal.usmap import build_usmap, parse_usmap

    pool, _ = _pool()
    mappings = dump.usmap_from_names(pool.names)
    data = build_usmap(mappings)
    parsed = parse_usmap(data)
    assert parsed.names == pool.names
    assert parsed.enums == {}
    assert parsed.structs == {}


def test_find_process_not_found():
    with pytest.raises(dump.UsmapDumpError, match="no running process"):
        dump.find_process("definitely-not-a-real-process-xyz")


def test_find_process_normalizes_exe():
    with pytest.raises(dump.UsmapDumpError):
        dump.find_process("something.exe")
