@echo off
echo Starting Brother Label Printer...
cd /d %~dp0
python main_desktop.py
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start. Make sure dependencies are installed.
    echo Run install.bat first.
    pause
)
