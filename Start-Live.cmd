@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run Setup.ps1 first.
  pause
  exit /b 1
)
start "PokeFT8" "%~dp0.venv\Scripts\pythonw.exe" -X utf8 "%~dp0app.py" --live
