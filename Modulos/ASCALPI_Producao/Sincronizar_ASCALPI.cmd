@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
rem ============================================================================================
rem  Sincroniza o clone UNICO do ASCALPI (D:\Programas\ASCALPI_Project) com o commit autorizado.
rem  Nao copia codigo para outra pasta. A pasta "dados" (base de homologacao) e ignorada pelo Git
rem  e o pull nao a toca; antes, uma copia dela vai para ASCALPI_Local_Archive\snapshots_dados.
rem  Uso: Sincronizar_ASCALPI.cmd [branch] [sha]     (padrao: modulo/producao-op)
rem ============================================================================================
set "MODULO=%~dp0"
for %%I in ("%MODULO%..\..") do set "RAIZ=%%~fI"
for %%I in ("%RAIZ%\..") do set "ARQUIVO=%%~fI\ASCALPI_Local_Archive\snapshots_dados"
set "BRANCH=%~1"
if "%BRANCH%"=="" set "BRANCH=modulo/producao-op"
set "PEDIDO=%~2"

where git >nul 2>&1
if errorlevel 1 ( echo GIT NAO ENCONTRADO NO PATH. & goto fim )
git -C "%RAIZ%" rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 ( echo "%RAIZ%" NAO E UM CLONE GIT. & goto fim )
for /f %%s in ('git -C "%RAIZ%" rev-parse --short HEAD') do set "ANTES=%%s"
for /f %%b in ('git -C "%RAIZ%" rev-parse --abbrev-ref HEAD') do set "ATUAL=%%b"
echo CLONE   : %RAIZ%
echo BRANCH  : !ATUAL!  -^>  %BRANCH%
echo SHA     : !ANTES!
if not "%PEDIDO%"=="" echo PEDIDO  : %PEDIDO%
echo.

rem 1) nenhuma alteracao local em arquivo versionado (dados\ e ignorada e nao conta)
set "SUJO="
for /f "delims=" %%l in ('git -C "%RAIZ%" status --porcelain --untracked-files=no') do set "SUJO=1"
if defined SUJO (
  echo HA ALTERACOES LOCAIS EM ARQUIVOS DO GIT. NADA FOI FEITO:
  git -C "%RAIZ%" status -s --untracked-files=no
  goto fim
)

rem 2) o ASCALPI precisa estar fechado (o banco e os modelos nao podem estar em uso)
netstat -ano | findstr /R /C:":8765 .*LISTENING" >nul
if not errorlevel 1 ( echo O ASCALPI ESTA ABERTO NA PORTA 8765. FECHE A JANELA DELE E RODE DE NOVO. & goto fim )

choice /C SN /M "Guardar copia de dados e sincronizar agora"
if errorlevel 2 goto fim

rem 3) copia da base de homologacao (so para recuperar testes)
if exist "%MODULO%dados" (
  for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CARIMBO=%%d"
  set "DESTINO=%ARQUIVO%\dados_!CARIMBO!_!ANTES!"
  echo COPIA DE DADOS: "!DESTINO!"
  robocopy "%MODULO%dados" "!DESTINO!" /E /R:1 /W:1 /NP /NFL /NDL >nul
  if errorlevel 8 ( echo FALHA NA COPIA DE DADOS. NADA FOI SINCRONIZADO. & goto fim )
)

rem 4) buscar e avancar so por fast-forward (nunca rebase, merge local ou force)
git -C "%RAIZ%" fetch origin --prune
if errorlevel 1 goto falha
if /I not "!ATUAL!"=="%BRANCH%" (
  git -C "%RAIZ%" switch "%BRANCH%"
  if errorlevel 1 goto falha
)
git -C "%RAIZ%" pull --ff-only origin "%BRANCH%"
if errorlevel 1 goto falha
for /f %%s in ('git -C "%RAIZ%" rev-parse --short HEAD') do set "DEPOIS=%%s"
echo.
echo SINCRONIZADO: !ANTES!  -^>  !DEPOIS!  (%BRANCH%)

rem 5) conferir o SHA autorizado, se informado
if not "%PEDIDO%"=="" (
  git -C "%RAIZ%" merge-base --is-ancestor "%PEDIDO%" HEAD
  if errorlevel 1 (
    echo ATENCAO: O SHA PEDIDO %PEDIDO% NAO ESTA NESTA VERSAO. CONFIRA NO QUADRO ANTES DE TESTAR.
  ) else (
    echo SHA PEDIDO %PEDIDO% CONFERIDO.
  )
)
echo.
echo Proximos passos: "Testar.cmd" (testes leves) e "Iniciar_ASCALPI_Producao.cmd".
echo Registre no QUADRO_TAREFAS.md o SHA testado (!DEPOIS!).
goto fim

:falha
echo FALHA NO GIT. NADA FOI APAGADO; A COPIA DE DADOS (SE FEITA) ESTA EM "%ARQUIVO%".
:fim
pause
