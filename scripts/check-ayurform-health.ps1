$ErrorActionPreference = "Stop"
$checks = @(
  @{ Name = "Auth API"; Url = "http://127.0.0.1:8000/health" },
  @{ Name = "AyurForm API"; Url = "http://127.0.0.1:8002/api/health" },
  @{ Name = "Streamlit"; Url = "http://127.0.0.1:8501/_stcore/health" }
)
$failed = $false
foreach ($check in $checks) {
  try {
    $r = Invoke-WebRequest $check.Url -UseBasicParsing -TimeoutSec 5
    Write-Output "$($check.Name): HTTP $($r.StatusCode)"
    if ($check.Name -eq "AyurForm API") {
      $body = $r.Content | ConvertFrom-Json
      if (-not $body.database.connected) { Write-Error "AyurForm database health is not connected"; $failed = $true }
    }
  } catch { Write-Error "$($check.Name) unavailable: $($_.Exception.Message)"; $failed = $true }
}
if ($failed) { exit 1 }
