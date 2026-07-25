@echo off
REM ==========================================================================
REM  Jungle board game - Windows build script
REM  Produces: release\jungle_game.exe (standalone, no Python required)
REM            release\jungle_game.zip (exe + README for distribution)
REM ==========================================================================
setlocal

echo.
echo =========================================
echo  Jungle Board Game - Build Script
echo =========================================
echo.

REM Prefer a project venv, but fall back to whatever python is on PATH.
REM The old script called `venv\Scripts\activate.bat` unconditionally and aborted
REM if it was missing, which meant the build could not run on a machine where the
REM dependencies were installed globally.
if exist venv\Scripts\activate.bat (
    echo Using project venv.
    call venv\Scripts\activate.bat
) else (
    echo No venv found - using python from PATH.
)

set PY=python
%PY% -c "import pygame, PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo ERROR: pygame and/or PyInstaller are not importable with %PY%.
    echo   python -m pip install -r requirements.txt
    exit /b 1
)

REM Run tests before building. Options come from pyproject.toml.
echo [1/5] Running tests...
%PY% -m pytest tests
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
if exist jungle_game.spec del /q jungle_game.spec
echo   Done.
echo.

REM Package. One --add-data for gui\assets is enough: PyInstaller copies the
REM directory tree, so the old per-subfolder arguments bundled tiles, pieces and
REM sounds three times each. --icon brands the exe (see generate_assets.py, which
REM writes icon.ico next to icon.png).
echo [3/5] Packaging with PyInstaller...
%PY% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --name jungle_game ^
    --icon "gui\assets\tiles\icon.ico" ^
    --add-data "gui\assets;gui\assets" ^
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
