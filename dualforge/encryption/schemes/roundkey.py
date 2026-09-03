"""Framework for games that substitute AES round keys / custom S-box.

A growing family of CUE4Parse "custom encryption" schemes (Monster Jam
Showdown, Styx: Blades of Greed, and many of the pseudo-AES entries such as
Apex Mobile, Snowbreak's older path, etc.) replace the standard AES round keys
with game-specific constants. These are not standard AES and need a raw AES
engine where the round keys can be injected.

This module provides a compact, correct, dependency-free AES-128/256 engine
that accepts explicit round keys, plus the shared boilerplate to decrypt with
game-supplied constants. Standard AES (provided by ``cryptography`` / the
``aes`` scheme) remains the fast path for ordinary archives.
"""

from __future__ import annotations

# ---- standard AES S-box (FIPS-197) ----
_SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)

_INV_SBOX = [0] * 256
for _i, _b in enumerate(_SBOX):
    _INV_SBOX[_b] = _i

# 2^i in GF(2^8)
_GF2 = [0] * 8
_GF2[0] = 1
for _i in range(1, 8):
    _GF2[_i] = (_GF2[_i - 1] << 1) ^ (0x1B if _GF2[_i - 1] & 0x80 else 0)


def _xtime(a: int) -> int:
    return ((a << 1) ^ (0x1B if a & 0x80 else 0)) & 0xFF


def _gmul(a: int, b: int) -> int:
    """GF(2^8) multiply using Russian peasant multiplication."""
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a <<= 1
        if hi:
            a ^= 0x1B
        a &= 0xFF
        b >>= 1
    return p


def expand_key(key: bytes) -> list:
    """Standard AES key expansion. Returns a flat list of round-key bytes."""
    nk = len(key) // 4
    nr = 6 + nk
    w = [list(key[4 * i : 4 * i + 4]) for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= rcon
            rcon = _xtime(rcon)
        elif nk > 6 and i % nk == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])
    flat = []
    for word in w:
        flat.extend(word)
    return flat


def _decrypt_block(state: bytes, round_keys: list, nr: int) -> bytes:
    """AES decrypt using an explicit round-key schedule (returns 16 bytes)."""
    s = list(state)
    # initial AddRoundKey (last round key)
    for i in range(16):
        s[i] ^= round_keys[nr * 16 + i]
    for rnd in range(nr - 1, 0, -1):
        # InvShiftRows
        s = [
            s[0], s[13], s[10], s[7],
            s[4], s[1], s[14], s[11],
            s[8], s[5], s[2], s[15],
            s[12], s[9], s[6], s[3],
        ]
        # InvSubBytes
        s = [_INV_SBOX[b] for b in s]
        # AddRoundKey
        for i in range(16):
            s[i] ^= round_keys[rnd * 16 + i]
        # InvMixColumns
        s = _inv_mix_columns(s)
    # last round (no InvMixColumns)
    s = [
        s[0], s[13], s[10], s[7],
        s[4], s[1], s[14], s[11],
        s[8], s[5], s[2], s[15],
        s[12], s[9], s[6], s[3],
    ]
    s = [_INV_SBOX[b] for b in s]
    for i in range(16):
        s[i] ^= round_keys[i]
    return bytes(s)


def _inv_mix_columns(s: list) -> list:
    out = [0] * 16
    for c in range(4):
        a0, a1, a2, a3 = s[c * 4 + 0], s[c * 4 + 1], s[c * 4 + 2], s[c * 4 + 3]
        out[c * 4 + 0] = _gmul(a0, 0x0E) ^ _gmul(a1, 0x0B) ^ _gmul(a2, 0x0D) ^ _gmul(a3, 0x09)
        out[c * 4 + 1] = _gmul(a0, 0x09) ^ _gmul(a1, 0x0E) ^ _gmul(a2, 0x0B) ^ _gmul(a3, 0x0D)
        out[c * 4 + 2] = _gmul(a0, 0x0D) ^ _gmul(a1, 0x09) ^ _gmul(a2, 0x0E) ^ _gmul(a3, 0x0B)
        out[c * 4 + 3] = _gmul(a0, 0x0B) ^ _gmul(a1, 0x0D) ^ _gmul(a2, 0x09) ^ _gmul(a3, 0x0E)
    return out


def decrypt_custom_roundkeys(data: bytes, round_keys: bytes) -> bytes:
    """Decrypt AES-128 blocks using an explicit round-key schedule.

    ``round_keys`` must be (nr+1)*16 bytes. Returns decrypted bytes.
    """
    nr = len(round_keys) // 16 - 1
    schedule = [round_keys[16 * i : 16 * i + 16] for i in range(nr + 1)]
    flat = []
    for word in schedule:
        flat.extend(word)
    out = bytearray()
    whole = len(data) - (len(data) % 16)
    for off in range(0, whole, 16):
        out += _decrypt_block(data[off : off + 16], flat, nr)
    out += data[whole:]
    return bytes(out)


def decrypt_custom_with_pre_xor(data: bytes, round_keys: bytes, xor_white: bytes = b"") -> bytes:
    """Monster Jam / Styx style: XOR the first round with an extra pad then run
    the injected -round-key decrypt (the CUE4Parse template does the first
    AddRoundKey manually via a round-keys[0] XOR, then decrypts with the rest).
    """
    nr = len(round_keys) // 16 - 1
    schedule = [bytes(round_keys[16 * i : 16 * i + 16]) for i in range(nr + 1)]
    flat = []
    for word in schedule:
        flat.extend(word)
    out = bytearray()
    whole = len(data) - (len(data) % 16)
    for off in range(0, whole, 16):
        blk = bytearray(data[off : off + 16])
        if xor_white:
            for i in range(16):
                blk[i] ^= xor_white[i % len(xor_white)]
        out += _decrypt_block(bytes(blk), flat, nr)
    out += data[whole:]
    return bytes(out)
