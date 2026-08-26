@echo off
title MAS Supply Chain — Stopping Services
color 0C

echo ============================================================
echo   MAS Poultry Supply Chain — Stopping Services
echo ============================================================
echo.

echo Menghentikan uvicorn (FastAPI)...
taskkill /f /im python.exe /fi "WINDOWTITLE eq MAS*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000"') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo   Done.

echo Menghentikan Ollama...
taskkill /f /im ollama.exe >nul 2>&1
echo   Done.

echo.
echo Semua service dihentikan.
pause
