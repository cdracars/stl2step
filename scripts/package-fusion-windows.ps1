[CmdletBinding()]
param(
    [string]$BuildDir = (Join-Path $PSScriptRoot '..\build'),
    [string]$OutputDir = (Join-Path $PSScriptRoot '..\integrations\fusion\Stl2StepFusion\bin\windows-x86_64'),
    [string]$OcctBin
)

$ErrorActionPreference = 'Stop'

function Resolve-ExistingPath([string]$Path, [string]$Description) {
    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $resolved) {
        throw "$Description was not found: $Path"
    }
    return $resolved.Path
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$buildRoot = Resolve-ExistingPath $BuildDir 'Build directory'
$config = if (Test-Path (Join-Path $buildRoot 'Release\stl2step.exe')) { 'Release' } else { '' }
$exe = if ($config) { Join-Path $buildRoot "$config\stl2step.exe" } else { Join-Path $buildRoot 'stl2step.exe' }
$exe = Resolve-ExistingPath $exe 'stl2step executable'

if (-not $OcctBin) {
    $cache = Join-Path $buildRoot 'CMakeCache.txt'
    if (Test-Path -LiteralPath $cache) {
        $prefix = Select-String -LiteralPath $cache -Pattern '^CMAKE_PREFIX_PATH:.*=(.+)$' |
            Select-Object -First 1 -ExpandProperty Matches |
            ForEach-Object { $_.Groups[1].Value }
        if ($prefix) {
            $candidate = Join-Path $prefix 'bin'
            if (Test-Path (Join-Path $candidate 'TKDESTL.dll')) { $OcctBin = $candidate }
        }
    }
}

if (-not $OcctBin) {
    $hints = @(
        'C:\Program Files\OpenCASCADE*\bin',
        'C:\Program Files\FreeCAD*\bin',
        'C:\Program Files\KiCad\*\bin'
    )
    foreach ($hint in $hints) {
        $candidate = Get-ChildItem -Path $hint -Directory -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
        if ($candidate -and (Test-Path (Join-Path $candidate 'TKDESTL.dll'))) {
            $OcctBin = $candidate
            break
        }
    }
}

$occtRoot = if ($OcctBin) { Resolve-ExistingPath $OcctBin 'OCCT runtime directory' } else { $null }
if (-not $occtRoot) {
    throw 'Could not locate OCCT DLLs. Pass -OcctBin <path-to-OCCT-bin>.'
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
# The directory is generated output. Remove only files in this exact package
# directory so a rerun cannot leave stale OCCT DLLs from an older build.
Get-ChildItem -LiteralPath $OutputDir -File | Remove-Item -Force
Copy-Item -LiteralPath $exe -Destination (Join-Path $OutputDir 'stl2step.exe') -Force

$dlls = Get-ChildItem -LiteralPath $occtRoot -Filter '*.dll' -File |
    Where-Object { $_.Name -notmatch '^(api-ms-win|ext-ms-win)-' }
if (-not $dlls) { throw "No DLLs found in OCCT runtime directory: $occtRoot" }
Copy-Item -LiteralPath $dlls.FullName -Destination $OutputDir -Force

$packagedExe = Join-Path (Resolve-Path $OutputDir) 'stl2step.exe'
$oldPath = $env:Path
try {
    $env:Path = "$(Resolve-Path $OutputDir);$oldPath"
    $version = (& $packagedExe --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^stl2step \d+\.\d+\.\d+$') {
        throw "Packaged executable validation failed (exit $LASTEXITCODE): $version"
    }
} finally {
    $env:Path = $oldPath
}

Write-Host "Packaged $($dlls.Count) OCCT DLL(s) and stl2step.exe into $OutputDir"
Write-Host "Validated: $version"
