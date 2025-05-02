@echo off
echo ===================================================
echo Softwood Lumber Board Document Checker Launcher
echo ===================================================
echo.

REM Check if Docker is installed and running
call check-docker.bat
if %errorlevel% neq 0 (
    exit /b %errorlevel%
)

REM Check if .env file exists, if not, create it from the template
if not exist .env (
    echo .env file not found. Let's set up your API keys now.
    echo.
    
    set /p OPENAI_KEY="Enter your OpenAI API key: "
    set /p GEMINI_KEY="Enter your Gemini API key: "
    set /p LLAMA_KEY="Enter your LlamaParse API key: "
    
    echo # API Keys > .env
    echo OPENAI_API_KEY=%OPENAI_KEY% >> .env
    echo GEMINI_API_KEY=%GEMINI_KEY% >> .env
    echo LLAMA_CLOUD_API_KEY=%LLAMA_KEY% >> .env
    
    echo.
    echo API keys saved to .env file.
    echo.
)

echo Building Docker container (this may take a few minutes the first time)...
docker-compose build

echo.
echo Starting Softwood Lumber Board Document Checker...
echo.
echo The application will be available at http://localhost:8501
echo When you're finished, you can close this window to stop the application.
echo.

REM Automatically open the browser
start "" http://localhost:8501

docker-compose up

echo.
echo Application stopped.
pause
