from __future__ import annotations

from dataclasses import dataclass, field
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
            value = getattr(file, "version_engine", None)
            if value:
                return str(value).strip()
        return ""

    def serialized_version(self) -> int:
        """Best-effort serialized format version (bundle header or -1)."""
        for file in self.env.files.values():
            value = getattr(file, "version", None)
            if isinstance(value, int):
                return value
        return -1

    def set_decrypt_key(self, key: str) -> None:
        try:
            self._types.set_assetbundle_decrypt_key(key)
        except (AttributeError, TypeError) as exc:
            raise UnityError(f"could not set decrypt key: {exc}") from exc

    def assets(self) -> Iterator[UnityAsset]:
        for path, reader in self.env.container.items():
            yield UnityAsset(
                path=path,
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
        from dualforge.export.convert import DEFAULT_FORMATS, save_mesh, save_text, save_texture

        written: List[str] = []
        obj = asset._reader.read()
        type_name = obj.type.name
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
            try:
                from UnityPy.helpers import MeshExporter
            except ImportError as exc:
                raise UnityError("Mesh export requires UnityPy.helpers") from exc
            name, data = MeshExporter.export_obj(obj)
            written.append(save_mesh(name, data, stem, chosen))
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


def _export_audio(obj, out_dir: str, asset_path: str, fmt: str) -> str:
    try:
        from UnityPy.helpers import AudioClipConverter
    except ImportError as exc:
        raise UnityError("Audio export requires UnityPy.helpers") from exc
    stem = _output_stem(out_dir, asset_path)
    fmt = fmt.lower().lstrip(".")
    if fmt == "raw":
        raw = getattr(obj, "m_AudioData", None)
        if raw is None:
            raw = getattr(obj, "raw_data", None)
        if raw:
            return _write_bytes(stem.with_suffix(".audio"), raw)
        raise UnityError("audio has no raw data to export")
    try:
        data = AudioClipConverter.export_wav(obj)
        target = _write_bytes(stem.with_suffix(".wav"), data)
    except Exception as wav_exc:
        try:
            data = AudioClipConverter.export_ogg(obj)
            target = _write_bytes(stem.with_suffix(".ogg"), data)
            if fmt == "ogg":
                return target
        except Exception as ogg_exc:
            raw = getattr(obj, "m_AudioData", None) or getattr(obj, "raw_data", None)
            if raw:
                return _write_bytes(stem.with_suffix(".audio"), raw)
            raise UnityError(f"audio export failed (wav: {wav_exc}, ogg: {ogg_exc})") from wav_exc
        raise UnityError(f"wav export failed: {wav_exc}") from wav_exc
    if fmt in {"wav", "ogg"}:
        if fmt == "ogg":
            try:
                data = AudioClipConverter.export_ogg(obj)
                return _write_bytes(stem.with_suffix(".ogg"), data)
            except Exception as ogg_exc:
                raise UnityError(f"ogg export failed: {ogg_exc}") from ogg_exc
        return target
    if fmt == "flac":
        try:
            from dualforge.audio import Vgmstream

            converted = Vgmstream().convert(target, str(stem.with_suffix(".flac")), "flac")
            return converted
        except Exception as exc:
            raise UnityError(f"flac export requires vgmstream: {exc}") from exc
    raise UnityError(f"unsupported audio format: {fmt}")


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
