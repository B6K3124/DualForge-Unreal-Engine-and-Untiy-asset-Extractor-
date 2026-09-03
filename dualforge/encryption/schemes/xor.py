"""Repeating-key XOR decryption schemes (Unity bundles, Delta-Force-style post-XOR)."""

from __future__ import annotations

from dualforge.encryption.registry import Context, KeyMaterial, register


def _repeating_xor(data: bytes, key: bytes, start: int = 0) -> bytes:
    if not key or not data:
        return data
    klen = len(key)
    out = bytearray(data)
    for i in range(start, len(out)):
        out[i] ^= key[(i - start) % klen]
    return bytes(out)


@register("xor")
def xor_scheme(data: bytes, key: KeyMaterial, ctx: Context) -> bytes:
    """General repeating-key XOR.

    Key material: a hex or plain bytes string. Optional parameters:
      - ``start``: byte offset where XOR begins (default 0)
      - ``length``: max number of bytes to XOR (default all)
      - ``repeats``: repeat pattern across the whole key (default true)
    """
    kb = key.hex_bytes()
    if not kb:
        return data
    params = key.parameters
    start = int(params.get("start", params.get("offset", "0")))
    length = int(params.get("length", "0") or 0)
    key_is_derived_from_path = params.get("derived_from") == "filename"
    if key_is_derived_from_path:
        # Key byte string is treated as a literal mask (e.g. Unity CN).
        kb = key.key_str.encode("utf-8")
    if length > 0:
        cap = min(length, len(data) - start)
        prefix = data[:start] if start else b""
        seg = data[start : start + cap]
        return prefix + _repeating_xor(seg, kb, 0) + data[start + cap :]
    return _repeating_xor(data, kb, start)


@register("xor8")
def xor8(data: bytes, key: KeyMaterial, ctx: Context) -> bytes:
    """8-byte repeating XOR (Delta Force post-decrypt)."""
    kb = key.hex_bytes()
    if len(kb) < 8:
        return data
    return _repeating_xor(data, kb[:8], 0)


@register("xor-header")
def xor_header(data: bytes, key: KeyMaterial, ctx: Context) -> bytes:
    """XOR only the leading ``header_bytes`` of a bundle (Unity pattern).

    ``header_bytes <= 0`` (or missing) means Xor the whole block, matching the
    ``unity-cn`` convention.
    """
    kb = key.hex_bytes() or key.key_str.encode("utf-8")
    if not kb:
        return data
    raw = key.parameters.get("header_bytes", key.parameters.get("length", "0")) or "0"
    n = int(raw)
    if n <= 0:
        n = len(data)
    n = min(n, len(data))
    return _repeating_xor(data[:n], kb, 0) + data[n:]
