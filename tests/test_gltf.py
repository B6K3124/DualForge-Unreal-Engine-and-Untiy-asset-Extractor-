from __future__ import annotations

import json
from pathlib import Path

import pytest

from dualforge.export.gltf import GltfError, write_gltf, write_gltf_animation, write_gltf_skinned


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
    with pytest.raises(GltfError):
        write_gltf(str(tmp_path / "empty.gltf"), [], [], name="empty")


_IDENTITY = [
    1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1,
]


def _skinned_quads():
    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    tris = [(0, 1, 2), (0, 2, 3)]
    joints = [[0, 1, 2, 3]] * 4
    weights = [[0.5, 0.3, 0.1, 0.1]] * 4
    bones = ["Hips", "Spine", "Chest", "Head"]
    parents = [-1, 0, 1, 2]
    return verts, tris, joints, weights, bones, parents


def test_write_gltf_skinned(tmp_path: Path):
    verts, tris, joints, weights, _, parents = _skinned_quads()
    target = str(tmp_path / "skinned.gltf")
    write_gltf_skinned(
        target,
        vertices=verts,
        triangles=tris,
        joints=joints,
        weights=weights,
        bind_matrices=[_IDENTITY] * 4,
        bone_names=["Hips", "Spine", "Chest", "Head"],
        bone_parents=parents,
        name="Character",
    )
    doc = json.loads(Path(target).read_text(encoding="utf-8"))
    primitive = doc["meshes"][0]["primitives"][0]
    assert primitive["attributes"]["JOINTS_0"] is not None
    assert primitive["attributes"]["WEIGHTS_0"] is not None
    skin = doc["skins"][0]
    assert skin["inverseBindMatrices"] is not None
    assert len(skin["joints"]) == 4
    names = [node["name"] for node in doc["nodes"]]
    assert names == ["Character", "Hips", "Spine", "Chest", "Head"]


def test_write_gltf_skinned_morphs(tmp_path: Path):
    verts, tris, joints, weights, _, parents = _skinned_quads()
    morphs = [
        {
            "name": "Smile",
            "positions": [(0, 0.1, 0)] * 4,
            "normals": [(0, 1, 0)] * 4,
        },
        {"name": "Brow", "positions": [(0, 0, 0)] * 4},
    ]
    target = str(tmp_path / "morph.gltf")
    write_gltf_skinned(
        target,
        vertices=verts,
        triangles=tris,
        joints=joints,
        weights=weights,
        bind_matrices=[_IDENTITY] * 4,
        bone_names=["Hips", "Spine", "Chest", "Head"],
        bone_parents=parents,
        blendshapes=morphs,
        name="Character",
    )
    doc = json.loads(Path(target).read_text(encoding="utf-8"))
    mesh = doc["meshes"][0]
    targets = mesh["primitives"][0]["targets"]
    assert len(targets) == 2
    assert "POSITION" in targets[0] and "NORMAL" in targets[0]
    assert "POSITION" in targets[1] and "NORMAL" not in targets[1]
    assert mesh["weights"] == [0.0, 0.0]


def test_write_gltf_animation(tmp_path: Path):
    targets = str(tmp_path / "idle.gltf")
    write_gltf_animation(
        targets,
        name="Idle",
        bone_names=["Hips", "Head"],
        bone_parents=[-1, 0],
        tracks={
            "Hips": {"translation": [(0.0, [0, 0, 0]), (1.0, [0.5, 0, 0])]},
            "Head": {"rotation": [(0.0, [0, 0, 0, 1]), (1.0, [0, 0, 0.7071, 0.7071])]},
        },
    )
    doc = json.loads(Path(targets).read_text(encoding="utf-8"))
    anim = doc["animations"][0]
    assert anim["name"] == "Idle"
    assert len(anim["channels"]) == 2
    assert anim["samplers"][0]["interpolation"] == "LINEAR"
    channel_paths = {c["target"]["path"] for c in anim["channels"]}
    assert channel_paths == {"translation", "rotation"}
    buffers = doc["buffers"][0]
    for view in doc["bufferViews"]:
        assert view["byteOffset"] + view["byteLength"] <= buffers["byteLength"]


def test_write_gltf_animation_empty_raises(tmp_path: Path):
    with pytest.raises(GltfError):
        write_gltf_animation(str(tmp_path / "none.gltf"), name="none", tracks={})