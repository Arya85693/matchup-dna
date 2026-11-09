<#
Results-only check between the twice-daily forecasting runs: refreshes ESPN, then attaches finished results to stored
matches (python -m matchup_dna.forecasting settle). It never issues a forecast.

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_settle.ps1 [-Python C:\path\to\python.exe]

It must never overlap the forecasting job (both write the store and the ESPN archive), so it does nothing when:
- a forecasting job ("MatchupDNA daily ..." or any "matchup_dna.forecasting daily" process) is running;
- a forecasting run is overdue (the computer was off at 07:00 or 19:00 and the job is about to catch up);
- it is within 30 minutes of 07:00 or 19:00.
Output is appended to data\logs\settle.log (ignored by git).
#>
param([string]$Python = "python")

$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
New-Item -ItemType Directory -Force "data\logs" | Out-Null
$Log = Join-Path $Repo "data\logs\settle.log"
function Note($text) { Add-Content -Path $Log -Value "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $text" }

$now = Get-Date
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
Note "settle start"
& $Python -m matchup_dna.forecasting settle 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $Log   # plain text, like the other logs
$code = $LASTEXITCODE
Note "settle exit $code"
exit $code
