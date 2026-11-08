# Presentation only. Never imports or invokes reservation code; reads evidence only.
function Read-SummaryEvidence {
    param([string]$Directory, [string]$Name)
    $value = Get-Content -LiteralPath (Join-Path $Directory $Name) -Encoding UTF8 -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    if ($null -eq $value -or $value -isnot [pscustomobject]) { throw "INVALID_OBJECT: $Name" }
    return $value
}

function Get-FinalResultSummary {
    param([string]$EvidencePath, [int]$LauncherExitCode = 0)
    $ErrorActionPreference = 'Stop'
    if (Test-Path -LiteralPath (Join-Path $EvidencePath 'safe_quit_result.json')) {
        $projectRoot = Split-Path -Parent $PSScriptRoot
        $validator = Join-Path $projectRoot 'current\app\safe_quit.py'
        $python = 'C:\Users\Takashi\AppData\Local\Programs\Python\Python313\python.exe'
        $raw = & $python -B $validator --summary $EvidencePath
        if ($LASTEXITCODE -ne 0) { throw 'SAFE_QUIT_EVIDENCE_VALIDATION_FAILED' }
        $summary = ($raw -join [Environment]::NewLine) | ConvertFrom-Json -ErrorAction Stop
        if ($summary.Result -ne 'SAFE QUIT / NO HUMAN GO / NO SUBMIT') { throw 'SAFE_QUIT_SUMMARY_INVALID' }
        if ($LauncherExitCode -ne 0) { $summary.Result = 'ERROR / SAFE QUIT LAUNCHER FAILED' }
        return $summary
    }
    $data = Read-SummaryEvidence $EvidencePath 'results.json'
    $admission = Read-SummaryEvidence $EvidencePath 'admission.json'
    $finished = Read-SummaryEvidence $EvidencePath 'finished.json'
    $workers = @{}
    foreach ($worker in @('A', 'B')) {
        $workers[$worker] = Read-SummaryEvidence $EvidencePath "worker-$worker.json"
        if ($workers[$worker].status -notin @('COMPLETED', 'ABORT')) { throw 'INVALID_WORKER_STATUS' }
    }
    if ($finished.lifecycle -ne 'CONSUMED_NO_RESTART' -or [string]::IsNullOrWhiteSpace($finished.created)) { throw 'INVALID_FINISHED' }
    $month = $admission.binding.configuration.month
    if ($month -isnot [string] -or $month -notmatch '^\d{6}$') { throw 'INVALID_MONTH' }
    if ($data.results -isnot [array] -or $data.results.Count -eq 0) { throw 'INVALID_RESULTS' }
    $rows = @($data.results)
    $entries = @($admission.entries)
    if ($entries.Count -ne $rows.Count -or $admission.binding.configuration.active_count -ne $rows.Count) { throw 'INCOMPLETE_RESULTS' }
    if ($data.worker_exit_codes -isnot [array] -or $data.worker_exit_codes.Count -ne 2) { throw 'INVALID_WORKER_EXIT_CODES' }
    foreach ($code in $data.worker_exit_codes) {
        if ($code -isnot [int] -and $code -isnot [long]) { throw 'INVALID_WORKER_EXIT_CODE' }
    }
    $seen = @{}
    $counts = @{ CONFIRMED=0; ALREADY_RESERVED=0; FAILED_FINAL=0; Review=0; Submit=0 }
    $displayRows = @(foreach ($row in $rows) {
        if ($row.worker -notin @('A','B') -or $row.request -isnot [string] -or $row.request -notmatch ('^' + $row.worker + '[1-9][0-9]*$') -or $seen.ContainsKey($row.request)) { throw 'INVALID_REQUEST_ID' }
        $seen[$row.request] = $true
        $match = @($entries | Where-Object { $_.request_id -ceq $row.request -and $_.worker -ceq $row.worker -and $_.lesson -ceq $row.lesson })
        if ($match.Count -ne 1 -or $row.lesson -isnot [string] -or [string]::IsNullOrWhiteSpace($row.lesson)) { throw 'REQUEST_BINDING_MISMATCH' }
        if ($null -ne $match[0].start_time -and ($row.start_time -cne $match[0].start_time -or $row.date -cne $match[0].date)) { throw 'REQUEST_TIME_BINDING_MISMATCH' }
        if ($row.final_result -isnot [string] -or [string]::IsNullOrWhiteSpace($row.final_result)) { throw 'MISSING_FINAL_RESULT' }
        if (($row.attempts -isnot [int] -and $row.attempts -isnot [long]) -or $row.attempts -lt 0 -or $row.attempt_records -isnot [array] -or $row.attempts -ne $row.attempt_records.Count) { throw 'INVALID_ATTEMPTS' }
        $submit = 0
        foreach ($attempt in $row.attempt_records) {
            if ($attempt.submission_attempted -isnot [bool]) { throw 'MISSING_OR_INVALID_SUBMISSION_ATTEMPTED' }
            if ($attempt.submission_attempted) { $submit++ }
        }
        $review = $row.final_result -cnotin @('CONFIRMED','ALREADY_RESERVED','FAILED_FINAL')
        foreach ($flag in @('owner_action_required','position_owner_review_required','remaining_ambiguity')) {
            if ($row.$flag -isnot [bool]) { throw "MISSING_OR_INVALID_$flag" }
            if ($row.$flag) { $review = $true }
        }
        $reservedWithoutAmbiguity = $row.final_result -ceq 'ALREADY_RESERVED' -and $row.remaining_ambiguity -eq $false
        if (($row.position_result -eq 'UNKNOWN' -and -not $reservedWithoutAmbiguity) -or $null -ne $row.position_review) { $review = $true }
        if ($row.final_result -cin @('CONFIRMED','ALREADY_RESERVED','FAILED_FINAL')) { $counts[$row.final_result]++ }
        if ($review) { $counts.Review++ }
        $counts.Submit += $submit
        $position = '-'
        if ($null -ne $row.actual_position) {
            if (($row.actual_position -isnot [int] -and $row.actual_position -isnot [long]) -or $row.actual_position -lt 1) { throw 'INVALID_ACTUAL_POSITION' }
            $position = [string]$row.actual_position + '番'
        }
        [pscustomobject]@{ Worker=$row.worker; Request=$row.request; Date=$row.date; StartTime=$row.start_time; Lesson=($row.lesson -replace '[\r\n\x1b]', ' '); Result=$row.final_result; Position=$position; Attempts=$row.attempts; Submit=$submit; Review=$review }
    })
    # Current frozen schema defines no safety-violation count. Never infer zero
    # from a worker exit code, terminal result, or absence of an error message.
    $status = if ($counts.Review -gt 0) { 'REVIEW REQUIRED' } else { 'COMPLETED' }
    if ($LauncherExitCode -ne 0 -or @($data.worker_exit_codes | Where-Object { $_ -ne 0 }).Count -gt 0 -or @($workers.Values | Where-Object { $_.status -ne 'COMPLETED' }).Count -gt 0) { $status = 'ERROR / LAUNCHER OR WORKER FAILED' }
    [pscustomobject]@{ Month=$month; Total=$rows.Count; Rows=$displayRows; Counts=$counts; Safety='N/A（専用count fieldなし）'; Result=$status; EvidencePath=$EvidencePath }
}

function Show-FinalResultSummary {
    param([string]$EvidencePath, [int]$LauncherExitCode = 0)
    Write-Host ''
    Write-Host '============================================================'
    Write-Host ' Lesson Reservation 実行結果'
    Write-Host '============================================================'
    try {
        # Validate everything before printing any counts: no partial success report.
        $summary = Get-FinalResultSummary $EvidencePath $LauncherExitCode
        Write-Host ('対象月              : ' + $summary.Month)
        Write-Host ('処理件数            : ' + $summary.Total)
        foreach ($worker in @('A','B')) {
            Write-Host ''
            Write-Host ('Worker ' + $worker)
            foreach ($row in @($summary.Rows | Where-Object { $_.Worker -eq $worker } | Sort-Object Request)) {
                $review = if ($row.Review) { ' / Owner Review Required' } else { '' }
                Write-Host ('  {0} {1} : {2} / {3}{4}' -f $row.Request,$row.Lesson,$row.Result,$row.Position,$review)
                if ($row.StartTime) { Write-Host ('     {0} {1}' -f $row.Date,$row.StartTime) }
                Write-Host ('     attempts: {0} / Submit: {1}' -f $row.Attempts,$row.Submit)
            }
        }
        Write-Host '------------------------------------------------------------'
        Write-Host ('予約成功            : ' + $summary.Counts.CONFIRMED)
        Write-Host ('予約済み検出        : ' + $summary.Counts.ALREADY_RESERVED)
        Write-Host ('予約失敗            : ' + $summary.Counts.FAILED_FINAL)
        Write-Host ('要確認              : ' + $summary.Counts.Review)
        Write-Host ('Submit回数          : ' + $summary.Counts.Submit)
        Write-Host ('Safety集計          : ' + $summary.Safety)
        Write-Host ('RESULT              : ' + $summary.Result)
        $ok = -not $summary.Result.StartsWith('ERROR')
    } catch {
        Write-Host 'RESULT              : ERROR / EVIDENCE READ FAILED' -ForegroundColor Red
        Write-Host ('読取エラー          : ' + $_.Exception.Message)
        $ok = $false
    }
    Write-Host '============================================================'
    Write-Host ('Execution Evidence = ' + $EvidencePath)
    return $ok
}
