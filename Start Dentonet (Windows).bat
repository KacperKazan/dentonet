@echo off
cd /d "%~dp0"
title FORUM DENTONET

where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo Instaluje uv ^(menedzer Pythona^), prosze czekac...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

uv run python app.py

echo.
echo Forum zostalo zamkniete. Mozesz zamknac to okno.
pause
