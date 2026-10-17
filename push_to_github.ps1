# Script to initialize git repository and push to GitHub
param (
    [string]$RepoUrl
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Telecom Network Performance Pipeline - Git Push Helper   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".git")) {
    Write-Host "[1/4] Initializing Git repository..." -ForegroundColor Yellow
    git init
    git branch -M main
}

Write-Host "[2/4] Staging files..." -ForegroundColor Yellow
git add .

Write-Host "[3/4] Creating initial commit..." -ForegroundColor Yellow
git commit -m "feat: initial release of telecom network performance data pipeline and observability platform"

if ($RepoUrl) {
    Write-Host "[4/4] Setting remote and pushing to $RepoUrl..." -ForegroundColor Yellow
    git remote remove origin 2>$null
    git remote add origin $RepoUrl
    git push -u origin main
    Write-Host "Successfully pushed to GitHub!" -ForegroundColor Green
} else {
    Write-Host "Repository initialized and committed locally." -ForegroundColor Green
    Write-Host "To push to GitHub, run: .\push_to_github.ps1 -RepoUrl 'https://github.com/YOUR_USERNAME/telecom-network-pipeline.git'" -ForegroundColor Yellow
}
