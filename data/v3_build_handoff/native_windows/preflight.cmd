@echo off
setlocal

call "%~dp0setup_jdk8.cmd"
if errorlevel 1 exit /b %ERRORLEVEL%

set "HANDOFF_ROOT=%~dp0.."

where py >nul 2>nul
if not errorlevel 1 (
  py "%HANDOFF_ROOT%\scripts\verify_bundle.py" --config "%HANDOFF_ROOT%\handoff_config.json"
  if errorlevel 1 exit /b %ERRORLEVEL%
  py "%HANDOFF_ROOT%\scripts\replay_builds.py" --config "%HANDOFF_ROOT%\handoff_config.json" --check-only
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if errorlevel 1 (
  echo STOP: Neither the py launcher nor python was found.
  exit /b 1
)

python "%HANDOFF_ROOT%\scripts\verify_bundle.py" --config "%HANDOFF_ROOT%\handoff_config.json"
if errorlevel 1 exit /b %ERRORLEVEL%
python "%HANDOFF_ROOT%\scripts\replay_builds.py" --config "%HANDOFF_ROOT%\handoff_config.json" --check-only
exit /b %ERRORLEVEL%
