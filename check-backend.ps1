#requires -Version 7.0
# check-backend.ps1 -- is the chosen backend installed AND logged in?
# Exits 0 when yes. Exits 1 with a plain message and the exact command to
# run when not. demo.bat runs this before drawing anything, so a missing
# login fails in two seconds instead of after agentry's 120 second timeout.
#
#   check-backend.ps1 -Backend codex
#   check-backend.ps1 -Backend grok
#   check-backend.ps1            (both; exits 0 if at least one is ready)

[CmdletBinding()]
param(
    [ValidateSet("codex", "grok", "")]
    [string]$Backend = ""
)
$ErrorActionPreference = 'Continue'

function Fail([string[]]$lines) {
    Write-Host ""
    Write-Host "  *** STOP ***" -ForegroundColor Red
    foreach ($l in $lines) { Write-Host "  $l" -ForegroundColor Red }
    Write-Host ""
}

function Check-Codex {
    $exe = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $exe) {
        Fail @("codex CLI is not installed.",
               "Install: npm install -g @openai/codex   (needs Node.js: winget install -e --id OpenJS.NodeJS.LTS)",
               "Then:    codex login")
        return $false
    }
    $out = & codex login status 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $out -notmatch 'Logged in') {
        Fail @("codex is installed but NOT logged in.", "Run in a terminal:   codex login", "(it opens a browser; use your ChatGPT account)", "codex said: $($out.Trim())")
        return $false
    }
    Write-Host "  [+] codex: $($out.Trim())"
    return $true
}

function Check-Grok {
    $exe = Get-Command grok -ErrorAction SilentlyContinue
    $home_bin = Join-Path $HOME '.grok\bin\grok.exe'
    $grok = if ($exe) { $exe.Source } elseif (Test-Path $home_bin) { $home_bin } else { $null }
    if (-not $grok) {
        Fail @("grok CLI is not installed.",
               "Install: irm https://x.ai/cli/install.ps1 | iex",
               "Then:    grok login")
        return $false
    }
    $auth = Join-Path $HOME '.grok\auth.json'
    if (-not (Test-Path $auth)) {
        Fail @("grok is installed but NOT logged in (no $auth).", "Run in a terminal:   grok login", "(SuperGrok or X Premium+ account)")
        return $false
    }
    $out = & $grok models 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Fail @("grok is installed and has a credential file, but 'grok models' failed.", "Run:   grok login   and try again.", "grok said: $($out.Trim())")
        return $false
    }
    Write-Host "  [+] grok: logged in, $($out.Trim().Split("`n").Count) model line(s) listed"
    return $true
}

$ok = $false
switch ($Backend) {
    "codex" { $ok = Check-Codex }
    "grok"  { $ok = Check-Grok }
    default {
        $c = Check-Codex
        $g = Check-Grok
        $ok = $c -or $g
        if (-not $ok) { Fail @("Neither codex nor grok is ready. One of them is enough.") }
    }
}
if ($ok) { exit 0 } else { exit 1 }
