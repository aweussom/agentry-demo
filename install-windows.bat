@echo off
rem ===========================================================================
rem  install-windows.bat -- agentry-demo setup for people who just cloned or
rem  downloaded a ZIP.
rem
rem  Double-click this file. It checks for PowerShell 7 and Python 3.11+,
rem  offers to install whatever is missing via winget, then hands off to
rem  install.ps1 (ffmpeg, git, agentry, the Python venv, keys.ini).
rem
rem  Why a .bat: Windows ships PowerShell 5.1, which cannot run install.ps1
rem  (#requires 7.0), and scripts from a downloaded ZIP are blocked by
rem  execution policy. A .bat has neither problem.
rem ===========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title agentry-demo install
echo.
echo  === agentry-demo install (Windows) ===
echo.

rem --- 0. Where are we? Long paths and OneDrive break Python venvs, npm and
rem        ffmpeg in ways nobody wants to debug. Refuse early.
set "HERE=%~dp0"
set "HERE=%HERE:~0,-1%"
call :pathcheck "%HERE%"
if errorlevel 1 goto :fail

rem --- 1. PowerShell 7 ------------------------------------------------------
set "PWSH="
where pwsh >nul 2>nul && set "PWSH=pwsh"
if not defined PWSH if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"

if not defined PWSH (
    echo  PowerShell 7 is not installed. Windows ships 5.1, which is too old.
    echo.
    echo  The command to install it ^(this is all this script will run^):
    echo.
    echo      winget install --id Microsoft.PowerShell --source winget
    echo.
    where winget >nul 2>nul
    if errorlevel 1 (
        echo  ...but 'winget' was not found either. Two options:
        echo    a^) Install "App Installer" from the Microsoft Store: https://aka.ms/getwinget
        echo    b^) Download PowerShell 7 directly: https://aka.ms/powershell-release?tag=stable
        echo  Then double-click this file again.
        goto :fail
    )
    choice /C YN /M "  Run it now"
    if errorlevel 2 goto :fail
    winget install --id Microsoft.PowerShell --source winget
    if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
        set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
    ) else (
        echo.
        echo  Installed, but this window's PATH is stale. Close this window and
        echo  double-click install-windows.bat again.
        goto :fail
    )
)
echo  [+] PowerShell 7 found.

rem --- 2. Python 3.11+ ------------------------------------------------------
rem 'where python' is not enough: Windows ships a Store stub called python.exe
rem that opens the Microsoft Store instead of running. Actually execute it.
set "PYOK="
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul && set "PYOK=1"
if not defined PYOK py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul && set "PYOK=1"

if not defined PYOK (
    echo  Python 3.11+ is not installed ^(or only the Microsoft Store stub is^).
    echo.
    echo  The command to install it:
    echo.
    echo      winget install -e --id Python.Python.3.12
    echo.
    choice /C YN /M "  Run it now"
    if errorlevel 2 goto :fail
    winget install -e --id Python.Python.3.12
    echo.
    echo  Python installed. The PATH of this window is stale. Close this
    echo  window and double-click install-windows.bat again to continue.
    pause
    exit /b 0
)
echo  [+] Python 3.11+ found.

rem --- 3. Hand off to the real installer ------------------------------------
echo.
echo  Handing off to install.ps1 ...
echo.
"%PWSH%" -NoLogo -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 goto :fail

:done
echo.
echo  Next: log in to a backend once ^(codex login, or grok login^), then
echo  double-click demo.bat to draw a strip.
pause
exit /b 0

:fail
echo.
pause
exit /b 1

:pathcheck
rem %~1 is the folder this script lives in. Fail on OneDrive, on spaces, and
rem on anything longer than 60 characters. The fix is always the same: move
rem the folder to C:\agentry-demo and double-click again.
set "P=%~1"
set "BAD="
if not "%P%"=="%P:OneDrive=%" set "BAD=it is inside OneDrive"
if not "%P%"=="%P: =%" set "BAD=it has a space in it"
set "N=0"
for /L %%i in (0,1,200) do if not "!P:~%%i,1!"=="" set /a N=%%i+1
if %N% GTR 60 set "BAD=it is %N% characters long (limit 60)"
if defined BAD (
    echo  This folder is:  %P%
    echo  Not going to install here, because %BAD%.
    echo.
    echo  Move the whole agentry-demo folder to   C:\agentry-demo   ^(or C:\tmp\agentry-demo^)
    echo  and double-click install-windows.bat there. agentry will be put next to it.
    exit /b 1
)
echo  [+] Folder is fine: %P%
exit /b 0
