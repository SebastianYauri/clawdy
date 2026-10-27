# Installs Clawdy on Windows (no administrator rights needed):
#   irm https://raw.githubusercontent.com/SebastianYauri/clawdy/main/get.ps1 | iex
# $env:CLAWDY_VERSION = '1.4.1' picks a specific release instead of the latest one.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'      # makes Invoke-WebRequest much faster
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$repo = 'SebastianYauri/clawdy'
$tag = $env:CLAWDY_VERSION
if (-not $tag) {
    $tag = (Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest").tag_name
}
$tag = $tag.TrimStart('v')
$setup = Join-Path $env:TEMP "Clawdy-Setup-$tag.exe"

Write-Host "> Downloading Clawdy $tag..." -ForegroundColor DarkYellow
Invoke-WebRequest "https://github.com/$repo/releases/download/v$tag/Clawdy-Setup.exe" -OutFile $setup -UseBasicParsing

Write-Host "> Installing..." -ForegroundColor DarkYellow
$p = Start-Process $setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru
Remove-Item $setup -ErrorAction SilentlyContinue
if ($p.ExitCode -ne 0) { throw "the installer failed (code $($p.ExitCode))" }

$exe = Join-Path $env:LOCALAPPDATA 'Programs\Clawdy\Clawdy.exe'
if (-not $env:CLAWDY_NO_START) { Start-Process $exe }
Write-Host "> Done! Clawdy is in the corner of your screen." -ForegroundColor DarkYellow
