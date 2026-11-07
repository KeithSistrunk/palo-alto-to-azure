# Creates (or with -Remove, deletes) the apiwriter account on the PA, then stores its key
# and runs a dry run. Uses the admin login once, in memory only; nothing admin is saved.
#   powershell -ExecutionPolicy Bypass -File .\bootstrap-writer.ps1
#   powershell -ExecutionPolicy Bypass -File .\bootstrap-writer.ps1 -Remove
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { Write-Host "Run setup.ps1 first (it creates the Python environment)." -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Force -Path .vscode | Out-Null
Copy-Item 'tools\vscode-tasks.json' '.vscode\tasks.json' -Force

function Plain($sec) {
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

$cfg = if (Test-Path '.secrets\config.json') { Get-Content '.secrets\config.json' | ConvertFrom-Json } else { $null }
$fwHost = if ($cfg) { $cfg.host } else { '192.168.1.100' }
Write-Host "== apiwriter bootstrap on $fwHost ==" -ForegroundColor Cyan
$adminUser = Read-Host "Firewall superuser [admin]"; if (-not $adminUser) { $adminUser = 'admin' }
$adminPw = Read-Host "Password for $adminUser (used once, not saved)" -AsSecureString

$writerPw = $null
if (-not $Remove) {
    $p1 = Read-Host "New password for apiwriter (8+ characters)" -AsSecureString
    $p2 = Read-Host "Confirm apiwriter password" -AsSecureString
    $writerPw = Plain $p1
    if ($writerPw -ne (Plain $p2)) { Write-Host "Passwords don't match." -ForegroundColor Red; exit 1 }
}

try {
    $env:PAN_HOST = $fwHost
    $env:PAN_ADMIN_USER = $adminUser
    $env:PAN_ADMIN_PASSWORD = Plain $adminPw
    if ($writerPw) { $env:PAN_WRITER_PASSWORD = $writerPw }
    $pyArgs = @((Join-Path $PSScriptRoot 'tools\bootstrap_writer.py'))
    if ($Remove) { $pyArgs += '--remove' }
    & $py @pyArgs
    $rc = $LASTEXITCODE
} finally {
    Remove-Item Env:PAN_ADMIN_PASSWORD, Env:PAN_WRITER_PASSWORD, Env:PAN_ADMIN_USER -ErrorAction SilentlyContinue
}
if ($rc -ne 0) { exit $rc }

if ($Remove) {
    Remove-Item '.secrets\pan_key_writer.xml', '.secrets\config_writer.json' -ErrorAction SilentlyContinue
    Write-Host "Writer key removed from this laptop." -ForegroundColor Green
    exit 0
}

# Generate and store the writer key (retries while the firewall finishes loading the new account)
$key = $null
try {
    $env:PAN_USER = 'apiwriter'; $env:PAN_PASSWORD = $writerPw
    for ($i = 1; $i -le 4 -and -not $key; $i++) {
        $out = & $py (Join-Path $PSScriptRoot 'tools\keygen.py')
        if ($LASTEXITCODE -eq 0 -and $out) { $key = "$out".Trim() } else { Write-Host "Key attempt $i/4: $out"; Start-Sleep -Seconds 10 }
    }
} finally {
    Remove-Item Env:PAN_PASSWORD, Env:PAN_USER -ErrorAction SilentlyContinue
    $writerPw = $null
}
if (-not $key) {
    Write-Host "apiwriter was created, but its API key couldn't be generated. Check: show log system direction equal backward | match apiwriter" -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force -Path .secrets | Out-Null
$key | ConvertTo-SecureString -AsPlainText -Force | Export-Clixml '.secrets\pan_key_writer.xml'
@{ host = $fwHost; user = 'apiwriter' } | ConvertTo-Json | Set-Content '.secrets\config_writer.json'
Write-Host "Writer key saved (encrypted). Running a dry run..." -ForegroundColor Green
& (Join-Path $PSScriptRoot 'run-push.ps1') --name lab-loopback --ip 10.100.99.1/32
