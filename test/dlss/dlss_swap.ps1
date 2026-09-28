# Swap a game's nvngx_dlss.dll with a source DLL (backup + md5 verify).
# For DLSS model-family A/B experiments (see docs/dlss_wedge_rootcause.md).
# Usage: .\dlss_swap.ps1 -GameDll "<game>\nvngx_dlss.dll" -Source "<new>\nvngx_dlss.dll"
param(
  [Parameter(Mandatory=$true)][string]$GameDll,
  [Parameter(Mandatory=$true)][string]$Source,
  [string]$BackupSuffix = '.bak'
)
$ErrorActionPreference = 'Continue'

# step0: refuse while the game is running (file would be locked / swap pointless)
$dir = Split-Path $GameDll
$running = Get-Process | Where-Object { $p = $null; try { $p = $_.Path } catch {}; ($p -and $p.StartsWith($dir, [StringComparison]::OrdinalIgnoreCase)) }
if ($running) {
  Write-Host 'BLOCKED: game processes still running:'
  $running | ForEach-Object { Write-Host ('  ' + $_.Name) }
  exit 1
}

if (-not (Test-Path $GameDll)) { Write-Host 'FAIL: game dll not found'; exit 1 }
if (-not (Test-Path $Source))  { Write-Host 'FAIL: source dll not found'; exit 1 }

# step1: one-time backup of the original
$bak = "$GameDll$BackupSuffix"
if (-not (Test-Path $bak)) {
  Copy-Item $GameDll $bak
  Write-Host ('backup created: ' + $bak)
} else {
  Write-Host 'backup already exists (kept)'
}

# step2: swap + verify
Copy-Item $Source $GameDll -Force
$md5s = (Get-FileHash $Source -Algorithm MD5).Hash
$md5d = (Get-FileHash $GameDll -Algorithm MD5).Hash
Write-Host ('source  md5 = ' + $md5s)
Write-Host ('inplace md5 = ' + $md5d + '  FileVersion=' + (Get-Item $GameDll).VersionInfo.FileVersion)
if ($md5s -eq $md5d) { Write-Host 'SWAP_OK' } else { Write-Host 'SWAP_FAILED' }

# NOTE: some launchers re-verify game files at every launch and will restore the
# original DLL (and clear the read-only attribute if set). Always re-check the
# in-place FileVersion before counting a session as a swapped sample.
