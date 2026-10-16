# Builds the Windows game folder with PyInstaller, then the installer with Inno Setup.
# Run from the project root, with the project venv active (or edit $python below).

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

# 1. Game folder: temp\dist\StellarWanderer\StellarWanderer.exe (PyInstaller's work files go to temp\build)
& $python -m PyInstaller --noconfirm --clean --workpath temp\build --distpath temp\dist tools\StellarWanderer.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

# 2. Installer: release\StellarWanderer-Setup-<version>.exe (needs Inno Setup 6)
$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    & $iscc (Join-Path $root 'tools\installer.iss')
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed ($LASTEXITCODE)" }
    Write-Host "Installer written to $root\release"
} else {
    Write-Host "Inno Setup 6 not found: the game folder is ready in temp\dist\StellarWanderer (zip it to share)."
}
