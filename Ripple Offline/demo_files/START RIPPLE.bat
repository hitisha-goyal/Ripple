@echo off
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
where %PY% >nul 2>nul || (
  echo.
  echo This laptop has no Python, so this folder cannot start.
  echo Use the .exe instead - see HOW-TO-RUN-THIS.md, Road A.
  echo.
  pause
  exit /b 1
)
%PY% run.py --demo
if errorlevel 1 pause
