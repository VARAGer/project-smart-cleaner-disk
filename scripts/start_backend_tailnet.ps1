param(
    [int]$Port = 8000,
    [int]$TimeoutSeconds = 90,
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $root "server\docker-compose.yml"
if (-not $EnvFile.Trim()) {
    $EnvFile = Join-Path $root "server\.env"
}

function Get-TailscaleCommand {
    $command = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if (-not $command) {
        $command = Get-Command tailscale -ErrorAction SilentlyContinue
    }
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "$env:ProgramFiles\Tailscale\tailscale.exe",
        "${env:ProgramFiles(x86)}\Tailscale\tailscale.exe",
        "$env:LOCALAPPDATA\Tailscale\tailscale.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "tailscale.exe was not found. Install Tailscale and sign in on this Windows host."
}

function Get-TailscaleIp([string]$Tailscale) {
    $ipText = & $Tailscale ip -4 2>$null | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "Tailscale is not connected. Sign in to Tailscale, then run this script again."
    }

    $match = [regex]::Match($ipText, "\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
    if (-not $match.Success) {
        throw "Tailscale did not report a 100.x IPv4 address. Check `tailscale status`."
    }
    return $match.Value
}

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

function Write-ClientBackendConfig([string]$BackendUrl, [int]$Port) {
    $localAppData = [Environment]::GetEnvironmentVariable("LOCALAPPDATA")
    if (-not $localAppData) {
        throw "LOCALAPPDATA is not available; cannot write SmartCleaner backend config"
    }

    $configDir = Join-Path $localAppData "SmartCleaner"
    New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    $configPath = Join-Path $configDir "backend_url.txt"
    $entries = @(
        $BackendUrl.Trim().TrimEnd("/")
        "http://localhost:$Port"
    ) | Select-Object -Unique
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($configPath, [string[]]$entries, $utf8NoBom)
    return $configPath
}

$tailscale = Get-TailscaleCommand
$tailscaleIp = Get-TailscaleIp -Tailscale $tailscale
$backendUrl = "http://${tailscaleIp}:$Port"

Set-EnvFileValue -Path $EnvFile -Name "BACKEND_HOST_IP" -Value $tailscaleIp
Import-EnvFile -Path $EnvFile

Push-Location $root
try {
    & docker compose -f $composeFile --env-file $EnvFile up -d --build
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed"
    }
}
finally {
    Pop-Location
}

if (-not (Wait-BackendHealth -Url "$backendUrl/health" -TimeoutSeconds $TimeoutSeconds)) {
    throw "Backend is not healthy at $backendUrl/health after $TimeoutSeconds seconds."
}

$configPath = Write-ClientBackendConfig -BackendUrl $backendUrl -Port $Port

[pscustomobject]@{
    BackendUrl = $backendUrl
    HealthUrl = "$backendUrl/health"
    TailscaleIp = $tailscaleIp
    ClientConfigPath = $configPath
    LaptopRequirement = "Install Tailscale on the laptop and sign in to the same tailnet."
}
