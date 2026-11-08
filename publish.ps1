# Commits this folder and pushes it to GitHub, after checking that no secrets are tracked.
# Safe to re-run: later runs just commit and push new changes.
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$RepoName = 'palo-alto-to-azure'

function Stop-With($msg) { Write-Host $msg -ForegroundColor Red; exit 1 }

# 1. Tools
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Stop-With "Git is not installed. Install it with:  winget install --id Git.Git -e  then reopen VS Code and run this again."
}
$hasGh = [bool](Get-Command gh -ErrorAction SilentlyContinue)
$ghAuthed = $false
if ($hasGh) { gh auth status *> $null; $ghAuthed = ($LASTEXITCODE -eq 0) }

# 2. Refresh VS Code tasks and make sure the ignore list is complete
New-Item -ItemType Directory -Force -Path .vscode | Out-Null
Copy-Item 'tools\vscode-tasks.json' '.vscode\tasks.json' -Force
$ignore = @('.venv/', '.secrets/', 'output/', '__pycache__/')
$current = if (Test-Path .gitignore) { Get-Content .gitignore } else { @() }
$missing = $ignore | Where-Object { $current -notcontains $_ }
if ($missing) { Add-Content .gitignore $missing }

# 3. Repo and identity
if (-not (Test-Path .git)) { git init -q; git branch -M main }
if (-not (git config user.email)) {
    $gName  = Read-Host "Name for your Git commits (e.g. Keith Sistrunk)"
    $gEmail = Read-Host "Email for your Git commits (your GitHub email or its noreply address)"
    git config user.name $gName
    git config user.email $gEmail
}

# 4. Stage, then refuse to continue if anything secret is staged
git add -A
$staged = git diff --cached --name-only
$badFiles = $staged | Where-Object { $_ -match '(^|/)\.secrets/|pan_key|(^|/)\.venv/|(^|/)output/|config(_writer)?\.json$' }
$badContent = git grep --cached -l -E 'LUFRPT|58\.11\.157\.82|20\.6\.122\.170' -- . ':!publish.ps1' 2>$null
if ($badFiles -or $badContent) {
    git reset -q
    Write-Host "Stopped: these files look secret or identifying and were NOT committed:" -ForegroundColor Red
    (@($badFiles) + @($badContent)) | Where-Object { $_ } | Select-Object -Unique | ForEach-Object { Write-Host "  $_" }
    exit 1
}
Write-Host "Secret check passed. Files to commit:" -ForegroundColor Green
$staged | ForEach-Object { Write-Host "  $_" }

# 5. Commit (skip if nothing changed)
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    $msg = @"
Update Palo Alto PA-440 firewall lab

Lab write-ups (baseline, SSL decryption, Azure VPN, GlobalProtect, API)
and PAN-OS XML API scripts: read-only rule audit and scripted change
with partial commit.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0141ytEP4aZUU84ETAdarVu5
"@
    $msgFile = Join-Path $env:TEMP 'pan-lab-commit.txt'
    [IO.File]::WriteAllText($msgFile, $msg, (New-Object System.Text.UTF8Encoding($false)))  # no BOM
    git commit -q -F $msgFile
    Remove-Item $msgFile -ErrorAction SilentlyContinue
    Write-Host "Committed." -ForegroundColor Green
} else {
    Write-Host "No changes to commit."
}

# 6. Push
$origin = git remote get-url origin 2>$null
if ($origin) {
    git push -u origin main
} elseif ($ghAuthed) {
    $vis = Read-Host "Create GitHub repo '$RepoName' as public or private? [public]"
    if ($vis -ne 'private') { $vis = 'public' }
    gh repo create $RepoName "--$vis" --source . --remote origin --push
} else {
    Write-Host "`nCommitted locally. To put it on GitHub:" -ForegroundColor Yellow
    if (-not $hasGh) {
        Write-Host "  Option A (easiest): winget install --id GitHub.cli -e ; gh auth login ; then run this task again."
    } else {
        Write-Host "  Option A (easiest): gh auth login ; then run this task again."
    }
    Write-Host "  Option B: create an empty repo named '$RepoName' on github.com, then run:"
    Write-Host "    git remote add origin https://github.com/<your-user>/$RepoName.git"
    Write-Host "    git push -u origin main"
}

# 7. Copy README and write-ups to the Obsidian vault
$vault = Join-Path $HOME 'Documents\Fire'
if (Test-Path $vault) {
    $dest = Join-Path $vault 'palo-alto-firewall-lab'
    New-Item -ItemType Directory -Force -Path (Join-Path $dest 'docs') | Out-Null
    Copy-Item README.md $dest -Force
    Copy-Item 'docs\*.md' (Join-Path $dest 'docs') -Force
    Write-Host "README and docs copied to Obsidian vault: $dest"
}
