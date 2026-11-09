<#
Results-only check between the twice-daily forecasting runs: refreshes ESPN, then attaches finished results to stored
matches (python -m matchup_dna.forecasting settle). It never issues a forecast.

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_settle.ps1 [-Python C:\path\to\python.exe] [-Watch]

-Watch (the scheduled mode, every 15 minutes) works only when it is worth it:
- a match has just become due (started between 45 minutes and 6 hours ago, no result yet, read from the latest local
  snapshot): checked at once;
- matches are still waiting: re-checked every 30 minutes;
- nothing waiting: every 2 hours (catches matches that ran very long or had no start time).
After a successful check it publishes and uploads at once (scripts\run_website.cmd publish), so a result reaches the
site minutes after ESPN reports it. Quiet periods make no requests and write nothing.

It must never overlap the forecasting job (both write the store and the ESPN archive), so it does nothing when:
- a forecasting job ("MatchupDNA daily ..." or any "matchup_dna.forecasting daily" process) is running;
- a forecasting run is overdue (the computer was off at 07:00 or 19:00 and the job is about to catch up);
- it is within 30 minutes of 07:00 or 19:00.
Output is appended to data\logs\settle.log (ignored by git).
#>
param([string]$Python = "python", [switch]$Watch)

$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$env:PYTHONUNBUFFERED = "1"
New-Item -ItemType Directory -Force "data\logs" | Out-Null
$Log = Join-Path $Repo "data\logs\settle.log"
$Last = Join-Path $Repo "data\logs\settle.last"
function Note($text) { Add-Content -Path $Log -Value "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $text" }

$now = Get-Date

if ($Watch) {
    # Is any result due? Started 45 min to 6 h ago, not settled, not cancelled or postponed.
    $due = @()
    try {
        $root = Join-Path $Repo "web\.data\snapshot\v1"
        $stamp = (Get-Content "$root\manifest.json" -Raw | ConvertFrom-Json).snapshot
        $index = Get-Content "$root\$stamp\matches\index.json" -Raw | ConvertFrom-Json
        $utc = $now.ToUniversalTime()
        $due = @($index.matches | Where-Object {
            -not $_.result -and $_.start -and $_.state -notin @("cancelled", "postponed") -and
            ([datetime]$_.start).ToUniversalTime() -le $utc.AddMinutes(-45) -and
            ([datetime]$_.start).ToUniversalTime() -ge $utc.AddHours(-6) })
    } catch { }
    # The last check: when, and which matches were waiting then (settle.last: time on line 1, match ids on line 2).
    $previous, $waited = $null, @()
    if (Test-Path $Last) {
        $lines = @(Get-Content $Last)
        try { $previous = [datetime]$lines[0].Trim() } catch { }
        if ($lines.Count -gt 1) { $waited = @($lines[1].Split(",") | Where-Object { $_ }) }
    }
    $minutes = if ($previous) { ($now - $previous).TotalMinutes } else { [double]::MaxValue }
    $newly = @($due | Where-Object { $_.uid -notin $waited })
    # A match that has just become due is checked now; matches still waiting are re-checked every 30 minutes (a check
    # can take minutes on a busy machine); with nothing waiting, every 2 hours.
    $go = ($newly.Count -gt 0) -or ($due.Count -gt 0 -and $minutes -ge 30) -or ($minutes -ge 120)
    if (-not $go) { exit 0 }                                         # nothing to do: no request, no log line
}

$reason = $null
$daily = Get-ScheduledTask -TaskName "MatchupDNA daily*" -ErrorAction SilentlyContinue
foreach ($task in $daily) {
    $info = $task | Get-ScheduledTaskInfo
    if ($task.State -eq "Running") { $reason = "the forecasting job '$($task.TaskName)' is running" }
    $at = [datetime]::Today.Add(([datetime]$task.Triggers[0].StartBoundary).TimeOfDay)
    if ($at -gt $now) { $at = $at.AddDays(-1) }                      # its most recent scheduled time
    # Overdue = it has run before but missed its latest time (Task Scheduler is about to catch it up). A task that has
    # never run (267011, e.g. registered after its time) has nothing pending.
    if ($info.LastTaskResult -ne 267011 -and $info.LastRunTime -lt $at) {
        $reason = "the forecasting run due at $($at.ToString('HH:mm')) has not run yet"
    }
    $gap = [math]::Abs(($now.TimeOfDay - $at.TimeOfDay).TotalMinutes)
    if ($gap -lt 30 -or $gap -gt 1410) { $reason = "too close to the $($at.ToString('HH:mm')) forecasting run" }
}
$busy = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "matchup_dna\.forecasting\s+(daily|forecast|settle)" }
if ($busy) { $reason = "another forecasting command is running (pid $($busy[0].ProcessId))" }

if ($reason) {
    Note "settle skipped: $reason"
    exit 0
}
$why = if ($Watch) { if ($due.Count) { "$($due.Count) result(s) due" } else { "two-hourly check" } } else { "manual" }
Note "settle start ($why)"
Set-Content -Path $Last -Value @($now.ToString("o"), (@($due | ForEach-Object { $_.uid }) -join ","))
& $Python -m matchup_dna.forecasting settle 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $Log   # plain text, like the other logs
$code = $LASTEXITCODE
Note "settle exit $code"
if ($Watch -and $code -eq 0) {
    & cmd.exe /c "`"$Repo\scripts\run_website.cmd`" `"$Python`" publish"     # publish and upload straight away
}
exit $code
