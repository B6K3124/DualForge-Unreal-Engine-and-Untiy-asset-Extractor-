"""Extract skinned-mesh, morph-target and animation data from UnityPy read
objects (typed, version-independent classes) so they can be converted to
glTF/OBJ by the exporters."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple


def _vec3(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    x = getattr(value, "x", None)
    y = getattr(value, "y", None)
    z = getattr(value, "z", None)
    if x is None or y is None or z is None:
        return None
    return [float(x), float(y), float(z)]


def _vec4(value: Any) -> Optional[List[float]]:
    parts = _vec3(value)
    if parts is None:
        return None
    return parts + [float(getattr(value, "w", 0.0))]


def skin_data(mesh: Any) -> Optional[Tuple[List[List[int]], List[List[float]]]]:
    """Return per-vertex (joint_indices, weights) pairs from ``m_Skin``.

    Handles both the older ``BoneWeights4`` and newer ``BoneInfluence`` layouts
    UnityPy exposes (four ``boneIndex_*_`` / ``weight_*_`` floats each).
    """
    skin = getattr(mesh, "m_Skin", None)
    if not skin:
        return None
    joints: List[List[int]] = []
    weights: List[List[float]] = []
    for entry in skin:
        js = []
        ws = []
        for slot in range(4):
            index = getattr(entry, f"boneIndex_{slot}_", None)
            weight = getattr(entry, f"weight_{slot}_", None)
            if index is None or weight is None:
                continue
            js.append(int(index))
            ws.append(float(weight))
        if not js:
            raise ValueError("skin entry has no bone weights")
        joints.append(js)
        weights.append(ws)
    return joints, weights


def bind_poses(mesh: Any) -> Optional[List[List[float]]]:
    """Return row-major 4x4 bind-pose matrices (one per bone)."""
    poses = getattr(mesh, "m_BindPose", None)
    if not poses:
        return None
    out: List[List[float]] = []
    for matrix in poses:
        row = [getattr(matrix, f"e{r}{c}", 0.0) for r in range(4) for c in range(4)]
        out.append([float(v) for v in row])
    return out


def joint_positions(bind_poses: Sequence[Sequence[float]]) -> List[List[float]]:
    """Translation component of each bind matrix.

    A Unity Matrix4x4 stores the translation in the right column, so for a
    row-major flatten the values live at indices 3, 7 and 11.
    """
    return [
        [float(pose[3]), float(pose[7]), float(pose[11])]
        for pose in bind_poses
    ]


def blend_shapes(mesh: Any, vertex_count: int) -> List[Dict[str, Any]]:
    """Return morph targets as ``{"name", "positions", "normals"}`` deltas.

    Each delta array is parallel to the exported vertex list (dense), zeros
    where the mesh is not affected.  Missing / malformed blend data degrades to
    an empty list rather than aborting the whole export.
    """
    if vertex_count <= 0:
        return []
    container = getattr(mesh, "m_Shapes", None) or getattr(mesh, "m_BlendShapes", None)
    if container is None:
        return []
    if hasattr(container, "shapes"):
        shapes = container.shapes or []
        raw_vertices = container.vertices or []
    elif isinstance(container, (list, tuple)):
        shapes = container
        raw_vertices = []
    else:
        return []
    if getattr(mesh, "m_ShapeVertices", None):
        source_vertices = mesh.m_ShapeVertices
    elif raw_vertices:
        source_vertices = raw_vertices
    else:
        source_vertices = []

    def fields(entry: Any) -> Tuple[Optional[int], Optional[List[float]], Optional[List[float]]]:
        index = getattr(entry, "index", None)
        vertex = _vec3(getattr(entry, "vertex", None)) or _vec3(getattr(entry, "position", None))
        normal = _vec3(getattr(entry, "normal", None))
        return index, vertex, normal

    records: List[Tuple[int, Optional[List[float]], Optional[List[float]]]] = []
    for entry in source_vertices:
        index, vertex, normal = fields(entry)
        if index is None:
            continue
        records.append((int(index), vertex, normal))

    out: List[Dict[str, Any]] = []
    for shape in shapes:
        name = str(getattr(shape, "name", None) or getattr(shape, "m_Name", "") or "Shape")
        first_vertex = int(getattr(shape, "firstVertex", 0) or 0)
        vertex_count_shape = int(getattr(shape, "vertexCount", 0) or 0)
        positions = [[0.0, 0.0, 0.0] for _ in range(vertex_count)]
        normals = [[0.0, 0.0, 0.0] for _ in range(vertex_count)]
        for slot in range(vertex_count_shape):
            index = first_vertex + slot
            if index >= len(records):
                break
            target, delta_pos, delta_normal = records[index]
            if delta_pos is not None and 0 <= target < vertex_count:
                positions[target] = delta_pos
            if delta_normal is not None and 0 <= target < vertex_count:
                normals[target] = delta_normal
        out.append(
            {
                "name": name,
                "positions": positions,
                "normals": normals,
            }
        )
    return out


def find_skinned_mesh_renderer(
    readers: Iterator[Any], mesh_reader: Any
) -> Optional[Any]:
    """Return the first SkinnedMeshRenderer whose m_Mesh points at mesh_reader."""
    target_path_id = getattr(mesh_reader, "path_id", None)
    seen = 0
    for reader in readers:
        try:
            type_name = reader.type.name
        except Exception:
            continue
        if type_name != "SkinnedMeshRenderer":
            continue
        seen += 1
        if seen > 5000:
            break
        try:
            obj = reader.read()
        except Exception:
            continue
        mesh_ptr = getattr(obj, "m_Mesh", None)
        if mesh_ptr is None:
            continue
        if target_path_id is not None and getattr(mesh_ptr, "path_id", None) == target_path_id:
            return obj
    return None


def _read_object(assets_file: Any, ptr: Any) -> Optional[Any]:
    """Best-effort resolve a PPtr to a typed read object."""
    if ptr is None or getattr(ptr, "path_id", None) is None:
        return None
    try:
        reader = assets_file.objects.get(ptr.path_id)
        if reader is None:
            return None
        return reader.read()
    except Exception:
        return None


def bone_hierarchy(smr: Any, assets_file: Any) -> Tuple[List[str], List[int]]:
    """Resolve SkinnedMeshRenderer bone names + parent indices.

    Returns (bone_names, bone_parents) where ``bone_parents[i]`` is -1 for the
    root bone.  Falls back to ``Bone_N`` names and a flat hierarchy when the
    transforms cannot be resolved.
    """
    bones = getattr(smr, "m_Bones", None) or []
    bone_count = len(bones)
    if bone_count == 0:
        return [], []

    root_ptr = getattr(smr, "m_RootBone", None)
    root_path = getattr(root_ptr, "path_id", None) if root_ptr is not None else None

    name_by_slot: Dict[int, str] = {}
    transform_paths: Dict[int, int] = {}
    for slot, ptr in enumerate(bones):
        transform = _read_object(assets_file, ptr)
        if transform is None:
            continue
        game_object_ptr = getattr(transform, "m_GameObject", None)
        game_object = _read_object(assets_file, game_object_ptr)
        name = ""
        if game_object is not None:
            name = str(getattr(game_object, "m_Name", "") or "")
        name_by_slot[slot] = name
        transform_paths[slot] = getattr(ptr, "path_id", None)

    names: List[str] = []
    parents: List[int] = []
    reverse_lookup = {path: slot for slot, path in transform_paths.items()}
    for slot in range(bone_count):
        ptr = bones[slot]
        transform = _read_object(assets_file, ptr)
        name = name_by_slot.get(slot, "") or f"Bone_{slot}"
        parent = -1
        if transform is not None:
            cursor = getattr(transform, "m_Father", None)
            hops = 0
            while cursor is not None and getattr(cursor, "path_id", None) is not None and hops < 64:
                path = cursor.path_id
                if path == root_path or path in reverse_lookup:
                    if path == root_path:
                        break
                    parent = reverse_lookup[path]
                    break
                cursor = getattr(_read_object(assets_file, cursor), "m_Father", None)
                hops += 1
        names.append(name)
        parents.append(parent)
    return names, parents


class AnimationTrackError(Exception):
    pass


def _curve_keyframes(curve: Any) -> List[Tuple[float, Any]]:
    items = getattr(curve, "m_Curve", None) or getattr(curve, "curve", None)
    if not items:
        return []
    frames: List[Tuple[float, Any]] = []
    for keyframe in items:
        time = getattr(keyframe, "time", None)
        value = getattr(keyframe, "value", None)
        if time is None or value is None:
            continue
        frames.append((float(time), value))
    return frames


def _path_leaf(path: str) -> str:
    leaf = path.rsplit("/", 1)[-1]
    return leaf.replace(" (1)", "").strip()


def animation_tracks(clip: Any) -> Dict[str, Dict[str, List[Tuple[float, List[float]]]]]:
    """Convert an AnimationClip to node TRS tracks for glTF.

    Returns ``{bone_name: {"translation"|"rotation"|"scale": [(t, values)]}}``
    using the per-component m_PositionCurves / m_RotationCurves /
    m_ScaleCurves UnityPy exposes.
    """
    tracks: Dict[str, Dict[str, List[Tuple[float, List[float]]]]] = {}

    def add_curves(curves: Any, target: str, width: int, is_rotation: bool = False) -> None:
        for curve_entry in curves or []:
            path = str(getattr(curve_entry, "path", "") or "")
            name = _path_leaf(path)
            if not name:
                continue
            frames = _curve_keyframes(getattr(curve_entry, "curve", None))
            keys: List[Tuple[float, List[float]]] = []
            for time, value in frames:
                values = _vec4(value) if is_rotation else _vec3(value)
                if values is None or len(values) != width:
                    continue
                if is_rotation:
                    values = _normalize_quat(values)
                keys.append((time, values))
            if keys and name not in tracks:
                tracks[name] = {}
            if keys:
                tracks.setdefault(name, {})[target] = keys

    add_curves(getattr(clip, "m_PositionCurves", None), "translation", 3)
    add_curves(getattr(clip, "m_RotationCurves", None), "rotation", 4, is_rotation=True)
    add_curves(getattr(clip, "m_ScaleCurves", None), "scale", 3)

    if "rotation" not in _any_track(tracks):
        euler = getattr(clip, "m_EulerCurves", None) or []
        if euler:
            for curve_entry in euler:
                path = str(getattr(curve_entry, "path", "") or "")
                name = _path_leaf(path)
                if not name:
                    continue
                frames = _curve_keyframes(getattr(curve_entry, "curve", None))
                keys = []
                for time, value in frames:
                    e = _vec3(value)
                    if e is None:
                        continue
                    keys.append((time, _euler_to_quat(e)))
                if keys:
                    tracks.setdefault(name, {})["rotation"] = keys
    return tracks


def _any_track(tracks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for _, target_data in tracks.items():
        for target, keys in target_data.items():
            if keys:
                result[target] = keys
    return result


def _normalize_quat(values: List[float]) -> List[float]:
    import math

    length = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / length for v in values]


def _euler_to_quat(euler: Sequence[float]) -> List[float]:
    """Convert Unity ZXY euler degrees to a quaternion (x, y, z, w)."""
    import math

    x, y, z = (math.radians(float(e)) for e in euler)
    cx, sx = math.cos(x / 2), math.sin(x / 2)
    cy, sy = math.cos(y / 2), math.sin(y / 2)
    cz, sz = math.cos(z / 2), math.sin(z / 2)
    return [
        sx * cy * cz - cx * sy * sz,
        cx * sy * cz + sx * cy * sz,
        cx * cy * sz - sx * sy * cz,
        cx * cy * cz + sx * sy * sz,
    ]


def clip_summary(clip: Any) -> Dict[str, Any]:
    """Small metadata dict shown in the preview details pane."""
    position_frames = 0
    rotation_frames = 0
    scale_frames = 0
    for curves, target in (
        (getattr(clip, "m_PositionCurves", None), 0),
        (getattr(clip, "m_RotationCurves", None), 1),
        (getattr(clip, "m_ScaleCurves", None), 2),
    ):
        for curve_entry in curves or []:
            frames = _curve_keyframes(getattr(curve_entry, "curve", None))
            if target == 0:
                position_frames += len(frames)
            elif target == 1:
                rotation_frames += len(frames)
            else:
                scale_frames += len(frames)
    return {
        "Position curves": str(len(getattr(clip, "m_PositionCurves", None) or [])),
        "Rotation curves": str(len(getattr(clip, "m_RotationCurves", None) or [])),
        "Scale curves": str(len(getattr(clip, "m_ScaleCurves", None) or [])),
        "Keyframes": str(position_frames + rotation_frames + scale_frames),
        "Sample rate": str(getattr(clip, "m_SampleRate", 0) or 0),
    }


__all__ = [
    "AnimationTrackError",
    "animation_tracks",
    "bind_poses",
    "blend_shapes",
    "bone_hierarchy",
    "clip_summary",
    "find_skinned_mesh_renderer",
    "joint_positions",
    "skin_data",
]