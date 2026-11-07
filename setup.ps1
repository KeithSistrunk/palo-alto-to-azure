# One-time setup for the PAN-OS API lab. Safe to re-run (e.g. after a password change).
#   .\setup.ps1                 read-only key for the audit (user apiuser)
#   .\setup.ps1 -KeyName writer change key for push_change (user apiwriter)
param([ValidateSet('writer')][string]$KeyName = '')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host "== PAN-OS API lab setup ==" -ForegroundColor Cyan

# 1. Python check (catches the Microsoft Store placeholder too)
& python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3.9+ not found. Install it from python.org (tick 'Add python.exe to PATH'), reopen VS Code, run setup again." -ForegroundColor Red
    exit 1
}

# 2. Virtual environment and packages
if (-not (Test-Path .venv)) { Write-Host "Creating virtual environment..."; & python -m venv .venv }
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $py -m pip install --quiet --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "Package install failed." -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Force -Path output, .secrets, .vscode | Out-Null
# VS Code tasks (Ctrl+Shift+B runs the audit)
Copy-Item 'tools\vscode-tasks.json' '.vscode\tasks.json' -Force

# 3. Firewall details (Enter accepts the default)
$fwHost = Read-Host "Firewall management IP [192.168.1.100]"; if (-not $fwHost) { $fwHost = '192.168.1.100' }
$defUser = if ($KeyName -eq 'writer') { 'apiwriter' } else { 'apiuser' }
$fwUser = Read-Host "API username [$defUser]";               if (-not $fwUser) { $fwUser = $defUser }
$secPw  = Read-Host "Password for $fwUser" -AsSecureString

# 4. Generate the API key. The password lives only in memory for this step.
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPw)
try {
    $env:PAN_HOST = $fwHost; $env:PAN_USER = $fwUser
    $env:PAN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $key = & $py (Join-Path $PSScriptRoot 'tools\keygen.py')
    $rc = $LASTEXITCODE
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    Remove-Item Env:PAN_PASSWORD, Env:PAN_USER -ErrorAction SilentlyContinue
}
if ($rc -ne 0 -or -not $key) {
    Write-Host "$key" -ForegroundColor Red
    Write-Host "Check the PA system log: show log system direction equal backward | match $fwUser" -ForegroundColor Yellow
    Write-Host "If it says 'Authentication profile not found', see the runbook's known issue (Local Database profile workaround)." -ForegroundColor Yellow
    exit 1
}

# 5. Save the key encrypted for this Windows user only (DPAPI), plus non-secret settings
$suffix = if ($KeyName) { "_$KeyName" } else { '' }
("$key".Trim()) | ConvertTo-SecureString -AsPlainText -Force | Export-Clixml ".secrets\pan_key$suffix.xml"
@{ host = $fwHost; user = $fwUser } | ConvertTo-Json | Set-Content ".secrets\config$suffix.json"
Write-Host "Key saved (encrypted) as .secrets\pan_key$suffix.xml" -ForegroundColor Green

# 6. Copy the README to the Obsidian vault, if it exists
$vault = Join-Path $HOME 'Documents\Fire'
if (Test-Path $vault) {
    $dest = Join-Path $vault 'pan-api-lab'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item README.md $dest -Force
    Write-Host "README copied to Obsidian vault: $dest"
}

if ($KeyName -eq 'writer') {
    Write-Host "`nWriter setup complete. Try a dry run: Terminal > Run Task > PAN: Add address object (dry run)" -ForegroundColor Green
} else {
    Write-Host "`nSetup complete. Running the first audit..." -ForegroundColor Green
    & (Join-Path $PSScriptRoot 'run-audit.ps1')
}
