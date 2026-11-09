@echo off
rem Runs the Matchup DNA daily forecasting job: refresh ESPN, forecast, settle, extend the ledger.
rem Usage: run_daily.cmd [path\to\python.exe]   (default: the first python on PATH)
rem Output is appended to data\logs\daily.log (ignored by git).
setlocal
cd /d "%~dp0.."
set "PYTHON=%~1"
if "%PYTHON%"=="" set "PYTHON=python"
if not exist "data\logs" mkdir "data\logs"
echo ===== %DATE% %TIME% start >> "data\logs\daily.log"
"%PYTHON%" -m matchup_dna.forecasting daily >> "data\logs\daily.log" 2>&1
set "CODE=%ERRORLEVEL%"
echo ===== %DATE% %TIME% exit %CODE% >> "data\logs\daily.log"
exit /b %CODE%
