#!/bin/bash

echo "Checking Docker installation..."

if ! command -v docker &> /dev/null; then
    echo ""
    echo "ERROR: Docker is not installed or not in your PATH."
    echo "Please download and install Docker Desktop from:"
    echo "https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "After installation, please restart your computer and try again."
    echo ""
    exit 1
fi

echo "Docker is installed. Checking if Docker is running..."

if ! docker info &> /dev/null; then
    echo ""
    echo "ERROR: Docker is installed but not running."
    echo "Please start Docker Desktop and try again."
    echo ""
    exit 1
fi

echo "Docker is running properly! You're good to go."
exit 0
