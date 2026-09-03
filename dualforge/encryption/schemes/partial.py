"""Partially-encrypted pak support (Wuthering Waves / NetEase pattern).

In these archives only some entries are encrypted; the reader decides per entry
via a partial-encryption flag. ``partial`` is a meta-scheme: it tells the
pipeline whether to apply AES to a given block, using ``ctx.extra`` flags.
"""

from __future__ import annotations

from dualforge.encryption.registry import Context, KeyMaterial, register
from dualforge.encryption.schemes.aes import _aes_ecb_decrypt


@register("partial-encrypt")
def partial_decrypt(data: bytes, key: KeyMaterial, ctx: Context) -> bytes:
    """Decrypt with AES only when the block is flagged as encrypted."""
    if ctx.extra.get("encrypted") in ("0", "false", "False", "", None):
        return data
    from dualforge.encryption.registry import unhex

    kb = unhex(key.key_str)
    if not kb:
        return data
    if len(data) % 16 != 0:
        whole = len(data) - (len(data) % 16)
        return _aes_ecb_decrypt(kb, data[:whole]) + data[whole:]
    return _aes_ecb_decrypt(kb, data)
