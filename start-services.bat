@echo off
REM ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
REM start-services.bat - Inicia os servicos do projeto
REM ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
REM Inicia FastAPI e ARQ Worker. Redis Cloud e usado (configurado no .env).
REM
REM PREREQUISITOS:
REM   - .venv configurado (via ensure-environment.ps1 ou reabrir VSCode)
REM   - .env configurado com credenciais Redis Cloud (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD)
REM
REM USO:
REM   Duplo clique neste arquivo OU execute: start-services.bat
REM
REM ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion
chcp 65001 >nul

echo Iniciando servicos do projeto...

powershell -ExecutionPolicy Bypass -NoExit -File "%~dp0.vscode\scripts\start-services.ps1"