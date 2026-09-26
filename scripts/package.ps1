# Prometheus packaging (PLAN section 10). ASCII only (GBK console safe).
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\package.ps1
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Step($message) {
    Write-Host "==> $message"
}

# 1. Toolchain verification must pass first.
Step "1/7 verify.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -Command ". E:\tools\Prometheus-Desktop\env.ps1; & E:\tools\Prometheus-Desktop\verify.ps1; exit $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { throw "verify.ps1 failed" }

. E:\tools\Prometheus-Desktop\env.ps1

$Runtime = Join-Path $RepoRoot "app\src-tauri\resources\runtime"
if (Test-Path $Runtime) { Remove-Item -Recurse -Force $Runtime }

# 2. Copy the fixed-version runtimes (PLAN section 4 list).
Step "2/7 copy runtimes"
$PythonDir = Split-Path -Parent $env:PROMETHEUS_PYTHON
New-Item -ItemType Directory -Force -Path "$Runtime\python", "$Runtime\node", "$Runtime\pi", "$Runtime\ffmpeg" | Out-Null
Copy-Item -Recurse -Force "$PythonDir\*" "$Runtime\python\"
Copy-Item -Force $env:PROMETHEUS_NODE "$Runtime\node\node.exe"
Copy-Item -Recurse -Force "$env:PROMETHEUS_TOOLS\pi\*" "$Runtime\pi\"
Copy-Item -Force "$env:PROMETHEUS_FFMPEG\*.exe" "$Runtime\ffmpeg\"
Copy-Item -Force "$env:PROMETHEUS_FFMPEG\*.dll" "$Runtime\ffmpeg\"

# 3. Export locked requirements and install into the copied interpreter.
Step "3/7 python dependencies"
New-Item -ItemType Directory -Force -Path "$RepoRoot\build" | Out-Null
& uv export --package prometheus-backend --no-dev --no-hashes --no-emit-workspace `
    --no-emit-package playwright --no-emit-package mlx-whisper `
    --output-file "$RepoRoot\build\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "uv export failed" }
$SitePackages = "$Runtime\python\Lib\site-packages"
& "$Runtime\python\python.exe" -m pip install --no-deps --target $SitePackages -r "$RepoRoot\build\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "pip install requirements failed" }

Step "3b/7 backend and vendor wheels (non-editable)"
& uv build --package prometheus-backend --out-dir "$RepoRoot\build\wheels"
if ($LASTEXITCODE -ne 0) { throw "uv build backend failed" }
& uv build --package video-report-agent --out-dir "$RepoRoot\build\wheels"
if ($LASTEXITCODE -ne 0) { throw "uv build vendor failed" }
& "$Runtime\python\python.exe" -m pip install --no-deps --target $SitePackages (Get-ChildItem "$RepoRoot\build\wheels\*.whl").FullName
if ($LASTEXITCODE -ne 0) { throw "pip install wheels failed" }

# 4. The Skill, templates and models.json must have made it into the package.
Step "4/7 verify packaged assets"
$Required = @(
    "$SitePackages\video_report_agent\skills\video-report\SKILL.md",
    "$SitePackages\video_report_agent\skills\video-report\assets\report-template.html",
    "$SitePackages\video_report_agent\defaults\models.json"
)
foreach ($Asset in $Required) {
    if (-not (Test-Path $Asset)) { throw "missing packaged asset: $Asset" }
}

# 5. Drop caches and test trees from the runtime.
Step "5/7 clean runtime"
Get-ChildItem -Recurse -Force -Directory "$Runtime" | Where-Object {
    $_.Name -in @("__pycache__", "test", "tests")
} | Remove-Item -Recurse -Force

# 6. Frontend build and NSIS installer.
Step "6/7 npm build + tauri build (NSIS)"
Push-Location "$RepoRoot\app"
& npm run build
if ($LASTEXITCODE -ne 0) { throw "npm build failed" }
& npm run tauri build -- --bundles nsis
if ($LASTEXITCODE -ne 0) { throw "tauri build failed" }
Pop-Location

# 7. Copy the installer to the release folder and print its size.
Step "7/7 publish installer"
$ReleaseDir = "E:\tools\Prometheus-Desktop\release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$Installer = Get-ChildItem "$env:CARGO_TARGET_DIR\release\bundle\nsis\*.exe" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Installer) { throw "no NSIS installer produced" }
Copy-Item -Force $Installer.FullName (Join-Path $ReleaseDir $Installer.Name)
$SizeMB = [math]::Round($Installer.Length / 1MB, 1)
Write-Host ("installer: {0} ({1} MB)" -f $Installer.Name, $SizeMB)
if ($SizeMB -gt 300) { throw "installer exceeds the 300 MB budget (D8)" }
Write-Host "PACKAGE OK"
