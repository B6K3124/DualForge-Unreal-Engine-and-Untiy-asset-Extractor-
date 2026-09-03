"""Unity CN Pro bundle decryption (many Chinese Unity games).

Unity CN Pro uses a fixed 16-char key XORed over the bundle header. The key is a
plain ASCII string (e.g. ``XxecodrPeGaka2e6``) handled by ``cryptography``'s
XOR path rather than AES. ``unity-cn`` routes to the generic ``xor-header``
scheme with the key treated as a literal ASCII mask.
"""

from __future__ import annotations

from dualforge.encryption.registry import Context, KeyMaterial, register
from dualforge.encryption.schemes.xor import _repeating_xor


@register("unity-cn")
def unity_cn(data: bytes, key: KeyMaterial, ctx: Context) -> bytes:
    mask = key.key_str.strip().encode("utf-8")
    if not mask:
        return data
    n = int(key.parameters.get("header_bytes", key.parameters.get("length", "0")) or 0)
    if n <= 0:
        n = len(data)
    n = max(0, min(n, len(data)))
    return _repeating_xor(data[:n], mask, 0) + data[n:]
