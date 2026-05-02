; OMNIDEPLOY IT - INNO SETUP CONFIGURATION
#define MyAppName "OmniDeploy IT Agent"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Techtix"
#define MyAppExeName "OmniDeploy ITAgent.exe"

[Setup]
AppId={{C4B8E1D2-8A3F-4B9E-BC12-D9E2A4F5B6C7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf}\OmniDeployIT
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Require Admin for Program Files access
PrivilegesRequired=admin
OutputDir=.\installer_output
OutputBaseFilename=OmniDeployIT_Setup_v3.0.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startupicon"; Description: "Launch Agent on Windows Startup"; GroupDescription: "Persistence:"

[Files]
; IMPORTANT: Uses relative path so GitHub Actions can find the freshly built EXE
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Creates a shortcut in the Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

; MAGIC LINE: Creates a shortcut in the user's Startup folder
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
; Launch the agent immediately after installation completes
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill the agent before uninstalling so files aren't locked
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM ""{#MyAppExeName}"" /T"; RunOnceId: "StopAgentBeforeUninstall"

[Code]
function IsPythonInstalled: Boolean;
begin
  Result := RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore') or 
            RegKeyExists(HKEY_CURRENT_USER, 'SOFTWARE\Python\PythonCore');
end;