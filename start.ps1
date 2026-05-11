# MediFormulary Quick Start Script
# Starts both the FastAPI Backend and the React Frontend

Write-Host "--- MediFormulary Quick Start (Modular FastAPI) ---" -ForegroundColor Cyan

# 1. Validation
$pythonExe = if (Test-Path ".venv/Scripts/python.exe") { ".venv/Scripts/python.exe" } else { "python" }

if (-not (Test-Path ".env")) {
    Write-Host "No .env file found. Creating a basic template..." -ForegroundColor Yellow
    "OPENAI_API_KEY=your_key_here`nENVIRONMENT=development`nOTEL_SDK_DISABLED=true" | Out-File -FilePath ".env"
}

# 2. Cleanup existing processes (Ports 8000 and 5173/5174)
Write-Host "Cleaning up existing processes..."
try {
    # Port 8000 (New FastAPI Backend)
    $port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($port8000 -and $port8000.OwningProcess -gt 0) { 
        Write-Host "Stopping process on port 8000 (PID: $($port8000.OwningProcess))..."
        Stop-Process -Id $port8000.OwningProcess -Force 
    }
    
    # Common Vite ports
    $portVite = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
    if (-not $portVite) { $portVite = Get-NetTCPConnection -LocalPort 5174 -ErrorAction SilentlyContinue }
    if ($portVite -and $portVite.OwningProcess -gt 0) { 
        Write-Host "Stopping process on port 5173/5174 (PID: $($portVite.OwningProcess))..."
        Stop-Process -Id $portVite.OwningProcess -Force 
    }

    # Clear Vite Cache
    Remove-Item -Path "frontend/node_modules/.vite" -Recurse -Force -ErrorAction SilentlyContinue
} catch {
    Write-Host "Cleanup skipped or failed."
}

# 3. Start Backend in separate window
Write-Host "Starting FastAPI Backend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Starting FastAPI Backend...'; & '$pythonExe' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

# 4. Start Frontend
Write-Host "Starting Frontend..." -ForegroundColor Green
Set-Location frontend
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..."
    npm install
}
npm run dev
