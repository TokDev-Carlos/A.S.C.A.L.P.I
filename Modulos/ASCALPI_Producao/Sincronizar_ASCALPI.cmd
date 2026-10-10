@echo off
chcp 65001 >nul
setlocal
rem Sincroniza o clone UNICO do ASCALPI com o SHA EXATO autorizado no QUADRO_TAREFAS.md.
rem A logica (e os testes) estao em ferramentas\sincronizar.py: confere o SHA ANTES de mexer no codigo,
rem guarda copia de "dados" em ASCALPI_Local_Archive\snapshots_dados e so entao faz git pull --ff-only.
rem Uso: Sincronizar_ASCALPI.cmd <SHA autorizado>
set "AQUI=%~dp0"
set "PY=C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe"
if not exist "%PY%" set "PY=python"
if "%~1"=="" (
  echo INFORME O SHA AUTORIZADO NO QUADRO. EXEMPLO: Sincronizar_ASCALPI.cmd 1a2b3c4
  goto fim
)
"%PY%" "%AQUI%ferramentas\sincronizar.py" --sha %*
:fim
pause
