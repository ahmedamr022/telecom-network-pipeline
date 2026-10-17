# Script to initialize git repository and push to GitHub
param (
    [string]$RepoUrl = "https://github.com/ahmedamr022/telecom-network-pipeline.git"
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

Write-Host "[3/4] Creating commit..." -ForegroundColor Yellow
git commit -m "feat: complete end-to-end telecom network performance pipeline with multi-evidence RCA, idempotency, and CI/CD" 2>$null

Write-Host "[4/4] Setting remote and pushing to $RepoUrl..." -ForegroundColor Yellow
git remote remove origin 2>$null
git remote add origin $RepoUrl
git branch -M main
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "Successfully pushed to GitHub: $RepoUrl" -ForegroundColor Green
} else {
    Write-Host "Push completed or requires authentication credentials." -ForegroundColor Yellow
}
