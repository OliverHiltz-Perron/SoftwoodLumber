FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies required by nomic-ai/nomic-embed-text-v2-moe
RUN pip install --no-cache-dir einops

# Copy the application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/prompts

# Set environment variables for API keys (these will be overridden by .env file)
ENV OPENAI_API_KEY=""
ENV GEMINI_API_KEY=""
ENV LLAMA_CLOUD_API_KEY=""

# Expose the Streamlit port
EXPOSE 8501

# Set the command to run the Streamlit app
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
