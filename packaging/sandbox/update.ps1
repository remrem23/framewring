# Runs INSIDE Windows Sandbox: downloads an OLDER published release from GitHub, installs it and starts it.
# Then click "Update" in the bar at the top and check that the newest version installs and restarts.
param([string]$From = '')
$ErrorActionPreference = 'Stop'
$api = 'https://api.github.com/repos/remrem23/framewring/releases'
$rels = Invoke-RestMethod $api -Headers @{ 'User-Agent' = 'Framewring-sandbox-test' } | Where-Object { -not $_.draft -and -not $_.prerelease }
if (-not $From) { $From = ($rels | Select-Object -Skip 1 -First 1).tag_name }   # second-to-last release
$rel = $rels | Where-Object { $_.tag_name -eq $From -or $_.tag_name -eq "v$From" } | Select-Object -First 1
if (-not $rel) { Write-Host "Release $From not found"; Read-Host 'Enter to exit'; exit 1 }
$asset = $rel.assets | Where-Object { $_.name -like '*-setup.exe' } | Select-Object -First 1
$dst = Join-Path $env:TEMP $asset.name
Write-Host "Downloading $($asset.name) from $($rel.tag_name) ..."
Invoke-WebRequest $asset.browser_download_url -OutFile $dst -UseBasicParsing
Start-Process $dst -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/CURRENTUSER', '/NORESTART' -Wait
$exe = Join-Path $env:LOCALAPPDATA 'Programs\Framewring\Framewring.exe'
Write-Host "Installed $($rel.tag_name): $((Get-Item $exe).VersionInfo.FileVersion). Starting — wait ~5 s for the update bar."
Start-Process $exe
