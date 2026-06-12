<#
.SYNOPSIS
    Build the published Lisbon Lemon Guide (wrapper for scripts/build.py).
.DESCRIPTION
    Runs the full publish pipeline: sync from raw -> generate index -> generate
    nav -> linkify claims -> lint. Exits non-zero if linting fails.
.EXAMPLE
    .\build.ps1               # advisory: logs lint issues, still succeeds
    .\build.ps1 -Strict       # hard gate: fails the build on lint errors
    .\build.ps1 -Check        # report sync drift only
#>
param(
    [switch]$Check,
    [switch]$SkipSync,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

$buildArgs = @()
if ($Check)    { $buildArgs += "--check" }
if ($SkipSync) { $buildArgs += "--skip-sync" }
if ($Strict)   { $buildArgs += "--strict" }

python "$PSScriptRoot\scripts\build.py" @buildArgs
exit $LASTEXITCODE
