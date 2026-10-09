@echo off
chcp 65001 >nul
setlocal
set "AQUI=%~dp0"
set "PY=C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe"
if not exist "%PY%" set "PY=python"
cd /d "%AQUI%"
title ASCALPI Producao
"%PY%" -m ascalpi_producao --dados "%AQUI%dados" servir --abrir
pause
