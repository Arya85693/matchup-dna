<#
Registers the Matchup DNA website refresh in Windows Task Scheduler, for the current user.

    powershell -ExecutionPolicy Bypass -File scripts\install_website_schedule.ps1
    powershell -ExecutionPolicy Bypass -File scripts\install_website_schedule.ps1 -Python "C:\path\to\python.exe"
    powershell -ExecutionPolicy Bypass -File scripts\install_website_schedule.ps1 -Remove

Two tasks, both running scripts\run_website.cmd:
- "MatchupDNA website publish": every two hours at 07:35, 09:35, ... 05:35, so one lands half an hour after each
  forecasting run (07:00 and 19:00) and match states ("upcoming", "awaiting result") stay current in between.
- "MatchupDNA website players": once a day at 07:50 (ratings, head-to-heads and photos change at most daily).
Both only read the forecast store and skip a run while a forecast is in progress, so they never hold up the
forecasting job; that job's own tasks ("MatchupDNA daily ...") are not touched. Output goes to data\logs\website.log.
#>
param(
    [string]$Python = (Get-Command python -ErrorAction Stop).Source,
    [string]$FirstPublish = "07:35",
    [int]$EveryHours = 2,
    [string]$PlayersAt = "07:50",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $Repo "scripts\run_website.cmd"

Get-ScheduledTask -TaskName "MatchupDNA website*" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false
if ($Remove) {
    Write-Output "Removed the Matchup DNA website tasks."
    return
}
if (-not (Test-Path $Python)) { throw "Python not found: $Python" }
if ($EveryHours -lt 1 -or 24 % $EveryHours -ne 0) { throw "-EveryHours must divide 24 (1, 2, 3, 4, 6, 8, 12 or 24)" }

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

$Start = [datetime]::ParseExact($FirstPublish, "HH:mm", $null)
$Times = 0..(24 / $EveryHours - 1) | ForEach-Object { $Start.AddHours($_ * $EveryHours).ToString("HH:mm") }
$Triggers = $Times | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
$Publish = New-ScheduledTaskAction -Execute $Script -Argument "`"$Python`" publish" -WorkingDirectory $Repo
Register-ScheduledTask -TaskName "MatchupDNA website publish" -Action $Publish -Trigger $Triggers -Settings $Settings `
    -Description "Matchup DNA: publish the website snapshot from the forecast store, read-only ($Repo)" | Out-Null
Write-Output "Registered 'MatchupDNA website publish' at $($Times -join ', ') with $Python"

$Players = New-ScheduledTaskAction -Execute $Script -Argument "`"$Python`" players" -WorkingDirectory $Repo
Register-ScheduledTask -TaskName "MatchupDNA website players" -Action $Players `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $PlayersAt) -Settings $Settings `
    -Description "Matchup DNA: export player ratings, head-to-heads and photos for the website ($Repo)" | Out-Null
Write-Output "Registered 'MatchupDNA website players' daily at $PlayersAt with $Python"
