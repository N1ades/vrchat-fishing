@echo off
chcp 65001 > nul
echo ============================================
echo VRChat Fishing Bot - Сборка EXE
echo ============================================
echo.

REM Проверка наличия PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller не найден. Устанавливаю...
    pip install pyinstaller
    if errorlevel 1 (
        echo Ошибка установки PyInstaller!
        pause
        exit /b 1
    )
)

echo Установка/обновление зависимостей...
pip install -r requirements.txt
if errorlevel 1 (
    echo Ошибка установки зависимостей!
    pause
    exit /b 1
)

echo.
echo Очистка старых файлов сборки...
if exist "build\exe_build" rmdir /s /q "build\exe_build"
if exist "dist" rmdir /s /q "dist"
if exist "VRChat_Fishing_Bot.spec" del /q "VRChat_Fishing_Bot.spec"

echo.
echo Сборка EXE файла...
echo Это может занять несколько минут...
echo.

python -m PyInstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "VRChat_Fishing_Bot" ^
    --icon=NONE ^
    --add-data "fishing_bot_settings.json;." ^
    --hidden-import "comtypes.stream" ^
    --hidden-import "pycaw.pycaw" ^
    --hidden-import "pycaw.utils" ^
    --hidden-import "win32gui" ^
    --hidden-import "win32con" ^
    --hidden-import "win32api" ^
    --hidden-import "win32process" ^
    --hidden-import "pyaudio" ^
    --hidden-import "numpy" ^
    --hidden-import "tkinter" ^
    --collect-all "pycaw" ^
    --collect-all "comtypes" ^
    vrchat_fishing_bot.py

if errorlevel 1 (
    echo.
    echo ============================================
    echo Ошибка при сборке!
    echo ============================================
    pause
    exit /b 1
)

echo.
echo ============================================
echo Сборка завершена успешно!
echo ============================================
echo.
echo EXE файл создан: dist\VRChat_Fishing_Bot.exe
echo.
echo ВАЖНО: Скопируйте fishing_bot_settings.json
echo в ту же папку, где будет находиться EXE файл!
echo.
echo Для запуска просто запустите VRChat_Fishing_Bot.exe
echo.
pause
