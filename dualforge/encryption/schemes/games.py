"""Per-game decryption schemes ported from reverse-engineering of CUE4Parse.

Each scheme mirrors the documented behaviour of a real game's protection. The
implementations are written from public algorithm descriptions to avoid copying
any library code verbatim.

Implemented in this module:
- ``delta-force``   AES-256 ECB followed by an 8-byte repeating XOR, where the
                    XOR key is recovered from the (auto-detected) pak index
                    custom-encryption data when not supplied directly.

Additional schemes registered in this file are framework entries; the
``custom-aes-round`` core (used by games that replace AES round keys) is
implemented in ``roundkey.py``.
"""

from __future__ import annotations

from dualforge.encryption.registry import Context, KeyMaterial, register, unhex
from dualforge.encryption.schemes.aes import _aes_ecb_decrypt
from dualforge.encryption.schemes.xor import _repeating_xor


@register("delta-force")
def delta_force(data: bytes, key: KeyMaterial, ctx: Context) -> bytes:
    """AES-256 ECB, then XOR with an 8-byte key.

    The XOR key is taken from ``key.parameters['xor_key']`` (8 bytes hex),
    ``key.parameters['xor_byte']`` (single repeating byte), or recovered from
    the index ``custom_encryption_data`` carried in ``ctx.extra``.
    """
    kb = unhex(key.key_str)
    if not kb:
        return data
    if len(data) % 16 != 0:
        whole = len(data) - (len(data) % 16)
        decrypted = _aes_ecb_decrypt(kb, data[:whole]) + data[whole:]
    else:
        decrypted = _aes_ecb_decrypt(kb, data)

    xor_key = _resolve_xor(key, ctx)
    if xor_key:
        return _repeating_xor(decrypted, xor_key, 0)
    return decrypted


def _resolve_xor(key: KeyMaterial, ctx: Context) -> bytes:
    params = key.parameters
    if params.get("xor_key"):
        raw = unhex(params["xor_key"])
        if len(raw) >= 8:
            return raw[:8]
    if params.get("xor_byte") is not None:
        try:
            byte = int(params["xor_byte"], 0) & 0xFF
            return bytes([byte]) * 8
        except ValueError:
            pass
    # Auto-recover: CUE4Parse recovers the XOR byte from a block where the
    # first 4 bytes are all equal after AES (the encrypted index marker).
    if ctx.extra.get("xor_byte_auto") is not None:
        try:
            byte = int(ctx.extra["xor_byte_auto"], 0) & 0xFF
            return bytes([byte]) * 8
        except ValueError:
            pass
    return b""


from dualforge.encryption.schemes.roundkey import decrypt_custom_roundkeys  # noqa: E402


@register("custom-aes-round")
def custom_aes_round(data: bytes, key: KeyMaterial, ctx: Context) -> bytes:
    """Decrypt with a game-supplied AES round-key schedule.

    ``key.parameters['round_keys']`` carries the (hex) concatenated round keys,
    or ``key.parameters['round_keys_base']`` which is expanded to 11 rounds via
    the standard key schedule when only the base key is provided.
    """
    rk = key.parameters.get("round_keys")
    if rk:
        raw = unhex(rk)
        if raw and len(raw) % 16 == 0:
            return decrypt_custom_roundkeys(data, raw)
    base = key.parameters.get("round_keys_base") or key.key_str
    if base:
        raw = unhex(base)
        if len(raw) in (16, 24, 32):
            from dualforge.encryption.schemes.roundkey import expand_key

            flat = expand_key(raw)
            return decrypt_custom_roundkeys(data, bytes(flat))
    return data
