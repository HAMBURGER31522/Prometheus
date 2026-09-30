# Installed live run (PLAN 15.4.16: E8, E4, E3). ASCII only.
# Installs the built installer into a scratch folder, starts it with a clean environment and
# PROMETHEUS_FORBID_DEV_PATHS=1, installs Codex CLI from the app, drives the real window to process a
# video (all three parts), cancels a second one during the report, closes the window properly,
# uninstalls, cleans up and restores the app's own folders under LOCALAPPDATA / APPDATA.
param(
    [string]$Installer = "E:\tools\Prometheus-Desktop\release\Prometheus_1.0.0_x64-setup.exe",
    [string]$Video = "https://www.bilibili.com/video/BV1P5h16JE8n",
    [string]$CancelVideo = "https://www.bilibili.com/video/BV1EJ4m1t7Zs",
    [string]$Preview = "F:\project\Prometheus\acceptance-output\r7-data",
    [string]$Profile = "chatgpt-codex"
)
$ErrorActionPreference = "Stop"
$Repo = "F:\project\Prometheus"
$Root = "$Repo\acceptance-output\installed-live"
$InstallDir = "$Root\app"
$DataDir = "$Root\data"
$Backup = "$Root\backup"
$Shots = "$Root\shots"
$Results = "$Repo\acceptance-output\r8-installed-results"
$AppId = "com.hamburger31522.prometheus"
$Folders = @("$env:LOCALAPPDATA\$AppId", "$env:APPDATA\$AppId")
$Node = "E:\tools\Prometheus-Desktop\node\node.exe"   # the test harness only; the app uses its own
$CdpPort = 9333
$failures = @()
$notes = @()

function Say($message) { Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $message) }
function Fail($message) { $script:failures += $message; Say "FAIL: $message" }
function Utf8NoBom($path, $text) { [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false)) }

function Link-Tree($from, $to) {
    # Hard links: no extra space, and deleting them later leaves the originals alone.
    if (-not (Test-Path $from)) { return }
    Get-ChildItem -LiteralPath $from -Recurse -File -Force | ForEach-Object {
        $rel = $_.FullName.Substring($from.Length).TrimStart('\')
        $dest = Join-Path $to $rel
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        New-Item -ItemType HardLink -Path $dest -Target $_.FullName | Out-Null
    }
}

function Descendants($rootPid) {
    $all = Get-CimInstance Win32_Process
    $found = @()
    $frontier = @($rootPid)
    while ($frontier.Count -gt 0) {
        $next = @()
        foreach ($p in $all) {
            if ($frontier -contains $p.ParentProcessId -and $p.ProcessId -ne $rootPid) { $found += $p; $next += $p.ProcessId }
        }
        $frontier = $next
    }
    return $found
}

function Api($method, $path, $body = $null, $timeout = 60) {
    $request = @{ Method = $method; Uri = "http://127.0.0.1:$script:Port$path"; Headers = @{ Authorization = "Bearer $script:Token" };
                  TimeoutSec = $timeout; UseBasicParsing = $true }
    if ($body -ne $null) {
        $request.Body = [Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 8 -Compress))
        $request.ContentType = "application/json; charset=utf-8"
    }
    try {
        $r = Invoke-WebRequest @request
    } catch [System.Net.WebException] {
        throw ("{0} {1} -> {2} {3}" -f $method, $path, $_.Exception.Message, $_.ErrorDetails.Message)
    }
    return ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json)
}

function Row($videoId) {
    $rows = Api GET "/api/queue"
    return ($rows | Where-Object { $_.video_id -like "$videoId*" } | Select-Object -First 1)
}

if (-not (Test-Path $Installer)) { throw "installer not found: $Installer" }
if (Test-Path $Root) { Remove-Item -Recurse -Force $Root }
New-Item -ItemType Directory -Force -Path $Root, $DataDir, $Backup, $Shots | Out-Null
if (Test-Path $Results) { Remove-Item -Recurse -Force $Results }
New-Item -ItemType Directory -Force -Path $Results | Out-Null

Say "back up the app's own folders"
$i = 0
foreach ($folder in $Folders) {
    if (Test-Path $folder) { Move-Item -LiteralPath $folder -Destination "$Backup\folder$i" }
    $i += 1
}

$app = $null
try {
    Say "silent install into $InstallDir"
    Start-Process -FilePath $Installer -ArgumentList "/S", "/D=$InstallDir" -Wait
    if (-not (Test-Path "$InstallDir\Prometheus.exe")) { throw "install failed: Prometheus.exe missing" }
    $size = (Get-Item $Installer).Length / 1MB
    Say ("installer {0:N1} MB" -f $size)

    Say "data dir: the $Profile profile, standard depth by default, figures on; Codex login; models by hard link"
    $config = "$DataDir\.prometheus\config"
    New-Item -ItemType Directory -Force -Path "$config\codex" | Out-Null
    # not $preview: PowerShell names ignore case, and the [string] parameter $Preview would turn it into text
    $previewSettings = [IO.File]::ReadAllText("$Preview\.prometheus\config\settings.json") | ConvertFrom-Json
    $chosen = $previewSettings.llm_profiles.items | Where-Object { $_.id -eq $Profile }
    if (-not $chosen) { throw "profile $Profile not in the preview settings" }
    $settings = [ordered]@{
        llm_profiles = [ordered]@{ active = $Profile; items = @($chosen) }
        figures_default = $true
        report = [ordered]@{ depth = "standard"; review = $true }
    }
    Utf8NoBom "$config\settings.json" ($settings | ConvertTo-Json -Depth 10)
    Copy-Item "$Preview\.prometheus\config\codex\auth.json" "$config\codex\auth.json"
    Link-Tree "$Preview\.prometheus\models" "$DataDir\.prometheus\models"
    Link-Tree "$Preview\.prometheus\runtime" "$DataDir\.prometheus\runtime"

    Say "start the installed app with a clean environment"
    foreach ($name in @(Get-ChildItem Env: | ForEach-Object { $_.Name })) {
        if ($name -match '^(PROMETHEUS_|UV_|VIRTUAL_ENV|PYTHON|HF_HOME|PLAYWRIGHT_|CARGO_|RUSTUP_|npm_)') { Remove-Item "Env:$name" }
    }
    $env:PATH = (($env:PATH -split ';') | Where-Object { $_ -and $_ -notlike '*Prometheus-Desktop*' -and $_ -notlike '*.venv*' -and $_ -notlike '*\uv' }) -join ';'
    $env:PROMETHEUS_TEST_DATA_DIR = $DataDir
    $env:PROMETHEUS_FORBID_DEV_PATHS = "1"
    $env:npm_config_cache = "$Root\npm-cache"
    $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=$CdpPort"
    $app = Start-Process -FilePath "$InstallDir\Prometheus.exe" -PassThru

    $deadline = (Get-Date).AddSeconds(90)
    $script:Port = $null
    while ((Get-Date) -lt $deadline -and -not $script:Port) {
        $portFile = "$DataDir\.prometheus\logs\backend.port"
        if (Test-Path $portFile) {
            $candidate = (Get-Content $portFile | Select-Object -First 1)
            try {
                $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$candidate/api/health" -TimeoutSec 2
                if ($r.StatusCode -eq 200) { $script:Port = $candidate }
            } catch {}
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $script:Port) { throw "backend did not report healthy within 90 seconds" }
    $backend = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*prometheus.server*--port $script:Port *" } | Select-Object -First 1
    if (-not $backend) { throw "backend process not found" }
    if ($backend.CommandLine -notmatch '--token (\S+)') { throw "no token on the backend command line" }
    $script:Token = $Matches[1]
    Say ("backend pid {0} on port {1}: {2}" -f $backend.ProcessId, $script:Port, $backend.ExecutablePath)
    if ($backend.ExecutablePath -notlike "$InstallDir*") { Fail "backend python is not the installed one: $($backend.ExecutablePath)" }

    Say "install Codex CLI from the app (npm, then its self-check)"
    $started = Get-Date
    $agents = Api POST "/api/agents/codex/install" $null 1800
    $codex = $agents.agents | Where-Object { $_.id -eq "codex" }
    Say ("codex installed={0} version={1} in {2:N0} s" -f $codex.installed, $codex.version, ((Get-Date) - $started).TotalSeconds)
    if (-not $codex.installed) { throw "Codex CLI did not install" }
    $notes += ("Codex CLI {0} installed from npm in {1:N0} s" -f $codex.version, ((Get-Date) - $started).TotalSeconds)
    $login = Api GET "/api/agents/codex/login"
    Say ("codex login: {0}" -f ($login | ConvertTo-Json -Compress))

    Say "drive the window: submit $Video"
    $env:PLAYWRIGHT_BROWSERS_PATH = "E:\tools\playwright-browsers"
    Push-Location "$Repo\app"
    & $Node "scripts\installed-live.mjs" "http://127.0.0.1:$CdpPort" "http://127.0.0.1:$script:Port" $script:Token $Video $Shots
    $driver = $LASTEXITCODE
    Pop-Location
    if ($driver -ne 0) { Fail "the window driver failed ($driver)" }

    $videoId = [regex]::Match($Video, 'BV[0-9A-Za-z]{10}').Value
    $row = Row $videoId
    if ($row -and $row.status -eq "done") {
        $folder = Join-Path $DataDir $row.library_path
        $names = @(Get-ChildItem -LiteralPath $folder -File | ForEach-Object { $_.Name })
        $expected = @("html", "md", "mindmap", "srt", "txt", "url")
        $files = [IO.File]::ReadAllText("$DataDir\index.json") | ConvertFrom-Json
        $entry = $files.items | Where-Object { $_.id -eq $row.id }
        foreach ($role in $expected) { if (-not $entry.paths.$role) { Fail "library file missing: $role" } }
        if ($row.subtitle_status -ne "ok") { Fail "subtitles not corrected: $($row.subtitle_status)" }
        if ($row.mindmap_status -ne "ok") { Fail "mind map: $($row.mindmap_status) $($row.mindmap_error)" }
        $html = [IO.File]::ReadAllText((Join-Path $DataDir $entry.paths.html))
        $chapters = ([regex]::Matches($html, 'class="section-title"')).Count
        $views = ([regex]::Matches($html, '<aside class="viewpoint">')).Count
        $nav = ([regex]::Matches($html, 'class="report-nav"')).Count
        $han = ([regex]::Matches(($html -replace '<(script|style)[^>]*>[\s\S]*?</\1>', '' -replace '<[^>]+>', ''), '[\u4e00-\u9fff]')).Count
        Say ("report: {0} chapters, {1} viewpoint boxes, nav {2}, {3} Chinese characters" -f $chapters, $views, $nav, $han)
        $notes += ("report: {0} chapters, {1} viewpoint boxes, nav {2}, {3} Chinese characters" -f $chapters, $views, $nav, $han)
        if ($chapters -ge 2 -and $nav -lt 1) { Fail "no jump TOC with $chapters chapters" }
        if ($views -lt 1) { $notes += "NOTE: no editor's viewpoint box in this report" }
        $trace = Get-Content -LiteralPath "$DataDir\.prometheus\cache\$($row.id)\run.trace.jsonl" -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json }
        $ended = @($trace | Where-Object { $_.event -eq "end" } | ForEach-Object { $_.stage })
        foreach ($stage in $row.stages) { if ($ended -notcontains $stage) { Fail "stage never ended: $stage" } }
        $first = [datetime]($trace | Select-Object -First 1).at
        $last = [datetime]($trace | Select-Object -Last 1).at
        $steps = ($trace | Where-Object { $_.event -eq "end" } | ForEach-Object { "{0} {1:N0}s" -f $_.stage, $_.elapsed_s }) -join ", "
        $notes += ("run: {0:N1} min: {1}" -f ($last - $first).TotalMinutes, $steps)
        Copy-Item -Recurse -LiteralPath $folder -Destination "$Results\library-item"
    } else {
        Fail ("video did not finish: {0}" -f ($row | ConvertTo-Json -Compress))
    }

    Say "cancel test (E4): $CancelVideo, cancelled during the report"
    $body = @{ url = $CancelVideo; figures = $false; depth = "standard"; outputs = @{ report = $true; subtitles = $true; mindmap = $true } }
    $created = Api POST "/api/items" $body
    $cancelId = [regex]::Match($CancelVideo, 'BV[0-9A-Za-z]{10}').Value
    $deadline = (Get-Date).AddMinutes(20)
    $cancelRow = $null
    while ((Get-Date) -lt $deadline) {
        $cancelRow = Row $cancelId
        if ($cancelRow.stage -eq "report") { break }
        if ($cancelRow.status -in @("failed", "done", "cancelled")) { break }
        Start-Sleep -Seconds 3
    }
    if ($cancelRow.stage -ne "report") {
        Fail ("cancel video never reached the report: {0} {1} {2}" -f $cancelRow.status, $cancelRow.stage, $cancelRow.error_message)
    } else {
        Start-Sleep -Seconds 20
        $before = @(Descendants $backend.ProcessId | Where-Object { $_.CommandLine -notlike "*app-server*" })
        Say ("children before cancel: {0}" -f (($before | ForEach-Object { $_.Name }) -join ", "))
        $cancelAt = Get-Date
        Api POST "/api/items/$($created.id)/cancel" | Out-Null
        $gone = $false
        while (((Get-Date) - $cancelAt).TotalSeconds -lt 5) {
            $left = @(Descendants $backend.ProcessId | Where-Object { $_.CommandLine -notlike "*app-server*" })
            if ($left.Count -eq 0) { $gone = $true; break }
            Start-Sleep -Milliseconds 250
        }
        $seconds = ((Get-Date) - $cancelAt).TotalSeconds
        $status = (Row $cancelId).status
        Say ("after cancel: children gone={0} in {1:N1} s, status={2}" -f $gone, $seconds, $status)
        $notes += ("cancel: {0} children before, all gone in {1:N1} s, status {2}" -f $before.Count, $seconds, $status)
        if ($before.Count -eq 0) { $notes += "NOTE: no child process was running at the cancel" }
        if (-not $gone) { Fail ("children still running 5 s after cancel: {0}" -f (($left | ForEach-Object { $_.Name }) -join ", ")) }
        Start-Sleep -Seconds 3
        if ((Row $cancelId).status -ne "cancelled") { Fail "cancelled item is $((Row $cancelId).status)" }
    }

    Say "close the window as a user would"
    $app.Refresh()
    $app.CloseMainWindow() | Out-Null
    if (-not $app.WaitForExit(30000)) { Fail "the app did not close in 30 s"; Stop-Process -Id $app.Id -Force }
    Start-Sleep -Seconds 3
    $orphans = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$InstallDir*" })
    if ($orphans.Count -gt 0) {
        Fail ("left running after closing: {0}" -f (($orphans | ForEach-Object { "$($_.Name)/$($_.ProcessId)" }) -join ", "))
        $orphans | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    $app = $null

    Say "silent uninstall"
    Start-Process -FilePath "$InstallDir\uninstall.exe" -ArgumentList "/S" -Wait
    Start-Sleep -Seconds 5
    if (Test-Path "$InstallDir\Prometheus.exe") { Fail "uninstall left Prometheus.exe behind" }
    if (-not (Test-Path "$DataDir\index.json")) { Fail "uninstall removed the data dir" }
    Copy-Item -Recurse "$Shots" "$Results\shots"
    Utf8NoBom "$Results\notes.txt" (($notes + ($failures | ForEach-Object { "FAIL: $_" })) -join "`r`n")
}
catch {
    Fail ("stopped: {0}" -f $_.Exception.Message)
}
finally {
    if ($app -and -not $app.HasExited) { $app.CloseMainWindow() | Out-Null; Start-Sleep -Seconds 10 }
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$InstallDir*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Say "clean up the scratch install, data and cache; restore the app's own folders"
    Start-Sleep -Seconds 2
    foreach ($folder in $Folders) { if (Test-Path $folder) { Remove-Item -Recurse -Force -LiteralPath $folder } }
    $i = 0
    foreach ($folder in $Folders) {
        if (Test-Path "$Backup\folder$i") { Move-Item -LiteralPath "$Backup\folder$i" -Destination $folder }
        $i += 1
    }
    foreach ($leftover in @($InstallDir, $DataDir, "$Root\npm-cache")) {
        if (Test-Path $leftover) { Remove-Item -Recurse -Force -LiteralPath $leftover -ErrorAction SilentlyContinue }
    }
}

Say "notes:"
$notes | ForEach-Object { Say "  $_" }
if ($failures.Count -gt 0) {
    Say ("INSTALLED LIVE FAILED ({0})" -f $failures.Count)
    exit 1
}
Say "INSTALLED LIVE OK"
exit 0
