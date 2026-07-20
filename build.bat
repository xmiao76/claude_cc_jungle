@echo off
REM ==========================================================================
REM  Jungle board game - Windows build script
REM  Output: release\jungle_game.exe (standalone, no Python needed)
REM          release\jungle_game.zip (exe + README for distribution)
REM
REM  Usage:  build.bat
REM  Uses a local venv if one exists, otherwise the Python on PATH.
REM ==========================================================================
setlocal

echo.
echo =========================================
echo  Jungle Board Game - Build
echo =========================================
echo.

if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat

REM Ensure assets exist (fresh checkout / clean build).
if not exist gui\assets\pieces\lion_blue.png (
    echo [0/5] Generating assets...
    python generate_assets.py || (echo ERROR: asset generation failed & exit /b 1)
)

echo [1/5] Running tests...
python -m pytest tests\ -q
if errorlevel 1 (
    echo.
    echo ERROR: Tests failed. Fix failures before packaging.
    exit /b 1
)
echo   Tests passed.
echo.

echo [2/5] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist jungle_game.spec del /q jungle_game.spec
echo   Done.
echo.

echo [3/5] Packaging with PyInstaller...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name jungle_game ^
    --icon gui\assets\tiles\icon.ico ^
    --add-data "gui\assets;gui\assets" ^
    main.py
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller packaging failed.
    exit /b 1
)
echo   Packaging complete.
echo.

echo [4/5] Copying to release folder...
if not exist release mkdir release
copy /Y dist\jungle_game.exe release\jungle_game.exe >nul
if errorlevel 1 (
    echo ERROR: Could not copy exe to release folder.
    exit /b 1
)
echo   Done.
echo.

echo [5/5] Creating distribution zip...
if exist release\jungle_game.zip del /q release\jungle_game.zip
powershell -NoProfile -Command "Compress-Archive -Path 'release\jungle_game.exe','release\README.md' -DestinationPath 'release\jungle_game.zip' -Force"
if errorlevel 1 (
    echo ERROR: Could not create release\jungle_game.zip.
    exit /b 1
)
echo   Zip created: release\jungle_game.zip
echo.

echo =========================================
echo  BUILD SUCCESSFUL
echo =========================================
echo   Output: release\jungle_game.exe
echo   Zip:    release\jungle_game.zip
echo   Docs:   release\README.md
echo.
echo  Now test the packaged executable:
echo    release\jungle_game.exe
echo.
endlocal
