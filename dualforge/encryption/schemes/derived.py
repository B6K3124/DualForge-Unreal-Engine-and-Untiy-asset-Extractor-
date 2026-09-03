"""Derived-key decryption schemes.

Some games don't encrypt with the key you provide directly - they derive the
real key from the archive name/path at runtime:

- **Snowbreak**:  md5(hex(pakname)) as ascii-hex string -> AES-256-ECB encrypt
  with the provided key -> use that 32-byte result as the actual key.
- **Star Savior**: mask = md5(filename + ".bytes") used as a repeating XOR mask.
"""

from __future__ import annotations

import hashlib

from dualforge.encryption.registry import Context, KeyMaterial, register


def _aes_ecb_encrypt(key_bytes: bytes, data: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    cipher = Cipher(algorithms.AES(key_bytes), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()


@register("derived-aes-md5")
def derived_aes_md5(data: bytes, key: KeyMaterial, ctx: Context) -> bytes:
    """Snowbreak-style: derive the working AES key from the archive filename.

    working_key = AES_ECB_encrypt( key, md5_hex(pakname) )
    Then ECB-decrypt ``data`` with working_key.
    """
    from dualforge.encryption.schemes.aes import _aes_ecb_decrypt

    name = (key.parameters.get("derived_name") or ctx.archive_name or "").strip()
    if not name:
        return data
    pakname = name.split("/")[-1].rsplit(".", 1)[0].lower()
    md5_hex = hashlib.md5(pakname.encode("ascii")).hexdigest().lower()
    provider_key = key.hex_bytes()
    if len(provider_key) not in (16, 32):
        # pad/truncate leniently to 32
        provider_key = (provider_key + b"\x00" * 32)[:32]
    working_key = _aes_ecb_encrypt(provider_key, md5_hex.encode("ascii"))
    if len(data) % 16 != 0:
        whole = len(data) - (len(data) % 16)
        return _aes_ecb_decrypt(working_key, data[:whole]) + data[whole:]
    return _aes_ecb_decrypt(working_key, data)


@register("derived-xor-md5")
def derived_xor_md5(data: bytes, key: KeyMaterial, ctx: Context) -> bytes:
    """Star-Savior-style: md5(filename + suffix) is the repeating XOR mask."""
    filename = (key.parameters.get("derived_filename") or ctx.archive_name or "").strip()
    suffix = key.parameters.get("filename_suffix", ".bytes")
    if not filename:
        return data
    stem = filename.split("/")[-1]
    mask = hashlib.md5((stem + suffix).encode("utf-8")).digest()
    raw = key.parameters.get("header_bytes", key.parameters.get("length", "0")) or "0"
    header = int(raw)
    if header <= 0:
        header = len(data)
    header = min(header, len(data))
    out = bytearray(data[:header])
    for i in range(header):
        out[i] ^= mask[i % 16]
    return bytes(out) + data[header:]
