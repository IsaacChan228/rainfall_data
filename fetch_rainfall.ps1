param(
    [string]$OutputPath = (Join-Path $PSScriptRoot 'hourly_rainfall.txt'),
    [string]$Url = 'https://data.weather.gov.hk/weatherAPI/opendata/hourlyRainfall.php?lang=en'
)

$ErrorActionPreference = 'Stop'

try {
    $response = Invoke-WebRequest -Uri $Url -Method Get -Headers @{ Accept = 'application/json' } -TimeoutSec 30
    $content = $response.Content

    if ([string]::IsNullOrWhiteSpace($content)) {
        throw 'The response body was empty.'
    }

    $directory = Split-Path -Parent $OutputPath
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($OutputPath, $content, $utf8NoBom)
}
catch {
    Write-Error "Failed to save rainfall data to '$OutputPath'. $($_.Exception.Message)"
    exit 1
}