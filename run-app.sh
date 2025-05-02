#!/bin/bash

echo "==================================================="
echo "Softwood Lumber Board Document Checker Launcher"
echo "==================================================="
echo ""

# Make the docker check script executable
chmod +x check-docker.sh

# Check if Docker is installed and running
./check-docker.sh
if [ $? -ne 0 ]; then
    exit $?
fi

# Check if .env file exists, if not, create it from the template
if [ ! -f .env ]; then
    echo ".env file not found. Let's set up your API keys now."
    echo ""
    
    read -p "Enter your OpenAI API key: " OPENAI_KEY
    read -p "Enter your Gemini API key: " GEMINI_KEY
    read -p "Enter your LlamaParse API key: " LLAMA_KEY
    
    echo "# API Keys" > .env
    echo "OPENAI_API_KEY=${OPENAI_KEY}" >> .env
    echo "GEMINI_API_KEY=${GEMINI_KEY}" >> .env
    echo "LLAMA_CLOUD_API_KEY=${LLAMA_KEY}" >> .env
    
    echo ""
    echo "API keys saved to .env file."
    echo ""
fi

echo "Building Docker container (this may take a few minutes the first time)..."
docker-compose build

echo ""
echo "Starting Softwood Lumber Board Document Checker..."
echo ""
echo "The application will be available at http://localhost:8501"
echo "Press Ctrl+C when you're finished to stop the application."
echo ""

# Attempt to open browser automatically (works on macOS and many Linux distros)
if [ "$(uname)" == "Darwin" ]; then
    # macOS
    open http://localhost:8501
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    # Linux
    if command -v xdg-open > /dev/null; then
        xdg-open http://localhost:8501 &
    elif command -v gnome-open > /dev/null; then
        gnome-open http://localhost:8501 &
    fi
fi

docker-compose up

echo ""
echo "Application stopped."
