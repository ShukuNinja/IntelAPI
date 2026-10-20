$ErrorActionPreference = 'Stop'

$trackedArtifacts = git ls-files | Where-Object {
    $_ -match '(^|/)__pycache__(/|$)' -or
    $_ -match '\.py[co]$' -or
    $_ -match '(^|/)[^/]+\.egg-info(/|$)'
}

if (-not $trackedArtifacts) {
    Write-Host 'No tracked Python cache/bytecode or egg-info artifacts found.'
    exit 0
}

Write-Host 'The following tracked generated artifacts will be removed from Git:'
$trackedArtifacts | ForEach-Object { Write-Host "  $_" }
$confirmation = Read-Host 'Type REMOVE to stage these deletions'
if ($confirmation -cne 'REMOVE') {
    Write-Host 'Cancelled; no files were removed.'
    exit 0
}

foreach ($path in $trackedArtifacts) {
    git rm -- "$path"
    if ($LASTEXITCODE -ne 0) {
        throw "git rm failed for: $path"
    }
}

Write-Host 'Generated artifacts removed from the Git index and working tree.'
Write-Host 'Review with: git status --short'
