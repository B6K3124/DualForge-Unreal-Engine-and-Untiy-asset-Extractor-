# DualForge — License Ledger

Third-party components used by DualForge and their license status.

| Component       | License        | Redistribution note                              |
| --------------- | -------------- | ------------------------------------------------ |
| Python 3        | PSF-2.0        | fine                                             |
| PySide6         | LGPL-3.0       | OK for closed-source commercial apps; dynamic linking required |
| UnityPy         | MIT            | keep attribution (About dialog)                  |
| numpy           | BSD-3          | fine                                             |
| Pillow          | HPND (MIT-like)| fine                                             |
| lz4             | BSD-3          | fine                                             |
| zstandard       | BSD            | fine                                             |
| brotli          | MIT            | fine                                             |
| py7zr           | LGPL-2.1       | fine (dynamic)                                   |
| python-snappy   | BSD            | optional                                         |
| CUE4Parse / CUE4ParseCLI | MIT | keep attribution (About dialog)              |
| vgmstream       | custom / LGPL-ish | **verify before distributing**                |
| oo2core_*.dll   | RAD Game Tools proprietary | never bundle; load on demand from target game or official SDK |
| ooz / python_oodle / kraken-decompressor | GPLv3 | excluded by policy                       |

## Policy

- The GPLv3 Oodle wrappers are intentionally excluded to keep DualForge
  closed-source and commercially monetizable.
- Oodle DLLs must never be redistributed; DualForge locates them in the target
  game's binary directory (or via `DUALFORGE_OODLE` / search paths).
- Third-party attribution must appear in the application About dialog and this
  document before first public release.
