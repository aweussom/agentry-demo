@echo off
rem ===========================================================================
rem  ny-stripe.bat -- start codex i denne mappa med veiviseren for en ny stripe.
rem
rem  Dobbeltklikk. Codex spor deg om vitsen, figurene og stedene, ett
rem  sporsmal om gangen, og tegner stripa. Du svarer kort: "1", "ja", eller
rem  med egne ord.
rem
rem  Krever at install-windows.bat er kjort en gang og at du er logget inn
rem  i codex (codex login).
rem
rem  Codex spor om lov for den kjorer kommandoer. Svar ja; det er comic.py
rem  den vil kjore.
rem ===========================================================================
setlocal
cd /d "%~dp0"
title Ny stripe
set "HERE=%~dp0"
if not "%HERE%"=="%HERE:OneDrive=%" (
    echo  Denne mappa ligger i OneDrive. Flytt agentry-demo til C:\agentry-demo og prov igjen.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo  Finner ikke .venv. Dobbeltklikk install-windows.bat forst.
    pause
    exit /b 1
)
if not exist "VEIVISER.md" (
    echo  Finner ikke VEIVISER.md her. Er dette agentry-demo-mappa?
    pause
    exit /b 1
)
where codex >nul 2>nul
if errorlevel 1 (
    echo  Finner ikke codex. Dobbeltklikk install-windows.bat forst, og kjor "codex login".
    pause
    exit /b 1
)

echo.
echo  Starter codex. Den spor deg om vitsen. Skriv /exit for a avslutte.
echo.
codex "Jeg vil lage en ny stripe. Folg VEIVISER.md, og still meg ett sporsmal om gangen."
pause
