# Runs the rule audit with the stored, encrypted API key.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
# keep VS Code tasks current
if (Test-Path 'tools\vscode-tasks.json') { New-Item -ItemType Directory -Force -Path .vscode | Out-Null; Copy-Item 'tools\vscode-tasks.json' '.vscode\tasks.json' -Force }
if (-not (Test-Path '.secrets\pan_key.xml')) { Write-Host "No saved key. Run setup first." -ForegroundColor Red; exit 1 }

$cfg = Get-Content '.secrets\config.json' | ConvertFrom-Json
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR((Import-Clixml '.secrets\pan_key.xml'))
try {
    $env:PAN_HOST = $cfg.host
    $env:PAN_KEY  = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    & (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'pan_audit.py')
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    Remove-Item Env:PAN_KEY -ErrorAction SilentlyContinue
}
