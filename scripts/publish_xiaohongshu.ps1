[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PackagePath,
    [Parameter(Mandatory = $true)][string]$StagingRoot,
    [Parameter(Mandatory = $true)][string]$SauHome,
    [Parameter(Mandatory = $true)][string]$Account
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$SauHome = [Environment]::ExpandEnvironmentVariables($SauHome)

function Assert-RegularNoReparseFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -or (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw "Required package file is not a regular non-reparse file: $Path"
    }
    return $item
}

function Add-HashField {
    param(
        [Parameter(Mandatory = $true)][Security.Cryptography.HashAlgorithm]$Hasher,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][byte[]]$Value
    )
    $labelBytes = [Text.Encoding]::UTF8.GetBytes($Label)
    $labelLength = [BitConverter]::GetBytes([Int64]$labelBytes.Length)
    $valueLength = [BitConverter]::GetBytes([Int64]$Value.Length)
    if ([BitConverter]::IsLittleEndian) {
        [Array]::Reverse($labelLength)
        [Array]::Reverse($valueLength)
    }
    [void]$Hasher.TransformBlock($labelLength, 0, $labelLength.Length, $labelLength, 0)
    [void]$Hasher.TransformBlock($labelBytes, 0, $labelBytes.Length, $labelBytes, 0)
    [void]$Hasher.TransformBlock($valueLength, 0, $valueLength.Length, $valueLength, 0)
    [void]$Hasher.TransformBlock($Value, 0, $Value.Length, $Value, 0)
}

function Get-PackageApprovalHash {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        Add-HashField -Hasher $hasher -Label 'format' -Value ([Text.Encoding]::UTF8.GetBytes('personal-content-approval-v1'))
        Add-HashField -Hasher $hasher -Label 'title' -Value ([Text.Encoding]::UTF8.GetBytes([string]$Manifest.title))
        Add-HashField -Hasher $hasher -Label 'body' -Value ([Text.Encoding]::UTF8.GetBytes([string]$Manifest.body))
        $tagIndex = 0
        foreach ($tag in @($Manifest.tags)) {
            Add-HashField -Hasher $hasher -Label "tag:$tagIndex" -Value ([Text.Encoding]::UTF8.GetBytes([string]$tag))
            $tagIndex++
        }
        $imageIndex = 0
        foreach ($image in @($Manifest.images)) {
            $imagePath = Join-Path $Path (([string]$image.package_path).Replace('/', '\'))
            Add-HashField -Hasher $hasher -Label "image-path:$imageIndex" -Value ([Text.Encoding]::UTF8.GetBytes([string]$image.source_path))
            Add-HashField -Hasher $hasher -Label "image-bytes:$imageIndex" -Value ([IO.File]::ReadAllBytes($imagePath))
            $imageIndex++
        }
        [void]$hasher.TransformFinalBlock([byte[]]::new(0), 0, 0)
        return ([BitConverter]::ToString($hasher.Hash)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $hasher.Dispose()
    }
}

function Test-StagedPackage {
    param([Parameter(Mandatory = $true)][string]$Path)
    $packageItem = Get-Item -LiteralPath $Path -Force
    if (-not $packageItem.PSIsContainer -or (($packageItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw "Staged package directory is unsafe: $Path"
    }
    $manifestPath = Join-Path $Path 'manifest.json'
    [void](Assert-RegularNoReparseFile -Path $manifestPath)
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $manifestKeys = @($manifest.PSObject.Properties.Name | Sort-Object)
    $expectedManifestKeys = @('approval_hash', 'body', 'images', 'schema_version', 'tags', 'title')
    if (@(Compare-Object $manifestKeys $expectedManifestKeys).Count -ne 0) {
        throw 'Staged manifest keys are invalid.'
    }
    if ($manifest.schema_version -ne 1 -or $manifest.approval_hash -notmatch '^[0-9a-f]{64}$') {
        throw 'Staged manifest format is invalid.'
    }
    if ((Split-Path -Leaf $Path) -cne [string]$manifest.approval_hash) {
        throw 'Staged directory does not use the full approval hash.'
    }
    $packageRoot = [IO.Path]::GetFullPath($Path).TrimEnd('\') + '\'
    $expectedFiles = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    [void]$expectedFiles.Add('manifest.json')
    foreach ($image in @($manifest.images)) {
        $imageKeys = @($image.PSObject.Properties.Name | Sort-Object)
        $expectedImageKeys = @('package_path', 'sha256', 'size', 'source_path')
        if (@(Compare-Object $imageKeys $expectedImageKeys).Count -ne 0) {
            throw 'Staged manifest image keys are invalid.'
        }
        $sourceIdentity = ([string]$image.source_path).Replace('\', '/')
        $sourceParts = @($sourceIdentity.Split('/'))
        if ($sourceIdentity -notmatch '^images/.+' -or $sourceParts -contains '.' -or $sourceParts -contains '..') {
            throw "Unsafe staged source image identity: $sourceIdentity"
        }
        if ([string]$image.sha256 -notmatch '^[0-9a-f]{64}$' -or [long]$image.size -lt 0) {
            throw 'Staged image metadata is invalid.'
        }
        $relative = ([string]$image.package_path).Replace('/', '\')
        if ($relative -notmatch '^images\\[0-9]{4}\.[A-Za-z0-9]+$') {
            throw "Unsafe staged image path: $relative"
        }
        $imagePath = [IO.Path]::GetFullPath((Join-Path $Path $relative))
        if (-not $imagePath.StartsWith($packageRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Staged image escapes package: $relative"
        }
        $imagesDirectory = Get-Item -LiteralPath (Split-Path -Parent $imagePath) -Force
        if (-not $imagesDirectory.PSIsContainer -or (($imagesDirectory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "Staged image has an unsafe intermediate directory: $relative"
        }
        $file = Assert-RegularNoReparseFile -Path $imagePath
        $actualHash = (Get-FileHash -LiteralPath $imagePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -cne [string]$image.sha256 -or $file.Length -ne [long]$image.size) {
            throw "Staged image digest mismatch: $relative"
        }
        [void]$expectedFiles.Add($relative)
    }
    $actualFiles = Get-ChildItem -LiteralPath $Path -File -Recurse -Force
    foreach ($file in $actualFiles) {
        if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Staged package contains a reparse point: $($file.FullName)"
        }
        $relative = $file.FullName.Substring($packageRoot.Length)
        if (-not $expectedFiles.Contains($relative)) {
            throw "Staged package contains an unexpected file: $relative"
        }
    }
    if ($actualFiles.Count -ne $expectedFiles.Count) {
        throw 'Staged package is missing required files.'
    }
    $actualDirectories = @(Get-ChildItem -LiteralPath $Path -Directory -Recurse -Force)
    $expectedDirectoryCount = if (@($manifest.images).Count -gt 0) { 1 } else { 0 }
    if ($actualDirectories.Count -ne $expectedDirectoryCount) {
        throw 'Staged package contains unexpected or missing directories.'
    }
    foreach ($directory in $actualDirectories) {
        if (($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Staged package contains a reparse directory: $($directory.FullName)"
        }
        if ($directory.FullName.Substring($packageRoot.Length) -cne 'images') {
            throw "Staged package contains an unexpected directory: $($directory.FullName)"
        }
    }
    $calculatedApprovalHash = Get-PackageApprovalHash -Manifest $manifest -Path $Path
    if ($calculatedApprovalHash -cne [string]$manifest.approval_hash) {
        throw 'Staged package approval hash mismatch.'
    }
    return $manifest
}

$source = Test-StagedPackage -Path $PackagePath
$sourceManifest = Join-Path $PackagePath 'manifest.json'

if (-not (Test-Path -LiteralPath $StagingRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $StagingRoot | Out-Null
}
$stagingRootItem = Get-Item -LiteralPath $StagingRoot -Force
if (-not $stagingRootItem.PSIsContainer -or (($stagingRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
    throw 'Windows staging root is unsafe.'
}
$target = Join-Path $StagingRoot ([string]$source.approval_hash)
if (-not (Test-Path -LiteralPath $target)) {
    New-Item -ItemType Directory -Path $target | Out-Null
    Copy-Item -LiteralPath $sourceManifest -Destination (Join-Path $target 'manifest.json')
    if (@($source.images).Count -gt 0) {
        Copy-Item -LiteralPath (Join-Path $PackagePath 'images') -Destination (Join-Path $target 'images') -Recurse
    }
}

$manifest = Test-StagedPackage -Path $target
$sauExecutable = Join-Path $SauHome '.venv\Scripts\sau.exe'
[void](Assert-RegularNoReparseFile -Path $sauExecutable)
$imagePaths = @($manifest.images | ForEach-Object { Join-Path $target (([string]$_.package_path).Replace('/', '\')) })
if ($imagePaths.Count -eq 0) {
    throw 'Xiaohongshu upload-note requires at least one approved image.'
}
$sauArguments = @('xiaohongshu', 'upload-note', '--account', $Account, '--images') + $imagePaths + @(
    '--title', [string]$manifest.title,
    '--note', [string]$manifest.body,
    '--tags', (@($manifest.tags) -join ',')
)

Push-Location -LiteralPath $SauHome
try {
    & $sauExecutable @sauArguments
    if ($LASTEXITCODE -ne 0) {
        throw "SAU failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
