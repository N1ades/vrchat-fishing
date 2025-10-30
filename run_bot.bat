@echo off
title VRChat Fishing Bot
echo Starting VRChat Fishing Bot...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please run install_dependencies.bat first.
    pause
    exit /b 1
)

REM Check if the main script exists
if not exist "vrchat_fishing_bot.py" (
    echo ERROR: vrchat_fishing_bot.py not found!
    echo Make sure you are running this from the correct directory.
    pause
    exit /b 1
)

echo Starting the bot...
echo.
echo IMPORTANT REMINDERS:
echo - Make sure VRChat is running
echo - Ensure you are in a fishing world
echo - Check that your microphone can capture VRChat audio
echo.
echo Starting in 3 seconds...
timeout /t 3 /nobreak >nul

REM Run the bot
python vrchat_fishing_bot.py

echo.
echo Bot has been closed.
pause