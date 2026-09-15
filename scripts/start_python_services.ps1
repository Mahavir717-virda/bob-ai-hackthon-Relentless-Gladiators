# GridPilot AI - Python Microservices Startup Script (venv)
# Usage: .\scripts\start_python_services.ps1
# Starts all 4 Python microservices in separate windows using the project venv.

$root = Split-Path -Parent $PSScriptRoot
$venvPython = "$root\venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "venv not found at $root\venv. Run: python -m venv venv && venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Write-Host "GridPilot AI - Starting Python Microservices via venv" -ForegroundColor Cyan
Write-Host "venv: $root\venv" -ForegroundColor Gray
Write-Host ""

$services = @(
    @{ Name = "Data Telemetry      (8001)"; Module = "services.data.api:app";              Port = 8001 },
    @{ Name = "Demand Forecasting   (8002)"; Module = "services.forecasting.api:app";       Port = 8002 },
    @{ Name = "Renewable / Kaggle   (8003)"; Module = "services.renewable.kaggle_api:app";  Port = 8003 },
    @{ Name = "Grid Optimization    (8004)"; Module = "services.optimization.api:app";      Port = 8004 }
)

foreach ($svc in $services) {
    # Kill any existing process on this port
    $owner = (Get-NetTCPConnection -LocalPort $svc.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
    if ($owner) {
        Write-Host "  Killing existing process on port $($svc.Port) (PID $owner)" -ForegroundColor DarkYellow
        Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
    }

    Write-Host "Starting $($svc.Name) ..." -ForegroundColor Green
    $cmd = "Set-Location '$root'; `$env:PYTHONPATH='.'; & '$venvPython' -m uvicorn $($svc.Module) --host 127.0.0.1 --port $($svc.Port)"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "All services launched. Health endpoints:" -ForegroundColor Cyan
Write-Host "  Data Telemetry  : http://127.0.0.1:8001/health"
Write-Host "  Demand Forecast : http://127.0.0.1:8002/health"
Write-Host "  Renewable Intel : http://127.0.0.1:8003/health"
Write-Host "  Grid Optimizer  : http://127.0.0.1:8004/health"
Write-Host ""
Write-Host "Node.js API gateway: http://localhost:8000" -ForegroundColor Yellow
