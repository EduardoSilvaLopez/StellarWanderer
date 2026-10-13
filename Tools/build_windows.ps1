# Builds the Windows game folder with PyInstaller, then the installer with Inno Setup.
# Run from the project root, with the project venv active (or edit $python below).

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

# 1. Game folder: dist\StellarWanderer\StellarWanderer.exe
& $python -m PyInstaller --noconfirm --clean StellarWanderer.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

# 2. Installer: installer\StellarWanderer-Setup-<version>.exe (needs Inno Setup 6)
$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    & $iscc (Join-Path $root 'installer.iss')
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed ($LASTEXITCODE)" }
    Write-Host "Installer written to $root\installer"
} else {
    Write-Host "Inno Setup 6 not found: the game folder is ready in dist\StellarWanderer (zip it to share)."
}
