param(
    [int]$Port = 8000,
    [int]$TimeoutSeconds = 120,
    [string]$Python = "",
    [switch]$SkipInstallerBuild
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $root "server\docker-compose.yml"
$envFile = Join-Path $root "server\.env"
$runtimeDir = Join-Path $root "build\smartcleaner-public-tunnel"
$cloudflaredPath = Join-Path $runtimeDir "cloudflared.exe"
$stdoutPath = Join-Path $runtimeDir "cloudflared.out.log"
$stderrPath = Join-Path $runtimeDir "cloudflared.err.log"
$pidPath = Join-Path $runtimeDir "cloudflared.pid"
$localBackendUrl = "http://127.0.0.1:$Port"

function Set-EnvFileValue([string]$Path, [string]$Name, [string]$Value) {
    $lines = @()
    if (Test-Path -LiteralPath $Path) {
        $lines = [System.IO.File]::ReadAllLines($Path)
    }

    $escapedName = [regex]::Escape($Name)
    $updated = $false
    $newLines = foreach ($line in $lines) {
        if ($line -match "^\s*$escapedName\s*=") {
            $updated = $true
            "$Name=$Value"
        } else {
            $line
        }
    }

    if (-not $updated) {
        $newLines += "$Name=$Value"
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($Path, [string[]]$newLines, $utf8NoBom)
}

function Import-EnvFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Env file is missing: $Path"
    }

    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or $trimmed -notmatch "^\s*([^=]+?)\s*=(.*)$") {
            continue
        }
        $name = $matches[1].Trim()
        $value = $matches[2].Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Test-BackendHealth([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Wait-BackendHealth([string]$Url, [int]$TimeoutSeconds) {
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        if (Test-BackendHealth -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-CloudflaredCommand {
    $command = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
    if (-not $command) {
        $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    }
    if ($command) {
        return $command.Source
    }

    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    if (-not (Test-Path -LiteralPath $cloudflaredPath)) {
        $downloadUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $cloudflaredPath -UseBasicParsing
    }
    return $cloudflaredPath
}

function Stop-ExistingCloudflared {
    if (-not (Test-Path -LiteralPath $pidPath)) {
        return
    }

    $pidText = [System.IO.File]::ReadAllText($pidPath).Trim()
    if ($pidText -match "^\d+$") {
        $process = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $process.Id -Force
        }
    }
    Remove-Item -LiteralPath $pidPath -ErrorAction SilentlyContinue
}

function Read-TextFileOrEmpty([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }

    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite
    )
    try {
        $reader = New-Object System.IO.StreamReader $stream
        try {
            return $reader.ReadToEnd()
        }
        finally {
            $reader.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
}

function Wait-CloudflareTunnelUrl([System.Diagnostics.Process]$Process, [int]$TimeoutSeconds) {
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        $text = @(
            Read-TextFileOrEmpty -Path $stdoutPath
            Read-TextFileOrEmpty -Path $stderrPath
        ) -join "`n"
        $match = [regex]::Match($text, "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($match.Success) {
            return $match.Value.TrimEnd("/")
        }
        if ($Process.HasExited) {
            throw "cloudflared exited before publishing a trycloudflare.com URL. Output:`n$text"
        }
        Start-Sleep -Seconds 1
    }
    throw "cloudflared did not publish a trycloudflare.com URL after $TimeoutSeconds seconds."
}

function Write-ClientBackendConfig([string]$PublicUrl, [string]$LocalUrl) {
    $localAppData = [Environment]::GetEnvironmentVariable("LOCALAPPDATA")
    if (-not $localAppData) {
        throw "LOCALAPPDATA is not available; cannot write SmartCleaner backend config"
    }

    $configDir = Join-Path $localAppData "SmartCleaner"
    New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    $configPath = Join-Path $configDir "backend_url.txt"
    $entries = @(
        $PublicUrl.Trim().TrimEnd("/")
        $LocalUrl.Trim().TrimEnd("/")
    ) | Select-Object -Unique
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($configPath, [string[]]$entries, $utf8NoBom)
    return $configPath
}

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

Set-EnvFileValue -Path $envFile -Name "BACKEND_HOST_IP" -Value "127.0.0.1"
Import-EnvFile -Path $envFile

Push-Location $root
try {
    & docker compose -f $composeFile --env-file $envFile up -d --build
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed"
    }
}
finally {
    Pop-Location
}

if (-not (Wait-BackendHealth -Url "$localBackendUrl/health" -TimeoutSeconds $TimeoutSeconds)) {
    throw "Backend is not healthy at $localBackendUrl/health after $TimeoutSeconds seconds."
}

$cloudflared = Get-CloudflaredCommand
Stop-ExistingCloudflared
Remove-Item -LiteralPath $stdoutPath, $stderrPath -ErrorAction SilentlyContinue

$process = Start-Process `
    -FilePath $cloudflared `
    -ArgumentList @("tunnel", "--url", $localBackendUrl, "--no-autoupdate") `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath

[System.IO.File]::WriteAllText($pidPath, [string]$process.Id)
$publicUrl = Wait-CloudflareTunnelUrl -Process $process -TimeoutSeconds $TimeoutSeconds
$configPath = Write-ClientBackendConfig -PublicUrl $publicUrl -LocalUrl $localBackendUrl

$installer = ""
if (-not $SkipInstallerBuild) {
    $buildScript = Join-Path $PSScriptRoot "build_client_installer.ps1"
    $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $buildScript, "-BackendUrl", $publicUrl)
    if ($Python.Trim()) {
        $args += @("-Python", $Python.Trim())
    }
    & powershell @args
    if ($LASTEXITCODE -ne 0) {
        throw "Client installer build failed"
    }
    $installer = Join-Path $root "deployment\client-installer\output\SmartCleanerSetup.exe"
}

[pscustomobject]@{
    PublicUrl = $publicUrl
    HealthUrl = "$publicUrl/health"
    LocalBackendUrl = $localBackendUrl
    CloudflaredPid = $process.Id
    ClientConfigPath = $configPath
    Installer = $installer
    StopTunnelCommand = "Stop-Process -Id $($process.Id) -Force"
    StopDockerCommand = "docker compose -f server\docker-compose.yml --env-file server\.env down"
}
