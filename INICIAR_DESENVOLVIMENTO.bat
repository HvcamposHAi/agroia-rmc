@echo off
REM Script para iniciar o sistema AgroIA-RMC em desenvolvimento
REM Abre 2 terminals: um para backend, outro para frontend

echo.
echo ========================================
echo  Sistema AgroIA-RMC - Inicializador
echo ========================================
echo.

cd /d "%~dp0"

REM Verificar se estamos no diretorio correto
if not exist api\main.py (
    echo ERRO: Arquivo api\main.py nao encontrado!
    echo Execute este script a partir da pasta raiz do projeto.
    pause
    exit /b 1
)

echo [1] Iniciando Backend (FastAPI)...
echo.
start "AgroIA-RMC Backend" cmd /k "python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak

echo [2] Iniciando Frontend (React/Vite)...
echo.
start "AgroIA-RMC Frontend" cmd /k "cd agroia-frontend && npm run dev"

echo.
echo ========================================
echo Sistema iniciando...
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
echo Pressione Ctrl+C em cada janela para parar.
echo.

pause
