# DualForge — Compression Format Reference

## Layer 1: Archive / container compression

### Unreal Engine classic `.pak` (`EPakCompressionMethod` flags)

| Method   | Notes                                        | Handler in DualForge                 |
| -------- | -------------------------------------------- | ------------------------------------ |
| None     | passthrough                                  | native                               |
| Zlib     | UE4 default below 4.27                       | `zlib` (stdlib)                      |
| Gzip     | UE4                                          | `gzip` (stdlib)                      |
| LZ4      | UE4.22+                                      | `lz4` (pip, BSD-3)                   |
| Zstd     | UE4.27+ / UE5                                | `zstandard` (pip, BSD)               |
| Oodle    | UE4.27+ / UE5 default (Kraken/Mermaid/Leviathan) | CUE4Parse (C#) or ctypes `oo2core_*.dll` |
| Custom   | rare, game-specific                          | CUE4Parse + custom handlers          |

### Unreal Engine IoStore `.utoc` / `.ucas` (`EIoCompressionMethod`)

None, Zlib, Gzip, Custom, Zstd, Oodle, LZ4, Brotli (UE 5.x+). Oodle sub-methods:
Kraken (default), Mermaid, Leviathan; legacy Selkie / BitKnit / LZNA / LZH / LZB / LZA.

### Unity AssetBundle / serialized files

| Format      | Notes                                                    | Handler                  |
| ----------- | -------------------------------------------------------- | ------------------------ |
| None        | 16-byte aligned, no decompression                        | passthrough              |
| LZMA        | default stream compression (not WebGL)                   | `lzma` / UnityPy         |
| LZ4 / LZ4HC | chunk-based, Unity 5.3+                                  | UnityPy                  |
| Brotli      | seen in newer/CN builds                                  | UnityPy                  |
| Zstd        | seen in newer/CN builds                                  | UnityPy                  |
| Snappy      | rare                                                      | optional `python-snappy` |

## Layer 2: Asset-level codecs (export phase)

| Type    | Formats                                                        | Handler                  |
| ------- | -------------------------------------------------------------- | ------------------------ |
| Audio   | Wwise WEM (Vorbis/Opus/WwiseADPCM), FSB, OGG, XMA, MP3, ADPCM  | vgmstream, UnityPy       |
| Texture | BC1–BC7/DXT, ASTC, ETC/ETC2, PVRTC, ATC, RGTC, CRN, Oodle Tex  | UnityPy, CUE4Parse       |
| Video   | Bink/Bink2, USM, VP9, H.264                                    | Phase 3+                 |
| Shader  | Oodle/Zlib-compressed `.ushaderbytecode`                       | CUE4Parse                |
| LocRes  | LZ4 (UE5)                                                      | CUE4Parse                |

## Python support matrix

| Codec    | Package       | License    | Note                                        |
| -------- | ------------- | ---------- | ------------------------------------------- |
| zlib     | stdlib        | PSF        |                                             |
| gzip     | stdlib        | PSF        |                                             |
| bz2      | stdlib        | PSF        |                                             |
| lzma     | stdlib        | PSF        | LZMA1/LZMA2                                 |
| lz4      | `lz4`         | BSD-3      | block + frame + raw                         |
| zstd     | `zstandard`   | BSD        |                                             |
| brotli   | `brotli`      | MIT        |                                             |
| snappy   | `python-snappy` | BSD      | optional                                    |
| zip      | stdlib        | PSF        |                                             |
| 7z       | `py7zr`       | LGPL-2.1   |                                             |
| oodle    | `oo2core_*.dll` | RAD proprietary | never bundle; load from target game or official SDK |
| oodle-py | `python_oodle` / `kraken-decompressor` | GPLv3 | **not used** — would force DualForge open-source |

## Oodle policy

- Decompression is provided by CUE4Parse internally (Unreal path) or by
  `dualforge/compression/oodle.py` which loads the game-shipped `oo2core_*.dll`
  and calls the public `OodleLZ_Decompress` export via ctypes.
- GPLv3 Python wrappers (`python_oodle`, `kraken-decompressor`) are deliberately
  excluded to keep the commercial build closed-source.
- The DLL is never redistributed with DualForge.

## Nested container sniffing

After decompression, `sniff()` checks magic bytes for `gzip`, `bz2`, `xz/lzma`,
`zstd`, `zip`, `7z`, `lz4` frames and recursively extracts nested archives.
