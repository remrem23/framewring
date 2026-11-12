# Runs INSIDE Windows Sandbox: installs the freshly built setup.exe from C:\release and starts Framewring.
# Запускается ВНУТРИ «Песочницы Windows»: ставит свежий setup.exe из C:\release и запускает Framewring.
$ErrorActionPreference = 'Stop'
$setup = Get-ChildItem 'C:\release' -Filter 'Framewring-*-setup.exe' | Sort-Object LastWriteTime | Select-Object -Last 1
if (-not $setup) { Write-Host 'No Framewring-*-setup.exe in C:\release'; Read-Host 'Enter to exit'; exit 1 }
Write-Host "Installing $($setup.Name) ..."
Start-Process $setup.FullName -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/CURRENTUSER', '/NORESTART' -Wait
$exe = Join-Path $env:LOCALAPPDATA 'Programs\Framewring\Framewring.exe'
if (-not (Test-Path $exe)) { Write-Host 'Install FAILED: Framewring.exe not found'; Read-Host 'Enter to exit'; exit 1 }
Write-Host "Installed: $exe  (version $((Get-Item $exe).VersionInfo.FileVersion))"
Start-Process $exe
Write-Host 'Framewring started. Check: window opens, modes list, Test on a sample video, Report a bug, update bar.'
