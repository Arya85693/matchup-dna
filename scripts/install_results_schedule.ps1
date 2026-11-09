<#
Registers the results watcher (scripts\run_settle.ps1 -Watch) in Windows Task Scheduler, for the current user.

    powershell -ExecutionPolicy Bypass -File scripts\install_results_schedule.ps1
    powershell -ExecutionPolicy Bypass -File scripts\install_results_schedule.ps1 -Python "C:\path\to\python.exe"
    powershell -ExecutionPolicy Bypass -File scripts\install_results_schedule.ps1 -EveryMinutes 20
    powershell -ExecutionPolicy Bypass -File scripts\install_results_schedule.ps1 -Remove

One task, "MatchupDNA results", every 15 minutes (at :10, :25, :40, :55). Each run does nothing unless a match is
waiting for its result or two hours have passed since the last check; then it settles results and publishes and
uploads at once (see run_settle.ps1). It never runs within 30 minutes of the 07:00 and 19:00 forecasting runs, which
settle results themselves. A missed run is not caught up (the next one is minutes away). The forecasting and website
tasks are not touched.
#>
param(
    [string]$Python = (Get-Command python -ErrorAction Stop).Source,
    [int]$EveryMinutes = 15,
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $Repo "scripts\run_settle.ps1"
$Name = "MatchupDNA results"

Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false
if ($Remove) {
    Write-Output "Removed '$Name'."
    return
}
if (-not (Test-Path $Python)) { throw "Python not found: $Python" }
if ($EveryMinutes -lt 10) { throw "-EveryMinutes must be at least 10" }

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`" -Python `"$Python`" -Watch" -WorkingDirectory $Repo
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$Trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddMinutes(10)) `
    -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "Matchup DNA: when a match is waiting for its result, settle results and publish; never forecasts ($Repo)" | Out-Null
Write-Output "Registered '$Name' every $EveryMinutes minutes with $Python"
