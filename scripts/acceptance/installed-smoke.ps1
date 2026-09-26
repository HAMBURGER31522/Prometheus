# Installed smoke test (PLAN section 10 / D8). ASCII only.
param([string]$Installer = "E:\tools\Prometheus-Desktop\release\Prometheus_0.1.0_x64-setup.exe")

$ErrorActionPreference = "Stop"
$InstallDir = "F:\project\Prometheus\acceptance-output\installed"
$DataDir = "F:\project\Prometheus\acceptance-output\smoke-data"

if (-not (Test-Path $Installer)) { throw "installer not found: $Installer" }
if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
if (Test-Path $DataDir) { Remove-Item -Recurse -Force $DataDir }
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

Write-Host "==> silent install"
Start-Process -FilePath $Installer -ArgumentList "/S", "/D=$InstallDir" -Wait
if (-not (Test-Path "$InstallDir\Prometheus.exe")) { throw "install failed: Prometheus.exe missing" }

Write-Host "==> launch installed app"
$env:PROMETHEUS_TEST_DATA_DIR = $DataDir
$proc = Start-Process -FilePath "$InstallDir\Prometheus.exe" -PassThru

Write-Host "==> poll /api/health via backend.port (D8: within 30 seconds)"
$deadline = (Get-Date).AddSeconds(30)
$ok = $false
while ((Get-Date) -lt $deadline) {
    $portFile = Join-Path $DataDir "logs\backend.port"
    if (Test-Path $portFile) {
        $port = (Get-Content $portFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($port) {
            try {
                $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/api/health" -TimeoutSec 2
                if ($r.StatusCode -eq 200) { $ok = $true; break }
            } catch {}
        }
    }
    Start-Sleep -Milliseconds 500
}
if (-not $ok) { throw "backend did not report healthy within 30 seconds" }
Write-Host "backend healthy"

Write-Host "==> stop the app"
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Get-Process -Name "Prometheus" -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
if (-not (Test-Path $DataDir)) { throw "data dir disappeared before uninstall" }

Write-Host "==> silent uninstall"
$Uninstall = "$InstallDir\uninstall.exe"
if (-not (Test-Path $Uninstall)) { throw "uninstaller missing" }
Start-Process -FilePath $Uninstall -ArgumentList "/S" -Wait
Start-Sleep -Seconds 5
if (Test-Path "$InstallDir\Prometheus.exe") { throw "uninstall left Prometheus.exe behind" }
if (-not (Test-Path $DataDir)) { throw "uninstall removed the data dir (D8 violation)" }

Write-Host "INSTALLED SMOKE OK"
