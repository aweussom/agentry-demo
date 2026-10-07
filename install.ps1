#requires -Version 7.0
# install.ps1 -- the real installer for agentry-demo. install-windows.bat
# calls this after it has made sure PowerShell 7 and Python 3.11+ exist.
#
# What it does, in order, asking before anything it installs:
#   1. git and ffmpeg on PATH (winget if missing)
#   2. agentry cloned next to this folder (..\agentry), or wherever -AgentryDir says
#   3. a Python venv here, with requirements.txt
#   4. keys.ini from keys.ini.template, pointed at the xkcd project and at agentry
#   5. the backend CLIs: codex (needs Node) and grok; it only prints the login commands
#
# Flags: -AgentryDir <path>  -SkipClis  -Yes (answer yes to every prompt)

[CmdletBinding()]
param(
    [string]$AgentryDir = "",
    [switch]$SkipClis,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Ask([string]$question) {
    if ($Yes) { return $true }
    $a = Read-Host "  $question [y/N]"
    return $a -match '^[yY]'
}

function Have([string]$cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

function WingetInstall([string]$id, [string]$what) {
    if (-not (Have 'winget')) {
        Write-Host "  $what is missing and winget is not available. Install it by hand, then run this again."
        exit 1
    }
    Write-Host "  $what is missing. The command: winget install -e --id $id"
    if (-not (Ask "Run it now")) { exit 1 }
    winget install -e --id $id --accept-package-agreements --accept-source-agreements
    Write-Host "  Installed. PATH in this window is stale; close it and run install-windows.bat again."
    exit 0
}

Write-Host ""
Write-Host "  === agentry-demo install.ps1 ==="
Write-Host ""

# --- 1. ffmpeg (git is optional, see step 2) --------------------------------
if (-not (Have 'ffmpeg')) { WingetInstall 'Gyan.FFmpeg' 'ffmpeg' }
Write-Host "  [+] ffmpeg found."
if (Have 'git') { Write-Host "  [+] git found." } else { Write-Host "  [ ] git not found; agentry will be downloaded as a ZIP instead." }

# --- 2. agentry: next to this folder. git clone if git exists, else the ZIP
#        GitHub serves for the main branch, so nothing is bundled and nothing
#        goes stale in this repo.
if (-not $AgentryDir) { $AgentryDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'agentry' }
$AgentryDir = [System.IO.Path]::GetFullPath($AgentryDir)
if (-not (Test-Path (Join-Path $AgentryDir 'agentry.py'))) {
    Write-Host "  agentry is not at $AgentryDir."
    if (Have 'git') {
        Write-Host "  The command: git clone https://github.com/aweussom/agentry `"$AgentryDir`""
        if (-not (Ask "Clone it now")) { exit 1 }
        git clone https://github.com/aweussom/agentry "$AgentryDir"
    } else {
        $zipUrl = 'https://github.com/aweussom/agentry/archive/refs/heads/main.zip'
        Write-Host "  Will download $zipUrl and unpack it to $AgentryDir"
        if (-not (Ask "Download it now")) { exit 1 }
        $tmp = Join-Path ([System.IO.Path]::GetTempPath()) 'agentry-main.zip'
        Invoke-WebRequest -Uri $zipUrl -OutFile $tmp
        $unpack = Join-Path ([System.IO.Path]::GetTempPath()) 'agentry-unpack'
        if (Test-Path $unpack) { Remove-Item $unpack -Recurse -Force }
        Expand-Archive -Path $tmp -DestinationPath $unpack
        Move-Item (Join-Path $unpack 'agentry-main') $AgentryDir
        Remove-Item $tmp -Force
    }
}
if (-not (Test-Path (Join-Path $AgentryDir 'agentry.py'))) {
    Write-Host "  agentry.py is still not at $AgentryDir. Stopping."
    exit 1
}
Write-Host "  [+] agentry at $AgentryDir"

# --- 3. venv + requirements ------------------------------------------------
$py = if (Have 'python') { 'python' } else { 'py' }
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host "  Creating .venv ..."
    & $py -m venv .venv
}
& '.venv\Scripts\python.exe' -m pip install --quiet --upgrade pip
& '.venv\Scripts\python.exe' -m pip install --quiet -r requirements.txt
Write-Host "  [+] Python packages installed in .venv"

# --- 4. keys.ini -----------------------------------------------------------
# keys.ini ships with the repo (no secrets; agentry_dir = ../agentry). Only
# rewrite agentry_dir when -AgentryDir points somewhere else.
$default = [System.IO.Path]::GetFullPath((Join-Path (Split-Path $PSScriptRoot -Parent) 'agentry'))
if ($AgentryDir -ne $default) {
    $t = Get-Content 'keys.ini' -Raw
    $t = $t -replace '(?m)^agentry_dir = .*$', ('agentry_dir = ' + ($AgentryDir -replace '\\', '/'))
    Set-Content 'keys.ini' $t -NoNewline
    Write-Host "  [+] keys.ini: agentry_dir = $AgentryDir"
} else {
    Write-Host "  [+] keys.ini as shipped (agentry_dir = ../agentry)"
}

# --- 5. backend CLIs -------------------------------------------------------
if (-not $SkipClis) {
    Write-Host ""
    Write-Host "  Backends. You need ONE of these, logged in:"
    Write-Host ""
    if (Have 'codex') {
        Write-Host "  [+] codex CLI found. Log in once with:   codex login"
    } else {
        Write-Host "  [ ] codex CLI (ChatGPT subscription, draws the strips)."
        if (Have 'npm') {
            Write-Host "      The command: npm install -g @openai/codex"
            if (Ask "Install codex now") { npm install -g @openai/codex }
        } else {
            Write-Host "      Needs Node.js first: winget install -e --id OpenJS.NodeJS.LTS"
            Write-Host "      then: npm install -g @openai/codex   and   codex login"
        }
    }
    if (Have 'grok') {
        Write-Host "  [+] grok CLI found. Log in once with:    grok login"
    } else {
        Write-Host "  [ ] grok CLI (SuperGrok subscription, draws the film and can draw strips)."
        Write-Host "      The command: irm https://x.ai/cli/install.ps1 | iex"
        if (Ask "Install grok now") { Invoke-Expression (Invoke-RestMethod 'https://x.ai/cli/install.ps1') }
    }
}

Write-Host ""
Write-Host "  Checking whether a backend is logged in ..."
& (Join-Path $PSScriptRoot 'check-backend.ps1')
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Install is done, but no backend is logged in yet. Run one of the login commands above, then double-click demo.bat."
    exit 0
}
Write-Host ""
Write-Host "  Done. Double-click demo.bat to draw a strip."
exit 0
