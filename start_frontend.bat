@echo off
echo ========================================
echo   SMART TRADER APP - Frontend React
echo ========================================
cd /d "%~dp0frontend"
echo Instalando dependencias...
npm install --legacy-peer-deps
echo.
echo Iniciando en http://localhost:3000
echo.
npm start
pause
