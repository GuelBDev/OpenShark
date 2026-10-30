$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python OpenShark/make_icon.py
$iconPath = Join-Path $PSScriptRoot 'OpenShark\openshark.ico'
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name OpenShark `
  --icon $iconPath `
  --add-data "$iconPath;OpenShark" `
  --add-data "$PSScriptRoot\OpenShark\assets;OpenShark/assets" `
  --add-data "C:\Users\migue\Downloads\AttackShark Software\Attack Shark Software\res\skins;OpenShark/vendor_art" `
  --collect-submodules pystray `
  --distpath 'OpenShark/dist' `
  --workpath "$env:TEMP\openshark-pyinstaller-build" `
  --specpath "$env:TEMP" `
  OpenShark/main.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
Write-Host "Executável: $PSScriptRoot\OpenShark\dist\OpenShark.exe"
