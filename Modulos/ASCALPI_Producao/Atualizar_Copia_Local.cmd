@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
rem Copia o modulo ASCALPI Producao (codigo, telas e atalhos) para a pasta de teste local.
rem NUNCA copia nem apaga a pasta "dados" (banco, modelos e documentos ficam onde estao).
set "AQUI=%~dp0"
set "DESTINO=%~1"
if "%DESTINO%"=="" set "DESTINO=D:\PROGRAMAS\ASCALPI_Project\Modulos\ASCALPI_Producao"
echo ORIGEM : %AQUI%
echo DESTINO: %DESTINO%
choice /C SN /M "Copiar agora (a pasta dados do destino nao e tocada)"
if errorlevel 2 goto fim
if exist "%DESTINO%\dados\ascalpi_producao.db" (
  for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CARIMBO=%%d"
  echo BACKUP DOS DADOS ANTES DE ATUALIZAR: "%DESTINO%\backup_dados_!CARIMBO!"
  robocopy "%DESTINO%\dados" "%DESTINO%\backup_dados_!CARIMBO!" /E /R:1 /W:1 /NP /NFL /NDL >nul
  if errorlevel 8 (
    echo FALHA NO BACKUP. NADA FOI ATUALIZADO.
    goto fim
  )
)
robocopy "%AQUI%." "%DESTINO%" /E /XD dados backup_dados_* __pycache__ .git /XF *.db *.db-wal *.db-shm config.json ~*.tmp /R:1 /W:1 /NP /NFL /NDL
if errorlevel 8 (
  echo FALHA NA COPIA. CONFIRA SE O ASCALPI PRODUCAO ESTA FECHADO E TENTE DE NOVO.
  goto fim
)
echo.
echo COPIA CONCLUIDA.
echo O banco e atualizado sozinho na 1a abertura (as migracoes nao apagam nada; o backup fica ao lado).
echo 1. Primeira vez: rode "%DESTINO%\Importar_Legado.cmd" (mostra a PREVIA e pede confirmacao).
echo 2. Depois: rode "%DESTINO%\Iniciar_ASCALPI_Producao.cmd".
echo 3. Testes leves: "%DESTINO%\Testar.cmd".
:fim
pause
