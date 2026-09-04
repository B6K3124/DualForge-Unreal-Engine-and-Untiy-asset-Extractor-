"""Tests for the dualforge.bethesda engine (BSA / BA2 reader)."""

from __future__ import annotations

import struct

import pytest

from dualforge.bethesda import BethesdaArchive, BethesdaError, build_dds
from dualforge.bethesda.writer import build_ba2_dx10, build_ba2_general, build_bsa
from dualforge.detector import BA2_MAGIC, BSA_MAGIC, detect_header
from dualforge.drivers.defaults import BUILTIN_DRIVERS
from dualforge.extract import ExtractOptions, extract_file

FILES = [
    ("meshes/actor/a.nif", "meshes/actor", b"AAA"),
    ("textures/t.dds", "textures", b"B" * 100),
    ("scripts/x.pex", "scripts", b"CCC"),
]
EXPECTED = ["meshes/actor/a.nif", "textures/t.dds", "scripts/x.pex"]


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


# ── BSA round-trips ──────────────────────────────────────────────────


@pytest.mark.parametrize("version", [103, 104, 105])
@pytest.mark.parametrize("compress", [False, True])
def test_bsa_roundtrip(tmp_path, version, compress):
    path = _write(tmp_path, "game.bsa", build_bsa(files=FILES, version=version, compress=compress))
    archive = BethesdaArchive(path)
    assert archive.format == "BSA"
    assert archive.version == version
    assert list(archive.list_files()) == EXPECTED
    for rel, _folder, data in FILES:
        assert archive.open_file(rel) == data
    assert archive.file_count == len(FILES)


def test_bsa_extract_all(tmp_path):
    path = _write(tmp_path, "game.bsa", build_bsa(files=FILES, version=105, compress=True))
    archive = BethesdaArchive(path)
    written = archive.extract_all(str(tmp_path / "out"))
    assert len(written) == len(FILES)
    for rel, _folder, data in FILES:
        assert (tmp_path / "out" / rel).read_bytes() == data


# ── BA2 GNRL round-trips ─────────────────────────────────────────────


@pytest.mark.parametrize("compress", [False, True])
def test_ba2_gnrl_roundtrip(tmp_path, compress):
    gf = [("meshes/a.nif", b"AAA"), ("sound/s.wav", b"Z" * 200)]
    path = _write(tmp_path, "main.ba2", build_ba2_general(files=gf, compress=compress))
    archive = BethesdaArchive(path)
    assert archive.format == "BA2"
    assert archive.type == "GNRL"
    assert list(archive.list_files()) == ["meshes/a.nif", "sound/s.wav"]
    for rel, data in gf:
        assert archive.open_file(rel) == data


# ── BA2 DX10 round-trips + DDS reconstruction ────────────────────────


def test_ba2_dx10_roundtrip(tmp_path):
    pixel = b"\x00\x80\x00" * 64
    tex = [("textures/rock.dds", 8, 8, 2, 71, pixel)]
    path = _write(tmp_path, "textures.ba2", build_ba2_dx10(files=tex, compress=True))
    archive = BethesdaArchive(path)
    assert archive.format == "BA2"
    assert archive.type == "DX10"
    assert list(archive.list_files()) == ["textures/rock.dds"]
    out = archive.open_file("textures/rock.dds")
    assert out[:4] == b"DDS "
    assert len(out) == 124 + len(pixel)
    assert struct.unpack_from("<I", out, 12)[0] == 8   # height
    assert struct.unpack_from("<I", out, 16)[0] == 8   # width
    assert struct.unpack_from("<I", out, 28)[0] == 2   # mip count


def test_ba2_dx10_uncompressed(tmp_path):
    pixel = b"\xff" * 16
    tex = [("textures/metal.dds", 2, 2, 1, 98, pixel)]
    path = _write(tmp_path, "textures.ba2", build_ba2_dx10(files=tex, compress=False))
    archive = BethesdaArchive(path)
    out = archive.open_file("textures/metal.dds")
    # BC7 emits a 20-byte DX10 extended header on top of the 124-byte DDS header.
    assert out[:4] == b"DDS "
    assert len(out) == 124 + 20 + len(pixel)


# ── detection ────────────────────────────────────────────────────────


def test_detect_bsa():
    header = build_bsa(files=FILES, version=105, compress=False)[:32]
    det = detect_header(header, "Skyrim - Meshes.bsa")
    assert det.engine == "bethesda"
    assert det.kind == "bsa"
    assert det.details["bsa_version"] == 105


def test_detect_bsa_v103():
    header = build_bsa(files=FILES, version=103, compress=False)[:32]
    det = detect_header(header, "oblivion.bsa")
    assert det.engine == "bethesda"
    assert det.details["bsa_version"] == 103


def test_detect_ba2_gnrl():
    header = build_ba2_general(files=[("a.txt", b"x")])[:32]
    det = detect_header(header, "Main.ba2")
    assert det.engine == "bethesda"
    assert det.kind == "ba2"
    assert det.details.get("ba2_type") == "GNRL"


def test_detect_ba2_dx10():
    header = build_ba2_dx10(files=[("t.dds", 2, 2, 1, 71, b"\x00" * 8)])[:32]
    det = detect_header(header, "Textures.ba2")
    assert det.engine == "bethesda"
    assert det.kind == "ba2"
    assert det.details.get("ba2_type") == "DX10"


def test_detector_exports_magics():
    assert BSA_MAGIC == b"BSA\x00"
    assert BA2_MAGIC == b"BTD\x00"


# ── extraction integration ───────────────────────────────────────────


def test_extract_bethesda_dispatch(tmp_path):
    path = _write(tmp_path, "Skyrim - Meshes.bsa", build_bsa(files=FILES, version=104, compress=True))
    result = extract_file(path, ExtractOptions(out_dir=str(tmp_path / "out")))
    assert result.detected is not None
    assert result.detected.engine == "bethesda"
    assert result.ok == len(FILES)


def test_extract_bethesda_file_filter(tmp_path):
    path = _write(tmp_path, "mod.ba2", build_ba2_general(files=[("a.txt", b"x"), ("b.txt", b"y")]))
    result = extract_file(
        path,
        ExtractOptions(out_dir=str(tmp_path / "out"), files=["a.txt"]),
    )
    assert result.ok == 1
    assert (tmp_path / "out" / "a.txt").exists()
    assert not (tmp_path / "out" / "b.txt").exists()


def test_extract_rejects_wrong_engine(tmp_path):
    path = _write(tmp_path, "mod.bsa", build_bsa(files=FILES, version=104))
    with pytest.raises(ValueError):
        extract_file(path, ExtractOptions(out_dir=str(tmp_path / "out"), engine="unreal"))


# ── error handling ───────────────────────────────────────────────────


def test_not_a_bethesda_archive(tmp_path):
    bad = _write(tmp_path, "junk.bsa", b"PK\x03\x04" + b"\x00" * 32)
    with pytest.raises(BethesdaError):
        BethesdaArchive(bad)


def test_open_missing_entry(tmp_path):
    path = _write(tmp_path, "g.bsa", build_bsa(files=FILES, version=104))
    archive = BethesdaArchive(path)
    with pytest.raises(BethesdaError):
        archive.open_file("does/not/exist.txt")


def test_unsupported_dxgi_raises():
    with pytest.raises(BethesdaError):
        build_dds(4, 4, 1, dxgi_format=0, is_cubemap=False)


# ── driver entries ───────────────────────────────────────────────────


def test_builtin_bethesda_drivers_present():
    names = {d.name: d for d in BUILTIN_DRIVERS}
    for name in ("skyrim", "fallout", "starfield", "oblivion", "fallout-new-vegas"):
        assert name in names
        assert names[name].engine == "bethesda"


def test_driver_engine_hint_scores_ba2():
    from dualforge.drivers import GameDriver

    driver = GameDriver(name="skyrim", label="Skyrim", engine="bethesda")
    assert driver.matches("/Data/Skyrim - Meshes.ba2") >= 10.0
