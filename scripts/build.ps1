param(
    [string]$OutDir = ".\dist\DualForge"
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

# The canonical PyInstaller onedir output lives at dist\DualForge\ and contains
# DualForge.exe + the _internal runtime beside it. This is the runnable artifact.
$built = Join-Path $root "dist\DualForge"
if (-not (Test-Path (Join-Path $built "DualForge.exe")) -or -not (Test-Path (Join-Path $built "_internal"))) {
    Write-Host "ERROR: build output is incomplete (expected DualForge.exe + _internal in dist\DualForge)." -ForegroundColor Red
    exit 1
}

# Remove any leftover flattened copies at the dist root so there is exactly one
# authoritative layout (the onedir). A bare DualForge.exe without _internal is
# non-runnable and confuses users - drop it.
$bare = Join-Path $root "dist\DualForge.exe"
if (Test-Path $bare) { Remove-Item $bare -Force }
$flatInternal = Join-Path $root "dist\_internal"
if (Test-Path $flatInternal) { Remove-Item $flatInternal -Recurse -Force }

# -OutDir lets you relocate the runnable app folder. It is the directory that
# should contain DualForge.exe + _internal directly. By default it is the
# canonical onedir (dist\DualForge), which is left in place.
if (-not [System.IO.Path]::IsPathRooted($OutDir)) {
    $OutDir = Join-Path $root $OutDir
}
$canonical = (Resolve-Path $built).Path
$target = (Resolve-Path $OutDir -ErrorAction SilentlyContinue).Path
if (-not $target -or $target -ne $canonical) {
    if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
    Copy-Item -Path "$built\*" -Destination $OutDir -Recurse -Force
    $built = $OutDir
}

Write-Host ""
Write-Host "Build complete. Run the onedir app:"
Write-Host "  $built\DualForge.exe"
Write-Host "Keep DualForge.exe and the '_internal' folder together - both live in $built."
Write-Host "To install, run: .\scripts\install.ps1  (installs from $built)"
Write-Host ""
Write-Host "Oodle DLLs and CUE4Parse/vgmstream CLIs are never bundled -"
Write-Host "place oo2core_*.dll next to the exe (or in ~/.dualforge) as needed."