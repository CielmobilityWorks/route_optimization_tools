@echo off
setlocal

echo ==================================================
echo  First-time setup + run for Flask Map Application
echo ==================================================

REM Determine python command. Try python, py -3, common install paths, then ask user.
set "PYCMD_CMD="
set "PYCMD_ARGS="

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PYCMD_CMD=python"
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PYCMD_CMD=py"
        set "PYCMD_ARGS=-3"
    )
)

if not defined PYCMD_CMD (
    echo Trying common Python install locations...
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYCMD_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
    if not defined PYCMD_CMD if exist "%LocalAppData%\Programs\Python\Python310\python.exe" set "PYCMD_CMD=%LocalAppData%\Programs\Python\Python310\python.exe"
    if not defined PYCMD_CMD if exist "%ProgramFiles%\Python39\python.exe" set "PYCMD_CMD=%ProgramFiles%\Python39\python.exe"
    if not defined PYCMD_CMD if exist "C:\Python39\python.exe" set "PYCMD_CMD=C:\Python39\python.exe"
)

if not defined PYCMD_CMD (
    set /p "PYCMD_CMD=Python not found. Enter full path to python.exe (or press Enter to abort): "
    if "%PYCMD_CMD%"=="" (
        echo Aborted: Python is required.
        pause
        exit /b 1
    )
)

echo Using Python command: %PYCMD_CMD% %PYCMD_ARGS%

REM verify python works
if defined PYCMD_ARGS (
    "%PYCMD_CMD%" %PYCMD_ARGS% --version >nul 2>nul
) else (
    "%PYCMD_CMD%" --version >nul 2>nul
)
if %ERRORLEVEL% neq 0 (
    echo Error: the selected Python command did not respond correctly. Please check the path and try again.
    pause
    exit /b 1
)

REM Virtual environment location (parent folder .venv)
set "VENV_PATH=..\.venv"
set "ACTIVATE=%VENV_PATH%\Scripts\activate"

if not exist "%ACTIVATE%" (
    echo Virtual environment not found at %VENV_PATH%.
    echo Creating virtual environment...
    %PYCMD% -m venv "%VENV_PATH%"
    if %ERRORLEVEL% neq 0 (
        echo Error: Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Found existing virtual environment at %VENV_PATH%.
    echo This script will activate it and ensure dependencies are installed.
)

echo Activating virtual environment...
call "%ACTIVATE%"
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

REM After activation, prefer the venv's python
set "PYCMD=python"

echo Upgrading pip, setuptools, wheel...
%PYCMD% -m pip install --upgrade pip setuptools wheel
if %ERRORLEVEL% neq 0 (
    echo Warning: Failed to upgrade pip. Continuing...
)

REM Install dependencies
if exist "requirements.txt" (
    echo Installing dependencies from requirements.txt...
    %PYCMD% -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo Error: Failed to install dependencies from requirements.txt
        pause
        exit /b 1
    )
) else (
    echo requirements.txt not found. Checking and installing common packages...
    %PYCMD% -c "import sys,subprocess; mapping={'flask':'flask','pandas':'pandas','numpy':'numpy','requests':'requests','ortools':'ortools','dotenv':'python-dotenv'}; miss=[]; [miss.append(mapping[k]) for k in mapping if subprocess.call([sys.executable,'-c',f'import {k}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)!=0]; print(' '.join(miss))" > .missing_pkgs.txt
    for /f "usebackq delims=" %%p in (.missing_pkgs.txt) do set "MISSING=%%p"
    del .missing_pkgs.txt 2>nul
    if defined MISSING (
        echo Missing packages detected: %MISSING%
        echo Installing missing packages...
        for %%g in (%MISSING%) do %PYCMD% -m pip install %%g
        if %ERRORLEVEL% neq 0 (
            echo Error: Failed to install one or more packages.
            pause
            exit /b 1
        )
    ) else (
        echo All dependencies are already satisfied.
    )
)

echo Starting Flask application...
echo You can access the app at http://127.0.0.1:5000
%PYCMD% app.py

echo Application stopped.
endlocal
pause
