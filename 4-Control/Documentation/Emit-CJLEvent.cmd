@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Engine\Emit-CJLEvent.ps1" %*
exit /b %ERRORLEVEL%
