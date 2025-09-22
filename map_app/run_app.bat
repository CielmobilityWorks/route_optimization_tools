@echo off
echo ==================================================
echo  Flask Map Application Starter
echo ==================================================

REM Use existing virtual environment from parent directory
echo Using existing virtual environment...
call "..\\.venv\\Scripts\\activate"

REM Check if virtual environment activation was successful
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to activate virtual environment
    echo Please make sure the virtual environment exists at ..\\.venv
    pause
    exit /b 1
)

REM Check and install dependencies
echo Checking dependencies...
python -c "import sys; import subprocess; missing = []; packages = ['flask', 'pandas', 'numpy', 'requests', 'ortools', 'dotenv']; [missing.append(pkg) for pkg in packages if subprocess.call([sys.executable, '-c', f'import {pkg}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0]; print('Missing packages:', missing) if missing else print('All dependencies satisfied'); sys.exit(1) if missing else sys.exit(0)" 2>nul

if %ERRORLEVEL% neq 0 (
    echo Some dependencies are missing. Installing from requirements.txt...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo Error: Failed to install dependencies
        echo Please check your internet connection and try again
        pause
        exit /b 1
    )
    echo Dependencies installed successfully!
) else (
    echo All dependencies are already satisfied.
)

echo Starting Flask application...
echo You can access the app at http://127.0.0.1:5000
python app.py

echo Application stopped.
pause