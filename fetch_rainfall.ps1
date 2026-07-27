param(
    [string]$OutputPath,
    [string]$Url = 'https://data.weather.gov.hk/weatherAPI/opendata/hourlyRainfall.php?lang=en'
)

$ErrorActionPreference = 'Stop'

try {
    $invokeWebRequestParams = @{
        Uri = $Url
        Method = 'Get'
        Headers = @{ Accept = 'application/json' }
        TimeoutSec = 30
    }

    if ((Get-Command Invoke-WebRequest).Parameters.ContainsKey('UseBasicParsing')) {
        $invokeWebRequestParams.UseBasicParsing = $true
    }

    $response = Invoke-WebRequest @invokeWebRequestParams
    $content = $response.Content

    if ([string]::IsNullOrWhiteSpace($content)) {
        throw 'The response body was empty.'
    }

    $data = $content | ConvertFrom-Json
    if (-not $data.obsTime) {
        throw 'The response did not contain an obsTime value.'
    }

    $takenTime = [System.DateTimeOffset]::Parse($data.obsTime).ToOffset([TimeSpan]::FromHours(8))
    $defaultFileName = 'rainfall {0} {1}HKT.txt' -f $takenTime.ToString('ddMMM', [System.Globalization.CultureInfo]::InvariantCulture), $takenTime.ToString('HHmm')

    if ([string]::IsNullOrWhiteSpace($OutputPath)) {
        $OutputPath = Join-Path $PSScriptRoot $defaultFileName
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