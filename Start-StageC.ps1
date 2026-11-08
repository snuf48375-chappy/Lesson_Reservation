param([switch]$Live,[switch]$ReadOnly)
$ErrorActionPreference = 'Stop'
$stageCPython = 'C:\Users\Takashi\AppData\Local\Programs\Python\Python313\python.exe'
$stageCEntry = Join-Path $PSScriptRoot 'launch.py'
if ($Live -and $ReadOnly) { throw 'CLA-1 conflicting run modes.' }
if ($ReadOnly) { & $stageCPython -B $stageCEntry --readonly }
elseif ($Live) { & $stageCPython -B $stageCEntry --live }
else { & $stageCPython -B $stageCEntry }
if ($LASTEXITCODE -ne 0) { throw 'CLA-1 failed closed. Do not clear a stale lock or retry an unresolved lifecycle.' }
