@echo off
title NovaCare System Care Suite 2026
cd /d "%~dp0"
if exist "NovaCare.lnk" (
    start "" "NovaCare.lnk"
) else (
    start "" pythonw main.py
)
exit
