"""Tests for the dualforge.encryption package: schemes, pipeline and presets."""

from __future__ import annotations

from dualforge.encryption import list_schemes
from dualforge.encryption.pipeline import TransformPipeline
from dualforge.encryption.presets import guess_scheme
from dualforge.encryption.registry import Context, KeyMaterial
from dualforge.encryption.schemes.aes import _aes_ecb_decrypt
from dualforge.encryption.schemes.roundkey import decrypt_custom_roundkeys, expand_key


def test_all_schemes_registered():
    names = set(list_schemes())
    assert {
        "aes-256",
        "xor8",
        "xor",
        "xor-header",
        "derived-aes-md5",
        "derived-xor-md5",
        "partial-encrypt",
        "unity-cn",
        "custom-aes-round",
        "delta-force",
    } <= names


def test_aes256_roundtrip_vector():
    # FIPS-197 AES-128 canonical vector
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    ciphertext = bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")
    plaintext = bytes.fromhex("00112233445566778899aabbccddeeff")
    km = KeyMaterial(key_str=key.hex(), scheme="aes-256")
    assert _aes_ecb_decrypt(key, ciphertext) == plaintext
    from dualforge.encryption.registry import transform

    assert transform(ciphertext, "aes-256", km, Context()) == plaintext


def test_aes256_non_aligned_tail_passthrough():
    km = KeyMaterial(key_str="AB" * 32, scheme="aes-256")
    from dualforge.encryption.registry import transform

    data = bytes.fromhex("00112233445566778899aabbccddeeff") + b"Z"
    out = transform(data, "aes-256", km, Context())
    assert out[-1:] == b"Z"


def test_custom_roundkeys_matches_standard_aes():
    key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
    pt = bytes.fromhex("3243f6a8885a308d313198a2e0370734")
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    ct = cipher.encryptor().update(pt) + cipher.encryptor().finalize()

    # Recovered schedule must decrypt the standard ciphertext to the plaintext.
    flat = expand_key(key)
    assert decrypt_custom_roundkeys(ct, bytes(flat)) == pt


def test_expand_key_matches_pyca_schedule():
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    flat = expand_key(key)
    assert flat[0:16] == list(key)
    assert len(flat) == 11 * 16  # AES-128: 11 round keys


def test_xor_scheme():
    from dualforge.encryption.registry import transform

    km = KeyMaterial(key_str="0a", scheme="xor")
    assert transform(b"\x01\x02\x03", "xor", km, Context()) == b"\x0b\x08\x09"


def test_xor_header_only_first_n():
    from dualforge.encryption.registry import transform

    params = {"header_bytes": "2"}
    km = KeyMaterial(key_str="ff", scheme="xor-header", parameters=params)
    out = transform(b"\x01\x02\x03\x04", "xor-header", km, Context())
    assert out[0:2] == b"\xfe\xfd"
    assert out[2:] == b"\x03\x04"


def test_xor_header_zero_means_all():
    from dualforge.encryption.registry import transform

    km = KeyMaterial(key_str="0a", scheme="xor-header", parameters={"header_bytes": "0"})
    assert transform(b"\x01\x02\x03", "xor-header", km, Context()) == b"\x0b\x08\x09"


def test_delta_force_pipeline_stages():
    pipe = TransformPipeline.from_scheme("aes-256+xor8")
    assert [s.name for s in pipe.stages] == ["aes-256", "xor8"]


def test_guess_scheme_by_mount():
    assert guess_scheme(archive_name="pakchunk0-Windows.pak", mount="FortniteGame") is not None
    assert guess_scheme(archive_name="a.pak", mount="/Game/Snowbreak") is not None


def test_scheme_validation_matches_preset_names():
    from dualforge.encryption.presets import PRESETS

    names = {p.name for p in PRESETS}
    assert "snowbreak" in names
    assert "delta-force" in names
