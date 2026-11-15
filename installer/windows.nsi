Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!include "WordFunc.nsh"
!include "FileFunc.nsh"
!include "nsDialogs.nsh"

!ifndef AppName
!define AppName "AIDA FPS Studio"
!endif
!define AppExe "AIDA-FPS-Studio.exe"
!define Publisher "Detonando Gueek"
!define SupportUrl "https://detonandogueek.com.br/aida"
!ifndef ProjectClass
!define ProjectClass "DetonandoGueek.AIDA.Project"
!endif
!ifndef ProjectExtension
!define ProjectExtension ".aida"
!endif
!define UninstallKey "Software\Microsoft\Windows\CurrentVersion\Uninstall\${AppName}"
Var TermsText
Var TermsCheck
Var TermsAccepted

Name "${AppName} ${Version}${Edition}"
OutFile "${SetupPath}"
InstallDir "$LOCALAPPDATA\Programs\${AppName}"
RequestExecutionLevel user
!ifdef TestUncompressed
SetCompress off
!else
SetCompressor /SOLID lzma
!endif
VIProductVersion "${Version}.0"
VIAddVersionKey /LANG=1033 "ProductName" "${AppName}"
VIAddVersionKey /LANG=1033 "ProductVersion" "${Version}"
VIAddVersionKey /LANG=1033 "FileDescription" "${AppName} Setup${Edition}"
VIAddVersionKey /LANG=1033 "FileVersion" "${Version}"
VIAddVersionKey /LANG=1033 "CompanyName" "${Publisher}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "${Publisher}"

!define MUI_ABORTWARNING
!define MUI_ICON "${AppIcon}"
!define MUI_UNICON "${AppIcon}"
!define MUI_LANGDLL_REGISTRY_ROOT HKCU
!define MUI_LANGDLL_REGISTRY_KEY "${UninstallKey}"
!define MUI_LANGDLL_REGISTRY_VALUENAME "InstallerLanguage"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${AppExe}"
!define MUI_FINISHPAGE_RUN_NOTCHECKED
!insertmacro MUI_PAGE_WELCOME
Page custom InstallModePage
Page custom TermsPage TermsPageLeave
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "PortugueseBR"

LangString CoreFiles ${LANG_ENGLISH} "Studio and Start menu shortcut"
LangString CoreFiles ${LANG_PORTUGUESEBR} "Studio e atalho no menu Iniciar"
LangString DesktopShortcut ${LANG_ENGLISH} "Desktop shortcut"
LangString DesktopShortcut ${LANG_PORTUGUESEBR} "Atalho na área de trabalho"
LangString ProjectType ${LANG_ENGLISH} "AIDA analysis project"
LangString ProjectType ${LANG_PORTUGUESEBR} "Projeto de análise AIDA"
LangString UnsupportedSystem ${LANG_ENGLISH} "This installer requires 64-bit Windows."
LangString UnsupportedSystem ${LANG_PORTUGUESEBR} "Este instalador requer Windows de 64 bits."
LangString CloseStudio ${LANG_ENGLISH} "Close AIDA FPS Studio and run the installer again."
LangString CloseStudio ${LANG_PORTUGUESEBR} "Feche o AIDA FPS Studio e execute o instalador novamente."
LangString Downgrade ${LANG_ENGLISH} "A newer version is already installed. Use its installer or uninstall it before installing an older version. Your projects will be preserved."
LangString Downgrade ${LANG_PORTUGUESEBR} "Uma versão mais recente já está instalada. Use o instalador dela ou desinstale antes de instalar uma versão antiga. Seus projetos serão preservados."
LangString AcceptLicense ${LANG_ENGLISH} "I accept the AIDA terms and acknowledge the third-party licenses."
LangString AcceptLicense ${LANG_PORTUGUESEBR} "Aceito os termos do AIDA e reconheço as licenças de terceiros."
LangString LicenseScope ${LANG_ENGLISH} "AIDA uses LGPL Qt/PySide/Shiboken and FFmpeg and other third-party components. Full licenses are available before acceptance and remain installed. Their rights are preserved."
LangString LicenseScope ${LANG_PORTUGUESEBR} "O AIDA usa Qt/PySide/Shiboken e FFmpeg sob LGPL e outros componentes. As licenças completas podem ser consultadas antes do aceite e acompanham a instalação. Seus direitos são preservados."
LangString TermsTitle ${LANG_ENGLISH} "Terms and licenses"
LangString TermsTitle ${LANG_PORTUGUESEBR} "Termos e licenças"
LangString TermsSubtitle ${LANG_ENGLISH} "Read the AIDA terms. Consult the complete licenses whenever you wish."
LangString TermsSubtitle ${LANG_PORTUGUESEBR} "Leia os termos do AIDA. Consulte as licenças completas quando desejar."
LangString ViewLicenses ${LANG_ENGLISH} "View complete licenses"
LangString ViewLicenses ${LANG_PORTUGUESEBR} "Consultar licenças completas"
LangString AcceptRequired ${LANG_ENGLISH} "Accept the AIDA terms to continue."
LangString AcceptRequired ${LANG_PORTUGUESEBR} "Aceite os termos do AIDA para continuar."
LangString ModeTitle ${LANG_ENGLISH} "Installation"
LangString ModeTitle ${LANG_PORTUGUESEBR} "Instalação"
LangString ModeSubtitle ${LANG_ENGLISH} "The installer detects your existing version."
LangString ModeSubtitle ${LANG_PORTUGUESEBR} "O instalador identifica sua versão atual."
LangString ModeNew ${LANG_ENGLISH} "New installation of ${AppName} ${Version}."
LangString ModeNew ${LANG_PORTUGUESEBR} "Nova instalação do ${AppName} ${Version}."
LangString ModeUpdate ${LANG_ENGLISH} "Update version $1 to ${Version}."
LangString ModeUpdate ${LANG_PORTUGUESEBR} "Atualizar a versão $1 para ${Version}."
LangString ModeRepair ${LANG_ENGLISH} "Reinstall ${AppName} ${Version}."
LangString ModeRepair ${LANG_PORTUGUESEBR} "Reinstalar o ${AppName} ${Version}."
LangString KeepProjects ${LANG_ENGLISH} "Your projects, original videos, settings and cache are preserved. Installation applies to your Windows account."
LangString KeepProjects ${LANG_PORTUGUESEBR} "Seus projetos, vídeos originais, preferências e cache serão preservados. A instalação vale para sua conta do Windows."
LangString InstallFailed ${LANG_ENGLISH} "Installation could not finish. Check available disk space and folder permissions, then run the installer again."
LangString InstallFailed ${LANG_PORTUGUESEBR} "Não foi possível concluir a instalação. Confira o espaço livre e a permissão da pasta e execute o instalador novamente."

Function TermsPage
    !insertmacro MUI_HEADER_TEXT "$(TermsTitle)" "$(TermsSubtitle)"
    nsDialogs::Create 1018
    Pop $0
    ${NSD_CreateLabel} 0 0 100% 28u "$(LicenseScope)"
    Pop $0
    nsDialogs::CreateControl EDIT ${DEFAULT_STYLES}|${WS_TABSTOP}|${ES_MULTILINE}|${ES_AUTOVSCROLL}|${WS_VSCROLL} ${WS_EX_CLIENTEDGE} 0 30u 100% 65u ""
    Pop $TermsText
    ${If} $LANGUAGE == ${LANG_PORTUGUESEBR}
        FileOpen $0 "$PLUGINSDIR\Terms.pt.txt" r
    ${Else}
        FileOpen $0 "$PLUGINSDIR\Terms.en.txt" r
    ${EndIf}
    FileSeek $0 2 SET
read_terms:
    ClearErrors
    FileReadUTF16LE $0 $1
    IfErrors terms_loaded
    SendMessage $TermsText ${EM_SETSEL} -1 -1
    SendMessage $TermsText ${EM_REPLACESEL} 0 "STR:$1"
    Goto read_terms
terms_loaded:
    FileClose $0
    SendMessage $TermsText ${EM_SETREADONLY} 1 0
    SendMessage $TermsText ${EM_SETSEL} 0 0
    SendMessage $TermsText ${EM_SCROLLCARET} 0 0
    ${NSD_CreateButton} 0 100u 100% 16u "$(ViewLicenses)"
    Pop $0
    ${NSD_OnClick} $0 ViewCompleteLicenses
    ${NSD_CreateCheckbox} 0 120u 100% 20u "$(AcceptLicense)"
    Pop $TermsCheck
    ${NSD_SetState} $TermsCheck $TermsAccepted
    ${NSD_OnClick} $TermsCheck TermsCheckChanged
    Call TermsStateChanged
    nsDialogs::Show
FunctionEnd

Function TermsStateChanged
    ${NSD_GetState} $TermsCheck $TermsAccepted
    GetDlgItem $0 $HWNDPARENT 1
    ${If} $TermsAccepted == ${BST_CHECKED}
        EnableWindow $0 1
    ${Else}
        EnableWindow $0 0
    ${EndIf}
FunctionEnd

Function TermsCheckChanged
    Pop $0
    Call TermsStateChanged
FunctionEnd

Function TermsPageLeave
    ${NSD_GetState} $TermsCheck $TermsAccepted
    ${If} $TermsAccepted != ${BST_CHECKED}
        MessageBox MB_ICONEXCLAMATION "$(AcceptRequired)"
        Abort
    ${EndIf}
FunctionEnd

Function ViewCompleteLicenses
    Pop $0
    ExecShell "open" "$PLUGINSDIR\AIDA-licenses.html"
FunctionEnd

Function InstallModePage
    !insertmacro MUI_HEADER_TEXT "$(ModeTitle)" "$(ModeSubtitle)"
    nsDialogs::Create 1018
    Pop $0
    ReadRegStr $1 HKCU "${UninstallKey}" "DisplayVersion"
    ${If} $1 == ""
        ${NSD_CreateLabel} 0 10u 100% 28u "$(ModeNew)"
    ${ElseIf} $1 == "${Version}"
        ${NSD_CreateLabel} 0 10u 100% 28u "$(ModeRepair)"
    ${Else}
        ${NSD_CreateLabel} 0 10u 100% 28u "$(ModeUpdate)"
    ${EndIf}
    Pop $0
    ${NSD_CreateLabel} 0 48u 100% 42u "$(KeepProjects)"
    Pop $0
    ${NSD_CreateLabel} 0 104u 100% 32u "$INSTDIR"
    Pop $0
    nsDialogs::Show
FunctionEnd

Function .onInit
    ${GetParameters} $0
    ClearErrors
    ${GetOptions} $0 "/UPDATEPID=" $1
    ${IfNot} ${Errors}
        System::Call 'kernel32::OpenProcess(i 0x100000, i 0, i r1) p .r0'
        ${If} $0 != 0
            System::Call 'kernel32::WaitForSingleObject(p r0, i 30000) i .r2'
            System::Call 'kernel32::CloseHandle(p r0)'
            ${If} $2 != 0
                MessageBox MB_ICONSTOP "Close AIDA FPS Studio and run the update again. / Feche o AIDA FPS Studio e execute a atualização novamente."
                SetErrorLevel 2
                Quit
            ${EndIf}
        ${EndIf}
    ${EndIf}
    !insertmacro MUI_LANGDLL_DISPLAY
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    File /oname=Terms.pt.txt "${TermsPtPath}"
    File /oname=Terms.en.txt "${TermsEnPath}"
    File /oname=AIDA-licenses.html "${LicenseCatalog}"
    ReadRegStr $1 HKCU "${UninstallKey}" "DisplayVersion"
    ${If} $1 != ""
        ${VersionCompare} "$1" "${Version}" $2
        ${If} $2 == 1
            MessageBox MB_ICONSTOP "$(Downgrade)" /SD IDOK
            SetErrorLevel 2
            Quit
        ${EndIf}
    ${EndIf}
    ${IfNot} ${RunningX64}
        MessageBox MB_ICONSTOP "$(UnsupportedSystem)" /SD IDOK
        SetErrorLevel 1
        Quit
    ${EndIf}
    IfFileExists "$INSTDIR\${AppExe}" 0 finished
    System::Call 'kernel32::CreateFileW(w "$INSTDIR\${AppExe}", i 0x40000000, i 0, p 0, i 3, i 0x80, p 0) p .r0'
    ${If} $0 == -1
        MessageBox MB_ICONSTOP "$(CloseStudio)" /SD IDOK
        SetErrorLevel 1
        Quit
    ${EndIf}
    System::Call 'kernel32::CloseHandle(p r0)'
finished:
FunctionEnd

Section "$(CoreFiles)" Core
    SectionIn RO
    SetShellVarContext current
    SetOutPath "$INSTDIR"
    ClearErrors
    File "${BundleDir}\${AppExe}"
    File /r "${BundleDir}\_internal"
    File /r "${BundleDir}\third_party_licenses"
    File /oname=Terms.txt "${TermsPath}"
    File /oname=LICENSE.txt "${LicensePath}"
    File /oname=THIRD_PARTY_NOTICES.md "${NoticesPath}"
    SetOutPath "$INSTDIR\third_party_licenses"
    File /oname=NSIS-LICENSE.txt "${CompilerLicense}"
    SetOutPath "$INSTDIR"
    IfErrors install_failed
    !ifdef RetireFiles
        !include "${RetireFiles}"
    !endif

    WriteUninstaller "$INSTDIR\Uninstall.exe"
    CreateShortcut "$SMPROGRAMS\${AppName}.lnk" "$INSTDIR\${AppExe}"
    WriteRegStr HKCU "${UninstallKey}" "DisplayName" "${AppName}${Edition}"
    WriteRegStr HKCU "${UninstallKey}" "DisplayVersion" "${Version}"
    WriteRegStr HKCU "${UninstallKey}" "Publisher" "${Publisher}"
    WriteRegStr HKCU "${UninstallKey}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${UninstallKey}" "DisplayIcon" "$INSTDIR\${AppExe},0"
    WriteRegStr HKCU "${UninstallKey}" "URLInfoAbout" "${SupportUrl}"
    WriteRegStr HKCU "${UninstallKey}" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
    WriteRegDWORD HKCU "${UninstallKey}" "NoModify" 1
    WriteRegDWORD HKCU "${UninstallKey}" "NoRepair" 1

    WriteRegStr HKCU "Software\Classes\${ProjectClass}" "" "$(ProjectType)"
    WriteRegStr HKCU "Software\Classes\${ProjectClass}\DefaultIcon" "" '$\"$INSTDIR\${AppExe}$\",0'
    WriteRegStr HKCU "Software\Classes\${ProjectClass}\shell\open\command" "" '$\"$INSTDIR\${AppExe}$\" $\"%1$\"'
    WriteRegNone HKCU "Software\Classes\${ProjectExtension}\OpenWithProgids" "${ProjectClass}"
    ReadRegStr $0 HKCR "${ProjectExtension}" ""
    ${If} $0 == ""
        WriteRegStr HKCU "Software\Classes\${ProjectExtension}" "" "${ProjectClass}"
    ${EndIf}
    System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
    Goto install_done
install_failed:
    MessageBox MB_ICONSTOP "$(InstallFailed)" /SD IDOK
    SetErrorLevel 3
    Abort
install_done:
SectionEnd

Section /o "$(DesktopShortcut)"
    SetShellVarContext current
    CreateShortcut "$DESKTOP\${AppName}.lnk" "$INSTDIR\${AppExe}"
SectionEnd

Function un.onInit
    !insertmacro MUI_UNGETLANGUAGE
    IfFileExists "$INSTDIR\${AppExe}" 0 un_finished
    System::Call 'kernel32::CreateFileW(w "$INSTDIR\${AppExe}", i 0x40000000, i 0, p 0, i 3, i 0x80, p 0) p .r0'
    ${If} $0 == -1
        MessageBox MB_ICONSTOP "$(CloseStudio)" /SD IDOK
        SetErrorLevel 1
        Quit
    ${EndIf}
    System::Call 'kernel32::CloseHandle(p r0)'
un_finished:
FunctionEnd

Section "Uninstall"
    SetShellVarContext current
    Delete "$DESKTOP\${AppName}.lnk"
    Delete "$SMPROGRAMS\${AppName}.lnk"
    ReadRegStr $0 HKCU "Software\Classes\${ProjectExtension}" ""
    ${If} $0 == "${ProjectClass}"
        DeleteRegValue HKCU "Software\Classes\${ProjectExtension}" ""
    ${EndIf}
    DeleteRegValue HKCU "Software\Classes\${ProjectExtension}\OpenWithProgids" "${ProjectClass}"
    DeleteRegKey /ifempty HKCU "Software\Classes\${ProjectExtension}\OpenWithProgids"
    DeleteRegKey /ifempty HKCU "Software\Classes\${ProjectExtension}"
    DeleteRegKey HKCU "Software\Classes\${ProjectClass}"
    System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
    DeleteRegKey HKCU "${UninstallKey}"

    !include "${RemoveFiles}"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"
SectionEnd

Section /o "Offline mode / Modo offline (disable automatic update checks)" OfflineUpdates
    SetOutPath "$INSTDIR"
    FileOpen $0 "$INSTDIR\.disable-update-check" w
    FileClose $0
SectionEnd
