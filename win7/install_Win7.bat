@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Judo Club Seddouk - Installation automatique Windows 7
color 0F

echo ============================================================
echo    JUDO CLUB SEDDOUK - Installation automatique Windows 7
echo ============================================================
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo    Elevation automatique : une fenetre bleue (UAC) va apparaitre.
    echo.
    echo    Cliquez sur "Oui" pour continuer. Rien d'autre a faire.
    echo.
    powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b 0
)

if not exist "%SystemRoot%\SysWOW64" (
    echo ERREUR : Windows 7 32 bits detecte.
    echo Ce programme d'installation ne couvre que Windows 7 64 bits.
    echo.
    pause
    exit /b 1
)

echo Activation de TLS 1.2 (necessaire pour telecharger) ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Client" /v Enabled /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Client" /v DisabledByDefault /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Server" /v Enabled /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Server" /v DisabledByDefault /t REG_DWORD /d 0 /f >nul 2>&1
echo    OK

set "WORK=%~dp0"
set "VB2=%ProgramFiles%\WebView2"
set "DEXT=%PUBLIC%\Desktop"

echo Etapes :
echo   1. Correctif Windows KB2533623 (securite)
echo   2. .NET Framework 4.8
echo   3. Composants Visual C++
echo   4. Moteur WebView2 version 109 (dernier compatible Windows 7)
echo   5. Application Judo Club Seddouk
echo.
echo Internet requis : les fichiers seront telecharges automatiquement.
echo S'ils sont deja a cote de ce fichier, ils seront reutilises.
echo.
echo ATTENTION : le PC sera REDEMARRE automatiquement a la fin.
echo.
set "FAIL=0"

echo [1/5] Correctif Windows KB2533623 ...
if not exist "%WORK%Windows6.1-KB2533623-x64.msu" (
    call :download "https://github.com/beny1226/Windows-7-KB2533623/raw/main/Windows6.1-KB2533623-x64.msu" "%WORK%Windows6.1-KB2533623-x64.msu"
)
if exist "%WORK%Windows6.1-KB2533623-x64.msu" (
    wusa.exe "%WORK%Windows6.1-KB2533623-x64.msu" /quiet /norestart >nul 2>&1
    set "R=!errorlevel!"
    if "!R!"=="0" ( echo    OK ) else if "!R!"=="2359302" ( echo    OK (deja installe) ) else ( echo    Attention: code !R! (ignore) )
) else (
    echo    MSU introuvable - etape ignoree
    set "FAIL=1"
)

echo [2/5] .NET Framework 4.8 ...
if not exist "%WORK%dotnetfx48.exe" (
    call :download "https://go.microsoft.com/fwlink/?linkid=2088631" "%WORK%dotnetfx48.exe"
)
if exist "%WORK%dotnetfx48.exe" (
    "%WORK%dotnetfx48.exe" /q /norestart >nul 2>&1
    set "R=!errorlevel!"
    if "!R!"=="0" ( echo    OK ) else if "!R!"=="3010" ( echo    OK (a terminer au redemarrage) ) else ( echo    Attention: code !R! - affichage de secours possible )
) else (
    echo    Installateur introuvable - etape ignoree
    set "FAIL=1"
)

echo [3/5] Visual C++ ...
if not exist "%WORK%vc_redist.x64.exe" (
    call :download "https://aka.ms/vs/17/release/vc_redist.x64.exe" "%WORK%vc_redist.x64.exe"
)
if exist "%WORK%vc_redist.x64.exe" (
    "%WORK%vc_redist.x64.exe" /install /quiet /norestart >nul 2>&1
    echo    OK
) else (
    echo    Installateur introuvable - etape ignoree
    set "FAIL=1"
)

echo [4/5] Moteur WebView2 109 ...
if not exist "%VB2%" mkdir "%VB2%" >nul 2>&1
if not exist "%WORK%Microsoft.WebView2.FixedVersionRuntime.109.0.1518.78.x64.cab" (
    call :download "https://github.com/westinyang/WebView2RuntimeArchive/releases/download/109.0.1518.78/Microsoft.WebView2.FixedVersionRuntime.109.0.1518.78.x64.cab" "%WORK%Microsoft.WebView2.FixedVersionRuntime.109.0.1518.78.x64.cab"
)
if exist "%WORK%Microsoft.WebView2.FixedVersionRuntime.109.0.1518.78.x64.cab" (
    expand "%WORK%Microsoft.WebView2.FixedVersionRuntime.109.0.1518.78.x64.cab" -F:* "%VB2%" >nul 2>&1
)
set "V2D="
for /f "delims=" %%d in ('dir /b /s /ad "%VB2%\*" 2^>nul') do (
    if exist "%%d\msedgewebview2.exe" set "V2D=%%d"
)
if not defined V2D if exist "%VB2%\msedgewebview2.exe" set "V2D=%VB2%"
if defined V2D (
    reg add "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv /t REG_SZ /d "109.0.1518.78" /f >nul 2>&1
    reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v WEBVIEW2_BROWSER_EXECUTABLE_FOLDER /t REG_SZ /d "!V2D!" /f >nul 2>&1
    setx WEBVIEW2_BROWSER_EXECUTABLE_FOLDER "!V2D!" >nul 2>&1
    echo    OK - !V2D!
) else (
    echo    ECHEC : moteur WebView2 introuvable apres decompression
    set "FAIL=1"
)

echo [5/5] Application Judo Club Seddouk ...
if exist "%DEXT%" (
    if not exist "%DEXT%\Judo_Club_Seddouk.exe" (
        call :download "https://raw.githubusercontent.com/mokrani-zahir/judo-seddouk-management-hr/master/dist/Judo_Club_Seddouk.exe" "%DEXT%\Judo_Club_Seddouk.exe"
    )
    if exist "%DEXT%\Judo_Club_Seddouk.exe" ( echo    OK - copiee sur le Bureau ) else ( echo    ECHEC du telechargement& set "FAIL=1" )
) else (
    echo    Bureau public introuvable - app non copiee
)

echo.
echo ============================================================
if "%FAIL%"=="1" (
    echo  Termine avec des alertes (voir au-dessus).
) else (
    echo  Installation terminee avec succes.
)
echo  REDEMARRAGE AUTOMATIQUE dans 15 secondes...
echo  (Pour annuler : ouvrir une invite de commandes et taper  shutdown /a )
echo ============================================================
echo.
shutdown /r /t 15 /c "Judo Club Seddouk - installation terminee." >nul 2>&1
echo  Apres le redemarrage, double-cliquez sur
echo  "Judo_Club_Seddouk.exe" sur le Bureau.
echo.
pause
exit /b 0

:download
set "U=%~1"
set "D=%~2"
if exist "!D!" for %%s in ("!D!") do if %%~zs GTR 1000 goto :eof
bitsadmin /transfer jd!RANDOM! /download /priority high "!U!" "!D!" >nul 2>&1
if not exist "!D!" certutil -urlcache -f -split "!U!" "!D!" >nul 2>&1
if exist "!D!" for %%s in ("!D!") do if %%~zs LSS 1000 del "!D!" >nul 2>&1
goto :eof