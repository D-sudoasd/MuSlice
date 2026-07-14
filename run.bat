@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"

rem Prefer real installs over the Windows Store stub.
where py >nul 2>&1 && (
  py -3 -m muslice %*
  goto :check
)
where python >nul 2>&1 && (
  python -m muslice %*
  goto :check
)
echo Python not found. Install Python 3.10+ and retry.
pause
exit /b 1

:check
if errorlevel 1 (
  echo.
  echo MuSlice failed to start. Install deps first:
  echo   py -3 -m pip install -r requirements.txt
  echo   or: py -3 -m pip install -e .
  pause
)
endlocal
