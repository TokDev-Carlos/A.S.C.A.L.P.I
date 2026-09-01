@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Engine\Process-CJLEvents.ps1" %*
exit /b %ERRORLEVEL%
