; OpenShark Windows installer (Inno Setup 6)
; The payload is intentionally taken from the real application folder:
; C:\Users\migue\Downloads\AttackShark Software\OpenShark\dist\OpenShark.exe
#define AppName "OpenShark"
#define AppVersion "0.6.2"
#define AppPublisher "GuelBDev"
#define AppExeName "OpenShark.exe"
#define AppSource "OpenShark\dist\OpenShark.exe"

[Setup]
AppId={{A9F6A6C8-73A4-4FC4-9E63-6C0A8B8B0F40}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=OpenShark Windows Installer
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
SetupIconFile=OpenShark\openshark.ico
DefaultDirName={autopf}\OpenShark
DefaultGroupName=OpenShark
OutputDir=OpenShark\dist
OutputBaseFilename=OpenShark-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}

[Files]
Source: "{#AppSource}"; DestDir: "{app}"; DestName: "{#AppExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\OpenShark"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\OpenShark"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Iniciar o OpenShark"; Flags: nowait postinstall skipifsilent
