@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
set "PY=%ROOT%\Runtime\Python\python.exe"
set "VAL=%ROOT%\App\Validacao\validar_sistema.py"
if not exist "%PY%" (
  echo ERRO: Runtime Python ausente: "%PY%"
  exit /b 2
)
"%PY%" -B -I -S "%VAL%" "%ROOT%"
exit /b %errorlevel%
