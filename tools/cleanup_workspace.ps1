param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$workspaceRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent)).TrimEnd('\')
$releaseRoot = Join-Path $workspaceRoot 'Releases/2026-11-12-automation'
$retiredPaths = @(
    'Automation/gamingshorts_automation_v1',
    'Automation/gamingshorts_automation_v1.zip',
    'Automation/gamingshorts_backup_20261111-200511-640128',
    'Automation/gamingshorts_spoiler_backup_20261111-214135-902521',
    'Automation/gamingshorts_v2/Backups',
    'Automation/gamingshorts_v2/config.backup-20261111-193736-062046.json',
    'Automation/gamingshorts_v2/UPGRADE_2_1.md',
    'Shorts_Queue', 'Shorts_Queue.zip', 'Shorts_Renderer', 'Shorts_Renderer.zip',
    'Cairn_Ubuntu_Toolkit', 'Cairn_Ubuntu_Toolkit.zip', 'Upgrades',
    'inspect_recording_gamingshorts.py'
)

function Get-CheckedPath([string]$relative) {
    $resolved = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $relative))
    if (-not $resolved.StartsWith($workspaceRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes workspace: $relative"
    }
    $cursor = $resolved
    while ($cursor -and $cursor -ne $workspaceRoot) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing reparse point: $cursor"
            }
        }
        $cursor = Split-Path $cursor -Parent
    }
    return $resolved
}

$files = @()
$directories = @()
foreach ($relative in $retiredPaths) {
    $path = Get-CheckedPath $relative
    if (-not (Test-Path -LiteralPath $path)) { continue }
    $item = Get-Item -LiteralPath $path -Force
    if ($item.PSIsContainer) {
        $children = @(Get-ChildItem -LiteralPath $path -Recurse -Force)
        if (@($children | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
            throw "Refusing linked content below $path"
        }
        $files += @($children | Where-Object { -not $_.PSIsContainer })
        $directories += @($children | Where-Object PSIsContainer) + $item
    } else { $files += $item }
}

$planPath = Join-Path $releaseRoot 'duplicate-plan.json'
$plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
Write-Output "Retire $($files.Count) obsolete files into a verified ZIP; delete $($plan.duplicates.Count) duplicate split fragments."
if (-not $Apply) { Write-Output 'Dry run. Use -Apply to execute this exact scoped cleanup.'; exit 0 }

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archivePath = Join-Path $releaseRoot 'retired-tools.zip'
$archiveManifest = @()
if ($files.Count) {
    $archive = [IO.Compression.ZipFile]::Open($archivePath, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in $files) {
            $relative = $file.FullName.Substring($workspaceRoot.Length + 1).Replace('\', '/')
            $sha = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, $relative, [IO.Compression.CompressionLevel]::Fastest) | Out-Null
            $archiveManifest += [PSCustomObject]@{path=$relative; bytes=$file.Length; sha256=$sha}
        }
    } finally { $archive.Dispose() }
    $archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        foreach ($item in $archiveManifest) {
            $entry = $archive.GetEntry($item.path)
            if (-not $entry -or $entry.Length -ne $item.bytes) { throw "Archive entry missing: $($item.path)" }
            $stream = $entry.Open()
            $hasher = [Security.Cryptography.SHA256]::Create()
            try { $sha = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
            finally { $stream.Dispose(); $hasher.Dispose() }
            if ($sha -ne $item.sha256) { throw "Archive checksum mismatch: $($item.path)" }
        }
    } finally { $archive.Dispose() }
    $archiveManifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $releaseRoot 'retired-manifest.json') -Encoding UTF8
    # Recheck every source before removing any loose copy. Keep the verified ZIP.
    foreach ($item in $archiveManifest) {
        $path = Get-CheckedPath $item.path
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) {
            throw "Retired file changed during archiving: $path"
        }
    }
    foreach ($item in $archiveManifest) { Remove-Item -LiteralPath (Get-CheckedPath $item.path) -Force }
    foreach ($directory in ($directories | Sort-Object { $_.FullName.Length } -Descending)) {
        $path = Get-CheckedPath ($directory.FullName.Substring($workspaceRoot.Length + 1))
        if (@(Get-ChildItem -LiteralPath $path -Force).Count -eq 0) { Remove-Item -LiteralPath $path -Force }
    }
}

$removed = @()
foreach ($item in $plan.duplicates) {
    # Only failed split fragments may be permanently deleted; never originals/outputs.
    if ($item.delete -notmatch '^(_Processing|SplitRetry)/.+\.mp4$' -or
        $item.keep -notmatch '^(_Processing|SplitRetry)/.+\.mp4$') { throw 'Invalid duplicate scope' }
    $target = Get-CheckedPath $item.delete
    $retained = Get-CheckedPath $item.keep
    if ($target -eq $retained) { throw 'Duplicate points to itself' }
    if (-not (Test-Path -LiteralPath $target)) { continue }
    foreach ($path in @($target, $retained)) {
        if ((Get-Item -LiteralPath $path).Length -ne $item.bytes -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) {
            throw "Duplicate changed since audit: $path"
        }
    }
    Remove-Item -LiteralPath $target
    $removed += $item
    # Persist evidence after every deletion so interrupted cleanup remains auditable.
    @($removed) | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $releaseRoot 'removed-duplicates.json') -Encoding UTF8
}
Write-Output "Archived $($archiveManifest.Count) obsolete files; removed $($removed.Count) verified duplicate fragments."
