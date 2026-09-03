from __future__ import annotations

from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path
from typing import Dict, Iterator, List, Optional


class UnityError(Exception):
    pass


@dataclass
class UnityAsset:
    path: str
    type_name: str
    byte_size: int
    _reader: object = field(repr=False)


class UnityArchive:
    def __init__(self, path: str):
        try:
            import UnityPy
        except ImportError as exc:
            raise UnityError("UnityPy is required (pip install UnityPy)") from exc
        self.path = str(path)
        self.env = UnityPy.load(self.path)
        self._types = UnityPy
        self.load_sibling_streams()

    def load_sibling_streams(self) -> int:
        """Pre-load sibling stream files (.resS / .resource / .split*).

        UnityPy resolves external streams lazily relative to the bundle's
        folder, but only for CAB names listed in m_ExternalFiles. Eagerly
        registering every matching sibling here also covers files whose
        on-disk name differs from the CAB reference, so streamed textures,
        audio and mesh data decode reliably.
        """
        import os

        loaded = 0
        directory = Path(self.path).parent
        candidates: List[Path] = []
        try:
            for file in self.env.files.values():
                for external in getattr(file, "externals", []) or []:
                    ref = str(getattr(external, "path", "") or "")
                    for prefix in ("archive:/", "library/", "resources/"):
                        if ref.lower().startswith(prefix):
                            ref = ref[len(prefix):]
                            break
                    if ref and Path(ref).name:
                        candidates.append(directory / Path(ref).name)
        except Exception:
            pass
        stem = Path(self.path).stem
        try:
            for pattern in (
                f"{stem}.resS",
                f"{stem}.resource",
                f"{stem}.split*",
                "CAB-*.resS",
                "*.resS",
                "*.resource",
            ):
                candidates.extend(directory.glob(pattern))
        except OSError:
            pass
        seen = set()
        for candidate in candidates:
            key = os.path.normcase(str(candidate))
            if key in seen:
                continue
            seen.add(key)
            try:
                if not candidate.is_file() or str(candidate) in self.env.files:
                    continue
                self.env.load_file(str(candidate), is_dependency=True)
                loaded += 1
            except Exception:
                continue
        return loaded

    def engine_version(self) -> str:
        """Best-effort engine version from the bundle/serialized header."""
        for file in self.env.files.values():
            value = getattr(file, "unity_version", None) or getattr(file, "version", None)
            if value:
                return str(value).strip()
        return ""

    def serialized_version(self) -> int:
        """Best-effort serialized format version (bundle header or -1)."""
        for file in self.env.files.values():
            header = getattr(file, "header", None)
            if header is not None:
                value = getattr(header, "version", None)
                if isinstance(value, int):
                    return value
        return -1

    def set_decrypt_key(self, key: str, scheme: str = "aes-256") -> None:
        """Set the Unity bundle decryption key via UnityPy.

        Standard Unity bundles take a 16-char ASCII key (or a 32-byte AES hex
        key as bytes). ``scheme`` selects the interpretation:

        - ``aes-256`` (default): pass the key straight through (UnityPy handles
          the AES/XOR bundle decryption with hex keys of any Unreal-style
          length, and 16-char keys verbatim).
        - ``unity-cn``: expect a 16-char key; if a ``0x``-hex AES key is given,
          UnityPy still accepts it (CN games commonly expose the raw AES key).
        """
        normalized = key
        if normalized.lower().startswith("0x"):
            hex_body = normalized[2:].strip()
            if len(hex_body) in (32, 64) and all(c in "0123456789abcdefABCDEF" for c in hex_body):
                normalized = bytes.fromhex(hex_body)
            else:
                normalized = normalized[2:].strip()
        try:
            self._types.set_assetbundle_decrypt_key(normalized)
        except (AttributeError, TypeError, ValueError) as exc:
            raise UnityError(f"could not set decrypt key: {exc}") from exc

    def assets(self) -> Iterator[UnityAsset]:
        """Iterate all readable objects.

        Bundles expose a name->reader container; plain serialized files
        (`.assets`, `level*`, `globalgamemanagers`, ...) have no container,
        so fall back to every object in the environment.
        """
        try:
            container = self.env.container.items()
            first = next(container, None)
        except Exception:
            first = None
        if first is not None:
            for path, reader in chain((first,), container):
                yield UnityAsset(
                    path=path,
                    type_name=reader.type.name,
                    byte_size=reader.byte_size,
                    _reader=reader,
                )
            return
        for reader in self.env.objects:
            yield UnityAsset(
                path=str(reader.path_id),
                type_name=reader.type.name,
                byte_size=reader.byte_size,
                _reader=reader,
            )

    def extract_asset(
        self,
        asset: UnityAsset,
        out_dir: str,
        fmt: Optional[str] = None,
        formats: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        from dualforge.export.convert import DEFAULT_FORMATS, save_text, save_texture

        written: List[str] = []
        obj = asset._reader.read()
        type_name = asset.type_name
        chosen = fmt or (formats or {}).get(type_name) or DEFAULT_FORMATS.get(type_name, "bin")
        stem = _output_stem(out_dir, asset.path)
        if type_name == "Texture2D":
            image = obj.image
            if image is None:
                raise UnityError(f"texture has no decodable image: {asset.path}")
            written.append(save_texture(image, stem, chosen))
        elif type_name == "Sprite":
            image = obj.image
            if image is None:
                raise UnityError(f"sprite has no decodable image: {asset.path}")
            written.append(save_texture(image, stem, chosen))
        elif type_name == "AudioClip":
            written.append(_export_audio(obj, out_dir, asset.path, chosen))
        elif type_name == "Mesh":
            written.append(_export_mesh(obj, out_dir, asset.path, chosen))
        elif type_name == "TextAsset":
            data = obj.m_Script
            if isinstance(data, str):
                data = data.encode("utf-8")
            written.append(save_text(data, stem, "txt"))
        elif type_name in {"MonoBehaviour", "Shader", "Material"}:
            try:
                data = obj.raw_data
            except AttributeError:
                data = asset._reader.get_raw_data()
            written.append(_write_bytes(stem.with_suffix(".bin"), data))
        else:
            data = asset._reader.get_raw_data()
            written.append(_write_bytes(stem.with_suffix(".bin"), data))
        return written


def _mesh_to_obj(name: str, verts, tris, uvs) -> bytes:
    lines = [f"o {name or 'mesh'}"]
    for vertex in verts:
        x, y, z = vertex[0], vertex[1], vertex[2] if len(vertex) > 2 else 0.0
        lines.append(f"v {x} {y} {z}")
    if uvs:
        for uv in uvs:
            u, v = uv[0], uv[1] if len(uv) > 1 else 0.0
            lines.append(f"vt {u} {v}")
    for submesh in tris:
        for tri in submesh:
            if uvs:
                lines.append("f " + " ".join(f"{i + 1}/{i + 1}" for i in tri))
            else:
                lines.append("f " + " ".join(str(i + 1) for i in tri))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _export_mesh(obj, out_dir: str, asset_path: str, fmt: str) -> str:
    from dualforge.export.convert import save_mesh
    from UnityPy.helpers import MeshHelper

    handler = MeshHelper.MeshHandler(obj)
    handler.process()
    name = str(getattr(obj, "m_Name", "") or "").strip()
    verts = handler.m_Vertices
    tris = handler.get_triangles()
    if not verts or not any(tris):
        raise UnityError(f"mesh has no decodable geometry: {asset_path}")
    uvs = handler.m_UV0 or []
    data = _mesh_to_obj(name, verts, tris, uvs)
    stem = _output_stem(out_dir, asset_path)
    return save_mesh(name or "mesh", data, stem, fmt)


def _export_audio(obj, out_dir: str, asset_path: str, fmt: str) -> str:
    from UnityPy.export import AudioClipConverter

    stem = _output_stem(out_dir, asset_path)
    fmt = fmt.lower().lstrip(".")
    if fmt == "raw":
        raw = getattr(obj, "m_AudioData", None)
        if raw is None:
            raw = getattr(obj, "raw_data", None)
        if raw:
            return _write_bytes(stem.with_suffix(".audio"), bytes(raw))
        raise UnityError("audio has no raw data to export")
    try:
        samples = AudioClipConverter.extract_audioclip_samples(obj)
    except Exception as exc:
        raw = getattr(obj, "m_AudioData", None) or getattr(obj, "raw_data", None)
        if raw:
            return _write_bytes(stem.with_suffix(".audio"), bytes(raw))
        raise UnityError(f"audio export failed: {exc}") from exc
    if not samples:
        raise UnityError("audio clip produced no samples")
    name, data = next(iter(samples.items()))
    if fmt in {"wav", "ogg"} and Path(name).suffix.lower() == f".{fmt}":
        return _write_bytes(stem.with_suffix(f".{fmt}"), data)
    if fmt == "flac":
        try:
            from dualforge.audio import Vgmstream

            source = _write_bytes(stem.with_suffix(Path(name).suffix or ".wav"), data)
            return Vgmstream().convert(source, str(stem.with_suffix(".flac")), "flac")
        except Exception as exc:
            raise UnityError(f"flac export requires vgmstream: {exc}") from exc
    return _write_bytes(stem.with_suffix(Path(name).suffix or ".wav"), data)


def _sanitize_name(name: str) -> str:
    clean = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in name)
    return clean.strip() or "unnamed"


def _output_stem(out_dir: str, asset_path: str, name: str | None = None) -> Path:
    stem = name or Path(asset_path).name
    target = (
        Path(out_dir)
        / _sanitize_name(Path(asset_path).parent.as_posix())
        / _sanitize_name(stem)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _write_bytes(path: Path, data: bytes) -> str:
    with open(path, "wb") as fh:
        fh.write(data)
    return str(path)


__all__ = ["UnityArchive", "UnityAsset", "UnityError"]
