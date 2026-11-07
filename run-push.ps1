# Runs push_change.py with the stored writer key. Arguments are passed through.
# Example: .\run-push.ps1 --name lab-loopback --ip 10.100.99.1/32 --apply
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$keyFile = '.secrets\pan_key_writer.xml'
if (-not (Test-Path $keyFile)) {
    Write-Host "No writer key yet. Run: powershell -ExecutionPolicy Bypass -File .\setup.ps1 -KeyName writer" -ForegroundColor Red
    exit 1
}
$cfg = Get-Content '.secrets\config_writer.json' | ConvertFrom-Json
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR((Import-Clixml $keyFile))
try {
    $env:PAN_HOST = $cfg.host
    $env:PAN_USER = $cfg.user
    $env:PAN_KEY  = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    & (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'push_change.py') @args
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    Remove-Item Env:PAN_KEY, Env:PAN_USER -ErrorAction SilentlyContinue
}
