# Pulls the newest pan-api-lab*.zip from Downloads into this folder.
# Your key (.secrets), Python env (.venv) and results (output) are not in the zip, so they are kept.
$ErrorActionPreference = 'Stop'
$zip = Get-ChildItem (Join-Path $HOME 'Downloads\pan-api-lab*.zip') -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $zip) { Write-Host "No pan-api-lab*.zip in Downloads." -ForegroundColor Red; exit 1 }
Unblock-File $zip.FullName
Expand-Archive $zip.FullName -DestinationPath $PSScriptRoot -Force
Write-Host "Updated from $($zip.Name)" -ForegroundColor Green
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -m pip install --quiet --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements.txt')
