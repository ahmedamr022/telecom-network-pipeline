# Launch Streamlit Telecom Operations Center Dashboard
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

$venvPython = "$projectRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPython = "python"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Launching TelcoPulse Network Operations Center (NOC) UI  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

& $venvPython -m streamlit run "$projectRoot\dashboards\app.py" --server.port 8501 --server.headless false
