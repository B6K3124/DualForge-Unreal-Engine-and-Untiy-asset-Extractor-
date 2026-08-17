param(
    [string]$OutDir = ".\dist"
)

$ErrorActionPreference = "Stop"

# Builds a standalone Windows build of DualForge with PyInstaller.
# Usage:  .\scripts\build.ps1  [-OutDir .\dist]

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "Installing PyInstaller..."
    python -m pip install pyinstaller
}

python -m pip install -e .

# Policy guard: pyuepak's Oodle DLL must never be bundled or downloaded.
# 1) Remove any stray oo2core_*.dll that a direct import left in site-packages.
# 2) Swap pyuepak's oodle.py for our stub during Analysis: PyInstaller's module
#    graph ignores sys.modules and executes the real oodle.py, which downloads
#    the DLL at import time. The stub is restored afterwards.
$pyuepakDir = python -c "import importlib.util; print(importlib.util.find_spec('pyuepak').submodule_search_locations[0])"
Get-ChildItem -Path $pyuepakDir -Filter "oo2core*" -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "Removing stray Oodle DLL from pyuepak package: $($_.Name)"
        Remove-Item $_.FullName -Force
    }

$oodleFile = Join-Path $pyuepakDir "oodle.py"
$oodleBak = "$oodleFile.dualforgebak"
if (Test-Path $oodleFile) {
    Copy-Item $oodleFile $oodleBak -Force
    Copy-Item (Join-Path $root "scripts\pyuepak_oodle_stub.py") $oodleFile -Force
    Write-Host "Swapped pyuepak oodle.py for the stub during analysis..."
}

try {
    Write-Host "Building DualForge..."
    python -m PyInstaller dualforge.spec --noconfirm --clean
} finally {
    if (Test-Path $oodleBak) {
        Copy-Item $oodleBak $oodleFile -Force
        Remove-Item $oodleBak -Force
        Write-Host "Restored original pyuepak oodle.py"
    }
}

# Remove any Oodle DLL the analysis could have re-created, and verify the build
# output contains none.
Get-ChildItem -Path $pyuepakDir -Filter "oo2core*" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

# Policy guard: verify the build output contains no Oodle DLL.
$bundled = Get-ChildItem -Path "dist\DualForge" -Recurse -Filter "oo2core*" -ErrorAction SilentlyContinue
if ($bundled) {
    Write-Host "ERROR: Oodle DLL was bundled into the build - aborting." -ForegroundColor Red
    exit 1
}

$target = Join-Path $root $OutDir
if ((Resolve-Path $target).Path -ne (Resolve-Path (Join-Path $root "dist\DualForge")).Path) {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Copy-Item -Path "dist\DualForge\*" -Destination $target -Recurse -Force
}

# Remove the non-runnable intermediate bootloader (bare exe with no python313.dll
# or _internal folder beside it) so users cannot launch it by mistake.
$intermediate = Join-Path $root "build\dualforge\DualForge.exe"
if (Test-Path $intermediate) {
    Remove-Item $intermediate -Force
}

$runnable = Join-Path $root "dist\DualForge.exe"
Write-Host ""
Write-Host "Build complete. Run this file (the one in dist\, NOT build\):"
Write-Host "  $runnable"
Write-Host "Note: keep '_internal' in the same folder as DualForge.exe."
Write-Host "Note: Oodle DLLs and CUE4Parse/vgmstream CLIs are never bundled -"
Write-Host "place oo2core_*.dll next to the exe (or in ~/.dualforge) as needed."