param(
    [string]$Source = ".\dist",
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\DualForge",
    [switch]$DesktopShortcut
)

# Installs the current DualForge build to a folder on the machine.
#   .\scripts\install.ps1                          install to LOCALAPPDATA\Programs
#   .\scripts\install.ps1 -DesktopShortcut         ...and put a shortcut on the desktop
#   .\scripts\install.ps1 -InstallDir "D:\Tools"   custom location
#
# Uninstall: just delete the install folder (and the shortcut).

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
if (-not [System.IO.Path]::IsPathRooted($Source)) {
    $Source = Join-Path $root $Source
}
$launcher = Join-Path $Source "DualForge.exe"
$internal = Join-Path $Source "_internal"

if (-not (Test-Path $launcher)) {
    Write-Host "ERROR: $launcher not found. Build first with .\scripts\build.ps1" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $internal)) {
    Write-Host "ERROR: $internal not found. DualForge.exe needs the _internal folder next to it." -ForegroundColor Red
    exit 1
}

Write-Host "Installing DualForge to $InstallDir ..."
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item $launcher $InstallDir -Force
Copy-Item $internal $InstallDir -Recurse -Force

$installed = Join-Path $InstallDir "DualForge.exe"
if (-not (Test-Path $installed)) {
    Write-Host "ERROR: install failed - $installed was not created." -ForegroundColor Red
    exit 1
}

if ($DesktopShortcut) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $link = Join-Path $desktop "DualForge.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($link)
    $shortcut.TargetPath = $installed
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.Description = "DualForge - Unity & Unreal asset extractor"
    $shortcut.Save()
    Write-Host "Shortcut created: $link"
}

Write-Host ""
Write-Host "Installed. Run it now:" -ForegroundColor Green
Write-Host "  $installed"
Write-Host ""
Write-Host "To uninstall, delete the folder '$InstallDir'$($(if ($DesktopShortcut) { ' and the desktop shortcut' } else { '' }))."
Write-Host "Keep the '_internal' folder next to DualForge.exe - it contains the runtime."
