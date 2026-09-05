@echo off
REM Starts Ripple. Double-click this file.
REM It opens a black window and then your browser. Leave the black window
REM open while you use Ripple; closing it is how you stop Ripple.

cd /d "%~dp0"

REM Windows can answer to "python" more than once - a real install, a shim for
REM a different version, a zero-byte Microsoft Store stub - and only the one
REM Ripple's packages were installed into can start it. Picking the first name
REM that answers printed a Python traceback about uvicorn on this very machine.
REM So each candidate is asked whether it can actually load them.
set "PY="
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -c "import uvicorn, fastapi, sqlglot" >nul 2>nul && set "PY=.venv\Scripts\python.exe"
)
for %%P in ("python" "py -3.12" "py -3" "py") do (
  if not defined PY (
    %%~P -c "import uvicorn, fastapi, sqlglot" >nul 2>nul && set "PY=%%~P"
  )
)

if not defined PY goto nothing_installed

echo Starting Ripple. It prints the address to open, and opens your browser.
echo Leave this window open. Closing it stops Ripple.
echo.
%PY% run.py
if errorlevel 1 pause
exit /b

:nothing_installed
echo.
echo Ripple's building blocks are not installed on this machine yet.
echo Nothing is broken - this is the one step that has to happen first.
echo.
echo Open a Command Prompt, run the line below, then double-click this again:
echo.
echo     python -m pip install --user -r "%~dp0requirements.txt"
echo.
pause
exit /b 1
