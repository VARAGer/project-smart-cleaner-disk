#define AppName "SmartCleaner"
#define AppVersion "0.1.0"
#define AppPublisher "MIREA SmartCleaner"
#define SourceDir "..\..\dist\SmartCleaner"

[Setup]
AppId={{92E8DD5B-4159-4790-9878-7D6E0D816B9B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\SmartCleaner
DefaultGroupName=SmartCleaner
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=SmartCleanerSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\SmartCleaner.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifdef BackendUrlFile
Source: "{#BackendUrlFile}"; DestDir: "{localappdata}\SmartCleaner"; DestName: "backend_url.txt"; Flags: ignoreversion
#endif

[Icons]
Name: "{group}\SmartCleaner"; Filename: "{app}\SmartCleaner.exe"
Name: "{autodesktop}\SmartCleaner"; Filename: "{app}\SmartCleaner.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\SmartCleaner.exe"; Description: "Launch SmartCleaner"; Flags: nowait postinstall skipifsilent
