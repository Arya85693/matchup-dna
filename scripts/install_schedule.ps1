<#
Registers the Matchup DNA daily forecasting job in Windows Task Scheduler, twice a day, for the current user.

    powershell -ExecutionPolicy Bypass -File scripts\install_schedule.ps1
    powershell -ExecutionPolicy Bypass -File scripts\install_schedule.ps1 -Python "C:\path\to\python.exe" -Times 07:00,19:00
    powershell -ExecutionPolicy Bypass -File scripts\install_schedule.ps1 -Remove

Each task runs scripts\run_daily.cmd with the given Python (default: the python first on PATH when this script runs),
so the job always uses the interpreter whose numpy the frozen models were checked with. A run missed because the
computer was off starts as soon as it is on again; a missed run means missed forecasts, never wrong ones (a forecast
is only issued at least 30 minutes before a match starts). Output goes to data\logs\daily.log.
#>
param(
    [string]$Python = (Get-Command python -ErrorAction Stop).Source,
    [string[]]$Times = @("07:00", "19:00"),
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $Repo "scripts\run_daily.cmd"
$Names = $Times | ForEach-Object { "MatchupDNA daily $($_.Replace(':', ''))" }

Get-ScheduledTask -TaskName "MatchupDNA daily*" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false
if ($Remove) {
    Write-Output "Removed the Matchup DNA scheduled tasks."
    return
}
if (-not (Test-Path $Python)) { throw "Python not found: $Python" }

$Action = New-ScheduledTaskAction -Execute $Script -Argument "`"$Python`"" -WorkingDirectory $Repo
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
for ($i = 0; $i -lt $Times.Count; $i++) {
    $Trigger = New-ScheduledTaskTrigger -Daily -At $Times[$i]
    Register-ScheduledTask -TaskName $Names[$i] -Action $Action -Trigger $Trigger -Settings $Settings `
        -Description "Matchup DNA: refresh ESPN, forecast, settle, extend the ledger ($Repo)" | Out-Null
    Write-Output "Registered '$($Names[$i])' daily at $($Times[$i]) with $Python"
}
