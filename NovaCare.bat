@echo off
title NovaCare System Care Suite 2026
cd /d "%~dp0"
if exist "NovaCare.exe" (
    start "" "NovaCare.exe" %*
) else if exist "dist\NovaCare.exe" (
    start "" "dist\NovaCare.exe" %*
) else (
    start "" pythonw main.py %*
)
exit
