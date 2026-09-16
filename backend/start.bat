@echo off
title MAS Supply Chain — Startup
color 0A

echo ============================================================
echo   MAS Poultry Supply Chain — Starting Services
echo ============================================================
echo.

REM ── 1. Cek apakah Ollama sudah terinstall ──────────────────
where ollama >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama tidak ditemukan!
    echo         Download di: https://ollama.com/download
    pause
    exit /b 1
)

REM ── 2. Cek apakah Ollama sudah berjalan ────────────────────
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [1/3] Menjalankan Ollama server...
    start "Ollama Server" /min cmd /c "ollama serve"
    echo       Menunggu Ollama siap...
    timeout /t 4 /nobreak >nul
) else (
    echo [1/3] Ollama sudah berjalan. Skip.
)

REM ── 3. Cek apakah model sudah di-pull ──────────────────────
echo [2/3] Mengecek model LLM...
ollama list 2>nul | findstr /i "qwen3" >nul
if errorlevel 1 (
    echo       qwen3:4b belum ada. Mengunduh... (butuh beberapa menit)
    ollama pull qwen3:4b
) else (
    echo       qwen3:4b  OK
)

ollama list 2>nul | findstr /i "llama3.1" >nul
if errorlevel 1 (
    echo       llama3.1:8b belum ada. Mengunduh... (butuh beberapa menit)
    ollama pull llama3.1:8b
) else (
    echo       llama3.1:8b  OK
)

REM ── 4. Jalankan FastAPI backend ─────────────────────────────
echo [3/3] Menjalankan FastAPI backend di http://localhost:8000 ...
echo.
echo ============================================================
echo   Semua service berjalan!
echo   Backend API : http://localhost:8000
echo   Docs        : http://localhost:8000/docs
echo   Tutup jendela ini untuk menghentikan backend.
echo ============================================================
echo.

cd /d "%~dp0.."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
