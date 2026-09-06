$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$graphicsPath = Join-Path $root 'Graphics'

function Invoke-GuiTests {
    Push-Location $root
    try {
        Write-Host "Running GUI regression tests..."
        & python -m unittest discover -s tests -v
        if ($LASTEXITCODE -eq 0) {
            Write-Host "GUI regression tests passed."
        } else {
            Write-Host "GUI regression tests failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
}

Invoke-GuiTests

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $graphicsPath
$watcher.Filter = '*.py'
$watcher.IncludeSubdirectories = $true
$watcher.NotifyFilter = [System.IO.NotifyFilters]::LastWrite -bor [System.IO.NotifyFilters]::FileName
$watcher.EnableRaisingEvents = $true

$action = {
    $changedPath = $Event.SourceEventArgs.FullPath
    Write-Host "GUI file changed: $changedPath"
    Invoke-GuiTests
}

$changedSubscription = Register-ObjectEvent -InputObject $watcher -EventName Changed -Action $action
$createdSubscription = Register-ObjectEvent -InputObject $watcher -EventName Created -Action $action
$renamedSubscription = Register-ObjectEvent -InputObject $watcher -EventName Renamed -Action $action

try {
    while ($true) {
        Wait-Event -Timeout 1 | Out-Null
    }
} finally {
    Unregister-Event -SubscriptionId $changedSubscription.Id
    Unregister-Event -SubscriptionId $createdSubscription.Id
    Unregister-Event -SubscriptionId $renamedSubscription.Id
    $watcher.Dispose()
}
