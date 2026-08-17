# DualForge

**Unity & Unreal game asset extractor** — a modern, professional desktop tool for browsing, previewing, and extracting game assets from both major engines.

> DualForge is a proprietary tool. It performs *decryption* (AES keys supplied by the user or fetched from community key repositories) and *decompression* (Oodle, Zstd, LZ4, etc.) purely in-memory — it never patches, modifies, or redistributes game files or third-party DLLs.

![engine](https://img.shields.io/badge/engine-Unity%20%2F%20Unreal-orange) ![ui](https://img.shields.io/badge/ui-PySide6-blue) ![python](https://img.shields.io/badge/python-3.10%2B-informational) ![license](https://img.shields.io/badge/license-Proprietary-critical)

> **New to DualForge?** Read the **[User Guide](docs/USER_GUIDE.md)** — install,
> first steps, interface reference, keys, and troubleshooting, step by step.

---

## Features

- **Automatic format detection** — scans magic bytes to identify `.pak`, `.utoc`/`.ucas` (Unreal) and `UnityFS`/`UnityWeb`/`UnityRaw` bundles and serialized files (`.assets`, `level0`, `globalgamemanagers`) (Unity); no manual configuration.
- **Native Unreal `.pak` support** — reads pak indices directly with `pyuepak` (zero external tools). Oodle-compressed archives use the game-shipped `oo2core_*.dll`, discovered automatically in the pak's own folder chain (`Binaries/Win64`, `Engine/Binaries`, ...), then `~/.dualforge`/PATH; the DLL is never bundled or downloaded. IoStore (`.utoc`/`.ucas`) and parser edge cases fall back to the CUE4Parse CLI.
- **Universal decompression core** — one unified `decompress()` API over zlib, gzip, bz2, lzma, LZ4/LZ4HC, Zstandard, Brotli, snappy, zip and 7z, with automatic magic sniffing and nested-container recursion.
- **Oodle support** — loads the game-shipped `oo2core_*.dll` via ctypes (`OodleLZ_Decompress`). The DLL is never bundled with DualForge.
- **AES decryption & unlocking** — every encrypted archive is opened by **auto-probing all stored keys** (no-key first, then every entry in the key store, then the default key), with the winning key reported in the log. Keys come from manual entry, FModel `Global.AESKeys.json` import, or opt-in community endpoint sync (FortniteCentral + multi-game `aes.ue4server.com`, configurable). UE 5.4+ paks that use per-chunk dynamic keys are detected and routed to the CLI with a clear hint.
- **Unity streamed data (.resS)** — sibling `.resS`/`.resource`/`.split*` stream files next to a bundle are loaded automatically, so streamed textures, audio and mesh data decode without manual file juggling.
- **Hierarchical asset browser** — folder tree with per-asset checkboxes, regex + type filters, "Check All / None", and multi-archive **Open Folder** mode (scan a whole game directory).
- **Asset previews** — texture/sprite image viewer (zoom/pan), audio clip waveform with inline playback (QtMultimedia), 3D mesh viewer (OpenGL wireframe + solid), text/JSON/XML viewer, and a full hex inspector. Unreal files preview natively from the pak (images, WAV/OGG/FLAC, `.wem`-style audio via vgmstream, text, hex).
- **Format-aware export** — per-type output formats (textures: PNG/JPG/BMP/WebP/TGA, audio: WAV/OGG/FLAC/raw, meshes: OBJ/glTF with embedded buffers) configurable in Settings or via the CLI; every run writes a `_dualforge_manifest.json`.
- **Game profiles** — save a game folder + AES key + output folder and reopen it in one click; the bound key is shown on each profile row.
- **Asset statistics** — per-type file counts and sizes in a summary dialog.
- **Polished PySide6 GUI** — dark & light themes, docked workspace (assets / properties / log), live search, drag-and-drop, recent files, per-file extraction progress with cancel, configurable Donate button, and a splash screen.
- **CLI** — headless `detect`, `extract`, `keys`, and `codecs` commands.

## Support the project

DualForge is free and open to use. If it saved you time (or an entire weekend), a
coffee is hugely appreciated:

[![ko-fi](https://img.shields.io/badge/Support%20me%20on-Ko--fi-ff5f5f)](https://ko-fi.com/b6000)

- **Ko-fi:** <https://ko-fi.com/b6000>
- The in-app **Donate** button (toolbar) opens the same page.

## Installation

### Option A — run the current Windows build (recommended for end users)

The build is a portable folder, **no installer needed**:

1. Copy the **entire `dist` folder** where you keep programs (e.g. `C:\Programs\DualForge\`).
   `DualForge.exe` **and** the `_internal` folder next to it must stay together —
   `_internal` contains the Python runtime and all modules.
2. Double-click `DualForge.exe` (if SmartScreen warns, choose **More info → Run anyway** —
   the build is unsigned).

Or install it with the one-command script (no admin rights needed):

```powershell
.\scripts\install.ps1                # installs to %LOCALAPPDATA%\Programs\DualForge
.\scripts\install.ps1 -DesktopShortcut   # ...and adds a desktop shortcut
.\scripts\install.ps1 -InstallDir "D:\Tools"   # custom location
```

Uninstall = delete the install folder (and the shortcut).

> **Run `dist\DualForge.exe` — never `build\dualforge\DualForge.exe`.** That one is an
> internal PyInstaller intermediate (a bare bootloader with no runtime beside it) and
> fails with *"Failed to load Python DLL"*. The build script deletes it automatically.

A full step-by-step (pinning to taskbar, first-run walkthrough, troubleshooting) is in
the [User Guide](docs/USER_GUIDE.md).

### Option B — run from source (developers)

```powershell
git clone <this-repo> DualForge
cd DualForge
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
python main.py
```

Optional extras:

```powershell
pip install -e ".[keys]"    # community key-endpoint sync (requests)
pip install -e ".[snappy]"  # snappy codec support
```

### External tools

| Tool | Needed for | Setup |
|---|---|---|
| **CUE4Parse-based CLI** | Unreal IoStore (`.utoc`/`.ucas`) & pak fallback | Point *Settings* or `DUALFORGE_CUE4PARSE` at a CLI built on CUE4Parse. The original `CUE4ParseCLI` is archived; the maintained successor is [**uex**](https://github.com/arkive-games/uex) (Apache-2.0, `.NET 10`, FModel-compatible). Note: the PyPI package `cue4parse` is currently broken and should **not** be installed. |
| **vgmstream** | Exotic audio format conversion (`.wem`, `.fsb`, ...) and FLAC export | Optional; set path in *Settings* or `DUALFORGE_VGMSTREAM` |
| **Oodle DLL** | Oodle-compressed Unreal packs | Discovered automatically: the pak's own folder chain (`Binaries/Win64`, `Engine/Binaries/Win64`, ...), then the working directory, `~/.dualforge`, and `PATH`. Never bundled or downloaded |

## Usage

### GUI

```powershell
python main.py          # from source
dist\DualForge.exe      # from the current build
```

Open an archive (or drag-and-drop it), click an asset to preview it, then **Extract All** to a folder or **Export Selected** for just the checked assets. Use **File ▸ Open Folder** to scan a whole game directory, **File ▸ Game Profiles** to reopen games in one click, **View ▸ Asset Statistics** for per-type summaries, **File ▸ Manage AES Keys** to add decryption keys, **Tools ▸ Ghidra Key Hunt** to find keys in a game binary with headless Ghidra, and **View ▸ Theme** to switch dark/light. Export formats are configured under **File ▸ Settings**.

### Unlocking encrypted archives

DualForge never ships or downloads keys or Oodle DLLs — it uses what you (or the game) provide:

1. **Add keys** — *File ▸ Manage AES Keys* (manual entry), *File ▸ Settings ▸ "Import AES Keys JSON..."* (FModel `Global.AESKeys.json`, incl. per-chunk dynamic keys), or CLI (`keys add` / `keys import`). Keys are stored locally in `~/.dualforge/keys.json`.
2. **Sync keys** (optional) — *File ▸ Manage AES Keys ▸ Sync from endpoints* pulls keys from community repositories (defaults: FortniteCentral and the multi-game `aes.ue4server.com`; editable in Settings). This is opt-in network access.
3. **Open the pak** — encrypted archives are opened by auto-probing every stored key (no-key → key store → default key). The log reports which key unlocked the archive. Toggle probing off via *Settings ▸ "Try every key from the key store before failing"* if you prefer only the default key.
4. **Oodle paks** — the game-shipped `oo2core_*.dll` is found automatically next to the pak (its folder chain and `Binaries/`/`Engine/` subpaths), so no manual copying is normally needed. The error message lists every location searched if it is missing.
5. **UE 5.4+ per-chunk encryption** — paks encrypted with per-chunk dynamic keys cannot be read natively (single-key only). DualForge detects these, tries the CLI fallback, and points you to FModel if the dynamic keys are needed.
6. **Automated key hunting (Ghidra)** — if a game's key is not in any community list and you have the game binary, DualForge can find it for you: it launches headless Ghidra, scans the binary's memory for crypto constants (AES S-box) and high-entropy hex keys, and adds the best 32-byte candidates straight into the key store. From the GUI use **Tools ▸ Ghidra Key Hunt...** (check the setup first, then start the hunt — live log + results table), or from a terminal:

   ```powershell
   python scripts\ghidra\ghidra_key_finder.py "C:\Game\Game.exe"
   # prerequisites: local Ghidra 11.x (GHIDRA_HOME or PATH) and Java 21;
   # `ghidra-bridge` is installed automatically on first run.
   # diagnostics: python scripts\ghidra\ghidra_key_finder.py --check
   ```

   The scan streams memory blocks in 4 MiB chunks over the bridge (base64), reports every hit with its address and candidate keys (`<binary>.keys.json`), and writes the top candidates into `~/.dualforge/keys.json` as `"<binary> [ghidra-N]"` — the pak auto-probe then tries them automatically. Only 32-byte candidates are stored (16-byte keys would break probing). Analysis runs with `-deleteProject` in a temp dir; nothing is left behind.

### CLI

```powershell
# Identify a file
python main.py detect "game\Content\Paks\pakchunk0-Windows.pak"

# Extract a Unity bundle to ./out
python main.py extract "game_Data\sharedassets0.assets" -o out

# Extract with a per-type format (textures as JPG, meshes as glTF, ...)
python main.py extract "game_Data\sharedassets0.assets" -o out --format jpg

# Store / list AES keys
python main.py keys add "Fortnite" 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
python main.py keys list

# Import an FModel Global.AESKeys.json key file
python main.py keys import "C:\FModel\Output\Global.AESKeys.json"

# Opt-in sync from community key endpoints
python main.py keys sync

# Show available codecs
python main.py codecs
```

### Building a standalone exe

```powershell
.\.venv\Scripts\activate
.\scripts\build.ps1
```

Builds with PyInstaller (`dualforge.spec`) and lands in `dist\`. **Run `dist\DualForge.exe`**
— keep the `_internal` folder beside it. The script removes the non-runnable
`build\dualforge\DualForge.exe` intermediate (running it yields *"Failed to load
Python DLL"*) and prints the exact file to run. Oodle DLLs and CLI helpers are never
bundled — drop `oo2core_*.dll` next to the exe or into `~/.dualforge` if a game needs it.

## Architecture

```
                 [ PySide6 GUI / CLI ]          main.py, dualforge/ui, dualforge/cli
                           │
                           ▼
                 [ Engine Router / Detector ]   dualforge/detector  (magic bytes)
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
            [ Unity Module ]    [ Unreal Module ]   dualforge/unity, dualforge/unreal
                 │                   │
                 └─────────┬─────────┘
                           ▼
            [ Decompression Core ]                dualforge/compression (Oodle, Zstd, LZ4, ...)
                           │
                           ▼
              [ Export / Audio / Preview ]        dualforge/export, dualforge/audio, dualforge/ui/preview
```

## Supported formats

- **Archives**: Unreal `.pak` (native, any version) and IoStore `.utoc`/`.ucas` (via CUE4Parse CLI), Unity asset bundles (`.unity3d`, `.bundle`, `.assets`) with `.resS` sibling stream files, plus nested zip / 7z / gzip / zstd / lz4 / lzma containers.
- **Compression**: None, zlib, gzip, bz2, lzma, LZ4, LZ4HC, Zstandard, Brotli, snappy, Oodle (Kraken/Mermaid/Leviathan), LZ4 frame, 7z.
- **Assets**: Texture2D/Sprite → PNG/JPG/BMP/WebP/TGA, AudioClip → WAV/OGG/FLAC/raw, Mesh → OBJ/glTF (+3D preview), TextAsset, Shader/Material/MonoBehaviour → raw, plus hex for everything else. Unreal previews auto-detect images, audio, and text inside paks.
- Full reference: [`docs/COMPRESSION.md`](docs/COMPRESSION.md), [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).

## Project layout

```
main.py                    Entry point (GUI + CLI routing)
dualforge/
  detector/                Format detection by magic bytes
  compression/             Universal decompression core + Oodle ctypes loader
  unity/                   UnityPy wrapper (list / extract / preview)
  unreal/                  Native pak reader (pyuepak) + CUE4ParseCLI bridge + AES key store
  audio/                   vgmstream bridge
  export/                  Sanitized output writer + format conversion (glTF, textures)
  ui/                      PySide6 GUI: themes, widgets, previews, dialogs, tree, profiles, stats
cli.py                     Headless commands
dualforge.spec             PyInstaller packaging
scripts/build.ps1          Windows build script
docs/                      User guide, design, format reference, license ledger
tests/                     pytest suite
```

## Legal & licensing

- DualForge is **proprietary software**. See [`docs/LICENSES.md`](docs/LICENSES.md) for the full third-party license ledger.
- GPLv3 Oodle wrappers are intentionally **not** used, to keep DualForge free to monetize.
- You are responsible for the files you decrypt/extract and for obtaining the rights to them.
