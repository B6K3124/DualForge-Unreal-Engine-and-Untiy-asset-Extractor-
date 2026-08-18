from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_ENDPOINTS = [
    "https://fortnitecentral.ga/api/v1/aes",
    "https://aes.ue4server.com/",
]


@dataclass
class KeyEntry:
    title: str
    aes_key: str
    engine: str = "unreal"
    notes: str = ""
    updated: str = ""
    dynamic_keys: Dict[str, str] = field(default_factory=dict)


class KeyStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or str(Path.home() / ".dualforge" / "keys.json")
        self._entries: Dict[str, KeyEntry] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return
        for key, value in raw.items():
            if isinstance(value, str):
                self._entries[key] = KeyEntry(title=key, aes_key=value)
            elif isinstance(value, dict):
                dynamic = value.get("dynamic_keys") or value.get("dynamicKeys") or {}
                self._entries[key] = KeyEntry(
                    title=value.get("title", key),
                    aes_key=value.get("aes_key", value.get("key", "")),
                    engine=value.get("engine", "unreal"),
                    notes=value.get("notes", ""),
                    updated=value.get("updated", ""),
                    dynamic_keys={str(k): str(v) for k, v in dynamic.items()},
                )

    def _save(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({k: asdict(v) for k, v in self._entries.items()}, fh, indent=2)

    def list(self) -> List[KeyEntry]:
        return list(self._entries.values())

    def get(self, title: str) -> Optional[str]:
        entry = self._entries.get(title)
        return entry.aes_key if entry else None

    def get_entry(self, title: str) -> Optional[KeyEntry]:
        return self._entries.get(title)

    def add(
        self,
        title: str,
        aes_key: str,
        engine: str = "unreal",
        notes: str = "",
        dynamic_keys: Optional[Dict[str, str]] = None,
    ) -> None:
        if not title or not aes_key:
            raise ValueError("title and aes_key are required")
        self._entries[title] = KeyEntry(
            title=title,
            aes_key=aes_key,
            engine=engine,
            notes=notes,
            updated=datetime.now(timezone.utc).isoformat(),
            dynamic_keys={str(k): str(v) for k, v in (dynamic_keys or {}).items()},
        )
        self._save()

    def remove(self, title: str) -> bool:
        if title in self._entries:
            del self._entries[title]
            self._save()
            return True
        return False

    def import_mapping(
        self,
        mapping: Dict[str, str],
        engine: str = "unreal",
        dynamic: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> int:
        count = 0
        for title, key in mapping.items():
            if not title or not key:
                continue
            existing = self._entries.get(title)
            dyn = (dynamic or {}).get(title, {})
            if existing is None:
                self.add(
                    title,
                    key,
                    engine=engine,
                    notes="imported",
                    dynamic_keys=dyn,
                )
                count += 1
            else:
                merged = {**existing.dynamic_keys, **dyn}
                changed = existing.aes_key != key or set(merged) != set(existing.dynamic_keys)
                if changed:
                    self.add(
                        existing.title,
                        key,
                        engine=existing.engine,
                        notes=existing.notes,
                        dynamic_keys=merged,
                    )
                    count += 1
        return count

    def import_fmodel_json(self, path: str) -> int:
        """Import an FModel Global.AESKeys.json key file.

        Format: {"GameName": {"mainKey": "0x...", "dynamicKeys": {"guid": "0x..."}}}
        """
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if not isinstance(payload, dict):
            raise ValueError("FModel key file must contain a JSON object")
        count = 0
        for title, value in payload.items():
            if not isinstance(value, dict):
                continue
            main_key = ""
            for candidate in ("mainKey", "main_key", "aes_key", "key"):
                if value.get(candidate):
                    main_key = str(value[candidate])
                    break
            dynamic = value.get("dynamicKeys") or value.get("dynamic_keys") or {}
            if not main_key:
                continue
            existing = self._entries.get(title)
            if existing is None:
                self.add(
                    title,
                    main_key,
                    engine="unreal",
                    notes="imported from FModel",
                    dynamic_keys=dynamic,
                )
                count += 1
            elif main_key != existing.aes_key or set(dynamic) != set(existing.dynamic_keys):
                self.add(
                    existing.title,
                    main_key,
                    engine=existing.engine,
                    notes=existing.notes,
                    dynamic_keys=dynamic,
                )
                count += 1
        return count

    def sync(self, endpoints: List[str]) -> Dict[str, int]:
        import requests

        synced: Dict[str, int] = {}
        for endpoint in endpoints:
            response = requests.get(endpoint, timeout=30)
            response.raise_for_status()
            payload = response.json()
            mapping, dynamic = _extract_keys(payload)
            synced[endpoint] = self.import_mapping(mapping, dynamic=dynamic)
        return synced


def _extract_keys(payload) -> Tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
    """Extract main + dynamic keys from a community endpoint payload.

    Supports FModel-style {"games": {...}}, FortniteCentral's
    {"mainKey": ..., "dynamicKeys": {...}}, and the plain
    {"Game": "0x..."} / {"keys": {...}} shapes.
    Returns (main_keys, dynamic) where dynamic maps title ->
    {"keys": {...}, "new": bool}.
    """
    mapping: Dict[str, str] = {}
    dynamic: Dict[str, Dict[str, str]] = {}
    if not isinstance(payload, dict):
        return mapping, dynamic
    source = payload
    if "games" in payload and isinstance(payload["games"], dict):
        source = payload["games"]
    elif "keys" in payload and isinstance(payload["keys"], dict):
        source = payload["keys"]
    for title, value in source.items():
        if title in (
            "mainKey", "main_key", "aes_key", "key",
            "dynamicKeys", "dynamic_keys", "version", "build", "updated",
        ):
            continue
        if isinstance(value, str):
            mapping[title] = value
        elif isinstance(value, dict):
            main_key = ""
            for field in ("mainKey", "main_key", "aes_key", "key"):
                if value.get(field):
                    main_key = str(value[field])
                    break
            if main_key:
                mapping[title] = main_key
            dynamic_keys = value.get("dynamicKeys") or value.get("dynamic_keys")
            if isinstance(dynamic_keys, dict):
                dynamic[title] = {str(k): str(v) for k, v in dynamic_keys.items()}
    for field in ("mainKey", "main_key", "aes_key", "key"):
        if source.get(field):
            mapping["Fortnite"] = str(source[field])
            dynamic_keys = source.get("dynamicKeys") or source.get("dynamic_keys")
            if isinstance(dynamic_keys, dict):
                dynamic["Fortnite"] = {str(k): str(v) for k, v in dynamic_keys.items()}
            break
    return mapping, dynamic


__all__ = ["KeyStore", "KeyEntry", "DEFAULT_ENDPOINTS"]