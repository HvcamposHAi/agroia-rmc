@echo off
REM Script para iniciar o sistema AgroIA-RMC completo
REM Executa em 2 terminais: API (8000) + Streamlit (8501)

echo.
echo ========================================
echo   AgroIA-RMC - Sistema Completo
echo ========================================
echo.
echo [1] FastAPI rodando em: http://localhost:8000
echo [2] Streamlit rodara em: http://localhost:8501
echo.
echo Pressione ENTER para iniciar...
pause

REM Terminal 1: FastAPI
start "FastAPI - AgroIA" cmd /k "cd "%CD%" && uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"

REM Aguardar API iniciar
timeout /t 3 /nobreak

REM Terminal 2: Streamlit
start "Streamlit - AgroIA" cmd /k "cd "%CD%" && streamlit run streamlit_app.py"

echo.
echo ========================================
echo Sistema iniciado!
echo - API:      http://localhost:8000
echo - Docs:     http://localhost:8000/docs
echo - Streamlit: http://localhost:8501
echo ========================================
echo.
