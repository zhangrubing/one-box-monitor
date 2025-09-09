@echo off
setlocal
REM Run FastAPI app with current environment (no venv creation)

REM Ensure we run from the repo root (this script's directory)
cd /d "%~dp0"

REM Default secret if not provided
if not defined APP_SECRET set "APP_SECRET=dev_secret_change_me"

REM Pick a Python launcher available on PATH
set "PYCMD=python"
where %PYCMD% >nul 2>nul
if errorlevel 1 (
  set "PYCMD=py"
  where %PYCMD% >nul 2>nul
  if errorlevel 1 (
    echo Python not found. Please ensure Python is on PATH.^& echo.
    exit /b 1
  )
)

%PYCMD% -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

endlocal

