# DualForge User Guide

**DualForge** is a desktop tool for browsing, previewing, and extracting game assets
from **Unity** and **Unreal** archives. This guide covers installing and using the
current build, step by step.

> The latest build always supersedes older instructions. When in doubt, follow the
> "Install the build" section below — especially the part about **which `.exe` is the
> real program** and what must stay next to it.

---

## 1. Install the current build (Windows)

The build output is a **portable folder** — there is no installer. It consists of two
things that must **stay together**:

| Item | What it is | Required? |
|---|---|---|
| `DualForge.exe` | The launcher / program | Yes |
| `_internal` | The runtime: Python, PySide6, all modules, plugins | Yes — never delete, never move alone |

### Step-by-step

1. Copy the **whole `dist` folder** (or at least `DualForge.exe` **and** the
   `_internal` folder next to it) to wherever you keep programs,
   e.g. `C:\Programs\DualForge\`.
2. Double-click `DualForge.exe`.
3. If Windows SmartScreen shows a warning: click **More info → Run anyway**
   (the build is unsigned; this is expected for a locally built program).

**Prefer a one-command install?** From the repo, run:

```powershell
.\scripts\install.ps1                # installs to %LOCALAPPDATA%\Programs\DualForge
.\scripts\install.ps1 -DesktopShortcut   # ...and adds a desktop shortcut
.\scripts\install.ps1 -InstallDir "D:\Tools"   # custom location
```

No admin rights are needed. **Uninstall** = delete the install folder (and the shortcut).

> **Common pitfall — "Failed to load Python DLL".** This error means you ran an exe
> that has no runtime next to it. The real program is `DualForge.exe` **with `_internal`
> in the same folder**. Never run:
> - `build\dualforge\DualForge.exe` (an internal PyInstaller intermediate — it is
>   deleted after each build on purpose), or
> - a bare `DualForge.exe` that was copied without its `_internal` folder.

### Optional: pin it to the taskbar / start menu

Right-click `DualForge.exe` → **Pin to taskbar** / **Pin to Start**. You can also
right-click → **Create shortcut** and put the shortcut anywhere.

---

## 2. Quick start (first 60 seconds)

1. Launch `DualForge.exe`.
2. Click **Open Archive...** (or press `Ctrl+O`) and pick a game archive:
   `.pak` (Unreal), `.utoc`/`.ucas` (Unreal IoStore), or Unity
   `.unity3d` / `.bundle` / `.assets` / `.assetbundle`.
   You can also **drag & drop** a file onto the window, or use **File ▸ Open Folder**
   to scan an entire game directory (recursive, up to 4 levels).
3. Browse the asset tree on the left. Use the **search box** (`Ctrl+F`) and the
   **type filter** to narrow down. Click any asset — a preview appears on the right
   (textures, sprites, audio with waveform playback, meshes in 3D, text/JSON/XML,
   hex for everything else).
4. **Extract**:
   - **File ▸ Extract All** (`Ctrl+Shift+E`) — extract everything in the archive.
   - **File ▸ Export Selected** (`Ctrl+E`) — first tick the checkboxes next to the
     assets you want, then export only those.
   - Both ask for an output folder. A progress bar appears in the status bar, with a
     **Cancel** button.
5. Done. A `_dualforge_manifest.json` is written into the output folder listing every
   extracted file, plus any warnings.

> **Tip:** check the **Log** dock at the bottom — it reports format detection,
> the AES key that unlocked an archive, and extraction warnings.

---

## 3. The interface

### Menu bar

| Menu | Item | What it does |
|---|---|---|
| File | Open Archive... (`Ctrl+O`) | Open a single archive |
| File | Open Folder... (`Ctrl+Shift+O`) | Scan a whole game folder (multi-archive mode) |
| File | Open Recent | Re-open previously opened archives |
| File | Export Selected / Extract All | Extract checked assets / everything |
| File | Manage AES Keys... | Add, remove, or sync decryption keys |
| File | Game Profiles... | Save a game (folder + key + output) and reopen it in one click |
| File | Settings... | Theme, paths, export formats, default key (see §6) |
| View | Asset Statistics... | Per-type file counts and sizes |
| View | Theme | Switch dark / light |
| Tools | **Ghidra Key Hunt...** | Find hardcoded AES keys in a game binary via headless Ghidra (see §5.4) |
| Help | About DualForge | Version and info |

### Toolbar

Open, Folder, Extract (all), Export Selected, Keys, and a **Donate** button that opens
the Ko-fi page (<https://ko-fi.com/b6000>) — the URL is editable in Settings.

### Docks

- **Assets** (left) — search + type filter + checkbox tree. Checkboxes drive
  *Export Selected*; "Check All / None" buttons affect only visible rows.
- **Properties** (bottom) — metadata of the selected asset (type, size, engine version…).
- **Log** (bottom) — detection results, key used, warnings.

All docks can be toggled under **View** and re-docked by dragging their title bars.

---

## 4. Previews

Selecting an asset loads a preview automatically (in a background thread):

| Asset type | Preview |
|---|---|
| Texture2D / Sprite | Image viewer — zoom (`+`/`-`), **Fit**, **1:1**, pan with the mouse |
| AudioClip (Unity) | Waveform + inline **Play/Stop** with a seek bar |
| `.wav` / `.ogg` / `.flac` and exotic Unreal audio (`.wem`, `.fsb`, …) | Same audio page — exotic formats need **vgmstream** (§6) |
| Mesh (Unity) | 3D viewer — **Wireframe** toggle, **Reset view**, drag to orbit |
| TextAsset | Pretty-printed JSON/XML/text viewer |
| Anything else | Hex inspector (first 256 KB shown) |

Previews are cached under `~/.dualforge/preview_cache` so revisiting an asset is fast.
Audio previews that fail to decode fall back gracefully with an error page.

---

## 5. Unlocking encrypted archives (AES keys)

DualForge **never ships keys**. It decrypts with keys you provide — manually, from an
FModel file, from community endpoints (opt-in), or by finding them yourself with
Ghidra. Keys are stored locally in plain text at `~/.dualforge/keys.json`.

### 5.1 Add a key manually

**File ▸ Manage AES Keys → Add...** — enter a title and a 64-hex-char AES-256 key.
Or paste your default key under **File ▸ Settings ▸ Default AES key**.

### 5.2 Import from FModel (`Global.AESKeys.json`)

**File ▸ Settings → Import AES Keys JSON...** — picks up main keys **and** per-chunk
dynamic keys (important for modern games).

### 5.3 Sync from community endpoints (opt-in, network)

**File ▸ Manage AES Keys → Sync from endpoints** pulls the latest keys from community
repositories (defaults: FortniteCentral, aes.ue4server.com — editable in Settings).

### 5.4 Automated Ghidra key hunt (find keys yourself)

If a key is not in any list and you own the game binary, DualForge can scan it for
AES S-box signatures and high-entropy 32-byte hex keys:

**From the GUI (recommended):** **Tools ▸ Ghidra Key Hunt...**

1. Click **Browse...** and pick the game `.exe` / `.dll`.
2. (Optional) tweak the entropy threshold and how many candidate keys to store.
3. Click **Check Setup** first — it verifies Ghidra, Java, and the bridge.
4. Click **Start Key Hunt** and watch the live log. This can take several minutes.
5. The best candidates are added to the key store automatically as
   `"<game> [ghidra-N]"` and are tried automatically the next time you open the pak.

**From the command line:**

```powershell
python scripts\ghidra\ghidra_key_finder.py "C:\Game\Game.exe"
python scripts\ghidra\ghidra_key_finder.py --check   # diagnostics
```

**Prerequisites:** Ghidra 11.x (set `GHIDRA_HOME` or add it to `PATH`) and **Java 21**.
`ghidra-bridge` is installed automatically on first run (source installs only — for
the frozen build, install it into the same Python environment used to build).

### 5.5 How unlocking works

Every pak is opened by auto-probing: **no key → every stored key → default key**.
The winning key is reported in the log. Toggle this off under
**Settings ▸ "Try every key from the key store before failing"** if you want only the
default key tried.

---

## 6. Settings reference (**File ▸ Settings**)

| Setting | Purpose |
|---|---|
| Theme | Dark / light |
| Default output folder | Pre-filled destination for extraction dialogs |
| CUE4Parse CLI (uex) | Path to the **uex** CLI — required for Unreal IoStore (`.utoc`/`.ucas`) and pak fallback. Download from [github.com/arkive-games/uex](https://github.com/arkive-games/uex) |
| vgmstream | Path to `vgmstream-cli` for exotic audio (`.wem`, `.fsb`, `.vag`, …) and FLAC export. Optional |
| Preview cache folder | Where previews are cached (default `~/.dualforge/preview_cache`) |
| Default AES key | Key tried for every archive (besides the key store) |
| Key probing | Try every stored key before failing |
| Key file (FModel) | Import `Global.AESKeys.json` |
| Sync endpoints | Comma-separated community key URLs |
| Donation URL | What the toolbar Donate button opens |
| Texture / Sprite / Audio / Mesh format | Export format per asset type (PNG/JPG/WebP/TGA, WAV/OGG/FLAC, OBJ/glTF…) |

### External tools at a glance

| Tool | Needed for | Where to configure |
|---|---|---|
| **uex** (CUE4Parse CLI) | `.utoc`/`.ucas` IoStore, pak fallback | Settings → CUE4Parse CLI, or env var `DUALFORGE_CUE4PARSE` |
| **vgmstream** | Exotic audio decode + FLAC export | Settings → vgmstream, or env var `DUALFORGE_VGMSTREAM` |
| **Oodle DLL** (`oo2core_*.dll`) | Oodle-compressed paks | Found automatically in the pak's folder chain, `Binaries/`, `~/.dualforge`, `PATH` — **never bundled or downloaded** |

---

## 7. Troubleshooting

| Symptom | Cause & fix |
|---|---|
| "Failed to load Python DLL" | You ran the wrong exe or split it from its runtime. Run `DualForge.exe` **with `_internal` in the same folder** (from `dist`), never `build\dualforge\DualForge.exe` |
| App closes instantly, nothing happens | Same as above, or a missing `_internal` folder |
| "CUE4Parse CLI not found" | IoStore/fallback needs **uex** — set its path in Settings |
| "Oodle DLL not found" | Oodle-compressed pak. Copy `oo2core_*.dll` from the game's `Binaries\Win64\` into the pak's folder, the working directory, or `~/.dualforge` |
| Archive won't open / encrypted | Add the AES key (File ▸ Manage AES Keys), import an FModel JSON, or run the Ghidra key hunt (Tools ▸ Ghidra Key Hunt) |
| Exotic audio has no sound | Install **vgmstream** and set it in Settings; without it only WAV/OGG/FLAC preview |
| 3D mesh viewer empty | OpenGL unavailable — the mesh page shows a message; mesh **export** still works |
| Ghidra hunt fails | Run **Check Setup** in the dialog; install Ghidra 11.x + Java 21 and set `GHIDRA_HOME` |
| Where did my files go? | The output folder you chose + `_dualforge_manifest.json` listing every file |
| Where are settings/keys stored? | `~/.dualforge/` — `settings.json`, `keys.json`, `preview_cache/` |

---

## 8. Build your own copy (from source)

Requires **Python 3.10+** and **Git**.

```powershell
git clone <this-repo> DualForge
cd DualForge
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .        # core
pip install -e ".[keys]"    # optional: community key sync
pip install -e ".[snappy]"  # optional: snappy codec
python main.py          # run from source
```

Run the test suite any time:

```powershell
python -m pytest tests -q
```

### Build the Windows exe

```powershell
.\.venv\Scripts\activate
.\scripts\build.ps1
```

The build lands in `dist\`. **Run `dist\DualForge.exe`** (keep `_internal` beside it).
The script deletes the confusing intermediate `build\dualforge\DualForge.exe` and
prints the exact file to run. Oodle DLLs and CLI helpers are never bundled — drop
`oo2core_*.dll` next to the exe (or into `~/.dualforge`) if a game needs it.

---

## 9. Command-line quick reference

```powershell
python main.py detect "game\Content\Paks\pakchunk0-Windows.pak"   # identify a file
python main.py extract "game_Data\sharedassets0.assets" -o out     # extract everything
python main.py extract "game_Data\sharedassets0.assets" -o out --format jpg
python main.py keys add "My Game" 0123...64hex...abc
python main.py keys list
python main.py keys import "C:\FModel\Output\Global.AESKeys.json"
python main.py keys sync
python main.py codecs
```
