# NGX DLSS screen indicator toggle (ShowDlssIndicator; admin required). ASCII only.
# Default = on (1024, plus EnableDevWatermark=0). -Off = restore (0).
# See docs/dlss_wedge_rootcause.md (section 1). Indicator needs a game restart.
# Usage: .\ngx_indicator.ps1 [-Off]
param([switch]$Off)
$ErrorActionPreference = 'Continue'
$tag = if ($Off) { 'OFF' } else { 'ON' }
$out = Join-Path $env:TEMP ('ngx_indicator_' + $tag.ToLower() + '_out.txt')
"step0: start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $out -Append -Encoding ascii

$key = 'HKLM:\SOFTWARE\NVIDIA Corporation\Global\NGXCore'
if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }

if ($Off) {
  Set-ItemProperty -Path $key -Name 'ShowDlssIndicator' -Value 0 -Type DWord
} else {
  Set-ItemProperty -Path $key -Name 'ShowDlssIndicator' -Value 1024 -Type DWord
  Set-ItemProperty -Path $key -Name 'EnableDevWatermark' -Value 0 -Type DWord
}

$v = (Get-ItemProperty -Path $key -Name 'ShowDlssIndicator' -ErrorAction SilentlyContinue).ShowDlssIndicator
"step1: ShowDlssIndicator=$v" | Out-File $out -Append -Encoding ascii

$want = if ($Off) { '0' } else { '1024' }
if ("$v" -eq $want) { "NGX_INDICATOR_$tag" | Out-File $out -Append -Encoding ascii }
else { 'NGX_INDICATOR_FAILED' | Out-File $out -Append -Encoding ascii }
