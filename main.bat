@echo off
REM ----------------------------------------------------
REM Run Snowflake Lineage Explorer Streamlit App
REM ----------------------------------------------------

REM Set the path to your Python virtual environment
SET VENV_PATH=C:\Users\dj297516\PycharmProjects\Record-level-lineage\venv

REM Activate the virtual environment
IF EXIST "%VENV_PATH%\Scripts\activate.bat" (
    call "%VENV_PATH%\Scripts\activate.bat"
) ELSE (
    echo ERROR: Virtual environment not found at "%VENV_PATH%"
    pause
    exit /b
)

REM Navigate to project directory
cd /d C:\Users\dj297516\PycharmProjects\Record-level-lineage

REM Run Streamlit app
streamlit run main.py

REM Keep the terminal open after closing
pause
