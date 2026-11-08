# Operational support only. The fixed candidate owns all reservation decisions.
$ErrorActionPreference = 'Stop'
$projectRoot = 'C:\Users\Takashi\OneDrive\Desktop\Lesson_Reservation'
$app = Join-Path $projectRoot 'current\app'
$entry = Join-Path $app 'Start-StageC.ps1'
$state = Join-Path $projectRoot 'runtime\reservation_journal\schema-v2\cla1-request-local-v1'
$exitCode = 1
$liveStarted = $false
$before = @()
try {
    Set-Location -LiteralPath $app
    if (-not (Test-Path -LiteralPath $entry -PathType Leaf)) { throw 'OFFICIAL_ENTRY_NOT_FOUND' }
    Write-Host ('Working directory: ' + (Get-Location).Path)
    Write-Host 'LOCAL PREFLIGHT: starting official entry (no Live argument).'
    & $entry
    if ($LASTEXITCODE -ne 0) { throw ('LOCAL_PREFLIGHT_EXIT_' + $LASTEXITCODE) }
    Write-Host 'LOCAL PREFLIGHT: PASS. Starting existing CLA-1 Live.'
    $before = @(Get-ChildItem -LiteralPath $state -Directory | Select-Object -ExpandProperty FullName)
    Write-Host 'Login / Identity: waiting for runtime verification and Worker A/B READY.'
    Write-Host 'Human GO remains required at the runtime prompt. A double-click is not Human GO.'
    $liveStarted = $true
    & $entry -Live
    if ($LASTEXITCODE -ne 0) { throw ('LIVE_EXIT_' + $LASTEXITCODE) }
    Write-Host 'Runtime returned exit code 0. Review the recorded results below for each reservation outcome.'
    $exitCode = 0
} catch {
    Write-Host ('STOP: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Do not clear locks, edit journals, or retry an unresolved session.'
} finally {
    if ($liveStarted) {
        try {
            $created = @(Get-ChildItem -LiteralPath $state -Directory | Where-Object { $_.FullName -notin $before })
            if ($created.Count -eq 1) {
                . (Join-Path $PSScriptRoot 'Final-ResultSummary.ps1')
                if (-not (Show-FinalResultSummary -EvidencePath $created[0].FullName -LauncherExitCode $exitCode)) { $exitCode = 1 }
            } else {
                Write-Host ('STOP: cannot identify exactly one new session; inspect evidence in ' + $state)
                Write-Host 'RESULT : ERROR / EVIDENCE READ FAILED'
                Write-Host ('Execution Evidence = unresolved; search root: ' + $state)
                $exitCode = 1
            }
        } catch {
            Write-Host ('STOP: result display failed: ' + $_.Exception.Message) -ForegroundColor Red
            Write-Host 'RESULT : ERROR / EVIDENCE READ FAILED'
            Write-Host ('Execution Evidence = search root: ' + $state)
            $exitCode = 1
        }
    } else {
        Write-Host 'RESULT : ERROR / LAUNCHER FAILED BEFORE EXECUTION'
        Write-Host 'Execution Evidence = unavailable (execution not started)'
    }
}
exit $exitCode
