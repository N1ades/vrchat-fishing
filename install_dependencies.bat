@echo off
echo Installing VRChat Fishing Bot dependencies...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python found! Installing dependencies...
echo.

REM Install dependencies using python -m pip (works even if pip is not in PATH)
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install some dependencies.
    echo Trying alternative installation for pyaudio...
    python -m pip install pipwin
    python -m pipwin install pyaudio
    python -m pip install numpy pywin32
)

echo.
echo Installation completed!
echo You can now run the bot using run_bot.bat
echo.
pause