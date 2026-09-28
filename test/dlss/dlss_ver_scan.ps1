# DLSS DLL / Streamline version scan (ASCII only)
# Usage: .\dlss_ver_scan.ps1 -Games 'D:\Games\Foo','E:\Bar' [-Out <file>]
param(
  [Parameter(Mandatory=$true)][string[]]$Games,
  [string]$Out = (Join-Path $env:TEMP 'dlss_ver_scan.txt')
)
Remove-Item -Path $Out -ErrorAction SilentlyContinue
foreach ($g in $Games) {
    Out-File -FilePath $Out -Append -Encoding ASCII -InputObject ('===== ' + $g + ' =====')
    $files = Get-ChildItem -Path $g -Recurse -Include 'nvngx*.dll','sl.*.dll','nvofapi*.dll' -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        $v = $f.VersionInfo
        $rel = $f.FullName.Substring($g.Length + 1)
        Out-File -FilePath $Out -Append -Encoding ASCII -InputObject ($rel + '  |  FileVersion=' + $v.FileVersion + '  |  Product=' + $v.ProductName)
    }
}
Out-File -FilePath $Out -Append -Encoding ASCII -InputObject 'DLSS_SCAN_DONE'
Write-Host ('written: ' + $Out)
