<#
Registers the results-only check (scripts\run_settle.ps1) in Windows Task Scheduler, for the current user.

    powershell -ExecutionPolicy Bypass -File scripts\install_results_schedule.ps1
    powershell -ExecutionPolicy Bypass -File scripts\install_results_schedule.ps1 -Python "C:\path\to\python.exe"
    powershell -ExecutionPolicy Bypass -File scripts\install_results_schedule.ps1 -Remove

One task, "MatchupDNA results", every two hours on the hour, except the forecasting job's own hours (07:00 and 19:00,
which settle results themselves): 09:00, 11:00, 13:00, 15:00, 17:00, 21:00, 23:00, 01:00, 03:00, 05:00. Each lands
35 minutes before a website publish. A missed check is not caught up (the next one is two hours later), so it never
starts at the same moment as a forecasting run catching up after the computer wakes. The forecasting and website
tasks are not touched.
#>
param(
    [string]$Python = (Get-Command python -ErrorAction Stop).Source,
    [string[]]$Times = @("09:00", "11:00", "13:00", "15:00", "17:00", "21:00", "23:00", "01:00", "03:00", "05:00"),
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
foreach ($t in $Times) {
    if ($t -in @("07:00", "19:00")) { throw "$t is a forecasting run; the results check must not share its hour" }
}

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`" -Python `"$Python`"" -WorkingDirectory $Repo
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$Triggers = $Times | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Triggers -Settings $Settings `
    -Description "Matchup DNA: attach finished results between forecasting runs; never forecasts ($Repo)" | Out-Null
Write-Output "Registered '$Name' at $($Times -join ', ') with $Python"
