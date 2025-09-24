@echo off
setlocal
set SCRIPT_DIR=%~dp0

call "%SCRIPT_DIR%env.bat"
call "%SCRIPT_DIR%dev-run.bat" %*
endlocal
