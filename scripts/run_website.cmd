@echo off
rem Refreshes the website's data from the forecast store (read-only): "publish" writes the match, forecast and archive
rem snapshot; "players" writes the player ratings, head-to-heads and photos. Each is then uploaded to the hosted copy
rem the live site reads (web\scripts\upload-snapshot.mjs), once web\.env.upload holds the storage keys; until then the
rem upload step only notes that hosting is not configured.
rem Usage: run_website.cmd [path\to\python.exe] [publish^|players]   (defaults: the first python on PATH, publish)
rem Output is appended to data\logs\website.log (ignored by git). Never touches the forecasting job or its store.
setlocal
cd /d "%~dp0.."
set "PYTHON=%~1"
if "%PYTHON%"=="" set "PYTHON=python"
set "STEP=%~2"
if "%STEP%"=="" set "STEP=publish"
set "AREA="
if /i "%STEP%"=="publish" set "AREA=snapshot"
if /i "%STEP%"=="players" set "AREA=history"
if not defined AREA (
    echo unknown step "%STEP%": use publish or players
    exit /b 2
)
rem Unbuffered, so the log shows how far a step got even if it is stopped.
set "PYTHONUNBUFFERED=1"
if not exist "data\logs" mkdir "data\logs"
echo ===== %DATE% %TIME% %STEP% start >> "data\logs\website.log"
"%PYTHON%" -m web.publisher.%STEP% >> "data\logs\website.log" 2>&1
set "CODE=%ERRORLEVEL%"
if "%CODE%"=="0" (
    node web\scripts\upload-snapshot.mjs %AREA% >> "data\logs\website.log" 2>&1
    if errorlevel 1 set "CODE=3"
)
echo ===== %DATE% %TIME% %STEP% exit %CODE% >> "data\logs\website.log"
exit /b %CODE%
