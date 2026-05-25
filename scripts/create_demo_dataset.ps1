param(
    [string]$OutputDir = "",
    [int]$FileCount = 300
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputDir.Trim()) {
    $OutputDir = Join-Path $root "build\demo-scan-folder-300"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$patterns = @(
    @{ Name = "old-driver-installer"; Extension = ".msi"; Category = "installers"; MinSize = 49152; MaxSize = 573440; Step = 37117 },
    @{ Name = "setup-package"; Extension = ".pkg"; Category = "installers"; MinSize = 32768; MaxSize = 393216; Step = 22871 },
    @{ Name = "setup-archive"; Extension = ".zip"; Category = "archives"; MinSize = 24576; MaxSize = 430080; Step = 31991 },
    @{ Name = "project-snapshot"; Extension = ".7z"; Category = "archives"; MinSize = 36864; MaxSize = 524288; Step = 41333 },
    @{ Name = "browser-cache"; Extension = ".tmp"; Category = "cache"; MinSize = 2048; MaxSize = 24576; Step = 1543 },
    @{ Name = "thumbnail-cache"; Extension = ".cache"; Category = "cache"; MinSize = 3072; MaxSize = 49152; Step = 2333 },
    @{ Name = "application-log"; Extension = ".log"; Category = "logs"; MinSize = 3072; MaxSize = 81920; Step = 4231 },
    @{ Name = "trace-output"; Extension = ".trace"; Category = "logs"; MinSize = 4096; MaxSize = 98304; Step = 7193 },
    @{ Name = "backup-copy"; Extension = ".bak"; Category = "backups"; MinSize = 8192; MaxSize = 245760; Step = 19891 },
    @{ Name = "autosave-recovery"; Extension = ".old"; Category = "backups"; MinSize = 6144; MaxSize = 196608; Step = 13691 },
    @{ Name = "old-report-draft"; Extension = ".pdf"; Category = "documents"; MinSize = 12288; MaxSize = 147456; Step = 8761 },
    @{ Name = "meeting-notes"; Extension = ".docx"; Category = "documents"; MinSize = 8192; MaxSize = 131072; Step = 6967 },
    @{ Name = "budget-export"; Extension = ".xlsx"; Category = "spreadsheets"; MinSize = 10240; MaxSize = 122880; Step = 7741 },
    @{ Name = "presentation-copy"; Extension = ".pptx"; Category = "presentations"; MinSize = 20480; MaxSize = 262144; Step = 15427 },
    @{ Name = "screenshot-copy"; Extension = ".png"; Category = "images"; MinSize = 4096; MaxSize = 184320; Step = 11113 },
    @{ Name = "preview-photo"; Extension = ".jpg"; Category = "images"; MinSize = 6144; MaxSize = 204800; Step = 12973 },
    @{ Name = "sample-video-cache"; Extension = ".mp4"; Category = "media"; MinSize = 65536; MaxSize = 819200; Step = 57737 },
    @{ Name = "screen-recording-temp"; Extension = ".mov"; Category = "media"; MinSize = 49152; MaxSize = 734003; Step = 48991 },
    @{ Name = "sqlite-export"; Extension = ".db"; Category = "databases"; MinSize = 16384; MaxSize = 262144; Step = 17389 },
    @{ Name = "local-index"; Extension = ".sqlite"; Category = "databases"; MinSize = 20480; MaxSize = 294912; Step = 24631 },
    @{ Name = "table-export"; Extension = ".csv"; Category = "exports"; MinSize = 4096; MaxSize = 90112; Step = 5963 },
    @{ Name = "json-cache"; Extension = ".json"; Category = "exports"; MinSize = 3072; MaxSize = 65536; Step = 3889 }
)

$now = Get-Date
$created = 0
$extensionCounts = @{}

function Get-DemoSize([hashtable]$Pattern, [int]$Index) {
    $span = [Math]::Max(1, $Pattern.MaxSize - $Pattern.MinSize + 1)
    return [int]($Pattern.MinSize + (($Index * $Pattern.Step + $Pattern.Category.Length * 997) % $span))
}

function Write-DemoBytes([string]$Path, [int]$Size, [hashtable]$Pattern, [int]$Index) {
    $header = [System.Text.Encoding]::UTF8.GetBytes(
        (
            "SmartCleaner demo file`r`n" +
            "Index: $Index`r`n" +
            "Category: $($Pattern.Category)`r`n" +
            "Extension: $($Pattern.Extension)`r`n" +
            "Generated metadata-only sample for presentation scanning.`r`n"
        )
    )
    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Create,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $remaining = $Size
        $headerBytes = [Math]::Min($header.Length, $remaining)
        if ($headerBytes -gt 0) {
            $stream.Write($header, 0, $headerBytes)
            $remaining -= $headerBytes
        }

        $chunkSize = [Math]::Min(8192, [Math]::Max(1, $Size))
        $chunk = New-Object byte[] $chunkSize
        $seed = ($Index * 1103515245 + 12345) % 251
        for ($j = 0; $j -lt $chunk.Length; $j++) {
            $chunk[$j] = [byte](($seed + $j * 31 + $Pattern.Category.Length) % 251)
        }

        while ($remaining -gt 0) {
            $writeCount = [Math]::Min($chunk.Length, $remaining)
            $stream.Write($chunk, 0, $writeCount)
            $remaining -= $writeCount
        }
    }
    finally {
        $stream.Dispose()
    }
}

for ($i = 0; $i -lt $FileCount; $i++) {
    $pattern = $patterns[$i % $patterns.Count]
    $folder = Join-Path $OutputDir $pattern.Category
    New-Item -ItemType Directory -Force -Path $folder | Out-Null

    $fileName = "{0}-{1:D3}{2}" -f $pattern.Name, ($i + 1), $pattern.Extension
    $path = Join-Path $folder $fileName
    $size = Get-DemoSize -Pattern $pattern -Index ($i + 1)
    Write-DemoBytes -Path $path -Size $size -Pattern $pattern -Index ($i + 1)

    $modifiedAgeDays = 200 + (($i * 17) % 760)
    $modifiedDate = $now.AddDays(-$modifiedAgeDays).AddHours(-($i % 23)).AddMinutes(-(($i * 7) % 59))
    $createdDate = $modifiedDate.AddDays(-(1 + (($i * 11) % 120))).AddMinutes(-($i % 47))
    $accessAgeDays = 185 + (($i * 23) % 720)
    $accessDate = $now.AddDays(-$accessAgeDays).AddHours(-(($i * 5) % 21))
    if ($accessDate -lt $createdDate) {
        $accessDate = $modifiedDate.AddDays(1)
    }

    [System.IO.File]::SetCreationTime($path, $createdDate)
    [System.IO.File]::SetLastWriteTime($path, $modifiedDate)
    [System.IO.File]::SetLastAccessTime($path, $accessDate)
    $extensionCounts[$pattern.Extension] = 1 + [int]($extensionCounts[$pattern.Extension])
    $created += 1
}

$files = Get-ChildItem -LiteralPath $OutputDir -File -Recurse

[pscustomobject]@{
    OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
    FileCount = $created
    ActualFileCount = $files.Count
    DistinctExtensions = $extensionCounts.Count
    MinSizeBytes = ($files | Measure-Object -Property Length -Minimum).Minimum
    MaxSizeBytes = ($files | Measure-Object -Property Length -Maximum).Maximum
    OldestCreationTime = ($files | Sort-Object CreationTime | Select-Object -First 1).CreationTime.ToString("s")
    NewestCreationTime = ($files | Sort-Object CreationTime -Descending | Select-Object -First 1).CreationTime.ToString("s")
    OldestLastWriteTime = ($files | Sort-Object LastWriteTime | Select-Object -First 1).LastWriteTime.ToString("s")
    NewestLastWriteTime = ($files | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime.ToString("s")
    Hint = "Use this folder in SmartCleaner: choose 'Выбрать папку для демо'."
}
