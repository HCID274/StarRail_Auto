param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("main", "universe")]
    [string]$Task,

    [Parameter(Mandatory = $true)]
    [int]$Timeout
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$uv = Get-Command uv -ErrorAction Stop

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] running scheduled task: $Task"
Write-Host "project root: $projectRoot"
Write-Host "uv path: $($uv.Source)"

& $uv.Source run python m7a_runner.py $Task --timeout $Timeout
exit $LASTEXITCODE
