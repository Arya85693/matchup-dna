@echo off
rem Refreshes the website's data from the forecast store (read-only): "publish" writes the match, forecast and archive
rem snapshot; "players" writes the player ratings, head-to-heads and photos.
rem Usage: run_website.cmd [path\to\python.exe] [publish^|players]   (defaults: the first python on PATH, publish)
rem Output is appended to data\logs\website.log (ignored by git). Never touches the forecasting job or its store.
setlocal
cd /d "%~dp0.."
set "PYTHON=%~1"
if "%PYTHON%"=="" set "PYTHON=python"
set "STEP=%~2"
if "%STEP%"=="" set "STEP=publish"
if /i not "%STEP%"=="publish" if /i not "%STEP%"=="players" (
    echo unknown step "%STEP%": use publish or players
    exit /b 2
)
if not exist "data\logs" mkdir "data\logs"
echo ===== %DATE% %TIME% %STEP% start >> "data\logs\website.log"
"%PYTHON%" -m web.publisher.%STEP% >> "data\logs\website.log" 2>&1
set "CODE=%ERRORLEVEL%"
echo ===== %DATE% %TIME% %STEP% exit %CODE% >> "data\logs\website.log"
exit /b %CODE%
