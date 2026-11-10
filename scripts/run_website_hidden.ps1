<#
Runs scripts\run_website.cmd for a scheduled task without a visible window. A visible console can be closed, or catch
a Ctrl+C typed for another app, which kills the step (seen on 9 November 2026). Its input is empty, so cmd's
"Terminate batch job (Y/N)?" prompt after an interruption ends the run instead of waiting forever.

    powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File scripts\run_website_hidden.ps1 -Python <python.exe> -Step publish
#>
param([string]$Python = "python", [ValidateSet("publish", "players")][string]$Step = "publish")

$Script = Join-Path $PSScriptRoot "run_website.cmd"
$null | & $Script $Python $Step          # empty input: a "Terminate batch job (Y/N)?" prompt cannot wait
exit $LASTEXITCODE
