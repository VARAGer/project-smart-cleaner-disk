param(
    [int]$Port = 8000,
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$healthUrl = "http://127.0.0.1:$Port/health"

function Write-ClientBackendConfig([string]$PublicUrl, [int]$Port) {
    $localAppData = [Environment]::GetEnvironmentVariable("LOCALAPPDATA")
    if (-not $localAppData) {
        throw "LOCALAPPDATA is not available; cannot write SmartCleaner backend config"
    }

    $configDir = Join-Path $localAppData "SmartCleaner"
    New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    $configPath = Join-Path $configDir "backend_url.txt"
    $entries = @(
        $PublicUrl.Trim().TrimEnd("/")
        "http://localhost:$Port"
    ) | Select-Object -Unique
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($configPath, [string[]]$entries, $utf8NoBom)
    return $configPath
}

function Test-BackendHealth([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
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

function Get-RunningTailscaleFunnelUrl([string]$Tailscale) {
    $statusText = & $Tailscale funnel status 2>$null | Out-String
    if ($LASTEXITCODE -ne 0) {
        return ""
    }
    $match = [regex]::Match($statusText, "https://[A-Za-z0-9.-]+\.ts\.net")
    if ($match.Success) {
        return $match.Value.TrimEnd("/")
    }
    return ""
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

function Stop-ProcessIfRunning([System.Diagnostics.Process]$Process) {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force
    }
}

function Get-TailscaleFunnelEnableUrl([string]$Text) {
    $match = [regex]::Match($Text, "https://login\.tailscale\.com/f/funnel\?node=\S+")
    if ($match.Success) {
        return $match.Value.Trim()
    }
    return ""
}

function Start-TailscaleFunnel([string]$Tailscale, [int]$Port, [int]$TimeoutSeconds) {
    $tempBase = Join-Path ([System.IO.Path]::GetTempPath()) ("smartcleaner-tailscale-funnel-{0}" -f [guid]::NewGuid().ToString("N"))
    $stdoutPath = "$tempBase.out"
    $stderrPath = "$tempBase.err"
    $process = Start-Process `
        -FilePath $Tailscale `
        -ArgumentList @("funnel", "--bg", "--yes", "$Port") `
        -NoNewWindow `
        -PassThru `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath

    try {
        for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
            Start-Sleep -Seconds 1

            $output = @(
                Read-TextFileOrEmpty -Path $stdoutPath
                Read-TextFileOrEmpty -Path $stderrPath
            ) -join "`n"
            $enableUrl = Get-TailscaleFunnelEnableUrl -Text $output
            if ($output -match "Funnel is not enabled" -or $enableUrl) {
                Stop-ProcessIfRunning -Process $process
                if ($enableUrl) {
                    throw "Tailscale Funnel is not enabled for this tailnet. Open $enableUrl, enable Funnel, then run this script again."
                }
                throw "Tailscale Funnel is not enabled for this tailnet. Enable MagicDNS, HTTPS certificates, and Funnel in the Tailscale admin console, then run this script again."
            }

            $publicUrl = Get-RunningTailscaleFunnelUrl -Tailscale $Tailscale
            if ($publicUrl) {
                return $publicUrl
            }

            if ($process.HasExited -and $process.ExitCode -ne 0) {
                throw "tailscale funnel failed with exit code $($process.ExitCode). Output:`n$output"
            }
        }

        $finalOutput = @(
            Read-TextFileOrEmpty -Path $stdoutPath
            Read-TextFileOrEmpty -Path $stderrPath
        ) -join "`n"
        Stop-ProcessIfRunning -Process $process
        if ($finalOutput.Trim()) {
            throw "tailscale funnel did not report a public URL after $TimeoutSeconds seconds. Last output:`n$finalOutput"
        }
        throw "tailscale funnel did not report a public URL after $TimeoutSeconds seconds."
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    }
}

function Wait-ForTailscaleFunnelUrl([string]$Tailscale, [int]$TimeoutSeconds) {
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        $url = Get-RunningTailscaleFunnelUrl -Tailscale $Tailscale
        if ($url) {
            return $url
        }
        Start-Sleep -Seconds 1
    }
    return ""
}

if (-not (Test-BackendHealth -Url $healthUrl)) {
    throw "Backend is not healthy at $healthUrl. Run Docker first: docker compose -f server/docker-compose.yml up -d --build"
}

$tailscale = Get-TailscaleCommand

$publicUrl = Get-RunningTailscaleFunnelUrl -Tailscale $tailscale
if (-not $publicUrl) {
    $publicUrl = Start-TailscaleFunnel -Tailscale $tailscale -Port $Port -TimeoutSeconds $TimeoutSeconds
}

if (-not $publicUrl) {
    throw "tailscale funnel status did not report a https://*.ts.net URL after $TimeoutSeconds seconds."
}

$configPath = Write-ClientBackendConfig -PublicUrl $publicUrl -Port $Port

[pscustomobject]@{
    PublicUrl = $publicUrl
    LocalTarget = "http://127.0.0.1:$Port"
    HealthUrl = $healthUrl
    ClientConfigPath = $configPath
    StopCommand = "tailscale funnel reset"
    ResetCommand = "tailscale funnel reset"
}
