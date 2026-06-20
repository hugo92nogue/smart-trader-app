@echo off
echo ========================================
echo   SMART TRADER APP - Backend Python
echo ========================================
cd /d "%~dp0backend"
echo Iniciando servidor en http://localhost:8000
echo.
py -3.11 -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
pause
