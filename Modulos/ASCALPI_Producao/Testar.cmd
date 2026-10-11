@echo off
chcp 65001 >nul
set "PY=C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe"
if not exist "%PY%" set "PY=python"
cd /d "%~dp0"
"%PY%" -m unittest discover -s tests -t . -v
pause
