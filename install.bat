@echo off
echo ========================================
echo  Installing Backend Python dependencies
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
echo  Installing Frontend npm dependencies
echo ========================================
cd /d %~dp0frontend
npm install
if errorlevel 1 (
    echo.
    echo ERROR: npm install failed. Make sure Node.js is installed.
    pause
    exit /b 1
)
echo.
echo ========================================
echo  All dependencies installed successfully!
echo  Now run: start.bat
echo ========================================
pause
