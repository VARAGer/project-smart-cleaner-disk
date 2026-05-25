param(
    [Parameter(Mandatory = $true)]
    [string]$BackendUrl,
    [string]$Python = "",
    [string]$Username = "",
    [string]$Password = "InstallerSmokePassword!42"
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
        "Usable Python interpreter was not found. Create a venv and install " +
        "client requirements, or pass -Python C:\path\to\python.exe, or set " +
        "SMARTCLEANER_PYTHON."
    )
}

$python = Resolve-Python

$env:PYTHONPATH = $root
$pythonCacheDir = Join-Path $root "build\python-cache"
New-Item -ItemType Directory -Force -Path $pythonCacheDir | Out-Null
$env:PYTHONPYCACHEPREFIX = $pythonCacheDir
$env:SMARTCLEANER_BACKEND = $BackendUrl.Trim().TrimEnd("/")
if ($Username.Trim()) {
    $env:SMARTCLEANER_TEST_USER = $Username.Trim()
} else {
    Remove-Item Env:\SMARTCLEANER_TEST_USER -ErrorAction SilentlyContinue
}
$env:SMARTCLEANER_TEST_PASSWORD = $Password

$smoke = @'
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

from client.api_client.client import ApiClientError, SmartCleanerApiClient


FALLBACK_REASONS = {
    "Сервис анализа временно недоступен",
    "Не удалось классифицировать",
}


def main() -> int:
    base_url = os.environ["SMARTCLEANER_BACKEND"].rstrip("/")
    username = os.environ.get("SMARTCLEANER_TEST_USER") or (
        f"smoke_{uuid.uuid4().hex[:12]}"
    )
    password = os.environ["SMARTCLEANER_TEST_PASSWORD"]

    probe_file = {
        "file_id": "smoke_setup_msi",
        "filename": "old-driver-installer.msi",
        "extension": ".msi",
        "size_bytes": 248_000_000,
        "modified_at": "2022-01-15T10:30:00Z",
        "accessed_at": "2022-01-16T10:30:00Z",
        "parent_dir": "Downloads",
    }

    with SmartCleanerApiClient(base_url=base_url, timeout_seconds=120) as client:
        try:
            session = client.register(username, password)
            auth_mode = "register"
        except ApiClientError as exc:
            if exc.status_code != 409:
                raise
            session = client.login(username, password)
            auth_mode = "login"

        result = client.analyze_files(
            f"installer-smoke-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            [probe_file],
        )

    if len(result.classifications) != 1:
        raise AssertionError(f"expected one classification, got {len(result.classifications)}")

    item = result.classifications[0]
    if item["file_id"] != probe_file["file_id"]:
        raise AssertionError("backend returned classification for the wrong file_id")
    if item.get("reason") in FALLBACK_REASONS:
        raise AssertionError(f"Gemini fallback response was treated as success: {item!r}")
    if float(item.get("confidence", 0)) <= 0.5:
        raise AssertionError(f"low-confidence analysis result is not acceptable for smoke test: {item!r}")

    print(
        "remote-backend-smoke-ok "
        f"auth={auth_mode} category={item.get('category')} confidence={item.get('confidence')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@

Push-Location $root
try {
    $smoke | & $python -
    if ($LASTEXITCODE -ne 0) { throw "Remote backend smoke test failed" }
}
finally {
    Pop-Location
}
