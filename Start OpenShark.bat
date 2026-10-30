@echo off
title OpenShark
cd /d "%~dp0"
if exist "%~dp0OpenShark\dist\OpenShark.exe" (
    start "" "%~dp0OpenShark\dist\OpenShark.exe"
) else (
    start "" pythonw "%~dp0OpenShark\main.py"
)
exit

