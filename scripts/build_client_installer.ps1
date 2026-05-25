param(
    [string]$BackendUrl = "",
    [string]$Python = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$pyInstallerSpec = Join-Path $root "deployment\client-installer\SmartCleaner.pyinstaller.spec"
$innoScript = Join-Path $root "deployment\client-installer\SmartCleaner.iss"
$buildDir = Join-Path $root "build\smartcleaner-client"
$pythonCacheDir = Join-Path $root "build\python-cache"
$distDir = Join-Path $root "dist\SmartCleaner"
$installerOutputDir = Join-Path $root "deployment\client-installer\output"

function Assert-UnderRoot([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside workspace: $full"
    }
}

function Test-PythonUsable([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    & $Path -c "import sys; print(sys.executable)" *> $null
    return $LASTEXITCODE -eq 0
}

function Resolve-Python {
    $candidates = @()
    if ($Python.Trim()) {
        $candidates += $Python.Trim()
    }
    if ($env:SMARTCLEANER_PYTHON) {
        $candidates += $env:SMARTCLEANER_PYTHON.Trim()
    }
    $candidates += (Join-Path $root ".venv\Scripts\python.exe")

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-PythonUsable $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd -and (Test-PythonUsable $pythonCmd.Source)) {
        return $pythonCmd.Source
    }

    throw (
        "Usable Python interpreter was not found. Create a venv and install " +
        "client requirements, or pass -Python C:\path\to\python.exe, or set " +
        "SMARTCLEANER_PYTHON."
    )
}

function Find-InnoCompiler {
    $candidates = @(
        "iscc",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }
    return $null
}

function Get-TailscaleCommand {
    $tailscale = (Get-Command tailscale.exe -ErrorAction SilentlyContinue).Source
    if (-not $tailscale) {
        $tailscale = (Get-Command tailscale -ErrorAction SilentlyContinue).Source
    }
    if (-not $tailscale) {
        $candidates = @(
            "$env:ProgramFiles\Tailscale\tailscale.exe",
            "${env:ProgramFiles(x86)}\Tailscale\tailscale.exe",
            "$env:LOCALAPPDATA\Tailscale\tailscale.exe"
        )
        foreach ($candidate in $candidates) {
            if (Test-Path -LiteralPath $candidate) {
                $tailscale = (Resolve-Path -LiteralPath $candidate).Path
                break
            }
        }
    }
    if (-not $tailscale) {
        return ""
    }
    return $tailscale
}

function Get-RunningTailscaleFunnelUrl {
    $tailscale = Get-TailscaleCommand
    if (-not $tailscale) {
        return ""
    }

    $statusText = & $tailscale funnel status 2>$null | Out-String
    if ($LASTEXITCODE -ne 0) {
        return ""
    }
    $match = [regex]::Match($statusText, "https://[A-Za-z0-9.-]+\.ts\.net")
    if ($match.Success) {
        return $match.Value.TrimEnd("/")
    }
    return ""
}

function Get-TailscaleBackendUrl([int]$Port) {
    $tailscale = Get-TailscaleCommand
    if (-not $tailscale) {
        return ""
    }

    $ipText = & $tailscale ip -4 2>$null | Out-String
    if ($LASTEXITCODE -ne 0) {
        return ""
    }
    $match = [regex]::Match($ipText, "\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
    if ($match.Success) {
        return "http://$($match.Value):$Port"
    }
    return ""
}

$resolvedPython = Resolve-Python

Assert-UnderRoot $buildDir
Assert-UnderRoot $pythonCacheDir
Assert-UnderRoot $distDir
Assert-UnderRoot $installerOutputDir

$env:PYTHONPYCACHEPREFIX = $pythonCacheDir
New-Item -ItemType Directory -Force -Path $pythonCacheDir | Out-Null

if (-not $SkipTests) {
    & $resolvedPython -m pytest (Join-Path $root "client\tests")
    if ($LASTEXITCODE -ne 0) { throw "Client tests failed" }
    & $resolvedPython -m compileall -q (Join-Path $root "client")
    if ($LASTEXITCODE -ne 0) { throw "Client compileall failed" }
}

if (Test-Path -LiteralPath $buildDir) {
    Remove-Item -LiteralPath $buildDir -Recurse -Force
}
if (Test-Path -LiteralPath $distDir) {
    Remove-Item -LiteralPath $distDir -Recurse -Force
}

Push-Location $root
try {
    & $resolvedPython -m PyInstaller `
        --noconfirm `
        --clean `
        --workpath $buildDir `
        --distpath (Join-Path $root "dist") `
        $pyInstallerSpec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
}
finally {
    Pop-Location
}

$exePath = Join-Path $distDir "SmartCleaner.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "PyInstaller output missing: $exePath"
}

$secretHits = Get-ChildItem -LiteralPath $distDir -Recurse -File |
    Where-Object { $_.Name -match '(^\.env$|\.db$|\.sqlite$|\.sqlite3$)' }
if ($secretHits) {
    $names = ($secretHits | ForEach-Object { $_.FullName }) -join ", "
    throw "Packaged artifact contains forbidden runtime/secrets files: $names"
}

$iscc = Find-InnoCompiler
if (-not $iscc) {
    Write-Warning "Inno Setup compiler was not found; PyInstaller app is available at $distDir"
    return
}

New-Item -ItemType Directory -Force -Path $installerOutputDir | Out-Null
$isccArgs = @($innoScript)
$effectiveBackendUrl = $BackendUrl.Trim()
if (-not $effectiveBackendUrl) {
    $effectiveBackendUrl = Get-RunningTailscaleFunnelUrl
}
if (-not $effectiveBackendUrl) {
    $effectiveBackendUrl = Get-TailscaleBackendUrl -Port 8000
}

if ($effectiveBackendUrl.Trim()) {
    $configDir = Join-Path $root "build\smartcleaner-installer-config"
    Assert-UnderRoot $configDir
    New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    $backendUrlFile = Join-Path $configDir "backend_url.txt"
    $backendUrls = @(
        $effectiveBackendUrl.Trim().TrimEnd("/")
        "http://localhost:8000"
    ) | Select-Object -Unique
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($backendUrlFile, [string[]]$backendUrls, $utf8NoBom)
    $isccArgs = @("/DBackendUrlFile=$backendUrlFile") + $isccArgs
}

Push-Location (Join-Path $root "deployment\client-installer")
try {
    & $iscc @isccArgs
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }
}
finally {
    Pop-Location
}

$installer = Join-Path $installerOutputDir "SmartCleanerSetup.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "Installer output missing: $installer"
}

Write-Output "PyInstaller app: $distDir"
Write-Output "Installer: $installer"
