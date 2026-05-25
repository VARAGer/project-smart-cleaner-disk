param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

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
        "Usable Python interpreter was not found. Create .venv and install " +
        "client requirements, or pass -Python C:\path\to\python.exe, or set " +
        "SMARTCLEANER_PYTHON."
    )
}

$resolvedPython = Resolve-Python

& $resolvedPython -c "import PyQt6" *> $null
if ($LASTEXITCODE -ne 0) {
    throw (
        "PyQt6 is not installed for $resolvedPython. Run: " +
        "$resolvedPython -m pip install -r client\requirements.txt pytest"
    )
}

$env:QT_QPA_PLATFORM = "offscreen"
& $resolvedPython -m pytest (Join-Path $root "client\tests")
if ($LASTEXITCODE -ne 0) {
    throw "Client tests failed"
}
