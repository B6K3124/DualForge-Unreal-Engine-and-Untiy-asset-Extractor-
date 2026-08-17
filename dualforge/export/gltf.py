from __future__ import annotations

import json
import math
import struct
from typing import List, Optional, Sequence, Tuple


class GltfError(Exception):
    pass


def _floats(data: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(data)}f", *data)


def _uints(data: Sequence[int]) -> bytes:
    return struct.pack(f"<{len(data)}I", *data)


def write_gltf(
    path: str,
    vertices: Sequence[Sequence[float]],
    triangles: Sequence[Sequence[int]],
    normals: Optional[Sequence[Sequence[float]]] = None,
    uvs: Optional[Sequence[Sequence[float]]] = None,
    name: str = "mesh",
) -> str:
    """Write a minimal glTF 2.0 file (embedded buffers, no external deps)."""
    if not vertices or not triangles:
        raise GltfError("mesh has no geometry to export")

    positions = [float(v) for vert in vertices for v in vert[:3]]
    if normals is None:
        normals = _smooth_normals(vertices, triangles)
    normal_data = [float(n) for n_vec in normals for n in n_vec[:3]]
    uv_data: List[float] = []
    if uvs:
        for uv in uvs:
            uv_data.extend((float(uv[0]), 1.0 - float(uv[1])))
    index_data = [int(i) for tri in triangles for i in tri[:3]]

    pos_bytes = _floats(positions)
    normal_bytes = _floats(normal_data)
    uv_bytes = _floats(uv_data) if uv_data else b""
    index_bytes = _uints(index_data)
    data_bytes = pos_bytes + normal_bytes + uv_bytes + index_bytes
    uri = "data:application/octet-stream;base64," + _b64(data_bytes)

    pos_offset = 0
    normal_offset = len(pos_bytes)
    uv_offset = normal_offset + len(normal_bytes)
    index_offset = uv_offset + len(uv_bytes)

    buffers = [{"byteLength": len(data_bytes), "uri": uri}]
    buffer_views = [
        {"buffer": 0, "byteOffset": pos_offset, "byteLength": len(pos_bytes), "target": 34962},
        {"buffer": 0, "byteOffset": normal_offset, "byteLength": len(normal_bytes), "target": 34962},
    ]
    if uv_bytes:
        buffer_views.append(
            {"buffer": 0, "byteOffset": uv_offset, "byteLength": len(uv_bytes), "target": 34962}
        )
    buffer_views.append(
        {"buffer": 0, "byteOffset": index_offset, "byteLength": len(index_bytes), "target": 34963}
    )

    accessors = [
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": len(vertices),
            "type": "VEC3",
            "min": [min(positions[i::3]) for i in range(3)],
            "max": [max(positions[i::3]) for i in range(3)],
        },
        {
            "bufferView": 1,
            "componentType": 5126,
            "count": len(vertices),
            "type": "VEC3",
        },
    ]
    if uv_bytes:
        accessors.append(
            {"bufferView": 2, "componentType": 5126, "count": len(vertices), "type": "VEC2"}
        )
    accessors.append(
        {
            "bufferView": len(buffer_views) - 1,
            "componentType": 5125,
            "count": len(triangles) * 3,
            "type": "SCALAR",
        }
    )

    attributes: dict = {"POSITION": 0, "NORMAL": 1}
    if uv_bytes:
        attributes["TEXCOORD_0"] = 2
    primitives = [
        {
            "attributes": attributes,
            "indices": len(accessors) - 1,
            "mode": 4,
        }
    ]
    meshes = [{"name": name, "primitives": primitives}]

    document = {
        "asset": {"version": "2.0", "generator": "DualForge"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": meshes,
        "buffers": buffers,
        "bufferViews": buffer_views,
        "accessors": accessors,
    }

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(document, fh, separators=(",", ":"))
    return path


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


def _smooth_normals(
    vertices: Sequence[Sequence[float]], triangles: Sequence[Sequence[int]]
) -> List[Tuple[float, float, float]]:
    normals: List[List[float]] = [[0.0, 0.0, 0.0] for _ in vertices]
    for tri in triangles:
        if len(tri) < 3:
            continue
        a, b, c = tri[:3]
        va = vertices[a]
        vb = vertices[b]
        vc = vertices[c]
        u = (vb[0] - va[0], vb[1] - va[1], vb[2] - va[2])
        v = (vc[0] - va[0], vc[1] - va[1], vc[2] - va[2])
        cross = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        length = math.sqrt(sum(c * c for c in cross))
        if length == 0:
            continue
        for i in tri[:3]:
            for axis in range(3):
                normals[i][axis] += cross[axis] / length
    out: List[Tuple[float, float, float]] = []
    for n in normals:
        length = math.sqrt(sum(c * c for c in n))
        if length == 0:
            out.append((0.0, 1.0, 0.0))
        else:
            out.append((n[0] / length, n[1] / length, n[2] / length))
    return out


__all__ = ["GltfError", "write_gltf"]