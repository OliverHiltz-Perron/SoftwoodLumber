@echo off
echo Checking Docker installation...

docker --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Docker is not installed or not in your PATH.
    echo Please download and install Docker Desktop from:
    echo https://www.docker.com/products/docker-desktop/
    echo.
    echo After installation, please restart your computer and try again.
    echo.
    pause
    exit /b 1
)

echo Docker is installed. Checking if Docker is running...

docker info > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Docker is installed but not running.
    echo Please start Docker Desktop and try again.
    echo Look for the Docker icon in your system tray and make sure it's running.
    echo.
    pause
    exit /b 1
)

echo Docker is running properly! You're good to go.
exit /b 0
