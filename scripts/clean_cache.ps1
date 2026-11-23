[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$prefix = $workspace.TrimEnd('\') + '\'
$cacheNames = @('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache')
$archive = Join-Path $workspace ('.local/archive/cache-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))

# Walk explicitly so junctions and symbolic links are never followed.
function Find-ProjectCache([string]$Directory) {
    foreach ($entry in Get-ChildItem -LiteralPath $Directory -Force) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        if (-not $entry.PSIsContainer) { continue }
        if ($entry.Name -in $cacheNames) {
            $entry
        } else {
            Find-ProjectCache $entry.FullName
        }
    }
}

function Assert-CacheTree([string]$Directory) {
    foreach ($entry in Get-ChildItem -LiteralPath $Directory -Force) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing to archive a cache containing a link: $($entry.FullName)"
        }
        if ($entry.PSIsContainer) { Assert-CacheTree $entry.FullName }
    }
}

$targets = @(
    foreach ($name in $cacheNames) {
        $candidate = Join-Path $workspace $name
        if (Test-Path -LiteralPath $candidate -PathType Container) {
            Get-Item -LiteralPath $candidate -Force
        }
    }
    foreach ($name in @('app', 'tests', 'scripts', 'migrations', 'deploy')) {
        $source = Get-Item -LiteralPath (Join-Path $workspace $name) -Force
        if ($source.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        Find-ProjectCache $source.FullName
    }
)

foreach ($target in $targets) {
    $resolved = (Resolve-Path -LiteralPath $target.FullName).Path
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
        $target.Name -notin $cacheNames -or
        ($target.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Refusing unsafe cache target: $resolved"
    }
    Assert-CacheTree $resolved
    $destination = [IO.Path]::GetFullPath((Join-Path $archive $resolved.Substring($prefix.Length)))
    if (-not $destination.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing archive outside workspace: $destination"
    }
    $ancestor = Split-Path -Parent $destination
    while ($ancestor -ne $workspace) {
        if (Test-Path -LiteralPath $ancestor) {
            $entry = Get-Item -LiteralPath $ancestor -Force
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing archive destination containing a link: $ancestor"
            }
        }
        $ancestor = Split-Path -Parent $ancestor
    }
    if ($PSCmdlet.ShouldProcess("$resolved -> $destination", 'Archive generated cache')) {
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force
        Move-Item -LiteralPath $resolved -Destination $destination
        Write-Output "Archived $resolved -> $destination"
    }
}
