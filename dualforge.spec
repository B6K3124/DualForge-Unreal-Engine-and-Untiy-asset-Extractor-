# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for DualForge.

Build with:
    pyinstaller dualforge.spec --noconfirm --clean
or via scripts/build.ps1
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = [
    "PIL._tkinter_finder",
]
hiddenimports += collect_submodules("dualforge")
hiddenimports += collect_submodules("UnityPy")
hiddenimports += collect_submodules("pyuepak")
hiddenimports += collect_submodules("py7zr")
hiddenimports += ["requests"]

# The Ghidra key-hunt scripts are loaded by path (never imported), so bundle
# them as data so the Tools > Ghidra Key Hunt UI works in frozen builds.
datas = collect_data_files("dualforge")
datas += [
    ("scripts/ghidra/ghidra_key_finder.py", "dualforge/ghidra"),
    ("scripts/ghidra/ghidra_key_finder_server.py", "dualforge/ghidra"),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DualForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DualForge",
)