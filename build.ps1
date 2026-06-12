<#
.SYNOPSIS
    Build the published Lisbon Lemon Guide (wrapper for scripts/build.py).
.DESCRIPTION
    Runs the full publish pipeline: sync from raw -> generate index -> generate
    nav -> linkify claims -> lint. Exits non-zero if linting fails.
.EXAMPLE
    .\build.ps1
    .\build.ps1 -Check        # report sync drift only
#>
param(
    [switch]$Check,
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

$buildArgs = @()
if ($Check)    { $buildArgs += "--check" }
if ($SkipSync) { $buildArgs += "--skip-sync" }

python "$PSScriptRoot\scripts\build.py" @buildArgs
exit $LASTEXITCODE
