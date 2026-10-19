@echo off
title Seamless - Local Wi-Fi Device Connectivity
cd /d "%~dp0"

echo ========================================================
echo  Launching Seamless Windows Desktop Application...
echo ========================================================

python windows-app\src\main.py
pause
