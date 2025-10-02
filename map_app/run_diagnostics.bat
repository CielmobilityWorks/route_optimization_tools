@echo off
echo ==================================================
echo  run_diagnostics.bat - Environment & path checks
echo ==================================================

echo Current directory:
cd

echo.
echo Checking expected virtualenv path (parent folder ..\.venv\Scripts\activate)
if exist "..\.venv\Scripts\activate" (
    echo Found: ..\.venv\Scripts\activate
    echo Listing ..\.venv\Scripts\
    dir "..\.venv\Scripts\" /b
) else (
    echo NOT FOUND: ..\.venv\Scripts\activate
)

echo.
echo Checking requirements.txt in current folder:
if exist "requirements.txt" (
    echo Found requirements.txt
) else (
    echo NOT FOUND: requirements.txt
)

echo.
echo Checking Python on PATH:
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 'python' not found on PATH. Trying 'py -3'...
    where py >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo No Python launcher found (py) either.
    ) else (
        echo Found 'py'. Version:
        py -3 --version
    )
) else (
    python --version
)

echo.
echo Attempting to expand and show absolute path of ..\.venv\Scripts\activate
for %%I in ("..\.venv\Scripts\activate") do echo %%~fI

echo.
echo Diagnostics complete.
pause
