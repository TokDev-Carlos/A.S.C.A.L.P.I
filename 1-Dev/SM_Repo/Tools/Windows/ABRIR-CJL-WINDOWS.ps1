param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^http://127[.]0[.]0[.]1:[0-9]{1,5}$')]
    [string]$Url
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$Response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 8

if ([int]$Response.StatusCode -ne 200) {
    throw "CJL HTTP returned status $($Response.StatusCode)."
}

Start-Process -FilePath $Url
Write-Output 'WINDOWS_HTTP=PASS'
