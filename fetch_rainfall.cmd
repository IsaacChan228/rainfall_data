@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fetch_rainfall.ps1" %*
exit /b %ERRORLEVEL%