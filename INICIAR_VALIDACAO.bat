@echo off
REM Abre a pagina de coordenacao da validacao autonoma do AgroIA-RMC.
REM Sobe o servidor local (so neste PC, 127.0.0.1) e abre o navegador.
REM Para encerrar, feche a janela "Validacao AgroIA".

cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo ========================================
echo   AgroIA-RMC - Validacao autonoma
echo ========================================
echo.
echo A pagina abre no navegador em alguns segundos.
echo Mantenha esta janela aberta enquanto usar a pagina.
echo.

title Validacao AgroIA
python -m validacao.coordenacao.app --abrir
pause
