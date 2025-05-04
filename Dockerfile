# Use an official Python base image
FROM python:3.10-slim

# Install system dependencies (pandoc, git, build tools for torch)
RUN apt-get update && \
    apt-get install -y pandoc git build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy only requirements first for better caching
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install llama-cloud-services

# Copy the rest of the code
COPY src/ ./src/
COPY run_pipeline.sh ./
COPY assets/ ./assets/
COPY input/ ./input/
COPY README.md ./

# Make the pipeline script executable
RUN chmod +x run_pipeline.sh

# Set environment variables for API keys (documented, not hardcoded)
# Users should pass these at runtime: --env OPENAI_API_KEY=... --env LLAMA_CLOUD_API_KEY=...
ENV OPENAI_API_KEY=""
ENV LLAMA_CLOUD_API_KEY=""

# Default command: show help
CMD ["bash", "-c", "echo 'To process files, run: docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output -e OPENAI_API_KEY=your_key -e LLAMA_CLOUD_API_KEY=your_key imagename ./run_pipeline.sh' && tail -f /dev/null"] 