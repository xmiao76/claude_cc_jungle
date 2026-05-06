@echo off
REM ==========================================================================
REM  Jungle board game - Windows build script
REM  Produces: release\jungle_game.exe (standalone, no Python required)
REM            release\jungle_game.zip (exe + README for distribution)
REM ==========================================================================

echo.
echo =========================================
echo  Jungle Board Game - Build Script
echo =========================================
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate venv. Run setup first:
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

REM Run tests before building
echo [1/5] Running tests...
pytest tests\ -v --tb=short -q
if errorlevel 1 (
    echo.
    echo ERROR: Tests failed. Fix failures before packaging.
    exit /b 1
)
echo   Tests passed.
echo.

REM Clean previous build artifacts
echo [2/5] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist jungle_game.spec del jungle_game.spec
echo   Done.
echo.

REM Run PyInstaller
echo [3/5] Packaging with PyInstaller...
PyInstaller ^
    --onefile ^
    --windowed ^
    --name jungle_game ^
    --add-data "gui\assets;gui\assets" ^
    --add-data "gui\assets\tiles;gui\assets\tiles" ^
    --add-data "gui\assets\pieces;gui\assets\pieces" ^
    --add-data "gui\assets\sounds;gui\assets\sounds" ^
    main.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller packaging failed.
    exit /b 1
)
echo   Packaging complete.
echo.

REM Copy exe to release folder
echo [4/5] Copying to release folder...
if not exist release mkdir release
copy /Y dist\jungle_game.exe release\jungle_game.exe
if errorlevel 1 (
    echo ERROR: Could not copy exe to release folder.
    exit /b 1
)
echo   Done.
echo.

REM Create distribution zip
echo [5/5] Creating distribution zip...
if exist release\jungle_game.zip del /q release\jungle_game.zip
powershell -NoProfile -Command "Compress-Archive -Path 'release\jungle_game.exe','release\README.txt' -DestinationPath 'release\jungle_game.zip' -Force"
if errorlevel 1 (
    echo ERROR: Could not create release\jungle_game.zip.
    exit /b 1
)
echo   Zip created: release\jungle_game.zip
echo.

echo =========================================
echo  BUILD SUCCESSFUL
echo =========================================
echo.
echo  Output: release\jungle_game.exe
echo  Zip:    release\jungle_game.zip
echo  Docs:   release\README.txt
echo.
echo  Test the packaged executable:
echo    release\jungle_game.exe
echo.
