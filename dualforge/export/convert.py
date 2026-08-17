from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from dualforge.export.gltf import write_gltf

TEXTURE_FORMATS = ("png", "jpg", "bmp", "webp", "tga")
AUDIO_FORMATS = ("wav", "ogg", "flac", "raw")
MESH_FORMATS = ("obj", "gltf")
TEXT_FORMATS = ("txt",)
RAW_FORMATS = ("bin",)

DEFAULT_FORMATS = {
    "Texture2D": "png",
    "Sprite": "png",
    "AudioClip": "wav",
    "Mesh": "obj",
    "TextAsset": "txt",
}


def normalize_format(fmt: Optional[str]) -> str:
    return (fmt or "png").lower().lstrip(".")


def format_choices(type_name: str) -> Tuple[str, ...]:
    if type_name in {"Texture2D", "Sprite"}:
        return TEXTURE_FORMATS
    if type_name == "AudioClip":
        return AUDIO_FORMATS
    if type_name == "Mesh":
        return MESH_FORMATS
    if type_name == "TextAsset":
        return TEXT_FORMATS
    return RAW_FORMATS


def save_texture(image, path_stem: Path, fmt: str) -> str:
    fmt = normalize_format(fmt)
    if fmt == "jpg":
        target = path_stem.with_suffix(".jpg")
        image.convert("RGB").save(target, quality=95)
        return str(target)
    target = path_stem.with_suffix(f".{fmt}")
    image.save(target)
    return str(target)


def save_mesh(name: str, obj_data: bytes, path_stem: Path, fmt: str) -> str:
    fmt = normalize_format(fmt)
    if fmt == "gltf":
        verts, tris, uvs = _parse_obj_with_uv(obj_data)
        if not verts or not tris:
            raise ValueError("mesh has no decodable geometry for glTF export")
        target = path_stem.with_suffix(".gltf")
        write_gltf(str(target), verts, tris, uvs=uvs, name=name or path_stem.stem)
        return str(target)
    target = path_stem.with_suffix(".obj")
    with open(target, "wb") as fh:
        fh.write(obj_data)
    return str(target)


def save_text(data: bytes, path_stem: Path, fmt: str = "txt") -> str:
    fmt = normalize_format(fmt)
    target = path_stem.with_suffix(f".{fmt}")
    text = data.decode("utf-8", "replace")
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return str(target)


def _parse_obj_with_uv(data: bytes):
    positions: List[Tuple[float, float, float]] = []
    uvs: List[Tuple[float, float]] = []
    faces_raw: List[List[str]] = []
    for line in data.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "v" and len(parts) >= 4:
            try:
                positions.append((float(parts[1]), float(parts[2]), float(parts[3])))
            except ValueError:
                continue
        elif parts[0] == "vt" and len(parts) >= 3:
            try:
                uvs.append((float(parts[1]), float(parts[2])))
            except ValueError:
                continue
        elif parts[0] == "f" and len(parts) >= 4:
            faces_raw.append(parts[1:])
    if not positions or not faces_raw:
        return [], [], []
    merge_map: dict = {}
    merged: List[Tuple[int, int]] = []
    tris: List[Tuple[int, int, int]] = []
    for face in faces_raw:
        corners: List[int] = []
        for part in face:
            segments = part.split("/")
            try:
                pos_index = int(segments[0]) - 1
            except ValueError:
                continue
            uv_index = -1
            if len(segments) > 1 and segments[1]:
                try:
                    uv_index = int(segments[1]) - 1
                except ValueError:
                    pass
            key = (pos_index, uv_index)
            index = merge_map.get(key)
            if index is None:
                index = len(merged)
                merge_map[key] = index
                merged.append(key)
            corners.append(index)
        for i in range(1, len(corners) - 1):
            tris.append((corners[0], corners[i], corners[i + 1]))
    if not tris:
        return [], [], []
    verts = [positions[pos_index] for pos_index, _ in merged]
    uv_out = [uvs[uv_index] if uv_index >= 0 and uv_index < len(uvs) else (0.0, 0.0) for _, uv_index in merged]
    return verts, tris, uv_out


__all__ = [
    "AUDIO_FORMATS",
    "DEFAULT_FORMATS",
    "MESH_FORMATS",
    "RAW_FORMATS",
    "TEXT_FORMATS",
    "TEXTURE_FORMATS",
    "format_choices",
    "normalize_format",
    "save_mesh",
    "save_text",
    "save_texture",
]