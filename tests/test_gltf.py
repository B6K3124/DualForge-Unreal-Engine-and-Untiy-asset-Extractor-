from __future__ import annotations

import json
from pathlib import Path

import pytest

from dualforge.export.gltf import write_gltf


def test_write_gltf_basic(tmp_path: Path):
    target = str(tmp_path / "tri.gltf")
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    tris = [(0, 1, 2)]
    write_gltf(target, verts, tris, name="tri")

    doc = json.loads(Path(target).read_text(encoding="utf-8"))
    assert doc["asset"]["version"] == "2.0"
    assert doc["scene"] == 0
    assert doc["meshes"][0]["name"] == "tri"
    buffer = doc["buffers"][0]
    assert buffer["uri"].startswith("data:application/octet-stream;base64,")
    assert buffer["byteLength"] > 0
    assert len(doc["meshes"][0]["primitives"]) == 1
    primitive = doc["meshes"][0]["primitives"][0]
    assert primitive["attributes"]["POSITION"] is not None
    assert primitive["attributes"]["NORMAL"] is not None
    assert primitive["mode"] == 4


def test_write_gltf_uvs(tmp_path: Path):
    target = str(tmp_path / "quad.gltf")
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    tris = [(0, 1, 2), (0, 2, 3)]
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    write_gltf(target, verts, tris, uvs=uvs, name="quad")

    doc = json.loads(Path(target).read_text(encoding="utf-8"))
    primitive = doc["meshes"][0]["primitives"][0]
    assert "TEXCOORD_0" in primitive["attributes"]


def test_write_gltf_empty_raises(tmp_path: Path):
    from dualforge.export.gltf import GltfError

    with pytest.raises(GltfError):
        write_gltf(str(tmp_path / "empty.gltf"), [], [], name="empty")