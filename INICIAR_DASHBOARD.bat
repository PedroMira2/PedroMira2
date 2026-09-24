@echo off
title GitHub AI Activity Hub - Inicializador
chcp 65001 >nul
cls

echo ============================================================
echo        🛡️ GITHUB AI ACTIVITY HUB - INICIALIZADOR
echo ============================================================
echo.
echo [*] Verificando dependencias essenciais...
python -m pip install requests --quiet >nul 2>&1

echo [*] Iniciando GitHub AI Activity Hub e Dashboard Web...
if exist "GitHubActivityHub.exe" (
    start "" "GitHubActivityHub.exe"
) else (
    start "" pythonw dashboard.py
)

echo.
echo [OK] O Dashboard Web esta abrindo no seu navegador padrao!
echo [URL] http://127.0.0.1:5050
echo.
timeout /t 3 >nul
exit
