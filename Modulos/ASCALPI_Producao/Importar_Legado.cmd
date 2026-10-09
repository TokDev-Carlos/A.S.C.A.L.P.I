@echo off
chcp 65001 >nul
setlocal
set "AQUI=%~dp0"
set "PY=C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe"
if not exist "%PY%" set "PY=python"
cd /d "%AQUI%"
set "ORIGEM=%~1"
if "%ORIGEM%"=="" set /p "ORIGEM=Pasta com os OK-*.xlsm e o Controle (somente leitura): "
"%PY%" -m ascalpi_producao --dados "%AQUI%dados" importar --origem "%ORIGEM%"
pause
