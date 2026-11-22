$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$envFile = Join-Path (Get-Location) ".env"
if (-not (Test-Path $envFile)) {
  $secret = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
  @("AYURSUTRA_ENV=development", "AYURSUTRA_AUTH_JWT_SECRET=$secret", "AYURSUTRA_AUTH_COOKIE_SECURE=0", "AYURSUTRA_AUTH_ALLOWED_ORIGIN=http://localhost:8501", "AYURSUTRA_AUTH_API_URL=http://localhost:8000", "AYURFORM_API_URL=http://localhost:8002", "AYURFORM_DB_FALLBACK=sqlite") | Set-Content $envFile -Encoding UTF8
  Write-Output "Created local .env with a new development JWT secret."
}
Get-Content $envFile | ForEach-Object { if ($_ -match '^\s*([^#][^=]*)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process') } }
if (-not $env:AYURFORM_DB_FALLBACK) { $env:AYURFORM_DB_FALLBACK = "sqlite" }
function Test-Port([int]$Port) { return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).Count -gt 0 }
function Start-ServiceIfNeeded([string]$Name, [int]$Port, [string]$Command) {
  if (Test-Port $Port) {
    if ($Name -eq "AyurForm API") {
      $apiOk = $false
      try { $doc = (Invoke-RestMethod "http://127.0.0.1:$Port/openapi.json" -TimeoutSec 3); $apiOk = $null -ne $doc.paths.'/api/reviews/pending' } catch { }
      if (-not $apiOk) {
        $listenerIds = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
        $owned = @($listenerIds | ForEach-Object { Get-CimInstance Win32_Process -Filter "ProcessId = $_" -ErrorAction SilentlyContinue } | Where-Object { $_.CommandLine -match 'uvicorn\s+ayurform_api:app' })
        if (-not $owned) { throw "Port $Port is occupied by a process that is not the AyurForm API. Stop it or choose another port." }
        foreach ($process in $owned) { Stop-Process -Id $process.ProcessId -Force }
        Write-Output "Restarted stale AyurForm API process to load current routes."
      } else { Write-Output "$Name already listening with current review routes on port $Port"; return }
    } else { Write-Output "$Name already listening on port $Port"; return }
  }
  Start-Process powershell -WorkingDirectory (Get-Location) -ArgumentList "-NoExit", "-Command", $Command | Out-Null
  for ($i=0; $i -lt 20; $i++) { Start-Sleep -Milliseconds 500; if (Test-Port $Port) { Write-Output "$Name ready on port $Port"; return } }
  throw "$Name did not become ready on port $Port. Check its service window for errors."
}
Start-ServiceIfNeeded "Auth API" 8000 ".\.venv\Scripts\python.exe -m uvicorn auth_api:app --host 127.0.0.1 --port 8000"
Start-ServiceIfNeeded "AyurForm API" 8002 ".\.venv\Scripts\python.exe -m uvicorn ayurform_api:app --host 127.0.0.1 --port 8002"
if (-not (Test-Port 8501)) { streamlit run app.py --server.address 127.0.0.1 --server.port 8501 } else { Write-Output "Streamlit already listening on port 8501" }
