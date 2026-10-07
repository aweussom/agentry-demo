@echo off
rem ===========================================================================
rem  demo.bat -- draw one xkcd strip through agentry and open the picker.
rem
rem  Double-click. Needs install-windows.bat done once, and one backend
rem  logged in (codex login, or grok login).
rem
rem  Optional arguments:
rem      demo.bat                       draws 058 Why Do You Love Me; grok if it
rem                                     is logged in, else codex
rem      demo.bat 069-pillow-talk       another draft from prosjekter\xkcd\utkast
rem      demo.bat 069-pillow-talk codex force a backend: codex or grok
rem ===========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title agentry-demo
set "HERE=%~dp0"
if not "%HERE%"=="%HERE:OneDrive=%" (
    echo  This folder is inside OneDrive. Move agentry-demo to C:\agentry-demo and try again.
    pause
    exit /b 1
)

set "DRAFT=%~1"
if "%DRAFT%"=="" set "DRAFT=058-why-do-you-love-me"
set "BACKEND=%~2"

if not exist ".venv\Scripts\python.exe" (
    echo  No .venv here. Double-click install-windows.bat first.
    pause
    exit /b 1
)
set "PY=.venv\Scripts\python.exe"
set "MD=prosjekter\xkcd\utkast\%DRAFT%.md"
if not exist "%MD%" (
    echo  No such draft: %MD%
    echo  Drafts available:
    dir /b prosjekter\xkcd\utkast
    pause
    exit /b 1
)

echo.
echo  === agentry-demo: %DRAFT% ===
echo.

rem --- Is the backend installed and logged in? Fail now, not in two minutes.
set "PWSH="
where pwsh >nul 2>nul && set "PWSH=pwsh"
if not defined PWSH if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not defined PWSH (
    echo  PowerShell 7 not found. Double-click install-windows.bat first.
    pause
    exit /b 1
)
rem No backend given: grok if it is installed and logged in (one SuperGrok
rem subscription covers strips and film), else codex, else stop.
if "%BACKEND%"=="" (
    "%PWSH%" -NoLogo -ExecutionPolicy Bypass -File "%~dp0check-backend.ps1" -Backend grok >nul 2>nul
    if not errorlevel 1 set "BACKEND=grok"
)
if "%BACKEND%"=="" (
    "%PWSH%" -NoLogo -ExecutionPolicy Bypass -File "%~dp0check-backend.ps1" -Backend codex >nul 2>nul
    if not errorlevel 1 set "BACKEND=codex"
)
if "%BACKEND%"=="" (
    "%PWSH%" -NoLogo -ExecutionPolicy Bypass -File "%~dp0check-backend.ps1"
    pause
    exit /b 1
)
"%PWSH%" -NoLogo -ExecutionPolicy Bypass -File "%~dp0check-backend.ps1" -Backend %BACKEND%
if errorlevel 1 (
    pause
    exit /b 1
)
echo  Backend: %BACKEND%

echo  First run starts agentry itself on port 8770 ^(codex^) or 8766 ^(grok^).
echo  A strip takes one to three minutes.
echo.

if /I "%BACKEND%"=="grok" (
    "%PY%" comic.py new "%MD%" -p grok-agentry --panels
) else (
    "%PY%" comic.py new "%MD%" -p agentry
)
if errorlevel 1 (
    echo.
    echo  That failed. The usual reasons: the backend is not logged in ^(run
    echo  "codex login" or "grok login" in a terminal^), or agentry is not where
    echo  keys.ini says ^(agentry_dir^).
    pause
    exit /b 1
)

echo.
echo  Opening the picker in your browser. Click a panel to comment, press
echo  "Velg denne" on the one you want. Close this window when done.
echo.
"%PY%" comic.py pick "%MD%"
pause
exit /b 0
