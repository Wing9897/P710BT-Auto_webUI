@echo off
echo ========================================
echo  Installing dependencies
echo ========================================
cd /d %~dp0backend
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)
echo.
echo ========================================
echo  All dependencies installed!
echo  Now run: start.bat
echo ========================================
pause
