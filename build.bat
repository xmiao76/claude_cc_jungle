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

REM The native engine is required for a release build, not optional.
REM ai\native.py falls back to the Python engine when the extension is missing,
REM which is right for a developer checkout but wrong for a shipped build: the
REM fallback is roughly 500 Elo weaker and ten plies shallower, and nothing in
REM the running game would say so. Fail loudly instead.
where cargo >nul 2>&1
if errorlevel 1 (
    echo ERROR: cargo is not on PATH, so the native engine cannot be built.
    echo   Install Rust from https://rustup.rs and re-run.
    echo   Building without it would silently ship the slow fallback engine.
    exit /b 1
)

echo [1/7] Building the native engine...
pushd rust
cargo build --release -p jungle-py
if errorlevel 1 (
    popd
    echo ERROR: cargo build failed.
    exit /b 1
)
popd
copy /Y rust\target\release\jungle_native.dll jungle_native.pyd >nul
if errorlevel 1 (
    echo ERROR: could not copy the built extension to jungle_native.pyd
    exit /b 1
)
%PY% -c "import jungle_native, sys; sys.exit(0 if jungle_native.perft(jungle_native.Position(), 4) == 260099 else 1)"
if errorlevel 1 (
    echo ERROR: the built extension does not import or fails its perft check.
    exit /b 1
)
echo   Native engine built and verified.
echo.

REM The Rust suite holds the rules contract: the frozen perft counts and the
REM ten-thousand-position golden corpus the engine is checked against.
echo [2/7] Running Rust tests...
pushd rust
cargo test --release
if errorlevel 1 (
    popd
    echo ERROR: Rust tests failed. Fix failures before packaging.
    exit /b 1
)
popd
echo   Rust tests passed.
echo.

REM Run tests before building. Options come from pyproject.toml.
echo [3/7] Running Python tests...
%PY% -m pytest tests
if errorlevel 1 (
    echo.
    echo ERROR: Tests failed. Fix failures before packaging.
    exit /b 1
)
echo   Tests passed.
echo.

REM Clean previous build artifacts
echo [4/7] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist jungle_game.spec del /q jungle_game.spec
echo   Done.
echo.

REM Package. One --add-data for gui\assets is enough: PyInstaller copies the
REM directory tree, so the old per-subfolder arguments bundled tiles, pieces and
REM sounds three times each. --icon brands the exe (see generate_assets.py, which
REM writes icon.ico next to icon.png).
REM --hidden-import jungle_native: the extension is imported inside a try/except
REM in ai\native.py so the game degrades gracefully without it, and naming it
REM explicitly guarantees PyInstaller bundles it rather than deciding it is
REM optional. --noupx because UPX corrupts some native binaries, and a corrupted
REM extension here would fail its import and silently drop us to the slow engine.
echo [5/7] Packaging with PyInstaller...
%PY% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --noupx ^
    --name jungle_game ^
    --icon "gui\assets\tiles\icon.ico" ^
    --add-data "gui\assets;gui\assets" ^
    --hidden-import jungle_native ^
    main.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller packaging failed.
    exit /b 1
)
echo   Packaging complete.
echo.

REM Copy exe to release folder
echo [6/7] Copying to release folder...
if not exist release mkdir release
copy /Y dist\jungle_game.exe release\jungle_game.exe
if errorlevel 1 (
    echo ERROR: Could not copy exe to release folder.
    exit /b 1
)
echo   Done.
echo.

REM Create distribution zip
echo [7/7] Creating distribution zip...
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
